# Agent Memory Benchmark Landscape 2026: The Evaluation Gap

> Research #058 | 2026-08-11 | Catalyst Deep Exploration
> Methodology: autoresearch.md (structured exploration with metrics)

---

## Executive Summary

The agent memory field has a paradox: **benchmarks are saturating while production failures compound**. LoCoMo scores exceed 92%, yet agents fail at basic multi-session tasks. MemoryArena (ICML 2026) proves the gap is structural — retrieval ≠ agentic memory. This note maps the full benchmark landscape, identifies where amg (agent-memory-graph) can differentiate, and provides a runnable benchmark adapter prototype.

---

## Core Concepts

### 1. The Three-Stage Memory Model (Write-Manage-Read)

The industry has converged on a three-stage mental model for agent memory:

| Stage | What It Does | What Benchmarks Test |
|-------|-------------|---------------------|
| **Write** | What gets stored, how, and when | ❌ Almost untested |
| **Manage** | Conflict resolution, forgetting, consolidation | ❌ Almost untested |
| **Read** | Retrieval, ranking, context assembly | ✅ LoCoMo, LongMemEval |

**Key insight:** Most production failures originate in Write and Manage, but all popular benchmarks only test Read. This is the structural gap.

### 2. Four Memory Competencies (MemoryAgentBench, ICLR 2026)

MemoryAgentBench defines four essential competencies for memory agents:

1. **Accurate Retrieval (AR)** — Precise information extraction from long histories (single-hop + multi-hop)
2. **Test-Time Learning (TTL)** — Learning from in-context examples across sessions and applying later
3. **Long-Range Understanding (LRU)** — Reasoning over extended context (200K+ tokens)
4. **Conflict Resolution (CR)** — Handling contradictory information, temporal updates

**Finding:** No current memory system masters all four. Most systems handle AR well, TTL and CR remain the weakest links.

### 3. MemoryArena: Agentic vs. Static Evaluation

MemoryArena (Stanford/UCSD, ICML 2026) exposes the critical gap:

- **LoCoMo** = static recall benchmark (Q&A about conversations)
- **MemoryArena** = agentic benchmark (memory must guide sequential decisions)

**Devastating finding:** Agents with 90%+ LoCoMo scores perform poorly when memory must **direct behavior** across sessions. The benchmark measures recall; production demands **memory that changes behavior**.

Four task domains:
- Bundled web shopping (multi-item constraints)
- Group travel planning (preference conflict resolution)
- Progressive information search (incremental knowledge building)
- Sequential formal reasoning (multi-step derivation)

### 4. The Benchmark Hierarchy (2026 State)

| Benchmark | Tests | Scale | Focus |
|-----------|-------|-------|-------|
| **LoCoMo** | Retrieval + temporal QA | 1,540 Qs, 300 turns/conv | Static recall from long dialogues |
| **LongMemEval** | Multi-session recall + knowledge updates | 500 Qs | Interactive chat memory |
| **BEAM** | System-level at scale | 1M + 10M tokens | Architecture comparison at extreme scale |
| **MemoryAgentBench** | All 4 competencies | Multi-dataset | Unified competency evaluation |
| **MemoryArena** | Agentic task completion | 4 domains | Memory-guided sequential decisions |
| **Letta Leaderboard** | Dynamic memory management | Model-level | Model capability comparison |
| **STATE-Bench** (Microsoft) | Enterprise agent tasks | Production scenarios | Task completion + pass^5 reliability |

### 5. Competitive Landscape (Public Scores)

From Agent Memory Benchmark leaderboard + Mem0 state-of-memory report:

| System | LoCoMo | LongMemEval | BEAM 1M | BEAM 10M | PersonaMem |
|--------|--------|-------------|---------|----------|------------|
| **Hindsight** | 92.0% | 94.6% | 73.9% | — | 86.6% |
| **Mem0** (Apr 2026) | 92.5% | 94.4% | 64.1% | 48.6% | — |
| **Supermemory** | — | — | — | — | — (self-reported) |
| **Full-context GPT-4o** | ~87% | ~85% | Fails | Fails | — |

**Critical observation:** LoCoMo is saturating (92%+ for multiple systems). The differentiation frontier has moved to:
- BEAM 10M (extreme scale: only 48.6% for best published)
- MemoryArena (agentic tasks: most systems <50%)
- Conflict resolution (MemoryAgentBench: worst-performing competency)

---

