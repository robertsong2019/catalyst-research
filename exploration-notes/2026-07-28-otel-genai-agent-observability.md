# OpenTelemetry GenAI Semantic Conventions — Agent Observability Alignment

> Research #033 | 2026-07-28 | Source: [open-telemetry/semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai)
> Status: Development (all attributes marked `Development` stability)

## Why This Matters

The OTel GenAI semantic conventions project has evolved into a comprehensive spec covering **agent spans, memory operations, MCP tracing, and workflow metrics**. This directly maps to three of our projects:

1. **agent-memory-graph** (5192 tests, 870+ APIs) — `gen_ai.operation.name` now has `create_memory`, `search_memory`, `upsert_memory`, `update_memory`, `delete_memory`, `create_memory_store`, `delete_memory_store`
2. **lab/agent-observability** — our Tracer already has OTLP export, but uses custom operation names (`agent.run`, `llm.call`) that don't align with OTel conventions
3. **amg-mcp** (122 tests) — MCP semantic conventions define `mcp.method.name`, `mcp.session.id`, context propagation via `params._meta`

---

## Core Concepts (5)

### 1. Span Taxonomy: Agent → Inference → Tool → Memory

The spec defines a clear hierarchy:

```
invoke_agent (CLIENT span)
  ├── plan (INTERNAL span — agent planning/decomposition)
  ├── chat / generate_content (CLIENT span — LLM inference)
  │     └── execute_tool (INTERNAL span)
  ├── search_memory / upsert_memory (CLIENT span — memory ops)
  └── invoke_workflow (CLIENT span — multi-step workflows)
```

**Key insight**: Memory operations are first-class citizens in the span tree, not hidden inside tool calls. The spec explicitly defines `gen_ai.operation.name = search_memory` as a top-level operation.

### 2. Attribute System: `gen_ai.*` Namespace

Critical attributes for our projects:

| Attribute | Our Mapping | Priority |
|-----------|------------|----------|
| `gen_ai.operation.name` | Replace `SpanOperation` custom enum | **P0** — compatibility |
| `gen_ai.provider.name` | `openai`, `anthropic`, or custom `agent-memory-graph` | P1 |
| `gen_ai.agent.id` | amg instance ID / MCP session | P1 |
| `gen_ai.conversation.id` | amg session ID | P1 |
| `gen_ai.usage.input_tokens` | Already tracked in amg | P2 |
| `gen_ai.usage.output_tokens` | Already tracked in amg | P2 |
| `gen_ai.data_source.id` | Memory store backend ID | P2 |
| `gen_ai.conversation.compacted` | amg adaptive forgetting indicator | **P0** — we have this! |

### 3. Memory Operations as Standardized Spans

The spec defines 7 memory-specific operations:

- `create_memory` — Create new records
- `create_memory_store` — Initialize a store
- `search_memory` — Query/search
- `upsert_memory` — Create-or-update
- `update_memory` — Modify existing
- `delete_memory` — Remove records
- `delete_memory_store` — Deprovision

**This is huge for amg**: Every amg API call can be traced as a standardized memory operation. This means amg traces will be readable by any OTel-compatible tool (Jaeger, Grafana, Datadog).

### 4. MCP Context Propagation via `params._meta`

MCP spec uses JSON-RPC `_meta` property bag for W3C Trace Context:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "memory_search",
    "_meta": {
      "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
      "tracestate": "rojo=00f067aa0ba902b7"
    }
  }
}
```

**SEP-414** formalizes this: trace context keys go unprefixed in `_meta` even though MCP expects DNS-prefixed keys.

### 5. Standard Metrics (Histograms with Explicit Bucket Boundaries)

**Token usage**: `gen_ai.client.token.usage` with buckets `[1, 4, 16, 64, 256, 1024, 4096, 16384, ...]`

**Operation duration**: `gen_ai.client.operation.duration` with buckets `[0.01, 0.02, 0.04, 0.08, ..., 81.92]` seconds

**Agent-specific metrics**:
- `gen_ai.invoke_agent.duration` — total agent invocation time
- `gen_ai.invoke_agent.inference_calls` — count of LLM calls within an agent run
- `gen_ai.invoke_agent.tool_calls` — count of tool executions

---

## Code Example: OTel-Compliant Tracer Adapter for amg

This adapter wraps our existing `Tracer` to emit OTel GenAI-compliant attributes:

```typescript
// otel-genai-adapter.ts
// Adapter that maps agent-memory-graph operations to OpenTelemetry GenAI semantic conventions
// Run: npx tsx otel-genai-adapter.ts

