# Structured Output Toolkit — 深度技术研究

> 日期: 2026-05-14 | 主题: LLM 结构化输出工具包设计
> 目标: 为 lab/structured-output-toolkit 提供架构设计和核心代码

---

## 核心概念

### 1. 约束解码 (Constrained Decoding)
LLM 生成时，用有限状态机 (FSM) 在 token 采样阶段遮蔽非法 token。2026 年 OpenAI/Gemini 原生支持，Anthropic 通过 tool use 间接实现。Schema 被编译为 CFG → FSM，每个状态只允许合法 token。

### 2. Validation Sandwich (验证三明治)
即使 provider 保证 schema 合规，仍需业务逻辑验证层。三层结构：
- **Provider 约束** → JSON Schema 级保证（类型、必填）
- **Zod/Pydantic 验证** → 业务规则（范围、格式、语义）
- **应用层断言** → 跨字段一致性、领域约束

### 3. Schema Cache (Schema 缓存)
OpenAI 首次使用新 schema 时需 ~10-60s 构建 FSM，之后按 API key 缓存，TTL ~120s。频繁使用的 schema 应保持热度。对高 QPS 场景，缓存策略直接影响 P99 延迟。

### 4. Multi-Provider Fallback (多 provider 降级链)
OpenAI 原生 SO → Anthropic tool use → Gemini response_schema → 正则兜底。每层有不同的 schema 支持度和延迟特征。

### 5. Schema Complexity Tax
Schema 越复杂，延迟越高。20+ 字段嵌套 schema 可使 tokens/s 下降 50%。策略：拆分为多个并行小 schema 调用。

---

## 可运行代码：StructuredLLMClient + SchemaCache

这是 lab/structured-output-toolkit 的核心原型，可直接运行测试：

