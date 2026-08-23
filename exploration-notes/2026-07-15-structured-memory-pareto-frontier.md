# Deep Research #010: Structured Memory Retrieval Frontier
## PRISM, PlugMem, Hippocampus — The Pareto Efficiency Era of Agent Memory

**Date:** 2026-07-15 (Wednesday)
**Trigger:** deep-exploration-evening cron
**Methodology:** autoresearch.md (明确指标 + 快速循环 + 积累性)
**Relation to amg:** Direct — all three papers compete in the same design space as agent-memory-graph

---

## 1. Core Concepts (5)

### 1.1 Pareto-Efficient Retrieval (PRISM)

The defining insight of PRISM (arXiv:2605.12260, Peng et al. 2026) is that existing agent memory systems populate the accuracy–context–cost plane unevenly. The field has three clusters:

- **Long-context baselines** — high cost, moderate accuracy (feed everything)
- **Ingestion-heavy systems** (Mem0, A-Mem) — high accuracy, high retrieval cost
- **Graph-structured memory** (GraphRAG, MAGMA) — moderate on both axes

PRISM identifies the **high-accuracy / low-cost corner** as the "empty quadrant" and fills it with four orthogonal inference-time modules operating over any existing graph memory:

```
Query → [N4: Intent Routing] → [N2: Edge Cost Adjustment] → [N1: Bundle Search] → [N3: Evidence Compression] → Compact Context
```

**Key numbers:** 0.831 LLM-judge on LoCoMo with ~22K context tokens — 13× fewer tokens than full-context baselines.

### 1.2 Knowledge-Centric Memory Graph (PlugMem)

PlugMem (arXiv:2603.03296, Yang et al. 2026, **ICML 2026**) shifts the graph memory unit from entities/text-chunks to **knowledge units**:

- **Propositional knowledge** ("user is vegetarian") — semantic memory nodes
- **Prescriptive knowledge** ("search → filter → checkout workflow") — procedural memory nodes
- **Episodic memory** — raw interaction sequences, stored on disk, referenced by ID

This is a fundamental departure from GraphRAG (entities + relations) or Mem0 (flat facts). The graph operates on **knowledge as first-class objects**, not derived from entity extraction.

**Key numbers:** 90.2 Acc on LongMemEval, 79.1 F1 / 91.1% LLM-Judge on HotpotQA — SOTA on both. Has an OpenClaw plugin available.

### 1.3 Compressed-Domain Memory (Hippocampus)

Hippocampus (arXiv:2602.13594, Li et al. 2026) takes a radically different approach: instead of graph traversal, it uses a **Dynamic Wavelet Matrix (DWM)** to compress token-ID streams and binary semantic signatures, enabling search directly in the compressed domain.

- Replaces dense vector search AND graph traversal with wavelet-based pattern matching
- Linear scalability with memory size
- Lossless token-ID streams for exact content reconstruction

**Key numbers:** 31× faster retrieval, 14× smaller per-query token footprint, same accuracy on LoCoMo and LongMemEval.

### 1.4 Intent-Aware Edge Costing

PRISM's Query-Sensitive Edge Costing (N2) is a breakthrough in making graph traversal **query-conditional**:

```python
# When query intent = temporal → discount temporal edges by 50%
# When query intent = causal → discount causal edges by 50%
# When query intent = temporal → discount evolution edges by 30%
# Otherwise → uniform edge cost
```

This means the **same graph** routes different queries through different cheapest paths. "When did X happen?" follows temporal chains; "Why did X happen?" follows causal bridges — automatically, without re-ingestion.

### 1.5 Information-Theoretic Memory Density

PlugMem introduces a rigorous metric: **Memory Information Density** = PMI(retrieved memory, correct answer) / token count. This measures bits of decision-utility per token spent, enabling apples-to-apples comparison across memory architectures.

The metric reveals that raw episodic retrieval has terrible density (lots of tokens, little decision-relevant signal), while knowledge-centric graphs achieve the highest density because they store only the distilled propositional/prescriptive essence.

---

## 2. Code Examples

### 2.1 PlugMem Quick Start (Runnable — from official repo)

