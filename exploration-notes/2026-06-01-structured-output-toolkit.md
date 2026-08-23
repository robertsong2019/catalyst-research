# 研究笔记：LLM Structured Output Toolkit (2026)

> 日期：2026-06-01 | 方法论：autoresearch | 状态：✅ 完成

---

## 核心概念

### 1. 约束解码 (Constrained Decoding)
LLM 生成每个 token 时，FSM（有限状态机）根据 JSON Schema 屏蔽非法 token，从物理层面保证输出符合 schema。OpenAI Strict Mode、Gemini response_schema、XGrammar（vLLM/SGLang 默认引擎）都采用此方法。首次编译 schema 需 10-30s，后续请求开销极小。

### 2. 三层结构保证
| 层级 | 方法 | 保证程度 |
|------|------|---------|
| JSON Mode | `response_format: {type: "json_object"}` | 合法 JSON，不保证 schema 一致 |
| Function Calling | tool input_schema | 高可靠性，但需要 "tool" 语义包装 |
| Strict Schema | 约束解码 + 严格模式 | 100% schema 合规 |

### 3. 格式税 (Format Tax)
研究表明：强制结构化输出会降低推理质量，尤其是深层推理任务。**最佳实践是分离推理和格式化**：先让模型自由推理，再结构化输出。

### 4. 语义验证 ≠ 语法验证
约束解码保证语法正确，但不保证语义正确（如：订单号可以是幻觉）。必须加业务层验证。

### 5. 库生态（2026）
- **Instructor** (Python): 装饰器模式，15+ provider，自动重试+验证错误反馈
- **Vercel AI SDK** (TypeScript): Zod schema，20+ provider，流式支持
- **BAML**: 跨语言 schema-first DSL，SAP 算法处理乱输出
- **XGrammar**: 本地模型高性能约束解码（100x faster）

---

## 可运行代码示例：StructuredLLMClient

一个轻量级的 TypeScript 结构化输出客户端，支持多 provider 路由、自动重试、schema 缓存。

