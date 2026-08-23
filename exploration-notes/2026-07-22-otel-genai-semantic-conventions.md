# OpenTelemetry GenAI Semantic Conventions — Deep Research

**Date:** 2026-07-22
**Researcher:** Catalyst (autoresearch cron)
**Topic:** OTel GenAI semantic conventions for agent observability
**Relevance:** lab/agent-observability project (166 tests, gen_ai.* attributes + CostAggregator pending)

---

## Core Concepts (5)

### 1. GenAI Span Hierarchy (not just "traces")

The conventions define a **layered span model** specific to AI operations:

- **Inference span** (`gen_ai.inference.client`) — wraps a single LLM API call (chat, generate_content, text_completion)
- **Agent spans** — `create_agent`, `invoke_agent` (client + internal variants), `invoke_workflow`, `plan`
- **Tool span** (`gen_ai.execute_tool`) — wrapping tool/function execution
- **Memory spans** — `create_memory`, `search_memory`, `update_memory`, `upsert_memory`, `delete_memory`, `create_memory_store`, `delete_memory_store`
- **Retrieval span** — for RAG/vector search operations
- **Embeddings span** — for embedding generation

**Key insight:** Memory and retrieval are first-class span types, not afterthoughts. The conventions explicitly recognize memory stores as a distinct GenAI operation category.

### 2. Token Accounting (the real cost model)

Token attributes are granular:

| Attribute | Purpose |
|-----------|---------|
| `gen_ai.usage.input_tokens` | Total input tokens (inclusive of cache) |
| `gen_ai.usage.output_tokens` | Total output tokens (inclusive of reasoning) |
| `gen_ai.usage.cache_read.input_tokens` | Tokens served from provider cache (subset of input) |
| `gen_ai.usage.cache_creation.input_tokens` | Tokens written to cache (subset of input) |
| `gen_ai.usage.reasoning.output_tokens` | Chain-of-thought/thinking tokens (subset of output) |

**Critical rule:** Cached and reasoning tokens are **subsets**, not additional. `input_tokens` includes `cache_read` + `cache_creation` + fresh tokens. This enables accurate cost calculation: you can charge cached tokens at the discounted rate.

### 3. Histogram Metrics with Explicit Bucket Boundaries

The conventions specify exact histogram bucket boundaries:

- **Token usage:** `[1, 4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864]` — powers of 4, covering 1 token to 67M tokens
- **Operation duration:** `[0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92]` — doubling from 10ms to ~82s

These aren't suggestions — they're **SHOULD** requirements for histogram instruments.

### 4. Agent-Specific Spans (beyond simple LLM calls)

The `invoke_agent` span type covers:
- `gen_ai.agent.id` — stable provider identifier (ARN, etc.)
- `gen_ai.agent.name` — human-readable name
- `gen_ai.agent.description` — free-form description
- `gen_ai.agent.version` — version string
- `gen_ai.conversation.id` — session/thread correlation
- `gen_ai.data_source.id` — data source identifier

And the **Plan span** (`gen_ai.operation.name = "plan"`) explicitly captures agent planning/task decomposition phases.

### 5. Streaming Observability

New attributes for streaming responses:
- `gen_ai.request.stream` (boolean) — whether streaming mode was used
- `gen_ai.response.time_to_first_chunk` (double, seconds) — TTFT metric
- Metrics: `gen_ai.client.operation.time_to_first_chunk` and `gen_ai.client.operation.time_per_output_chunk`

---

## Code Example: OTel-Compliant GenAI Span Creator

This is a **runnable** Node.js/TypeScript module that bridges the existing `agent-observability` Tracer to the OTel GenAI semantic conventions. It demonstrates proper attribute naming, token accounting, and metric recording.

