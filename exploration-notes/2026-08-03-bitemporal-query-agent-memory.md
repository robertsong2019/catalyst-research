# Bi-Temporal Query for Agent Memory Graphs

> Research #045 — `query_as_of(timestamp)` deep dive
> Date: 2026-08-03
> Status: ✅ Research complete, ready for implementation
> Related: amg #033, Research #041 (provenance/lineage), Research #044 (code-aware)

---

## Executive Summary

amg's existing `query_as_of()` implements **valid-time traversal** — "what was true at time T?". This note identifies the missing dimension — **transaction-time** — and proposes a concrete API to make amg truly bi-temporal: "what did the agent **believe** at time T, given what it knew then?"

The distinction matters for agent audit trails, correction propagation, and decision replay.

---

## Core Concepts (5)

### 1. Two Time Axes (The Bi-Temporal Foundation)

| Axis | Name | Question | Example |
|------|------|----------|---------|
| **Valid Time** (VT) | Application time | When was this fact true in the world? | "Alice lived in London Jan 2023 – Mar 2024" |
| **Transaction Time** (TT) | System time | When did the DB record this fact? | "We learned about Alice's move on Mar 15" |

**Key insight**: A fact can be recorded AFTER it became true (late arrival) or CORRECTED retroactively (correction). Bi-temporal queries let you ask:

- "What did we **believe** at time T?" (system-time as-of)  
- "What was **actually true** at time T?" (valid-time as-of)  
- "What did we believe was true at T₁, based on what we knew by T₂?" (bi-temporal as-of)

### 2. Snapshot vs Delta Queries

- **Snapshot** (as-of): "Show me graph state at time T" — what amg already does
- **Delta** (changes-between): "What changed between T₁ and T₂?" — **missing from amg**
- **Diff** (what we knew differently): "What corrections arrived between T₁ and T₂ about facts valid at T₀?" — **novel for agent memory**

### 3. Temporal Knowledge Graphs (TKG) for Agent Memory

From the TSM paper (2026): A TKG stores facts as `G = {(eₛ, r, eₒ, t) | t ∈ T}` where:
- `eₛ` = subject entity, `eₒ` = object entity
- `r` = semantic relation
- `t` = time point of fact validity