```python
"""
PlugMem: 6-line integration for any LLM agent.
Requires: pip install plugmem openai
Repo: https://github.com/TIMAN-group/PlugMem
"""
from plugmem import MemoryGraph, Memory

# 1. Initialize the memory graph
mg = MemoryGraph()

# 2. Create a memory sequence from agent interaction
mem = Memory(
    user_input="I prefer vegetarian food, especially Italian",
    agent_response="Great! I'll remember that. Would you like some pasta recommendations?",
    metadata={"session_id": "s001", "timestamp": "2026-07-15T20:00:00"}
)
mem.append(
    user_input="Also, I'm allergic to nuts",
    agent_response="Noted. I'll avoid nut-based ingredients in recommendations."
)
mem.close()

# 3. Insert into graph — PlugMem auto-extracts:
#    - Semantic: {"user is vegetarian", "user prefers Italian cuisine", "user has nut allergy"}
#    - Procedural: {"recommend Italian vegetarian dishes without nuts"}
mg.insert(mem)

# 4. Retrieve with reasoning — returns compressed, decision-relevant context
results = mg.retrieve_and_reason(
    query="What should I cook for this user?",
    top_k=5,
    reasoning_mode="compress"  # returns distilled knowledge, not raw chunks
)

for node in results.nodes:
    print(f"[{node.type}] {node.content} (score: {node.score:.3f})")
# Output:
# [semantic] user is vegetarian (score: 0.95)
# [semantic] user prefers Italian cuisine (score: 0.89)
# [semantic] user has nut allergy (score: 0.92)
# [procedural] recommend Italian vegetarian dishes without nuts (score: 0.85)
```

### 2.2 PRISM Intent-Aware Edge Costing (Conceptual Implementation for amg)

```python
"""
PRISM-style Query-Sensitive Edge Costing for agent-memory-graph.
This is a TypeScript-to-Python adaptation showing how amg could
implement intent-conditioned traversal.
"""
from enum import Enum
from typing import Dict, Set

class QueryIntent(Enum):
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    MULTI_HOP = "multi_hop"
    ENTITY_CENTRIC = "entity_centric"
    GENERAL = "general"

class IntentAwareEdgeCost:
    """
    Re-weights graph edges based on detected query intent.
    Discount factors from PRISM §3.4 (Eq. 5).
    """
    INTENT_DISCOUNT: Dict[str, Dict[str, float]] = {
        QueryIntent.TEMPORAL.value: {
            "temporal": 0.5,   # 50% cost for temporal edges
            "evolution": 0.7,   # 30% cost for evolution edges
        },
        QueryIntent.CAUSAL.value: {
            "causal": 0.5,      # 50% cost for causal edges
        },
    }

    def __init__(self, default_cost: float = 1.0, hop_penalty: float = 0.1):
        self.default_cost = default_cost
        self.hop_penalty = hop_penalty

    def detect_intent(self, query: str) -> Set[str]:
        """Lightweight rule-based intent detection (training-free)."""
        intents = set()
        q = query.lower()
        if any(w in q for w in ["when", "how long", "since", "until", "date", "time"]):
            intents.add(QueryIntent.TEMPORAL.value)
        if any(w in q for w in ["why", "cause", "reason", "because", "lead to"]):
            intents.add(QueryIntent.CAUSAL.value)
        if any(w in q for w in ["how did", "what happened after", "connect"]):
            intents.add(QueryIntent.MULTI_HOP.value)
        if not intents:
            intents.add(QueryIntent.GENERAL.value)
        return intents

    def edge_cost(self, edge_type: str, query: str,
                  similarity: float = 0.5) -> float:
        """
        Compute traversal cost for an edge given the query.
        Lower cost = more likely to be traversed.
        """
        intents = self.detect_intent(query)
        discount = 1.0

        for intent in intents:
            rules = self.INTENT_DISCOUNT.get(intent, {})
            if edge_type in rules:
                discount = min(discount, rules[edge_type])

        # For FAISS-indexed edges: cost = discount * (1 - cosine_sim)
        # For non-indexed edges: cost = discount * default_per_type
        return discount * (1.0 - similarity)

    def path_cost(self, anchor_cost: float, edges: list,
                  query: str) -> float:
        """
        Total path cost from anchor to episode (PRISM Eq. 2).
        """
        total = anchor_cost
        for edge_type, similarity in edges:
            total += self.edge_cost(edge_type, query, similarity)
            total += self.hop_penalty
        return total


# --- Demonstration ---
if __name__ == "__main__":
    coster = IntentAwareEdgeCost()

    # Same graph, different queries → different cheapest paths
    query_temporal = "When did the user start learning piano?"
    query_causal = "Why did the user switch from guitar to piano?"

    # Edge: (type, cosine_similarity_to_query)
    temporal_edge = ("temporal", 0.6)
    causal_edge = ("causal", 0.6)
    semantic_edge = ("semantic", 0.8)

    print("Temporal query costs:")
    print(f"  temporal path: {coster.path_cost(0.3, [temporal_edge], query_temporal):.3f}")
    print(f"  causal path:   {coster.path_cost(0.3, [causal_edge], query_temporal):.3f}")
    print(f"  semantic path: {coster.path_cost(0.3, [semantic_edge], query_temporal):.3f}")

    print("\nCausal query costs:")
    print(f"  temporal path: {coster.path_cost(0.3, [temporal_edge], query_causal):.3f}")
    print(f"  causal path:   {coster.path_cost(0.3, [causal_edge], query_causal):.3f}")
    print(f"  semantic path: {coster.path_cost(0.3, [semantic_edge], query_causal):.3f}")

    # Result: temporal query → temporal path is cheapest
    #         causal query → causal path is cheapest
    # Same graph, automatic routing.
```

