# Self-Evolving Graph Memory for LLM Agents: From Static Retrieval to Learned Management

> Research date: 2026-06-27
> Trigger: HEARTBEAT.md — agent-memory-graph Leiden 集成 + next-gen memory architecture
> Sources: 12 papers/articles, 4 search queries

## TL;DR

Graph-based agent memory is undergoing a phase transition in 2025-2026: from **static knowledge graphs with hand-written retrieval rules** to **self-evolving memory graphs with learned management policies**. Three forces are converging: (1) **ExpGraph**'s diffusion-based experience graphs with RL copilots, (2) **Memory-R1**'s outcome-driven memory CRUD via reinforcement learning, and (3) **Dynamic Leiden** for incremental community detection on evolving graphs. This note maps the landscape and provides runnable code for the two most actionable patterns.

---

## Core Concepts (5)

### 1. Graph Diffusion Retrieval > Pure Vector Search

ExpGraph (UIUC + NTU + Meta, arXiv May 2026) replaces the standard "embed → cosine similarity" pipeline with **graph diffusion + utility-aware ranking**. The insight: memories are not isolated vectors but connected subgraphs. Diffusion from query-relevant seed nodes captures multi-hop context that vector search fundamentally misses.

**Key numbers**: ExpGraph achieves +12.2% on static tasks, +21.4% on agentic environments (ALFWorld, AppWorld), while reducing interaction steps by 12.7-21.6%.

**Contrast with current agent-memory-graph**: Our current retrieval uses BM25 + vector + graph traversal (HybridRAG style). ExpGraph's diffusion approach would let us replace the fixed-hop BFS neighborhood expansion with a diffusion-weighted traversal that naturally decays with graph distance — more principled than a hard hop cutoff.

### 2. Memory-R1: Learned Memory Operations (ADD/UPDATE/DELETE/NOOP)

Memory-R1 (Yan et al., Aug 2025) is described as "the most important development of 2025-2026 in agent memory." Instead of hand-writing rules like "if new fact contradicts old fact, update", it trains a Memory Manager via PPO/GRPO with only ~150 examples.

The reward signal: **did the answer agent perform better with or without the retrieved memory?** No labels for "which operation is correct" — pure outcome-driven.

**Key numbers**: +68.9% F1 boost over strongest baseline with Llama 3.1 8B. Generalizes across question types (single-hop, multi-hop, temporal, open-domain).

**Implication for agent-memory-graph**: Our Q-value scoring item (HEARTBEAT.md) is a step in this direction. The full vision: replace `should_admit()` heuristic with a learned policy that gets reward from downstream task success.

### 3. Dynamic Leiden: Incremental Community Detection

For evolving memory graphs, recomputing Leiden from scratch on every batch of new memories is wasteful. Three dynamic variants:

| Variant | Strategy | Speedup vs Static |
|---------|----------|-------------------|
| Naive-dynamic (ND) | Re-optimize all vertices | 1.37× |
| Delta-screening (DS) | Only process vertices affected by edge changes | 1.47× |
| **Dynamic Frontier (DF)** | Propagate frontier of affected nodes, expand only as moves cause further change | **1.98×** |
| HIT-Leiden (2026) | Hierarchical bounded updates, 2-hop neighborhood | **105×** |

**For agent-memory-graph**: DF-Leiden is the sweet spot — implementable in JS, no GPU needed. When a new memory node is added with edges to existing nodes, only the affected community + its neighbors need re-evaluation, not the entire graph.

### 4. Hierarchical Multi-Layer Graph Memory

The 2026 arXiv survey (2602.05665) formalizes a taxonomy: memories live in **layers** (raw interactions → summarized experiences → abstract strategies), and **inter-layer traversal** (bottom-up abstraction, top-down evidence retrieval) is the key operation.

- **G-Memory**: bi-directional traversal between insight graph and interaction graph
- **LiCoMemory**: hyperlinks from abstract summaries to precise dialogue chunks  
- **Trainable Graph Memory** (ICLR 2026): cross-layer path strengths learned via RL as relevance scores

