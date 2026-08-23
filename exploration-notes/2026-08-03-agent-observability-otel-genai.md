# Agent Observability with OpenTelemetry GenAI Semantic Conventions

> Research #034 — Deep Dive into OTel GenAI SemConv for Agent Memory Systems
> Date: 2026-08-03 | Status: Development (semconv v1.41.0, pinned commit c739977)

---

## TL;DR

OpenTelemetry's GenAI Semantic Conventions have evolved from basic LLM call tracing (April 2024) into a six-layer observability stack covering model inference, agent orchestration, MCP tool calls, content capture, metrics, and provider-specific extensions. The conventions define **17 operation names**, **61 `gen_ai.*` attributes**, **8 span shapes**, **12 metric instruments**, and **3 event types** — all vendor-neutral, carried over OTLP. This research maps the spec to our agent-memory-graph (AMG) project and provides a runnable instrumentation prototype.

---

## Core Concepts (5)

### 1. The Six-Layer Architecture

The GenAI SemConv stack, bottom to top:

| Layer | What It Does | Maturity |
|-------|-------------|----------|
| **L1: Client Spans** | Standardizes LLM API calls (`gen_ai.operation.name = chat/embeddings/retrieval`) | ✅ Stable-ish, 22 libraries |
| **L2: Agent & Workflow Spans** | `create_agent`, `invoke_agent`, `invoke_workflow`, `execute_tool`, `plan` | ⚠️ Development, 2-6 libraries |
| **L3: MCP Conventions** | Trace continuity across MCP client↔server boundary | ⚠️ Development, new in v1.39 |
| **L4: Events & Content** | Privacy-gated prompt/completion capture + evaluation scores | ⚠️ Development, opt-in |
| **L5: Metrics** | `gen_ai.client.token.usage`, `gen_ai.client.operation.duration`, `gen_ai.invoke_agent.duration` | ✅ Core metrics stable |
| **L6: Provider-Specific** | OpenAI cache tokens, Anthropic billing, AWS Bedrock, Azure | Per-provider |

**Key insight:** L1 is well-covered by auto-instrumentation. Everything above it (L2-L4) requires manual instrumentation for most frameworks. This is exactly where our projects live.

### 2. The Agent Span Tree

The canonical trace shape for a single agent turn:

```
invoke_agent research-assistant (INTERNAL)
├── chat gpt-4o (CLIENT)         ← Model decides to search
├── execute_tool web_search (INTERNAL)  ← Search executed
├── chat gpt-4o (CLIENT)         ← Continues with results
├── memory search (INTERNAL)     ← Retrieves from memory store
└── chat gpt-4o (CLIENT)         ← Final answer
```

Critical structural rules:
- Tool spans are children of the **agent**, not the model call
- `invoke_agent` splits into CLIENT (remote) vs INTERNAL (in-process)
- A single `trace_id` links the entire chain

### 3. Memory Span Operations (`gen_ai.memory.*`)

