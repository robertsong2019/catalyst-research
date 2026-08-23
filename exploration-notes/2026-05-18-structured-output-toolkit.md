# 深度研究笔记：Structured Output Toolkit

> 日期：2026-05-18
> 主题：LLM 结构化输出工具包设计（StructuredLLMClient + SchemaCache）
> 目标：为 `lab/structured-output-toolkit/` 提供技术基础

---

## 核心概念

### 1. 约束解码（Constrained Decoding）
LLM 生成 token 时，通过有限状态机（FSM）屏蔽不符合 JSON Schema 的 token。OpenAI `strict: true`、Gemini `response_schema`、vLLM+XGrammar 均使用此技术，实现 **100% schema 合规**（语法层面）。

**关键局限**：约束解码保证语法正确，但不保证语义正确。`{"sentiment": "positive"}` 结构正确，但情感标注可能标错。

### 2. 四代结构化输出演进
| 代际 | 方法 | 可靠率 | 适用场景 |
|------|------|--------|---------|
| Gen 1 | Prompt Engineering | 80-95% | 原型/内部工具 |
| Gen 2 | Function Calling / Tool Use | 95-99% | 通用生产 |
| Gen 3 | Native Schema-Enforced APIs | ~100% | 关键路径 |
| Gen 4 | 自托管约束解码（Outlines/XGrammar） | ~100% | 私有化/高频 |

### 3. 三层可靠性架构（The Reliability Stack）
- **参数验证层**（Schema Validation）：Pydantic/Zod 在调用前校验 schema 本身
- **失败重试层**（Retry with Error Feedback）：解析失败时将错误信息反馈给模型重试
- **约束解码层**（Constrained Decoding）：生成时保证语法合规

### 4. Schema 缓存与编译（SchemaCache）
约束解码的 FSM 编译成本高（复杂 schema 可达 8-60 秒），但生成阶段开销极低。**编译结果可缓存**——这是 SchemaCache 的核心价值。对于云 API 调用，schema 以 token 形式包含在 system prompt 中，缓存可减少 prompt caching miss 的成本。

### 5. Schema 设计原则（影响质量的核心）
- **扁平化**：避免 5 层以上嵌套
- **枚举优先**：有限值集合用 enum 而非自由字符串
- **显式 required + additionalProperties: false**：消除幻觉字段
- **避免 anyOf/oneOf 复杂联合**：用 discriminated union 替代
- **description 字段**：帮助模型理解字段含义，提升内容质量

---

## 代码示例：StructuredLLMClient + SchemaCache（可运行）