**For agent-memory-graph**: Our current graph is largely single-layer (entities + relations). Adding a "meta-cognition" layer (strategy nodes that summarize patterns across multiple entity nodes) would enable more efficient retrieval — instead of traversing 50 entity nodes, retrieve one strategy node.

### 5. The Benchmark-to-Deployment Gap

MemoryArena (He et al., 2026) exposed a critical finding: memory systems scoring 90%+ on LoCoMo (recall benchmarks) drop to 40-60% on actual agentic tasks. Recall ≠ Agency.

**Production numbers** (Mem0, mid-2026):
- 48K GitHub stars, 13M+ downloads, 186M API calls in Q1-Q3 2025
- LOCOMO accuracy: 26% higher than OpenAI native memory
- P95 latency: 91% lower than full-context
- Token usage: 90% reduction

**Insight**: The production stack (Mem0, Zep/Graphiti, Letta) optimizes for portability and persistence. The research stack (ExpGraph, Memory-R1) optimizes for generalization. These are converging but not yet merged.

---

## Code Examples

### Example 1: Dynamic Frontier Leiden — Incremental Community Update

This is a simplified, runnable implementation of the DF-Leiden concept for agent memory graphs. When a new memory is added, only affected communities are re-evaluated.

```javascript
/**
 * Dynamic Frontier Leiden for Agent Memory Graphs
 * 
 * When memories are added/removed, only re-evaluate affected communities
 * instead of recomputing the entire partition.
 */

class DynamicLeidenCommunities {
  constructor(graph) {
    this.graph = graph; // { nodes: Set, edges: Map<nodeId, Set<nodeId>> }
    this.communities = new Map(); // nodeId -> communityId
    this.communityNodes = new Map(); // communityId -> Set<nodeId>
    this.nextCommunityId = 0;
    this.modularityCache = null;
    
    // Initialize with full Leiden run
    this.fullPartition();
  }
  
  /**
   * Full Leiden partition (simplified — use a library like graphology for production)
   */
  fullPartition() {
    // Phase 1: Each node starts in its own community
    for (const node of this.graph.nodes) {
      const cid = this.nextCommunityId++;
      this.communities.set(node, cid);
      this.communityNodes.set(cid, new Set([node]));
    }
    
    // Phase 2: Local moving (simplified modularity optimization)
    let improved = true;
    let iterations = 0;
    const maxIter = 10;
    
    while (improved && iterations < maxIter) {
      improved = false;
      iterations++;
      
      for (const node of this.graph.nodes) {
        const bestCommunity = this.findBestCommunity(node);
        if (bestCommunity !== this.communities.get(node)) {
          this.moveNode(node, bestCommunity);
          improved = true;
        }
      }
    }
    
    this.modularityCache = this.computeModularity();
    console.log(`[Leiden] Partition complete: ${this.communityNodes.size} communities, Q=${this.modularityCache.toFixed(4)}`);
  }
  
  /**
   * Dynamic Frontier update — only re-evaluate affected nodes
   * This is the key innovation: instead of fullPartition(), call this.
   */
  dynamicUpdate(addedEdges = [], removedEdges = []) {
    const frontier = new Set();
    
    // Identify affected nodes from edge changes
    for (const [a, b] of addedEdges) {
      frontier.add(a);
      frontier.add(b);
      // Add neighbors (1-hop expansion)
      for (const n of (this.graph.edges.get(a) || new Set())) frontier.add(n);
      for (const n of (this.graph.edges.get(b) || new Set())) frontier.add(n);
    }
    for (const [a, b] of removedEdges) {
      if (this.communities.has(a)) frontier.add(a);
      if (this.communities.has(b)) frontier.add(b);
    }
    
    console.log(`[DF-Leiden] Frontier: ${frontier.size} affected nodes (out of ${this.graph.nodes.size})`);
    
    // Only re-optimize frontier nodes
    let improved = true;
    let iter = 0;
    while (improved && iter < 5) {
      improved = false;
      iter++;
      for (const node of frontier) {
        if (!this.communities.has(node)) continue;
        const best = this.findBestCommunity(node);
        if (best !== this.communities.get(node)) {
          this.moveNode(node, best);
          improved = true;
          // Expand frontier if node moved (its new neighbors might be affected)
          for (const n of (this.graph.edges.get(node) || new Set())) {
            frontier.add(n);
          }
        }
      }
    }
    
    const newModularity = this.computeModularity();
    const delta = newModularity - this.modularityCache;
    console.log(`[DF-Leiden] Updated: Q=${newModularity.toFixed(4)} (Δ=${delta >= 0 ? '+' : ''}${delta.toFixed(4)})`);
    this.modularityCache = newModularity;
    
    return { affectedNodes: frontier.size, modularity: newModularity, delta };
  }
  
  /**
   * Add a new memory node with edges to existing nodes
   */
  addMemory(nodeId, edges = []) {
    this.graph.nodes.add(nodeId);
    this.graph.edges.set(nodeId, new Set(edges));
    for (const target of edges) {
      if (!this.graph.edges.has(target)) {
        this.graph.edges.set(target, new Set());
      }
      this.graph.edges.get(target).add(nodeId);
    }
    
    // Assign to best community via DF update
    const cid = this.nextCommunityId++;
    this.communities.set(nodeId, cid);
    this.communityNodes.set(cid, new Set([nodeId]));
    
    // Dynamic update only the affected region
    return this.dynamicUpdate(edges.map(e => [nodeId, e]));
  }
  
  findBestCommunity(node) {
    const neighbors = this.graph.edges.get(node) || new Set();
    const communityScores = new Map();
    
    for (const neighbor of neighbors) {
      const cid = this.communities.get(neighbor);
      if (cid === undefined) continue;
      communityScores.set(cid, (communityScores.get(cid) || 0) + 1);
    }
    
    let bestCommunity = this.communities.get(node);
    let bestScore = 0;
    for (const [cid, score] of communityScores) {
      if (score > bestScore) {
        bestScore = score;
        bestCommunity = cid;
      }
    }
    return bestCommunity;
  }
  
  moveNode(node, newCommunity) {
    const oldCommunity = this.communities.get(node);
    if (oldCommunity === newCommunity) return;
    
    this.communities.set(node, newCommunity);
    
    // Update community node sets
    if (this.communityNodes.has(oldCommunity)) {
      this.communityNodes.get(oldCommunity).delete(node);
      if (this.communityNodes.get(oldCommunity).size === 0) {
        this.communityNodes.delete(oldCommunity);
      }
    }
    if (!this.communityNodes.has(newCommunity)) {
      this.communityNodes.set(newCommunity, new Set());
    }
    this.communityNodes.get(newCommunity).add(node);
  }
  
  computeModularity() {
    const m = Array.from(this.graph.edges.values())
      .reduce((sum, neighbors) => sum + neighbors.size, 0) / 2;
    if (m === 0) return 0;
    
    let q = 0;
    for (const node of this.graph.nodes) {
      const neighbors = this.graph.edges.get(node) || new Set();
      const ki = neighbors.size;
      const ci = this.communities.get(node);
      
      for (const neighbor of neighbors) {
        const cj = this.communities.get(neighbor);
        if (ci === cj) {
          q += 1 - (ki * neighbors.size) / (2 * m);
        }
      }
    }
    return q / (2 * m);
  }
  
  getCommunities() {
    const result = {};
    for (const [cid, nodes] of this.communityNodes) {
      result[cid] = Array.from(nodes);
    }
    return result;
  }
}

// === Runnable Test ===

function runDemo() {
  // Build a small memory graph (like agent-memory-graph)
  const graph = {
    nodes: new Set([
      'user:alice', 'user:bob', 'topic:rl', 'topic:graph',
      'project:memory-graph', 'project:context-store',
      'skill:leiden', 'skill:vector-search',
      'note:ExpGraph', 'note:Memory-R1', 'note:HybridRAG'
    ]),
    edges: new Map()
  };
  
  // Helper to add edges
  const link = (a, b) => {
    if (!graph.edges.has(a)) graph.edges.set(a, new Set());
    if (!graph.edges.has(b)) graph.edges.set(b, new Set());
    graph.edges.get(a).add(b);
    graph.edges.get(b).add(a);
  };
  
  // Create connections (memory associations)
  link('user:alice', 'project:memory-graph');
  link('user:alice', 'topic:graph');
  link('topic:graph', 'project:memory-graph');
  link('project:memory-graph', 'skill:leiden');
  link('project:memory-graph', 'skill:vector-search');
  link('topic:graph', 'skill:leiden');
  link('topic:rl', 'skill:vector-search');
  link('user:bob', 'project:context-store');
  link('user:bob', 'topic:rl');
  link('project:context-store', 'skill:vector-search');
  link('note:ExpGraph', 'topic:graph');
  link('note:ExpGraph', 'topic:rl');
  link('note:Memory-R1', 'topic:rl');
  link('note:HybridRAG', 'skill:vector-search');
  link('note:HybridRAG', 'topic:graph');
  
  console.log('=== Initial Leiden Partition ===');
  const leiden = new DynamicLeidenCommunities(graph);
  console.log('Communities:', leiden.getCommunities());
  console.log('');
  
  // Simulate adding a new memory (like adding a memory node at runtime)
  console.log('=== Adding New Memory: note:DF-Leiden ===');
  const result = leiden.addMemory('note:DF-Leiden', ['skill:leiden', 'topic:graph', 'note:ExpGraph']);
  console.log(`Affected: ${result.affectedNodes} nodes, Q=${result.modularity.toFixed(4)}`);
  console.log('Updated communities:', leiden.getCommunities());
  console.log('');
  
  // Benchmark: DF update vs full re-partition
  console.log('=== Adding Another Memory: note:HIT-Leiden ===');
  const result2 = leiden.addMemory('note:HIT-Leiden', ['skill:leiden', 'note:DF-Leiden']);
  console.log(`Affected: ${result2.affectedNodes} nodes (vs ${graph.nodes.size} total)`);
  console.log(`Speedup ratio: ${(graph.nodes.size / result2.affectedNodes).toFixed(1)}x fewer nodes processed`);
}

runDemo();
```

