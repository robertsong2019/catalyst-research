# Structured Output Toolkit — 深度研究

> 日期: 2026-05-30 | 主题: LLM 结构化输出工具包设计
> 来源: Tavily 搜索 (techsy.io, dev.to, glukhov.org benchmarks)

## 核心概念

### 1. 约束解码 (Constrained Decoding)
模型在生成时通过 FSM/grammar mask 限制 token 采样空间，保证输出 100% 合法。代表：XGrammar、Outlines。仅适用于本地模型。

### 2. 后置验证 + 重试 (Post-hoc Validation + Retry)
生成后用 Zod/Pydantic 验证，失败则重试或 re-prompt 附带错误信息。95% 场景够用。代表：Instructor(Python)、Vercel AI SDK(TS)。

### 3. Schema Cache
缓存 JSON Schema → 编译后的验证器（Zod schema / grammar FSM），避免每次请求重新编译。对高频相同 schema 的场景（如批量信息提取）提速显著。

### 4. Provider 自适应 (Provider-Adaptive Strategy)
自动检测 provider 能力：支持 structured output API（OpenAI）直接用原生能力，不支持则降级到 prompt-based JSON + Zod 验证。AI SDK 已实现此模式。

### 5. 流式结构化输出 (Streaming Structured Output)
`streamObject()` 在生成过程中增量解析 JSON，结合 React Server Components 实现实时 UI 更新。对复杂 schema 需要 partial schema 验证支持。

---

## 关键洞察

1. **2026 年 TypeScript 生态的最佳实践是 Vercel AI SDK + Zod**。一条 `generateObject()` 调用自动处理 provider 检测、schema 编译、验证和重试。不需要自己造轮子，但理解底层机制对构建工具包至关重要。

2. **Schema Cache 的价值在于编译成本**。Zod schema 编译本身很快，但如果你在用 constrained decoding（XGrammar），grammar 编译可能需要数百毫秒。缓存这一步是必须的，不是可选优化。

3. **工具包设计应分层**：底层是 Provider Adapter（统一接口），中层是 Schema Registry + Cache（编译缓存 + 版本管理），上层是类型安全的 API（`generateObject<T>()` 全链路类型推断）。

---

## 代码示例：StructuredLLMClient 原型