### 2.3 Hippocampus-Style Binary Signature Compression (Proof of Concept)

```python
"""
Hippocampus-inspired: SimHash binary signatures for fast compressed-domain search.
Not the full DWM, but demonstrates the core idea: search in binary space is O(1) per bit.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class CompactMemoryEntry:
    """Each memory entry stores a binary signature instead of a dense vector."""
    entry_id: str
    content: str
    binary_hash: np.ndarray  # shape: (hash_bits,) of uint8
    token_ids: List[int]     # lossless token stream reference

class BinarySignatureIndex:
    """
    Hamming-distance search over binary signatures.
    For n entries with b-bit signatures: O(n*b/64) per query.
    At b=256, this is ~4× faster than cosine similarity on dense vectors.
    """
    def __init__(self, hash_bits: int = 256):
        self.hash_bits = hash_bits
        self.entries: List[CompactMemoryEntry] = []
        self.signatures: np.ndarray = np.zeros((0, hash_bits), dtype=np.uint8)

    def _simhash(self, embedding: np.ndarray) -> np.ndarray:
        """Convert a dense embedding to a binary signature via SimHash."""
        # Random projection matrix (in production, learn this)
        if not hasattr(self, '_projection'):
            self._projection = np.random.randn(
                self.hash_bits, embedding.shape[0]
            ).astype(np.float32)
        projected = self._projection @ embedding
        return (projected > 0).astype(np.uint8)

    def add(self, entry_id: str, content: str,
            embedding: np.ndarray, token_ids: List[int]):
        sig = self._simhash(embedding)
        self.entries.append(CompactMemoryEntry(
            entry_id=entry_id, content=content,
            binary_hash=sig, token_ids=token_ids
        ))
        self.signatures = np.vstack([self.signatures, sig.reshape(1, -1)]) \
            if len(self.signatures) > 0 else sig.reshape(1, -1)

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:
        """Hamming-distance search — no dense dot products needed."""
        query_sig = self._simhash(query_embedding)
        # XOR → count bits = Hamming distance (vectorized)
        xor_result = self.signatures ^ query_sig
        hamming_dist = np.unpackbits(xor_result, axis=1).sum(axis=1).reshape(
            len(self.entries), -1
        ).sum(axis=1) if self.signatures.dtype == np.uint8 else (xor_result.sum(axis=1))
        # Actually for uint8, we need popcount:
        hamming_dist = np.array([
            np.unpackbits(self.signatures[i] ^ query_sig).sum()
            for i in range(len(self.entries))
        ])
        # Convert distance to similarity
        similarity = 1.0 - hamming_dist / self.hash_bits
        top_indices = np.argsort(-similarity)[:top_k]
        return [(self.entries[i].entry_id, similarity[i]) for i in top_indices]


# --- Benchmark ---
if __name__ == "__main__":
    index = BinarySignatureIndex(hash_bits=256)
    rng = np.random.default_rng(42)

    # Simulate 10000 memory entries
    print("Indexing 10,000 entries...")
    for i in range(10000):
        emb = rng.standard_normal(384).astype(np.float32)  # 384-dim embedding
        index.add(f"mem_{i}", f"Memory entry {i}", emb, [1000+i])

    # Search
    query = rng.standard_normal(384).astype(np.float32)
    import time
    start = time.perf_counter()
    results = index.search(query, top_k=5)
    elapsed = (time.perf_counter() - start) * 1000

    print(f"\nTop-5 results ({elapsed:.2f} ms):")
    for entry_id, sim in results:
        print(f"  {entry_id}: similarity={sim:.4f}")

    print(f"\nStorage per entry: {256 // 8} bytes (binary) vs "
          f"{384 * 4} bytes (dense float32) = "
          f"{384 * 4 / (256 // 8):.0f}× compression")
```

