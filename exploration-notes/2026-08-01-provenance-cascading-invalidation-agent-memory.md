# Research #041: Provenance Tracking & Cascading Invalidation in Agent Memory

> **Date:** 2026-08-01
> **Trigger:** HEARTBEAT.md next API target: `depends_on` edge + `propagate_invalidation()`
> **Status:** Research complete. Directly enables amg cycles 336+.
> **Related:** #040 (Graph-Native Agent Memory), #033 (Bi-temporal), #032 (Production Memory)

---

## Summary

Agent memory systems face a fundamental problem: when a fact changes, every fact that was derived from it may also be wrong. No existing benchmark or production system fully solves cascading invalidation — the propagation of corrections through dependency chains. This research surveys the 2025-2026 frontier (STALE, GRADE, MemClaw, GUARDIAN, AgentArmor) and maps their insights to amg's planned `depends_on` edge type + `propagate_invalidation()` API.

---

## Core Concepts

### 1. Implicit Conflict vs Explicit Conflict (STALE, arXiv:2605.06527)

STALE introduces a critical distinction:

- **Type I — Direct Conflict:** A new observation updates the *same* attribute. E.g., user says "I moved to Portland" — directly invalidates "lives in Seattle." The old value is wrong for the same slot.
- **Type II — Propagated (Cascading) Conflict:** A new observation updates a *different* attribute whose causal/logical dependency invalidates a prior belief. E.g., user says "I got a leg injury" — logically invalidates "commutes by bicycle" even though neither "bicycle" nor "commute" was mentioned.

Type II is the hard problem. Every existing benchmark (LoCoMo, LongMemEval, IMPLEXCONV, FactConsolidation, KnowMe-Bench, PersonaMem-v2, AMEMGYM) has × in the Cascading Invalidation column. STALE is the first to isolate it.

**Key numbers:** Best model (Gemini-3.1-pro) achieves only 55.2% overall accuracy. On cascading invalidation specifically, performance is even worse — models "highly susceptible to queries that presuppose stale information."

### 2. Two-Layer Dependency Graph (GRADE, arXiv:2606.22741)

GRADE models every agent run as a directed typed temporal multigraph `G = (V, E_X, E_D, τ, t, σ)` with:

- **Execution layer (E_X):** What ran in what order (emits, handoffs). **Free** — read directly from traces.
- **Dependency layer (E_D):** What each step relied on (depends_on, reads, writes). **Costly** — must be recovered from trace content, declared by instrumentation, or inferred under assumption.

The **attachment grade** `σ: E_D → {observed, declared, inferred}` stamps HOW each dependency edge is known. This is the missing inductive bias that generic GNNs lack:

| Grade | Meaning | Saturation ρ | Signal Quality |
|-------|---------|-------------|----------------|
| observed | Trace logs the read/write | ~0.01 | Strong, transferable |
| declared | Instrumentation logs it | ~0.07 | Medium, non-degenerate |
| inferred | Assumed (full history) | 1.00 | Degenerate, collapses to run size |

**Key finding:** Size-normalized dependency shape transfers across agent classes (above chance on all 6 held-out corpora), while run size inverts on 2/6. The dependency layer predicts failure where run size is weak.

### 3. Four Fleet-Memory Failure Modes (MemClaw, arXiv:2606.24535)

When memory becomes shared state across agent fleets:

| Failure Mode | Description | Example |
|-------------|-------------|---------|
| **Unauthorized Leakage** | Agent retrieves memory outside authorized scope | Support agent reads billing notes |
| **Stale Propagation** | Memory updates fail to synchronize across agents | Address updated, old address still served |
| **Contradiction Persistence** | Conflicting memories coexist without resolution | Two incompatible preferences both retrievable |
| **Provenance Collapse** | Retrieved memories cannot be traced to origin | Fact found but no writer/source/timestamp |