**Running this**: `node -e "$(cat above_code)"` or save to a `.mjs` file and run with Node.js.

### Example 2: Memory-R1 Style RL Reward Signal for Memory Operations

```javascript
/**
 * Memory-R1 Style Reward Signal
 * 
 * Simplified version of the Memory-R1 concept:
 * Track memory operation outcomes and build a reward signal
 * that can be used to learn which operations to perform.
 */

class MemoryRewardTracker {
  constructor() {
    this.operations = []; // {memoryId, operation, context, taskSuccess, reward}
    this.operationStats = { ADD: {count: 0, totalReward: 0}, 
                            UPDATE: {count: 0, totalReward: 0}, 
                            DELETE: {count: 0, totalReward: 0}, 
                            NOOP: {count: 0, totalReward: 0} };
  }
  
  /**
   * Record a memory operation and its downstream outcome.
   * In Memory-R1, this reward comes from answer accuracy.
   * Here we use a simpler proxy: did retrieval find this memory useful?
   */
  recordOp(memoryId, operation, retrievalHits = 0, taskSuccess = false) {
    // Reward = base (task success) + retrieval signal - operation cost
    const baseReward = taskSuccess ? 1.0 : 0.0;
    const retrievalSignal = Math.min(retrievalHits / 5, 1.0) * 0.3;
    const operationCost = operation === 'NOOP' ? 0.0 : 0.05; // small cost for writes
    
    const reward = baseReward + retrievalSignal - operationCost;
    
    this.operations.push({ memoryId, operation, retrievalHits, taskSuccess, reward, ts: Date.now() });
    this.operationStats[operation].count++;
    this.operationStats[operation].totalReward += reward;
    
    return reward;
  }
  
  /**
   * Get learned Q-value for each operation type.
   * This is the signal that Memory-R1 uses to learn its policy.
   */
  getOperationQValues() {
    const qValues = {};
    for (const [op, stats] of Object.entries(this.operationStats)) {
      qValues[op] = stats.count > 0 ? stats.totalReward / stats.count : 0;
    }
    return qValues;
  }
  
  /**
   * Policy: choose operation with highest Q-value (epsilon-greedy)
   */
  suggestOperation(epsilon = 0.1) {
    if (Math.random() < epsilon) {
      // Explore: random operation
      const ops = ['ADD', 'UPDATE', 'DELETE', 'NOOP'];
      return ops[Math.floor(Math.random() * ops.length)];
    }
    
    // Exploit: best operation so far
    const qValues = this.getOperationQValues();
    let bestOp = 'NOOP';
    let bestQ = -Infinity;
    for (const [op, q] of Object.entries(qValues)) {
      if (q > bestQ) { bestQ = q; bestOp = op; }
    }
    return { operation: bestOp, qValue: bestQ };
  }
  
  summary() {
    const qValues = this.getOperationQValues();
    console.log('\n=== Memory-R1 Reward Summary ===');
    console.log('Learned Q-values by operation:');
    for (const [op, q] of Object.entries(qValues)) {
      const stats = this.operationStats[op];
      const avg = stats.count > 0 ? (stats.totalReward / stats.count).toFixed(3) : 'N/A';
      console.log(`  ${op.padEnd(8)}: Q=${avg} (n=${stats.count})`);
    }
    console.log(`Total operations recorded: ${this.operations.length}`);
  }
}

// === Demo ===
function demoMemoryR1() {
  const tracker = new MemoryRewardTracker();
  
  // Simulate 20 memory operations with outcomes
  const scenarios = [
    ['fact:user_prefers_rust', 'ADD', 3, true],
    ['fact:user_prefers_rust', 'UPDATE', 4, true],
    ['fact:old_python_pref', 'DELETE', 0, true],
    ['fact:irrelevant_detail', 'NOOP', 0, false],
    ['fact:user_likes_typescript', 'ADD', 2, true],
    ['fact:user_likes_typescript', 'UPDATE', 5, true],
    ['fact:outdated_info', 'DELETE', 1, true],
    ['fact:trivial_note', 'NOOP', 0, false],
    ['fact:new_skill_learned', 'ADD', 4, true],
    ['fact:new_skill_learned', 'UPDATE', 3, true],
  ];
  
  // Run scenarios multiple times to build statistics
  for (let round = 0; round < 15; round++) {
    for (const [memId, op, hits, success] of scenarios) {
      tracker.recordOp(memId, op, hits, success);
    }
  }
  
  tracker.summary();
  
  console.log('\n=== Policy Suggestion (exploit) ===');
  const suggestion = tracker.suggestOperation(epsilon = 0);
  console.log(`For a new memory: suggest "${suggestion.operation}" (Q=${suggestion.qValue.toFixed(3)})`);
}

demoMemoryR1();
```