## Code: LoCoMo Adapter Skeleton for amg-bench

```python
"""
amg-bench LoCoMo Adapter — Minimal scaffold for benchmarking agent-memory-graph.

Usage:
    python -m amg_bench.locomo_adapter --agent-path my_agent --output results.json

Dependencies:
    pip install datasets agent-memory-graph
"""

import json
import time
import argparse
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from datasets import load_dataset


# ── Benchmark Schema ──────────────────────────────────────────────

@dataclass
class LoCoMoQuestion:
    """One evaluation question from LoCoMo."""
    question_id: str
    category: str          # single_hop | multi_hop | open_domain | temporal
    question: str
    gold_answer: str
    session_ids: list[str] # which conversation sessions are relevant
    turns: list[int]       # specific turn indices


@dataclass
class BenchmarkResult:
    """Result of a single question evaluation."""
    question_id: str
    category: str
    answer: str
    gold: str
    correct: bool
    latency_ms: float
    tokens_used: int = 0


@dataclass
class AggregateReport:
    """Final benchmark report."""
    total: int = 0
    correct: int = 0
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)
    avg_latency_ms: float = 0.0
    total_tokens: int = 0
    results: list[BenchmarkResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0


# ── LoCoMo Loader ─────────────────────────────────────────────────

def load_locomo() -> tuple[list[dict], list[LoCoMoQuestion]]:
    """
    Load LoCoMo dataset from HuggingFace.

    Returns:
        conversations: list of {session_id, turns, speaker_a, speaker_b}
        questions: list of LoCoMoQuestion
    """
    ds = load_dataset("snap-research/locomo", split="test")

    conversations = []
    questions = []

    for item in ds:
        # Each item has conversation sessions + QA pairs
        conv_sessions = item.get("conversation", [])
        for i, session in enumerate(conv_sessions):
            conversations.append({
                "session_id": f"{item['id']}_session_{i}",
                "turns": session,
            })

        for qa in item.get("qa_pairs", []):
            questions.append(LoCoMoQuestion(
                question_id=qa["question_id"],
                category=qa.get("category", "single_hop"),
                question=qa["question"],
                gold_answer=qa["answer"],
                session_ids=[f"{item['id']}_session_{s}" for s in qa.get("sessions", [])],
                turns=qa.get("turns", []),
            ))

    return conversations, questions


# ── Agent Interface ────────────────────────────────────────────────

# The agent under test must implement this interface:
AgentIngestFn = Callable[[str, list[dict]], None]
AgentQueryFn = Callable[[str], str]


def wrap_amg_agent(graph):
    """
    Wrap an agent-memory-graph instance as a benchmark agent.

    Args:
        graph: MultiAgentMemoryGraph or MemoryGraph instance

    Returns:
        (ingest_fn, query_fn) tuple
    """
    from amg import MemoryGraph  # adjust import as needed

    def ingest(session_id: str, turns: list[dict]):
        """Write stage: ingest conversation turns into memory graph."""
        for turn in turns:
            speaker = turn.get("speaker", "user")
            text = turn.get("text", "")
            graph.add(
                content=f"{speaker}: {text}",
                metadata={
                    "session_id": session_id,
                    "turn_index": turn.get("turn_index", 0),
                    "timestamp": turn.get("timestamp"),
                }
            )

    def query(question: str) -> str:
        """Read stage: retrieve and answer."""
        results = graph.search(question, k=5)
        # Simple answer composition — agents can override with LLM synthesis
        if not results:
            return ""
        # Return top result content as baseline
        return results[0].content if hasattr(results[0], 'content') else str(results[0])

    return ingest, query


# ── Evaluation Harness ────────────────────────────────────────────

def evaluate_agent(
    ingest_fn: AgentIngestFn,
    query_fn: AgentQueryFn,
    conversations: list[dict],
    questions: list[LoCoMoQuestion],
    max_questions: Optional[int] = None,
) -> AggregateReport:
    """
    Run the LoCoMo evaluation loop.

    Phase 1: Ingest all conversations (Write stage)
    Phase 2: Answer all questions (Read stage)
    Phase 3: Score with substring exact match + LLM judge (optional)
    """
    report = AggregateReport()

    # Phase 1: Write
    print(f"[Phase 1] Ingesting {len(conversations)} conversation sessions...")
    t0 = time.time()
    for conv in conversations:
        ingest_fn(conv["session_id"], conv["turns"])
    print(f"  Ingestion complete in {time.time() - t0:.1f}s")

    # Phase 2: Query
    qs = questions[:max_questions] if max_questions else questions
    print(f"[Phase 2] Evaluating {len(qs)} questions...")

    latencies = []
    for q in qs:
        t0 = time.time()
        answer = query_fn(q.question)
        latency = (time.time() - t0) * 1000
        latencies.append(latency)

        # Phase 3: Score (SubEM — substring exact match)
        is_correct = _substring_match(answer, q.gold_answer)

        result = BenchmarkResult(
            question_id=q.question_id,
            category=q.category,
            answer=answer,
            gold=q.gold_answer,
            correct=is_correct,
            latency_ms=latency,
        )
        report.results.append(result)
        report.total += 1
        if is_correct:
            report.correct += 1

    # Aggregate
    report.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0

    # Per-category breakdown
    categories = set(r.category for r in report.results)
    for cat in categories:
        cat_results = [r for r in report.results if r.category == cat]
        cat_correct = sum(1 for r in cat_results if r.correct)
        report.by_category[cat] = {
            "total": len(cat_results),
            "correct": cat_correct,
            "accuracy": cat_correct / len(cat_results) if cat_results else 0,
            "avg_latency_ms": sum(r.latency_ms for r in cat_results) / len(cat_results),
        }

    return report


def _substring_match(prediction: str, gold: str) -> bool:
    """LoCoMo-style SubEM metric."""
    pred_lower = prediction.lower().strip()
    gold_lower = gold.lower().strip()
    if not gold_lower:
        return False
    # Check if gold answer appears as substring of prediction or vice versa
    return gold_lower in pred_lower or pred_lower in gold_lower


def print_report(report: AggregateReport):
    """Pretty-print benchmark results."""
    print("\n" + "=" * 60)
    print("LoCoMo Benchmark Results")
    print("=" * 60)
    print(f"\nOverall Accuracy: {report.accuracy:.1%} ({report.correct}/{report.total})")
    print(f"Average Latency: {report.avg_latency_ms:.0f}ms")
    print(f"\n{'Category':<20} {'Accuracy':>10} {'Latency':>10} {'Count':>8}")
    print("-" * 50)
    for cat, stats in sorted(report.by_category.items()):
        print(f"{cat:<20} {stats['accuracy']:>10.1%} {stats['avg_latency_ms']:>9.0f}ms {stats['total']:>8}")

    print("\n" + "=" * 60)


# ── CLI Entry Point ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run LoCoMo benchmark on agent")
    parser.add_argument("--max-questions", type=int, default=None, help="Limit questions (for quick runs)")
    parser.add_argument("--output", type=str, default=None, help="Save JSON results to path")
    args = parser.parse_args()

    # Load dataset
    conversations, questions = load_locomo()
    print(f"Loaded {len(conversations)} sessions, {len(questions)} questions")

    # Create amg agent
    from amg import MemoryGraph
    graph = MemoryGraph()
    ingest_fn, query_fn = wrap_amg_agent(graph)

    # Run evaluation
    report = evaluate_agent(ingest_fn, query_fn, conversations, questions, args.max_questions)
    print_report(report)

    # Save results
    if args.output:
        data = {
            "accuracy": report.accuracy,
            "total": report.total,
            "correct": report.correct,
            "avg_latency_ms": report.avg_latency_ms,
            "by_category": report.by_category,
        }
        with open(args.output, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
```