```typescript
// genai-otel-bridge.ts — Runnable example
// npx tsx genai-otel-bridge.ts

import { randomUUID } from 'node:crypto';
import { performance } from 'node:perf_hooks';

// ─── Types from OTel GenAI Semantic Conventions ───

type GenAiOperationName =
  | 'chat' | 'generate_content' | 'text_completion'
  | 'create_agent' | 'invoke_agent' | 'invoke_workflow'
  | 'execute_tool' | 'plan'
  | 'create_memory' | 'search_memory' | 'update_memory'
  | 'upsert_memory' | 'delete_memory' | 'create_memory_store'
  | 'delete_memory_store'
  | 'embeddings' | 'retrieval';

type GenAiTokenType = 'input' | 'output';

type GenAiProviderName =
  | 'openai' | 'anthropic' | 'aws.bedrock' | 'azure.ai.openai'
  | 'azure.ai.inference' | 'cohere' | 'deepseek' | 'gcp.gemini'
  | 'gcp.gen_ai' | 'gcp.vertex_ai' | 'groq' | 'ibm.watsonx.ai'
  | 'mistral_ai' | 'moonshot_ai' | 'perplexity' | 'x_ai';

// ─── Token Usage Record ───

interface TokenUsage {
  inputTokens: number;           // total input (inclusive of cache)
  outputTokens: number;          // total output (inclusive of reasoning)
  cacheReadInputTokens?: number;  // subset of input
  cacheCreationInputTokens?: number; // subset of input
  reasoningOutputTokens?: number; // subset of output
}

// ─── Cost Aggregator ───

interface PricingTier {
  inputPer1M: number;
  outputPer1M: number;
  cachedInputPer1M?: number;    // usually discounted
  reasoningPer1M?: number;
}

const PRICING: Record<string, PricingTier> = {
  'gpt-4': { inputPer1M: 30, outputPer1M: 60, cachedInputPer1M: 15 },
  'claude-3.5-sonnet': { inputPer1M: 3, outputPer1M: 15, cachedInputPer1M: 0.3 },
  'glm-4': { inputPer1M: 0.5, outputPer1M: 0.5 },
};

class CostAggregator {
  private entries: Array<{ model: string; usage: TokenUsage; cost: number; timestamp: number }> = [];

  record(model: string, usage: TokenUsage): number {
    const pricing = PRICING[model] ?? { inputPer1M: 1, outputPer1M: 1 };
    const freshInput = usage.inputTokens
      - (usage.cacheReadInputTokens ?? 0)
      - (usage.cacheCreationInputTokens ?? 0);
    const cacheRead = usage.cacheReadInputTokens ?? 0;
    const cacheCreate = usage.cacheCreationInputTokens ?? 0;
    const reasoning = usage.reasoningOutputTokens ?? 0;
    const regularOutput = usage.outputTokens - reasoning;

    const cost =
      (freshInput / 1e6) * pricing.inputPer1M +
      (cacheRead / 1e6) * (pricing.cachedInputPer1M ?? pricing.inputPer1M) +
      (cacheCreate / 1e6) * (pricing.cachedInputPer1M ?? pricing.inputPer1M) +
      (regularOutput / 1e6) * pricing.outputPer1M +
      (reasoning / 1e6) * (pricing.reasoningPer1M ?? pricing.outputPer1M);

    this.entries.push({ model, usage, cost, timestamp: Date.now() });
    return cost;
  }

  totalCost(): number {
    return this.entries.reduce((sum, e) => sum + e.cost, 0);
  }

  costByModel(): Record<string, number> {
    const byModel: Record<string, number> = {};
    for (const e of this.entries) {
      byModel[e.model] = (byModel[e.model] ?? 0) + e.cost;
    }
    return byModel;
  }

  totalTokens(): { input: number; output: number; cached: number; reasoning: number } {
    return this.entries.reduce((acc, e) => ({
      input: acc.input + e.usage.inputTokens,
      output: acc.output + e.usage.outputTokens,
      cached: acc.cached + (e.usage.cacheReadInputTokens ?? 0),
      reasoning: acc.reasoning + (e.usage.reasoningOutputTokens ?? 0),
    }), { input: 0, output: 0, cached: 0, reasoning: 0 });
  }

  summary(): string {
    const cost = this.totalCost();
    const tokens = this.totalTokens();
    const byModel = this.costByModel();
    const lines = [
      '═══ CostAggregator Summary ═══',
      `Total Cost: $${cost.toFixed(4)}`,
      `Input Tokens:  ${tokens.input.toLocaleString()} (cached: ${tokens.cached.toLocaleString()})`,
      `Output Tokens: ${tokens.output.toLocaleString()} (reasoning: ${tokens.reasoning.toLocaleString()})`,
      '',
      'By Model:',
    ];
    for (const [model, mcost] of Object.entries(byModel)) {
      lines.push(`  ${model}: $${mcost.toFixed(4)}`);
    }
    return lines.join('\n');
  }
}

// ─── GenAI Span Builder (OTel-compliant attributes) ───

class GenAiSpanBuilder {
  readonly spanId: string;
  readonly traceId: string;
  readonly parentSpanId: string | null;
  readonly operationName: GenAiOperationName;
  readonly providerName: GenAiProviderName;
  readonly startTime: number;
  private endTime: number | null = null;
  private attrs: Record<string, unknown> = {};
  private events: Array<{ name: string; timestamp: number; attributes?: Record<string, unknown> }> = [];

  constructor(
    traceId: string,
    operationName: GenAiOperationName,
    providerName: GenAiProviderName,
    parentSpanId: string | null = null,
  ) {
    this.spanId = randomUUID();
    this.traceId = traceId;
    this.operationName = operationName;
    this.providerName = providerName;
    this.parentSpanId = parentSpanId;
    this.startTime = performance.now();

    // Required attributes per OTel GenAI spec
    this.attrs['gen_ai.operation.name'] = operationName;
    this.attrs['gen_ai.provider.name'] = providerName;
  }

  setModel(model: string): this {
    this.attrs['gen_ai.request.model'] = model;
    return this;
  }

  setResponseModel(model: string): this {
    this.attrs['gen_ai.response.model'] = model;
    return this;
  }

  setConversationId(id: string): this {
    this.attrs['gen_ai.conversation.id'] = id;
    return this;
  }

  setTokenUsage(usage: TokenUsage): this {
    this.attrs['gen_ai.usage.input_tokens'] = usage.inputTokens;
    this.attrs['gen_ai.usage.output_tokens'] = usage.outputTokens;
    if (usage.cacheReadInputTokens !== undefined) {
      this.attrs['gen_ai.usage.cache_read.input_tokens'] = usage.cacheReadInputTokens;
    }
    if (usage.cacheCreationInputTokens !== undefined) {
      this.attrs['gen_ai.usage.cache_creation.input_tokens'] = usage.cacheCreationInputTokens;
    }
    if (usage.reasoningOutputTokens !== undefined) {
      this.attrs['gen_ai.usage.reasoning.output_tokens'] = usage.reasoningOutputTokens;
    }
    return this;
  }

  setStreaming(ttftSeconds?: number): this {
    this.attrs['gen_ai.request.stream'] = true;
    if (ttftSeconds !== undefined) {
      this.attrs['gen_ai.response.time_to_first_chunk'] = ttftSeconds;
    }
    return this;
  }

  setTemperature(temp: number): this {
    this.attrs['gen_ai.request.temperature'] = temp;
    return this;
  }

  setMaxTokens(max: number): this {
    this.attrs['gen_ai.request.max_tokens'] = max;
    return this;
  }

  setReasoningLevel(level: 'low' | 'medium' | 'high'): this {
    this.attrs['gen_ai.request.reasoning.level'] = level;
    return this;
  }

  setAgentInfo(info: { id?: string; name?: string; description?: string; version?: string }): this {
    if (info.id) this.attrs['gen_ai.agent.id'] = info.id;
    if (info.name) this.attrs['gen_ai.agent.name'] = info.name;
    if (info.description) this.attrs['gen_ai.agent.description'] = info.description;
    if (info.version) this.attrs['gen_ai.agent.version'] = info.version;
    return this;
  }

  setFinishReasons(reasons: string[]): this {
    this.attrs['gen_ai.response.finish_reasons'] = reasons;
    return this;
  }

  setError(errorType: string): this {
    this.attrs['error.type'] = errorType;
    return this;
  }

  addEvent(name: string, attributes?: Record<string, unknown>): this {
    this.events.push({ name, timestamp: Date.now(), attributes });
    return this;
  }

  end(): this {
    this.endTime = performance.now();
    return this;
  }

  get durationMs(): number {
    return this.endTime !== null ? this.endTime - this.startTime : 0;
  }

  get attributes(): Record<string, unknown> {
    return { ...this.attrs };
  }

  /** Export to OTLP-compatible JSON */
  toOTLP() {
    return {
      traceId: this.traceId,
      spanId: this.spanId,
      parentSpanId: this.parentSpanId ?? undefined,
      name: `${this.operationName} ${this.attrs['gen_ai.request.model'] ?? ''}`.trim(),
      kind: 1, // INTERNAL
      startTimeUnixNano: Math.round(this.startTime * 1e6),
      endTimeUnixNano: this.endTime !== null ? Math.round(this.endTime * 1e6) : undefined,
      status: { code: this.attrs['error.type'] ? 2 : 1 },
      attributes: Object.entries(this.attrs).map(([k, v]) => {
        const type = typeof v;
        if (type === 'number') return { key: k, value: { intValue: v } };
        if (type === 'boolean') return { key: k, value: { boolValue: v } };
        return { key: k, value: { stringValue: String(v) } };
      }),
      events: this.events.map(e => ({
        timeUnixNano: e.timestamp * 1e6,
        name: e.name,
        attributes: Object.entries(e.attributes ?? {}).map(([k, v]) => ({
          key: k,
          value: { stringValue: String(v) },
        })),
      })),
    };
  }
}

// ─── Demo: Full Agent Invocation with Cost Tracking ───

async function demo() {
  console.log('🧪 OTel GenAI Semantic Conventions Demo\n');

  const traceId = randomUUID();
  const costAgg = new CostAggregator();

  // Simulate an agent invocation with an LLM call + tool execution

  // 1. Agent invocation span
  const agentSpan = new GenAiSpanBuilder(traceId, 'invoke_agent', 'openai')
    .setAgentInfo({
      id: 'asst_catalyst_001',
      name: 'Catalyst',
      description: 'Research assistant',
      version: '2.0.0',
    })
    .setConversationId('conv_abc123')
    .setModel('gpt-4');

  // 2. Nested LLM inference span
  const llmSpan = new GenAiSpanBuilder(traceId, 'chat', 'openai', agentSpan.spanId)
    .setModel('gpt-4')
    .setResponseModel('gpt-4-0613')
    .setTemperature(0.7)
    .setMaxTokens(1000)
    .setStreaming(0.45) // TTFT = 450ms
    .setReasoningLevel('medium');

  // Simulate token usage with cache + reasoning
  const usage: TokenUsage = {
    inputTokens: 1500,           // total input
    outputTokens: 800,           // total output
    cacheReadInputTokens: 500,   // 500 of the 1500 input tokens were cached
    cacheCreationInputTokens: 200, // 200 written to cache
    reasoningOutputTokens: 150,  // 150 of 800 output tokens were reasoning
  };
  llmSpan.setTokenUsage(usage).setFinishReasons(['stop']).end();

  // Record cost
  const cost = costAgg.record('gpt-4', usage);
  console.log(`LLM call cost: $${cost.toFixed(6)}`);

  // 3. Tool execution span
  const toolSpan = new GenAiSpanBuilder(traceId, 'execute_tool', 'openai', agentSpan.spanId);
  toolSpan.addEvent('tool.invocation', { tool_name: 'web_search', query: 'OTel GenAI conventions' });
  toolSpan.end();

  // 4. Memory operation span (search memory)
  const memSpan = new GenAiSpanBuilder(traceId, 'search_memory', 'openai', agentSpan.spanId)
    .setConversationId('conv_abc123');
  memSpan.end();

  // Close agent span
  agentSpan.end();

  // ─── Output ───

  console.log('\n📋 Span Summary:');
  for (const span of [agentSpan, llmSpan, toolSpan, memSpan]) {
    const attrs = span.attributes;
    console.log(`  ${span.operationName.padEnd(20)} | ${span.durationMs.toFixed(1).padStart(8)}ms | model=${attrs['gen_ai.request.model'] ?? 'N/A'}`);
  }

  console.log('\n' + costAgg.summary());

  // OTLP export
  console.log('\n📤 OTLP Export (first span):');
  console.log(JSON.stringify(agentSpan.toOTLP(), null, 2));

  // Histogram bucket boundaries (per spec)
  console.log('\n📊 Token Usage Histogram Boundaries (per OTel spec):');
  console.log([1, 4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864].join(' → '));

  console.log('\n📊 Duration Histogram Boundaries (seconds):');
  console.log([0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92].join(' → '));
}

demo().catch(console.error);
```

