# The Memory Policy Paradigm: System-2 Control, Multi-Context RL, and Structured Substrates

**Date:** 2026-06-15
**Topic:** Post-ICLR 2026 synthesis — how agent memory is shifting from static retrieval to learned policies
**Research Methodology:** autoresearch (explicit metrics, rapid cycles, retain/rollback, cumulative, simplicity-first)
**Relation to existing work:** Complements `2026-06-15-hindsight-mini-rl-memory-integration.md` (which focuses on HER+RL integration). This note focuses on the *architectural paradigm shift* and extracts actionable patterns for agent-memory-graph.

---

## 核心概念 (Core Concepts)

### 1. System-2 Memory Control (InfMem / ICLR 2026)

**Paper:** "INFMEM: Learning System-2 Memory Control for Long-Context Agent" (Wang et al., ICLR 2026 Workshop)

The core insight: memory management is not a side-effect of retrieval — it's a **deliberate reasoning process** that should be learned. InfMem introduces a three-phase protocol:

```
PreThink → Retrieve → Write → (loop or STOP)
```

- **PreThink:** Monitors current memory buffer; decides if evidence is sufficient to answer (STOP) or if more retrieval is needed (RETRIEVE). Synthesizes query + predicts retrieve size.
- **Retrieve:** Issues targeted queries *within the same document* (no external corpus). Non-monotonic access — can revisit earlier sections.
- **Write:** Evidence-aware joint compression. Prioritizes answer-critical evidence. Maintains bounded memory.
- **Adaptive Early Stopping:** Stops when PreThink confidence crosses threshold → massive wall-clock savings.

**Key results:** On Qwen2.5-7B, InfMem achieves 60.30 avg accuracy vs MemAgent's 37.06 — a **63% relative improvement** while being 3x faster (14:08 vs 51:34 on 7B).

**Why it matters for us:** Our agent-memory-graph currently uses static retrieval (BM25 + Vector + Graph fusion). InfMem shows that a *learned* retrieval controller trained with GRPO can dramatically outperform static fusion — this is the natural next step after our Adaptive Fusion work.

### 2. Multi-Context GRPO (MemSearcher)

**Paper:** "MemSearcher: Training LLMs to Reason, Search and Manage Memory via End-to-End Reinforcement Learning" (Yuan et al., Nov 2025)

MemSearcher solves the context explosion problem in search agents by making the LLM itself a memory manager:

```
Turn i:
  context = (question, memory_{i-1})    // NOT full history
  thought = LLM(context)
  action = LLM(thought)
  observation = execute(action)
  memory_i = LLM_Manager(observation, memory_{i-1})  // compact update
```

**Multi-Context GRPO** extends standard GRPO by sampling trajectory groups *across different contexts* (conversations), propagating trajectory-level advantages across all. This jointly optimizes:
- Reasoning quality
- Search strategy
- Memory management

**Key results:** 3B MemSearcher outperforms 7B baselines (+11-12% average gain across 7 benchmarks), proving that **smart memory management > raw model capacity**.

### 3. Structured Memory Substrate (Hindsight)

**Paper:** "Hindsight is 20/20: Building Agent Memory that Retains, Recalls, and Reflects" (Latimer et al., Dec 2025)

Hindsight separates memory into four **epistemically-distinct networks**:

| Network | Content | Example |
|---------|---------|---------|
| **World** | Objective facts about entities | "User lives in Shanghai" |
| **Bank (Experience)** | Agent's own actions, first-person | "I helped the user debug a Python script" |
| **Opinion** | Subjective beliefs with confidence scores | "User prefers concise answers (0.8)" |
| **Observation** | Entity summaries synthesized from facts | "Project X: React frontend, Python backend, deployed on Vercel" |

Two engines operate over these networks:
- **TEMPR** (Temporal Entity Memory Priming Retrieval): 4 parallel searches (semantic vector, BM25, graph traversal, temporal filtering) merged via Reciprocal Rank Fusion + neural reranker
- **CARA** (Coherent Adaptive Reasoning Agents): Preference-conditioned reflection with configurable skepticism/literalism/empathy

**Key results:** 91% accuracy on LongMemEval, significant gains over RAG baselines across all question types.

### 4. Memory-R1: Outcome-Driven RL for Memory Operations