The OpenLLMetry RFC (#3460) proposes 5 memory span types:

| Span | Operation | Key Attributes |
|------|-----------|---------------|
| `gen_ai.memory.store` | `"store"` | `memory.type` (short_term/long_term/episodic/semantic/procedural), `memory.store`, `items_stored`, `size_bytes`, `ttl_seconds` |
| `gen_ai.memory.retrieve` | `"retrieve"` | `memory.type`, `memory.store`, `items_retrieved`, `relevance_score`, `hit` (bool) |
| `gen_ai.memory.search` | `"search"` | `memory.type`, `search.query`, `search.top_k`, `search.min_score`, `search.filters` (JSON) |
| `gen_ai.memory.update` | `"update"` | `memory.type`, `memory.store`, `items_updated`, `keys[]` |
| `gen_ai.memory.delete` | `"delete"` | `memory.type`, `memory.store`, `items_deleted`, `keys[]` |

**The official OTel semconv repo also has:** `create_memory`, `create_memory_store`, `delete_memory`, `delete_memory_store`, `search_memory`, `update_memory`, `upsert_memory` as operation names — but these are still being aligned between the two proposals.

### 4. MCP Trace Continuity

Before v1.39, MCP broke traces: agent-side Trace A and server-side Trace B were disconnected. The fix uses W3C Trace Context propagation:

- **Client span** (`tools/call {tool_name}`, Kind=CLIENT): carries `mcp.method.name`, `mcp.session.id`, `mcp.protocol.version`
- **Server span** (`tools/call {tool_name}`, Kind=SERVER): nests under client span when context is propagated
- **Deduplication:** if outer GenAI instrumentation already tracks tool execution, MCP instrumentation enriches the existing span instead of creating a duplicate

Four MCP metrics: `mcp.client.operation.duration`, `mcp.server.operation.duration`, `mcp.client.session.duration`, `mcp.server.session.duration`.

### 5. Three-Mode Content Capture

| Mode | What Happens | When to Use |
|------|-------------|-------------|
| **Not recorded** (default) | Content absent | Production default |
| **Span attributes** | `gen_ai.input.messages` / `gen_ai.output.messages` on span | Debugging, low volume |
| **Event only** | Content on `gen_ai.client.inference.operation.details` event | Pattern-2 richness with pattern-3-like separation |
| **External storage + reference** | Content in S3/GreptimeDB, URL on span | Production with sensitive data |

Enable via: `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=span_only|event_only|span_and_event|no_content`

---

## Runnable Code: AMG Instrumented with GenAI SemConv

```python
"""
Agent Memory Graph — OpenTelemetry GenAI Instrumentation Prototype

Demonstrates how AMG operations map to gen_ai.memory.* spans.
Requires: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
"""

from __future__ import annotations
import json, time, uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

# --- OpenTelemetry imports ---
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.trace import Span, Tracer

# --- Setup ---
def setup_tracing(exporter="console"):
    """Initialize OTel tracing with GenAI SemConv."""
    provider = TracerProvider()
    if exporter == "console":
        provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )
    trace.set_tracer_provider(provider)
    return trace.get_tracer("agent-memory-graph", "1.0.0")


# --- AMG Instrumentation Wrapper ---

@dataclass
class MemoryRecord:
    """Simulated AMG memory node."""
    id: str
    content: str
    memory_type: str = "long_term"  # short_term, long_term, episodic, semantic, procedural
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class InstrumentedMemoryGraph:
    """
    Wraps AMG operations with gen_ai.memory.* semantic conventions.
    
    Each method creates a span with the correct operation name, attributes,
    and status — following the OpenLLMetry RFC and OTel GenAI SemConv.
    """

    def __init__(self, tracer: Tracer, store_backend: str = "agent_memory_graph"):
        self.tracer = tracer
        self.store = store_backend
        self._records: dict[str, MemoryRecord] = {}

    @contextmanager
    def _memory_span(
        self,
        operation: str,
        memory_type: str,
        name: Optional[str] = None,
        **extra_attrs,
    ):
        """Create a gen_ai.memory.* span with standard attributes."""
        span_name = name or f"gen_ai.memory.{operation}"
        attrs = {
            "gen_ai.operation.name": operation,
            "gen_ai.memory.type": memory_type,
            "gen_ai.memory.store": self.store,
        }
        attrs.update(extra_attrs)
        
        with self.tracer.start_as_current_span(span_name) as span:
            for k, v in attrs.items():
                if isinstance(v, (list, dict)):
                    span.set_attribute(k, json.dumps(v))
                else:
                    span.set_attribute(k, v)
            yield span

    def store_memory(
        self,
        content: str,
        memory_type: str = "long_term",
        session_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Store a memory record (gen_ai.memory.store span)."""
        record_id = f"mem_{uuid.uuid4().hex[:12]}"
        
        with self._memory_span(
            "store",
            memory_type,
            gen_ai_memory_session_id=session_id or "",
            gen_ai_memory_actor_id=actor_id or "",
        ) as span:
            record = MemoryRecord(
                id=record_id,
                content=content,
                memory_type=memory_type,
            )
            self._records[record_id] = record
            
            span.set_attribute("gen_ai.memory.items_stored", 1)
            span.set_attribute("gen_ai.memory.size_bytes", len(content.encode()))
            if ttl_seconds:
                span.set_attribute("gen_ai.memory.ttl_seconds", ttl_seconds)
            span.set_attribute("gen_ai.memory.keys", [record_id])
            
        return record_id

    def retrieve_memory(
        self,
        record_id: str,
        memory_type: str = "long_term",
        session_id: Optional[str] = None,
    ) -> Optional[MemoryRecord]:
        """Retrieve a specific memory by ID (gen_ai.memory.retrieve span)."""
        with self._memory_span(
            "retrieve",
            memory_type,
            gen_ai_memory_session_id=session_id or "",
        ) as span:
            record = self._records.get(record_id)
            
            span.set_attribute("gen_ai.memory.items_retrieved", 1 if record else 0)
            span.set_attribute("gen_ai.memory.hit", record is not None)
            span.set_attribute("gen_ai.memory.relevance_score", 1.0 if record else 0.0)
            
        return record

    def search_memory(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        memory_type: str = "semantic",
        filters: Optional[dict] = None,
    ) -> list[MemoryRecord]:
        """Semantic search over memories (gen_ai.memory.search span)."""
        with self._memory_span(
            "search",
            memory_type,
        ) as span:
            span.set_attribute("gen_ai.memory.search.query", query)
            span.set_attribute("gen_ai.memory.search.top_k", top_k)
            span.set_attribute("gen_ai.memory.search.min_score", min_score)
            if filters:
                span.set_attribute(
                    "gen_ai.memory.search.filters",
                    json.dumps(filters),
                )
            
            # Naive text matching (real AMG uses graph traversal + entropy)
            results = [
                r for r in self._records.values()
                if query.lower() in r.content.lower()
            ][:top_k]
            
            span.set_attribute("gen_ai.memory.items_retrieved", len(results))
            if results:
                span.set_attribute(
                    "gen_ai.memory.vector_dimensions",
                    len(results[0].embedding) if results[0].embedding else 0,
                )
            
        return results

    def update_memory(
        self,
        record_id: str,
        content: str,
        memory_type: str = "long_term",
    ) -> bool:
        """Update an existing memory record (gen_ai.memory.update span)."""
        with self._memory_span(
            "update",
            memory_type,
        ) as span:
            if record_id not in self._records:
                span.set_attribute("gen_ai.memory.items_updated", 0)
                return False
            
            old_size = len(self._records[record_id].content.encode())
            self._records[record_id].content = content
            new_size = len(content.encode())
            
            span.set_attribute("gen_ai.memory.items_updated", 1)
            span.set_attribute("gen_ai.memory.keys", [record_id])
            span.set_attribute("gen_ai.memory.size_bytes", new_size)
            
        return True

    def delete_memory(
        self,
        record_id: str,
        memory_type: str = "long_term",
    ) -> bool:
        """Delete a memory record (gen_ai.memory.delete span)."""
        with self._memory_span(
            "delete",
            memory_type,
        ) as span:
            existed = record_id in self._records
            if existed:
                del self._records[record_id]
            
            span.set_attribute("gen_ai.memory.items_deleted", 1 if existed else 0)
            span.set_attribute("gen_ai.memory.keys", [record_id] if existed else [])
            
        return existed


# --- Agent Instrumentation ---

def instrumented_agent_turn(
    tracer: Tracer,
    memory: InstrumentedMemoryGraph,
    user_input: str,
    agent_name: str = "catalyst",
) -> str:
    """
    Simulate a full agent turn with proper span tree structure.
    
    invoke_agent (INTERNAL)
    ├── chat {model} (CLIENT) — simulate LLM call
    ├── memory.store (INTERNAL) — store user input
    ├── memory.search (INTERNAL) — search for relevant context
    └── chat {model} (CLIENT) — simulate final response
    """
    with tracer.start_as_current_span(
        f"invoke_agent {agent_name}",
        kind=trace.SpanKind.INTERNAL,
    ) as agent_span:
        agent_span.set_attribute("gen_ai.operation.name", "invoke_agent")
        agent_span.set_attribute("gen_ai.agent.name", agent_name)
        agent_span.set_attribute("gen_ai.agent.type", "react")
        agent_span.set_attribute("gen_ai.agent.framework", "openclaw")

        # Step 1: Simulate LLM reasoning (CLIENT span)
        with tracer.start_as_current_span(
            "chat glm-4",
            kind=trace.SpanKind.CLIENT,
        ) as llm_span1:
            llm_span1.set_attribute("gen_ai.operation.name", "chat")
            llm_span1.set_attribute("gen_ai.provider.name", "zai")
            llm_span1.set_attribute("gen_ai.request.model", "glm-4")
            llm_span1.set_attribute("gen_ai.usage.input_tokens", len(user_input) // 4)
            llm_span1.set_attribute("gen_ai.response.finish_reasons", ["tool_calls"])
            time.sleep(0.01)  # simulate latency

        # Step 2: Store the user input in memory
        mem_id = memory.store_memory(
            content=user_input,
            memory_type="short_term",
            actor_id=agent_name,
        )

        # Step 3: Search for relevant context
        results = memory.search_memory(
            query=user_input,
            top_k=5,
            min_score=0.3,
            memory_type="semantic",
        )

        # Step 4: Final LLM response
        with tracer.start_as_current_span(
            "chat glm-4",
            kind=trace.SpanKind.CLIENT,
        ) as llm_span2:
            llm_span2.set_attribute("gen_ai.operation.name", "chat")
            llm_span2.set_attribute("gen_ai.provider.name", "zai")
            llm_span2.set_attribute("gen_ai.request.model", "glm-4")
            llm_span2.set_attribute("gen_ai.usage.input_tokens", len(user_input) // 4 + 50)
            llm_span2.set_attribute("gen_ai.usage.output_tokens", 42)
            llm_span2.set_attribute("gen_ai.response.finish_reasons", ["stop"])
            time.sleep(0.01)

        return f"Processed: {user_input[:50]}... (found {len(results)} related memories)"


# --- Main Demo ---

if __name__ == "__main__":
    tracer = setup_tracing(exporter="console")
    memory = InstrumentedMemoryGraph(tracer, store_backend="agent_memory_graph")

    # Populate memory
    memory.store_memory(
        "OpenTelemetry GenAI semantic conventions define gen_ai.* attributes",
        memory_type="semantic",
    )
    memory.store_memory(
        "Agent memory graphs need observability for debugging",
        memory_type="episodic",
    )

    # Run an instrumented agent turn
    result = instrumented_agent_turn(
        tracer,
        memory,
        "How does OTel work with agent memory systems?",
        agent_name="catalyst",
    )
    print(f"\nResult: {result}")

    # Demonstrate CRUD operations with spans
    new_id = memory.store_memory("Test observation", memory_type="short_term")
    memory.retrieve_memory(new_id)
    memory.update_memory(new_id, "Updated observation with more context")
    memory.delete_memory(new_id)

    print("\n✅ All spans emitted to console. Pipe to OTLP collector for Grafana/Jaeger.")
```

### Running the Code

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
python agent_observability_demo.py

# To export to a real backend (e.g., Jaeger):
# docker run -d -p 4317:4317 -p 16686:16686 jaegertracing/all-in-one
# Then replace ConsoleSpanExporter with OtlpExporter
```

**Expected output:** A tree of spans printed to console showing:
```
invoke_agent catalyst (INTERNAL)
├── chat glm-4 (CLIENT)
├── gen_ai.memory.store (INTERNAL)
├── gen_ai.memory.search (INTERNAL)
├── chat glm-4 (CLIENT)
gen_ai.memory.store (INTERNAL)
gen_ai.memory.retrieve (INTERNAL)
gen_ai.memory.update (INTERNAL)
gen_ai.memory.delete (INTERNAL)
```

---

## Key Insights (5)

### Insight 1: Memory Observability Is the Missing Layer

The OTel GenAI SemConv has solid coverage for LLM calls (22 libraries) and decent coverage for tool execution (13 libraries). But **memory operations have only 2 libraries** with reference coverage. This is the biggest gap in the spec, and it's exactly where AMG lives. By instrumenting AMG with `gen_ai.memory.*` spans, we're not just observability consumers — we're **defining what memory observability means** for the ecosystem.

### Insight 2: The `invoke_agent` CLIENT/INTERNAL Split Matters Enormously

OpenClaw agents run in-process (INTERNAL), not as remote services (CLIENT). The spec explicitly says: don't put `provider.name` or `server.address` on INTERNAL agent spans — those attributes belong to the model call, not the agent. This distinction prevents attribute pollution and makes agent traces cleaner. For our edge-agent-runtime, all `invoke_agent` spans should be INTERNAL with `gen_ai.agent.framework = "openclaw"`.

### Insight 3: Sampling Attributes Must Be Set at Span Creation

The most common GenAI instrumentation bug: creating a span, calling the model, then setting `gen_ai.request.model` afterward. But samplers only see attributes that exist when the sampling decision is made. The 5 attributes that MUST be set at creation: `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `server.address`, `server.port`. For memory spans: `gen_ai.operation.name`, `gen_ai.memory.type`, `gen_ai.memory.store`.

### Insight 4: Metrics and Spans Serve Different Questions

The two agent histogram metrics — `gen_ai.invoke_agent.inference_calls` and `gen_ai.invoke_agent.tool_calls` — answer the question "how many model/tool calls does one agent turn take?" rather than "how many happened this minute?" This per-invocation distribution reveals:
- **Long tail on inference_calls** = loop that doesn't terminate cleanly
- **Bimodal tool_calls** = two distinct user intents served by one agent

These are invisible in simple counters. AMG's `classify_agent_pattern` could feed these distributions.

### Insight 5: The Spec Is Moving Fast — Pin and Map

v1.37 to v1.41 each changed GenAI conventions:
- v1.37: Chat history overhaul, `gen_ai.system` → `gen_ai.provider.name`
- v1.38: Evaluation events, tool definitions, `invoke_agent` guidance
- v1.39: MCP semantic conventions
- v1.40: Retrieval spans, cache token attributes
- v1.41: `execute_tool` naming requires tool name, reasoning tokens, streaming metrics

**Survival strategy:** (1) Pin instrumentation version + convention commit, (2) Put a mapping layer between raw attribute keys and dashboards, (3) Never invent custom `gen_ai.*` keys (use your own namespace), (4) Dual-emit across renames briefly.

---

## Connection to Existing Projects

| Project | Application |
|---------|------------|
| **agent-memory-graph (AMG)** | Instrument `remember()`, `recall()`, `classify()` with `gen_ai.memory.*` spans. AMG becomes the first graph-memory system with native OTel observability. The `trace_derivation()` API maps perfectly to a chain of `gen_ai.memory.retrieve` spans showing provenance. |
| **edge-agent-runtime** | Each sensor reading → `execute_tool` span, each coordinator decision → `invoke_agent` span. The 3-tier architecture (sensors/actuators/coordinators) produces clean hierarchical traces. |
| **agent-task-cli** | Each task execution maps to `gen_ai.task.execute` spans with `task.id`, `task.name`, `task.status`. |
| **context-forge** | Context compression maps to `gen_ai.context.compress` spans with `tokens_before`, `tokens_after`, `compression_ratio`. |
| **lab/agent-observability** | This research directly informs the lab project. The prototype code above can be the starting point. |

---

## Competitive Landscape (Tools)

| Tool | Type | OTel Native | Memory Spans | Best For |
|------|------|-------------|-------------|----------|
| **Arize Phoenix** | Open source | ✅ Built on OTel | ❌ | OTel-compatible tracing + eval |
| **Langfuse** | Open source + Cloud | ✅ Via OTLP | ❌ | Self-hosting, comprehensive tracing |
| **Braintrust** | Commercial | ⚠️ Custom format | ❌ | Purpose-built AI trace DB (Brainstore) |
| **OpenLLMetry (Traceloop)** | Open source | ✅ Native | ✅ RFC proposed | Auto-instrumentation (OpenAI, Anthropic) |
| **Datadog LLM Obs** | Commercial | ✅ v1.37+ native | ❌ | Infrastructure correlation |
| **MLflow** | Open source | ✅ GenAI SemConv export | ❌ | Experiment tracking + tracing |

**Gap:** None of these tools have native graph-memory observability. AMG + OTel = unique positioning.

---

## Next Actions

1. **Implement OTel instrumentation in AMG** — Create a `telemetry/` module with `MemorySpan` wrapper (≈50 lines). Wrap the 5 core operations (store/retrieve/search/update/delete). Start with ConsoleSpanExporter, add OTLP exporter config.

2. **Write a compliance matrix** — Document which `gen_ai.*` attributes each AMG operation emits, following the format in `reference/README.md` of the semconv repo. This becomes part of the README for npm publish.

3. **Create a reference trace visualization** — Run the prototype code with Jaeger backend, capture the trace waterfall screenshot. Use it in the README and in the "Agent Memory Protocol Convergence" essay.

4. **Prototype `gen_ai.invoke_agent.duration` + `gen_ai.invoke_agent.tool_calls` metrics** — These two histograms answer agent reliability questions that no current AMG metric covers. ~20 lines of code using OTel Instruments API.

5. **Evaluate alignment with OpenLLMetry RFC** — The 20-span RFC is comprehensive but not yet official. Determine which spans we adopt vs. defer. Priority: lifecycle (4) + memory (5) + tools (3) = 12 spans for MVP.

---

## References

- **OTel GenAI SemConv repo:** https://github.com/open-telemetry/semantic-conventions-genai (pinned: commit c739977, 2026-07-30)
- **Greptime deep dive:** https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions
- **Implementation guide:** https://hidekazu-konishi.com/entry/opentelemetry_genai_semantic_conventions_guide.html
- **OpenLLMetry RFC (#3460):** https://github.com/traceloop/openllmetry/issues/3460
- **Agentic Systems proposal (#35):** https://github.com/open-telemetry/semantic-conventions-genai/issues/35
- **OTel Blog — AI Agent Observability:** https://opentelemetry.io/blog/2025/ai-agent-observability
- **Expanso Best Practices 2026:** https://expanso.io/blog/ai-agent-observability-best-practices
- **Zylos Research:** https://zylos.ai/research/2026-02-28-opentelemetry-ai-agent-observability
- **Uptrace Guide:** https://uptrace.dev/blog/opentelemetry-ai-systems
- **Chanl Production Guide:** https://www.chanl.ai/blog/ai-agent-observability-opentelemetry-production

---

*Research #034 | Generated by Catalyst deep-exploration-evening cron | 2026-08-03 20:00 CST*