**Run it:** `npx tsx genai-otel-bridge.ts`

---

## Key Insights (5)

### 1. Memory Operations Are First-Class Citizens in OTel GenAI

The spec defines 7 memory operation types: `create_memory`, `search_memory`, `update_memory`, `upsert_memory`, `delete_memory`, `create_memory_store`, `delete_memory_store`. This directly validates the `amg-mcp` project's tool design (recall, remember, health, forget, query, consolidate). The next amg-mcp tools (gaps/skills) should map to `search_memory` and `retrieval` operations respectively.

### 2. The Current Tracer Uses Wrong Operation Names

The existing `agent-observability` Tracer uses `agent.run`, `llm.call`, `tool.execute` — these should be mapped to the standard:
- `agent.run` → `invoke_agent` (with `gen_ai.agent.id`, `gen_ai.agent.name`)
- `llm.call` → `chat` or `generate_content` (with `gen_ai.request.model`, `gen_ai.usage.*`)
- `tool.execute` → `execute_tool`
- `memory.read/write` → `search_memory` / `upsert_memory`
- `retrieval.search` → `retrieval`

**This is a breaking change but a necessary alignment.** The mapping layer should be added as a compatibility shim.

### 3. CostAggregator Needs Subset Token Awareness

The biggest cost tracking mistake is double-counting: if you add `input_tokens + cache_read_tokens`, you overcount. The spec is explicit: cache tokens are subsets of `input_tokens`. The CostAggregator in the code example above handles this correctly by subtracting cached tokens from fresh tokens before applying pricing.

