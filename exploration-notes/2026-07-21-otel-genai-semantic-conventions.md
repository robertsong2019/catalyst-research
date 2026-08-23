# Deep Research #023: OpenTelemetry GenAI 语义约定与 Agent 可观测性

> **日期**: 2026-07-21
> **触发**: deep-exploration-evening cron
> **关联项目**: lab/agent-observability (166 tests), agent-memory-graph (4099 tests)
> **来源**: open-telemetry/semantic-conventions-genai (官方仓库, 2026-07-21 快照)

---

## 核心概念

### 1. gen_ai.* 属性体系 — 六层信号模型

OTel GenAI 语义约定定义了六种信号类型，覆盖 AI 系统全链路：

| 信号 | Span 类型 | 关键属性 |
|------|-----------|----------|
| **Inference** (推理) | `gen_ai.inference.client` | `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| **Agent** (智能体) | `gen_ai.create_agent.client` / `gen_ai.invoke_agent.client` | `gen_ai.agent.id`, `gen_ai.agent.name`, `gen_ai.agent.version` |
| **Tool Execution** (工具调用) | `gen_ai.execute_tool` | tool name, duration |
| **Memory** (记忆操作) | Memory-specific spans | `create_memory`, `search_memory`, `upsert_memory`, `delete_memory`, `update_memory` |
| **Retrieval** (检索) | Retrieval spans | `retrieval` operation |
| **Embeddings** (向量嵌入) | Embedding spans | `embeddings` operation |

**重大发现**: `gen_ai.operation.name` 的官方枚举值中 **已包含 memory 操作**：`create_memory`, `search_memory`, `upsert_memory`, `update_memory`, `delete_memory`, `create_memory_store`, `delete_memory_store`。这意味着 agent-memory-graph 的所有操作可以直接映射到 OTel 标准属性。

### 2. Provider 作为鉴别器 — Discriminator 模式

`gen_ai.provider.name` 不只是标签，它是 **telemetry format flavor 的鉴别器**：
- 设置为 `openai` → 遵循 OpenAI 特定属性格式
- 设置为 `aws.bedrock` → 遵循 Bedrock 格式
- 自定义系统可以用任意值（如 `amg` 或 `agent-memory-graph`）

Provider 决定了附加属性的格式约定，这就是为什么规范强调 "SHOULD be set consistently with provider-specific attributes"。

**16 个官方 Provider 枚举**: anthropic, aws.bedrock, azure.ai.inference, azure.ai.openai, cohere, deepseek, gcp.gemini, gcp.gen_ai, gcp.vertex_ai, groq, ibm.watsonx.ai, mistral_ai, moonshot_ai, openai, perplexity, x_ai。

### 3. Metrics 体系 — 四组 Histogram

| Metric | 单位 | 描述 |
|--------|------|------|
| `gen_ai.client.token.usage` | `{token}` | 输入/输出 token 用量 (Histogram, 按 `gen_ai.token.type` 区分 input/output) |
| `gen_ai.client.operation.duration` | `s` | 客户端操作耗时 |
| `gen_ai.client.operation.time_to_first_chunk` | `s` | 流式响应首块延迟 (TTFT) |
| `gen_ai.client.operation.time_per_output_chunk` | `s` | 每块生成时间 |

Agent 专属 metrics：
- `gen_ai.invoke_agent.duration` — Agent 调用总耗时
- `gen_ai.invoke_agent.inference_calls` — Agent 内 LLM 调用次数
- `gen_ai.invoke_agent.tool_calls` — Agent 内工具调用次数

Tool 专属 metrics：
- `gen_ai.execute_tool.duration` — 工具执行耗时

### 4. 内容捕获三级策略

| 级别 | 属性 | 用途 |
|------|------|------|
| **Disabled** | 不记录内容 | 生产环境默认，仅记录 token 计数 |
| **On Span** | `gen_ai.input.messages`, `gen_ai.output.messages` 直接作为 span 属性 | 开发调试 |
| **On Event** | 通过 `gen_ai.client.inference.operation.details` 事件 | 推荐：解耦内容与 trace，支持独立存储 |

**消息格式统一**：`{ role, parts: [{ type, content }] }`，支持 text/tool_call/tool_call_response/image 等多种 part 类型。

### 5. Agent Span 层级模型

OTel 定义了 Agent 的五层 span 层级：

```
invoke_workflow (工作流)
  └── invoke_agent (Agent 调用)
        ├── create_agent (Agent 创建, 通常一次性)
        ├── plan (规划/任务分解)
        ├── inference (LLM 推理, 可能多次)
        └── execute_tool (工具执行)
              └── retrieval/memory (二级操作)