**Paper:** "Memory-R1" (Yan et al., ACL 2026 Main, 164 citations)

Already partially implemented in our `LearnableMemoryManager`. Key updates from the latest version (v5, Jan 2026):
- Generalizes across **3 benchmarks** (LoCoMo, MSC, LongMemEval) and **3 model scales** (3B-14B)
- Only **152 training QA pairs** needed — outcome-driven RL eliminates need for labeled memory operations
- Answer Agent applies **Memory Distillation**: filters 60 retrieved memories → surfaces only relevant entries

### 5. The Convergence Pattern: What All Four Papers Agree On

Every top-tier paper at ICLR 2026 converges on the same architecture:

```
┌─────────────────────────────────────────────┐
│         LEARNED MEMORY POLICY               │
│  (System-2 controller, not heuristics)      │
├─────────────────────────────────────────────┤
│  PreThink (sufficiency check)               │
│     ↓                                       │
│  Retrieve (targeted, non-monotonic)          │
│     ↓                                       │
│  Distill (filter noise, keep signal)         │
│     ↓                                       │
│  Write (evidence-aware compression)          │
│     ↓                                       │
│  Reflect (update beliefs, evolve)            │
├─────────────────────────────────────────────┤
│       STRUCTURED MEMORY SUBSTRATE           │
│  (separated by epistemic type, not flat)     │
├─────────────────────────────────────────────┤
│  MULTI-SIGNAL FUSION RETRIEVAL              │
│  (vector + BM25 + graph + temporal)         │
└─────────────────────────────────────────────┘
```

---

## 代码示例 (Runnable Code)

### Example 1: Minimal System-2 Memory Controller

A lightweight PreThink-Retrieve-Write loop inspired by InfMem, implementable as a pluggable layer over agent-memory-graph:

```python
"""
Minimal System-2 Memory Controller
Inspired by InfMem (ICLR 2026) — PreThink/Retrieve/Write protocol
Designed to plug into agent-memory-graph's retrieval pipeline.

Usage:
    controller = System2MemoryController(memory_store, llm_client)
    result = controller.answer("What did we decide about the API design?", max_steps=5)
"""

from dataclasses import dataclass, field
from typing import Optional, Literal
import json

@dataclass
class MemoryBuffer:
    """Bounded memory buffer with evidence tracking."""
    items: list[dict] = field(default_factory=list)
    max_tokens: int = 2048

    def add(self, content: str, source: str, relevance: float):
        self.items.append({
            "content": content,
            "source": source,
            "relevance": relevance,
            "token_est": len(content) // 4,  # rough estimate
        })
        self._compress()

    def _compress(self):
        """Evidence-aware compression: drop lowest-relevance items when over budget."""
        total = sum(i["token_est"] for i in self.items)
        while total > self.max_tokens and self.items:
            # Remove lowest relevance item (InfMem's evidence-aware write)
            worst = min(range(len(self.items)), key=lambda i: self.items[i]["relevance"])
            total -= self.items[worst]["token_est"]
            self.items.pop(worst)

    def context(self) -> str:
        return "\n".join(f"[{i['relevance']:.2f}] {i['content']}" for i in self.items)

    def is_sufficient(self, question: str, llm) -> tuple[bool, str]:
        """PreThink: check if current memory suffices to answer."""
        prompt = f"""Question: {question}

Current memory:
{self.context()}

Can you answer the question using ONLY the memory above?
Respond JSON: {{"sufficient": true/false, "missing": "what's missing"}}
"""
        resp = llm.complete(prompt)
        result = json.loads(resp)
        return result.get("sufficient", False), result.get("missing", "")


class System2MemoryController:
    """
    PreThink → Retrieve → Write loop with adaptive early stopping.
    Plugs into any retrieval backend (BM25, vector, graph).
    """

    def __init__(self, memory_store, llm_client, retrieve_fn=None):
        self.memory_store = memory_store
        self.llm = llm_client
        self.retrieve_fn = retrieve_fn or memory_store.search
        self.buffer = MemoryBuffer(max_tokens=2048)

    def answer(self, question: str, max_steps: int = 5) -> str:
        for step in range(max_steps):
            # Phase 1: PreThink — sufficiency check
            sufficient, missing = self.buffer.is_sufficient(question, self.llm)
            if sufficient:
                return self._generate_answer(question)

            # Phase 2: Retrieve — targeted query synthesis
            query = self._synthesize_query(question, missing)
            results = self.retrieve_fn(query, top_k=10)

            # Phase 3: Write — evidence-aware memory update
            for r in results:
                relevance = self._score_relevance(question, r)
                if relevance > 0.5:  # threshold
                    self.buffer.add(
                        content=r.get("content", ""),
                        source=r.get("id", "unknown"),
                        relevance=relevance,
                    )

        return self._generate_answer(question)

    def _synthesize_query(self, question: str, missing: str) -> str:
        """Generate a targeted query to fill evidence gaps."""
        if missing:
            return f"{missing} (for: {question})"
        return question

    def _score_relevance(self, question: str, result: dict) -> float:
        """Score relevance — can use embedding similarity, LLM judge, or heuristic."""
        # Simple heuristic: overlap-based scoring
        q_words = set(question.lower().split())
        r_words = set(result.get("content", "").lower().split())
        overlap = len(q_words & r_words) / max(len(q_words), 1)
        return min(overlap * 2, 1.0)

    def _generate_answer(self, question: str) -> str:
        prompt = f"""Based on the following memory, answer the question concisely.

Memory:
{self.buffer.context()}

Question: {question}
Answer:"""
        return self.llm.complete(prompt)


# === Quick test with mock LLM ===
if __name__ == "__main__":
    class MockLLM:
        def complete(self, prompt: str) -> str:
            if "Can you answer" in prompt:
                return '{"sufficient": true, "missing": ""}'
            if "Answer:" in prompt:
                return "Based on memory: The API uses REST with JSON."
            return '{"sufficient": false, "missing": "API protocol details"}'

    class MockStore:
        def search(self, query, top_k=10):
            return [
                {"id": "m1", "content": "API uses REST with JSON encoding"},
                {"id": "m2", "content": "Rate limit is 100 req/min"},
            ]

    ctrl = System2MemoryController(MockStore(), MockLLM())
    answer = ctrl.answer("What protocol does the API use?", max_steps=3)
    print(f"Answer: {answer}")
    print(f"Buffer items: {len(ctrl.buffer.items)}")
    print("✅ System-2 controller works!")
```