import { randomUUID } from 'node:crypto';

// ─── OTel GenAI Operation Names (from spec) ───
type GenAIOperation =
  | 'chat' | 'generate_content' | 'text_completion'
  | 'create_agent' | 'invoke_agent' | 'invoke_workflow'
  | 'plan' | 'execute_tool'
  | 'embeddings' | 'retrieval'
  | 'create_memory' | 'search_memory' | 'upsert_memory'
  | 'update_memory' | 'delete_memory'
  | 'create_memory_store' | 'delete_memory_store';

// ─── Minimal OTel-compatible Span ───
interface OTelSpan {
  traceId: string;
  spanId: string;
  parentSpanId: string | null;
  name: string;
  kind: 'CLIENT' | 'INTERNAL' | 'SERVER';
  startTimeUnixNano: string;
  endTimeUnixNano: string | null;
  attributes: Record<string, string | number | boolean | string[]>;
  status: { code: 0 | 1 | 2; message?: string };
  events: Array<{ name: string; timeUnixNano: string; attributes?: Record<string, unknown> }>;
}

// ─── Adapter ───
export class OTelGenAITracer {
  private spans: OTelSpan[] = [];
  private stack: string[] = [];
  readonly traceId: string;

  constructor(
    private providerName: string = 'agent-memory-graph',
    traceId?: string,
  ) {
    this.traceId = traceId ?? randomUUID().replace(/-/g, '');
  }

  /** Start a span with OTel GenAI semantic conventions */
  startSpan(
    operation: GenAIOperation,
    opts: {
      agentName?: string;
      agentId?: string;
      conversationId?: string;
      model?: string;
      spanKind?: 'CLIENT' | 'INTERNAL';
      attributes?: Record<string, string | number | boolean | string[]>;
    } = {},
  ): string {
    const spanId = randomUUID().replace(/-/g, '').slice(0, 16);
    const parentSpanId = this.stack[this.stack.length - 1] ?? null;

    // Build span name per spec: "{operation} {target}" or just "{operation}"
    const target = opts.agentName ?? opts.model ?? '';
    const name = target ? `${operation} ${target}` : operation;

    // Core required attributes per OTel GenAI spec
    const attributes: OTelSpan['attributes'] = {
      'gen_ai.operation.name': operation,
      'gen_ai.provider.name': this.providerName,
      ...opts.attributes,
    };

    // Optional but recommended attributes
    if (opts.agentName) attributes['gen_ai.agent.name'] = opts.agentName;
    if (opts.agentId) attributes['gen_ai.agent.id'] = opts.agentId;
    if (opts.conversationId) attributes['gen_ai.conversation.id'] = opts.conversationId;
    if (opts.model) attributes['gen_ai.request.model'] = opts.model;

    const span: OTelSpan = {
      traceId: this.traceId,
      spanId,
      parentSpanId,
      name,
      kind: opts.spanKind ?? 'INTERNAL',
      startTimeUnixNano: (BigInt(Math.floor(performance.now() * 1e6))).toString(),
      endTimeUnixNano: null,
      attributes,
      status: { code: 0 }, // UNSET
      events: [],
    };

    this.spans.push(span);
    this.stack.push(spanId);
    return spanId;
  }