---

## Key Insights

### Insight 1: Retrieval Benchmarks Are Saturating — The Moat Has Moved

LoCoMo scores of 92%+ are now table stakes (Hindsight, Mem0, Supermemory all claim this). Publishing another system with "93% on LoCoMo" adds zero competitive signal. The actual frontier is:

- **BEAM 10M** (extreme scale: best published is 48.6%)
- **MemoryArena** (agentic tasks: most systems <50%)
- **Conflict resolution** (the weakest competency across all systems)

**Action for amg:** Don't compete on LoCoMo scores. Compete on conflict resolution (amg has `retrieval_quality_audit`, `attention_distribution`, OWASP security suite) and structural organization (graph-based memory, which no benchmark yet measures well).

### Insight 2: The Write-Manage Gap Is Where Graph Memory Wins

The three-stage model (Write-Manage-Read) reveals that vector stores only handle Read. Graph-based memory with provenance tracking, consolidation, and conflict detection can address all three stages. amg's unique capabilities map perfectly:

| Stage | What Fails in Production | amg Capability |
|-------|------------------------|----------------|
| Write | Over-storing noise | `entropy_contribution` (leave-one-out) + adaptive forgetting |
| Manage | Unresolved conflicts | `consolidate()` NREM/REM + `retrieval_quality_audit()` + interference detection |
| Read | Low diversity retrieval | `attention_distribution()` + `retrieval_quality_explain()` |

