# Structured Output Toolkit — 深度研究笔记

> 日期: 2026-05-21 | 主题: LLM Structured Output 最佳实践与 TypeScript Toolkit 设计
> 关联项目: lab/structured-output-toolkit (HEARTBEAT 高优先级待办)

---

## 核心概念

### 1. 三层结构化输出体系 (Level 1→2→3)

| 层级 | 方法 | 可靠性 | 适用场景 |
|------|------|--------|---------|
| **Level 1** | Prompt Engineering ("respond in JSON") | ~35% | 原型/快速验证 |
| **Level 2** | Function Calling / Tool Use | 95-99% | 通用生产环境 |
| **Level 3** | Constrained Decoding (FSM) | 100% schema-valid | 关键业务路径 |

**关键洞察**: Level 3 使用有限状态机(FSM)在 token 生成时屏蔽非法 token，保证输出 100% 符合 JSON Schema。但 **schema-valid ≠ content-correct**，业务逻辑验证仍然不可少。

### 2. Provider 差异化策略

- **OpenAI**: `response_format: { type: "json_schema" }` — 原生 FSM 约束
- **Anthropic**: 无原生 structured output，通过 tool use 模拟 — 需额外 Zod 兜底
- **Gemini**: `response_schema` 原生支持 — 不合规时抛 `JSONSchemaValidationError`
- **Vercel AI SDK**: `generateObject()` 统一封装，自动选最佳策略

### 3. Schema Cache 模式

Schema 编译是重复开销。缓存策略：
- Zod schema 对象按引用缓存（进程级 Map）
- JSON Schema 序列化结果按 hash 缓存
- Provider-specific schema 转换结果按 provider+hash 缓存

### 4. Retry + Validation Pipeline

```
LLM Output → JSON Parse → Schema Validate → Business Logic Validate → [OK / Retry with Error Context]
```

关键：retry 不只是"再来一次"，而是把验证错误信息反馈给 LLM，让它修复。

### 5. 成本优化 — Schema 分解

复杂 schema 的 constrained decoding 开销显著。策略：
- 大 schema → 拆分为多个并行小 schema 调用
- 嵌套对象深度 ≤ 3 层为佳
- enum 值保持 ≤ 10 个，且语义明确不重叠

---

## 可运行代码：StructuredLLMClient 原型

> 完整可运行原型，零外部依赖（仅用内置 fetch + 手写 mini-validator）。

