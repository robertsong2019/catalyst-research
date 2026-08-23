# Structured Output Toolkit — 深度研究笔记

> 日期: 2026-05-24 | 主题: LLM Structured Output 最佳实践与 Toolkit 设计
> 状态: ✅ 含可运行代码

---

## 核心概念 (5个)

### 1. 三级输出控制模型

| 级别 | 方法 | 可靠性 | 适用场景 |
|------|------|--------|---------|
| L1 | Prompt Engineering | 80-95% | 原型/非关键路径 |
| L2 | Function Calling / Tool Use | 95-99% | Agent工具调用 |
| L3 | Native Structured Output (约束解码) | ~100% | 生产环境 |

**关键洞察**: 2026年生产系统应全部使用 L3。L2 的 schema 只是"提示"而非"约束"，仍可能产生无效值。

### 2. 约束解码 (Constrained Decoding) 原理

核心机制：**有限状态机 (FSM) + 动态 logit masking**

```
LLM 生成流程：
raw logits → FSM 过滤无效 token → softmax → 采样

FSM 状态跟踪 (例如 {"name": string, "age": integer}):
START → expect "{" → expect "name" → expect string → expect "age" → expect integer → DONE
```

每生成一个 token 后，FSM 根据当前状态计算哪些 token 合法，将非法 token 的 logit 设为 -∞。模型权重不修改，只约束采样分布。

### 3. 跨平台 API 差异

| 特性 | OpenAI | Anthropic | Gemini |
|------|--------|-----------|--------|
| 参数 | `response_format` / `text.format` | `output_config.format` | `response_mime_type` + `response_schema` |
| Strict 模式 | `additionalProperties: false` | 默认开启 | 通过 `response_schema` |
| 递归 Schema | ✅ `$ref` | ✅ | ✅ (2025.11+) |
| 底层引擎 | llguidance (基于 CFG) | 自研 | 自研 |

### 4. 开源引擎生态 (自部署场景)

| 引擎 | 特点 | 适用场景 |
|------|------|---------|
| **XGrammar** | vLLM/SGLang/TRT-LLM 默认引擎 | 单 schema 大规模请求 |
| **Guidance** | 最高吞吐，最广 schema 覆盖 | 多 schema 混合 + 自由文本混合 |
| **Outlines** | Pydantic-first，Rust 核心 | Pydantic 工作流 + regex/CFG |
| **llguidance** | OpenAI 底层使用，CFG-based | 兼容性最好 |

**JSONSchemaBench 基准**: 10K 真实 schema 测试，Guidance 覆盖率最高（2x于最差引擎），XGrammar 编译速度最快。

### 5. 生产陷阱

- **语义 vs 语法**: 结构正确 ≠ 内容正确。`{"score": 999}` 语法合法但语义可能错误
- **Schema 复杂度与质量权衡**: 过度约束会降低 LLM 输出质量（4% 性能下降）
- **`additionalProperties: false` 的代价**: OpenAI strict 模式要求此设置，意味着无法有动态字段
- **拒绝检测**: 模型安全拒绝时需要可编程检测（OpenAI 通过 refusal 字段处理）

---

## 代码示例: StructuredLLMClient 原型

这是一个可直接运行的 TypeScript 原型，演示结构化输出客户端的核心设计：

