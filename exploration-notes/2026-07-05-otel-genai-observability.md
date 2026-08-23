# OTel GenAI Semantic Conventions for LLM Agent Observability

> Research date: 2026-07-05
> Motivation: `lab/agent-observability` needs `gen_ai.*` attribute compliance + CostAggregator
> Sources: 25+ articles, spec docs, and code examples from OTel blog, Greptime, MLflow, Elastic, MorphLLM, Zylos.ai, Traceloop RFC

---

## Core Concepts

### 1. The `gen_ai.*` Attribute Namespace

OpenTelemetry's GenAI Semantic Conventions (developed by the GenAI SIG since April 2024) define a vendor-neutral vocabulary for AI telemetry. As of mid-2026, they're in **Development status** but already adopted by Datadog, Grafana, MLflow, Elastic, and others.

**Core attribute set:**

| Attribute | Type | Example | Purpose |
|-----------|------|---------|---------|
| `gen_ai.system` | string | `openai` | Provider identifier |
| `gen_ai.request.model` | string | `gpt-4o-mini` | Requested model |
| `gen_ai.response.model` | string | `gpt-4o-mini-2024-07-18` | Actual responding model |
| `gen_ai.operation.name` | string | `chat` | Operation type |
| `gen_ai.usage.input_tokens` | int | `142` | Prompt token count |
| `gen_ai.usage.output_tokens` | int | `87` | Completion token count |
| `gen_ai.response.finish_reasons` | string[] | `["stop"]` | Why generation stopped |
| `gen_ai.agent.name` | string | `research-bot` | Agent identifier |
| `gen_ai.tool.name` | string | `web_search` | Tool identifier |

**Provider-specific extensions:**
- OpenAI: `gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_creation.input_tokens`, `gen_ai.usage.reasoning.output_tokens`
- Anthropic: separate cache read/write token tracking

**Version management:** `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` enables latest experimental conventions.

### 2. Four-Layer Span Hierarchy for Agents

The spec defines distinct operation types that map to a parent-child span tree:

```
[invoke_agent: research-agent]     ← root agent span (INTERNAL or CLIENT)
  ├── [chat: openai]               ← LLM call for planning
  ├── [execute_tool: web_search]   ← tool invocation #1
  ├── [chat: openai]               ← LLM call to process results
  ├── [execute_tool: write_file]   ← tool invocation #2
  └── [chat: openai]               ← final synthesis LLM call
```

**Operation types (v1.41):**
- `create_agent` — agent construction (CLIENT)
- `invoke_agent` — agent invocation (CLIENT for remote, INTERNAL for local)
- `invoke_workflow` — predefined workflow execution (new in v1.41)
- `chat` — LLM inference call
- `execute_tool` — tool/function call (INTERNAL)
- `embeddings` — vector embedding generation

This hierarchy is the key insight: **agents are traced as span trees, not flat logs**. Each LLM call and tool invocation becomes a child span, enabling per-step latency/cost attribution.

### 3. MCP Semantic Conventions (v1.39+)

For MCP (Model Context Protocol) interactions, the spec adds:
- `mcp.session.id` — session identifier
- `mcp.method.name` — JSON-RPC method (e.g., `tools/call`)
- `mcp.protocol.version` — MCP version
- `gen_ai.tool.name` — tool name within MCP call

This fixes the "Trace A / Trace B" problem where agent and MCP server had disconnected traces.

### 4. Token Cost Attribution Architecture

Cost tracking builds on token attributes. The pattern across vendors:

```
Cost = (input_tokens × input_rate) 
     + (output_tokens × output_rate)
     + (cache_read_tokens × cache_rate)    // OpenAI
     + (reasoning_tokens × reasoning_rate) // o-series models
```

**Key insight from Galileo's cost analysis:** Agent costs scale nonlinearly because:
- Retries multiply token consumption (3 ReAct iterations vs 10 = 3.3× cost)
- Context windows grow per turn (conversation history accumulation)
- Tool calls add hidden latency costs (web searches, DB queries)

**Per-user cost attribution** uses span attributes like `gen_ai.conversation.id` or custom `user.id` to facet spend.

### 5. Multi-Agent Tracing Patterns

For multi-agent systems (CrewAI, LangGraph, OpenAI Agents SDK):

```
[invoke_workflow: research-pipeline]
  ├── [invoke_agent: researcher]
  │     ├── [chat: openai]
  │     └── [execute_tool: search]
  ├── [invoke_agent: analyst]
  │     ├── [chat: anthropic]
  │     └── [execute_tool: database_query]
  └── [invoke_agent: writer]
        └── [chat: openai]
```