```

Plan span 是一个独立操作类型 `gen_ai.operation.name = plan`，专门用于 Agent 的任务分解/规划阶段。这直接对应了 ReAct、Plan-and-Execute 等 agent 模式。

---

## 可运行代码示例

### 示例 1: OTel GenAI 兼容的 Agent Memory Tracer (TypeScript)

以下代码实现了 `gen_ai.*` 兼容的 memory 操作 tracer，可直接集成到 agent-memory-graph：

```typescript
// gen-ai-memory-tracer.ts
// OTel GenAI 语义约定兼容的 Memory 操作 Tracer
// 依赖: 无（纯 TypeScript，零外部依赖）

interface GenAISpan {
  traceId: string;
  spanId: string;
  parentSpanId: string | null;
  name: string;
  kind: 'CLIENT' | 'INTERNAL';
  startTime: number;
  endTime: number | null;
  attributes: Record<string, unknown>;
  status: 'ok' | 'error' | 'unset';
  events: Array<{ name: string; timestamp: number; attributes?: Record<string, unknown> }>;
}

// gen_ai.operation.name 的 memory 相关枚举
type MemoryOperation =
  | 'create_memory'
  | 'search_memory'
  | 'upsert_memory'
  | 'update_memory'
  | 'delete_memory'
  | 'create_memory_store'
  | 'delete_memory_store';

interface MemoryRecord {
  id: string;
  content: string;
  metadata?: Record<string, unknown>;
}

class GenAIMemoryTracer {
  private spans: GenAISpan[] = [];
  private stack: string[] = [];
  readonly traceId: string;

  constructor(traceId?: string) {
    this.traceId = traceId ?? crypto.randomUUID();
  }

  /** 开始一个 memory 操作 span */
  startMemorySpan(
    operation: MemoryOperation,
    opts: {
      providerName?: string;
      parentSpanId?: string | null;
      attributes?: Record<string, unknown>;
    } = {}
  ): string {
    const spanId = crypto.randomUUID();
    const parentSpanId = opts.parentSpanId
      ?? (this.stack.length > 0 ? this.stack[this.stack.length - 1] : null);

    const span: GenAISpan = {
      traceId: this.traceId,
      spanId,
      parentSpanId,
      name: `${operation} ${opts.providerName ?? 'agent-memory-graph'}`,
      kind: 'INTERNAL',
      startTime: performance.now(),
      endTime: null,
      attributes: {
        'gen_ai.operation.name': operation,
        'gen_ai.provider.name': opts.providerName ?? 'agent-memory-graph',
        ...opts.attributes,
      },
      status: 'unset',
      events: [],
    };

    this.spans.push(span);
    this.stack.push(spanId);
    return spanId;
  }