```typescript
// structured-output-toolkit/src/client.ts
import { z } from 'zod';

type Provider = 'openai' | 'anthropic' | 'generic';

interface SchemaEntry<T extends z.ZodType> {
  schema: T;
  compiled: z.ZodType<T>;
  name: string;
  version: number;
  lastUsed: number;
}

// Schema Registry with LRU cache
class SchemaCache {
  private cache = new Map<string, SchemaEntry<any>>();
  private maxSize: number;

  constructor(maxSize = 100) {
    this.maxSize = maxSize;
  }

  register<T extends z.ZodType>(name: string, schema: T): void {
    // Evict oldest if at capacity
    if (this.cache.size >= this.maxSize && !this.cache.has(name)) {
      let oldest = '';
      let oldestTime = Infinity;
      for (const [k, v] of this.cache) {
        if (v.lastUsed < oldestTime) {
          oldestTime = v.lastUsed;
          oldest = k;
        }
      }
      this.cache.delete(oldest);
    }

    const existing = this.cache.get(name);
    this.cache.set(name, {
      schema,
      compiled: schema, // Zod schemas ARE validators, no separate compile step
      name,
      version: existing ? existing.version + 1 : 1,
      lastUsed: Date.now(),
    });
  }

  get<T extends z.ZodType>(name: string): SchemaEntry<T> | undefined {
    const entry = this.cache.get(name);
    if (entry) entry.lastUsed = Date.now();
    return entry;
  }

  get size() { return this.cache.size; }
}

// Provider-adaptive structured output client
class StructuredLLMClient {
  private cache = new SchemaCache();

  constructor(private provider: Provider) {}

  registerSchema<T extends z.ZodType>(name: string, schema: T): this {
    this.cache.register(name, schema);
    return this;
  }

  async generate<T extends z.ZodType>(
    schemaName: string,
    prompt: string,
    retries = 2,
  ): Promise<z.infer<T>> {
    const entry = this.cache.get<T>(schemaName);
    if (!entry) throw new Error(`Schema "${schemaName}" not registered`);

    const jsonSchema = zodToJsonSchema(entry.schema);

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const raw = await this.callProvider(prompt, jsonSchema);
        return entry.schema.parse(raw) as z.infer<T>;
      } catch (err) {
        if (attempt === retries) throw err;
        // Re-prompt with error context
        prompt += `\n\nPrevious attempt failed: ${err}. Try again.`;
      }
    }
    throw new Error('Unreachable');
  }

  private async callProvider(prompt: string, jsonSchema: object): Promise<unknown> {
    // Provider-adaptive strategy
    if (this.provider === 'openai') {
      // Use native structured output API
      const resp = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model: 'gpt-4o',
          messages: [{ role: 'user', content: prompt }],
          response_format: { type: 'json_schema', json_schema: { name: 'output', schema: jsonSchema } },
        }),
      });
      const data = await resp.json();
      return JSON.parse(data.choices[0].message.content);
    }

    // Fallback: prompt-based JSON extraction
    const augmentedPrompt = `${prompt}\n\nRespond with valid JSON matching this schema:\n${JSON.stringify(jsonSchema)}`;
    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': process.env.ANTHROPIC_API_KEY!,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 4096,
        messages: [{ role: 'user', content: augmentedPrompt }],
      }),
    });
    const data = await resp.json();
    const text = data.content[0].text;
    // Extract JSON from markdown code blocks if present
    const match = text.match(/```(?:json)?\s*([\s\S]*?)```/) || [null, text];
    return JSON.parse(match[1]);
  }
}

// Minimal zod-to-json-schema converter (avoiding dependency for demo)
function zodToJsonSchema(schema: z.ZodType): object {
  // In production, use 'zod-to-json-schema' package
  // This is a simplified version for the prototype
  if (schema instanceof z.ZodObject) {
    const properties: Record<string, object> = {};
    const required: string[] = [];
    for (const [key, value] of Object.entries(schema.shape)) {
      properties[key] = zodToJsonSchema(value as z.ZodType);
      required.push(key);
    }
    return { type: 'object', properties, required, additionalProperties: false };
  }
  if (schema instanceof z.ZodString) return { type: 'string' };
  if (schema instanceof z.ZodNumber) return { type: 'number' };
  if (schema instanceof z.ZodBoolean) return { type: 'boolean' };
  if (schema instanceof z.ZodArray) return { type: 'array', items: zodToJsonSchema(schema.element) };
  if (schema instanceof z.ZodEnum) return { type: 'string', enum: schema.options };
  if (schema instanceof z.ZodOptional) return zodToJsonSchema(schema.unwrap());
  return {};
}

// === Usage Example ===
import { z } from 'zod';

const EventSchema = z.object({
  title: z.string(),
  date: z.string(),
  location: z.string(),
  attendees: z.number().optional(),
  sentiment: z.enum(['positive', 'neutral', 'negative']),
});

const client = new StructuredLLMClient('openai')
  .registerSchema('event', EventSchema);

// Type-safe output — TypeScript infers the shape
async function demo() {
  const event = await client.generate('event',
    'Extract the event: "AI Summit 2026 in Shanghai on June 15, expecting 500 attendees. Very exciting!"'
  );
  console.log(event.title);     // string
  console.log(event.sentiment); // 'positive' | 'neutral' | 'negative'
}

demo().catch(console.error);
```

---

## 与现有项目关联

| 项目 | 关联 |
|------|------|
| **openclaw-langgraph-bridge** | Supervisor 路由可用 SchemaCache 缓存路由 schema，减少重复编译 |
| **agent-context-store** | snapshot 的 schema 验证可用此工具包替代手写 JSON.parse |
| **prompt-router** | 路由决策本身就是结构化输出场景，天然适配 |
| **better-ralph-core** | PRD story 解析 → 结构化输出 |

---

## 下一步行动

1. **在 `lab/structured-output-toolkit/` 创建项目**，以上述原型为基础，补全：
   - 完整的 `zod-to-json-schema` 集成（用成熟包替代 demo 版本）
   - Provider 抽象层（支持 OpenAI / Anthropic / Gemini）
   - Schema 版本管理（schema evolve 时自动 invalidate cache）
   - 单元测试目标：≥50 tests

2. **性能基准**：对比原生 API 调用 vs 工具包的开销（应 <5% overhead）

3. **发布为 npm 包**，与 agent-context-store 一起作为 agent 基础设施

---

## 参考资料

- [8 LLM Structured Output Libraries Ranked (2026)](https://techsy.io/en/blog/best-llm-structured-output-libraries) — 全景对比
- [Top 5 Structured Output Libraries for LLMs in 2026](https://dev.to/thedailyagent/top-5-structured-output-libraries-for-llms-in-2026-48g0) — 决策树
- [Structured output comparison across LLM providers](https://www.glukhov.org/llm-performance/benchmarks/structured-output-comparison-popular-llm-providers) — 性能基准
- [OpenAI Structured Outputs vs Zod (2026)](https://dev.to/whoffagents/openai-structured-outputs-vs-zod-which-to-use-for-llm-response-validation-in-2026-366m) — TS 最佳实践
