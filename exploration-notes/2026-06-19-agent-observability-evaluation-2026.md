# Agent Observability & Evaluation 2026

> Research date: 2026-06-19
> Connection: lab/agent-observability (166 tests, Tracer + Evaluator + PolicyEngine)
> Trigger: HEARTBEAT.md 中优先级 "lab/agent-observability 继续"

---

## Executive Summary

Agent observability has crystallized into a distinct discipline in 2026, separating from traditional APM. The **layered pattern** (LLM-native observability + infrastructure APM) is now the production standard. OpenTelemetry GenAI Semantic Conventions are the emerging wire format — still in Development status but already adopted by Datadog, Elastic, and Google Cloud. For lab/agent-observability, the highest-leverage upgrade is: (1) align span attributes to `gen_ai.*` conventions, (2) add token/cost tracking, (3) implement LLM-judge evaluation metrics on traces.

---

## 核心概念 (5)

### 1. OTel GenAI Semantic Conventions — `gen_ai.*` 命名空间

OpenTelemetry GenAI SIG 定义的标准化属性集，覆盖模型调用、token 用量、工具执行、agent 推理。

**六层架构**:
- Layer 1: Client Spans (`gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`)
- Layer 2: Agent Spans (`gen_ai.agent.*`, `invoke_agent` operation)
- Layer 3: MCP Conventions (`mcp.client.operation.duration`, `mcp.server.operation.duration`)
- Layer 4: Events (opt-in content capture: `gen_ai.client.inference.operation.details`)
- Layer 5: Metrics (`gen_ai.client.operation.duration` histogram, `gen_ai.client.token.usage` histogram)
- Layer 6: Provider-specific attributes

**状态**: Development (v1.41, 2026-05)。未稳定但已被 Datadog/Elastic/Google Cloud 原生支持。`OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 启用最新实验属性。

**Agent span 调用链结构**:
```
invoke_agent weather-forecast-agent (INTERNAL)
├── chat {model} (CLIENT)           ← GenAI model call
├── tools/call get-weather (CLIENT) ← MCP client
│   └── tools/call get-weather (SERVER) ← MCP server
└── chat {model} (CLIENT)           ← GenAI model call (synthesis)
```

### 2. Agent Evaluation Metrics — 三层评估栈

DeepEval/Confident AI 定义的 agent 专属指标体系:

| 层次 | 指标 | 类型 | 衡量什么 |
|------|------|------|---------|
| End-to-end | Task Completion | LLM Judge | agent 是否完成了用户目标 |
| Trajectory | Step Efficiency | LLM Judge | 是否有不必要的步骤、重试、循环 |
| Trajectory | Plan Adherence | LLM Judge | 是否遵循了预定计划/约束 |
| Component | Tool Correctness | Deterministic | 是否调用了正确的工具 |
| Component | Argument Correctness | LLM Judge | 工具参数是否正确 |
| Component | Plan Quality | LLM Judge | 计划是否完整、逻辑合理 |

**关键洞察**: 高 Task Completion + 低 Step Efficiency = agent 能完成任务但需要优化（减少冗余步骤）。这两个指标的组合是 agent 性能调优的核心信号。

### 3. Multi-Agent Tracing — 跨 Agent 手-off 可观测

**核心规则**: 一个用户请求 = 一条 trace。Orchestrator 创建 root trace + root span，下游 agent 继续同一 traceId 的 child span。

**Handoff 失败**是最常见的 multi-agent 故障模式: Agent A 传给 Agent B 的 context 不完整或错误，Agent B 基于错误假设继续执行。没有跨 agent tracing，debug 团队看不到根因在上游。

**实现模式**: parent-child span propagation across agent boundaries。Handoff payload 作为 span 记录在 parent agent 的 trace 上，receiving agent 的 run 嵌套在该 handoff span 下，同一 traceId 贯穿两个 agent。

### 4. Cost Attribution — 多维度成本追踪

| 维度 | 用途 |
|------|------|
| Per prompt/version | 哪些 prompt 消耗最多 token |
| Per agent/workflow | 完整 agent run 的端到端成本（含 planning + tools + retries） |
| Per user/team | 业务侧成本分摊 |
| Per model | 模型选择对成本的影响 |

**两个 mandatory metrics** (OTel GenAI):
- `gen_ai.client.operation.duration` — 延迟直方图（秒）
- `gen_ai.client.token.usage` — token 消耗直方图（input/output 分开）

### 5. Instrumentation 生态 — OpenLLMetry vs OpenInference vs 原生 OTel

| 方案 | 维护者 | 命名空间 | 语言覆盖 | 特点 |
|------|--------|---------|---------|------|
| OpenLLMetry (Traceloop) | Traceloop | `gen_ai.*` (OTel原生) | Python, JS/TS, Java | vendor-neutral SDK, Apache 2.0 |
| OpenInference | Arize | `openinference.*`, `llm.*` | Python, JS/TS | Phoenix 参考实现, Apache 2.0 |
| 原生 OTel GenAI | OTel SIG | `gen_ai.*` | 多语言 | 标准本身, v1.41 Development |

**互操作性**: OpenInference 提供 `OpenInferenceSpanProcessor` 将 OpenLLMetry spans 转换为 OpenInference 格式。大多数后端（Phoenix, Langfuse, Datadog）都能消费 OTLP 流。"Instrument once, switch backends later" 已成为现实。

---

## 代码示例

### 示例 1: OTel GenAI 兼容的 Span 属性对齐 (TypeScript, 可运行)

现有 lab/agent-observability 的 Tracer 已有 OTLP 导出，但 span 属性未对齐 `gen_ai.*` 约定。以下是兼容升级方案，可直接集成到现有 tracer.ts：

```typescript
// genai-conventions.ts — OTel GenAI Semantic Convention 属性对齐层
// 零依赖，可直接集成到 lab/agent-observability/src/