MemClaw defines five design principles: scoped retrieval, explicit provenance, temporal correctness, policy-governed propagation, persistent shared state. Provenance graph stores writer identity, source system, derivation history (`derived_from`), and modification lineage.

**Key finding:** Contradiction detection works when both writes are admitted (90/90 = 100% supersession), but a synchronous dedup gate can pre-empt near-identical contradictory writes before the async detector runs. Pipeline ordering matters.

### 4. Temporal Graph Anomaly Detection (GUARDIAN, NeurIPS 2025)

GUARDIAN models multi-agent collaboration as a discrete-time temporal attributed graph. An unsupervised encoder-decoder with incremental training learns to reconstruct normal patterns. Anomalies (hallucination amplification, error injection/propagation) are detected as reconstruction errors.

**Three threat modes measured:**
- Hallucination amplification: 66.92-91.52% detection rate
- Agent-targeted error injection: 72.31-92.63%
- Communication-targeted error injection: 70.65-94.74%

The temporal graph captures propagation dynamics that static per-message analysis misses.

### 5. Write-Side State Adjudication (CUPMem, from STALE paper)

CUPMem reframes memory management as explicit state tracking with write-time decisions:

```
y_i = J_θ(i, Δt, x_t, Ω) ∈ {KEEP, STALE, REPLACE, UNKNOWN}
```

Three-stage pipeline:
1. **Write-side belief updating:** An LLM adjudicator evaluates each candidate against existing state
2. **Topology-triggered belief propagation:** Search expands beyond directly-touched slots to structurally affected regions via `Affected_θ(Δt, Ω)` — the dependency topology
3. **Constrained readout:** Only adjudicated facts reach the query path

**Result:** 68% accuracy (vs 55% baseline) — a +13pp improvement from write-side adjudication.

---

## Code Example: Provenance Graph + Cascading Invalidation (TypeScript, zero-dep)

This prototype demonstrates the core mechanism for amg's planned `propagate_invalidation()`:

```typescript
/**
 * ProvenanceGraph — Dependency-aware memory invalidation prototype
 * 
 * Demonstrates: 
 * - depends_on edges between memory nodes
 * - propagate_invalidation() for cascading corrections  
 * - STALE Type II (cascading) conflict resolution
 * - GRADE-style edge grading (observed/declared/inferred)
 */

type EdgeGrade = 'observed' | 'declared' | 'inferred';
type NodeStatus = 'active' | 'stale' | 'invalidated' | 'superseded';

interface MemoryNode {
  id: string;
  content: string;
  attributes: Record<string, unknown>;  // e.g., { city: "Seattle", commute: "bicycle" }
  status: NodeStatus;
  validAt: number;   // bi-temporal: when fact held
  recordedAt: number; // bi-temporal: when ingested
  invalidAt?: number;
  provenance: {
    writer: string;
    source: string;
    derivedFrom?: string[];  // parent node IDs
  };
}

interface DependsOnEdge {
  from: string;  // child (depends on parent)
  to: string;    // parent
  grade: EdgeGrade;
  reason: string;  // WHY the dependency exists
  weight: number;  // confidence in the dependency [0,1]
}

class ProvenanceGraph {
  nodes = new Map<string, MemoryNode>();
  edges: DependsOnEdge[] = [];

  addNode(node: MemoryNode): void {
    this.nodes.set(node.id, node);
    // Auto-create derived_from → depends_on edges
    if (node.provenance.derivedFrom) {
      for (const parentId of node.provenance.derivedFrom) {
        this.addEdge(node.id, parentId, 'declared', 'derived_from', 1.0);
      }
    }
  }

  addEdge(from: string, to: string, grade: EdgeGrade, reason: string, weight: number): void {
    // Avoid duplicates
    const exists = this.edges.some(e => e.from === from && e.to === to);
    if (!exists) {
      this.edges.push({ from, to, grade, reason, weight });
    }
  }

  /** Get all nodes that directly depend on `nodeId` */
  getDependents(nodeId: string): MemoryNode[] {
    return this.edges
      .filter(e => e.to === nodeId)
      .map(e => this.nodes.get(e.from)!)
      .filter(Boolean);
  }

  /** Get all nodes that `nodeId` depends on */
  getDependencies(nodeId: string): MemoryNode[] {
    return this.edges
      .filter(e => e.from === nodeId)
      .map(e => this.nodes.get(e.to)!)
      .filter(Boolean);
  }

  /**
   * propagate_invalidation() — Cascading correction
   * 
   * When a base fact is invalidated, mark all derived facts as stale.
   * Uses BFS traversal of dependency edges (reverse direction).
   * 
   * Returns the cascade trace for auditability.
   */
  propagate_invalidation(
    invalidatedNodeId: string,
    reason: string,
    maxDepth: number = 10
  ): {
    invalidated: string[];
    trace: { node: string; depth: number; reason: string; grade: EdgeGrade }[];
  } {
    const invalidated: string[] = [invalidatedNodeId];
    const trace: { node: string; depth: number; reason: string; grade: EdgeGrade }[] = [];
    const visited = new Set<string>([invalidatedNodeId]);

    // Mark source node as invalidated
    const source = this.nodes.get(invalidatedNodeId);
    if (source) {
      source.status = 'invalidated';
      source.invalidAt = Date.now();
    }

    // BFS cascade — find all nodes that depend on the invalidated node
    const queue: { id: string; depth: number; reason: string; grade: EdgeGrade }[] = [
      { id: invalidatedNodeId, depth: 0, reason, grade: 'observed' }
    ];

    while (queue.length > 0) {
      const { id, depth, reason: why, grade } = queue.shift()!;

      if (depth >= maxDepth) continue;

      const dependents = this.edges
        .filter(e => e.to === id && !visited.has(e.from))
        .map(e => ({ node: e, memoryNode: this.nodes.get(e.from)! }));

      for (const { node: edge, memoryNode } of dependents) {
        visited.add(edge.from);

        // Only cascade through edges with sufficient weight
        if (edge.weight < 0.3) {
          trace.push({
            node: edge.from,
            depth: depth + 1,
            reason: `skipped (weight=${edge.weight.toFixed(2)} < 0.3)`,
            grade: edge.grade
          });
          continue;
        }

        // STALE Type II logic: mark as stale (not fully invalidated)
        // The derived fact might still be independently valid
        memoryNode.status = 'stale';
        invalidated.push(edge.from);

        trace.push({
          node: edge.from,
          depth: depth + 1,
          reason: `${why} → ${edge.reason} (w=${edge.weight.toFixed(2)})`,
          grade: edge.grade
        });

        queue.push({
          id: edge.from,
          depth: depth + 1,
          reason: `${why} → ${edge.reason}`,
          grade: edge.grade
        });
      }
    }

    return { invalidated, trace };
  }

  /**
   * CUPMem-style write-side adjudication
   * When new evidence arrives, decide what to do with existing state
   */
  adjudicate(
    newNode: MemoryNode,
    existingNodes: MemoryNode[]
  ): 'KEEP' | 'STALE' | 'REPLACE' | 'UNKNOWN' {
    // Check if new node conflicts with any existing active node
    for (const existing of existingNodes) {
      if (existing.status !== 'active') continue;

      // Type I: Same attribute, different value
      for (const [key, newVal] of Object.entries(newNode.attributes)) {
        const oldVal = existing.attributes[key];
        if (oldVal !== undefined && String(oldVal) !== String(newVal)) {
          // Direct conflict — supersede the old node (no depends_on edge;
          // supersedes is a different relationship that should NOT cascade)
          existing.status = 'superseded';
          existing.invalidAt = Date.now();
          return 'REPLACE';
        }
      }

      // Type II: Check dependency chain for cascading implications
      const deps = this.getDependencies(existing.id);
      for (const dep of deps) {
        for (const [key, newVal] of Object.entries(newNode.attributes)) {
          const depVal = dep.attributes[key];
          if (depVal !== undefined && String(depVal) !== String(newVal)) {
            // Potential cascading invalidation
            existing.status = 'stale';
            this.addEdge(newNode.id, existing.id, 'inferred', 'cascade_conflict', 0.6);
            return 'STALE';
          }
        }
      }
    }

    return 'KEEP';
  }

  /** GRADE-style saturation ratio */
  saturationRatio(): number {
    const n = this.nodes.size;
    if (n < 2) return 0;
    const maxEdges = (n * (n - 1)) / 2;
    return this.edges.length / maxEdges;
  }

  /** Query only adjudicated (non-stale) facts */
  queryActive(predicate: (n: MemoryNode) => boolean): MemoryNode[] {
    return Array.from(this.nodes.values())
      .filter(n => n.status === 'active' && predicate(n));
  }
}

// ==================== DEMO ====================

const graph = new ProvenanceGraph();

// Initial facts
graph.addNode({
  id: 'fact-1',
  content: 'User lives in Seattle',
  attributes: { city: 'Seattle', state: 'WA' },
  status: 'active',
  validAt: Date.now() - 86400000,
  recordedAt: Date.now() - 86400000,
  provenance: { writer: 'agent-1', source: 'conversationturn-3' }
});

graph.addNode({
  id: 'fact-2',
  content: 'User commutes by bicycle',
  attributes: { commute: 'bicycle', commuteTime: '30min' },
  status: 'active',
  validAt: Date.now() - 80000000,
  recordedAt: Date.now() - 80000000,
  provenance: { writer: 'agent-1', source: 'conversationturn-5', derivedFrom: ['fact-1'] }
});

graph.addNode({
  id: 'fact-3',
  content: 'User owns a road bike',
  attributes: { ownsEquipment: 'road-bike' },
  status: 'active',
  validAt: Date.now() - 70000000,
  recordedAt: Date.now() - 70000000,
  provenance: { writer: 'agent-2', source: 'conversationturn-8', derivedFrom: ['fact-2'] }
});

// Explicitly declare a dependency: commute depends on city (weather/terrain)
graph.addEdge('fact-2', 'fact-1', 'declared', 'commute_feasibility', 0.7);
graph.addEdge('fact-3', 'fact-2', 'declared', 'equipment_for_commute', 0.8);

console.log('=== Before invalidation ===');
console.log('Active facts:', graph.queryActive(n => true).map(n => n.content));

// New evidence: user moved to Portland (Type I direct conflict on fact-1)
const newFact: MemoryNode = {
  id: 'fact-4',
  content: 'User signed a lease in Portland',
  attributes: { city: 'Portland', state: 'OR' },
  status: 'active',
  validAt: Date.now(),
  recordedAt: Date.now(),
  provenance: { writer: 'agent-1', source: 'conversationturn-12' }
};

// CUPMem-style adjudication
const decision = graph.adjudicate(newFact, Array.from(graph.nodes.values()));
console.log(`\nAdjudication decision: ${decision}`);
graph.addNode(newFact);

// Propagate invalidation from fact-1 (city change)
const result = graph.propagate_invalidation('fact-1', 'city changed Seattle→Portland');

console.log('\n=== Cascade trace ===');
for (const step of result.trace) {
  const indent = '  '.repeat(step.depth);
  const node = graph.nodes.get(step.node);
  console.log(`${indent}depth=${step.depth} [${step.grade}] ${node?.content}`);
  console.log(`${indent}  reason: ${step.reason}`);
  console.log(`${indent}  status: ${node?.status}`);
}

console.log(`\n=== After invalidation ===`);
console.log('Invalidated/stale nodes:', result.invalidated);
console.log('Active facts:', graph.queryActive(n => true).map(n => n.content));
console.log('Saturation ratio ρ:', graph.saturationRatio().toFixed(3));

// Expected output:
// fact-1: invalidated (source)
// fact-2: stale (depends on fact-1 via commute_feasibility, weight=0.7)
// fact-3: stale (depends on fact-2 via equipment_for_commute, weight=0.8)
// Only fact-4 (Portland) remains active
```