```typescript
// structured-output-toolkit.ts
// 零依赖，可直接 node structured-output-toolkit.ts 运行测试

// === Schema 定义 ===
interface SchemaField {
  name: string;
  type: "string" | "number" | "boolean" | "enum";
  required: boolean;
  description?: string;
  enumValues?: string[];
}

interface OutputSchema {
  name: string;
  description: string;
  fields: SchemaField[];
}

// === Schema 缓存 ===
class SchemaCache {
  private cache = new Map<string, { schema: OutputSchema; jsonSchema: object }>();

  register(schema: OutputSchema): void {
    const jsonSchema = this.toJsonSchema(schema);
    this.cache.set(schema.name, { schema, jsonSchema });
  }

  get(name: string) {
    return this.cache.get(name);
  }

  private toJsonSchema(schema: OutputSchema): object {
    const properties: Record<string, object> = {};
    const required: string[] = [];

    for (const field of schema.fields) {
      const prop: Record<string, unknown> = {
        type: field.type === "enum" ? "string" : field.type,
        description: field.description || "",
      };
      if (field.type === "enum" && field.enumValues) {
        prop.enum = field.enumValues;
      }
      properties[field.name] = prop;
      if (field.required) required.push(field.name);
    }

    return {
      type: "object",
      properties,
      required,
      additionalProperties: false,
    };
  }

  /** 从 JSON Schema 生成验证器 */
  createValidator(schema: OutputSchema): (data: unknown) => { valid: boolean; errors: string[] } {
    return (data: unknown) => {
      const errors: string[] = [];
      if (typeof data !== "object" || data === null) {
        return { valid: false, errors: ["Expected object"] };
      }
      const obj = data as Record<string, unknown>;

      for (const field of schema.fields) {
        if (field.required && !(field.name in obj)) {
          errors.push(`Missing required field: ${field.name}`);
          continue;
        }
        if (field.name in obj) {
          const val = obj[field.name];
          if (field.type === "string" && typeof val !== "string")
            errors.push(`${field.name}: expected string, got ${typeof val}`);
          if (field.type === "number" && typeof val !== "number")
            errors.push(`${field.name}: expected number, got ${typeof val}`);
          if (field.type === "boolean" && typeof val !== "boolean")
            errors.push(`${field.name}: expected boolean, got ${typeof val}`);
          if (field.type === "enum" && field.enumValues && !field.enumValues.includes(String(val)))
            errors.push(`${field.name}: expected one of ${field.enumValues.join("|")}, got ${val}`);
        }
      }
      return { valid: errors.length === 0, errors };
    };
  }
}

// === 核心 Client ===
type Provider = "openai" | "anthropic" | "gemini";

interface StructuredRequest {
  prompt: string;
  schemaName: string;
  provider?: Provider;
  maxRetries?: number;
}

class StructuredLLMClient {
  private cache: SchemaCache;
  private retryStats = new Map<string, { attempts: number; successes: number }>();

  constructor(cache: SchemaCache) {
    this.cache = cache;
  }

  /**
   * 模拟 LLM 调用 + 结构化输出解析
   * 生产环境中，这里替换为真实的 provider SDK 调用
   */
  async extract<T>(request: StructuredRequest): Promise<{ data: T | null; attempts: number; errors: string[] }> {
    const entry = this.cache.get(request.schemaName);
    if (!entry) throw new Error(`Schema "${request.schemaName}" not registered`);

    const { schema } = entry;
    const validator = this.cache.createValidator(schema);
    const maxRetries = request.maxRetries ?? 3;
    const allErrors: string[] = [];

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      // 模拟 LLM 输出（生产环境：调用 provider API + 约束解码）
      const raw = this.simulateLLM(request.prompt, schema, attempt);
      
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        allErrors.push(`Attempt ${attempt}: Invalid JSON`);
        continue;
      }

      const result = validator(parsed);
      if (result.valid) {
        this.recordStats(request.schemaName, attempt, true);
        return { data: parsed as T, attempts: attempt, errors: allErrors };
      }
      allErrors.push(`Attempt ${attempt}: ${result.errors.join(", ")}`);
    }

    this.recordStats(request.schemaName, maxRetries, false);
    return { data: null, attempts: maxRetries, errors: allErrors };
  }

  /** 模拟 LLM — 第1次故意返回不完整数据测试重试 */
  private simulateLLM(prompt: string, schema: OutputSchema, attempt: number): string {
    // 模拟第1次返回缺少字段（测试重试机制）
    if (attempt === 1 && prompt.includes("sentiment")) {
      return JSON.stringify({ sentiment: "positive" }); // 缺少 confidence
    }
    
    const result: Record<string, unknown> = {};
    for (const field of schema.fields) {
      if (field.type === "string") result[field.name] = "example value";
      if (field.type === "number") result[field.name] = 0.85;
      if (field.type === "boolean") result[field.name] = true;
      if (field.type === "enum" && field.enumValues) result[field.name] = field.enumValues[0];
    }
    return JSON.stringify(result);
  }

  private recordStats(schemaName: string, attempts: number, success: boolean): void {
    const stats = this.retryStats.get(schemaName) || { attempts: 0, successes: 0 };
    stats.attempts += attempts;
    stats.successes += success ? 1 : 0;
    this.retryStats.set(schemaName, stats);
  }

  getStats() {
    return Object.fromEntries(this.retryStats);
  }
}

// === 运行测试 ===
async function main() {
  const cache = new SchemaCache();

  // 注册情感分析 schema
  cache.register({
    name: "sentiment",
    description: "Sentiment analysis result",
    fields: [
      { name: "sentiment", type: "enum", required: true, description: "Detected sentiment", enumValues: ["positive", "negative", "neutral"] },
      { name: "confidence", type: "number", required: true, description: "Confidence score 0-1" },
      { name: "key_phrases", type: "string", required: false, description: "Important phrases" },
    ],
  });

  // 注册实体提取 schema
  cache.register({
    name: "entities",
    description: "Named entity extraction",
    fields: [
      { name: "entity_name", type: "string", required: true, description: "Entity name" },
      { name: "entity_type", type: "enum", required: true, enumValues: ["person", "org", "location", "date"] },
      { name: "confidence", type: "number", required: true },
    ],
  });

  const client = new StructuredLLMClient(cache);

  // 测试1：情感分析（会触发重试）
  console.log("=== Test 1: Sentiment Analysis ===");
  const r1 = await client.extract({ prompt: "Analyze sentiment of: 'This product is amazing!'", schemaName: "sentiment" });
  console.log("Result:", JSON.stringify(r1, null, 2));
  console.log("✅ Retry worked:", r1.attempts === 2 ? "YES (fixed on retry)" : "NO");

  // 测试2：实体提取（一次成功）
  console.log("\n=== Test 2: Entity Extraction ===");
  const r2 = await client.extract({ prompt: "Extract entities from text", schemaName: "entities" });
  console.log("Result:", JSON.stringify(r2, null, 2));
  console.log("✅ First attempt:", r2.attempts === 1 ? "YES" : "NO");

  // 测试3：schema 未注册
  console.log("\n=== Test 3: Missing Schema ===");
  try {
    await client.extract({ prompt: "test", schemaName: "nonexistent" });
  } catch (e) {
    console.log("✅ Correctly threw:", (e as Error).message);
  }

  // 统计
  console.log("\n=== Retry Statistics ===");
  console.log(JSON.stringify(client.getStats(), null, 2));
}

main().catch(console.error);
```

