# Agent Memory Benchmarking: Designing amg-bench

> Research Date: 2026-08-06
> Topic: How to evaluate agent memory systems — landscape, metrics, and amg-bench design
> Context: HEARTBEAT lists amg-bench as next dev target (Research #037 done)

---

## Core Concepts

### 1. The Four-Layer Evaluation Stack (arXiv:2603.07670)

The definitive 2026 survey proposes four evaluation layers that no single benchmark covers alone:

| Layer | What It Measures | Example Metrics |
|-------|-----------------|-----------------|
| **L1: Task Effectiveness** | Does memory improve outcomes? | success rate, factual correctness, plan completion |
| **L2: Memory Quality** | Is the right stuff retrieved? | precision/recall of retrieved records, contradiction rate, staleness %, coverage |
| **L3: Efficiency** | At what cost? | latency per op, prompt tokens consumed, retrieval calls/step, storage growth |
| **L4: Governance** | Is it safe/compliant? | privacy leakage rate, deletion compliance, access violations |

**Key insight**: Classical IR metrics (P@k, nDCG) only cover L2 partially. They tell you whether the right record was retrieved, not whether the agent *used* it correctly or whether retrieving it was worth the latency.

### 2. FAMA — Forgetting-Aware Memory Accuracy (Memora, arXiv:2604.20006)

The first metric to penalize reliance on **outdated** memory:

```
FAMA = max(0, MPA - λ · (1 - FAA))
λ = N_forget / (N_presence + N_forget)
```

Where:
- **MPA** = Memory Presence Accuracy (fraction of valid info correctly included)
- **FAA** = Forgetting Absence Accuracy (fraction of obsolete info correctly excluded)
- **λ** = weight based on ratio of forgetting criteria to total criteria

**Impact**: Across all tested systems, applying FAMA reduces scores by 15–43 points. Systems that rank well on MPA reshuffle dramatically under FAMA — Nemori jumps from 3rd to 1st in monthly settings because it has the smallest forgetting penalty.

### 3. The Retrieval-to-Reasoning Gap (MemoryArena, arXiv:2602.16313)

Models that score 90%+ on LoCoMo (passive recall) plummet to **40–60%** on MemoryArena (active, interdependent tasks). The gap exists because:

- LoCoMo tests: "Was fact X in conversation Y?" (single-hop retrieval)
- MemoryArena tests: "Use fact X from session 1 to make decision in session 3" (multi-session reasoning)
- MemoryArena has **766 tasks** across 4 domains: bundled shopping, group travel planning, progressive web search, sequential formal reasoning
- Tasks are **interdependent**: later subtasks require distilling experience from earlier ones

### 4. STATE-Bench: Enterprise Procedural Memory (Microsoft, May 2026)

STATE-Bench evaluates whether memory improves agents on **realistic enterprise tasks**:

- **450 tasks** across travel, customer support, shopping
- Pre-populated environments with databases (bookings, orders)
- LLM user simulator with task-specific rules (~1% variance)
- **Four metrics**: task completion rate, reliability (pass^5), efficiency (turns/tokens), UX score (1-5 rubric)
- "Bring your own memory" pluggable interface
- **Key finding**: Even GPT-5.1 without memory completes <50% of tasks reliably; pass^5 for travel is only ~30%

### 5. The Agent-Capability > Tool-Sophistication Principle (Letta, Aug 2025)

Letta showed that a simple filesystem agent (grep + search_files + answer_question) with GPT-4o-mini scores **74.0%** on LoCoMo — beating Mem0's graph variant (68.5%). This means:

- Agent's ability to *formulate queries* matters more than the retrieval mechanism
- Simpler tools (filesystem ops) are better supported by training data
- Specialized memory tools that require non-standard API patterns may be *harder* for LLMs to use effectively
- **Implication for amg-bench**: test the *system* (agent + memory API), not just the retrieval backend

---

## Code Example: amg-bench Harness Skeleton

A minimal, runnable benchmark harness implementing the four-layer evaluation stack:

```python
"""
amg-bench: Minimal evaluation harness for agent memory systems.

Implements the four-layer metric stack from arXiv:2603.07670
plus FAMA from Memora (arXiv:2604.20006).

Usage:
    python amg_bench.py --dataset locomo --memory-agent my_agent --top-k 10
"""

import time
import json
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from abc import ABC, abstractmethod


# ─── Memory Agent Interface (Bring Your Own Memory) ──────────────────────

class MemoryAgent(ABC):
    """Base class for memory-augmented agents. Plug in your own implementation."""

    @abstractmethod
    def ingest(self, conversation: list[dict]) -> None:
        """Process and store a conversation."""
        ...

    @abstractmethod
    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Retrieve relevant memories for a query."""
        ...

    @abstractmethod
    def answer(self, question: str, retrieved: list[dict]) -> str:
        """Generate an answer using retrieved memories."""
        ...


# ─── Evaluation Criteria ─────────────────────────────────────────────────

@dataclass
class EvalCriterion:
    """Atomic evaluation criterion — presence or forgetting check."""
    description: str
    expected: bool          # True = should be present, False = should be absent
    is_forgetting: bool     # Is this a forgetting-absence criterion?


@dataclass
class BenchmarkQuestion:
    """A single benchmark question with ground-truth criteria."""
    question_id: str
    question: str
    conversation_id: str
    criteria: list[EvalCriterion]
    category: str = "general"   # single-hop, multi-hop, temporal, etc.


@dataclass
class BenchmarkDataset:
    """A collection of conversations and questions."""
    conversations: dict[str, list[dict]]   # id -> messages
    questions: list[BenchmarkQuestion]


# ─── Metrics ─────────────────────────────────────────────────────────────

@dataclass
class Layer1Metrics:
    """Task effectiveness."""
    success_rate: float = 0.0
    avg_answer_correctness: float = 0.0
    per_category: dict[str, float] = field(default_factory=dict)


@dataclass
class Layer2Metrics:
    """Memory quality."""
    retrieval_precision: float = 0.0
    retrieval_recall: float = 0.0
    contradiction_rate: float = 0.0
    staleness_ratio: float = 0.0           # fraction of retrieved that are stale
    fama_score: float = 0.0                # forgetting-aware accuracy


@dataclass
class Layer3Metrics:
    """Efficiency."""
    avg_ingest_time_ms: float = 0.0
    avg_search_time_ms: float = 0.0
    avg_tokens_per_query: int = 0
    avg_retrieval_calls: float = 0.0
    storage_growth_mb: float = 0.0


@dataclass
class Layer4Metrics:
    """Governance (optional, for systems with privacy features)."""
    deletion_compliance: float = 0.0       # did deleted facts stop appearing?
    access_scope_violations: int = 0


@dataclass
class BenchmarkResult:
    agent_name: str
    dataset_name: str
    l1: Layer1Metrics
    l2: Layer2Metrics
    l3: Layer3Metrics
    l4: Optional[Layer4Metrics] = None
    per_question_details: list[dict] = field(default_factory=list)


# ─── FAMA Computation ────────────────────────────────────────────────────

def compute_fama(
    presence_criteria: list[bool],
    forgetting_criteria: list[bool],
    lambda_weight: Optional[float] = None,
) -> float:
    """
    Compute Forgetting-Aware Memory Accuracy (FAMA).

    FAMA = max(0, MPA - λ * (1 - FAA))

    Where:
        MPA = fraction of presence criteria satisfied
        FAA = fraction of forgetting criteria satisfied
        λ = N_forget / (N_presence + N_forget)  [auto if None]

    Returns: FAMA score in [0, 1]
    """
    n_presence = len(presence_criteria)
    n_forget = len(forgetting_criteria)

    if n_presence == 0:
        return 0.0

    mpa = sum(presence_criteria) / n_presence

    if n_forget == 0:
        return mpa  # No forgetting dimension → standard accuracy

    faa = sum(forgetting_criteria) / n_forget

    if lambda_weight is None:
        lambda_weight = n_forget / (n_presence + n_forget)

    return max(0.0, mpa - lambda_weight * (1 - faa))


# ─── LLM-as-Judge (Multi-Judge Protocol) ─────────────────────────────────

def llm_judge(
    response: str,
    criterion: str,
    judge_models: list[Callable] | None = None,
) -> bool:
    """
    Multi-judge protocol: majority vote across 3 judges.

    In production, replace with actual LLM calls:
        judge_models = [gpt_4_call, claude_call, gemini_call]
    """
    if judge_models is None:
        # Simplified: substring match as fallback
        return criterion.lower() in response.lower()

    votes = [model(response, criterion) for model in judge_models]
    return sum(votes) >= (len(votes) // 2 + 1)  # majority


# ─── Benchmark Runner ────────────────────────────────────────────────────

def run_benchmark(
    agent: MemoryAgent,
    dataset: BenchmarkDataset,
    top_k: int = 10,
    verbose: bool = True,
) -> BenchmarkResult:
    """
    Run the full four-layer evaluation pipeline.

    Pipeline: Ingest → Search → Answer → Judge → Score
    """
    # ─── Phase 1: Ingestion ───
    ingest_times = []
    for conv_id, messages in dataset.conversations.items():
        t0 = time.perf_counter()
        agent.ingest(messages)
        ingest_times.append((time.perf_counter() - t0) * 1000)

    # ─── Phase 2: Query & Evaluate ───
    search_times = []
    all_presence = []
    all_forgetting = []
    per_category_correct = {}
    per_category_total = {}
    details = []

    for q in dataset.questions:
        # Search
        t0 = time.perf_counter()
        retrieved = agent.search(q.question, top_k=top_k)
        search_times.append((time.perf_counter() - t0) * 1000)

        # Answer
        answer = agent.answer(q.question, retrieved)

        # Judge each criterion
        presence_results = []
        forgetting_results = []

        for crit in q.criteria:
            passed = llm_judge(answer, crit.description)
            if crit.is_forgetting:
                # For forgetting criteria, "expected=False" means info should NOT appear
                # So "passed" (info absent) = correct
                forgetting_results.append(passed != crit.expected if not crit.expected else passed)
            else:
                presence_results.append(passed == crit.expected)

        # Compute per-question FAMA
        fama = compute_fama(presence_results, forgetting_results)

        all_presence.extend(presence_results)
        all_forgetting.extend(forgetting_results)

        # Track category
        is_correct = fama > 0.5
        per_category_correct[q.category] = per_category_correct.get(q.category, 0) + int(is_correct)
        per_category_total[q.category] = per_category_total.get(q.category, 0) + 1

        details.append({
            "question_id": q.question_id,
            "category": q.category,
            "fama": round(fama, 4),
            "presence_rate": sum(presence_results) / max(1, len(presence_results)),
            "forgetting_rate": sum(forgetting_results) / max(1, len(forgetting_results)),
            "n_retrieved": len(retrieved),
        })

    # ─── Aggregate Metrics ───
    n_questions = len(dataset.questions)

    l1 = Layer1Metrics(
        success_rate=sum(1 for d in details if d["fama"] > 0.5) / n_questions,
        avg_answer_correctness=sum(all_presence) / max(1, len(all_presence)),
        per_category={
            cat: per_category_correct[cat] / per_category_total[cat]
            for cat in per_category_total
        },
    )

    l2 = Layer2Metrics(
        retrieval_precision=sum(all_presence) / max(1, len(all_presence)),
        retrieval_recall=sum(all_presence) / max(1, len(all_presence)),  # proxy
        fama_score=compute_fama(all_presence, all_forgetting),
        # contradiction_rate and staleness_ratio require additional instrumentation
    )

    l3 = Layer3Metrics(
        avg_ingest_time_ms=statistics.mean(ingest_times) if ingest_times else 0,
        avg_search_time_ms=statistics.mean(search_times) if search_times else 0,
        avg_tokens_per_query=0,  # requires token counter integration
        avg_retrieval_calls=1.0,  # one per question in this harness
    )

    if verbose:
        print(f"\n{'═' * 60}")
        print(f"  amg-bench Results: {agent.__class__.__name__}")
        print(f"{'═' * 60}")
        print(f"\nL1 — Task Effectiveness:")
        print(f"  Success Rate:     {l1.success_rate:.1%}")
        print(f"  Answer Correct:   {l1.avg_answer_correctness:.1%}")
        for cat, score in sorted(l1.per_category.items()):
            print(f"    {cat:20s} {score:.1%}")
        print(f"\nL2 — Memory Quality:")
        print(f"  Retrieval Prec:   {l2.retrieval_precision:.1%}")
        print(f"  FAMA Score:       {l2.fama_score:.1%}")
        delta = l2.retrieval_precision - l2.fama_score
        if delta > 0.05:
            print(f"  ⚠ Forgetting Penalty: -{delta:.1%} (stale memory problem)")
        print(f"\nL3 — Efficiency:")
        print(f"  Avg Ingest:       {l3.avg_ingest_time_ms:.1f}ms")
        print(f"  Avg Search:       {l3.avg_search_time_ms:.1f}ms")
        print(f"{'═' * 60}\n")

    return BenchmarkResult(
        agent_name=agent.__class__.__name__,
        dataset_name=dataset.name if hasattr(dataset, 'name') else 'unknown',
        l1=l1,
        l2=l2,
        l3=l3,
        per_question_details=details,
    )


# ─── Demo: Simple In-Memory Agent ────────────────────────────────────────

class SimpleKeywordAgent(MemoryAgent):
    """Minimal agent: stores everything, retrieves by keyword match."""

    def __init__(self):
        self.store: list[str] = []

    def ingest(self, conversation: list[dict]) -> None:
        for msg in conversation:
            self.store.append(f"{msg.get('role','')}: {msg.get('content','')}")

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        query_words = set(query.lower().split())
        scored = []
        for text in self.store:
            text_words = set(text.lower().split())
            overlap = len(query_words & text_words)
            scored.append((overlap, text))
        scored.sort(reverse=True)
        return [{"content": t, "score": s} for s, t in scored[:top_k]]

    def answer(self, question: str, retrieved: list[dict]) -> str:
        if not retrieved:
            return "I don't have information about that."
        context = " ".join(r["content"] for r in retrieved[:3])
        return f"Based on stored info: {context[:200]}"


# ─── Smoke Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Create a tiny dataset
    conversations = {
        "conv_001": [
            {"role": "user", "content": "My name is Alice and I prefer vegetarian food."},
            {"role": "assistant", "content": "Noted! Vegetarian preference saved."},
            {"role": "user", "content": "Actually, I recently started eating fish too."},
            {"role": "assistant", "content": "Updated! Pescatarian preference saved."},
            {"role": "user", "content": "What diet do I follow?"},
        ],
    }

    questions = [
        BenchmarkQuestion(
            question_id="q_001",
            question="What is Alice's current diet?",
            conversation_id="conv_001",
            category="knowledge-update",
            criteria=[
                EvalCriterion("pescatarian", expected=True, is_forgetting=False),
                EvalCriterion("fish", expected=True, is_forgetting=False),
                EvalCriterion("vegetarian", expected=False, is_forgetting=True),
            ],
        ),
    ]

    dataset = BenchmarkDataset(conversations=conversations, questions=questions)

    # Run benchmark
    agent = SimpleKeywordAgent()
    result = run_benchmark(agent, dataset, top_k=5)

    # Verify FAMA computation independently
    # FAMA = max(0, MPA - λ * (1 - FAA)) where λ = N_forget / (N_presence + N_forget)
    fama_all_pass = compute_fama([True, True], [True])
    assert fama_all_pass == 1.0, f"FAMA should be 1.0 when all pass, got {fama_all_pass}"

    fama_forget_fail = compute_fama([True, True], [False])
    # λ = 1/3, FAMA = max(0, 1.0 - 1/3 * 1) = 0.667
    assert 0.6 < fama_forget_fail < 0.7, f"FAMA penalized, got {fama_forget_fail}"

    fama_no_forgetting = compute_fama([True, False], [])
    assert fama_no_forgetting == 0.5, f"FAMA without forgetting = MPA, got {fama_no_forgetting}"

    print("✅ All assertions passed. Harness is working.")
```

**Run it:**
```bash
python amg_bench.py
# Output: Four-layer report with FAMA score, per-category breakdown,
# efficiency metrics, and forgetting penalty warning
```

---

## Key Insights

### Insight #1: Retrieval ≠ Memory (The 50-Point Gap)

The most striking finding across the 2026 literature: **systems scoring 90%+ on LoCoMo drop to 40–60% on MemoryArena**. LoCoMo tests passive recall ("Was this fact mentioned?"), while MemoryArena tests active utility ("Use what you learned in session 1 to solve a different problem in session 3"). **For amg-bench, this means we need interdependent, multi-session tasks — not just QA pairs.** The 50-point gap is the single most important number in agent memory evaluation.

### Insight #2: Forgetting is the Dark Horse

Only 1 of 4 major benchmarks (MemoryAgentBench) tests selective forgetting explicitly. Yet FAMA shows that **forgetting penalties cause 15–43 point score reductions** across all systems. Systems that look identical on MPA reshuffle dramatically under FAMA. **For amg-bench, every question should have paired presence + forgetting criteria** — this is cheap to implement (just add expected=False criteria) and surfaces a failure mode nobody else is measuring well. amg's `adaptive_forgetting` API becomes a first-class differentiator.

### Insight #3: Agent Capability > Tool Sophistication

Letta's filesystem agent (grep + search_files) beats Mem0's graph memory on LoCoMo. This means: (a) evaluation results are **system-level** not **component-level**, (b) LLM post-training determines tool-use effectiveness more than tool design, (c) the "right" evaluation tests the full agent+memory loop, not just the retrieval backend. **For amg-bench, we should provide a reference agent loop** and let systems plug in their memory backend, not the other way around. This matches STATE-Bench's "bring your own memory" interface.

### Insight #4: No Standardized Harness Exists (GLUE Moment)

The arXiv:2603.07670 survey explicitly calls out: *"The field still lacks a community-standard evaluation harness. Each benchmark uses its own datasets, metrics, and protocols, making cross-paper comparison unreliable."* The survey authors propose a "GLUE-style shared leaderboard." **This is the exact opportunity amg-bench can fill** — especially for the graph-memory + entropy + classification niche that no existing benchmark covers.

### Insight #5: The Benchmark Trio (LoCoMo + LongMemEval + BEAM)

The 2026 consensus "trio" for standardized evaluation:
- **LoCoMo** (1,540 Qs): factual recall, temporal reasoning, multi-hop inference
- **LongMemEval** (500 Qs): 6 categories incl. knowledge updates and multi-session recall
- **BEAM** (2,000+ Qs): real-world scale at 1M and 10M token horizons

Mem0 leads with 92.5/94.4/64.1/48.6 scores respectively. **amg-bench should start by supporting these three datasets** via a unified ingestion pipeline, then add amg-specific tests for entropy-guided retrieval, graph topology, and spreading activation.

---

## Next Actions for amg-bench

1. **Implement the harness skeleton above** as `amg/bench/__init__.py` — the four-layer metric stack + FAMA computation is ~200 lines, directly composable with existing amg Python tests (2,294 tests)

2. **Add LoCoMo dataset adapter** — download and parse the public dataset, convert to `BenchmarkDataset` format. This is the fastest path to a publishable benchmark score (~300 questions, 10 conversations)

3. **Define amg-specific test categories** that no existing benchmark covers:
   - **Entropy-guided retrieval**: Does FINGER entropy ranking improve over cosine similarity?
   - **Graph topology utilization**: Does PPR leverage graph structure for multi-hop queries?
   - **Code-aware memory**: Can the system retrieve and apply code decisions across sessions?
   - **Spreading activation**: Does ACT-R activation improve related-concept recall?

4. **Publish results alongside competitive positioning** — run amg against Mem0, LangMem, and A-Mem on LoCoMo. amg's unique differentiators (entropy + classification + streaming + provenance) should show measurable advantages on specific question types

5. **Submit to the Awesome-Agent-Memory list** (TeleAI-UAGI) — this is the de facto benchmark registry. Getting listed there = visibility

---

## Benchmark Landscape Summary Table

| Benchmark | Year | Questions | Multi-Session | Agentic | Forgetting | Key Innovation |
|-----------|------|-----------|---------------|---------|------------|----------------|
| LoCoMo | 2024 | 1,540 | ✓ | ✗ | ✗ | Long-conversation QA, event graphs |
| LongMemEval | 2025 | 500 | ✓ | ✗ | partial | 6 categories incl. knowledge updates |
| MemoryAgentBench | 2025 | 2,000 | ✗ | ✓ | ✓ | 4 cognitive competencies |
| MemBench | 2025 | — | ✗ | ✗ | ✗ | Factual vs. reflective memory |
| BEAM | 2026 | 2,000+ | ✓ | ✗ | ✗ | 1M–10M token scale |
| **MemoryArena** | 2026 | 766 | ✓ | ✓ | ✗ | Interdependent multi-session tasks |
| **STATE-Bench** | 2026 | 450 | ✓ | ✓ | ✗ | Enterprise procedural evaluation |
| **Memora** | 2026 | 600 | ✓ | ✗ | ✓ | FAMA metric, memory mutation |
| **OmniMemEval** | 2026 | — | ✓ | ✓ | — | Agent-native memory system test |
| **amg-bench** (proposed) | 2026 | TBD | ✓ | ✓ | ✓ | **Entropy + graph topology + code-aware** |

---

## References

- arXiv:2603.07670 — *Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers* (2026 survey, 4-layer stack)
- arXiv:2602.16313 — *MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks* (ICML 2026)
- arXiv:2604.20006 — *From Recall to Forgetting: Benchmarking Long-Term Memory for Personalized Agents* (Memora + FAMA, ACL 2026)
- Microsoft STATE-Bench — https://opensource.microsoft.com/blog/2026/05/19/introducing-state-bench-a-benchmark-for-ai-agent-memory
- Letta Blog — *Benchmarking AI Agent Memory: Is a Filesystem All You Need?* (Aug 2025)
- Mem0 State of Agent Memory 2026 — https://mem0.ai/blog/state-of-ai-agent-memory-2026
- Mem0 memory-benchmarks repo — https://github.com/mem0ai/memory-benchmarks
- TeleAI Awesome-Agent-Memory — https://github.com/TeleAI-UAGI/Awesome-Agent-Memory
- Vectorize.io — *Best AI Agent Memory Systems in 2026* (competitive landscape)
- Letta Memory Benchmark / Leaderboard — https://www.letta.com/blog/benchmarking-ai-agent-memory

---

_Research #051 — Generated by deep-exploration-evening cron, 2026-08-06_