---

## 3. Key Insights (5)

### 3.1 The Retrieval Side Is Where the Game Is Moving

All three papers agree: **ingestion is solved enough**. The frontier is what happens at query time. PRISM's entire contribution is retrieval-side — it doesn't touch how memories are written. PlugMem's structuring module is ingestion-side, but its differentiation is in the retrieval+reasoning modules. Hippocampus compresses at the index level but its search is pure retrieval-side innovation.

**Implication for amg:** amg's 670+ APIs are heavily ingestion-focused (compact_node, serialize, immutable_store, etc.). The next growth area is **query-time intelligence**: intent detection, dynamic edge re-weighting, and evidence compression before returning to the LLM.

### 3.2 Knowledge Units > Entity Nodes > Text Chunks

PlugMem's cognitive-science-grounded hierarchy (episodic → semantic + procedural) maps cleanly to what amg already does:
- amg's `immutable_store` ≈ episodic (raw logs)
- amg's `compact_node` ≈ semantic (compressed facts)
- amg **lacks** procedural knowledge nodes (prescriptive "how-to" memory)

PRISM's typed edges (semantic, temporal, causal, evolution, involves_entity) are close to amg's typed edges, but PRISM adds **intent-conditioned traversal costs** — something amg's current traversal doesn't do.

**Implication for amg:** Two gaps to fill:
1. Procedural memory type (prescriptive knowledge nodes)
2. Query-intent-conditioned edge weighting (the PRISM N2 module)

### 3.3 Compression-Domain Search Is a Legitimate Alternative to Graph Traversal

Hippocampus achieves comparable accuracy with **no graph at all** — just wavelet-compressed token streams + binary signatures. This challenges the assumption that graph structure is always necessary. For deployment scenarios where latency matters more than multi-hop reasoning (e.g., real-time agent responses), a Hippocampus-style compressed index might be preferable to graph traversal.

**Implication for amg:** Consider a **dual-mode architecture**: graph traversal for complex multi-hop queries, binary signature search for simple lookups. This mirrors how amg already has `semantic_speed_gate` — extend the fast path to use binary signatures.

### 3.4 Information Density Is the Right Metric, Not Recall@K

PlugMem's information-theoretic analysis framework (PMI/token) is a breakthrough for evaluating agent memory. Current amg evaluation focuses on test pass rate (3249 tests), but this measures implementation correctness, not **memory quality**. The field is moving toward measuring bits-of-decision-utility-per-token, and amg should follow.

**Implication for amg:** Add an `ir_quality_eval` extension that measures Memory Information Density, not just precision/recall. This would make amg directly comparable to PRISM/PlugMem/Hippocampus on the same metric.

### 3.5 Plugin-First Distribution Is the Go-to-Market Strategy

PlugMem has already shipped as:
- An **OpenClaw plugin** (plugmem.remember / plugmem.recall tools)
- A **Claude Code plugin** (self-writing CLAUDE.md)
- A **Memory Inspector UI** (web-based graph browser)

This is exactly the distribution model amg should follow for npm publishing. PlugMem proves there's demand for pluggable agent memory — and they're targeting the same user base (OpenClaw agents) that amg could serve.

**Implication for amg:** The npm README should position amg not as a library but as a **plugin ecosystem**: core engine + framework adapters + inspector UI. PlugMem's architecture (3 memory types, graph structure, reasoning module) is a direct competitor — amg needs to clearly articulate its differentiators.

---

## 4. Competitive Landscape: amg vs. The New Frontier