### 4. Reasoning Token Tracking Is New and Important

`gen_ai.usage.reasoning.output_tokens` captures chain-of-thought/extended thinking tokens (e.g., OpenAI o1/o3, Claude with extended thinking, Gemini Thinking). These are a subset of `output_tokens` but may be priced differently. The spec uses `gen_ai.request.reasoning.level` (low/medium/high) on the request side — this maps to OpenAI's reasoning_effort parameter.

### 5. Provider Ecosystem Has Expanded Significantly

The well-known provider list now includes: `openai`, `anthropic`, `aws.bedrock`, `azure.ai.openai`, `azure.ai.inference`, `cohere`, `deepseek`, `gcp.gemini`, `gcp.gen_ai`, `gcp.vertex_ai`, `groq`, `ibm.watsonx.ai`, `mistral_ai`, `moonshot_ai`, `perplexity`, `x_ai`. This covers essentially all major AI providers including Chinese ones (DeepSeek, Moonshot AI). The `gen_ai.provider.name` acts as a discriminator for telemetry format flavors.

---

## Next Actions (3)

1. **Implement `gen_ai.*` attribute mapping in lab/agent-observability**
   - Add a `GenAiSpanAdapter` that wraps the existing `Tracer` and emits OTel-compliant attribute names
   - Map: `agent.run` → `invoke_agent`, `llm.call` → `chat`, `tool.execute` → `execute_tool`, `memory.*` → `*_memory`
   - Target: +30 tests (mapping correctness + OTLP export format)
   - This is the foundational step for the pending `gen_ai.* 属性` task

