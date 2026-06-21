# Temporal Knowledge Graphs for Agent Memory: Time-Aware Retrieval, Fact Lifecycle & Evolution

> Research Note — 2026-06-21 Evening
> Topic: How temporal knowledge graphs (TKGs) transform agent memory from flat accumulation to evolving state
- Sources: 8 papers/systems synthesized

---

## Executive Summary

Agent memory systems face a fundamental problem: **facts change**. Users change jobs, preferences shift, policies update, organizations restructure. Traditional vector stores and static knowledge graphs treat all facts as eternally true — they accumulate but don't evolve. **Temporal Knowledge Graphs (TKGs)** solve this by attaching validity intervals to every edge, enabling time-travel queries, automatic fact invalidation, and contradiction resolution without data loss.

This note synthesizes the state-of-the-art in TKG-based agent memory (Zep/Graphiti, RoMem, ATOM, CIK-LLM, TREK, memory-engine) and provides a runnable TypeScript implementation of bi-temporal edge lifecycle management — the core primitive that differentiates temporal graphs from static ones.

---

## Core Concepts

### 1. Bi-Temporal Model: Two Timelines, Four Timestamps

The foundational insight from Zep (arXiv:2501.13956, 212 citations) and the graph-based agent memory taxonomy (arXiv:2602.05665):

**Every edge carries two independent timelines:**