  /** 结束 span */
  endSpan(spanId: string, attributes?: Record<string, unknown>): void {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span) throw new Error(`Span ${spanId} not found`);
    span.endTime = performance.now();
    span.status = 'ok';
    if (attributes) Object.assign(span.attributes, attributes);
    // pop from stack
    const idx = this.stack.lastIndexOf(spanId);
    if (idx >= 0) this.stack.splice(idx, 1);
  }

  /** 添加错误 */
  markError(spanId: string, errorType: string, message: string): void {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span) return;
    span.status = 'error';
    span.attributes['error.type'] = errorType;
    span.events.push({
      name: 'exception',
      timestamp: performance.now(),
      attributes: { 'exception.message': message, 'error.type': errorType },
    });
  }

  /** 记录 token 使用量 (gen_ai.usage.* 属性) */
  recordTokenUsage(spanId: string, inputTokens: number, outputTokens: number): void {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span) return;
    span.attributes['gen_ai.usage.input_tokens'] = inputTokens;
    span.attributes['gen_ai.usage.output_tokens'] = outputTokens;
  }

  /** 导出为 OTel-compatible JSON */
  export(): { traceId: string; spans: GenAISpan[]; metrics: object } {
    const tokenMetrics = this.spans
      .filter(s => s.attributes['gen_ai.usage.input_tokens'] !== undefined)
      .map(s => ({
        name: 'gen_ai.client.token.usage',
        value: s.attributes['gen_ai.usage.input_tokens'],
        attributes: {
          'gen_ai.operation.name': s.attributes['gen_ai.operation.name'],
          'gen_ai.provider.name': s.attributes['gen_ai.provider.name'],
          'gen_ai.token.type': 'input',
        },
      }));

    return {
      traceId: this.traceId,
      spans: this.spans,
      metrics: {
        'gen_ai.client.token.usage': tokenMetrics,
        'gen_ai.client.operation.duration': this.spans
          .filter(s => s.endTime !== null)
          .map(s => ({
            name: 'gen_ai.client.operation.duration',
            value: (s.endTime! - s.startTime) / 1000,
            attributes: {
              'gen_ai.operation.name': s.attributes['gen_ai.operation.name'],
              'gen_ai.provider.name': s.attributes['gen_ai.provider.name'],
            },
          })),
      },
    };
  }
}

// ===== 可运行演示 =====
const tracer = new GenAIMemoryTracer();

// 模拟 agent-memory-graph 的 search 操作
const searchSpan = tracer.startMemorySpan('search_memory', {
  attributes: {
    'gen_ai.request.model': 'text-embedding-3-small',
    'amg.query': 'semantic search: "agent memory patterns"',
    'amg.top_k': 5,
  },
});

// 模拟处理时间
await new Promise(r => setTimeout(r, 15));

tracer.recordTokenUsage(searchSpan, 42, 0); // embedding tokens
tracer.endSpan(searchSpan, {
  'amg.results_count': 5,
  'amg.top_score': 0.92,
});

// 模拟 create memory 操作
const createSpan = tracer.startMemorySpan('create_memory', {
  attributes: {
    'amg.node_type': 'entity',
    'amg.content_preview': 'Catalyst is a digital familiar',
  },
});
await new Promise(r => setTimeout(r, 8));
tracer.endSpan(createSpan, {
  'amg.node_id': 'node_abc123',
});

// 导出
const report = tracer.export();
console.log('=== OTel GenAI Trace Report ===');
console.log(`Trace ID: ${report.traceId}`);
console.log(`Spans: ${report.spans.length}`);
for (const span of report.spans) {
  const dur = span.endTime ? `${(span.endTime - span.startTime).toFixed(2)}ms` : 'open';
  console.log(`  ${span.name} [${span.status}] ${dur}`);
  console.log(`    op=${span.attributes['gen_ai.operation.name']} provider=${span.attributes['gen_ai.provider.name']}`);
  if (span.attributes['gen_ai.usage.input_tokens']) {
    console.log(`    tokens: in=${span.attributes['gen_ai.usage.input_tokens']} out=${span.attributes['gen_ai.usage.output_tokens']}`);
  }
}
console.log(`\nMetrics: ${Object.keys(report.metrics).join(', ')}`);
```

运行方式：
```bash
npx tsx gen-ai-memory-tracer.ts
```

预期输出：
```
=== OTel GenAI Trace Report ===
Trace ID: <uuid>
Spans: 2
  search_memory agent-memory-graph [ok] ~15ms
    op=search_memory provider=agent-memory-graph
    tokens: in=42 out=0
  create_memory agent-memory-graph [ok] ~8ms
    op=create_memory provider=agent-memory-graph