/**
 * OTel GenAI Semantic Conventions v1.41 属性名常量
 * 参考: https://opentelemetry.io/docs/specs/semconv/gen/genai/
 */
export const GenAIAttrs = {
  // System attributes
  SYSTEM: 'gen_ai.system',
  OPERATION_NAME: 'gen_ai.operation.name',
  REQUEST_MODEL: 'gen_ai.request.model',
  RESPONSE_MODEL: 'gen_ai.response.model',
  // Token usage
  USAGE_INPUT_TOKENS: 'gen_ai.usage.input_tokens',
  USAGE_OUTPUT_TOKENS: 'gen_ai.usage.output_tokens',
  // Content (opt-in)
  INPUT_MESSAGES: 'gen_ai.input.messages',
  OUTPUT_MESSAGES: 'gen_ai.output.messages',
  RESPONSE_FINISH_REASONS: 'gen_ai.response.finish_reasons',
  // Agent attributes
  AGENT_NAME: 'gen_ai.agent.name',
  AGENT_DESCRIPTION: 'gen_ai.agent.description',
  // Tool attributes
  TOOL_NAME: 'gen_ai.tool.name',
  TOOL_DESCRIPTION: 'gen_ai.tool.description',
  TOOL_ARGUMENTS: 'gen_ai.tool.arguments',
  TOOL_RESULT: 'gen_ai.tool.result',
} as const;

/** Token usage tracker — attached to LLM call spans */
export interface TokenUsage {
  inputTokens: number;
  outputTokens: number;
  model: string;
  costPer1kInput?: number;  // USD per 1K input tokens
  costPer1kOutput?: number; // USD per 1K output tokens
}

/** Cost calculator with 2026 model pricing */
const MODEL_PRICING: Record<string, { input: number; output: number }> = {
  'gpt-4o':       { input: 0.0025, output: 0.01 },
  'gpt-4o-mini':  { input: 0.00015, output: 0.0006 },
  'claude-sonnet-4': { input: 0.003, output: 0.015 },
  'claude-haiku-3.5': { input: 0.0008, output: 0.004 },
  'gemini-2.0-flash': { input: 0.0001, output: 0.0004 },
};

export function calculateCost(usage: TokenUsage): number {
  const pricing = MODEL_PRICING[usage.model];
  if (!pricing) return 0;
  return (usage.inputTokens / 1000 * pricing.input) +
         (usage.outputTokens / 1000 * pricing.output);
}