```typescript
// structured-llm-client.ts
// 零依赖可运行原型 — StructuredLLMClient + SchemaCache

// ─── Mini Zod-like Schema System ───
type SchemaType = 'string' | 'number' | 'boolean' | 'array' | 'object' | 'enum';

interface FieldDef {
  type: SchemaType;
  required?: boolean;
  enumValues?: string[];
  items?: FieldDef;         // for arrays
  properties?: Record<string, FieldDef>;  // for objects
  description?: string;
  min?: number;
  max?: number;
}

interface SchemaDef {
  type: 'object';
  properties: Record<string, FieldDef>;
  required?: string[];
}

// ─── Validation Result ───
interface ValidationResult {
  ok: boolean;
  data?: any;
  errors: string[];
}

// ─── Schema Cache ───
class SchemaCache {
  private cache = new Map<string, { schema: SchemaDef; jsonSchema: object }>();
  private hitCount = 0;
  private missCount = 0;

  get(key: string): { schema: SchemaDef; jsonSchema: object } | undefined {
    const entry = this.cache.get(key);
    if (entry) { this.hitCount++; return entry; }
    this.missCount++;
    return undefined;
  }

  set(key: string, schema: SchemaDef): void {
    const jsonSchema = this.toJsonSchema(schema);
    this.cache.set(key, { schema, jsonSchema });
  }

  getOrCreate(key: string, factory: () => SchemaDef): { schema: SchemaDef; jsonSchema: object } {
    const cached = this.get(key);
    if (cached) return cached;
    this.set(key, factory());
    return this.get(key)!;
  }

  stats() { return { size: this.cache.size, hits: this.hitCount, misses: this.missCount }; }

  private toJsonSchema(schema: SchemaDef): object {
    const props: any = {};
    for (const [name, field] of Object.entries(schema.properties)) {
      props[name] = this.fieldToJsonSchema(field);
    }
    return { type: 'object', properties: props, required: schema.required ?? [] };
  }

  private fieldToJsonSchema(field: FieldDef): any {
    if (field.type === 'enum') {
      return { type: 'string', enum: field.enumValues };
    }
    if (field.type === 'array' && field.items) {
      return { type: 'array', items: this.fieldToJsonSchema(field.items) };
    }
    if (field.type === 'object' && field.properties) {
      const props: any = {};
      for (const [k, v] of Object.entries(field.properties)) {
        props[k] = this.fieldToJsonSchema(v);
      }
      return { type: 'object', properties: props };
    }
    return { type: field.type, description: field.description };
  }
}

// ─── Validator ───
function validate(data: any, schema: SchemaDef): ValidationResult {
  const errors: string[] = [];

  if (typeof data !== 'object' || data === null) {
    return { ok: false, errors: ['Expected object, got ' + typeof data] };
  }

  const required = new Set(schema.required ?? []);
  for (const key of required) {
    if (!(key in data)) errors.push(`Missing required field: "${key}"`);
  }

  for (const [key, field] of Object.entries(schema.properties)) {
    if (!(key in data)) continue;
    const val = data[key];
    const fieldErr = validateField(val, field, key);
    errors.push(...fieldErr);
  }

  return errors.length === 0 ? { ok: true, data, errors: [] } : { ok: false, errors };
}

function validateField(val: any, field: FieldDef, path: string): string[] {
  const errors: string[] = [];

  if (field.type === 'string' && typeof val !== 'string') {
    errors.push(`"${path}": expected string, got ${typeof val}`);
  }
  if (field.type === 'number') {
    if (typeof val !== 'number') errors.push(`"${path}": expected number, got ${typeof val}`);
    else {
      if (field.min !== undefined && val < field.min) errors.push(`"${path}": ${val} < min ${field.min}`);
      if (field.max !== undefined && val > field.max) errors.push(`"${path}": ${val} > max ${field.max}`);
    }
  }
  if (field.type === 'boolean' && typeof val !== 'boolean') {
    errors.push(`"${path}": expected boolean, got ${typeof val}`);
  }
  if (field.type === 'enum' && field.enumValues) {
    if (!field.enumValues.includes(val)) {
      errors.push(`"${path}": "${val}" not in [${field.enumValues.join(', ')}]`);
    }
  }
  if (field.type === 'array') {
    if (!Array.isArray(val)) errors.push(`"${path}": expected array`);
    else if (field.items) {
      val.forEach((item: any, i: number) => {
        errors.push(...validateField(item, field.items!, `${path}[${i}]`));
      });
    }
  }

  return errors;
}

// ─── StructuredLLMClient ───
interface ClientConfig {
  provider: 'openai' | 'anthropic' | 'gemini';
  apiKey: string;
  model: string;
  maxRetries?: number;
  retryDelayMs?: number;
}

interface RequestOptions {
  schema: SchemaDef;
  schemaKey: string;  // cache key
  prompt: string;
  systemPrompt?: string;
}

class StructuredLLMClient {
  private cache = new SchemaCache();
  private config: Required<ClientConfig>;

  constructor(config: ClientConfig) {
    this.config = {
      maxRetries: 3,
      retryDelayMs: 1000,
      ...config,
    };
  }

  async extract<T = any>(opts: RequestOptions): Promise<T> {
    const cached = this.cache.getOrCreate(opts.schemaKey, () => opts.schema);
    let lastErrors: string[] = [];

    for (let attempt = 0; attempt <= this.config.maxRetries; attempt++) {
      try {
        // Build prompt with retry context
        let prompt = opts.prompt;
        if (lastErrors.length > 0) {
          prompt += `\n\nPrevious attempt had these validation errors:\n${
            lastErrors.map(e => `- ${e}`).join('\n')
          }\nPlease fix these errors.`;
        }

        // In real impl: call LLM API with schema constraint
        // For demo: simulate LLM response
        const raw = await this.callLLM(prompt, opts.systemPrompt, cached.jsonSchema);
        const parsed = JSON.parse(raw);

        const result = validate(parsed, opts.schema);
        if (result.ok) return result.data as T;

        lastErrors = result.errors;
        console.warn(`[Attempt ${attempt + 1}] Validation failed:`, result.errors);
      } catch (e: any) {
        lastErrors = [e.message];
      }

      // Exponential backoff
      if (attempt < this.config.maxRetries) {
        const delay = this.config.retryDelayMs * Math.pow(2, attempt);
        await new Promise(r => setTimeout(r, delay));
      }
    }

    throw new Error(`Failed after ${this.config.maxRetries + 1} attempts. Last errors: ${lastErrors.join('; ')}`);
  }

  getCacheStats() { return this.cache.stats(); }

  private async callLLM(prompt: string, systemPrompt: string | undefined, jsonSchema: object): Promise<string> {
    // ─── Demo Mode: simulate LLM output ───
    // Real impl would be:
    //   OpenAI: fetch('https://api.openai.com/v1/chat/completions', { response_format: { type: "json_schema", json_schema } })
    //   Anthropic: fetch with tool_use
    //   Gemini: fetch with responseSchema

    // Simulate a valid response for demo
    return JSON.stringify({
      sentiment: "positive",
      confidence: 0.92,
      topics: ["product quality", "customer satisfaction"],
      summary: "The customer is very happy with the product",
    });
  }
}

// ─── Demo ───
async function demo() {
  const client = new StructuredLLMClient({
    provider: 'openai',
    apiKey: 'demo-key',
    model: 'gpt-4o',
  });

  // Define schema for sentiment analysis
  const sentimentSchema: SchemaDef = {
    type: 'object',
    properties: {
      sentiment: { type: 'enum', enumValues: ['positive', 'negative', 'neutral'], description: 'Overall sentiment' },
      confidence: { type: 'number', min: 0, max: 1, description: 'Confidence score 0-1' },
      topics: { type: 'array', items: { type: 'string' }, description: 'Key topics mentioned' },
      summary: { type: 'string', description: 'Brief summary of the text' },
    },
    required: ['sentiment', 'confidence', 'topics', 'summary'],
  };

  const result = await client.extract({
    schema: sentimentSchema,
    schemaKey: 'sentiment-analysis-v1',
    prompt: 'Analyze this customer feedback: "The product is amazing! Best purchase I\'ve made all year."',
    systemPrompt: 'You are a sentiment analysis engine. Respond with structured JSON.',
  });

  console.log('✅ Result:', JSON.stringify(result, null, 2));
  console.log('📊 Cache stats:', client.getCacheStats());

  // Second call hits cache
  const result2 = await client.extract({
    schema: sentimentSchema,
    schemaKey: 'sentiment-analysis-v1',
    prompt: 'Analyze: "Terrible experience. Product broke after 2 days."',
  });

  console.log('✅ Result 2:', JSON.stringify(result2, null, 2));
  console.log('📊 Cache stats:', client.getCacheStats());
}

demo().catch(console.error);
```