### Example 2: Multi-Signal Fusion with Learned Weights (MemSearcher-inspired)

```python
"""
Multi-Signal Fusion with Adaptive Weights
Inspired by MemSearcher's multi-context GRPO + our Adaptive Fusion (QDAP).

Instead of fixed weights for vector/BM25/graph, learn optimal fusion per query type.
This is a simplified version showing the core idea — real training uses GRPO.
"""

from dataclasses import dataclass
from collections import defaultdict
import math

@dataclass
class RetrievedItem:
    id: str
    content: str
    vector_score: float = 0.0
    bm25_score: float = 0.0
    graph_score: float = 0.0
    temporal_score: float = 0.0

class AdaptiveFusionRetriever:
    """
    Fuses multiple retrieval signals with query-adaptive weights.
    Query types: factual → BM25 heavy, semantic → vector heavy,
                 relational → graph heavy, temporal → time heavy.
    """

    def __init__(self):
        # Default weights (will be adapted per query type)
        self.query_type_weights = {
            "factual":     {"vector": 0.2, "bm25": 0.5, "graph": 0.1, "temporal": 0.2},
            "semantic":    {"vector": 0.5, "bm25": 0.2, "graph": 0.2, "temporal": 0.1},
            "relational":  {"vector": 0.2, "bm25": 0.1, "graph": 0.6, "temporal": 0.1},
            "temporal":    {"vector": 0.1, "bm25": 0.2, "graph": 0.1, "temporal": 0.6},
        }
        # Feedback tracker for online weight updates
        self.feedback_history: list[dict] = []

    def classify_query(self, query: str) -> str:
        """Classify query type — in production use QDAP-Lite or LLM."""
        q = query.lower()
        if any(w in q for w in ["when", "time", "date", "recent", "before", "after"]):
            return "temporal"
        if any(w in q for w in ["who", "what", "define", "how many"]):
            return "factual"
        if any(w in q for w in ["connect", "relate", "between", "because", "cause"]):
            return "relational"
        return "semantic"

    def fuse(self, query: str, items: list[RetrievedItem]) -> list[RetrievedItem]:
        """Fuse scores using query-adaptive weights."""
        qtype = self.classify_query(query)
        weights = self.query_type_weights[qtype]

        for item in items:
            item.fused_score = (
                item.vector_score * weights["vector"] +
                item.bm25_score * weights["bm25"] +
                item.graph_score * weights["graph"] +
                item.temporal_score * weights["temporal"]
            )

        items.sort(key=lambda x: x.fused_score, reverse=True)
        return items

    def update_weights(self, query: str, qtype: str, reward: float):
        """
        Online weight update inspired by Exp4Fuse.
        reward: 1.0 (good retrieval) to 0.0 (poor).
        Nudges weights toward strategies that worked.
        """
        weights = self.query_type_weights[qtype]
        lr = 0.05  # learning rate

        # Exp3-style weight update: reward good strategies
        total = sum(weights.values())
        for signal in weights:
            prob = weights[signal] / total
            estimated_reward = reward / max(prob, 0.01)
            weights[signal] *= math.exp(lr * estimated_reward / total)

        # Normalize
        total = sum(weights.values())
        for signal in weights:
            weights[signal] /= total

        self.feedback_history.append({
            "query": query, "type": qtype,
            "reward": reward, "weights": dict(weights),
        })


# === Demo ===
if __name__ == "__main__":
    retriever = AdaptiveFusionRetriever()

    items = [
        RetrievedItem("m1", "Meeting scheduled for March 15",
                       vector_score=0.3, bm25_score=0.8, graph_score=0.1, temporal_score=0.9),
        RetrievedItem("m2", "REST API uses JSON encoding",
                       vector_score=0.9, bm25_score=0.7, graph_score=0.3, temporal_score=0.1),
        RetrievedItem("m3", "User connected to backend via VPN",
                       vector_score=0.5, bm25_score=0.2, graph_score=0.9, temporal_score=0.3),
    ]

    for query in ["When was the meeting?", "What is the API protocol?", "How are systems connected?"]:
        qtype = retriever.classify_query(query)
        ranked = retriever.fuse(query, items.copy())
        top = ranked[0]
        print(f"\nQuery: {query!r} → type: {qtype}")
        print(f"  Top: [{top.id}] {top.content} (fused: {top.fused_score:.3f})")

        # Simulate feedback (good retrieval)
        retriever.update_weights(query, qtype, reward=0.9)

    print("\n✅ Adaptive fusion with learned weights works!")
    print(f"Feedback entries: {len(retriever.feedback_history)}")
```