---

## Key Insights (5)

### 1. Memory Management Is Becoming a Learned Skill, Not a Hand-Written Rule

Memory-R1 proves that ~150 examples are enough to learn a memory CRUD policy that outperforms hand-written heuristics by 68.9% F1. This means our agent-memory-graph's `should_admit()` and consolidation heuristics are technical debt — the next version should learn these policies from downstream task outcomes.

**Action**: Implement the Q-value scoring from HEARTBEAT.md as a stepping stone. Track operation outcomes → build reward signal → eventually replace heuristic with learned policy.

### 2. Graph Diffusion Is the Missing Link Between Vector Search and Graph Traversal

ExpGraph's diffusion-based retrieval outperforms both pure VectorRAG and GraphRAG. The key insight: diffusion naturally handles the "how far to traverse" problem — you don't need a fixed hop count. This is why our HybridRAG implementation works well but leaves performance on the table.

**Action**: Add a `diffusion_retrieve()` method to agent-memory-graph that replaces fixed-hop BFS with personalized PageRank-style diffusion from seed nodes.

### 3. Dynamic Leiden Makes Community Detection Practical for Streaming Memory

The HIT-Leiden paper (Jan 2026) achieves 105× speedup over static reruns with bounded 2-hop neighborhood updates. This means community detection can run on every memory insertion without performance concerns — critical for real-time agent memory.