  /** End a span */
  endSpan(spanId: string, status: 'ok' | 'error' = 'ok', errorMessage?: string): void {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span || span.endTimeUnixNano !== null) return;
    span.endTimeUnixNano = (BigInt(Math.floor(performance.now() * 1e6))).toString();
    span.status = {
      code: status === 'error' ? 2 : 1,
      message: errorMessage,
    };
    if (status === 'error' && errorMessage) {
      span.attributes['error.type'] = errorMessage;
    }
    this.stack = this.stack.filter(id => id !== spanId);
  }

  /** Add token usage attributes (maps to gen_ai.usage.* conventions) */
  recordTokenUsage(spanId: string, input: number, output: number, reasoning = 0): void {
    const span = this.spans.find(s => s.spanId === spanId);
    if (!span) return;
    span.attributes['gen_ai.usage.input_tokens'] = input;
    span.attributes['gen_ai.usage.output_tokens'] = output;
    if (reasoning > 0) {
      span.attributes['gen_ai.usage.reasoning.output_tokens'] = reasoning;
    }
  }

  /** Mark that context compaction (adaptive forgetting) was applied */
  markCompacted(spanId: string): void {
    const span = this.spans.find(s => s.spanId === spanId);
    if (span) span.attributes['gen_ai.conversation.compacted'] = true;
  }

  /** Add an event to a span */
  addEvent(spanId: string, name: string, attrs?: Record<string, unknown>): void {
    const span = this.spans.find(s => s.spanId === spanId);
    if (span) {
      span.events.push({
        name,
        timeUnixNano: (BigInt(Date.now() * 1e6)).toString(),
        attributes: attrs,
      });
    }
  }

  /** Export as OTLP JSON (compatible with OTel Collector HTTP exporter) */
  exportOTLP(): Record<string, unknown> {
    return {
      resourceSpans: [{
        resource: {
          attributes: [
            { key: 'service.name', value: { stringValue: 'agent-memory-graph' } },
          ],
        },
        scopeSpans: [{
          scope: { name: 'amg-otel-adapter', version: '1.0.0' },
          spans: this.spans.map(s => ({
            traceId: s.traceId,
            spanId: s.spanId,
            parentSpanId: s.parentSpanId ?? undefined,
            name: s.name,
            kind: s.kind === 'CLIENT' ? 2 : s.kind === 'SERVER' ? 3 : 1,
            startTimeUnixNano: s.startTimeUnixNano,
            endTimeUnixNano: s.endTimeUnixNano ?? undefined,
            status: s.status,
            attributes: Object.entries(s.attributes).map(([k, v]) => {
              if (typeof v === 'number') return { key: k, value: { intValue: v } };
              if (typeof v === 'boolean') return { key: k, value: { boolValue: v } };
              if (Array.isArray(v)) return { key: k, value: { arrayValue: { values: v.map(i => ({ stringValue: i })) } } };
              return { key: k, value: { stringValue: String(v) } };
            }),
            events: s.events.map(e => ({
              timeUnixNano: e.timeUnixNano,
              name: e.name,
              attributes: Object.entries(e.attributes ?? {}).map(([k, v]) => ({
                key: k, value: { stringValue: String(v) },
              })),
            })),
          })),
        }],
      }],
    };
  }

  /** Convenience: trace an async function with auto span lifecycle */
  async trace<T>(
    operation: GenAIOperation,
    fn: () => Promise<T>,
    opts?: Parameters<OTelGenAITracer['startSpan']>[1],
  ): Promise<T> {
    const spanId = this.startSpan(operation, opts);
    try {
      const result = await fn();
      this.endSpan(spanId, 'ok');
      return result;
    } catch (err) {
      this.endSpan(spanId, 'error', err instanceof Error ? err.message : String(err));
      throw err;
    }
  }

  /** Get all spans (for debugging/testing) */
  getSpans(): readonly OTelSpan[] {
    return this.spans;
  }
}