| Timeline | Fields | Meaning |
|----------|--------|---------|
| **Valid Time (T)** | `t_valid_start`, `t_valid_end` | When the fact was true in the real world |
| **Transaction Time (T')** | `t_created`, `t_invalidated` | When the system learned/forgot the fact |

This separation enables:
- "What did we know on March 15?" (transaction-time query)
- "Where did the user live in 2024?" (valid-time query)
- "When did we learn the user moved?" (provenance query)

Zep calls this the **bi-temporal model**. The Missing Knowledge Layer paper (arXiv:2604.11364) implements "four timestamps per fact" in a Rust memory-engine. Graphiti's `valid_from`/`valid_until` on every edge is the production standard.

**Key distinction from simple timestamping:** A fact learned at t=5 might describe an event at t=3. Without bi-temporal modeling, you conflate "when we heard it" with "when it happened."

### 2. Fact Invalidation Lifecycle: Don't Delete, Invalidate

When new information contradicts existing facts, the system doesn't overwrite — it **invalidates**:

```
State before: (Alice) --[works_at→TechCorp, valid: 2024-01..∞]--> (TechCorp)
New episode: "Alice joined DataCorp on 2026-06-01"
State after:
  (Alice) --[works_at→TechCorp, valid: 2024-01..2026-06-01, INVALIDATED]--> (TechCorp)
  (Alice) --[works_at→DataCorp, valid: 2026-06-01..∞, CURRENT]--> (DataCorp)
```

Zep's Graphiti implements this via an LLM-driven contradiction detector: when a new edge is added, semantically related existing edges are compared, and overlapping contradictions are invalidated by setting `t_invalid = t_valid_new`.

ATOM (EACL 2026, arXiv:2510.22590) preprocesses this during extraction: "John Doe is no longer CEO" is transformed into `(John_Doe, is_ceo, X, [start], [01-01-2026])` — the end-validity is encoded directly in the tuple.

### 3. Relational Volatility: Not All Facts Age Equally

RoMem (arXiv:2604.11544) introduces the **Semantic Speed Gate** — a pretrained module that maps relation text embeddings to volatility scores:

| Relation | Volatility | Rotation Speed |
|----------|-----------|---------------|
| "born in" | Near-zero | Static — never rotates |
| "ceo of" | High | Fast rotation |
| "lives in" | Medium | Moderate rotation |
| "prefers" | Variable | Learned from data |

This solves the **static-dynamic dilemma**: recency sorting buries permanent facts ("born in Paris") under evolving ones ("currently likes Adidas"), while uniform overwriting loses history. RoMem uses **continuous phase rotation** in complex vector space — obsolete facts are geometrically "shadowed" (rotated out of phase) so current facts naturally outrank them without deletion.

**Results:** SOTA on ICEWS05-15 (72.6 MRR), 2-3× MRR improvement on temporal reasoning (MultiTQ), zero degradation on static memory (DMR-MSC), zero-shot generalization to financial domains (FinTMMBench 0.728 MRR).

### 4. Hybrid Retrieval: Graph + Vector + BM25 + Temporal Filter

All production TKG systems converge on the same retrieval architecture:

1. **Semantic search** (vector) — find candidate entities/edges by embedding similarity
2. **BM25** (lexical) — keyword-precision complement
3. **Graph traversal** — multi-hop expansion from seed entities
4. **Temporal filter** — only edges where `t_valid_start ≤ query_time < t_valid_end`

Zep reports sub-200ms p95 latency with this stack. The critical insight: **no LLM calls at query time** — all intelligence is in the graph structure and pre-computed embeddings.

CIK-LLM (CoLLAs 2024) demonstrates that a frozen LLM + TKG with subgraph extraction matches fine-tuned models on temporal QA, validating the "storage ≠ reasoning" separation.

### 5. Three-Tier Subgraph Hierarchy

Zep's architecture mirrors human cognitive memory:

| Tier | Content | Analogy |
|------|---------|---------|
| **Episode subgraph** | Raw interaction records with timestamps | Episodic memory |
| **Semantic entity subgraph** | Extracted entities + facts with validity | Semantic memory |
| **Community subgraph** | Clustered entity groups + summaries | Schemas / mental models |

The Missing Knowledge Layer paper extends this with a **Wisdom layer** — procedural skills distilled from experience, following Ebbinghaus forgetting curves with configurable half-lives.

---

## Runnable Code: Bi-Temporal Edge Lifecycle Manager

```typescript
/**
 * Bi-Temporal Edge Lifecycle Manager
 * 
 * Demonstrates the core primitives of temporal knowledge graphs:
 * - Edges with validity intervals (t_valid_start, t_valid_end)
 * - Transaction-time tracking (t_created, t_invalidated)
 * - Fact invalidation (not deletion) on contradiction
 * - Time-travel queries (as-of-date retrieval)
 * - Current-state retrieval (only valid facts)
 * 
 * Inspired by: Zep (arXiv:2501.13956), ATOM (EACL 2026), RoMem (arXiv:2604.11544)
 * 
 * Zero dependencies. Production-grade concepts in ~200 lines.
 */

// ─── Types ───────────────────────────────────────────────

interface TemporalEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  
  // Valid time (T): when the fact is true in the real world
  valid_from: number;    // epoch ms
  valid_until: number | null;  // null = still valid (open interval)
  
  // Transaction time (T'): when the system recorded this
  recorded_at: number;   // epoch ms
  invalidated_at: number | null;  // when we learned this was wrong
  
  // Provenance
  episode_id: string;    // which interaction produced this fact
  invalidated_by: string | null;  // which edge superseded this one
  
  // Metadata
  confidence: number;    // 0-1, from extraction
  properties: Record<string, unknown>;
}

interface Episode {
  id: string;
  content: string;
  timestamp: number;
  source: 'chat' | 'document' | 'structured' | 'inferred';
}

// ─── Bi-Temporal Graph ───────────────────────────────────

class BiTemporalGraph {
  private edges: Map<string, TemporalEdge> = new Map();
  private episodes: Map<string, Episode> = new Map();
  private edgeCounter = 0;
  
  /** Record an episode and return its ID */
  recordEpisode(content: string, timestamp: number = Date.now(), 
                source: Episode['source'] = 'chat'): string {
    const id = `ep_${this.episodes.size}_${timestamp}`;
    this.episodes.set(id, { id, content, timestamp, source });
    return id;
  }
  
  /** Add a fact (temporal edge) to the graph */
  addFact(params: {
    source: string;
    target: string;
    relation: string;
    valid_from?: number;
    valid_until?: number | null;
    recorded_at?: number;  // Override for testing (defaults to now)
    episode_id: string;
    confidence?: number;
    properties?: Record<string, unknown>;
  }): string {
    const now = params.recorded_at ?? Date.now();
    const id = `e_${++this.edgeCounter}`;
    
    const edge: TemporalEdge = {
      id,
      source: params.source,
      target: params.target,
      relation: params.relation,
      valid_from: params.valid_from ?? now,
      valid_until: params.valid_until ?? null,
      recorded_at: now,
      invalidated_at: null,
      episode_id: params.episode_id,
      invalidated_by: null,
      confidence: params.confidence ?? 1.0,
      properties: params.properties ?? {},
    };
    
    this.edges.set(id, edge);
    
    // Auto-invalidate contradictory edges
    this.invalidateContradictions(edge);
    
    return id;
  }
  
  /**
   * Find and invalidate edges that contradict the new edge.
   * Two edges contradict if: same (source, relation, target_pattern)
   * and overlapping validity intervals.
   * 
   * Simplified: invalidates same (source, relation) with open/overlapping valid_until.
   * Production systems (Graphiti) use LLM-based semantic comparison.
   */
  private invalidateContradictions(newEdge: TemporalEdge): number {
    let invalidated = 0;
    
    for (const edge of this.edges.values()) {
      // Skip self
      if (edge.id === newEdge.id) continue;
      // Skip already invalidated
      if (edge.invalidated_at !== null) continue;
      // Must be same source + relation (simplified matching)
      if (edge.source !== newEdge.source) continue;
      if (edge.relation !== newEdge.relation) continue;
      // Same target OR one of them is a different entity (contradiction)
      // In production: use embedding similarity + LLM judgment
      if (edge.target === newEdge.target) continue; // same fact, skip
      
      // Check validity overlap
      const edgeEnd = edge.valid_until ?? Infinity;
      const newEnd = newEdge.valid_until ?? Infinity;
      const overlaps = edge.valid_from < newEnd && newEdge.valid_from < edgeEnd;
      
      if (overlaps) {
        // Invalidate the old edge
        edge.invalidated_at = now();
        edge.valid_until = newEdge.valid_from;  // close its validity
        edge.invalidated_by = newEdge.id;
        invalidated++;
      }
    }
    
    return invalidated;
  }
  
  /** Query: What facts are currently valid? */
  currentFacts(entityId?: string, relation?: string): TemporalEdge[] {
    const now_ = Date.now();
    return this.queryAt(now_, entityId, relation);
  }
  
  /** Query: What was true at time T? (time-travel query) */
  queryAt(timestamp: number, entityId?: string, relation?: string): TemporalEdge[] {
    const results: TemporalEdge[] = [];
    
    for (const edge of this.edges.values()) {
      // Must have been recorded before or at the query time
      if (edge.recorded_at > timestamp) continue;
      // Must not have been invalidated before the query time
      if (edge.invalidated_at !== null && edge.invalidated_at <= timestamp) continue;
      // Validity interval must contain the query time
      if (edge.valid_from > timestamp) continue;
      const validEnd = edge.valid_until ?? Infinity;
      if (validEnd <= timestamp) continue;
      
      // Optional filters
      if (entityId && edge.source !== entityId && edge.target !== entityId) continue;
      if (relation && edge.relation !== relation) continue;
      
      results.push(edge);
    }
    
    return results;
  }
  
  /** Query: Full history of a relationship (all versions) */
  history(entityId: string, relation?: string): TemporalEdge[] {
    return [...this.edges.values()]
      .filter(e => e.source === entityId && (!relation || e.relation === relation))
      .sort((a, b) => a.valid_from - b.valid_from);
  }
  
  /** Query: When did we learn X? (provenance/audit trail) */
  provenance(edgeId: string): { edge: TemporalEdge; episode: Episode | undefined }[] {
    const chain: { edge: TemporalEdge; episode: Episode | undefined }[] = [];
    let current = this.edges.get(edgeId);
    
    while (current) {
      chain.push({
        edge: current,
        episode: this.episodes.get(current.episode_id),
      });
      current = current.invalidated_by ? this.edges.get(current.invalidated_by) : undefined;
    }
    
    return chain;
  }
  
  /** Stats */
  stats() {
    let valid = 0, invalidated = 0;
    for (const e of this.edges.values()) {
      if (e.invalidated_at === null) valid++;
      else invalidated++;
    }
    return {
      total_edges: this.edges.size,
      valid_edges: valid,
      invalidated_edges: invalidated,
      episodes: this.episodes.size,
    };
  }
  
  /** Export as JSON (for serialization/persistence) */
  export(): { edges: TemporalEdge[]; episodes: Episode[] } {
    return {
      edges: [...this.edges.values()],
      episodes: [...this.episodes.values()],
    };
  }
}

// ─── Demo & Tests ────────────────────────────────────────

function now() { return Date.now(); }

function daysAgo(days: number): number {
  return Date.now() - days * 86_400_000;
}

function dateFrom(d: string): number {
  return new Date(d).getTime();
}

// Helper to format dates for display
function fmt(ts: number): string {
  return new Date(ts).toISOString().split('T')[0]!;
}

// ─── Test Suite ──────────────────────────────────────────

function assert(cond: boolean, msg: string): void {
  if (!cond) throw new Error(`FAIL: ${msg}`);
  console.log(`  ✅ ${msg}`);
}

function runTests(): void {
  console.log('\n🧪 Bi-Temporal Graph Tests\n');
  
  // Test 1: Basic fact addition and current-state query
  console.log('Test 1: Basic fact lifecycle');
  const graph = new BiTemporalGraph();
  
  const ep1 = graph.recordEpisode("I live in Barcelona", dateFrom("2024-03-15"));
  graph.addFact({
    source: "user:alice",
    target: "Barcelona",
    relation: "lives_in",
    valid_from: dateFrom("2024-03-15"),
    recorded_at: dateFrom("2024-03-15"),
    episode_id: ep1,
  });
  
  let current = graph.currentFacts("user:alice", "lives_in");
  assert(current.length === 1, "One current 'lives_in' fact for Alice");
  assert(current[0]!.target === "Barcelona", "Alice currently lives in Barcelona");
  
  // Test 2: Fact invalidation (not deletion)
  console.log('\nTest 2: Fact invalidation on contradiction');
  const ep2 = graph.recordEpisode("I just moved to Madrid!", dateFrom("2026-05-01"));
  graph.addFact({
    source: "user:alice",
    target: "Madrid",
    relation: "lives_in",
    valid_from: dateFrom("2026-05-01"),
    recorded_at: dateFrom("2026-05-01"),
    episode_id: ep2,
  });
  
  current = graph.currentFacts("user:alice", "lives_in");
  assert(current.length === 1, "Still one current 'lives_in' fact (not two)");
  assert(current[0]!.target === "Madrid", "Alice now lives in Madrid (current)");
  
  // Test 3: Time-travel query
  console.log('\nTest 3: Time-travel query');
  const pastFacts = graph.queryAt(dateFrom("2025-06-01"), "user:alice", "lives_in");
  assert(pastFacts.length === 1, "One 'lives_in' fact valid in June 2025");
  assert(pastFacts[0]!.target === "Barcelona", "In June 2025, Alice lived in Barcelona");
  
  const futureFacts = graph.queryAt(dateFrom("2026-10-01"), "user:alice", "lives_in");
  assert(futureFacts.length === 1, "One 'lives_in' fact valid in Oct 2026");
  assert(futureFacts[0]!.target === "Madrid", "In Oct 2026, Alice lives in Madrid");
  
  // Test 4: History (all versions)
  console.log('\nTest 4: Full relationship history');
  const history = graph.history("user:alice", "lives_in");
  assert(history.length === 2, "Two versions of 'lives_in' in history");
  assert(history[0]!.target === "Barcelona", "First version: Barcelona");
  assert(history[1]!.target === "Madrid", "Second version: Madrid");
  assert(history[0]!.invalidated_at !== null, "Barcelona fact is invalidated");
  assert(history[1]!.invalidated_at === null, "Madrid fact is current");
  
  // Test 5: Provenance chain
  console.log('\nTest 5: Provenance / audit trail');
  const prov = graph.provenance(history[0]!.id);
  assert(prov.length === 2, "Provenance chain has 2 hops");
  assert(prov[0]!.edge.target === "Barcelona", "Chain starts with Barcelona");
  assert(prov[1]!.edge.target === "Madrid", "Chain links to Madrid");
  assert(prov[0]!.episode!.content === "I live in Barcelona", 
         "Source episode content preserved");
  
  // Test 6: Stats and export
  console.log('\nTest 6: Stats and export');
  const stats = graph.stats();
  assert(stats.total_edges === 2, "Total 2 edges in graph");
  assert(stats.valid_edges === 1, "1 valid edge (Madrid)");
  assert(stats.invalidated_edges === 1, "1 invalidated edge (Barcelona)");
  assert(stats.episodes === 2, "2 episodes recorded");
  
  // Test 7: Non-contradicting fact doesn't invalidate
  console.log('\nTest 7: Non-contradicting fact coexistence');
  const ep3 = graph.recordEpisode("I work as a software engineer", dateFrom("2024-01-01"));
  graph.addFact({
    source: "user:alice",
    target: "Software Engineer",
    relation: "job_title",
    valid_from: dateFrom("2024-01-01"),
    recorded_at: dateFrom("2024-01-01"),
    episode_id: ep3,
  });
  
  const jobs = graph.currentFacts("user:alice", "job_title");
  assert(jobs.length === 1, "Alice has one current job title");
  assert(graph.stats().total_edges === 3, "3 total edges (lives_in x2 + job_title x1)");
  
  // Test 8: Multiple entity tracking
  console.log('\nTest 8: Multiple entities in same graph');
  const ep4 = graph.recordEpisode("Bob also lives in Barcelona", dateFrom("2025-01-01"));
  graph.addFact({
    source: "user:bob",
    target: "Barcelona",
    relation: "lives_in",
    valid_from: dateFrom("2025-01-01"),
    recorded_at: dateFrom("2025-01-01"),
    episode_id: ep4,
  });
  
  const aliceHome = graph.currentFacts("user:alice", "lives_in");
  const bobHome = graph.currentFacts("user:bob", "lives_in");
  assert(aliceHome[0]!.target === "Madrid", "Alice in Madrid");
  assert(bobHome[0]!.target === "Barcelona", "Bob in Barcelona");
  
  console.log('\n🎉 All 8 tests passed!\n');
  
  // Display the graph state
  console.log('📊 Graph Statistics:');
  console.log(graph.stats());
  console.log('\n📋 Alice\'s Location History:');
  for (const e of graph.history("user:alice", "lives_in")) {
    const validEnd = e.valid_until ? fmt(e.valid_until) : 'present';
    const status = e.invalidated_at ? '❌ INVALIDATED' : '✅ CURRENT';
    console.log(`  ${fmt(e.valid_from)} → ${validEnd}: ${e.target} ${status}`);
    console.log(`    Source: "${graph.provenance(e.id)[0]!.episode!.content}"`);
  }
}

// ─── Run ─────────────────────────────────────────────────

runTests();
```

**Output:**
```
🧪 Bi-Temporal Graph Tests

Test 1: Basic fact lifecycle
  ✅ One current 'lives_in' fact for Alice
  ✅ Alice currently lives in Barcelona

Test 2: Fact invalidation on contradiction
  ✅ Still one current 'lives_in' fact (not two)
  ✅ Alice now lives in Madrid (current)

Test 3: Time-travel query
  ✅ One 'lives_in' fact valid in June 2025
  ✅ In June 2025, Alice lived in Barcelona
  ✅ One 'lives_in' fact valid in Oct 2026
  ✅ In Oct 2026, Alice lives in Madrid

Test 4: Full relationship history
  ✅ Two versions of 'lives_in' in history
  ✅ First version: Barcelona
  ✅ Second version: Madrid
  ✅ Barcelona fact is invalidated
  ✅ Madrid fact is current

Test 5: Provenance / audit trail
  ✅ Provenance chain has 2 hops
  ✅ Chain starts with Barcelona
  ✅ Chain links to Madrid
  ✅ Source episode content preserved

Test 6: Stats and export
  ✅ Total 2 edges in graph
  ✅ 1 valid edge (Madrid)
  ✅ 1 invalidated edge (Barcelona)
  ✅ 2 episodes recorded

Test 7: Non-contradicting fact coexistence
  ✅ Alice has one current job title
  ✅ 3 total edges (lives_in x2 + job_title x1)

Test 8: Multiple entities in same graph
  ✅ Alice in Madrid
  ✅ Bob in Barcelona

🎉 All 8 tests passed!

📊 Graph Statistics:
{ total_edges: 4, valid_edges: 3, invalidated_edges: 1, episodes: 4 }

📋 Alice's Location History:
  2024-03-15 → 2026-05-01: Barcelona ❌ INVALIDATED
    Source: "I live in Barcelona"
  2026-05-01 → present: Madrid ✅ CURRENT
    Source: "I just moved to Madrid!"
```

---

## Key Insights

### 1. Temporal validity is the missing dimension in agent-memory-graph

agent-memory-graph currently has `created_at` and `updated_at` timestamps, but **no validity intervals** on edges. This means:
- "Where did Alice live?" works (current state)
- "Where did Alice live last year?" **doesn't work** (no historical state)
- "When did Alice move?" **doesn't work** (no invalidation tracking)

**Adding `valid_from`, `valid_until`, `invalidated_by` to the edges table** (~3 columns, ~60 lines of query logic) would unlock time-travel queries — a feature no npm agent memory library currently supports. This directly counters Zep's main differentiator.

### 2. Fact invalidation ≠ deletion — this is the core philosophical difference

Static KGs store facts as timeless truths. When facts change, you either:
- **Overwrite** (lose history) ← what most systems do
- **Append** (create contradictions) ← what naive graph stores do
- **Invalidate** (mark old as superseded, preserve both) ← what TKGs do

Invalidation is the only option that enables: audit trails, time-travel queries, and contradiction-aware retrieval. Zep/Graphiti's entire value proposition rests on this primitive.

**For agent-memory-graph:** Adding an `invalidate_edge(edge_id, at_time, by_edge_id)` method (~30 lines) and a `query_at(timestamp, ...)` method (~40 lines) would add temporal capabilities. The edge table already exists — this is an evolution, not a rebuild.

### 3. Relational volatility is the "free" win — RoMem's Semantic Speed Gate

Not all facts need temporal tracking. "Born in Paris" is permanent. "Currently CEO of Apple" changes every few years. "Loves Adidas shoes" might change monthly.

RoMem shows that a simple **volatility score per relation type** (learned from embeddings or hand-coded) enables:
- Smart retrieval ranking (stable facts get boosted, volatile facts get recency-weighted)
- Automatic expiration hints (high-volatility = shorter retention)
- Contradiction prioritization (only check high-volatility relations for conflicts)

For agent-memory-graph, a `volatility_score` field on edges (0=permanent, 1=highly volatile) would let `search_hybrid` weight temporal relevance automatically — a capability no competitor in npm has.

### 4. Production TKG retrieval needs zero LLM calls at query time

Both Zep and RoMem explicitly avoid LLM calls during retrieval. All temporal reasoning happens through:
- Pre-computed embeddings (semantic similarity)
- BM25 (lexical precision)
- Graph traversal (multi-hop relationships)
- Temporal filters (validity window checks)

**The LLM is only used during ingestion** (entity extraction, contradiction detection). This is why Zep achieves sub-200ms p95 latency. For agent-memory-graph, this validates the existing architecture — temporal features should be pure SQL operations on indexed columns.

### 5. The market gap: SQLite-native temporal KG

The current landscape:
- **Zep/Graphiti**: Production TKG, but requires Neo4j/FalkorDB (heavy dependency), Python-only
- **RoMem**: Research, complex embedding rotation (not yet production)
- **ATOM**: Research, focuses on extraction (not retrieval/storage)
- **memory-engine** (Missing Knowledge Layer paper): Rust + SQLite + HNSW, closest architecturally, but not npm-available

**agent-memory-graph can be the first npm package with bi-temporal edge support** — adding `valid_from`, `valid_until`, `invalidated_at`, `invalidated_by` columns to the edges table, plus `invalidate_edge()` and `query_at()` methods. This directly counters Zep's positioning:

| Feature | Zep/Graphiti | agent-memory-graph (proposed) |
|---------|-------------|-------------------------------|
| Temporal model | Bi-temporal | Bi-temporal |
| Backend | Neo4j (required) | SQLite (embedded) |
| Language | Python only | TypeScript (npm native) |
| LLM at query | No | No |
| Invalidation | LLM-driven | Rule + embedding hybrid |
| Time-travel queries | Yes | Yes |
| Volatility scoring | No | Planned (RoMem-inspired) |
| Graph algorithms | Limited | 30+ (PageRank, HITS, etc.) |
| npm | ✗ | ✓ |

---

## Comparison: Temporal KG Systems Landscape (June 2026)

| System | Venue | Temporal Model | Invalidation | Retrieval | Backend | Open Source |
|--------|-------|---------------|-------------|-----------|---------|-------------|
| **Zep/Graphiti** | arXiv:2501.13956 | Bi-temporal (4 timestamps) | LLM-driven contradiction detection | Hybrid (vec+BM25+graph+time) | Neo4j/FalkorDB | Apache 2.0 (Python) |
| **RoMem** | arXiv:2604.11544 | Continuous phase rotation | Geometric shadowing | Embedding rotation | Drop-in module | Research code |
| **ATOM** | EACL 2026 | 5-tuple (s,r,o,t_start,t_end) | Preprocessing-time resolution | N/A (construction only) | Python (iText2KG) | MIT |
| **CIK-LLM** | CoLLAs 2024 | Dynamic TKG (quadruples) | N/A (external TKG) | Subgraph + LLM reasoning | External TKG | GitHub |
| **TREK** | arXiv:2509.15464 | Validity intervals on edges | N/A (external KG) | Temporal reasoning + KG | External KG | GitHub |
| **memory-engine** | arXiv:2604.11364 | 4 timestamps + Ebbinghaus decay | Supersession chain | HNSW + Petgraph | Rust + SQLite | Research |
| **agent-memory-graph** | This project | ⚠️ `created_at` only (no validity) | N/A | BM25+Vector+Graph RRF | SQLite | MIT (npm) |

---

## Next Actions

1. **agent-memory-graph: Add bi-temporal edge support** (~80 lines + 15 tests)
   - Add columns: `valid_from`, `valid_until` (nullable), `invalidated_at` (nullable), `invalidated_by` (nullable FK to edges)
   - Add methods: `invalidate_edge(edge_id, at_time, by_edge_id)`, `query_at(timestamp, ...)`, `history(entity_id, relation)`, `provenance(edge_id)`
   - Add method: `temporal_conflicts(entity_id, relation)` — find overlapping validity intervals
   - This closes the competitive gap with Zep/Graphiti

2. **agent-memory-graph: Add `volatility_score` to edges** (~20 lines + 8 tests)
   - Field: `volatility_score REAL DEFAULT 0.0` (0=permanent, 1=highly volatile)
   - Use in `search_hybrid`: high-volatility edges get recency boost, low-volatility get stability boost
   - Pre-compute from relation type (e.g., "born_in"=0.0, "ceo_of"=0.7, "prefers"=0.5)

3. **README positioning update**: "Only npm agent memory with bi-temporal validity tracking" — directly counters Zep

4. **Research follow-up**: Study Graphiti's MCP server pattern — their integration approach may inform openclaw-mcp-server design

---

## Quality Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 5 concepts | Bi-temporal, invalidation lifecycle, volatility, hybrid retrieval, subgraph hierarchy |
| Runnable code (≥1) | ✅ ~200 lines TS | BiTemporalGraph class, 8/8 assertions pass |
| Key insights (≥3) | ✅ 5 insights | Each with specific agent-memory-graph impact |
| Next actions (≥1) | ✅ 4 actions | Concrete line counts + test targets |
| Novel vs prior research | ✅ Fresh topic | No prior temporal KG research in 150+ notes |
| Project relevance | ✅ Direct | Identifies exact columns/methods to add to agent-memory-graph |

---

## Sources

1. **Zep: A Temporal Knowledge Graph Architecture for Agent Memory** — Rasmussen et al., arXiv:2501.13956 (212 citations)
2. **RoMem: Continuous Phase Rotation for TKGs** — arXiv:2604.11544 (SOTA ICEWS05-15 72.6 MRR)
3. **ATOM: AdapTive and OptiMized Dynamic TKG Construction** — Lairgi et al., EACL 2026 Findings
4. **CIK-LLM: Continual In-context Knowledge LLM** — Di Maio et al., CoLLAs 2024
5. **Graph-based Agent Memory: Taxonomy, Techniques, and Challenges** — arXiv:2602.05665 (comprehensive survey)
6. **The Missing Knowledge Layer in Cognitive Architectures** — arXiv:2604.11364 (memory-engine, Rust+SQLite)
7. **TREK: Temporal Reasoning over Evolving KGs** — arXiv:2509.15464 (8B matches 671B with temporal reasoning)
8. **Thoughtworks Technology Radar Vol. 31** — Graphiti moved to "Trial" (production viability endorsement)

---

_Research note by Catalyst 🧪 — 2026-06-21_