Metrics: gen_ai.client.token.usage, gen_ai.client.operation.duration
```

### 示例 2: CostAggregator — 基于 gen_ai.usage.* 的成本计算器

```typescript
// cost-aggregator.ts
// 基于 OTel gen_ai.usage.* 属性的成本聚合器
// 适用于 lab/agent-observability 的 CostAggregator 需求

interface PricingTier {
  inputPer1k: number;   // USD per 1K input tokens
  outputPer1k: number;  // USD per 1K output tokens
  cacheReadPer1k?: number;
  cacheWritePer1k?: number;
}

const PRICING: Record<string, PricingTier> = {
  'gpt-4': { inputPer1k: 0.03, outputPer1k: 0.06 },
  'gpt-4o': { inputPer1k: 0.005, outputPer1k: 0.015 },
  'gpt-4o-mini': { inputPer1k: 0.00015, outputPer1k: 0.0006 },
  'claude-3.5-sonnet': { inputPer1k: 0.003, outputPer1k: 0.015 },
  'text-embedding-3-small': { inputPer1k: 0.00002, outputPer1k: 0 },
};

class CostAggregator {
  private entries: Array<{
    model: string;
    inputTokens: number;
    outputTokens: number;
    cacheReadTokens: number;
    cacheWriteTokens: number;
    cost: number;
    operation: string;
    timestamp: number;
  }> = [];

  /** 从 OTel span 属性提取成本 */
  recordFromSpan(attrs: Record<string, unknown>, timestamp: number = Date.now()): void {
    const model = String(attrs['gen_ai.response.model'] ?? attrs['gen_ai.request.model'] ?? 'unknown');
    const operation = String(attrs['gen_ai.operation.name'] ?? 'unknown');
    const inputTokens = Number(attrs['gen_ai.usage.input_tokens'] ?? 0);
    const outputTokens = Number(attrs['gen_ai.usage.output_tokens'] ?? 0);
    const cacheRead = Number(attrs['gen_ai.usage.cache_read.input_tokens'] ?? 0);
    const cacheWrite = Number(attrs['gen_ai.usage.cache_creation.input_tokens'] ?? 0);

    const pricing = PRICING[model] ?? { inputPer1k: 0.001, outputPer1k: 0.002 };
    const cost =
      (inputTokens / 1000) * pricing.inputPer1k +
      (outputTokens / 1000) * pricing.outputPer1k +
      (cacheRead / 1000) * (pricing.cacheReadPer1k ?? pricing.inputPer1k * 0.5) +
      (cacheWrite / 1000) * (pricing.cacheWritePer1k ?? pricing.inputPer1k * 1.25);

    this.entries.push({
      model, inputTokens, outputTokens, cacheReadTokens: cacheRead, cacheWriteTokens: cacheWrite,
      cost, operation, timestamp,
    });
  }

  /** 生成成本报告 */
  report(): {
    totalCost: number;
    totalInputTokens: number;
    totalOutputTokens: number;
    byModel: Record<string, { calls: number; cost: number; tokens: number }>;
    byOperation: Record<string, { calls: number; cost: number }>;
  } {
    const byModel: Record<string, { calls: number; cost: number; tokens: number }> = {};
    const byOperation: Record<string, { calls: number; cost: number }> = {};

    let totalCost = 0, totalInputTokens = 0, totalOutputTokens = 0;

    for (const e of this.entries) {
      totalCost += e.cost;
      totalInputTokens += e.inputTokens;
      totalOutputTokens += e.outputTokens;

      if (!byModel[e.model]) byModel[e.model] = { calls: 0, cost: 0, tokens: 0 };
      byModel[e.model].calls++;
      byModel[e.model].cost += e.cost;
      byModel[e.model].tokens += e.inputTokens + e.outputTokens;

      if (!byOperation[e.operation]) byOperation[e.operation] = { calls: 0, cost: 0 };
      byOperation[e.operation].calls++;
      byOperation[e.operation].cost += e.cost;
    }

    return { totalCost, totalInputTokens, totalOutputTokens, byModel, byOperation };
  }
}