```typescript
// structured-output-prototype.ts
// 零依赖，纯 TypeScript 运行：npx tsx structured-output-prototype.ts

// === 1. Schema 定义层 ===
interface SchemaField {
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  description: string;
  enum?: string[];
  items?: SchemaField;
  properties?: Record<string, SchemaField>;
  required?: string[];
}

interface StructuredSchema {
  name: string;
  description: string;
  fields: Record<string, SchemaField>;
  required?: string[];
}

// === 2. JSON Schema 生成器 ===
function toJsonSchema(schema: StructuredSchema): object {
  const properties: Record<string, object> = {};
  
  for (const [key, field] of Object.entries(schema.fields)) {
    properties[key] = fieldToSchema(field);
  }
  
  return {
    type: 'object',
    properties,
    required: schema.required ?? Object.keys(schema.fields),
    additionalProperties: false,
  };
}

function fieldToSchema(field: SchemaField): object {
  const base: Record<string, unknown> = { type: field.type, description: field.description };
  if (field.enum) base.enum = field.enum;
  if (field.type === 'array' && field.items) base.items = fieldToSchema(field.items);
  if (field.type === 'object' && field.properties) {
    base.properties = Object.fromEntries(
      Object.entries(field.properties).map(([k, v]) => [k, fieldToSchema(v)])
    );
    base.required = field.required ?? Object.keys(field.properties);
    base.additionalProperties = false;
  }
  return base;
}

// === 3. 输出验证器 ===
interface ValidationResult {
  valid: boolean;
  errors: string[];
}

function validateOutput(data: unknown, schema: StructuredSchema): ValidationResult {
  const errors: string[] = [];
  
  if (typeof data !== 'object' || data === null) {
    return { valid: false, errors: ['Output must be an object'] };
  }
  
  const obj = data as Record<string, unknown>;
  const required = schema.required ?? Object.keys(schema.fields);
  
  // Check required fields
  for (const key of required) {
    if (!(key in obj)) {
      errors.push(`Missing required field: ${key}`);
    }
  }
  
  // Validate field types and constraints
  for (const [key, value] of Object.entries(obj)) {
    const field = schema.fields[key];
    if (!field) {
      errors.push(`Unknown field: ${key}`);
      continue;
    }
    
    // Type check
    if (field.type === 'string' && typeof value !== 'string') {
      errors.push(`Field ${key}: expected string, got ${typeof value}`);
    }
    if (field.type === 'number' && typeof value !== 'number') {
      errors.push(`Field ${key}: expected number, got ${typeof value}`);
    }
    
    // Enum check
    if (field.enum && typeof value === 'string' && !field.enum.includes(value)) {
      errors.push(`Field ${key}: "${value}" not in [${field.enum.join(', ')}]`);
    }
  }
  
  return { valid: errors.length === 0, errors };
}

// === 4. Prompt 构建器 ===
function buildStructuredPrompt(
  userPrompt: string,
  schema: StructuredSchema,
  level: 'L1' | 'L2' | 'L3' = 'L3'
): string {
  const jsonSchema = JSON.stringify(toJsonSchema(schema), null, 2);
  
  const levelInstructions: Record<string, string> = {
    'L1': `Return JSON matching this structure. Output ONLY valid JSON, no markdown fences.`,
    'L2': `Call the function "${schema.name}" with the appropriate arguments based on the user input.`,
    'L3': `Respond with JSON that EXACTLY matches this schema. Every required field must be present. No additional fields.\n\nSchema:\n${jsonSchema}`,
  };
  
  return `${levelInstructions[level]}\n\n${userPrompt}`;
}

// === 5. SchemaCache — 避免重复编译 ===
class SchemaCache {
  private cache = new Map<string, { schema: object; compiled: number }>();
  
  get(name: string, builder: () => StructuredSchema): object {
    if (!this.cache.has(name)) {
      const schema = builder();
      this.cache.set(name, {
        schema: toJsonSchema(schema),
        compiled: Date.now(),
      });
    }
    return this.cache.get(name)!.schema;
  }
  
  stats() {
    return { cached: this.cache.size, keys: [...this.cache.keys()] };
  }
}

// === 运行演示 ===
console.log('=== Structured Output Toolkit Prototype ===\n');

// 定义 schema
const articleSchema: StructuredSchema = {
  name: 'ArticleAnalysis',
  description: 'Analyze an article and extract structured information',
  fields: {
    title: { type: 'string', description: 'Article title' },
    sentiment: {
      type: 'string',
      description: 'Overall sentiment',
      enum: ['positive', 'negative', 'neutral', 'mixed'],
    },
    keyPoints: {
      type: 'array',
      description: 'Key points from the article',
      items: { type: 'string', description: 'A key point' },
    },
    confidence: { type: 'number', description: 'Confidence score 0-1' },
  },
};

// 生成 JSON Schema
const jsonSchema = toJsonSchema(articleSchema);
console.log('Generated JSON Schema:');
console.log(JSON.stringify(jsonSchema, null, 2));

// 构建各级别 prompt
console.log('\n--- L1 Prompt ---');
console.log(buildStructuredPrompt(
  'Analyze: AI adoption in enterprise has doubled in 2025',
  articleSchema,
  'L1'
).slice(0, 200) + '...');

console.log('\n--- L3 Prompt (truncated) ---');
console.log(buildStructuredPrompt(
  'Analyze: AI adoption in enterprise has doubled in 2025',
  articleSchema,
  'L3'
).slice(0, 300) + '...');

// 验证测试
console.log('\n=== Validation Tests ===');

const validOutput = {
  title: 'Enterprise AI Adoption Doubles',
  sentiment: 'positive',
  keyPoints: ['AI spending doubled', 'Enterprise adoption accelerates'],
  confidence: 0.85,
};
console.log('Valid output:', validateOutput(validOutput, articleSchema));

const invalidOutput = {
  title: 'Test',
  sentiment: 'excited', // not in enum
  // missing keyPoints and confidence
};
console.log('Invalid output:', validateOutput(invalidOutput, articleSchema));

// SchemaCache 演示
console.log('\n=== SchemaCache ===');
const cache = new SchemaCache();
cache.get('article', () => articleSchema);
cache.get('article', () => articleSchema); // hit cache
console.log('Cache stats:', cache.stats());

console.log('\n✅ Prototype complete. Ready for lab/structured-output-toolkit/');
```