2. **Build CostAggregator with subset-aware token pricing**
   - Use the TokenUsage interface from the code example
   - Support per-model pricing tiers (input, output, cached, reasoning rates)
   - Add `gen_ai.client.token.usage` histogram metric with the spec's bucket boundaries
   - Target: +25 tests (cost calculations, edge cases, multi-model aggregation)

3. **Align amg-mcp memory tools with OTel memory operation names**
   - `amg-mcp`'s `recall` tool → emit `search_memory` span
   - `amg-mcp`'s `remember` tool → emit `upsert_memory` span
   - `amg-mcp`'s `consolidate` tool → emit `update_memory` span
   - `amg-mcp`'s `forget` tool → emit `delete_memory` span
   - `amg-mcp`'s `query` tool → emit `retrieval` span
   - This gives amg-mcp standardized observability for free

---

## Quality Checklist

- [x] Core concepts: 5 (span hierarchy, token accounting, histogram buckets, agent spans, streaming)
- [x] Code example: 1 complete runnable TypeScript module (~250 lines) with CostAggregator + GenAiSpanBuilder + demo
- [x] Key insights: 5 (memory ops, operation name mapping, subset tokens, reasoning tokens, provider list)
- [x] Next actions: 3 concrete steps with test targets
- [x] Project relevance: Directly maps to lab/agent-observability (166 tests) + amg-mcp (43 tests)
- [x] Unique perspective: Subset token cost calculation pattern, memory operation standardization insight

---

## Sources

- **OTel GenAI Semantic Conventions (new repo):** https://github.com/open-telemetry/semantic-conventions-genai
- **GenAI Spans:** https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-spans.md
- **GenAI Metrics:** https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-metrics.md
- **GenAI Agent Spans:** https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-agent-spans.md
- **GenAI Events:** https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-events.md
- **Existing project:** lab/agent-observability/src/tracer.ts (166 tests, custom Tracer class)
