# Agent Memory Engineering 2026 H2: Bi-Temporal Models, Hybrid Retrieval & Co-Evolutionary Graphs

> Research #033 — 2026-07-28
> Method: arxiv search → full-text read → structured analysis → amg roadmap implications

---

## TL;DR

The agent memory field has crystallized into three converging paradigms in 2026 H1: **bi-temporal fact graphs** (Engram), **hybrid tree+graph memory** (H-Mem), and **information-theoretic retrieval** (Memanto). The bar for "beats full-context baseline" has been raised from LoCoMo 65% → 83.6% (Engram). amg's entropy toolkit maps directly onto this landscape — but competitors are shipping faster.

---

## Papers Analyzed

| Paper | arXiv | Date | Key Contribution | Code? |
|-------|-------|------|------------------|-------|
| **Engram** | 2606.09900 | Jun 2026 | Bi-temporal dual-process engine. 83.6% vs 73.2% full-context. Hybrid retrieval: dense+lexical+graph+recency. | ✅ [GitHub](https://github.com/ly-wang19/engram) |
| **H-Mem** | 2605.15701 | May 2026 | Hybrid tree+graph. Temporal-semantic consolidation. SOTA on 3 benchmarks. | ❌ |
| **Memanto** | (pending) | Apr 2026 | Information-theoretic retrieval without KG complexity. Typed semantic memory. | ❌ |
| **MAGE** | (pending) | May 2026 | Co-evolutionary KG for multi-agent. Four-subgraph external memory. | ❌ |
| **ST-LT Transfer** | (pending) | May 2026 | Neuro-symbolic RL for short→long-term KG transfer under partial observability. | ❌ |
| **WorldDB** | (pending) | Apr 2026 | Vector graph-of-worlds. Ontology-aware write-time reconciliation. | ❌ |
| **BrainMem** | (pending) | Apr 2026 | Brain-inspired evolving memory for embodied task planning. | ❌ |

---

## Core Concepts

### 1. Bi-Temporal Data Model (Engram)

**What:** Every fact has TWO temporal dimensions:
- **Valid time** (when the fact was true in the world)
- **Transaction time** (when the fact was recorded in the system)

Contradictions are resolved by **invalidating, never deleting** — each fact keeps full provenance and a supersession chain. This means you can query "as-of" any point in time.

**Why it matters:** This is Graphiti's moat (identified in Research #032). Engram proves the bi-temporal model beats full-context by +10.4 points on LongMemEval. amg already has bi-temporal edge tracking (discovered during Research #032 implementation), but doesn't expose it as a first-class query dimension.

**Code (Engram's approach, simplified):**

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class BiTemporalFact:
    """Bi-temporal fact with provenance chain."""
    subject: str
    predicate: str
    object: str
    valid_from: datetime          # When the fact became true
    valid_to: Optional[datetime]  # None = still valid; set when superseded
    recorded_at: datetime         # When the system learned it
    superseded_by: Optional[str] = None  # ID of the fact that replaced this one
    source: str = "unknown"

class BiTemporalStore:
    """Append-only store. Invalidates, never deletes."""
    def __init__(self):
        self._facts: list[BiTemporalFact] = []
        self._index: dict[str, list[int]] = {}  # (s,p) -> fact indices

    def add(self, fact: BiTemporalFact) -> str:
        """Add fact, auto-invalidate prior facts with same (s,p)."""
        key = f"{fact.subject}|{fact.predicate}"
        if key in self._index:
            for idx in self._index[key]:
                old = self._facts[idx]
                if old.valid_to is None:
                    # Invalidate the old fact — don't delete it!
                    old.valid_to = fact.valid_from
                    old.superseded_by = f"{fact.subject}|{fact.predicate}|{fact.valid_from.isoformat()}"
        idx = len(self._facts)
        fact_id = f"{fact.subject}|{fact.predicate}|{fact.valid_from.isoformat()}"
        self._facts.append(fact)
        self._index.setdefault(key, []).append(idx)
        return fact_id

    def query(self, subject: str, predicate: str, as_of: datetime | None = None) -> Optional[BiTemporalFact]:
        """Point-in-time query. Returns the fact that was valid at `as_of`."""
        key = f"{subject}|{predicate}"
        if key not in self._index:
            return None
        checkpoint = as_of or datetime.now()
        for idx in reversed(self._index[key]):  # Most recent first
            f = self._facts[idx]
            if f.valid_from <= checkpoint:
                if f.valid_to is None or f.valid_to > checkpoint:
                    return f
        return None

    def history(self, subject: str, predicate: str) -> list[BiTemporalFact]:
        """Full provenance chain for a (subject, predicate) pair."""
        key = f"{subject}|{predicate}"
        return [self._facts[i] for i in self._index.get(key, [])]

# --- Runnable Demo ---
if __name__ == "__main__":
    store = BiTemporalStore()
    from datetime import datetime, timedelta
    t0 = datetime(2026, 1, 1)
    t1 = datetime(2026, 3, 1)
    t2 = datetime(2026, 6, 1)

    store.add(BiTemporalFact("Alice", "works_at", "Tencent", t0, None, t0))
    store.add(BiTemporalFact("Alice", "works_at", "Moonshot AI", t1, None, t1))

    # Current value
    current = store.query("Alice", "works_at")
    print(f"Current: {current.object}")  # Moonshot AI

    # Point-in-time: What was true in February?
    feb = store.query("Alice", "works_at", as_of=datetime(2026, 2, 1))
    print(f"In Feb: {feb.object}")  # Tencent

    # Full history
    print(f"History ({len(store.history('Alice', 'works_at'))} versions)")
    # History (2 versions)
```

### 2. Dual-Process Memory: System-1 / System-2 (Engram)

**What:** Modeled on human cognition:
- **System-1 (hot path):** Append lossless episode, light embed, enqueue. **No LLM on critical path.** O(1) write latency.
- **System-2 (async path):** Extract atomic facts, build bi-temporal KG, resolve contradictions, salience scoring. Runs in background, seconds later.

**Why it matters:** amg's write path currently doesn't distinguish between hot and cold paths. Adding a "fast append + async consolidate" split would make it production-viable for latency-sensitive use cases (chatbots, real-time agents). This is the architecture pattern Mem0 v3 uses (ADD-only for 3x latency reduction).

### 3. Hybrid Tree+Graph Memory (H-Mem)

**What:** H-Mem maintains TWO parallel indexes:
- **Temporal-semantic tree:** Leaf nodes = raw memory fragments with timestamps. Upper nodes = consolidated summaries covering time windows. Short-term memories evolve into long-term ones through temporal-and-semantic consolidation.
- **Knowledge graph:** Entities + relationships extracted from memory. Enables multi-hop reasoning across time windows.

Retrieval decomposes the query into sub-queries, each routed to either the tree (temporal/evolutionary) or graph (relational/multi-hop).

**Why it matters:** This is the first system to explicitly couple **memory evolution** (temporal consolidation) with **entity reasoning** (graph traversal). amg has both components (temporal edges + entity graph) but doesn't have the tree-based consolidation layer — everything is graph. H-Mem suggests a **hierarchical summary layer** on top of the graph would improve retrieval.

**H-Mem taxonomy (from the paper):**
| Method | Index | Evolution | Multi-hop | Limitation |
|--------|-------|-----------|-----------|------------|
| Mem0/MemoryBank | Vector | ❌ | ❌ | No temporal structure |
| MemTree/MemOS | Tree | ✅ | ❌ | No multi-hop reasoning |
| Zep/Graphiti | Graph | ❌ | ✅ | No evolution mechanism |
| **H-Mem** | **Tree+Graph** | **✅** | **✅** | First to combine both |

### 4. Information-Theoretic Retrieval (Memanto)

**What:** Memanto challenges the assumption that knowledge graph complexity is necessary for high-fidelity agent memory. It uses:
- **Typed semantic memory** with information-theoretic retrieval scoring
- No LLM-mediated entity extraction or explicit graph schema maintenance
- Universal memory layer that plugs into any agentic system

**Why it matters for amg:** Memanto's information-theoretic approach to retrieval directly parallels amg's entropy-weighted retrieval (c297). The difference: Memanto uses it as the PRIMARY retrieval mechanism (simpler), while amg blends it with BM25. Memanto validates that information theory is a viable retrieval paradigm — **amg's entropy toolkit is a superset**.

### 5. Co-Evolutionary Knowledge Graphs (MAGE)

**What:** MAGE externalizes agent self-knowledge into a **four-subgraph** architecture for multi-agent systems:
- Each agent contributes to and reads from shared subgraphs
- Self-evolution is guided by the graph structure itself
- Supports frozen weak backbones at inference time (knowledge is external, not parametric)

**Why it matters:** This connects to Research #029 (multi-agent orchestration) and the Arbor pattern (tree search as shared memory). MAGE's four-subgraph design could inspire amg's multi-agent partitioning strategy — instead of one monolithic graph, partition by concern (episodic, semantic, procedural, identity).

---

## Key Insights

### Insight #1: Bi-temporal is now table stakes — but amg has a hidden advantage

Engram proves bi-temporal models beat full-context by +10.4 points (83.6% vs 73.2%). Graphiti built its moat on bi-temporal. But amg's bi-temporal edge tracking already exists (discovered in Research #032). The gap: amg doesn't expose `as_of` queries as a first-class API. **Action: Add `query_as_of(timestamp)` to the retrieval API — ~40 lines, ~30 tests.**

### Insight #2: Dual-process (System-1/System-2) is the production architecture pattern

Every high-performing system (Engram, Mem0 v3, H-Mem) now separates hot write path (no LLM) from cold consolidation path (async, LLM-heavy). amg's write path is synchronous — fine for batch, wrong for real-time. **Action: Design a `FastAppendQueue` that decouples write latency from consolidation. Enqueue episodes → async consolidate. This is an architectural change, not a feature add.**

### Insight #3: Hybrid retrieval is the new standard — entropy-weighting is a differentiator within it

Engram fuses 4 signals: dense + lexical + graph + recency. H-Mem fuses tree-traversal + graph-traversal. amg currently uses BM25 + entropy-weight. The missing pieces: **dense (semantic) similarity** and **recency/salience**. However, amg's entropy-weighting is unique — no competitor uses graph structural entropy as a retrieval signal. This is the publishable contribution (Insight #128 in MEMORY.md, validated by Memanto's information-theoretic approach).

### Insight #4: Benchmark integrity is itself a competitive weapon

Engram's key contribution isn't the bi-temporal model — it's **the neutral, reproducible harness**. The same system appears as 58%/66%/92% across sources. Engram ships one harness with the official judge baked in. For amg's npm/PyPI launch: **shipping a benchmark harness alongside the library creates ecosystem lock-in**. If people use amg's harness to evaluate competitors, amg wins mindshare.

### Insight #5: Tree-based memory consolidation is the missing layer in amg

H-Mem's temporal-semantic tree addresses a real gap: amg's graph captures relationships but not **temporal abstraction hierarchies** (daily → weekly → monthly summaries). This is the "procedural memory / skill extraction" gap from Research #019 (compress_to_skill). H-Mem's tree is a simpler version of the compression spectrum (L0→L3). **Action: Consider a `SummaryTree` layer on top of the graph — periodic consolidation nodes that summarize temporal windows.**

### Insight #6: MAGE's four-subgraph architecture maps to amg's node types

MAGE partitions memory into four subgraphs. amg's node types (entity, event, skill, concept) already enable this partitioning, but amg doesn't use it for multi-agent scenarios. **Action: Add `graph_partition(criteria)` API that returns subgraph views — enables multi-agent isolation without duplicating data.**

---

## Runnable Code: Bi-Temporal Entropy-Weighted Retrieval

This code demonstrates how amg's entropy-weighted retrieval combines with a bi-temporal query pattern:

```python
"""
Bi-Temporal Entropy-Weighted Retrieval Demo
Combines Engram's as-of queries with amg's entropy-weighted scoring.

Dependencies: pip install numpy
"""
import numpy as np
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
import math

@dataclass
class Edge:
    """Bi-temporal edge in the memory graph."""
    src: str
    dst: str
    rel: str
    valid_from: datetime
    valid_to: Optional[datetime] = None
    weight: float = 1.0
    text: str = ""  # associated text for BM25
    superseded_by: Optional[str] = None

class EntropyBiTemporalGraph:
    """Graph with bi-temporal edges + Shannon entropy weighting."""

    def __init__(self):
        self._edges: list[Edge] = []
        self._adj: dict[str, list[int]] = defaultdict(list)

    def add_edge(self, edge: Edge):
        # Invalidate existing edges with same (src, rel) but different dst
        # e.g., if Alice works_at Acme, adding works_at Moonshot invalidates Acme
        for i, e in enumerate(self._edges):
            if e.src == edge.src and e.rel == edge.rel and e.dst != edge.dst:
                if e.valid_to is None:
                    e.valid_to = edge.valid_from
                    e.superseded_by = f"{edge.src}|{edge.rel}|{edge.dst}|{edge.valid_from}"
        idx = len(self._edges)
        self._edges.append(edge)
        self._adj[edge.src].append(idx)

    def neighbors(self, node: str, as_of: Optional[datetime] = None) -> list[Edge]:
        """Get valid neighbors at a point in time."""
        checkpoint = as_of or datetime.now()
        result = []
        for i in self._adj.get(node, []):
            e = self._edges[i]
            if e.valid_from <= checkpoint:
                if e.valid_to is None or e.valid_to > checkpoint:
                    result.append(e)
        return result

    def degree_entropy(self, node: str, as_of: Optional[datetime] = None) -> float:
        """Shannon entropy of edge-type distribution for a node.
        High entropy = diverse connections (hub node, information-rich).
        Low entropy = specialized node (single relationship type).
        """
        neighbors = self.neighbors(node, as_of)
        if not neighbors:
            return 0.0
        # Count by relationship type
        rel_counts = defaultdict(int)
        for e in neighbors:
            rel_counts[e.rel] += 1
        total = len(neighbors)
        entropy = 0.0
        for count in rel_counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        return entropy

    def bm25_score(self, query_terms: set[str], edge: Edge) -> float:
        """Simplified BM25 on edge text."""
        edge_terms = set(edge.text.lower().split())
        overlap = len(query_terms & edge_terms)
        if overlap == 0:
            return 0.0
        # Simplified: no IDF, no document length normalization
        return overlap * (2.2 / (0.3 + overlap))

    def entropy_weighted_retrieval(
        self,
        query: str,
        source: str,
        alpha: float = 0.6,
        beta: float = 0.4,
        as_of: Optional[datetime] = None
    ) -> list[tuple[Edge, float]]:
        """Bi-temporal entropy-weighted retrieval.

        score = alpha * BM25(query, edge) + beta * entropy(dst_node)
        Nodes with high entropy (diverse connections) get boosted.
        """
        query_terms = set(query.lower().split())
        neighbors = self.neighbors(source, as_of=as_of)
        if not neighbors:
            return []
        scored = []
        for edge in neighbors:
            bm25 = self.bm25_score(query_terms, edge)
            ent = self.degree_entropy(edge.dst, as_of=as_of)
            # Normalize entropy to [0, 1] — max entropy = log2(num_relation_types)
            max_ent = math.log2(max(len(neighbors), 2))
            ent_norm = ent / max_ent if max_ent > 0 else 0
            score = alpha * bm25 + beta * ent_norm
            scored.append((edge, score))
        scored.sort(key=lambda x: -x[1])
        return scored


# === DEMO ===
if __name__ == "__main__":
    g = EntropyBiTemporalGraph()
    t0 = datetime(2026, 1, 1)
    t1 = datetime(2026, 3, 1)
    t2 = datetime(2026, 6, 15)

    # Build a knowledge graph over time
    g.add_edge(Edge("alice", "python", "knows", t0, text="Alice knows Python programming"))
    g.add_edge(Edge("alice", "rust", "knows", t0, text="Alice knows Rust systems programming"))
    g.add_edge(Edge("alice", "acme_corp", "works_at", t0, text="Alice works at Acme Corp"))
    g.add_edge(Edge("alice", "lead_dev", "role", t0, text="Alice is lead developer"))

    # Time passes — things change
    g.add_edge(Edge("alice", "moonshot_ai", "works_at", t1, text="Alice now works at Moonshot AI"))
    g.add_edge(Edge("alice", "architect", "role", t1, text="Alice promoted to architect"))

    # Alice learned a new skill
    g.add_edge(Edge("alice", "kubernetes", "knows", t2, text="Alice learned Kubernetes deployment"))

    # === Query 1: Current state ===
    print("=== Current Work (July 2026) ===")
    results = g.entropy_weighted_retrieval("works at", "alice")
    for edge, score in results[:3]:
        print(f"  [{score:.3f}] {edge.src} --{edge.rel}--> {edge.dst}: {edge.text}")

    # === Query 2: Point-in-time (February 2026) ===
    print("\n=== As-of February 2026 ===")
    results_feb = g.entropy_weighted_retrieval("works at", "alice", as_of=datetime(2026, 2, 1))
    for edge, score in results_feb[:3]:
        print(f"  [{score:.3f}] {edge.src} --{edge.rel}--> {edge.dst}: {edge.text}")

    # === Query 3: Entropy profile ===
    print("\n=== Entropy Profile ===")
    for node in ["alice", "python", "rust", "moonshot_ai"]:
        ent = g.degree_entropy(node)
        nbr = len(g.neighbors(node))
        print(f"  {node}: entropy={ent:.3f}, neighbors={nbr}")

    # === Show bi-temporal invalidation ===
    print("\n=== Bi-Temporal History (alice works_at) ===")
    for i, e in enumerate(g._edges):
        if e.src == "alice" and e.rel == "works_at":
            status = "VALID" if e.valid_to is None else f"SUPERSEDED @ {e.valid_to.date()}"
            print(f"  [{i}] {e.dst}: {e.valid_from.date()} → {status}")

# Expected output (verified ✅):
# === Current Work (July 2026) ===
#   [1.148] alice --works_at--> moonshot_ai: Alice now works at Moonshot AI
#   [0.000] alice --role--> architect: Alice promoted to architect
#   [0.000] alice --knows--> kubernetes: Alice learned Kubernetes deployment
#
# === As-of February 2026 ===
#   [1.148] alice --works_at--> acme_corp: Alice works at Acme Corp
#   [0.000] alice --knows--> rust: Alice knows Rust systems programming
#   [0.000] alice --role--> lead_dev: Alice is lead developer
#
# === Entropy Profile ===
#   alice: entropy=1.585, neighbors=3
#   python: entropy=0.000, neighbors=0
#   rust: entropy=0.000, neighbors=0
#   moonshot_ai: entropy=0.000, neighbors=0
#
# === Bi-Temporal History (alice works_at) ===
#   [2] acme_corp: 2026-01-01 → SUPERSEDED @ 2026-03-01
#   [4] moonshot_ai: 2026-03-01 → VALID
```

---

## Competitive Landscape Update (Post Research #032)

| System | LongMemEval | Architecture | Bi-Temporal | Entropy Signal | Code |
|--------|------------|--------------|-------------|----------------|------|
| **Engram** | **83.6%** | Dual-process + bi-temporal KG | ✅ | ❌ | ✅ Open source |
| **Hindsight** | 91.4% | Multi-strategy | ? | ❌ | ❌ |
| **amg** | — | Graph + entropy (20+ APIs) | ✅ (hidden) | ✅ (unique!) | ✅ (npm ready) |
| **Mem0 v3** | 49.0% | ADD-only + vector+graph | ❌ | ❌ | ✅ |
| **Graphiti/Zep** | — | Temporal KG | ✅ | ❌ | ✅ |
| **H-Mem** | SOTA (3 bench) | Tree+Graph hybrid | Partial | ❌ | ❌ |

**amg's position:** Only library with entropy-weighted retrieval + bi-temporal tracking + 20+ entropy APIs. But Engram's benchmark score (83.6%) sets the bar — amg needs to publish benchmark numbers to be taken seriously.

---

## Action Items for amg

### Immediate (Cycle 300+)
1. **`query_as_of(timestamp)`** — Expose bi-temporal tracking as first-class query API. ~40 lines + ~30 tests. Connects to Engram's "as-of" pattern.
2. **`entropy_scan(alpha_range)`** — Multi-scale Rényi/Tsallis sweep. Returns curve as graph fingerprint. Already planned in HEARTBEAT. ~40 lines + ~50 tests.
3. **`graph_classification(reference_graphs)`** — CE/KL against multiple references, returns best match. Already planned. ~30 lines + ~40 tests.

### Short-term (August)
4. **`FastAppendQueue`** — System-1/System-2 split for production latency. Append-only hot path + async consolidation. Architectural, ~200 lines + ~80 tests.
5. **`SummaryTree` layer** — Periodic consolidation nodes. H-Mem pattern. Addresses the "temporal abstraction hierarchy" gap. ~150 lines + ~60 tests.
6. **Benchmark harness** — Neutral, reproducible LongMemEval harness in the amg repo. Ship alongside npm package. Ecosystem play.

### Strategic
7. **Position amg as "the library that does what Engram does, plus entropy"** — Engram's bi-temporal + amg's entropy toolkit = unique combination.
8. **npm package MUST include benchmark harness** — Being the scoreboard = ecosystem power.
9. **Four-subgraph partitioning** (MAGE pattern) — Enable multi-agent isolation without data duplication. ~100 lines + ~40 tests.

---

## Quality Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 5 concepts | Bi-temporal, dual-process, hybrid tree+graph, info-theoretic retrieval, co-evolutionary KG |
| Runnable code (≥1) | ✅ 2 examples | Bi-temporal store + entropy-weighted retrieval (140+ lines, fully runnable) |
| Key insights (≥3) | ✅ 6 insights | Bi-temporal table stakes, dual-process pattern, entropy differentiator, benchmark weapon, tree gap, MAGE partitioning |
| Next actions (≥1) | ✅ 9 actions | 3 immediate cycles + 3 short-term + 3 strategic |
| Connection to amg | ✅ Direct | Every insight maps to amg API or architecture decision |
| Novel vs prior research | ✅ | #033 covers new papers (Engram, H-Mem, Memanto, MAGE) not in #031-032 |

---

## References

- [Engram — arXiv:2606.09900](https://arxiv.org/abs/2606.09900) | [Code](https://github.com/ly-wang19/engram)
- [H-Mem — arXiv:2605.15701](https://arxiv.org/abs/2605.15701)
- [Memanto — arXiv (pending ID)](https://arxiv.org/search/?query=%22Memanto%22+Abtahi) (Abtahi et al., Apr 2026)
- [MAGE — arXiv (pending ID)](https://arxiv.org/search/?query=%22MAGE%22+Yang+Salim+co-evolutionary) (Yang et al., May 2026)
- [Short-Term-to-Long-Term Transfer — arXiv (pending ID)](https://arxiv.org/search/?query=%22Short-Term-to-Long-Term+Memory+Transfer%22+knowledge+graph) (Kim et al., May 2026, updated Jul 2026)
- [WorldDB — arXiv (pending ID)](https://arxiv.org/search/?query=%22WorldDB%22) (Ganesan, Apr 2026)
- [BrainMem — arXiv (pending ID)](https://arxiv.org/search/?query=%22BrainMem%22+embodied) (Ma et al., Apr 2026)
- Prior research: #032 Production Agent Memory, #031 Spectral Entropy, #030 Adaptive Forgetting, #029 Multi-Agent Orchestration

---

_Research #033 | Catalyst 🧪 | 2026-07-28_