// 演示
const agg = new CostAggregator();

// 模拟 OTel span 属性
agg.recordFromSpan({
  'gen_ai.operation.name': 'chat',
  'gen_ai.request.model': 'gpt-4o',
  'gen_ai.response.model': 'gpt-4o-2024-08-06',
  'gen_ai.usage.input_tokens': 1500,
  'gen_ai.usage.output_tokens': 300,
});

agg.recordFromSpan({
  'gen_ai.operation.name': 'search_memory',
  'gen_ai.request.model': 'text-embedding-3-small',
  'gen_ai.usage.input_tokens': 800,
  'gen_ai.usage.output_tokens': 0,
});

agg.recordFromSpan({
  'gen_ai.operation.name': 'chat',
  'gen_ai.request.model': 'gpt-4o',
  'gen_ai.response.model': 'gpt-4o-2024-08-06',
  'gen_ai.usage.input_tokens': 2000,
  'gen_ai.usage.output_tokens': 500,
  'gen_ai.usage.cache_read.input_tokens': 1500,
});

const r = agg.report();
console.log('=== Cost Report ===');
console.log(`Total: $${r.totalCost.toFixed(4)} | In: ${r.totalInputTokens} | Out: ${r.totalOutputTokens}`);
console.log('By Model:', Object.entries(r.byModel).map(([k,v]) => `${k}: ${v.calls} calls, $${v.cost.toFixed(4)}`));
console.log('By Op:', Object.entries(r.byOperation).map(([k,v]) => `${k}: ${v.calls} calls, $${v.cost.toFixed(4)}`));
```

---

## 关键洞察

### 1. OTel GenAI 规范已原生支持 Memory 操作 — 这是 agent-memory-graph 的战略对齐点

`gen_ai.operation.name` 枚举中包含了 `create_memory`、`search_memory`、`upsert_memory`、`update_memory`、`delete_memory`、`create_memory_store`、`delete_memory_store` 共 **7 个 memory 专用操作类型**。这意味着 OTel 规范制定者已经将 Agent Memory 作为一等公民纳入标准。

**战略含义**: agent-memory-graph 如果在 amg 的 API 层面直接输出 `gen_ai.*` 兼容的 span 属性，就可以与任何 OTel-compatible 的可观测性后端（Jaeger, Tempo, Datadog, Honeycomb）无缝集成。这是**合规即营销**（compliance as marketing）的机会——"4099 tests + OTel GenAI compatible" 是 npm 发布的差异化卖点。

### 2. Provider Discriminator 模式解决了多供应商遥测格式混乱

当前 lab/agent-observability 使用自定义的 `SpanOperation` 类型（`'agent.run' | 'llm.call' | 'tool.execute' | ...`），这是 **pre-standard 风格**。OTel 的 `gen_ai.provider.name` discriminator 模式意味着：

- 同一个 trace 中可以混合 OpenAI 调用 + AMG memory 调用 + 自定义工具
- 每个调用有自己的 provider 特定属性
- 后端可以按 provider 做聚合/过滤

**升级路径**: 将 `SpanOperation` 的 `'memory.read'` → `gen_ai.operation.name = 'search_memory'`，`'memory.write'` → `gen_ai.operation.name = 'create_memory'`，保持内部 API 不变，仅修改属性命名。

### 3. 三级内容捕获策略解决了 PII 与调试的矛盾

现有 tracer 没有内容捕获策略——要么记要么不记。OTel 的三级策略（Disabled → On Span → On Event）提供了更精细的控制：

- **生产环境**: Disabled（仅 token 计数 + 延迟）
- **预发环境**: On Event（通过 `gen_ai.client.inference.operation.details` 事件，内容独立于 trace 存储）
- **开发环境**: On Span（直接作为 span 属性，便于 Jaeger UI 查看）

这对 amg 的 `query_explain()` 诊断工具特别有价值——可以在 Event 级别捕获查询计划和匹配详情，不污染主 trace。

### 4. Agent Span 层级模型直接映射到 OpenClaw 的 cron → spawn → tool 执行链

OTel 的五层 Agent span 模型（workflow → agent → plan → inference → tool）完美映射到 OpenClaw 的执行流：

```
invoke_workflow = cron job / heartbeat
  └── invoke_agent = sessions_spawn / main session
        ├── plan = 任务分解（如 autoresearch 方法论）
        ├── inference = LLM API 调用
        └── execute_tool = read/write/exec/message
              └── search_memory / create_memory = amg 操作