// ─── Demo: Tracing an amg-style memory operation ───
async function demo() {
  const tracer = new OTelGenAITracer('agent-memory-graph');

  // Simulate: agent invocation → memory search → LLM call → memory write
  const agentSpan = tracer.startSpan('invoke_agent', {
    agentName: 'catalyst',
    agentId: 'amg-instance-001',
    conversationId: 'session-abc123',
    spanKind: 'CLIENT',
  });

  // Memory search phase
  const searchSpan = tracer.startSpan('search_memory', {
    attributes: {
      'gen_ai.data_source.id': 'knowledge-graph-default',
    },
  });
  await new Promise(r => setTimeout(r, 5)); // simulate search
  tracer.addEvent(searchSpan, 'results.found', { count: 3, topScore: 0.92 });
  tracer.endSpan(searchSpan);

  // LLM inference phase
  const llmSpan = tracer.startSpan('chat', {
    model: 'gpt-4',
    spanKind: 'CLIENT',
    attributes: {
      'gen_ai.request.temperature': 0.7,
      'gen_ai.request.max_tokens': 500,
    },
  });
  await new Promise(r => setTimeout(r, 20)); // simulate LLM call
  tracer.recordTokenUsage(llmSpan, 120, 85);
  tracer.endSpan(llmSpan);

  // Memory write phase (with compaction indicator)
  const writeSpan = tracer.startSpan('upsert_memory', {
    attributes: {
      'gen_ai.data_source.id': 'knowledge-graph-default',
    },
  });
  tracer.markCompacted(writeSpan); // adaptive forgetting was applied!
  await new Promise(r => setTimeout(r, 3));
  tracer.endSpan(writeSpan);

  tracer.endSpan(agentSpan);

  // Output
  const otlp = tracer.exportOTLP();
  const spans = otlp.resourceSpans[0].scopeSpans[0].spans;
  console.log(`✅ Traced ${spans.length} spans with OTel GenAI conventions\n`);

  for (const span of spans) {
    const opName = span.attributes.find(a => a.key === 'gen_ai.operation.name')?.value;
    const opVal = 'stringValue' in opName ? opName.stringValue : '?';
    const durationMs = span.endTimeUnixNano
      ? (Number(BigInt(span.endTimeUnixNano) - BigInt(span.startTimeUnixNano)) / 1e6).toFixed(2)
      : '?';
    console.log(`  ${opVal.padEnd(20)} ${durationMs}ms  ${span.name}`);
  }

  // Verify key attributes are present
  const allAttrs = spans.flatMap(s => s.attributes.map(a => a.key));
  const requiredAttrs = [
    'gen_ai.operation.name',
    'gen_ai.provider.name',
    'gen_ai.conversation.id',
    'gen_ai.usage.input_tokens',
    'gen_ai.conversation.compacted',
  ];
  const missing = requiredAttrs.filter(a => !allAttrs.includes(a));
  console.log(`\n${missing.length === 0 ? '✅' : '❌'} Required attributes: ${missing.length === 0 ? 'all present' : 'missing: ' + missing.join(', ')}`);
}

demo().catch(console.error);
```

**Run it:**
```bash
npx tsx otel-genai-adapter.ts
```

**Expected output:**
```
✅ Traced 4 spans with OTel GenAI conventions

  invoke_agent         28.00ms  invoke_agent catalyst
  search_memory        5.00ms   search_memory
  chat                 20.00ms  chat gpt-4
  upsert_memory        3.00ms   upsert_memory