**运行方式:**
```bash
npx tsx structured-llm-client.ts
# 或
npx ts-node structured-llm-client.ts
```

**预期输出:**
```
✅ Result: {
  "sentiment": "positive",
  "confidence": 0.92,
  "topics": ["product quality", "customer satisfaction"],
  "summary": "The customer is very happy with the product"
}
📊 Cache stats: { size: 1, hits: 0, misses: 1 }
✅ Result 2: { ... }
📊 Cache stats: { size: 1, hits: 1, misses: 1 }
```

---

## 关键洞察

### 1. Schema-Valid ≠ Content-Correct — 双重验证不可或缺

OpenAI 声称 100% schema-compliant，但 JSON Schema 只管"形状"不管"语义"。`confidence: 0.92` 满足 `min:0 max:1` 但可能完全不准。**必须加业务逻辑验证层**（如 Pydantic 的 `@field_validator` / Zod 的 `.refine()`）。

### 2. Retry with Error Context 是生产级必需品

LangChain JS 的 `handleError` 模式证明：把验证错误反馈给 LLM 比盲目重试有效得多。错误信息越具体（字段名+期望值+实际值），修复成功率越高。这正是 Toolkit 的核心差异化——不是简单的 try-catch，而是 validation-aware retry loop。

### 3. 多 Provider 统一接口有真实价值