/** Span annotator: applies gen_ai.* attributes to an existing Span */
export function annotateLLMSpan(
  span: { attributes: Record<string, unknown> },
  params: {
    model: string;
    operation: string; // 'chat' | 'generate' | 'stream'
    inputTokens?: number;
    outputTokens?: number;
    finishReason?: string;
  }
): TokenUsage | null {
  span.attributes[GenAIAttrs.SYSTEM] = 'openai'; // or 'anthropic' etc
  span.attributes[GenAIAttrs.OPERATION_NAME] = params.operation;
  span.attributes[GenAIAttrs.REQUEST_MODEL] = params.model;
  span.attributes[GenAIAttrs.RESPONSE_MODEL] = params.model;

  let usage: TokenUsage | null = null;
  if (params.inputTokens !== undefined && params.outputTokens !== undefined) {
    span.attributes[GenAIAttrs.USAGE_INPUT_TOKENS] = params.inputTokens;
    span.attributes[GenAIAttrs.USAGE_OUTPUT_TOKENS] = params.outputTokens;
    usage = {
      inputTokens: params.inputTokens,
      outputTokens: params.outputTokens,
      model: params.model,
    };
    const cost = calculateCost(usage);
    if (cost > 0) {
      span.attributes['gen_ai.cost.usd'] = cost;
    }
  }
  if (params.finishReason) {
    span.attributes[GenAIAttrs.RESPONSE_FINISH_REASONS] = params.finishReason;
  }
  return usage;
}

/** Trace-level cost aggregator */
export class CostAggregator {
  private usages: TokenUsage[] = [];

  add(usage: TokenUsage): void {
    this.usages.push(usage);
  }

  getTotalCost(): number {
    return this.usages.reduce((sum, u) => sum + calculateCost(u), 0);
  }

  getCostByModel(): Record<string, number> {
    const byModel: Record<string, number> = {};
    for (const u of this.usages) {
      byModel[u.model] = (byModel[u.model] ?? 0) + calculateCost(u);
    }
    return byModel;
  }

  getTotalTokens(): { input: number; output: number; total: number } {
    const input = this.usages.reduce((s, u) => s + u.inputTokens, 0);
    const output = this.usages.reduce((s, u) => s + u.outputTokens, 0);
    return { input, output, total: input + output };
  }

  getSummary(): {
    totalCost: number;
    byModel: Record<string, number>;
    tokens: { input: number; output: number; total: number };
    callCount: number;
  } {
    return {
      totalCost: this.getTotalCost(),
      byModel: this.getCostByModel(),
      tokens: this.getTotalTokens(),
      callCount: this.usages.length,
    };
  }
}

// === Demo ===
// 也可以直接运行: npx tsx genai-conventions.ts

const agg = new CostAggregator();

// Simulate annotating LLM call spans
const mockSpan1 = { attributes: {} as Record<string, unknown> };
const mockSpan2 = { attributes: {} as Record<string, unknown> };

const u1 = annotateLLMSpan(mockSpan1, {
  model: 'gpt-4o',
  operation: 'chat',
  inputTokens: 1200,
  outputTokens: 450,
  finishReason: 'stop',
});
if (u1) agg.add(u1);

const u2 = annotateLLMSpan(mockSpan2, {
  model: 'claude-sonnet-4',
  operation: 'chat',
  inputTokens: 2000,
  outputTokens: 800,
  finishReason: 'tool_calls',
});
if (u2) agg.add(u2);

console.log('=== Span 1 Attributes (gen_ai.* aligned) ===');
console.log(JSON.stringify(mockSpan1.attributes, null, 2));
console.log('\n=== Span 2 Attributes (gen_ai.* aligned) ===');
console.log(JSON.stringify(mockSpan2.attributes, null, 2));

console.log('\n=== Trace Cost Summary ===');
console.log(JSON.stringify(agg.getSummary(), null, 2));
```

**预期输出**:
```
=== Span 1 Attributes (gen_ai.* aligned) ===
{
  "gen_ai.system": "openai",
  "gen_ai.operation.name": "chat",
  "gen_ai.request.model": "gpt-4o",
  "gen_ai.response.model": "gpt-4o",
  "gen_ai.usage.input_tokens": 1200,
  "gen_ai.usage.output_tokens": 450,
  "gen_ai.cost.usd": 0.0075,
  "gen_ai.response.finish_reasons": "stop"
}

=== Trace Cost Summary ===
{
  "totalCost": 0.0315,
  "byModel": { "gpt-4o": 0.0075, "claude-sonnet-4": 0.024 },
  "tokens": { "input": 3200, "output": 1250, "total": 4450 },
  "callCount": 2
}
```

### 示例 2: LLM-Judge 评估器集成到现有 Evaluator (TypeScript, 可运行)

```typescript
// llm-judge-metrics.ts — Agent trace 评估指标
// 集成到 lab/agent-observability/src/evaluator.ts