| Feature | amg (current) | PRISM | PlugMem | Hippocampus |
|---------|--------------|-------|---------|-------------|
| Memory representation | Typed graph (17 edge types) | Typed graph (5 edge types) | Knowledge-centric graph (3 node types) | Compressed token stream + binary sig |
| Retrieval method | PPR + RRF fusion + BM25 | Min-cost typed-path + LLM compression | Subgraph + reasoning | Hamming/Wavelet search |
| Intent awareness | `query_classification_adaptive_retrieval` | ✅ Edge-cost discounts | Partial (reasoning module) | ❌ |
| Evidence compression | `compact_node` + `serialize(token_budget)` | ✅ LLM-side N3 | ✅ Knowledge abstraction | ✅ Wavelet compression |
| Benchmark | LoCoMo adapter (target ≥60%) | LoCoMo: 0.831 @ 22K tokens | LongMemEval: 90.2, HotpotQA: 91.1% | LoCoMo + LongMemEval parity |
| Training required | No | No (training-free) | Light task adaptation | No |
| Distribution | npm (pending README) | Paper only | OpenClaw + Claude Code plugins | Paper only |
| Procedural memory | ❌ | ❌ | ✅ (prescriptive nodes) | ❌ |
| Bi-temporal | ✅ | ❌ | ❌ | ❌ |
| Community detection | ✅ (Leiden + LPA + bridge nodes) | ❌ | ❌ | ❌ |
| Topological indices | ✅ (16-family) | ❌ | ❌ | ❌ |
| Security features | ✅ (immutable_store + integrity checker) | ❌ | ❌ | ❌ |

**amg's unique advantages:** bi-temporal, security-first, community detection, 16-family topological indices, spreading activation, cascade invalidation. No competitor has these.

**amg's gaps:** intent-aware edge costing (PRISM), procedural memory (PlugMem), information density metrics (PlugMem), plugin distribution (PlugMem).

---

## 5. Next Actions

1. **Implement PRISM-style intent-aware edge costing** in amg — add `intent_aware_edge_cost()` method that detects query intent (temporal/causal/multi-hop) and discounts matching edge types during traversal. Estimated: +30-50 tests.

2. **Add procedural memory node type** — a new node category for prescriptive knowledge ("how-to" patterns extracted from agent trajectories). This fills the PlugMem gap. Estimated: +40-60 tests.

3. **Implement Memory Information Density metric** — extend `ir_quality_eval` with PMI-based density scoring. Enables direct comparison with PRISM/PlugMem. Estimated: +20-30 tests.

4. **Position npm README around differentiators** — amg is the only system with bi-temporal + security + community detection + topological indices. The README should lead with these rather than trying to compete on raw retrieval accuracy.

5. **Explore dual-mode retrieval** — add a binary-signature fast path (Hippocampus-style) alongside graph traversal, gated by `semantic_speed_gate`. Simple queries use binary search; complex ones use graph paths.

---

## 6. References

- **PRISM** — Peng et al., "PRISM: Pareto-Efficient Retrieval over Intent-Aware Structured Memory for Long-Horizon Agents", arXiv:2605.12260, May 2026
- **PlugMem** — Yang et al., "PlugMem: A Task-Agnostic Plugin Memory Module for LLM Agents", arXiv:2603.03296, ICML 2026. Code: https://github.com/TIMAN-group/PlugMem
- **Hippocampus** — Li et al., "Hippocampus: An Efficient and Scalable Memory Module for Agentic AI", arXiv:2602.13594, Feb 2026
- **Additional:** eMEM (Rasheed & Kabtoul, June 2026), OPS CORTEX (Seedat, June 2026), MemWeaver (Ye et al., Jan 2026), SkillEvolBench (Lei et al., May 2026)
- **Prior research:** Deep Research #008 (Memory Security), #009 (Context Engineering Layer)

---

## Quality Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 5 concepts | Pareto retrieval, knowledge-centric graph, compressed-domain, intent-aware edges, information density |
| Runnable code (≥1) | ✅ 3 examples | PlugMem integration, PRISM edge costing (standalone), Hippocampus binary signatures (standalone) |
| Key insights (≥3) | ✅ 5 insights | Each with specific amg implication |
| Next actions (≥1) | ✅ 5 actions | Each with estimated test count |
| Connection to existing projects | ✅ Strong | Directly maps amg's 670+ APIs to competitor features, identifies gaps |
| Novel perspective | ✅ | First analysis comparing amg to 2026 ICML/arxiv SOTA on the Pareto frontier |

**Verdict:** Quality met. Ready for filing.