```

### 5. Metrics 与 Spans 分离 — CostAggregator 应该消费 Metrics，不是 Spans

OTel 规范将 token usage 同时定义为 Span 属性（`gen_ai.usage.input_tokens`）和 Histogram Metric（`gen_ai.client.token.usage`）。这意味着 CostAggregator 有两个数据源：
- **实时路径**: 直接从 span 属性提取（当前代码做法，适合开发期）
- **聚合路径**: 从 OTel Metric pipeline 消费（适合生产期，可接入 Prometheus/Grafana）

**架构建议**: CostAggregator 应该定义一个 `FromSpan` 和 `FromMetric` 双入口，这样开发时直接接 span，生产时接 metric pipeline。

---

## 下一步行动

### A. 立即可做 — lab/agent-observability 属性对齐 (1 cycle, ~30 tests)

1. 在 `tracer.ts` 中添加 `GenAIAttributes` 类型，映射现有 `SpanOperation` → `gen_ai.operation.name`
2. 修改 `startSpan()` 方法，自动设置 `gen_ai.provider.name` 和 `gen_ai.operation.name`
3. 在 `endSpan()` 中自动计算并设置 `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens`（如果有）
4. 添加 `toOTelJSON()` 方法，输出 OTel-compatible trace JSON
5. 测试验证每个 span 的属性命名符合规范

### B. agent-memory-graph OTel 适配层 (独立模块, ~50 tests)

1. 创建 `src/otel/otel-tracer.ts` — 包装 amg 的核心操作（recall/remember/query/forget）
2. 每个操作自动产出 `gen_ai.*` 兼容 span
3. 使用 provider name `amg`（或 `agent-memory-graph`）
4. 这个模块可以作为 amg 的**差异化 npm 功能**——"内置 OTel GenAI 可观测性"

### C. CostAggregator 升级 (在 lab/agent-observability 中, ~20 tests)

1. 替换硬编码价格为可配置 pricing table
2. 支持 `gen_ai.usage.cache_read.input_tokens` 和 `gen_ai.usage.cache_creation.input_tokens`
3. 输出按 model/operation/provider 三维聚合
4. 支持 JSON export 格式（与 Grafana dashboard 兼容）

---

## 参考来源

1. **OTel GenAI Semantic Conventions** (官方仓库, 2026-07):
   - Spans: https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md
   - Agent Spans: https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md
   - Metrics: https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md
   - Events: https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md
   - LLM Call Examples: https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/non-normative/examples-llm-calls.md

2. **现有项目代码**:
   - `lab/agent-observability/src/tracer.ts` — 自定义 tracer (525+ lines, 166 tests)
   - `agent-memory-graph` — 4099 tests, 785+ APIs

3. **OTel Core Spec**:
   - Span naming: https://github.com/open-telemetry/opentelemetry-specification/blob/v1.56.0/specification/trace/api.md#span
   - Recording errors: https://github.com/open-telemetry/semantic-conventions/blob/v1.43.0/docs/general/recording-errors.md

---

_Quality check: ✅ 5 core concepts, ✅ 2 runnable code examples, ✅ 5 key insights, ✅ 3 next actions, ✅ linked to existing projects (lab/agent-observability + agent-memory-graph)_