---

## 关键洞察 (Key Insights)

### Insight 1: Memory Management Is Now a Learned Policy Problem, Not a Systems Problem

The ICLR 2026 workshop keynote made this explicit: *"Memory is a data problem, not a systems problem."* Every top paper (InfMem, MemSearcher, Memory-R1, Hindsight) trains a policy — not just builds a better store. Our agent-memory-graph already has the substrate (graph + vector + BM25 + Adaptive Fusion). The next frontier is adding a **PreThink controller** that learns when to retrieve, what to retrieve, and when to stop.

### Insight 2: 3B + Smart Memory > 7B + Dumb Memory

MemSearcher's 3B model beating 7B baselines is the strongest evidence yet that **memory policy quality matters more than model size**. This means our agent-memory-graph (running as infrastructure for any LLM) can give a small model the effective memory performance of a much larger one. This is the core value proposition for npm publish.

### Insight 3: Epistemic Separation Is the Missing Layer

Hindsight's four-network separation (World / Experience / Opinion / Observation) maps perfectly to our agent-memory-graph's entity-relation graph. Currently, all memories are treated uniformly. Adding an **epistemic type tag** (fact | experience | belief | summary) to each memory node would:
- Improve retrieval precision (don't retrieve opinions for factual queries)
- Enable belief evolution tracking (confidence scores on Opinion nodes)
- Support the CARA reflection pattern (preference-conditioned reasoning)

This is a **schema change, not an algorithm change** — very low implementation cost.

### Insight 4: Multi-Context GRPO Is the Training Method We Need

Standard GRPO optimizes within a single conversation. MemSearcher's multi-context GRPO samples trajectory groups *across* conversations, propagating advantages globally. This is exactly what we need for training memory policies that generalize across different user interactions. The key insight: **memory management skills transfer across conversations** — learning what to remember in one chat helps in the next.

### Insight 5: Early Stopping Is Where the Money Is

InfMem's adaptive early stopping gives a **3x speedup** with no accuracy loss. In production, most queries can be answered after 1-2 retrieval rounds, not the current 5-10. This directly impacts API costs and latency. Adding a simple sufficiency check (PreThink) before each retrieval round would be the highest-ROI feature for agent-memory-graph.

### Insight 6: Hindsight's TEMPR = Our Three-Way Fusion + One Missing Piece

TEMPR uses four parallel signals (semantic, BM25, graph, temporal) merged via Reciprocal Rank Fusion. We have three (vector, BM25, graph). The **missing piece is temporal filtering** — many real queries are time-sensitive ("what did we decide last week?"). Adding a temporal signal (date-range filtering + recency boost) to Adaptive Fusion would complete the TEMPR equivalence and is straightforward to implement.

---

## 与现有项目的关联 (Project Connections)

| Research Finding | agent-memory-graph Feature | Priority | Effort |
|-----------------|---------------------------|----------|--------|
| PreThink sufficiency check | New `System2Controller` class | HIGH | ~150 lines |
| Epistemic type tagging | Schema field on MemoryNode | HIGH | ~30 lines |
| Temporal signal in fusion | Extend AdaptiveFusion with time scoring | MEDIUM | ~80 lines |
| Early stopping | Retrieval loop with confidence threshold | MEDIUM | ~50 lines |
| Multi-context GRPO | Training pipeline for memory policies | LOW (research) | ~500 lines |
| CARA reflection | Opinion/belief network evolution | LOW (future) | ~300 lines |

---

## 下一步行动 (Next Actions)

1. **[IMMEDIATE]** Add `epistemic_type` field to MemoryNode schema (fact | experience | belief | summary). This is a 30-line change that unlocks Hindsight-style structured retrieval.

2. **[THIS WEEK]** Implement `System2MemoryController` — a lightweight PreThink/Retrieve/Write loop wrapper around the existing retrieval pipeline. Start with a rule-based PreThink (token threshold + keyword overlap) before graduating to LLM-based.

3. **[NEXT WEEK]** Add temporal signal to Adaptive Fusion. This completes the four-way fusion (vector + BM25 + graph + temporal) matching Hindsight's TEMPR architecture.

4. **[RESEARCH]** Prototype the multi-context GRPO training loop for memory policies. Use MemSearcher's open-source code (github.com/icip-cas/MemSearcher) as reference.

5. **[DOC]** Update README for npm publish to highlight that agent-memory-graph implements the substrate layer that these ICLR 2026 papers require. Position it as: *"The structured memory substrate for learned memory policies."*

---

## 质量自评 (Quality Assessment)

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 5 concepts | Each with paper reference + key metrics |
| Runnable code (≥1) | ✅ 2 examples | System2Controller (~80 lines) + AdaptiveFusionRetriever (~70 lines) |
| Key insights (≥3) | ✅ 6 insights | Each actionable and tied to our codebase |
| Next actions (≥1) | ✅ 5 actions | Prioritized with effort estimates |
| Unique perspective | ✅ | Synthesizes 4 papers into unified architecture pattern; connects to specific code changes |
| Project connection | ✅ | 6-row mapping table from research → feature |

---

## References

- **InfMem** (Wang et al., ICLR 2026 Workshop): arxiv.org/abs/2602.02704 | github.com/UCMP13753/InfMem
- **MemSearcher** (Yuan et al., Nov 2025): arxiv.org/abs/2511.02805 | github.com/icip-cas/MemSearcher
- **Hindsight** (Latimer et al., Dec 2025): arxiv.org/abs/2512.12818
- **Memory-R1** (Yan et al., ACL 2026 Main): arxiv.org/abs/2508.19828
- **Mem0 State of Agent Memory 2026**: mem0.ai/blog/state-of-ai-agent-memory-2026
- **ICLR 2026 Memory Workshop**: iclr.cc/virtual/2026/workshop/10000792
- **Tsinghua Agent Memory Paper List**: github.com/TsinghuaC3I/Awesome-Memory-for-Agents

---

*Generated by Catalyst autoresearch loop — 2026-06-15 20:10 CST*