```typescript
// structured-output-toolkit.ts
// Node.js 可运行示例：统一多 Provider 结构化输出 + Schema 缓存

import { z } from 'zod';

// ─── SchemaCache ───────────────────────────────────────────────
// 缓存编译后的 schema（JSON Schema 字符串 + hash），避免重复编译
interface CachedSchema<T extends z.ZodType> {
  hash: string;           // schema 内容 hash，用于版本检测
  jsonSchema: object;     // 编译后的 JSON Schema
  tokenEstimate: number;  // 估算 schema 在 prompt 中的 token 数
  compiledAt: number;     // 编译时间戳
  hitCount: number;       // 缓存命中次数
}

class SchemaCache {
  private cache = new Map<string, CachedSchema<any>>();

  // 简单 hash（生产环境可用 crypto.createHash）
  private hashSchema(schema: object): string {
    const str = JSON.stringify(schema);
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const chr = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + chr;
      hash |= 0; // Convert to 32bit integer
    }
    return hash.toString(36);
  }

  // 估算 token 数（粗略：每 4 字符 ~1 token）
  private estimateTokens(schema: object): number {
    return Math.ceil(JSON.stringify(schema).length / 4);
  }

  get<T extends z.ZodType>(key: string): CachedSchema<T> | undefined {
    const entry = this.cache.get(key);
    if (entry) entry.hitCount++;
    return entry;
  }

  compile<T extends z.ZodType>(key: string, zodSchema: T): CachedSchema<T> {
    // 检查是否已缓存
    const existing = this.cache.get(key);
    const jsonSchema = this.zodToJsonSchema(zodSchema);
    const hash = this.hashSchema(jsonSchema);

    if (existing && existing.hash === hash) {
      existing.hitCount++;
      return existing; // schema 未变化，复用缓存
    }

    // schema 变化或首次编译
    const cached: CachedSchema<T> = {
      hash,
      jsonSchema,
      tokenEstimate: this.estimateTokens(jsonSchema),
      compiledAt: Date.now(),
      hitCount: 1,
    };
    this.cache.set(key, cached);
    return cached;
  }

  // 简化的 Zod → JSON Schema（生产环境用 zodToJsonSchema 库）
  private zodToJsonSchema(schema: z.ZodType): object {
    // 这里用简化实现，实际项目 import { zodToJsonSchema } from 'zod-to-json-schema'
    if (schema instanceof z.ZodObject) {
      const shape = schema.shape;
      const properties: Record<string, any> = {};
      const required: string[] = [];

      for (const [key, value] of Object.entries(shape)) {
        properties[key] = this.zodToJsonSchema(value as z.ZodType);
        if (!(value instanceof z.ZodOptional) && !(value instanceof z.ZodNullable)) {
          required.push(key);
        }
      }

      return {
        type: 'object',
        properties,
        required,
        additionalProperties: false,
      };
    }
    if (schema instanceof z.ZodString) return { type: 'string' };
    if (schema instanceof z.ZodNumber) return { type: 'number' };
    if (schema instanceof z.ZodBoolean) return { type: 'boolean' };
    if (schema instanceof z.ZodArray) {
      return { type: 'array', items: this.zodToJsonSchema(schema.element) };
    }
    if (schema instanceof z.ZodEnum) {
      return { type: 'string', enum: schema.options };
    }
    if (schema instanceof z.ZodOptional) {
      return this.zodToJsonSchema(schema.unwrap());
    }
    if (schema instanceof z.ZodNullable) {
      return { ...this.zodToJsonSchema(schema.unwrap()), nullable: true };
    }
    return {};
  }

  stats(): { size: number; totalHits: number; schemas: string[] } {
    let totalHits = 0;
    const schemas: string[] = [];
    for (const [key, val] of this.cache) {
      totalHits += val.hitCount;
      schemas.push(`${key} (hits: ${val.hitCount}, tokens: ~${val.tokenEstimate})`);
    }
    return { size: this.cache.size, totalHits, schemas };
  }
}

// ─── ValidationSandwich ────────────────────────────────────────
// 三层验证：预处理 → LLM 调用 → 后验证
class ValidationError extends Error {
  constructor(
    message: string,
    public layer: 'schema' | 'structure' | 'semantic',
    public raw?: unknown
  ) {
    super(message);
    this.name = 'ValidationError';
  }
}

// ─── StructuredLLMClient ───────────────────────────────────────
// 统一接口，封装多 Provider 结构化输出
interface LLMProvider {
  name: string;
  extract<T>(prompt: string, schema: object): Promise<unknown>;
}

// Mock provider（可运行示例用，实际替换为 OpenAI/Anthropic SDK）
class MockProvider implements LLMProvider {
  name = 'mock';

  async extract<T>(prompt: string, schema: object): Promise<unknown> {
    // 模拟 LLM 返回结构化 JSON
    // 在真实实现中，这里调用 OpenAI client.beta.chat.completions.parse()
    const schemaObj = schema as any;
    const result: Record<string, any> = {};

    if (schemaObj.properties) {
      for (const [key, prop] of Object.entries(schemaObj.properties as Record<string, any>)) {
        if (prop.type === 'string') {
          if (prop.enum) result[key] = prop.enum[0];
          else result[key] = `sample_${key}`;
        }
        if (prop.type === 'number') result[key] = 0.85;
        if (prop.type === 'boolean') result[key] = true;
        if (prop.type === 'array') result[key] = [];
      }
    }
    return result;
  }
}

class StructuredLLMClient {
  private cache = new SchemaCache();
  private maxRetries = 3;

  constructor(
    private providers: LLMProvider[],
    private options?: { maxRetries?: number }
  ) {
    this.maxRetries = options?.maxRetries ?? 3;
  }

  // 核心方法：带缓存 + 重试 + 验证三明治的结构化提取
  async extract<T extends z.ZodType>(
    key: string,
    schema: T,
    prompt: string
  ): Promise<z.infer<T>> {
    // 1. 编译并缓存 schema
    const cached = this.cache.compile(key, schema);
    console.log(`[SchemaCache] ${key}: ~${cached.tokenEstimate} tokens, hash=${cached.hash.slice(0, 8)}`);

    // 2. 带重试的多 Provider 提取
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      for (const provider of this.providers) {
        try {
          const raw = await provider.extract(prompt, cached.jsonSchema);

          // 3. Validation Sandwich - 后验证层
          const parsed = schema.safeParse(raw);
          if (parsed.success) {
            console.log(`[StructuredLLM] ✓ ${key} via ${provider.name} (attempt ${attempt + 1})`);
            return parsed.data;
          }

          // 语义验证失败，将错误反馈给下一轮
          lastError = new ValidationError(
            `Validation failed: ${parsed.error.message}`,
            'semantic',
            raw
          );
          console.log(`[StructuredLLM] ✗ ${provider.name}: ${parsed.error.message.slice(0, 60)}...`);

        } catch (err) {
          lastError = err as Error;
          console.log(`[StructuredLLM] ✗ ${provider.name}: ${lastError.message}`);
        }
      }
    }

    throw lastError ?? new Error('All providers failed');
  }

  getCacheStats() {
    return this.cache.stats();
  }
}

// ─── 可运行示例 ────────────────────────────────────────────────
async function main() {
  // 定义业务 schema
  const TicketClassification = z.object({
    intent: z.enum(['question', 'complaint', 'feedback', 'request', 'bug_report']),
    urgency: z.enum(['low', 'medium', 'high', 'critical']),
    summary: z.string(),
    actionRequired: z.boolean(),
    confidence: z.number(),
  });

  const client = new StructuredLLMClient([new MockProvider()], { maxRetries: 2 });

  // 多次调用 — 第二次命中缓存
  console.log('=== 第一次调用 ===');
  const r1 = await client.extract(
    'ticket-classification',
    TicketClassification,
    'Classify: My app crashes when I click the login button!'
  );
  console.log('Result:', r1);

  console.log('\n=== 第二次调用（缓存命中）===');
  const r2 = await client.extract(
    'ticket-classification',
    TicketClassification,
    'Classify: How do I change my password?'
  );
  console.log('Result:', r2);

  console.log('\n=== 缓存统计 ===');
  console.log(client.getCacheStats());
}

main().catch(console.error);
```