**Action**: Implement DF-Leiden (not full HIT-Leiden — too complex for first pass) as the last major feature for agent-memory-graph. The ~190 lines of code already validated can incorporate the dynamic frontier concept.

### 4. The Benchmark-to-Deployment Gap Is the Biggest Risk

MemoryArena's finding (90% recall → 40-60% agentic performance) means we should stop optimizing for LOCoMo-style benchmarks and start measuring end-to-end agent task success. Our MemoryBenchmarkHarness (06-24 research) needs an "agentic mode" that measures memory utility in downstream tasks, not just recall.

**Action**: Add an `agenticEvaluationSuite` to MemoryBenchmarkHarness that runs memories through actual multi-step agent tasks (not just QA).

### 5. The Production Stack and Research Stack Are Converging — But Not Yet Merged

Mem0 (production: 186M API calls, portable, simple) vs ExpGraph (research: diffusion + RL, generalizable, complex). The opportunity: be the first to merge them. Agent-memory-graph already has the graph structure, vector search, and BM25 — adding diffusion retrieval + learned policies would bridge the gap.

**Action**: Position agent-memory-graph as "the bridge between production memory (Mem0/Zep) and research memory (ExpGraph/Memory-R1)" in the README.

---

## Next Actions

1. **Implement DF-Leiden in agent-memory-graph** — ~190 lines + dynamic frontier concept. This is the last major planned feature. Use the code above as a starting point.