---

## Key Insights

### Insight #163: Cascading invalidation is the unsolved problem — and the opportunity

STALE is the **first benchmark** to systematically isolate cascading invalidation (Type II). Every prior benchmark has × in that column. The best frontier model scores only 55.2% overall and worse on cascading cases. This means: **any system that solves cascading invalidation even partially has a defensible contribution**. For amg, `propagate_invalidation()` with explicit `depends_on` edges would be the **first npm library** with cascading correction capability. No competitor (Mem0, Zep, Letta, Cognee) has this.

### Insight #164: Write-side adjudication beats query-time cleverness by +13pp

CUPMem's central insight: don't try to resolve conflicts at query time — resolve them at **write time**. When new evidence arrives, an adjudicator decides KEEP/STALE/REPLACE/UNKNOWN before the fact enters the retrieval pool. This is architecturally identical to amg's existing `write_governance_check()` — but amg currently lacks the **propagation step** that extends the search beyond directly-touched slots to structurally affected regions via dependency topology. The gap between amg's current capability and CUPMem's is precisely `propagate_invalidation()`.

### Insight #165: The attachment grade is the missing inductive bias for dependency edges

GRADE's key discovery: not all dependency edges are equal. **Observed** edges (logged reads/writes) carry transferable failure-prediction signal. **Inferred** edges (assumed full-history) collapse to a function of run size — degenerate and non-transferable. The saturation ratio `ρ = |E_D| / (n choose 2)` separates the regimes: observed ~0.01 (sparse, informative), inferred ~1.0 (saturated, useless). For amg: `depends_on` edges should default to **declared** grade (the user/agent states the dependency), not inferred. An inferred full-history dependency layer would be actively misleading.