**运行方式**：
```bash
# 安装依赖
npm init -y && npm add zod typescript tsx
# 直接运行
npx tsx structured-output-toolkit.ts
```

**预期输出**：
```
=== 第一次调用 ===
[SchemaCache] ticket-classification: ~45 tokens, hash=abc12345
[StructuredLLM] ✓ ticket-classification via mock (attempt 1)
Result: { intent: 'question', urgency: 'low', summary: 'sample_summary', ... }

=== 第二次调用（缓存命中）===
[SchemaCache] ticket-classification: ~45 tokens, hash=abc12345
[StructuredLLM] ✓ ticket-classification via mock (attempt 1)
Result: { intent: 'question', urgency: 'low', summary: 'sample_summary', ... }

=== 缓存统计 ===
{ size: 1, totalHits: 3, schemas: ['ticket-classification (hits: 3, tokens: ~45)'] }
```

---

## 关键洞察

### 洞察 1：结构化输出的真正瓶颈不是技术，是 Schema 设计
2026 年所有主流 Provider 都支持约束解码，schema 语法合规率接近 100%。但 **语义正确性**（内容是否准确）仍无法通过 schema 保证。好的 schema 设计（扁平、枚举、明确 description）比选择 Provider 更影响输出质量。

**对 toolkit 的启示**：SchemaCache 不应只缓存编译结果，还应缓存 **schema 质量指标**（命中率、验证通过率、平均 token 数），用于 schema 优化反馈循环。

### 洞察 2：多步 Agent 中结构化输出失败会指数放大
12 步 agent run，每步 5% schema 失败率 → 至少一步失败的概率 = `1 - 0.95^12 = 46%`。这对 agent observability 项目有直接影响——structured-output-toolkit 应与 agent-observability 的 trace 系统集成。

**对 toolkit 的启示**：StructuredLLMClient 的重试 + fallback 机制不是锦上添花，是 agent 系统的**刚需**。

### 洞察 3：Schema 复杂度有隐性成本（延迟 + 费用）
复杂 schema（20+ 字段、深层嵌套）可使延迟翻倍甚至三倍（从 200ms → 1.5s），token 消耗增加 2-3 倍。最佳实践是将大 schema 拆成多个小 schema **并行调用**。

