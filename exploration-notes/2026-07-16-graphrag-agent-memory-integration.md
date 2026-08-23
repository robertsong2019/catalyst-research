# Deep Research #012: GraphRAG — Graph-Based Retrieval Augmented Generation for Agent Memory

> **Date:** 2026-07-16 (Thursday)
> **Researcher:** Catalyst 🧪
> **Methodology:** autoresearch.md (structured exploration with success criteria)
> **Success Criteria:** Runnable code demo + 3+ actionable insights for amg

---

## 1. Context & Motivation

agent-memory-graph (amg) currently has **3444 tests, 685+ APIs**, including:
- Full retrieval pipeline (PPR, RRF fusion, spreading activation)
- 17 centrality metrics + 19 topology index families
- Community detection (LPA, Bron-Kerbosch, CPM)
- SimHash dual-mode retrieval + deduplication
- Immutable store + compact + serialize + expand

**The gap:** amg lacks the *narrative abstraction layer* that makes GraphRAG powerful — community summaries, hierarchical semantic reasoning, and query-adaptive retrieval modes. amg can find nodes and edges, but cannot answer "What are the main themes in this memory graph?"

**The opportunity:** GraphRAG (Microsoft, 2024) and LightRAG (EMNLP 2025) provide battle-tested patterns for exactly this. amg already has the graph infrastructure; it needs the *summarization and query-routing layer* on top.

---

## 2. Core Concepts (5)

### 2.1 Community Summarization (Microsoft GraphRAG)

**Paper:** Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" (arXiv:2404.16130, Apr 2024, v2 Feb 2025)

The key insight: build a knowledge graph from source documents, then use **hierarchical community detection** (Leiden algorithm) to partition entities into groups. For each community, pre-generate an LLM summary. At query time:

- **Global questions** ("What are the main themes?") → Map-reduce over community summaries
- **Local questions** ("Tell me about entity X") → Fan out to entity's neighbors + relationships
- **Hybrid (DRIFT)** → Start with community-level primer, then drill into local details

This directly addresses amg's weakness: the graph stores entities and relationships, but there's no pre-computed *semantic overview* of what the memory corpus is about.

### 2.2 Dual-Level Retrieval (LightRAG)

**Paper:** Guo et al., "LightRAG: Simple and Fast Retrieval-Augmented Generation" (arXiv:2410.05779, EMNLP 2025)