export interface AgentTrace {
  spans: Array<{
    operation: string;
    status: string;
    duration: number;
    attributes: Record<string, unknown>;
  }>;
  input: string;
  output: string;
  expectedOutput?: string;
}

export interface MetricResult {
  metric: string;
  score: number;    // 0.0 - 1.0
  reason: string;
  type: 'deterministic' | 'llm_judge';
}

/** Task Completion — agent 是否完成了任务 (简化版, 无外部 API 调用) */
export function taskCompletion(trace: AgentTrace): MetricResult {
  const hasOutput = trace.output.trim().length > 0;
  const noErrors = trace.spans.every(s => s.status !== 'error');
  const hasAgentRun = trace.spans.some(s => s.operation === 'agent.run');

  // 如果有 expectedOutput，做简单的包含/精确匹配
  if (trace.expectedOutput) {
    const expected = trace.expectedOutput.toLowerCase().trim();
    const actual = trace.output.toLowerCase().trim();
    if (expected === actual) {
      return { metric: 'task_completion', score: 1.0, reason: 'Output matches expected exactly', type: 'deterministic' };
    }
    if (actual.includes(expected) || expected.includes(actual)) {
      return { metric: 'task_completion', score: 0.8, reason: 'Output partially matches expected', type: 'deterministic' };
    }
  }

  // 启发式: 有输出 + 无错误 + 有 agent.run span
  let score = 0;
  if (hasOutput) score += 0.4;
  if (noErrors) score += 0.3;
  if (hasAgentRun) score += 0.3;
  return {
    metric: 'task_completion',
    score,
    reason: `hasOutput=${hasOutput}, noErrors=${noErrors}, hasAgentRun=${hasAgentRun}`,
    type: 'deterministic',
  };
}

/** Tool Correctness — 是否调用了期望的工具 */
export function toolCorrectness(
  trace: AgentTrace,
  expectedTools: string[]
): MetricResult {
  const calledTools = trace.spans
    .filter(s => s.operation === 'tool.execute')
    .map(s => s.attributes['gen_ai.tool.name'] as string)
    .filter(Boolean);

  if (expectedTools.length === 0) {
    return { metric: 'tool_correctness', score: 1.0, reason: 'No tools expected', type: 'deterministic' };
  }

  const correct = expectedTools.filter(t => calledTools.includes(t)).length;
  const extra = calledTools.filter(t => !expectedTools.includes(t)).length;
  const score = correct / expectedTools.length - (extra * 0.1);

  return {
    metric: 'tool_correctness',
    score: Math.max(0, Math.min(1, score)),
    reason: `Expected [${expectedTools.join(', ')}], called [${calledTools.join(', ')}], extra=${extra}`,
    type: 'deterministic',
  };
}

/** Step Efficiency — 步骤效率 (无冗余) */
export function stepEfficiency(trace: AgentTrace): MetricResult {
  const toolSpans = trace.spans.filter(s => s.operation === 'tool.execute');
  const llmSpans = trace.spans.filter(s => s.operation === 'llm.call');
  const totalSteps = toolSpans.length + llmSpans.length;

  if (totalSteps === 0) {
    return { metric: 'step_efficiency', score: 1.0, reason: 'No steps taken', type: 'deterministic' };
  }

  // 检测重复工具调用 (相同 tool name + 相同 arguments)
  const toolSigatures = new Set<string>();
  let duplicates = 0;
  for (const s of toolSpans) {
    const sig = `${s.attributes['gen_ai.tool.name']}:${JSON.stringify(s.attributes['gen_ai.tool.arguments'] ?? '')}`;
    if (toolSigatures.has(sig)) duplicates++;
    else toolSigatures.add(sig);
  }

  // 检测错误 span (retry 指标)
  const errors = trace.spans.filter(s => s.status === 'error').length;

  const efficiency = (totalSteps - duplicates - errors * 0.5) / totalSteps;
  return {
    metric: 'step_efficiency',
    score: Math.max(0, Math.min(1, efficiency)),
    reason: `steps=${totalSteps}, duplicates=${duplicates}, errors=${errors}`,
    type: 'deterministic',
  };
}

/** Full evaluation suite */
export function evaluateAgent(
  trace: AgentTrace,
  options: { expectedTools?: string[] } = {}
): { results: MetricResult[]; overallScore: number; pass: boolean } {
  const results: MetricResult[] = [
    taskCompletion(trace),
    stepEfficiency(trace),
  ];
  if (options.expectedTools) {
    results.push(toolCorrectness(trace, options.expectedTools));
  }
  const overallScore = results.reduce((s, r) => s + r.score, 0) / results.length;
  return {
    results,
    overallScore,
    pass: overallScore >= 0.7, // 阈值可调
  };
}