**运行方式**: `npx tsx structured-output-prototype.ts` (零外部依赖)

---

## 关键洞察 (4条)

1. **约束解码是基础设施，不是应用逻辑**。2026年的正确姿势是让推理引擎（OpenAI/vLLM/SGlang）在生成时保证 schema 合规，而不是在应用层做解析+重试。`structured-output-toolkit` 应该是 schema 管理 + 多提供商适配层，不是又一个 JSON parser。

2. **SchemaCache 是性能关键路径**。XGrammar 等 FSM 引擎编译 schema 有开销（尤其复杂 schema），编译后缓存可复用是生产必备。这是 `structured-output-toolkit` 中 `SchemaCache` 设计的核心价值。

3. **语义验证比语法验证更难更有价值**。FSM 保证 `{"score": 999}` 语法正确，但不保证 score 范围合理。toolkit 应该在 schema 定义层支持语义约束（范围、格式、业务规则），这是区别于原生 API 的增值点。

4. **多提供商适配是实际痛点**。OpenAI 用 `response_format`，Anthropic 用 `output_config`，Gemini 用 `response_mime_type`，自部署用 XGrammar 参数。一个统一适配层能消除大量样板代码——这正是 toolkit 的核心价值主张。

---

## 与现有项目关联

- **agent-context-store**: Context 条目的 schema 可以用 toolkit 管理，确保存储层和 API 层 schema 一致
- **prompt-router**: 路由决策的结构化输出可以用 toolkit 的验证层保证质量
- **AMS**: Agent Memory Service 的记忆提取可以受益于结构化输出（从非结构化文本提取结构化记忆条目）

---

## 下一步行动

1. **创建 `lab/structured-output-toolkit/`** — 基于本研究的原型，实现：
   - `SchemaRegistry`: schema 注册 + 缓存 + JSON Schema 生成
   - `StructuredLLMClient`: 多提供商适配（OpenAI/Anthropic/自部署）
   - `SemanticValidator`: 超越语法的业务规则验证
   - 目标: 10+ tests, 支持 3 种提供商适配

2. **benchmark**: 用 JSONSchemaBench 的子集测试验证适配层的 schema 覆盖率

---

## 参考资料

- [LLM Structured Output in 2026: Stop Parsing JSON with Regex](https://dev.to/pockit_tools/llm-structured-output-in-2026-stop-parsing-json-with-regex-and-do-it-right-34pk) — 三级模型总结
- [OpenAI Introducing Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api) — 约束解码原理
- [How Structured Outputs and Constrained Decoding Work](https://letsdatascience.com/blog/structured-outputs-making-llms-return-reliable-json) — 跨平台对比
- [JSONSchemaBench](https://arxiv.org/html/2501.10868v1) — 学术基准测试
- [Structured Outputs for Real Pipelines (2026)](https://collinwilkins.com/articles/structured-output) — XGrammar/Guidance/Outlines 实战对比