### Insight #166: Provenance collapse is the fourth failure mode — and amg already prevents it

MemClaw identifies "provenance collapse" (retrieved memories can't be traced to origin) as one of four fleet-memory failure modes. amg's existing bi-temporal edge tracking already records `validAt`, `recordedAt`, and source metadata. The missing piece is `derivedFrom` — a chain of provenance links that enables auditability. With `depends_on` edges carrying provenance metadata, amg would have a complete provenance graph: every fact traces back to its original source through a chain of declared dependencies. This is a **zero-cost extension** of the existing edge infrastructure.

### Insight #167: Contradiction detection pipeline ordering matters — dedup starves contradiction

MemClaw discovered a subtle production bug: a synchronous near-duplicate detector runs before the asynchronous contradiction detector. Since contradictory writes are naturally near-identical text ("X is A" vs "X is B"), the dedup gate rejects them with 409 before the contradiction detector ever sees them. This is an architectural lesson for amg: **contradiction detection must run before dedup**, or at minimum, the dedup threshold must be widened for writes carrying structural metadata (RDF triples / relation types). The fix is pipeline ordering, not algorithm improvement.

---

## Mapping to amg Implementation

### `depends_on` Edge Type (~20 lines)

```typescript
// Add to MemoryGraph.addEdge() — new kind
addDependsOn(
  childId: string,
  parentId: string,
  opts: {
    grade?: 'observed' | 'declared' | 'inferred';  // default: 'declared'
    reason?: string;                                  // WHY the dependency
    weight?: number;                                  // confidence [0,1], default 1.0
  } = {}
): void {
  this.addEdge(childId, parentId, {
    kind: 'depends_on',
    grade: opts.grade ?? 'declared',
    reason: opts.reason ?? 'derived_from',
    weight: opts.weight ?? 1.0,
    validAt: Date.now(),
    recordedAt: Date.now(),
  });
}
```

### `propagate_invalidation()` (~60 lines)

```typescript
propagate_invalidation(
  nodeId: string,
  opts: {
    reason?: string;
    maxDepth?: number;
    minWeight?: number;     // default 0.3
    markAs?: 'stale' | 'invalidated';  // default 'stale' (conservative)
  } = {}
): {
  invalidated: string[];
  trace: CascadeStep[];
} {
  // BFS reverse-traversal of depends_on edges
  // Mark each reached node as stale/invalidated
  // Respect maxDepth and minWeight thresholds
  // Return cascade trace for auditability
}
```

### Test Plan (~50 tests)

- Type I direct conflict → source invalidated, dependents stale
- Type II cascading conflict → upstream change propagates downstream
- Multi-hop cascade (depth=3+) with weight decay
- Cycle detection (A→B→A) — visited set prevents infinite loop
- minWeight threshold — low-weight edges don't cascade
- maxDepth cutoff — deep chains bounded
- markAs='stale' vs 'invalidated' — conservative vs aggressive
- No depends_on edges → no cascade (graceful no-op)
- Saturation ratio computation
- Bi-temporal: invalidAt timestamp recorded
- Provenance chain reconstruction via derivedFrom
- CUPMem adjudication integration with write_governance_check()

---

## Next Actions

1. **amg Cycle 336: `addDependsOn()` + `propagate_invalidation()`** — Implement the two APIs with ~50 tests. The code prototype above is the blueprint. Start with declared grade (user states dependency) and observed grade (trace logs).

2. **amg Cycle 337: `adjudicate_write()` enhancement** — Extend existing `write_governance_check()` to include CUPMem-style state adjudication. When new evidence arrives, check dependency chain for cascading implications. Decision: KEEP/STALE/REPLACE/UNKNOWN.

3. **STALE benchmark adapter** — Create `benchmarks/stale-adapter.ts` that converts STALE's 400 conflict scenarios into amg test cases. Run amg's propagation against Type II cascading conflicts. Target: beat CUPMem's 68%.

4. **GRADE-style saturation ratio diagnostic** — Add `dependency_saturation()` API that returns ρ for the graph's depends_on layer. Useful for diagnostic: if ρ approaches 1.0, the dependency layer is degenerate (inferred full-history) and should be replaced with observed/declared edges.

---

## References

| Paper | arXiv | Key Contribution |
|-------|-------|-----------------|
| STALE + CUPMem | 2605.06527 | First cascading invalidation benchmark. Type I/II taxonomy. Write-side adjudication. |
| GRADE | 2606.22741 | Two-layer execution+dependency graph. Attachment grade (observed/declared/inferred). Transfer signal. |
| MemClaw | 2606.24535 | Fleet-memory failure modes. Governed shared memory. Provenance graph. Contradiction pipeline ordering. |
| GUARDIAN | 2505.19234 (NeurIPS 2025) | Temporal graph for error propagation. Unsupervised anomaly detection. |
| AgentArmor | 2508.01249 | Program Dependency Graph (PDG) for agent security. Control + data flow analysis. |
| MAGMA | (2026) | Multi-graph: associative + causal + temporal + semantic layers. Adaptive traversal policy. |
| MemGraphRAG | 2606.00610 | Conflict Detection Agent + Conflict Resolution Agent with PPR propagation. |

---

## Quality Checklist

- [x] Core concepts: 5 (STALE types, GRADE layers, MemClaw failures, GUARDIAN temporal, CUPMem adjudication)
- [x] Code example: 1 complete TypeScript prototype (~200 lines, runnable, zero-dep)
- [x] Key insights: 5 (#163-#167)
- [x] Next actions: 4 specific implementation cycles
- [x] Relation to existing projects: amg (depends_on + propagate_invalidation), amg-bench (STALE adapter), write_governance_check (CUPMem integration)
- [x] Competitive positioning: No npm/PyPI competitor has cascading invalidation. First-mover advantage.