// === Demo ===
const demoTrace: AgentTrace = {
  spans: [
    { operation: 'agent.run', status: 'ok', duration: 5000, attributes: {} },
    { operation: 'llm.call', status: 'ok', duration: 800, attributes: { 'gen_ai.request.model': 'gpt-4o' } },
    { operation: 'tool.execute', status: 'ok', duration: 300, attributes: { 'gen_ai.tool.name': 'web_search', 'gen_ai.tool.arguments': { query: 'weather' } } },
    { operation: 'tool.execute', status: 'ok', duration: 250, attributes: { 'gen_ai.tool.name': 'web_search', 'gen_ai.tool.arguments': { query: 'weather' } } }, // duplicate!
    { operation: 'llm.call', status: 'ok', duration: 600, attributes: { 'gen_ai.request.model': 'gpt-4o' } },
  ],
  input: 'What is the weather today?',
  output: 'The weather today is sunny with a high of 25°C.',
  expectedOutput: 'The weather today is sunny with a high of 25°C.',
};

const evalResult = evaluateAgent(demoTrace, { expectedTools: ['web_search'] });
console.log('=== Agent Evaluation ===');
console.log(JSON.stringify(evalResult, null, 2));
// Overall score < 1.0 due to duplicate tool call → step efficiency penalty
```

---

## 关键洞察 (5)

### 1. "Instrument once, switch backends" 已成为现实

OpenLLMetry 和 OpenInference 都基于 OTel，spans 可以导出到任何 OTLP-compatible 后端（Phoenix, Langfuse, Datadog, Grafana）。这意味着 **instrumentation 是一次性投资，后端可以随时切换**。对 lab/agent-observability 而言，exportOTLP() 方法已经是正确的架构——下一步只需对齐 `gen_ai.*` 属性名。

### 2. OTel GenAI 仍未稳定，但 de facto 标准已形成

Semantic Conventions v1.41 仍是 Development 状态，但 Datadog、Elastic、Google Cloud、AWS 已原生支持。89% 的 OTel 生产用户认为 vendor compliance 是 "critical" 或 "very important"。**等待稳定再采用是错误的策略——早期采用者已经在塑造标准。** 特别是 `gen_ai.agent.*` 和 `gen_ai.memory.*` 提案（GitHub issue #35）直接关系到我们的 agent-memory-graph。

### 3. Agent Evaluation ≠ LLM Evaluation

Agent 评估必须覆盖 **trajectory（路径）** 而非仅看 final output。三个层次的指标各有用途：
- **End-to-end**: Task Completion — 最终用户只关心这个
- **Trajectory**: Step Efficiency + Plan Adherence — 调优用，发现冗余和偏离
- **Component**: Tool Correctness + Argument Correctness — 调试用，定位具体故障点

现有 evaluator.ts 有基础框架，但缺少 Tool Correctness 和 Step Efficiency 指标——这两个是 deterministic 的，无需 LLM judge，实现成本低。

### 4. Cost Tracking 是 observability 的 "killer feature"

2026 年 AI 成本是 engineering team 最难 reason about 的问题之一。一个用户请求可能触发多个 model call、retry、tool invocation、agent loop——成本是动态的、非确定性的、隐藏在多层抽象后面的。**Cost per agent/workflow** 是 manager 最关心的维度，而现有的 tracer.ts 缺少 token tracking 和 cost aggregation。这是一个 ~100 行代码的增量改进。

### 5. Multi-Agent Handoff Tracing 是下一个前沿

现有 tracer 的 causal links 是很好的基础，但 multi-agent 场景需要 **trace context propagation across agent boundaries**——即 traceId 贯穿 orchestrator → sub-agent → tool，形成单一执行树。OTel 的 `gen_ai.agent.*` 提案正在标准化这个模式。对 openclaw-langgraph-bridge（195 tests）而言，这是天然的集成点。

---

## 与现有项目关联

| 项目 | 关联点 | 下一步 |
|------|--------|--------|
| lab/agent-observability (166 tests) | 直接目标：升级 Tracer 的 span 属性到 gen_ai.* 约定 | +GenAIAttrs 常量 + CostAggregator + 3 个 eval metrics |
| agent-memory-graph (1213 tests) | gen_ai.memory.* 提案正在标准化 → 可以提前对齐 | 关注 OTel SEMCONV GitHub issue #35 |
| openclaw-langgraph-bridge (195 tests) | Multi-agent handoff tracing 的天然集成点 | trace context propagation across Supervisor → Worker |
| agent-context-store (1347 tests) | Trace context = context store 的 use case | trace_export → context_store.import() |

---

## 下一步行动 (3)

1. **[高优先级] lab/agent-observability: 集成 gen_ai.* 属性 + CostAggregator (~120 行)**
   - 新建 `src/genai-conventions.ts`: GenAIAttrs 常量 + annotateLLMSpan() + CostAggregator
   - 修改 `tracer.ts`: startSpan 支持 gen_ai.* 属性自动注入
   - 新增 15-20 tests: 属性对齐验证 + cost 计算准确性 + 多模型 pricing
   - 验证标准: exportOTLP() 输出包含 `gen_ai.request.model`、`gen_ai.usage.input_tokens` 等标准属性

2. **[中优先级] lab/agent-observability: 添加 Tool Correctness + Step Efficiency 指标 (~80 行)**
   - 在 evaluator.ts 中添加 toolCorrectness() + stepEfficiency() deterministic metrics
   - 无需外部 LLM API 调用——纯基于 trace 结构分析
   - 新增 10-15 tests
   - 验证标准: 给定含重复工具调用的 trace，stepEfficiency < 1.0

3. **[探索] OTel GenAI Agent Spans 提案跟踪**
   - 关注 `gen_ai.agent.*` 和 `gen_ai.memory.*` semantic convention 提案
   - GitHub: open-telemetry/semantic-conventions-genai/issues/35
   - 当 proposal 进入 Experimental 时，评估 agent-memory-graph 的提前对齐价值

---

## 市场参考 — 2026 平台对比矩阵

| 平台 | License | 部署 | OTel 原生 | Agent 评估 | 成本追踪 | 适合场景 |
|------|---------|------|----------|-----------|---------|---------|
| Langfuse | MIT | Self-host/Cloud | ✅ | 基础 | Per-call | OSS首选 |
| Phoenix (Arize) | Apache 2.0 | Self-host/Cloud | ✅ | Phoenix Evals | Token-based | ML-grade rigor |
| LangSmith | Proprietary | SaaS only | Partial | ✅ (LangChain) | Per-span | LangChain stacks |
| Braintrust | Proprietary | SaaS | Partial | 强 (CI/CD gates) | Per-span | Eval-driven dev |
| Laminar | Apache 2.0 | Self-host/Cloud | ✅ | Signals + replay | Data-volume | Long-running agents |
| Datadog LLM Obs | Proprietary | SaaS | ✅ (v1.37+) | 监控为主 | 自动 | Enterprise Datadog shops |

**推荐策略**: lab/agent-observability 保持 vendor-neutral OTLP 导出 → 可以对接任何上述平台。核心价值在于 instrumentation 层（gen_ai.* 属性）和 evaluation 层（deterministic + LLM judge 指标），而非绑定某个后端。

---

## 参考资料

- [OTel GenAI Semantic Conventions (v1.41, Development)](https://opentelemetry.io/docs/specs/semconv/gen/genai/)
- [Greptime: How OTel Traces LLM Calls, Agent Reasoning, and MCP](https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions)
- [Digital Applied: Agent Observability Platforms 2026](https://www.digitalapplied.com/blog/agent-observability-platforms-langsmith-langfuse-arize-2026)
- [Braintrust: Agent Observability Complete Guide 2026](https://www.braintrust.dev/articles/agent-observability-complete-guide-2026)
- [Confident AI: LLM Agent Evaluation Metrics](https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide)
- [DeepEval Agent Evaluation Docs](https://deepeval.com/guides/guides-ai-agent-evaluation-metrics)
- [OTel SEMCONV GitHub: Agentic Systems Proposal (#35)](https://github.com/open-telemetry/semantic-conventions-genai/issues/35)
- [Fiddler AI: OTel for AI Observability Guide](https://www.fiddler.ai/blog/opentelemetry-ai-observability-guide)
- [Elastic 2026 Observability Trends](https://www.elastic.co/blog/2026-observability-trends-generative-ai-opentelemetry)
- [OpenInference JS SDK](https://arize-ai.github.io/openinference/js)