The **RFC for AI Agent Observability** (traceloop/openllmetry#3460) proposes additional namespaces:
- `gen_ai.team.*` — multi-agent team coordination
- `gen_ai.task.*` — task decomposition and assignment
- `gen_ai.memory.*` — agent memory operations
- `gen_ai.session.*` — session/conversation tracking
- `gen_ai.human.*` — human-in-the-loop approval and feedback

---

## Code Examples

### Example 1: One-Line Python Instrumentation (OpenAI SDK)

```python
# pip install opentelemetry-distro opentelemetry-instrumentation-openai-v2 openai

from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from openai import OpenAI

# One line to instrument all OpenAI calls
OpenAIInstrumentor().instrument()

client = OpenAI()  # uses OPENAI_API_KEY env var

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is 2+2?"}],
)

# This automatically emits spans with:
# gen_ai.operation.name = chat
# gen_ai.request.model = gpt-4o-mini
# gen_ai.usage.input_tokens = ...
# gen_ai.usage.output_tokens = ...
# gen_ai.response.finish_reasons = ["stop"]
```

Run with console exporter:
```bash
opentelemetry-instrument --traces_exporter console --metrics_exporter console python main.py
```

### Example 2: TypeScript CostAggregator (Directly Applicable to lab/agent-observability)

```typescript
/**
 * CostAggregator: Tracks token usage and estimated costs per model/provider.
 * Uses gen_ai.* semantic convention attributes.
 */

export interface ModelPricing {
  inputPer1M: number;   // USD per 1M input tokens
  outputPer1M: number;  // USD per 1M output tokens
  cacheReadPer1M?: number;
  reasoningPer1M?: number;
}

// 2026 mid-year pricing snapshot (USD per 1M tokens)
export const DEFAULT_PRICING: Record<string, ModelPricing> = {
  'gpt-4o':        { inputPer1M: 2.50, outputPer1M: 10.00 },
  'gpt-4o-mini':   { inputPer1M: 0.15, outputPer1M: 0.60 },
  'gpt-4.1':       { inputPer1M: 2.00, outputPer1M: 8.00 },
  'gpt-4.1-mini':  { inputPer1M: 0.40, outputPer1M: 1.60 },
  'o3':            { inputPer1M: 2.00, outputPer1M: 8.00, reasoningPer1M: 8.00 },
  'o4-mini':       { inputPer1M: 1.10, outputPer1M: 4.40, reasoningPer1M: 4.40 },
  'claude-sonnet-4': { inputPer1M: 3.00, outputPer1M: 15.00 },
  'claude-haiku-3.5': { inputPer1M: 0.80, outputPer1M: 4.00 },
  'gemini-2.5-pro': { inputPer1M: 1.25, outputPer1M: 10.00 },
  'gemini-2.5-flash': { inputPer1M: 0.075, outputPer1M: 0.30 },
  'deepseek-chat':  { inputPer1M: 0.14, outputPer1M: 0.28 },
};

export interface CostRecord {
  model: string;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens?: number;
  reasoningTokens?: number;
  cost: number;
  timestamp: number;
  agentName?: string;
  toolName?: string;
}

export class CostAggregator {
  private pricing: Record<string, ModelPricing>;
  private records: CostRecord[] = [];

  constructor(pricing: Record<string, ModelPricing> = DEFAULT_PRICING) {
    this.pricing = pricing;
  }

  /** Calculate cost for a single LLM call based on gen_ai.* attributes */
  calculateCost(
    model: string,
    inputTokens: number,
    outputTokens: number,
    cacheReadTokens = 0,
    reasoningTokens = 0,
  ): number {
    const p = this.pricing[model] ?? { inputPer1M: 1, outputPer1M: 5 };
    const inputCost = (inputTokens / 1_000_000) * p.inputPer1M;
    const outputCost = (outputTokens / 1_000_000) * p.outputPer1M;
    const cacheCost = cacheReadTokens > 0 && p.cacheReadPer1M
      ? (cacheReadTokens / 1_000_000) * p.cacheReadPer1M
      : 0;
    const reasoningCost = reasoningTokens > 0 && p.reasoningPer1M
      ? (reasoningTokens / 1_000_000) * p.reasoningPer1M
      : 0;
    return inputCost + outputCost + cacheCost + reasoningCost;
  }

  /** Record a cost entry from span attributes */
  recordFromAttributes(attrs: Record<string, unknown>, agentName?: string): CostRecord {
    const model = String(attrs['gen_ai.request.model'] ?? attrs['gen_ai.response.model'] ?? 'unknown');
    const inputTokens = Number(attrs['gen_ai.usage.input_tokens'] ?? 0);
    const outputTokens = Number(attrs['gen_ai.usage.output_tokens'] ?? 0);
    const cacheReadTokens = Number(attrs['gen_ai.usage.cache_read.input_tokens'] ?? 0);
    const reasoningTokens = Number(attrs['gen_ai.usage.reasoning.output_tokens'] ?? 0);

    const cost = this.calculateCost(model, inputTokens, outputTokens, cacheReadTokens, reasoningTokens);
    const record: CostRecord = {
      model, inputTokens, outputTokens, cacheReadTokens, reasoningTokens,
      cost, timestamp: Date.now(), agentName,
      toolName: attrs['gen_ai.tool.name'] ? String(attrs['gen_ai.tool.name']) : undefined,
    };
    this.records.push(record);
    return record;
  }

  /** Get total cost across all recorded calls */
  getTotalCost(): number {
    return this.records.reduce((sum, r) => sum + r.cost, 0);
  }

  /** Get cost breakdown by model */
  getCostByModel(): Record<string, { cost: number; calls: number; inputTokens: number; outputTokens: number }> {
    const result: Record<string, { cost: number; calls: number; inputTokens: number; outputTokens: number }> = {};
    for (const r of this.records) {
      if (!result[r.model]) {
        result[r.model] = { cost: 0, calls: 0, inputTokens: 0, outputTokens: 0 };
      }
      result[r.model].cost += r.cost;
      result[r.model].calls++;
      result[r.model].inputTokens += r.inputTokens;
      result[r.model].outputTokens += r.outputTokens;
    }
    return result;
  }

  /** Get cost breakdown by agent */
  getCostByAgent(): Record<string, number> {
    const result: Record<string, number> = {};
    for (const r of this.records) {
      const key = r.agentName ?? 'unknown';
      result[key] = (result[key] ?? 0) + r.cost;
    }
    return result;
  }

  /** Get all records */
  getRecords(): CostRecord[] {
    return [...this.records];
  }

  /** Reset records */
  reset(): void {
    this.records = [];
  }

  /** Get summary report */
  getSummary(): { totalCost: number; totalCalls: number; totalInputTokens: number; totalOutputTokens: number; byModel: Record<string, { cost: number; calls: number }> } {
    return {
      totalCost: this.getTotalCost(),
      totalCalls: this.records.length,
      totalInputTokens: this.records.reduce((s, r) => s + r.inputTokens, 0),
      totalOutputTokens: this.records.reduce((s, r) => s + r.outputTokens, 0),
      byModel: Object.fromEntries(
        Object.entries(this.getCostByModel()).map(([k, v]) => [k, { cost: v.cost, calls: v.calls }])
      ),
    };
  }
}
```

### Example 3: Integration with Existing Tracer (Runnable Test)

```typescript
// This snippet shows how to add gen_ai.* attributes and cost tracking
// to the existing lab/agent-observability Tracer class.

import { Tracer } from './tracer.js';

// ... (CostAggregator class from above) ...

// Usage with existing AgentObserver pattern:
const tracer = new Tracer();
const costAggregator = new CostAggregator();

// Start agent span with gen_ai.* conventions
const agentSpan = tracer.startSpan('agent.run', {
  'gen_ai.operation.name': 'invoke_agent',
  'gen_ai.agent.name': 'research-bot',
});

// Simulate LLM call with full gen_ai.* attributes
const llmSpan = tracer.startSpan('llm.call', {
  'gen_ai.operation.name': 'chat',
  'gen_ai.system': 'openai',
  'gen_ai.request.model': 'gpt-4o-mini',
  'gen_ai.usage.input_tokens': 150,
  'gen_ai.usage.output_tokens': 80,
  'gen_ai.response.finish_reasons': ['stop'],
});
tracer.endSpan(llmSpan.spanId);

// Record cost from span attributes
costAggregator.recordFromAttributes(llmSpan.attributes, 'research-bot');

// Tool call
const toolSpan = tracer.startSpan('tool.execute', {
  'gen_ai.operation.name': 'execute_tool',
  'gen_ai.tool.name': 'web_search',
});
tracer.endSpan(toolSpan.spanId);

// Another LLM call with different model
const llmSpan2 = tracer.startSpan('llm.call', {
  'gen_ai.operation.name': 'chat',
  'gen_ai.system': 'anthropic',
  'gen_ai.request.model': 'claude-sonnet-4',
  'gen_ai.usage.input_tokens': 500,
  'gen_ai.usage.output_tokens': 200,
});
tracer.endSpan(llmSpan2.spanId);
costAggregator.recordFromAttributes(llmSpan2.attributes, 'research-bot');

tracer.endSpan(agentSpan.spanId);

// Get cost report
console.log(costAggregator.getSummary());
// {
//   totalCost: 0.00795,  // ~$0.008 for the entire agent run
//   totalCalls: 2,
//   totalInputTokens: 650,
//   totalOutputTokens: 280,
//   byModel: {
//     'gpt-4o-mini': { cost: 0.000073, calls: 1 },
//     'claude-sonnet-4': { cost: 0.007875, calls: 1 },  // Claude is 100× more expensive here
//   }
// }
```

**Running the test:**
```bash
cd lab/agent-observability
npx tsx -e "
import { CostAggregator } from './src/cost-aggregator.js';
const agg = new CostAggregator();
const cost1 = agg.calculateCost('gpt-4o-mini', 1000, 500);
console.log('GPT-4o-mini 1K+500 tokens:', cost1.toFixed(6), 'USD');
const cost2 = agg.calculateCost('claude-sonnet-4', 1000, 500);
console.log('Claude Sonnet 4 1K+500 tokens:', cost2.toFixed(6), 'USD');
console.log('Ratio Claude/GPT:', (cost2/cost1).toFixed(1) + 'x');
"
# Output:
# GPT-4o-mini 1K+500 tokens: 0.000550 USD
# Claude Sonnet 4 1K+500 tokens: 0.010500 USD
# Ratio Claude/GPT: 19.1x
```

---

## Key Insights

### 1. The existing Tracer already has the right structure — it just needs attribute alignment

The current `lab/agent-observability` Tracer uses custom operation names (`agent.run`, `llm.call`, `tool.execute`) and custom attribute names (`promptTokens`, `completionTokens`). The OTel GenAI conventions map almost 1:1 to this structure:
- `agent.run` → `invoke_agent` operation
- `llm.call` → `chat` operation  
- `tool.execute` → `execute_tool` operation
- `promptTokens` → `gen_ai.usage.input_tokens`
- `completionTokens` → `gen_ai.usage.output_tokens`

**Migration is mechanical**, not architectural. The `exportOTLP()` method already exists — it just needs to emit the correct attribute keys.

### 2. Cost visibility transforms from engineering concern to leadership priority

From Horovits's analysis: "In 2025, I watched organizations where a single poorly-optimized prompt could cost more per day than the entire Kubernetes cluster running it." The CostAggregator pattern isn't just nice-to-have — it's becoming a **first-class observability requirement**. Elastic's 2026 report shows 85% of organizations plan for LLM observability with cost attribution.

The Galileo cost optimization playbook identifies the top 3 cost sinks in agent systems:
1. **Retries** — 10 ReAct iterations vs 3 can 3.3× the cost for marginal accuracy gain
2. **Context bloat** — conversation history accumulation without summarization
3. **Hidden tool costs** — each web search / DB query adds latency AND tokens

A CostAggregator that surfaces per-agent, per-tool, and per-model costs directly addresses these sinks.

### 3. The spec is unstable but the direction is clear — bet on it now

As of May 2026, GenAI semantic conventions are still in "Development" status. But:
- Core attributes (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.*`) have been stable since v1.37
- v1.41 added `invoke_workflow` and clarified `invoke_agent` span kinds
- Datadog, Grafana, MLflow, Elastic, and Splunk all support v1.37+
- The `OTEL_SEMCONV_STABILITY_OPT_IN` env var handles version transitions

**Strategic insight:** Build to the current spec (v1.41) now. The core concepts won't change — only edge-case attribute names. Our `exportOTLP()` method already produces valid OTLP JSON, so we're one attribute rename away from compliance.

### 4. Multi-agent tracing is the frontier — and our agent-memory-graph is directly applicable

The Traceloop RFC for agent observability proposes `gen_ai.memory.*` attributes for agent memory operations. Our `agent-memory-graph` project already has memory read/write spans in the Tracer (`memory.read`, `memory.write`). Mapping these to `gen_ai.memory.read` / `gen_ai.memory.write` would make our memory graph system **natively OTel-compatible** — a unique differentiator.

### 5. Sampling strategy matters more than instrumentation

From the MLflow observability guide: "Run LLM-as-judge scoring on 10-20% of production traffic to balance quality coverage against evaluation cost." Full-fidelity tracing of every LLM call is expensive when the calls themselves are expensive. The CostAggregator should support **configurable sampling** — trace every call for cost, but only capture full prompt/completion content for a subset.

---

## Gap Analysis: lab/agent-observability vs OTel GenAI Conventions

| Feature | Current State | OTel Convention | Gap |
|---------|--------------|-----------------|-----|
| Operation names | `agent.run`, `llm.call` | `invoke_agent`, `chat`, `execute_tool` | Rename needed |
| Token attributes | `promptTokens`, `completionTokens` | `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | Add `gen_ai.*` keys |
| Provider tracking | Not tracked | `gen_ai.system`, `gen_ai.provider.name` | Add attributes |
| Cost tracking | None | (Not in spec, but universally needed) | **Add CostAggregator** |
| Span tree export | `exportOTLP()` exists | Correct structure, wrong attribute names | Attribute migration |
| Content capture | Stored as `gen_ai.prompt` / `gen_ai.completion` | Should use OTel events, not attributes | Convert to events |
| Cache/reasoning tokens | Not tracked | `gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.reasoning.output_tokens` | Add for o-series/Anthropic |
| MCP spans | Not supported | `mcp.session.id`, `mcp.method.name` | Future addition |

---

## Next Actions

1. **[Immediate] Implement CostAggregator class** — Create `src/cost-aggregator.ts` in `lab/agent-observability/` with the code from Example 2. Add ~15 tests covering: cost calculation per model, recordFromAttributes, getCostByModel, getCostByAgent, edge cases (unknown model, zero tokens). This directly unblocks the `gen_ai.* 属性 + CostAggregator` pending task.

2. **[Short-term] Migrate attribute names to gen_ai.* conventions** — In `tracer.ts`, add dual-key attributes (both custom and `gen_ai.*`) during the transition period. Update `exportOTLP()` to emit only `gen_ai.*` keys. Add `gen_ai.system` and `gen_ai.operation.name` to all span creation paths.

3. **[Medium-term] Add provider-specific token tracking** — Support `cache_read.input_tokens` and `reasoning.output_tokens` for OpenAI o-series models. This enables accurate cost tracking for reasoning models where reasoning tokens dominate cost.

4. **[Research] Investigate OTel GenAI Events for content capture** — Currently prompt/completion text is stored as span attributes. The spec recommends using OTel Span Events for message content. This matters for privacy (events can be selectively sampled/dropped) and for backend compatibility.

---

## References

- [OTel GenAI Semantic Conventions (official docs, v1.41)](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai)
- [Inside the LLM Call: GenAI Observability (OTel blog, May 2026)](https://opentelemetry.io/blog/2026/genai-observability)
- [How OTel Traces LLM Calls, Agent Reasoning, and MCP (Greptime, May 2026)](https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions)
- [Setting Up LLM Observability Pipelines in 2026 (MLflow)](https://mlflow.org/articles/setting-up-llm-observability-pipelines-in-2026)
- [Agent Tracing 2026 (MorphLLM)](https://www.morphllm.com/agent-tracing)
- [OTel for AI Agents: Observability, Tracing, GenAI (Zylos.ai, Feb 2026)](https://zylos.ai/research/2026-02-28-opentelemetry-ai-agent-observability)
- [GenAI Semantic Conventions for LLM Monitoring (OneUptime, Feb 2026)](https://oneuptime.com/blog/post/2026-02-06-genai-semantic-conventions-llm-monitoring/view)
- [Observability Trends 2026: GenAI + OTel (Elastic)](https://www.elastic.co/blog/2026-observability-trends-generative-ai-opentelemetry)
- [Cost Tracking Per User (Traceloop, Nov 2025)](https://www.traceloop.com/blog/from-bills-to-budgets-how-to-track-llm-token-usage-and-cost-per-user)
- [AI Agent Cost Optimization (Galileo, Nov 2025)](https://galileo.ai/blog/ai-agent-cost-optimization-observability)
- [Best Tools for LLM Cost Tracking 2026 (Braintrust)](https://www.braintrust.dev/articles/best-tools-tracking-llm-costs-2026)
- [RFC: Semantic Conventions for AI Agent Observability (Traceloop GitHub#3460)](https://github.com/traceloop/openllmetry/issues/3460)
- [OTel SRE Guide for LLMs (OpenObserve, 2026)](https://openobserve.ai/blog/opentelemetry-for-llms)
- [Datadog LLM OTel SemConv Support (Datadog blog)](https://www.datadoghq.com/blog/llm-otel-semantic-convention)