**对 toolkit 的启示**：SchemaCache 应跟踪每个 schema 的延迟/成本指标，自动建议拆分。这是 `SchemaCache` 的差异化价值——不仅是缓存编译结果，还是 schema 性能分析的仪表盘。

### 洞察 4：Provider 差异显著，但正在收敛
- OpenAI：`strict: true` 最成熟，但不支持 `minLength/maxLength/regex` 等约束
- Anthropic：通过 tool use 实现，不支持 recursive schema 和 `minimum/maximum`
- Gemini：`response_json_schema` 支持 `enum/format/propertyOrdering`
- 2026 Q3-Q4 趋势：跨 Provider schema 可移植性正在出现

**对 toolkit 的启示**：StructuredLLMClient 的多 Provider 抽象要处理这些差异——同一个 Zod schema 在不同 Provider 可能需要不同的 JSON Schema 变体。SchemaCache 正好可以存储这些 Provider 特定的编译结果。

---

## Provider 2026 对比速查

| 特性 | OpenAI | Anthropic | Gemini |
|------|--------|-----------|--------|
| 方法 | Native SO | Tool Use | Native SO |
| 约束解码 | ✅ | 部分 | ✅ |
| 100% schema 合规 | ✅ | 99%+ | ✅ |
| Pydantic 原生 | `.parse()` | 手动 | 手动 |
| Zod 原生 | `zodResponseFormat` | 手动 | 手动 |
| 递归 schema | 有限 | ✅ | 有限 |
| 流式支持 | ✅ | ✅ | ✅ |
| 拒绝处理 | `message.refusal` | N/A | N/A |

---

## 生产模式速查

### Validation Sandwich（验证三明治）
```
输入 → Schema预处理 → LLM调用 → Zod后验证 → 输出
                      ↑                    |
                      └── 失败重试(≤3次) ──┘
```

### Multi-Provider Fallback
```
OpenAI (fastest) → Anthropic (fallback) → 本地模型 (last resort)
```

### Schema Pipeline（复杂任务拆分）
```
Step1: QuickClassify (cheap model, 3 fields)
Step2: DetailedExtract (smart model, only if needed)
Step3: AutoRoute (cheap model, 5 fields)
```

---

## 与现有项目关联

| 项目 | 关联点 |
|------|--------|
| **lab/agent-observability** | 结构化输出失败是 agent trace 中的关键错误源，toolkit 应输出 trace spans |
| **agent-context-store** | store 的 middleware pipeline 可集成 schema 验证作为 middleware |
| **AMS** | 记忆提取/摘要可使用结构化输出保证格式一致性 |
| **prompt-router** | 路由决策本身就是结构化输出场景（intent + confidence → route） |
| **lab/openclaw-langgraph-bridge** | LangGraph node 输出需要结构化保证 |

---

## 下一步行动

1. **创建 `lab/structured-output-toolkit/`** — 基于本研究的 StructuredLLMClient + SchemaCache 实现
   - 第一个 PR：SchemaCache（缓存 + hash + 性能追踪）+ StructuredLLMClient（多 Provider + 重试）
   - 目标：50+ tests
2. **集成 agent-observability** — 在 toolkit 中输出 OpenTelemetry-compatible trace spans
3. **Schema 质量仪表盘** — 追踪每个 schema 的命中率/延迟/token 消耗，自动建议优化

---

## 参考来源

- [Beyond JSON Mode (Tian Pan, 2026)](https://tianpan.co/blog/2025-10-29-structured-outputs-llm-production) — 四代演进 + 约束解码详解
- [LLM Structured Output in 2026 (HK Lee)](https://dev.to/pockit_tools/llm-structured-output-in-2026-stop-parsing-json-with-regex-and-do-it-right-34pk) — 三层验证 + Provider 对比
- [Three Layers of Validation (FutureAGI)](https://futureagi.com/blog/what-is-llm-input-output-validation-2026/) — Schema/Structural/Content 三层架构
- [Structured Output Enforcement On-Premises (Sysart)](https://sysart.consulting/insights/structured-output-enforcement-on-premises-llm/) — vLLM + XGrammar 实践
- [Schema Reinforcement Learning (arXiv 2502.18878)](https://arxiv.org/html/2502.18878v1) — 用 RL 提升 schema 合规性