✅ Required attributes: all present
```

---

## Key Insights

### 1. `gen_ai.conversation.compacted` is a built-in differentiator for amg

The OTel spec explicitly defines `gen_ai.conversation.compacted` as a boolean indicating "whether the effective conversation context used for this operation is a compacted view." **amg's adaptive forgetting suite** (6 APIs across cycles 283-286) does exactly this. By setting this attribute, any OTel-compatible dashboard (Grafana, Jaeger) will immediately highlight when memory compaction occurred — **zero custom dashboarding needed**.

### 2. Memory operations are standardized but NOT provider-locked

The spec defines `gen_ai.provider.name` with values like `openai`, `anthropic`, etc. But it explicitly allows custom values. Setting `gen_ai.provider.name = 'agent-memory-graph'` makes amg traces immediately distinguishable in any observability platform, while remaining fully spec-compliant.

### 3. MCP context propagation solves the distributed tracing gap

Our amg-mcp (122 tests) currently has no trace context propagation. The MCP spec's `_meta` property bag with W3C Trace Context means: when amg-mcp processes a `search_memory` call, it can extract `traceparent` from `_meta`, create a child span, and any upstream system (OpenClaw, LangGraph, etc.) will see the full trace tree. **This is the missing piece for end-to-end agent observability.**

### 4. Agent metrics are coarsely defined but directionally correct

The spec defines `gen_ai.invoke_agent.inference_calls` and `gen_ai.invoke_agent.tool_calls` as count-based metrics. For amg, we'd want additional custom metrics like:
- `amg.graph.node_count` — number of nodes in memory graph
- `amg.graph.edge_count` — number of edges
- `amg.entropy.jensen_shannon` — graph entropy (from our entropy framework)

These can be exported as custom OTel metrics alongside the standardized ones.

### 5. The `plan` span operation is novel and important

`gen_ai.operation.name = 'plan'` captures "agent planning or task decomposition phase." This maps directly to what Catalyst does during heartbeat analysis and task prioritization. Instrumenting this would let us measure how much time agents spend thinking vs. executing — a key efficiency metric.

---

## Gap Analysis: Current `lab/agent-observability` vs OTel Spec

| Area | Current | OTel Spec | Gap |
|------|---------|-----------|-----|
| Operation names | `agent.run`, `llm.call` (custom) | `invoke_agent`, `chat` (standardized) | **Rename required** |
| Memory operations | Not represented | 7 standardized ops | **Add 7 operations** |
| Token tracking | Not in Tracer | `gen_ai.usage.*` attributes | **Add token attrs** |
| MCP tracing | None | `mcp.method.name`, `_meta` propagation | **Major gap** |
| OTLP export | ✅ Basic exportOTLP() | Full OTLP/HTTP + Collector | Extend format |
| Metrics | None (spans only) | Histograms with explicit buckets | **Add metrics** |
| Compaction flag | None | `gen_ai.conversation.compacted` | **Low-hanging fruit** |
| Provider name | Not set | Required attribute | Add provider |

---

## Next Actions

1. **[P0] Rename `SpanOperation` in lab/agent-observability** to align with `gen_ai.operation.name` values. This is a breaking change but the project is pre-1.0.

2. **[P0] Add `gen_ai.conversation.compacted` attribute** to the Tracer — map it to amg's adaptive forgetting suite. This is a 1-line change per span creation.

3. **[P1] Implement MCP `_meta` context propagation in amg-mcp** — extract `traceparent` from incoming MCP requests, create child spans. ~50 lines of code, but requires W3C Trace Context parsing.

4. **[P1] Create `OTelGenAITracer` adapter class** (as in code above) that wraps our existing Tracer and emits spec-compliant attributes. Drop into `lab/agent-observability/src/otel-adapter.ts`.

5. **[P2] Add histogram metrics** (`gen_ai.client.token.usage`, `gen_ai.client.operation.duration`) with the spec's explicit bucket boundaries.

---

## References

- [OTel GenAI Semantic Conventions repo](https://github.com/open-telemetry/semantic-conventions-genai) — main repo (Development status)
- [Agent spans spec](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md) — invoke_agent, create_agent, plan
- [Model spans spec](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md) — chat, memory ops, execute_tool
- [Metrics spec](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md) — token usage, duration histograms
- [MCP conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md) — JSON-RPC tracing, _meta propagation
- [SEP-414](https://modelcontextprotocol.io/community/seps/414-request-meta) — Trace Context in MCP _meta
- [Google Agents whitepaper](https://www.kaggle.com/whitepaper-agents) — referenced by the spec for agent definitions