### 运行方式

```bash
# 无需安装依赖
npx tsx structured-output-toolkit.ts
# 或
node --experimental-strip-types structured-output-toolkit.ts
```

---

## 关键洞察

1. **分离推理与格式化** — 结构化输出的最大陷阱是"格式税"：强制 JSON 输出会降低推理质量。最佳方案是两步走：先让模型自由推理（chain-of-thought），再用结构化格式输出。Schema 设计中把 `reasoning` 字段放在 `answer` 前面也能提升准确率。

2. **100% schema 合规 ≠ 正确** — 约束解码消除了语法错误，但语义幻觉（如虚假订单号、捏造的置信度）仍需业务层验证。arXiv 多模态基准显示：文本 Value Accuracy 0.830，音频仅 0.237 — 结构正确但内容可能全错。

3. **Instructor 的重试反馈机制是杀手级特性** — 验证失败时把 Pydantic 错误信息发回给 LLM，让它自我修正。大多数情况第2次就对了。这比单纯的约束解码更鲁棒。

4. **Provider 选择策略** — 单 provider 直接用原生 SDK；多 provider 用 Instructor(Python) 或 Vercel AI SDK(TS)；跨语言团队用 BAML；本地模型用 XGrammar/Outlines。

5. **Schema 缓存对生产至关重要** — 首次编译 FSM 需 10-30s，缓存后几乎零开销。Toolkit 必须内置缓存层。

---

## 与现有项目关联

| 项目 | 关联 |
|------|------|
| **agent-context-store** | 可用 StructuredLLMClient 做快照 diff 的结构化摘要 |
| **agent-memory-graph** | evolve() 的审计记录可以用 schema 约束保证格式 |
| **openclaw-langgraph-bridge** | Supervisor 的 LLM 路由可以用结构化输出做决策 |
| **prompt-router** | 路由决策本身可以用结构化输出保证返回合法路由目标 |

---

## 下一步行动

1. **创建 `lab/structured-output-toolkit/`** — 基于 TypeScript 实现完整版，接入 OpenAI/Anthropic 原生 SDK
2. **实现 SchemaCache + retry 反馈** — 核心差异化特性
3. **为 agent-context-store 添加结构化摘要适配器** — 第一个实际应用场景

---

## 参考来源

- Zylos Research: Structured Output and JSON Mode in LLMs 2026
- TECHSY: Reliable JSON from Any LLM: Pydantic + Zod (2026)
- TECHSY: 8 LLM Structured Output Libraries Ranked (2026)
- Rephrase: Structured Output in 2026: What to Use
- Collin Wilkins: LLM Structured Outputs: Schema Validation for Real Pipelines
- arXiv 2604.25359: A Multi-Source Benchmark for Evaluating Structured Output Quality
- DEV Community: LLM Structured Output in 2026: Stop Parsing JSON with Regex