```typescript
// structured-output-toolkit.ts
import { z } from 'zod';

// ─── SchemaCache ─────────────────────────────────────────────
interface CacheEntry<T extends z.ZodType> {
  schema: T;
  jsonSchema: object;
  hash: string;
  lastUsed: number;
  hitCount: number;
}

export class SchemaCache {
  private cache = new Map<string, CacheEntry<z.ZodType>>();
  private ttlMs: number;

  constructor(ttlMs = 120_000) { // OpenAI TTL ~120s
    this.ttlMs = ttlMs;
  }

  private hash(schema: z.ZodType): string {
    // Deterministic hash from JSON schema representation
    const str = JSON.stringify(schema);
    let h = 0;
    for (let i = 0; i < str.length; i++) {
      h = ((h << 5) - h + str.charCodeAt(i)) | 0;
    }
    return h.toString(36);
  }

  get<T extends z.ZodType>(key: string): CacheEntry<T> | undefined {
    const entry = this.cache.get(key);
    if (!entry) return undefined;
    if (Date.now() - entry.lastUsed > this.ttlMs) {
      this.cache.delete(key);
      return undefined;
    }
    entry.lastUsed = Date.now();
    entry.hitCount++;
    return entry as CacheEntry<T>;
  }

  set<T extends z.ZodType>(key: string, schema: T): CacheEntry<T> {
    const entry: CacheEntry<T> = {
      schema,
      jsonSchema: this.zodToJsonSchema(schema),
      hash: this.hash(schema),
      lastUsed: Date.now(),
      hitCount: 0,
    };
    this.cache.set(key, entry);
    return entry;
  }

  /** Minimal Zod → JSON Schema (no external dep) */
  private zodToJsonSchema(schema: z.ZodType): object {
    if (schema instanceof z.ZodString) {
      return { type: 'string' };
    } else if (schema instanceof z.ZodNumber) {
      return { type: 'number' };
    } else if (schema instanceof z.ZodBoolean) {
      return { type: 'boolean' };
    } else if (schema instanceof z.ZodArray) {
      return { type: 'array', items: this.zodToJsonSchema(schema.element) };
    } else if (schema instanceof z.ZodObject) {
      const properties: Record<string, object> = {};
      const required: string[] = [];
      for (const [key, value] of Object.entries(schema.shape)) {
        properties[key] = this.zodToJsonSchema(value as z.ZodType);
        // Check if optional
        if (!(value instanceof z.ZodOptional)) {
          required.push(key);
        }
      }
      return {
        type: 'object',
        properties,
        required: required.length > 0 ? required : undefined,
      };
    } else if (schema instanceof z.ZodEnum) {
      return { type: 'string', enum: schema.options };
    } else if (schema instanceof z.ZodOptional) {
      return this.zodToJsonSchema(schema.unwrap());
    } else if (schema instanceof z.ZodDefault) {
      return this.zodToJsonSchema(schema.removeDefault());
    } else if (schema instanceof z.ZodNullable) {
      return { ...this.zodToJsonSchema(schema.unwrap()), nullable: true };
    }
    return {};
  }

  stats() {
    let hits = 0, misses = 0;
    for (const entry of this.cache.values()) {
      if (entry.hitCount > 0) hits += entry.hitCount;
      else misses++;
    }
    return { size: this.cache.size, hits, misses };
  }
}

// ─── Provider Adapter ────────────────────────────────────────
type Provider = 'openai' | 'anthropic' | 'gemini';

interface ProviderConfig {
  name: Provider;
  priority: number; // lower = tried first
  client: any;      // actual SDK client (injected)
}

// ─── StructuredLLMClient ─────────────────────────────────────
export interface ExtractOptions {
  model?: string;
  maxRetries?: number;
  provider?: Provider;
  temperature?: number;
}

export class StructuredLLMClient {
  private cache = new SchemaCache();
  private providers: ProviderConfig[] = [];

  addProvider(config: ProviderConfig) {
    this.providers.push(config);
    this.providers.sort((a, b) => a.priority - b.priority);
  }

  /**
   * Extract structured data from text using Zod schema.
   * In production, this calls real LLM APIs.
   * For testing, inject a mock provider.
   */
  async extract<T>(
    text: string,
    schema: z.ZodType<T>,
    options: ExtractOptions = {}
  ): Promise<T> {
    const cacheKey = schema.toString();
    let cached = this.cache.get(cacheKey);
    if (!cached) {
      cached = this.cache.set(cacheKey, schema);
    }

    const maxRetries = options.maxRetries ?? 3;
    const errors: Error[] = [];

    // Try each provider in priority order
    const targetProviders = options.provider
      ? this.providers.filter(p => p.name === options.provider)
      : this.providers;

    for (const provider of targetProviders) {
      for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
          const raw = await this.callProvider(
            provider, text, cached.jsonSchema, options
          );
          // Validation Sandwich: always re-validate
          return schema.parse(raw);
        } catch (err) {
          errors.push(err as Error);
          if (attempt < maxRetries - 1) {
            // Brief backoff
            await new Promise(r => setTimeout(r, 100 * (attempt + 1)));
          }
        }
      }
    }

    throw new AggregateError(errors, 'All providers failed for structured output');
  }

  private async callProvider(
    provider: ProviderConfig,
    text: string,
    jsonSchema: object,
    options: ExtractOptions
  ): Promise<unknown> {
    // In production, call actual SDK.
    // For lab prototype, this is the extension point.
    if (provider.client?.mockResponse) {
      return provider.client.mockResponse(text, jsonSchema);
    }
    throw new Error(`Provider ${provider.name} has no client configured`);
  }
}

// ─── Quick Usage Example (runnable with mock) ────────────────
async function demo() {
  const TicketSchema = z.object({
    intent: z.enum(['question', 'complaint', 'feedback', 'request']),
    urgency: z.enum(['low', 'medium', 'high', 'critical']),
    summary: z.string(),
    actionRequired: z.boolean(),
  });

  const client = new StructuredLLMClient();
  client.addProvider({
    name: 'openai',
    priority: 0,
    client: {
      mockResponse: (_text: string, _schema: object) => ({
        intent: 'complaint',
        urgency: 'high',
        summary: 'Customer reports login failure on mobile',
        actionRequired: true,
      }),
    },
  });

  const result = await client.extract(
    'I cannot log in on my phone! This has been broken for 3 days!',
    TicketSchema
  );

  console.log('Extracted:', result);
  // Extracted: { intent: 'complaint', urgency: 'high',
  //   summary: 'Customer reports login failure on mobile', actionRequired: true }

  console.log('Cache stats:', client.cache.stats());
  // Cache stats: { size: 1, hits: 0, misses: 1 }
}

// Run demo
demo().catch(console.error);
```

### 测试代码

```typescript
// structured-output-toolkit.test.ts
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { z } from 'zod';
import { StructuredLLMClient, SchemaCache } from './structured-output-toolkit.js';

describe('SchemaCache', () => {
  it('caches and retrieves schemas', () => {
    const cache = new SchemaCache();
    const schema = z.object({ name: z.string(), age: z.number() });
    const entry = cache.set('test', schema);
    assert.equal(entry.hash, cache.get('test')?.hash);
  });

  it('expires entries after TTL', async () => {
    const cache = new SchemaCache(50); // 50ms TTL
    cache.set('test', z.string());
    await new Promise(r => setTimeout(r, 60));
    assert.equal(cache.get('test'), undefined);
  });

  it('tracks hit counts', () => {
    const cache = new SchemaCache();
    cache.set('test', z.string());
    cache.get('test');
    cache.get('test');
    assert.deepEqual(cache.stats(), { size: 1, hits: 2, misses: 0 });
  });
});

describe('StructuredLLMClient', () => {
  it('extracts and validates structured data', async () => {
    const client = new StructuredLLMClient();
    const SentimentSchema = z.object({
      sentiment: z.enum(['positive', 'negative', 'neutral']),
      confidence: z.number().min(0).max(1),
    });

    client.addProvider({
      name: 'mock',
      priority: 0,
      client: {
        mockResponse: () => ({ sentiment: 'positive', confidence: 0.92 }),
      },
    });

    const result = await client.extract('Great product!', SentimentSchema);
    assert.equal(result.sentiment, 'positive');
    assert.equal(result.confidence, 0.92);
  });

  it('retries on validation failure', async () => {
    const client = new StructuredLLMClient();
    let attempts = 0;

    client.addProvider({
      name: 'flaky',
      priority: 0,
      client: {
        mockResponse: () => {
          attempts++;
          if (attempts < 3) return { sentiment: 'bad_value', confidence: -1 };
          return { sentiment: 'neutral', confidence: 0.5 };
        },
      },
    });

    const result = await client.extract('test', z.object({
      sentiment: z.enum(['positive', 'negative', 'neutral']),
      confidence: z.number().min(0).max(1),
    }));

    assert.equal(result.sentiment, 'neutral');
    assert.equal(attempts, 3);
  });

  it('falls back to next provider', async () => {
    const client = new StructuredLLMClient();
    const Schema = z.object({ value: z.number() });

    client.addProvider({
      name: 'failing',
      priority: 0,
      client: { mockResponse: () => { throw new Error('API down'); } },
    });
    client.addProvider({
      name: 'backup',
      priority: 1,
      client: { mockResponse: () => ({ value: 42 }) },
    });

    const result = await client.extract('test', Schema);
    assert.equal(result.value, 42);
  });
});
```