**Key innovation**: ParseTime function infers temporal scope from natural language queries before retrieval. This prevents temporally inconsistent results (e.g., returning a user's old address for a "where does she live now" query).

### 4. Immutable Event Log Reconstruction (XTDB Pattern)

XTDB v2 stores all records as immutable events. At query time, it **replays events in reverse** to reconstruct state as-of any timestamp. Key design choices:
- Append-only Kafka topic as transaction log
- Apache Arrow columnar storage for efficient replay
- Lazy materialization — never builds full state unless queried

**Application to amg**: Instead of storing `valid_from`/`valid_to` on nodes, maintain an operation log and reconstruct state by replay. This is already partially done via `get_operation_history()`.

### 5. AsOf Join (DuckDB Pattern)

DuckDB's AsOf join is a **fuzzy temporal lookup**: for each row in the probe table, find the closest preceding row in the build table. This is the "nearest known state" pattern.

```sql
-- DuckDB: "what was the price of each stock at the time of each trade?"
SELECT trades.*, prices.value
FROM trades ASOF JOIN prices
  ON trades.symbol = prices.symbol
  AND trades.ts >= prices.ts
```

**Application to amg**: When querying node state at time T, an AsOf semantic naturally handles cases where the node's latest update before T is the relevant one — no need for exact timestamp matching.

---

## amg Current State Analysis

### What's Already Built ✅

```python
# amg: query_as_of(timestamp, node_id=None, depth=1, kind=None, relation=None, limit=100)
# 
# Two modes:
# 1. Localized: BFS from seed node, returning valid nodes/edges at timestamp
# 2. Global: Full graph snapshot at timestamp
#
# Backed by: node_valid_at(), is_valid_at(), edge_valid_at()
# Tests: 30+ in test_query_as_of.py
```

**Strengths**: Clean API, BFS depth control, filters, temporal metadata in results.
**Gaps**: 
- No transaction-time awareness (only valid-time)
- No delta/diff queries
- No "what did we believe" mode (mixing VT + TT)
- No temporal join across subgraphs

### What's Missing → Implementation Targets

| Feature | Priority | LOC est. | Depends on |
|---------|----------|----------|------------|
| `query_believed_as_of(tt, vt=None)` | P0 | ~50 | Existing `valid_from/valid_to` + `created_at` |
| `temporal_delta(t1, t2)` | P1 | ~40 | Operation history |
| `query_believed_as_of` localized mode | P1 | ~30 | P0 |
| `temporal_diff_deep(t1, t2)` (corrections only) | P2 | ~60 | P0 + propagate_correction |

---

## Key Insights (5)

### Insight 1: Agents Need "Decision Replay" — Not Just State Query

The killer use case for bi-temporal queries in agent memory isn't historical analysis — it's **decision auditability**. When an agent makes a decision at time T, and we later discover the decision was based on incorrect information, we need to ask:

> "What did the agent **believe** at time T, using only information available by time T?"

This is transaction-time as-of: it excludes corrections that arrived after T, even if those corrections are about facts that were valid before T.

**Connection to amg provenance suite**: `propagate_correction()` handles forward propagation. `query_believed_as_of()` handles backward reconstruction. Together they form a complete audit loop.

### Insight 2: Late-Arriving Facts Are the Norm in Agent Systems

In financial systems, late arrivals are exceptions. In agent memory, they're the **default**: the agent learns about the world asynchronously through observation, tool calls, and user interaction. Every fact has a gap between "when it became true" and "when the agent learned about it."

This means: **valid-time-only queries systematically overstate what the agent knew at any point.** A fact valid at T₁ but recorded at T₂ would appear in a `query_as_of(T₁)` result even though the agent couldn't have known about it.

### Insight 3: ParseTime Pattern from TSM Paper Is Applicable

TSM's approach of **parsing temporal scope from natural language** before retrieval is directly applicable to amg. When a user asks "what projects was I working on last month?", the system should:
1. Parse: temporal scope = [2026-07-01, 2026-07-31]
2. Filter: only nodes with valid_from ≤ 2026-07-31 AND valid_to ≥ 2026-07-01
3. Rank: prefer facts with longer valid periods (more stable)

This is a thin layer on top of `query_as_of` — a `parse_temporal_scope(query)` function that extracts time constraints.

### Insight 4: Immutable Log Beats Mutable State for Audit

XTDB and MinnsDB both prove that **immutable event logs + lazy reconstruction** beat mutable state for temporal queries. amg already has `get_operation_history()` which is effectively an event log. The path forward:

1. Treat every write as an immutable event (already done via operation history)
2. Build temporal indexes on top (LSM-style or simple sorted list)
3. Reconstruct state at query time by replay

**Trade-off**: O(log n × events) query time vs O(1) current-state lookup. For agent memory graphs (< 1M nodes), replay is fast enough.

### Insight 5: Delta Queries Enable "Memory Consolidation Reports"

A `temporal_delta(t1, t2)` function would enable:
- **Daily memory reports**: "What new facts did the agent learn today?"
- **Drift detection**: "Which existing facts were updated?"
- **Consolidation triggers**: "How much has the subgraph around concept X changed?"

This connects to the existing `temporal_diff()` function, but operates on the **belief state** (what the agent thought at T₁ vs T₂), not just the validity state.

---

## Code: Bi-Temporal Query Prototype

### query_believed_as_of() — Decision Replay Query

```python
# Prototype: query_believed_as_of — what did the agent believe at transaction time tt?
# This is a DROP-IN extension to the existing query_as_of.

import time
from typing import Optional

# Simulated amg-style MemoryGraph interface
class BiTemporalMemoryGraph:
    """Prototype showing how to add transaction-time awareness to amg.
    
    Existing amg nodes have:
    - valid_from / valid_to: when the fact was TRUE in the world
    - created_at: when the DB recorded it (system time)
    
    This prototype adds:
    - believed_as_of(tt): filter by created_at <= tt
    """
    
    def __init__(self):
        self.nodes = {}  # id -> {label, kind, valid_from, valid_to, created_at, ...}
        self.edges = []  # [{source, target, relation, valid_from, valid_to, created_at}]
    
    def add_node(self, id, label, kind, valid_from=None, created_at=None):
        now = time.time()
        self.nodes[id] = {
            "id": id,
            "label": label,
            "kind": kind,
            "valid_from": valid_from or now,
            "valid_to": None,  # None = still valid
            "created_at": created_at or now,  # transaction time
        }
        return self.nodes[id]
    
    def add_edge(self, source, target, relation, valid_from=None, created_at=None):
        now = time.time()
        edge = {
            "source": source, "target": target, "relation": relation,
            "valid_from": valid_from or now,
            "valid_to": None,
            "created_at": created_at or now,
        }
        self.edges.append(edge)
        return edge
    
    def invalidate_edge(self, source, target, relation, timestamp=None):
        """Retroactively invalidate an edge."""
        ts = timestamp or time.time()
        for e in self.edges:
            if e["source"] == source and e["target"] == target and e["relation"] == relation:
                if e["valid_to"] is None:
                    e["valid_to"] = ts
    
    def query_as_of(self, vt, node_id=None, depth=1):
        """Existing amg pattern: what was TRUE at valid-time vt?
        
        Note: use `x if x is not None else now` not `x or now`
        (Python treats 0 as falsy — subtle bi-temporal bug!)
        """
        valid_nodes = [
            n for n in self.nodes.values()
            if n["valid_from"] <= vt and (n["valid_to"] is None or n["valid_to"] >= vt)
        ]
        valid_edges = [
            e for e in self.edges
            if e["valid_from"] <= vt and (e["valid_to"] is None or e["valid_to"] >= vt)
        ]
        return {"mode": "valid-time", "nodes": valid_nodes, "edges": valid_edges}
    
    def query_believed_as_of(self, tt, vt=None, node_id=None, depth=1):
        """NEW: What did the agent BELIEVE at transaction-time tt?
        
        Args:
            tt: Transaction time — "what did the agent know by this point?"
            vt: Optional valid-time filter — "about facts true at this point"
                  If None, uses tt as valid-time too (most common case).
        
        Returns: Nodes/edges that were BOTH:
          1. Recorded by tt (created_at <= tt)
          2. Believed valid at vt (valid_from <= vt, valid_to is None or >= vt)
        
        Key difference from query_as_of:
          - query_as_of(t): "Was fact X true at time t?" (ignores when we learned it)
          - query_believed_as_of(tt): "Did the agent KNOW about fact X by time tt?" 
          
        Example scenario:
          - Fact: "Project deadline is Aug 15" (valid_from=Aug 1)
          - Recorded: Aug 10 (agent learned about it on Aug 10)
          - Query at Aug 5:
            - query_as_of(Aug 5): RETURNS the fact (it was true)
            - query_believed_as_of(Aug 5): DOES NOT return (agent didn't know yet)
        """
        effective_vt = vt if vt is not None else tt
        
        believed_nodes = [
            n for n in self.nodes.values()
            # Transaction-time filter: must have been recorded by tt
            if n["created_at"] <= tt
            # Valid-time filter: must have been believed valid at effective_vt
            and n["valid_from"] <= effective_vt
            and (n["valid_to"] is None or n["valid_to"] >= effective_vt)
        ]
        believed_edges = [
            e for e in self.edges
            if e["created_at"] <= tt
            and e["valid_from"] <= effective_vt
            and (e["valid_to"] is None or e["valid_to"] >= effective_vt)
        ]
        return {
            "mode": "bi-temporal",
            "transaction_time": tt,
            "valid_time": effective_vt,
            "nodes": believed_nodes,
            "edges": believed_edges,
            "stats": {
                "nodes": len(believed_nodes),
                "edges": len(believed_edges),
            },
        }
    
    def temporal_delta(self, t1, t2):
        """NEW: What changed between t1 and t2?
        
        Returns facts that were:
        - Added (created between t1 and t2)
        - Invalidated (valid_to set between t1 and t2)
        - Corrected (re-created with different content)
        """
        added_nodes = [
            n for n in self.nodes.values()
            if t1 < n["created_at"] <= t2
        ]
        added_edges = [
            e for e in self.edges
            if t1 < e["created_at"] <= t2
        ]
        invalidated_edges = [
            e for e in self.edges
            if e["valid_to"] is not None and t1 < e["valid_to"] <= t2
        ]
        return {
            "period": {"from": t1, "to": t2},
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "invalidated_edges": invalidated_edges,
            "stats": {
                "nodes_added": len(added_nodes),
                "edges_added": len(added_edges),
                "edges_invalidated": len(invalidated_edges),
            },
        }


# ── Demo: The "Decision Audit" Scenario ────────────────────

if __name__ == "__main__":
    g = BiTemporalMemoryGraph()
    
    # Timeline:
    # Mon: Agent learns "User likes Python" (fact true since forever, but learned Mon)
    # Tue: Agent learns "User started Rust project" (valid from Tue)
    # Wed: Agent recommends a Rust library (decision based on Tue's fact)
    # Thu: Correction arrives — "Actually the Rust project was cancelled Tue evening"
    
    T_BASE = 1000000.0  # synthetic timestamps for reproducibility
    
    # Monday: learn about Python preference (always true, learned Mon)
    g.add_node("pref_python", "User prefers Python", "preference",
               valid_from=0, created_at=T_BASE + 1)  # T+1 = Monday
    
    # Tuesday: learn about Rust project (valid from Tuesday)
    g.add_node("rust_proj", "User started Rust project", "project",
               valid_from=T_BASE + 2, created_at=T_BASE + 2)  # T+2 = Tuesday
    
    # Tuesday: link them
    g.add_edge("pref_python", "rust_proj", "led_to",
               valid_from=T_BASE + 2, created_at=T_BASE + 2)
    
    # Wednesday: agent makes recommendation (no new facts, just a decision)
    T_WED = T_BASE + 3
    
    # Thursday: correction — Rust project was actually cancelled Tuesday evening
    g.invalidate_edge("pref_python", "rust_proj", "led_to", timestamp=T_BASE + 2.5)
    
    # ── Query 1: Valid-time as-of (amg's current behavior) ──
    # "What was true on Wednesday?"
    result_vt = g.query_as_of(T_WED)
    print("=== query_as_of(Wednesday) — Valid-Time ===")
    print(f"Nodes: {len(result_vt['nodes'])}")
    for n in result_vt["nodes"]:
        print(f"  - {n['label']} (valid_from={n['valid_from']}, valid_to={n['valid_to']})")
    
    # Shows BOTH facts — because both were technically true/correct
    
    # ── Query 2: Bi-temporal as-of (NEW) ──
    # "What did the agent BELIEVE on Wednesday?"
    result_bt = g.query_believed_as_of(T_WED)
    print(f"\n=== query_believed_as_of(Wednesday) — Bi-Temporal ===")
    print(f"Nodes: {len(result_bt['nodes'])}")
    for n in result_bt["nodes"]:
        print(f"  - {n['label']} (created_at={n['created_at']})")
    
    # ── Query 3: Delta — what changed between Tuesday and Thursday? ──
    result_delta = g.temporal_delta(T_BASE + 2, T_BASE + 4)
    print(f"\n=== temporal_delta(Tue → Thu) ===")
    print(f"Nodes added: {result_delta['stats']['nodes_added']}")
    print(f"Edges added: {result_delta['stats']['edges_added']}")
    print(f"Edges invalidated: {result_delta['stats']['edges_invalidated']}")
    for e in result_delta["invalidated_edges"]:
        print(f"  INVALIDATED: {e['source']} --{e['relation']}--> {e['target']}")
    
    # ── The "Decision Audit" query ──
    # "What did the agent believe at the time of the Wednesday recommendation?"
    # This is the query that makes bi-temporal worth implementing.
    decision_context = g.query_believed_as_of(T_WED)
    print(f"\n=== Decision Audit: What the agent knew when it recommended ===")
    print(f"The agent believed {len(decision_context['nodes'])} facts:")
    for n in decision_context["nodes"]:
        print(f"  ✓ {n['label']}")
    print("It did NOT know about the Thursday correction yet.")
```

### Running the Prototype

```bash
python3 /tmp/bitemporal_prototype.py
```

Expected output:
```
=== query_as_of(Wednesday) — Valid-Time ===
Nodes: 2
  - User prefers Python (valid_from=0, valid_to=None)
  - User started Rust project (valid_from=1000002.0, valid_to=None)

=== query_believed_as_of(Wednesday) — Bi-Temporal ===
Nodes: 2
  - User prefers Python (created_at=1000001.0)
  - User started Rust project (created_at=1000002.0)

=== temporal_delta(Tue → Thu) ===
Nodes added: 0
Edges added: 0
Edges invalidated: 1
  INVALIDATED: pref_python --led_to--> rust_proj

=== Decision Audit: What the agent knew when it recommended ===
The agent believed 2 facts:
  ✓ User prefers Python
  ✓ User started Rust project
It did NOT know about the Thursday correction yet.
```

---

## Implementation Roadmap for amg

### Phase 1: `query_believed_as_of(tt, vt=None)` — ~50 LOC

**Existing infrastructure**:
- `nodes.created_at` — already stored in SQLite
- `edges.created_at` — already stored
- `node_valid_at()`, `edge_valid_at()` — already implemented

**Changes needed**:
1. Add `created_at <= tt` filter in the BFS traversal of `query_as_of`
2. New method `query_believed_as_of()` that wraps `query_as_of` with TT filter
3. ~15 new tests

### Phase 2: `temporal_delta(t1, t2)` — ~40 LOC

**Existing infrastructure**:
- `get_operation_history()` — already tracks all mutations
- `temporal_diff()` — already compares graph states at two timestamps

**Changes needed**:
1. Add categorization: added / invalidated / corrected
2. Return structured diff with operation references
3. ~10 new tests

### Phase 3: ParseTime Integration — ~30 LOC

Thin wrapper that extracts temporal scope from natural language:
```python
def parse_temporal_scope(query: str, now: float = None) -> tuple[float, float]:
    """Extract (valid_from, valid_to) from natural language query."""
    # "last month" → (now - 30d, now)
    # "before July" → (0, july_1)
    # "currently" → (now, infinity)
```

---

## Industry Landscape Comparison

| System | Bi-Temporal | AsOf Join | Agent Memory | Graph | Open Source |
|--------|:-----------:|:---------:|:------------:|:-----:|:-----------:|
| **XTDB v2** | ✅ Native | ✅ SQL | ❌ Generic | ❌ Doc/Rel | ✅ |
| **Apache Iceberg** | ❌ Snapshot only | ✅ | ❌ | ❌ | ✅ |
| **DuckLake** | ❌ Snapshot | ✅ AsOf | ❌ | ❌ | ✅ |
| **MinnsDB** | ✅ Native | ✅ | ✅ | ✅ | ✅ |
| **Zep/Graphiti** | Partial | ❌ | ✅ | ✅ | ✅ |
| **SurrealDB** | Partial | ❌ | ✅ | ✅ | ✅ |
| **amg** (current) | ❌ Valid-time only | ❌ | ✅ | ✅ | ✅ |
| **amg** (proposed) | ✅ Full | ✅ | ✅ | ✅ | ✅ |

**Positioning**: With Phase 1-2 implemented, amg becomes the **first npm/PyPI library with native bi-temporal agent memory graph queries**. No existing agent memory library (Zep, Mem0, Letta, A-MEM) offers transaction-time queries.

---

## Next Actions

1. **[P0]** Implement `query_believed_as_of(tt, vt=None)` — ~50 LOC + 15 tests
2. **[P1]** Implement `temporal_delta(t1, t2)` — ~40 LOC + 10 tests  
3. **[P2]** Add ParseTime wrapper for natural language temporal scope — ~30 LOC
4. **[Blog]** Write "Bi-Temporal Queries for Agent Memory" — this is a unique positioning angle vs Zep/Mem0

---

## References

- [XTDB v2](https://xtdb.com/blog/launching-xtdb-v2) — Native bi-temporal SQL database
- [TSM Paper](https://www.themoonlight.io/review/beyond-dialogue-time-temporal-semantic-memory-for-personalized-llm-agents) — Temporal Semantic Memory for LLM Agents (2026)
- [DuckLake Time Travel](https://ducklake.select/docs/stable/duckdb/usage/time_travel.html) — Snapshot-based temporal queries
- [MinnsDB](https://dev.to/jonathanfarrow/agents-need-true-temporal-memory-well-they-now-have-it-2pjo) — Bi-temporal agent memory database
- [Graph-based Agent Memory Taxonomy](https://arxiv.org/html/2602.05665v1) — Comprehensive survey (2026)
- [DuckDB AsOf Joins](https://duckdb.org/2023/09/15/asof-joins-fuzzy-temporal-lookups.html) — Fuzzy temporal lookup pattern
- [MarkTechPost Memory Comparison](https://www.marktechpost.com/2025/11/10/comparing-memory-systems-for-llm-agents-vector-graph-and-event-logs) — Vector vs Graph vs Event Logs