Vercel AI SDK 的 `generateObject` 模式说明：OpenAI 用 FSM 约束，Anthropic 用 tool use + Zod 兜底，Gemini 用原生 schema。**用户不应该关心底层差异**。StructuredLLMClient 的职责就是根据 provider 自动选最优策略。

### 4. Schema Cache 的隐性收益常被低估

Schema → JSON Schema 转换在每次请求都做是浪费。缓存后：
- 减少 CPU 开销（JSON Schema 生成是递归遍历）
- 保证同一 schema key 的 JSON Schema 稳定（方便 A/B 测试、日志对比）
- 为未来的 schema 版本管理打基础

### 5. "不要用 Structured Output" 的情况同样重要

来源 dev.to 文章明确列出反模式：
- 输出直接展示给用户时（聊天、内容生成）
- schema 比任务本身更复杂时
- 快速原型且 schema 每天在变时
- 成本敏感且自由文本够用时

---

## 与现有项目的关联

| 现有项目 | 关联点 |
|----------|--------|
| **agent-context-store** | 存储结构化 schema 元数据，支持 prefix_scan 查询已注册 schema |
| **prompt-router** | 路由时可根据 schema 复杂度选择不同 provider（简单→便宜模型，复杂→支持 FSM 的模型） |
| **lab/agent-observability** | 追踪 structured output 成功率、retry 次数、validation 失败模式 |
| **AMS** | embedding + schema cache 联动：相似 schema 可复用验证逻辑 |

---

## 下一步行动

1. **创建 lab/structured-output-toolkit/** — 基于 原型 扩展为完整项目
   - StructuredLLMClient: 支持 OpenAI/Anthropic/Gemini 三种 provider
   - SchemaCache: LRU + TTL + stats
   - ValidationPipeline: schema validate → business validate → retry with context
   - 目标: 20+ tests

2. **接入真实 LLM API** — 将 demo callLLM 替换为：
   - OpenAI: `response_format: { type: "json_schema" }`
   - Anthropic: tool use pattern
   - 统一错误处理和 refusal 检测

3. **Schema 版本管理** — 利用 agent-context-store 存储 schema 历史，支持 A/B 测试不同 schema 版本的输出质量

---

## 参考来源

- [LLM Structured Output in 2026 (dev.to)](https://dev.to/pockit_tools/llm-structured-output-in-2026-stop-parsing-json-with-regex-and-do-it-right-34pk)
- [Vercel AI SDK - Generating Structured Data](https://ai-sdk.dev/docs/ai-sdk-core/generating-structured-data)
- [LangChain JS Structured Output](https://docs.langchain.com/oss/javascript/langchain/structured-output)
- [OpenAI Structured Outputs vs Zod (dev.to)](https://dev.to/whoffagents/openai-structured-outputs-vs-zod-which-to-use-for-llm-response-validation-in-2026-366m)
- [Simon Willison - LLM Schemas](https://simonwillison.net/2025/Feb/28/llm-schemas)
- [JSON Schema Conference 2025 Recap](https://json-schema.org/blog/posts/apidays-paris-2025-recap)
- [Strands Agents SDK - Structured Output](https://strandsagents.com/docs/user-guide/concepts/agents/structured-output)
- [BAML - Every Way To Get Structured Output](https://boundaryml.com/blog/structured-output-from-llms)