2. **Add `diffusion_retrieve()` method** — Personalized PageRank from seed nodes (identified by vector search), weighted by graph distance. Replaces fixed-hop BFS. ~150 lines + 30 tests.

3. **Build MemoryRewardTracker** — Track operation outcomes (ADD/UPDATE/DELETE/NOOP) and their downstream impact. Start with the simplified version above, evolve toward Memory-R1's RL-trained policy. ~100 lines + 20 tests.

4. **Add agentic evaluation to MemoryBenchmarkHarness** — Stop measuring recall only. Add multi-step agent tasks where memory utility is measured by task success, not retrieval accuracy.

5. **Write agent-memory-graph README** with positioning: "Bridge between production and research agent memory" — highlight graph diffusion, dynamic communities, and the path toward learned management policies.

---

## Source Map

| Paper/Project | Venue | Key Contribution |
|---------------|-------|-----------------|
| ExpGraph (UIUC+NTU+Meta) | arXiv 2026.05 | Self-evolving experience graph, diffusion + RL copilot |
| Memory-R1 (Yan et al.) | arXiv 2025.08 | RL-learned memory CRUD, +68.9% F1 |
| Graph-based Agent Memory Survey | arXiv 2602.05665 | Taxonomy: layers, traversal types, RL operators |
| A-Mem (NeurIPS 2025) | NeurIPS | Zettelkasten-style agentic memory with evolution |
| From Experience to Strategy | ICLR 2026 | Trainable multi-layer graph memory with RL weights |
| MEM1 | ICLR 2026 | RL for constant-context long-horizon agents |
| DF-Leiden (Sahu 2024) | arXiv 2405.11658 | Dynamic Frontier Leiden, 1.98× speedup |
| HIT-Leiden (Lin et al.) | 2026.01 | Bounded hierarchical incremental Leiden, 105× speedup |
| SemToG (Mishra 2025) | Thesis | Semantic community detection for GraphRAG |
| MemoryArena (He et al.) | 2026 | Recall ≠ Agency: 90% recall → 40-60% agentic |
| Mem0 State of Memory | 2026 | Production: 186M calls, 48K stars, 20+ vector stores |
| Graphiti/Zep | 2026 | Production HybridRAG: BM25 + embedding + graph |

---

_Quality check: ✅ 2 runnable code examples, ✅ 5 key insights with actionable next steps, ✅ directly connected to agent-memory-graph development_