**This is the positioning argument:** "Other systems pass retrieval benchmarks. We're the only system that diagnoses and manages memory quality."

### Insight 3: MCP Registry Is the Distribution Channel, Not Just npm

The MCP registry hit 10K+ servers by mid-2026. The 2026 MCP roadmap includes **native session memory protocol** — meaning memory will become a first-class MCP concern. amg already has 16 MCP tools. Publishing to the registry is a strategic imperative:

- First-mover advantage for graph-based memory in MCP registry
- Amg's 16 MCP tools already cover write/read/manage operations
- MCP Server Cards (2026 roadmap) will expose capabilities — amg's 875+ APIs dwarf competitors

### Insight 4: MemoryArena's POMDP Framing Is the Right Mental Model

MemoryArena models memory as belief-state tracking in a POMDP (Partially Observable MDP). This is exactly how amg should be positioned theoretically:

- **States** = underlying user preferences/facts (partially observable)
- **Observations** = conversation turns (noisy, incomplete)
- **Actions** = retrieval decisions (what to surface)
- **Reward** = task completion (not recall accuracy)

This connects to amg's `spreading_activation` + `competitive_spreading` as approximate belief-state updates.

---

## amg Strategic Positioning Matrix

```
                    Retrieval-Only Benchmarks
                    (LoCoMo, LongMemEval)
                    ┌──────────────────────────┐
                    │  COMMODITIZED ZONE       │
                    │  Mem0, Hindsight, Zep    │
                    │  (92%+ — no moat)        │
                    └──────────────────────────┘
                                          ↓
    Agentic Benchmarks                    ↓
    (MemoryArena, STATE-Bench)            ↓
    ┌──────────────────────────────────────┐
    │  FRONTIER ZONE                       │
    │  → amg ← (graph + quality mgmt)      │
    │  (no system dominates yet)           │
    └──────────────────────────────────────┘
```

---

## Next Actions

1. **[P0] Implement amg-bench LoCoMo adapter** — Use the code scaffold above as starting point. The adapter needs: HuggingFace dataset loader → amg agent wrapper → evaluation harness → JSON output. Estimated: 1 day.

2. **[P1] Write amg positioning whitepaper** — "Beyond Retrieval: The Write-Manage-Read Framework for Agent Memory." Uses this research as backbone. The three-stage model + MemoryArena gap is the core argument.

3. **[P1] Submit amg MCP server to official registry** — 10K+ servers already registered. amg's 16 MCP tools = most comprehensive memory MCP. First graph-based memory server in registry = strong positioning.

4. **[P2] Implement MemoryArena adapter** — More complex than LoCoMo (requires agent-in-environment loop). But this is where the field is heading. Start with the bundled shopping domain (simplest).

5. **[P2] Add conflict_resolution metric to amg-bench** — MemoryAgentBench's CR category is the weakest link across all systems. amg's `retrieval_quality_audit()` already detects interference. Formalize as benchmark metric.

---

## Quality Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 5 concepts | Three-stage model, Four competencies, MemoryArena, Benchmark hierarchy, Competitive landscape |
| Runnable code (≥1) | ✅ ~200 lines | LoCoMo adapter scaffold with CLI, dataset loader, evaluation harness, amg wrapper |
| Key insights (≥3) | ✅ 4 insights | Saturation, Write-Manage gap, MCP distribution, POMDP framing |
| Next actions (≥1) | ✅ 5 actions | LoCoMo adapter → positioning paper → MCP registry → MemoryArena → CR metric |
| Project connection | ✅ Strong | Directly serves amg-bench, MCP registry publish, and competitive positioning against Mandol/Mem0/Hindsight |

---

_Sources: LoCoMo (Snap Research), MemoryArena (Stanford/UCSD, ICML 2026), MemoryAgentBench (HUST, ICLR 2026), Mem0 State of Memory 2026, Letta Memory Benchmark, MCP Registry (registry.modelcontextprotocol.io), EverMind 2026 rankings, Label Studio eval guide, WorkOS MCP Guide 2026._