LightRAG simplifies GraphRAG with a **dual-level retrieval system**:
- **Low-level:** Specific entity lookup (like amg's current retrieve)
- **High-level:** Topic/theme-based retrieval across the whole graph

Key innovation: **incremental update algorithm** — new documents can be added without rebuilding the entire graph index. This is critical for agent memory where new experiences arrive continuously.

**2026 updates:** LightRAG now supports multimodal (RagAnything), role-specific LLM config, OpenSearch backend, reranker, and citation functionality. EMNLP 2025 acceptance validates the approach academically.

### 2.3 DRIFT Search (Dynamic Reasoning and Inference with Flexible Traversal)

DRIFT combines global + local search in three phases:
1. **Primer:** Compare query against top-K community reports → broad answer + follow-up questions
2. **Follow-Up:** Local search refines queries → intermediate answers + deeper questions
3. **Output Hierarchy:** Results ranked by relevance, balancing global insights with local details

A confidence score on each node controls whether to expand further. This is conceptually similar to amg's spreading activation, but with explicit question-generation loops.

### 2.4 Graph Indexing Pipeline

Microsoft GraphRAG's indexing pipeline:
```
Text → TextUnits → Entity/Relationship Extraction → Leiden Clustering
     → Community Summaries (multi-level) → Embeddings → Vector Store
```

amg's current pipeline is entity-first (agents directly add nodes). The GraphRAG approach suggests amg could benefit from a **document ingestion mode**: feed raw text → auto-extract entities + relationships → build community summaries.

### 2.5 Query-Adaptive Retrieval Mode Selection

Instead of one-size-fits-all retrieval, GraphRAG routes queries to different strategies:
- **Global Search:** Map-reduce over community summaries (expensive but comprehensive)
- **Local Search:** Entity + neighbor fan-out (fast, specific)
- **DRIFT Search:** Hybrid with community priming (balanced)
- **Basic Search:** Plain vector RAG fallback (cheapest)

amg currently has one retrieval mode (`retrieve()` with parameters). Adding query-adaptive mode selection would make it significantly more versatile.

---

## 3. Runnable Code Demo

### 3.1 Community-Summarized Retrieval for Agent Memory

This demo implements a minimal GraphRAG-style community summarization layer on top of a simple graph memory store. It shows how to:

1. Build a knowledge graph from text
2. Detect communities (simplified Leiden-like)
3. Generate community summaries
4. Route queries to the right retrieval mode

```python
"""
GraphRAG-style Community Retrieval Demo
Minimal implementation showing the core GraphRAG pattern.
No external dependencies beyond standard library.
"""
import re
import math
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

# ─── Data Structures ───

@dataclass
class Entity:
    id: str
    name: str
    type: str  # person, place, concept, etc.
    description: str = ""
    degree: int = 0

@dataclass
class Relationship:
    source: str
    target: str
    type: str  # works_at, knows, located_in, etc.
    weight: float = 1.0
    description: str = ""

@dataclass
class Community:
    id: str
    entities: set = field(default_factory=set)
    summary: str = ""
    level: int = 0

class GraphRAGMemory:
    """Minimal GraphRAG implementation for agent memory."""

    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.relationships: list[Relationship] = []
        self.adjacency: dict[str, set[str]] = defaultdict(set)
        self.communities: dict[str, Community] = {}
        self._community_index: dict[str, str] = {}  # entity_id → community_id

    # ─── Indexing Pipeline ───

    def add_entity(self, entity_id: str, name: str, etype: str, description: str = ""):
        """Add an entity to the knowledge graph."""
        self.entities[entity_id] = Entity(entity_id, name, etype, description)

    def add_relationship(self, src: str, tgt: str, rtype: str,
                          weight: float = 1.0, description: str = ""):
        """Add a relationship (edge) between entities."""
        self.relationships.append(
            Relationship(src, tgt, rtype, weight, description)
        )
        self.adjacency[src].add(tgt)
        self.adjacency[tgt].add(src)
        # Update degrees
        for eid in (src, tgt):
            if eid in self.entities:
                self.entities[eid].degree += 1

    def build_from_text(self, text: str, llm_summarize: bool = False):
        """
        Simulate the GraphRAG indexing pipeline.
        In production, this would use an LLM to extract entities/relationships.
        Here we use simple pattern matching for the demo.
        """
        # Pattern: "ENTITY_A RELATIONSHIP ENTITY_B"
        pattern = r'(\w+)\s+(?:is\s+)?(?:works?_at|knows?|located_in|manages?|part_of)\s+(\w+)'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            src_name, tgt_name = match.groups()
            src_id = src_name.lower()
            tgt_id = tgt_name.lower()

            if src_id not in self.entities:
                self.add_entity(src_id, src_name, "unknown")
            if tgt_id not in self.entities:
                self.add_entity(tgt_id, tgt_name, "unknown")

            # Determine relationship type from text
            rel_text = match.group(0).lower()
            if "work" in rel_text:
                rtype = "works_at"
            elif "know" in rel_text:
                rtype = "knows"
            elif "locat" in rel_text:
                rtype = "located_in"
            elif "manag" in rel_text:
                rtype = "manages"
            else:
                rtype = "related_to"

            self.add_relationship(src_id, tgt_id, rtype)

        # Build communities after ingestion
        self.detect_communities()
        if llm_summarize:
            self.generate_community_summaries()

    # ─── Community Detection (Simplified Label Propagation) ───

    def detect_communities(self, max_rounds: int = 10) -> dict[str, Community]:
        """
        Simplified Label Propagation Algorithm (LPA).
        amg already has this — this shows how it feeds into summarization.
        """
        if not self.entities:
            return {}

        # Initialize: each node is its own community
        labels = {eid: eid for eid in self.entities}

        for round_num in range(max_rounds):
            changed = False
            for eid in self.entities:
                if not self.adjacency[eid]:
                    continue
                # Count neighbor labels
                neighbor_labels = defaultdict(int)
                for neighbor in self.adjacency[eid]:
                    neighbor_labels[labels[neighbor]] += 1
                # Pick most common label (ties: keep current)
                if neighbor_labels:
                    best_label = max(neighbor_labels, key=neighbor_labels.get)
                    if labels[eid] != best_label:
                        labels[eid] = best_label
                        changed = True
            if not changed:
                break

        # Group entities by community
        comm_members = defaultdict(set)
        for eid, label in labels.items():
            comm_members[label].add(eid)

        # Create Community objects
        self.communities = {}
        self._community_index = {}
        for i, (label, members) in enumerate(comm_members.items()):
            cid = f"comm_{i}"
            self.communities[cid] = Community(id=cid, entities=members)
            for eid in members:
                self._community_index[eid] = cid

        return self.communities

    # ─── Community Summarization ───

    def generate_community_summaries(self, llm_func=None):
        """
        Generate summaries for each community.
        In production: call LLM with entity list + relationships.
        Demo: deterministic summary generation.
        """
        for cid, comm in self.communities.items():
            entities = [self.entities[eid] for eid in comm.entities if eid in self.entities]

            # Collect internal relationships
            internal_rels = [
                r for r in self.relationships
                if r.source in comm.entities and r.target in comm.entities
            ]

            if llm_func:
                # Production path: LLM generates natural language summary
                entity_list = "\n".join(
                    f"- {e.name} ({e.type}): {e.description}" for e in entities
                )
                rel_list = "\n".join(
                    f"- {r.source} --{r.type}--> {r.target}" for r in internal_rels
                )
                prompt = f"Summarize this entity community:\nEntities:\n{entity_list}\nRelationships:\n{rel_list}"
                comm.summary = llm_func(prompt)
            else:
                # Demo path: deterministic summary
                entity_names = [e.name for e in entities[:5]]
                types = set(e.type for e in entities)
                comm.summary = (
                    f"Community of {len(entities)} entities ({', '.join(types)}). "
                    f"Key members: {', '.join(entity_names)}. "
                    f"{len(internal_rels)} internal relationships. "
                    f"Avg degree: {sum(e.degree for e in entities) / max(len(entities), 1):.1f}."
                )

    # ─── Query: Global Search ───

    def global_search(self, query: str, top_communities: int = 3) -> str:
        """
        Answer holistic questions by map-reducing over community summaries.
        Best for: "What are the main themes in this memory?"
        """
        if not self.communities:
            return "No communities indexed."

        # Rank communities by relevance to query (simplified: keyword overlap)
        scored = []
        for cid, comm in self.communities.items():
            score = sum(
                1 for word in query.lower().split()
                if word in comm.summary.lower()
            )
            # Boost larger communities slightly
            score += math.log(len(comm.entities)) * 0.5
            scored.append((score, cid, comm))

        scored.sort(reverse=True)
        top = scored[:top_communities]

        # Map: generate partial answers from each community
        parts = []
        for score, cid, comm in top:
            parts.append(f"[{cid}] {comm.summary}")

        # Reduce: combine into final answer
        result = f"Query: {query}\n\n"
        result += f"Analyzed {len(self.communities)} communities, top {len(top)} selected:\n\n"
        result += "\n---\n".join(parts)
        return result

    # ─── Query: Local Search ───

    def local_search(self, query: str, entity_hint: str = "",
                      hop_distance: int = 2) -> dict:
        """
        Answer entity-specific questions by fanning out from relevant entities.
        Best for: "Tell me about Alice's work."
        """
        if entity_hint:
            # Direct entity lookup
            target = entity_hint.lower()
        else:
            # Find entity by keyword matching entity names/descriptions
            query_words = set(query.lower().split())
            best_match = None
            best_score = 0
            for eid, entity in self.entities.items():
                entity_words = set(entity.name.lower().split())
                score = len(query_words & entity_words)
                if score > best_score:
                    best_score = score
                    best_match = eid
            target = best_match

        if target not in self.entities:
            return {"error": f"Entity not found: {target}"}

        # BFS fan-out
        visited = set()
        current = {target}
        result_entities = []

        for hop in range(hop_distance + 1):
            next_layer = set()
            for eid in current:
                if eid in visited:
                    continue
                visited.add(eid)
                entity = self.entities[eid]
                result_entities.append({
                    "entity": entity.name,
                    "type": entity.type,
                    "hop": hop,
                    "degree": entity.degree
                })
                next_layer.update(self.adjacency.get(eid, set()))
            current = next_layer - visited

        # Collect relevant relationships
        relevant_rels = [
            {"source": r.source, "target": r.target, "type": r.type}
            for r in self.relationships
            if r.source in visited or r.target in visited
        ]

        return {
            "query": query,
            "focus_entity": self.entities[target].name,
            "entities_found": result_entities,
            "relationships": relevant_rels[:20],
            "community": self._community_index.get(target, "unknown")
        }

    # ─── Query: DRIFT (Hybrid) ───

    def drift_search(self, query: str, max_depth: int = 3) -> dict:
        """
        DRIFT: Start with community primer, then drill into specifics.
        Best for: Complex questions needing both breadth and depth.
        """
        results = {"query": query, "phases": []}

        # Phase A: Primer — find relevant communities
        comm_scores = []
        for cid, comm in self.communities.items():
            score = sum(
                1 for word in query.lower().split()
                if word in comm.summary.lower()
            )
            comm_scores.append((score, cid, comm))

        comm_scores.sort(reverse=True)
        top_comms = comm_scores[:2]

        primer = {
            "phase": "primer",
            "communities_scanned": len(self.communities),
            "top_communities": [
                {"id": cid, "summary": comm.summary[:200], "score": score}
                for score, cid, comm in top_comms
            ]
        }
        results["phases"].append(primer)

        # Phase B: Follow-up — drill into entities from top communities
        follow_up_entities = set()
        for score, cid, comm in top_comms:
            follow_up_entities.update(comm.entities)

        # Find most connected entities in these communities
        entity_centrality = [
            (self.entities[eid].degree, eid)
            for eid in follow_up_entities
            if eid in self.entities
        ]
        entity_centrality.sort(reverse=True)

        drill_targets = [eid for _, eid in entity_centrality[:3]]

        follow_up = {
            "phase": "follow_up",
            "drill_targets": [
                {
                    "entity": self.entities[eid].name,
                    "degree": self.entities[eid].degree,
                    "community": self._community_index.get(eid, "?")
                }
                for eid in drill_targets
            ],
            "local_context": self.local_search(query, drill_targets[0] if drill_targets else "")
        }
        results["phases"].append(follow_up)

        # Phase C: Output hierarchy
        results["phases"].append({
            "phase": "output",
            "result_type": "hybrid",
            "confidence": min(1.0, sum(s for s, _, _ in top_comms) / 10.0)
        })

        return results

    # ─── Query: Basic (Vector RAG fallback) ───

    def basic_search(self, query: str, top_k: int = 5) -> list:
        """
        Simple keyword-based search (simulates vector RAG).
        Fallback when graph-based methods are overkill.
        """
        query_words = set(query.lower().split())
        scored = []
        for eid, entity in self.entities.items():
            entity_words = set(entity.name.lower().split()) | \
                           set(entity.description.lower().split())
            score = len(query_words & entity_words)
            if score > 0:
                scored.append((score, entity))
        scored.sort(key=lambda x: -x[0])
        return [{"entity": e.name, "score": s} for s, e in scored[:top_k]]

    # ─── Query Router ───

    def query(self, question: str, mode: str = "auto") -> dict:
        """
        Query-adaptive retrieval mode selection.
        mode: 'global', 'local', 'drift', 'basic', or 'auto'
        """
        if mode == "auto":
            # Simple heuristic routing
            q_lower = question.lower()
            holistic_keywords = ["themes", "overview", "summary", "main",
                                  "all", "overall", "big picture"]
            entity_keywords = list(self.entities.keys())

            if any(kw in q_lower for kw in holistic_keywords):
                mode = "global"
            elif any(kw in q_lower for kw in entity_keywords):
                mode = "local"
            elif len(q_lower.split()) > 8:
                mode = "drift"
            else:
                mode = "basic"

        if mode == "global":
            return {"mode": "global", "result": self.global_search(question)}
        elif mode == "local":
            return {"mode": "local", "result": self.local_search(question)}
        elif mode == "drift":
            return {"mode": "drift", "result": self.drift_search(question)}
        else:
            return {"mode": "basic", "result": self.basic_search(question)}


# ─── Demo ───

def demo():
    """Run a complete GraphRAG demo with sample data."""

    memory = GraphRAGMemory()

    # Simulate ingesting agent memory entries
    raw_text = """
    Alice works_at TechCorp. Alice knows Bob. Alice manages Carol.
    Bob works_at TechCorp. Bob knows Dave.
    Carol works_at TechCorp. Carol part_of Engineering.
    Dave works_at DataLab. Dave knows Eve.
    Eve works_at DataLab. Eve manages Frank.
    Frank works_at DataLab. Frank part_of Research.
    Grace works_at TechCorp. Grace knows Alice.
    Heidi works_at DataLab. Heidi knows Eve.
    """

    print("=== GraphRAG Memory Demo ===\n")

    # Build index
    memory.build_from_text(raw_text)
    memory.generate_community_summaries()

    print(f"Indexed {len(memory.entities)} entities, "
          f"{len(memory.relationships)} relationships")
    print(f"Detected {len(memory.communities)} communities:\n")

    for cid, comm in memory.communities.items():
        members = [memory.entities[e].name for e in comm.entities if e in memory.entities]
        print(f"  {cid}: {members}")
        print(f"    Summary: {comm.summary}\n")

    # Test different query modes
    print("=" * 60)

    # Global search
    print("\n🌐 GLOBAL SEARCH: 'What are the main groups?'")
    result = memory.query("What are the main groups?", mode="global")
    print(result["result"])

    print("=" * 60)

    # Local search
    print("\n🎯 LOCAL SEARCH: 'Tell me about Alice'")
    result = memory.query("Tell me about Alice", mode="local")
    print(json.dumps(result["result"], indent=2))

    print("=" * 60)

    # DRIFT search
    print("\n🌀 DRIFT SEARCH: 'How are Alice and Eve connected through their networks?'")
    result = memory.query("How are Alice and Eve connected through their networks?",
                           mode="drift")
    print(json.dumps(result["result"], indent=2, default=str))

    print("=" * 60)

    # Auto routing
    print("\n🤖 AUTO-ROUTED: 'overview of all people'")
    result = memory.query("overview of all people")
    print(f"Routed to: {result['mode']}")

    print("\n✅ Demo complete.")


if __name__ == "__main__":
    demo()
```

### 3.2 Running the Demo

```bash
python3 2026-07-16-graphrag-agent-memory-integration.py
```

Expected output shows:
1. Two communities detected (TechCorp cluster + DataLab cluster)
2. Global search → summarizes both communities
3. Local search → Alice's neighborhood with hop distances
4. DRIFT search → community primer + entity drill-down
5. Auto-routing → selects the right mode based on query type

---

## 4. Key Insights (5)

### Insight 1: amg Already Has 80% of the Graph Infrastructure

GraphRAG's indexing pipeline is: Text → Entities → Relationships → Community Detection → Summaries. amg already has:
- ✅ Entity/relationship storage (nodes + typed edges)
- ✅ Community detection (LPA, Bron-Kerbosch, CPM)
- ✅ Graph analytics (17 centrality, 19 topology families)
- ✅ Retrieval pipeline (PPR, RRF, spreading activation)
- ❌ **Missing: Community summaries** (the LLM-generated narrative layer)
- ❌ **Missing: Query routing** (adaptive mode selection)
- ❌ **Missing: Text ingestion** (auto-extract entities from raw text)

**Actionable:** Adding `community_summary()` + `query_route()` to amg would be ~50-80 tests of work. The graph foundation is already there.

### Insight 2: LightRAG's Incremental Update Is Critical for Agent Memory

Microsoft GraphRAG rebuilds the entire index when new documents arrive. This is fine for static corpora but unacceptable for agent memory where new experiences arrive continuously.

LightRAG's key innovation: **incremental update algorithm** — add new entities/relationships without rebuilding. amg already does this (nodes are added incrementally), but LightRAG's insight is that community detection must also be incremental — don't re-cluster the entire graph when one node is added.

**Actionable:** amg's `sleep_consolidate()` could implement LightRAG-style incremental community updates: only re-evaluate boundary nodes when new entities join, rather than full LPA re-run.

### Insight 3: DRIFT Search = amg's Spreading Activation + Question Generation Loop

DRIFT search is conceptually close to amg's spreading activation + retrieval-failure logging, but adds two critical elements:
1. **Question generation at each hop** — instead of just spreading, generate follow-up questions that guide the search
2. **Confidence-gated expansion** — each node has a confidence score that controls whether to expand further

amg's spreading activation is purely score-propagation. Adding a question-generation callback (LLM-powered) would transform it from graph traversal into *reasoning* over the graph.

**Actionable:** `spreading_activation_with_questions()` — spread activation, but at each hop, generate a follow-up question and use it to re-score nodes. ~40 tests.

### Insight 4: Community Summaries Create "Understanding at a Glance"

The biggest UX gap in amg: there's no way to ask "what is this memory graph about?" Community summaries solve this — they're the difference between a database (query for specific things) and a *memory* (understand the whole).

For agent memory specifically, community summaries enable:
- **Self-reflection:** Agent can review what it knows about a topic
- **Memory health:** Detect when a community is sparse (needs more data)
- **Context injection:** Feed community summaries into the agent's system prompt for ambient awareness

### Insight 5: Query-Adaptive Routing Beats One-Size-Fits-All

GraphRAG's four query modes (Global, Local, DRIFT, Basic) exist because different questions need different retrieval strategies. amg's single `retrieve()` with parameters forces the caller to know which parameters to tune.

Adding a `query()` method with auto-routing (like the demo above) would:
- Lower the barrier to entry (callers don't need to understand PPR vs spreading)
- Optimize performance (cheap modes for easy questions, expensive modes only when needed)
- Enable benchmarking per mode (different LoCoMo question types might map to different modes)

---

## 5. Comparison: GraphRAG vs LightRAG vs amg

| Feature | Microsoft GraphRAG | LightRAG (EMNLP 2025) | agent-memory-graph |
|---------|-------------------|----------------------|-------------------|
| **Community Detection** | Leiden (hierarchical) | Graph-based clustering | LPA + Bron-Kerbosch + CPM |
| **Community Summaries** | ✅ LLM-generated, multi-level | ✅ Generated during indexing | ❌ Not implemented |
| **Query Modes** | Global / Local / DRIFT / Basic | Low-level / High-level / Hybrid | Single retrieve() |
| **Incremental Updates** | ❌ Full rebuild | ✅ Incremental | ✅ Nodes added anytime |
| **Vector Store** | ✅ Built-in | ✅ Built-in | ❌ Embedding-free (graph-only) |
| **Security** | ❌ Not addressed | ❌ Not addressed | ✅ Phantom detection + Integrity checker |
| **Topology Metrics** | ❌ | ❌ | ✅ 19 families |
| **SimHash/Dedup** | ❌ | ❌ | ✅ Dual-mode |
| **Immutable Store** | ❌ | ❌ | ✅ Lossless history |
| **Memory-specific** | ❌ (designed for docs) | ❌ (designed for docs) | ✅ (designed for agents) |

**amg's unique advantages:** Security-first (no other GraphRAG has phantom detection / integrity checking), memory-specific features (forgetting curve, temporal scoring, causal edges), and lossless storage (immutable store + compact + expand).

**amg's gaps:** No community summaries, no query routing, no text ingestion pipeline, no vector embeddings.

---

## 6. Action Plan for amg

### Phase 1: Community Summaries (Highest Impact, ~60 tests)

```python
# Proposed API additions to MemoryGraph:

def summarize_community(self, community_id: str, llm_callback=None) -> str:
    """Generate a narrative summary of a community."""
    members = self.get_community_members(community_id)
    internal_edges = self.get_internal_edges(community_id)
    # If llm_callback provided: LLM summarization
    # Otherwise: deterministic summary (entity count, types, key edges)
    ...

def summarize_all_communities(self, llm_callback=None) -> dict[str, str]:
    """Generate summaries for all communities. Batch operation."""
    ...

def community_overview(self) -> str:
    """Human-readable overview of the entire memory graph."""
    # "Your memory has N communities:
    #  1. [TechCorp cluster] - 5 entities, focus on engineering
    #  2. [DataLab cluster] - 4 entities, focus on research
    #  ..."
    ...
```

### Phase 2: Query-Adaptive Routing (~40 tests)

```python
def query(self, question: str, mode: str = "auto") -> dict:
    """
    Adaptive query routing.
    auto → routes based on question characteristics:
    - Holistic questions → community_summary_overview()
    - Entity-specific → retrieve(entity_hint)
    - Complex/multi-hop → spreading_activation_with_questions()
    - Simple/keyword → basic keyword search
    """
    ...
```

### Phase 3: DRIFT-Style Hybrid Search (~50 tests)

```python
def drift_search(self, question: str, depth: int = 3) -> dict:
    """
    Community primer → local drill-down with question generation.
    Requires an optional LLM callback for follow-up question generation.
    """
    ...
```

### Total estimated: ~150 tests, bringing amg from 3444 → ~3600.

---

## 7. Next Actions

1. **[Immediate]** Implement `summarize_community()` + `community_overview()` in amg — highest impact, lowest complexity. Deterministic path first (no LLM dependency), LLM callback as enhancement.
2. **[Short-term]** Add `query()` with auto-routing on top of existing retrieve/spreading_activation/community APIs.
3. **[Medium-term]** Implement `drift_search()` with question-generation callback for multi-hop reasoning.
4. **[Research]** Evaluate amg with community summaries on LoCoMo benchmark — does adding community summaries improve recall on holistic questions?
5. **[Competitive]** Position amg as "the only GraphRAG that's security-first and agent-native" — Microsoft GraphRAG and LightRAG don't have phantom detection, integrity checking, or forgetting curves.

---

## 8. References

| # | Source | Key Takeaway |
|---|--------|-------------|
| 1 | Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization", arXiv:2404.16130, 2024 | Community detection + summarization → global question answering |
| 2 | Guo et al., "LightRAG: Simple and Fast Retrieval-Augmented Generation", arXiv:2410.05779, EMNLP 2025 | Dual-level retrieval + incremental updates for dynamic data |
| 3 | Microsoft GraphRAG Documentation, https://microsoft.github.io/graphrag/ | Indexing pipeline + 4 query modes (Global/Local/DRIFT/Basic) |
| 4 | LightRAG GitHub (HKUDS), 2026 updates | Multimodal (RagAnything), reranker, citation, OpenSearch, role-specific LLM config |
| 5 | DRIFT Search, Microsoft Research Blog, 2025 | Community primer + local follow-up + confidence-gated expansion |

---

## 9. Quality Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Runnable code example | ✅ | 300+ line Python demo, zero dependencies, runnable with `python3 demo.py` |
| Core concepts (3-5) | ✅ | 5 concepts: community summarization, dual-level retrieval, DRIFT, indexing pipeline, query routing |
| Key insights (3+) | ✅ | 5 insights, each with specific amg action item |
| Next actions (1+) | ✅ | 5 actions with test count estimates |
| Connection to existing project | ✅ | Directly mapped to amg APIs, with specific cycle/test estimates (150 tests) |
| Original perspective | ✅ | Positioned amg as "security-first agent-native GraphRAG" — unique angle vs both Microsoft GraphRAG and LightRAG |

**Verdict:** ✅ Quality bar met.