---

## 关键洞察

### 洞察 1: Schema 是新 API Contract
2026 年，Schema 不再只是验证工具，而是 LLM 和应用之间的**接口契约**。好的 schema 设计直接影响：
- 延迟（复杂度税，20+ 字段可降 50% tokens/s）
- 准确性（空数组陷阱、enum 混淆）
- 成本（structured output 比自由文本多 2-3x tokens）

**策略**：拆分为多个并行小 schema 调用，而非一个巨型 schema。

### 洞察 2: 缓存是 Schema 的隐形成本
OpenAI schema 缓存 TTL ~120s，API key 级别。高频场景必须保持 schema 热度，否则首次请求的 10-60s 延迟会直接影响用户。SchemaCache 应：
- 预热常用 schema（后台心跳）
- 监控缓存命中率
- 根据热度动态调整 TTL

### 洞察 3: Validation Sandwich 不可省略
即使 provider 保证 100% schema 合规（OpenAI/Gemini 约束解码），仍需业务逻辑验证层。JSON Schema 无法表达：
- 跨字段一致性（total = subtotal × (1 + taxRate)）
- 语义约束（title 不能是 "good"/"bad" 等泛词）
- 领域规则（日期必须在范围内、邮箱格式等）

### 洞察 4: Multi-Provider 不是奢侈品而是必需品
生产环境没有 100% 可靠的单 provider。降级链设计：
1. OpenAI（原生 SO，最快最可靠）
2. Anthropic（tool use，99%+ 可靠）
3. Gemini（原生 SO，适合备用）
4. 本地模型 + Outlines（离线兜底）

### 洞察 5: 2026 Q3-Q4 趋势值得提前布局
- 跨 provider schema 可移植性（一套 schema，任意 LLM）
- Streaming partial objects + field-level callbacks
- Schema 自动生成（从 TypeScript interface 直接生成）

---

## 与现有项目的关联

| 项目 | 关联点 |
|------|--------|
| **prompt-router** | 可作为 routing strategy：根据 schema 复杂度路由到不同 provider |
| **prompt-weaver** | 模板系统可集成 schema 定义，自动生成 validation 代码 |
| **AMS (agent-memory-service)** | 内存结构化存储需要 schema 验证层 |
| **agent-context-store** | changelog 审计日志本身就是结构化输出场景 |
| **better-ralph** | PRD 解析和 story 提取可受益于结构化输出 |
| **lab/agent-observability** | Tracer 可追踪 schema 验证成功率、缓存命中率 |

---

## 下一步行动

1. **创建 `lab/structured-output-toolkit/`** — 基于上述原型，集成真实 provider SDK
   - 优先实现 OpenAI adapter（`zodResponseFormat`）
   - 然后实现 Anthropic adapter（tool use + `zodToJsonSchema`）
   - SchemaCache 预热机制
   - 目标：18/18 tests（与 openclaw-langgraph-bridge 同标准）

2. **与 prompt-router 集成** — 新增 `structured-route` strategy，根据 schema 复杂度自动选择 provider

3. **性能基准测试** — 测量不同 schema 复杂度下的延迟/成本，建立 complexity-latency 矩阵

---

## 参考资料

- [LLM Structured Output in 2026: Stop Parsing JSON with Regex](https://dev.to/pockit_tools/llm-structured-output-in-2026-stop-parsing-json-with-regex-and-do-it-right-34pk) — 最全面的跨 provider 指南
- [Structured Output: Caching and Latency (OpenAI Community)](https://community.openai.com/t/structured-output-caching-and-latency/904483) — 缓存 TTL 和 CFG 编译细节
- [LLM Input/Output Validation 2026 (FutureAGI)](https://futureagi.com/blog/what-is-llm-input-output-validation-2026) — 验证三层模型和工具对比
- [Structured Outputs in LLMs (collinwilkins.com)](https://collinwilkins.com/articles/structured-output) — Provider 对比和 vLLM 自部署方案
- [LangChain Structured Output (JS)](https://docs.langchain.com/oss/javascript/langchain/structured-output) — Zod schema + agent 集成模式
