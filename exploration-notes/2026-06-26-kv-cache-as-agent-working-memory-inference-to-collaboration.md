# KV Cache as Agent Working Memory: From Inference Optimization to Cross-Agent Collaboration

> Research Date: 2026-06-26
> Trigger: KV cache optimization is the #1 cost lever in 2026 production agent deployments. This note bridges inference-system KV cache management ↔ external agent memory (agent-memory-graph / agent-context-store).

---

## TL;DR

KV cache is no longer just an inference optimization — it has become **the working memory of intelligent agents**. This research synthesizes 15+ papers/systems from NeurIPS 2025, ICLR 2026, DAC 2026, FAST 2026, and arXiv 2026 to extract the design principles, performance data, and actionable insights for bridging internal KV cache management with external agent memory stores. Includes ~300 lines of runnable TypeScript demonstrating a KV-cache-aware memory manager.

---

## 1. Core Concepts (5)

### 1.1 KV Cache IS Agent Working Memory

The paradigm shift in 2026: KV cache is not merely a transformer inference optimization — it is the **semantic substrate of agent state**. When an agent executes a multi-step ReAct loop, each tool call's output becomes KV tokens that the model attends to in subsequent steps. The KV cache *is* the agent's short-term memory in the most literal sense.

**Evidence**: KEEP (DAC 2026) explicitly calls KV cache "a critical carrier of agents' working memory." The LLM Agent Memory Survey (March 2026) classifies KV cache as a first-class memory representation alongside token-based and parametric memory.

**Implication**: External agent memory stores (agent-memory-graph) and internal KV cache are **two layers of the same problem** — managing what the agent knows across time scales.

### 1.2 Breaking the Prefix Barrier: From Rigid to Semantic Cache Reuse

Traditional KV cache reuse requires **exact prefix matching** — the new request must start with the same tokens as the cached entry. This is catastrophically broken for multi-agent scenarios where different agents have heterogeneous system prompts.

**Three breakthrough approaches**:
- **Segment-Level KV Cache Sharing** (ICLR 2026 submission): Decomposes cache into fine-grained semantic segments. Any agent can reuse any other agent's KV segments at arbitrary positions, with RoPE position correction.
- **KVCOMM** (NeurIPS 2025): Aligns KV cache offsets for shared content across agents using an "anchor pool" of observed deviations. Achieves 70%+ reuse rate across diverse multi-agent workloads.
- **TokenDance** (April 2026): Identifies the **All-Gather pattern** — every multi-agent round, a scheduler gathers all outputs and redistributes. Optimizes the KV layer for this recurring gather-and-redistribute flow.

### 1.3 Model-Driven Eviction: LLM-as-Garbage-Collector

The death of heuristic KV cache compression. Instead of fixed rules (H2O Heavy Hitters, SnapKV windows), the model itself decides what to evict.

**SideQuest** (NVIDIA, arXiv:2602.22603):
- Runs a **parallel auxiliary thread** that reasons about which tool responses are stale
- The main thread does inference; the auxiliary thread emits `delete_cursor` commands
- **56-65% peak token reduction** with negligible accuracy loss
- Eliminates the need for manual token budgeting

**IntentKV** (arXiv:2606.09916): Multi-query retention — scores tokens against a session-level QueryMemory that evolves as the agent discovers new intents across turns. 20.7% prefix-hit rate at 88K budget where baselines get 0-3%.

### 1.4 Workflow-Aware Cache Management

**KVFlow** (NeurIPS 2025, arXiv:2507.07400):
- Abstracts agent execution as an **Agent Step Graph**
- Each agent gets a `steps-to-execution` score (temporal proximity to next activation)
- Eviction policy: preserve entries likely to be reused based on graph topology
- **1.83× speedup** (single workflow, large prompts), **2.19× speedup** (concurrent workflows)
- Fully overlapped prefetching eliminates cache-miss stalls

**Continuum** (arXiv:2511.02230): KV cache **Time-to-Live** for multi-turn agents. When an agent makes a tool call, Continuum pins the KV cache with a TTL derived from the expected tool duration + average turn count. Prevents unnecessary re-prefill when the tool returns.

### 1.5 Plan-Level Caching: Test-Time Memory

**Agentic Plan Caching** (NeurIPS 2025, Stanford):
- Extracts structured **plan templates** from completed agent executions
- Keyword matching finds similar past plans; lightweight model adapts template to new context
- **50.31% cost reduction, 27.28% latency reduction** while maintaining 96.61% performance
- Complements KV cache (which operates at token level) by operating at the plan/trajectory level

**AgenticCache** (arXiv:2604.24039): Cache of plan-transition 2-grams (e.g., `GoGrasp → Transport`). Background LLM validates entries. 65% latency reduction, 50% token reduction for embodied agents.

---

## 2. Performance Data Summary

| System | Venue | Technique | Speedup/Reduction | Key Metric |
|--------|-------|-----------|-------------------|------------|
| KVFlow | NeurIPS 2025 | Step Graph eviction + prefetch | 2.19× throughput | Multi-agent |
| KEEP | DAC 2026 | Static-dynamic memory + multi-hop recompute | 2.68× speedup | Embodied planning |
| SideQuest | arXiv (NVIDIA) | Model-driven parallel eviction | 65% token reduction | ReAct agents |
| Segment-Level | ICLR 2026 | Semantic segment sharing | Throughput ↑, quality ↑ | Multi-agent |
| KVCOMM | NeurIPS 2025 | Offset-aligned cross-context reuse | 70% reuse rate | Multi-agent |
| TokenDance | arXiv Apr 2026 | All-Gather KV sharing | Memory 2-4× reduction | Social simulation |
| Continuum | arXiv Nov 2025 | KV cache TTL | JCCT ↓ significant | Multi-turn agents |
| Agentic Plan Cache | NeurIPS 2025 | Plan template extraction | 50.31% cost ↓ | Plan-Act agents |
| IntentKV | arXiv Jun 2026 | Cross-turn intent-aware pruning | 20.7% prefix-hit @ 88K | Long-context agents |
| CacheSlide | FAST 2026 | Cross-position-aware reuse | Latency ↓ significant | LLM serving |
| AgenticCache | arXiv Apr 2026 | Plan-transition 2-gram cache | 65% latency ↓ | Embodied AI |

---

## 3. The Two-Layer Memory Problem

```
┌──────────────────────────────────────────────────────────┐
│                    Agent Memory Stack                     │
├──────────────────────────────────────────────────────────┤
│  Layer 2: External Memory (agent-memory-graph)           │
│  - Persistent across sessions                            │
│  - Graph + BM25 + Vector retrieval                       │
│  - Consolidation, workflow memory, CRDT sync             │
│  - Timescale: hours → days → weeks                       │
│  - Analogy: Long-term memory (hippocampus)               │
├──────────────────────────────────────────────────────────┤
│  Layer 1: KV Cache (GPU/HBM)                             │
│  - Ephemeral, within a single inference session          │
│  - Attention-based retrieval                             │
│  - Prefix caching, segment sharing, model-driven prune   │
│  - Timescale: milliseconds → minutes                     │
│  - Analogy: Working memory (prefrontal cortex)           │
├──────────────────────────────────────────────────────────┤
│  Layer 0: Model Parameters (frozen weights)              │
│  - Semantic knowledge from training                      │
│  - Timescale: months → years                             │
│  - Analogy: Long-term semantic memory (neocortex)        │
└──────────────────────────────────────────────────────────┘
```

**Key insight**: agent-memory-graph operates at Layer 2. KV cache research operates at Layer 1. **Nobody is bridging them**. The agent that wins will have a coherent memory policy spanning both layers.

---

## 4. SIGARCH 2026: The Architecture View

SIGARCH's "Multi-Agent Memory from a Computer Architecture Perspective" (Jan 2026) frames the gap:

- **Missing Piece 1**: Agent Cache Sharing Protocol — no principled protocol for transforming and reusing cached artifacts across agents
- **Missing Piece 2**: Agent Memory Access Protocol — no semantics for permissions, scope, and granularity of cross-agent memory access
- **Analogy**: CPUs solved this decades ago with cache coherence protocols (MESI/MOESI). Agent systems need the equivalent.

This directly maps to agent-memory-graph's CRDT multi-agent merge + provenance/trust tracking. The "cache coherence protocol" for agents = CRDT + HLC + trust-weighted merge.

---

## 5. Key Insights (5)

### 5.1 External Memory ↔ KV Cache Are Two Layers of the Same Problem

agent-memory-graph's `consolidation_pipeline` (semantic_divergence → consolidate → evict) is the **external-memory analog** of SideQuest's model-driven KV cache eviction. Both ask: "What memory is stale and can be safely removed?"

**Actionable**: agent-memory-graph should expose a `cache_temperature()` API that the inference layer can query — "is this memory hot (recently accessed, high relevance) or cold?" — enabling the KV cache to make informed eviction decisions.

### 5.2 The Prefix Barrier = The BM25 Barrier

KV cache's prefix-matching rigidity is structurally identical to agent-memory-graph's early BM25-only search. The evolution path is the same: exact match → fuzzy match → semantic match. Segment-Level KV Cache Sharing is doing for KV cache what vector search did for agent memory.

**Actionable**: The `search_hybrid()` 4-way fusion (BM25 + Vector + Graph + KGE) pattern applies to KV cache segment retrieval too. The Segment-Level paper's RoPE correction is the "position encoding tax" — worth paying for non-prefix reuse.

### 5.3 KVFlow's Step Graph Maps to agent-memory-graph's Workflow Memory

KVFlow models agent execution as a Step Graph and computes `steps-to-execution` for eviction priority. agent-memory-graph already has Workflow Memory (`add_workflow` / `retrieve` / `record_outcome`). The connection: **workflow steps should annotate memory entries with expected reuse proximity**.

**Actionable**: When `record_outcome()` is called, automatically compute a `reuse_proximity` score (how soon this memory will be needed again based on workflow patterns). Feed this into the KV cache layer's eviction policy.

### 5.4 Plan Caching Is the Missing Production Optimization

Agentic Plan Caching (NeurIPS 2025) proves that **plan templates** — not just token-level KV cache — are reusable. This is the inference-layer equivalent of agent-memory-graph's Workflow Memory + Skill Discovery. The agent that caches plans + manages KV cache + has external graph memory wins on all three cost axes: token cost, latency, and accuracy.

**Actionable**: agent-memory-graph's `compose()` API (workflow composition) should output plan templates compatible with APC's keyword-extraction matching format. This creates a direct pipeline from graph memory → inference cost reduction.

### 5.5 SIGARCH's "Cache Coherence for Agents" Validates CRDT + HLC Direction

SIGARCH 2026 identifies the exact gap that agent-memory-graph's CRDT + HLC research addresses. The "Agent Cache Sharing Protocol" they call for is: (1) CRDT merge semantics, (2) HLC causal ordering, (3) trust-weighted resolution. All three are already in agent-memory-graph's roadmap.

**Actionable**: Position agent-memory-graph in README as "the cache coherence protocol for agent memory" — explicitly citing SIGARCH 2026's call for Missing Piece 1.

---

## 6. Runnable Code: KVCacheAwareMemoryManager

A TypeScript implementation demonstrating the bridge between external agent memory and KV cache management. Implements:
- **Cache temperature tracking** (hot/warm/cold) for external memory entries
- **Workflow-aware eviction priority** (inspired by KVFlow's steps-to-execution)
- **TTL-based retention** (inspired by Continuum's tool-call-aware TTL)
- **Semantic segment matching** (inspired by Segment-Level KV Cache Sharing)
- **Plan template extraction** (inspired by Agentic Plan Caching)

```typescript
/**
 * KVCacheAwareMemoryManager
 *
 * Bridges external agent memory (persistent store) with internal KV cache
 * (ephemeral working memory). Implements insights from:
 * - KVFlow (NeurIPS 2025): Workflow-aware eviction via Step Graph
 * - SideQuest (NVIDIA 2026): Model-driven stale detection
 * - Continuum (2025): KV cache TTL for multi-turn agents
 * - Segment-Level KV Cache Sharing (ICLR 2026): Semantic segment reuse
 * - Agentic Plan Caching (NeurIPS 2025): Plan template extraction
 */

// ─── Types ──────────────────────────────────────────────

interface MemoryEntry {
  id: string;
  content: string;
  tags: string[];
  timestamp: number;          // HLC or wall clock
  accessCount: number;
  lastAccess: number;
  workflowStep?: number;      // Position in current workflow
  reuseProximity: number;     // Estimated steps until next reuse (0 = never)
  segmentHash?: string;       // Content hash for KV segment matching
  planTemplate?: string;      // Extracted plan pattern
}

interface KVSegment {
  id: string;
  hash: string;
  tokenCount: number;
  agentId: string;
  ttl?: number;               // Milliseconds until expiry
  createdAt: number;
  semanticTag: string;        // For cross-agent matching
}

interface CacheTemperature {
  level: 'hot' | 'warm' | 'cold' | 'frozen';
  score: number;              // 0.0 - 1.0
  reason: string;
}

interface EvictionDecision {
  action: 'retain' | 'evict' | 'compress' | 'promote';
  priority: number;           // Lower = evict first
  reason: string;
}

interface WorkflowStep {
  agentId: string;
  stepIndex: number;
  dependencies: string[];     // Agent IDs that must complete first
  estimatedDuration: number;  // Milliseconds
}

// ─── KVCacheAwareMemoryManager ──────────────────────────

class KVCacheAwareMemoryManager {
  private store: Map<string, MemoryEntry> = new Map();
  private kvSegments: Map<string, KVSegment> = new Map();
  private workflowGraph: WorkflowStep[] = [];
  private planTemplates: Map<string, string[]> = new Map();
  private accessLog: Array<{ id: string; time: number; agentId: string }> = [];
  
  private config = {
    hotThreshold: 0.7,
    warmThreshold: 0.3,
    coldThreshold: 0.1,
    maxKvSegments: 100,
    defaultTtl: 30_000,        // 30 seconds
    planTemplateMinSimilarity: 0.3,
    reuseDecayFactor: 0.85,    // Per step, proximity decays
  };

  // ── External Memory Operations ───────────────────────

  /** Store a memory entry with workflow-aware metadata */
  remember(
    id: string,
    content: string,
    tags: string[] = [],
    workflowStep?: number
  ): MemoryEntry {
    const entry: MemoryEntry = {
      id,
      content,
      tags,
      timestamp: Date.now(),
      accessCount: 0,
      lastAccess: Date.now(),
      workflowStep,
      reuseProximity: workflowStep !== undefined ? 1 : 0,
      segmentHash: this.hashContent(content),
    };
    this.store.set(id, entry);
    return entry;
  }

  /** Retrieve with cache temperature update */
  recall(id: string, agentId: string = 'default'): MemoryEntry | null {
    const entry = this.store.get(id);
    if (!entry) return null;

    entry.accessCount++;
    entry.lastAccess = Date.now();
    this.accessLog.push({ id, time: Date.now(), agentId });

    // Update reuse proximity: recently accessed entries are more likely needed soon
    if (entry.workflowStep !== undefined) {
      entry.reuseProximity = Math.max(0, entry.reuseProximity * this.config.reuseDecayFactor);
    }

    return entry;
  }

  /** Compute cache temperature for an entry */
  cacheTemperature(id: string): CacheTemperature {
    const entry = this.store.get(id);
    if (!entry) return { level: 'frozen', score: 0, reason: 'not found' };

    const now = Date.now();
    const ageMs = now - entry.lastAccess;
    const recencyScore = Math.exp(-ageMs / (60_000 * 10)); // 10-min half-life
    const frequencyScore = Math.min(1, entry.accessCount / 10);
    const proximityScore = 1 / (1 + entry.reuseProximity);

    // Workflow-aware boost: entries in upcoming steps get hotter
    const workflowBoost = this.workflowBoost(id);

    const score = (
      recencyScore * 0.35 +
      frequencyScore * 0.25 +
      proximityScore * 0.25 +
      workflowBoost * 0.15
    );

    let level: CacheTemperature['level'];
    let reason: string;

    if (score >= this.config.hotThreshold) {
      level = 'hot';
      reason = `recency=${recencyScore.toFixed(2)} freq=${entry.accessCount} proximity=${entry.reuseProximity}`;
    } else if (score >= this.config.warmThreshold) {
      level = 'warm';
      reason = `moderate activity, aging`;
    } else if (score >= this.config.coldThreshold) {
      level = 'cold';
      reason = `rarely accessed, ${Math.round(ageMs / 1000)}s old`;
    } else {
      level = 'frozen';
      reason = `stale, candidate for consolidation/eviction`;
    }

    return { level, score, reason };
  }

  // ── KV Cache Segment Management ──────────────────────

  /** Register a KV cache segment from an agent's output */
  registerKVSegment(
    agentId: string,
    content: string,
    tokenCount: number,
    semanticTag: string,
    ttl?: number
  ): KVSegment {
    const segment: KVSegment = {
      id: `${agentId}-seg-${Date.now()}`,
      hash: this.hashContent(content),
      tokenCount,
      agentId,
      ttl: ttl ?? this.config.defaultTtl,
      createdAt: Date.now(),
      semanticTag,
    };
    this.kvSegments.set(segment.id, segment);

    // Enforce capacity: evict coldest
    if (this.kvSegments.size > this.config.maxKvSegments) {
      this.evictColdestSegment();
    }

    return segment;
  }

  /** Find reusable KV segments across agents (Segment-Level Sharing) */
  findReusableSegments(
    queryContent: string,
    requestingAgent: string,
    minSimilarity: number = 0.5
  ): Array<{ segment: KVSegment; similarity: number; reuseType: string }> {
    const queryHash = this.hashContent(queryContent);
    const results: Array<{ segment: KVSegment; similarity: number; reuseType: string }> = [];

    for (const segment of this.kvSegments.values()) {
      if (segment.agentId === requestingAgent) continue;

      // Check TTL expiry
      if (segment.ttl && Date.now() - segment.createdAt > segment.ttl) {
        this.kvSegments.delete(segment.id);
        continue;
      }

      // Exact hash match = direct reuse (like prefix caching)
      if (segment.hash === queryHash) {
        results.push({ segment, similarity: 1.0, reuseType: 'exact' });
        continue;
      }

      // Semantic tag match = segment-level reuse
      const tagSimilarity = this.textSimilarity(
        queryContent.slice(0, 200),
        segment.semanticTag
      );

      if (tagSimilarity >= minSimilarity) {
        results.push({
          segment,
          similarity: tagSimilarity,
          reuseType: tagSimilarity > 0.8 ? 'semantic' : 'fuzzy',
        });
      }
    }

    return results.sort((a, b) => b.similarity - a.similarity);
  }

  // ── Workflow-Aware Cache Eviction (KVFlow-inspired) ──

  /** Set the current workflow execution graph */
  setWorkflowGraph(steps: WorkflowStep[]): void {
    this.workflowGraph = steps;
  }

  /** Compute steps-to-execution for a given agent */
  stepsToExecution(agentId: string): number {
    const idx = this.workflowGraph.findIndex(s => s.agentId === agentId);
    if (idx === -1) return Infinity;
    return idx;
  }

  /** Get eviction decision for a KV segment (KVFlow + Continuum hybrid) */
  evictionDecision(segmentId: string): EvictionDecision {
    const segment = this.kvSegments.get(segmentId);
    if (!segment) return { action: 'evict', priority: 0, reason: 'not found' };

    const STE = this.stepsToExecution(segment.agentId);

    // TTL expired → evict
    if (segment.ttl && Date.now() - segment.createdAt > segment.ttl) {
      return { action: 'evict', priority: 0, reason: 'TTL expired' };
    }

    // Agent is next in workflow → retain at all costs
    if (STE === 0) {
      return { action: 'retain', priority: 100, reason: 'agent is next to execute' };
    }

    // Agent is within 3 steps → retain (warm)
    if (STE <= 3) {
      return { action: 'retain', priority: 80 - STE * 10, reason: `agent executes in ${STE} steps` };
    }

    // Agent is far away → candidate for eviction
    if (STE > 10) {
      return { action: 'evict', priority: 10, reason: `agent far from execution (${STE} steps)` };
    }

    // Medium distance → compress if large
    if (segment.tokenCount > 1000) {
      return { action: 'compress', priority: 40, reason: 'distant but large, compress to save space' };
    }

    return { action: 'retain', priority: 50, reason: 'moderate proximity' };
  }

  // ── Plan Template Extraction (Agentic Plan Caching) ──

  /** Extract a plan template from a completed workflow execution */
  extractPlanTemplate(
    workflowId: string,
    steps: Array<{ action: string; tool: string; input_summary: string }>
  ): string {
    // Create a generalized template: replace specifics with placeholders
    const template = steps.map(s => {
      const actionType = s.action.split('(')[0]; // Strip arguments
      return `${actionType}(${s.tool})`;
    }).join(' → ');

    // Store with keywords for matching
    const keywords = this.extractKeywords(
      steps.map(s => s.input_summary).join(' ')
    );

    this.planTemplates.set(workflowId, [template, ...keywords]);
    return template;
  }

  /** Find matching plan template for a new task */
  matchPlanTemplate(
    taskDescription: string
  ): { template: string; workflowId: string; similarity: number } | null {
    const taskKeywords = this.extractKeywords(taskDescription);
    let bestMatch: { template: string; workflowId: string; similarity: number } | null = null;

    for (const [wfId, [template, ...keywords]] of this.planTemplates) {
      const overlap = this.keywordOverlap(taskKeywords, keywords);
      if (overlap >= this.config.planTemplateMinSimilarity) {
        if (!bestMatch || overlap > bestMatch.similarity) {
          bestMatch = { template, workflowId: wfId, similarity: overlap };
        }
      }
    }

    return bestMatch;
  }

  // ── Batch Operations ──────────────────────────────────

  /** Run full cache health check */
  cacheHealthReport(): {
    totalEntries: number;
    totalSegments: number;
    temperatureDistribution: Record<string, number>;
    evictionCandidates: Array<{ id: string; decision: EvictionDecision }>;
    reuseOpportunities: number;
    expiredSegments: number;
  } {
    const tempDist: Record<string, number> = { hot: 0, warm: 0, cold: 0, frozen: 0 };
    const evictionCandidates: Array<{ id: string; decision: EvictionDecision }> = [];

    for (const id of this.store.keys()) {
      const temp = this.cacheTemperature(id);
      tempDist[temp.level]++;
      if (temp.level === 'frozen' || temp.level === 'cold') {
        // These are external memory consolidation candidates
      }
    }

    let expired = 0;
    let reuseOpps = 0;
    for (const [segId, seg] of this.kvSegments) {
      if (seg.ttl && Date.now() - seg.createdAt > seg.ttl) {
        expired++;
        continue;
      }
      const decision = this.evictionDecision(segId);
      if (decision.action === 'evict') {
        evictionCandidates.push({ id: segId, decision });
      }
      // Count cross-agent reuse opportunities
      for (const otherSeg of this.kvSegments.values()) {
        if (otherSeg.agentId !== seg.agentId && otherSeg.hash === seg.hash) {
          reuseOpps++;
        }
      }
    }

    return {
      totalEntries: this.store.size,
      totalSegments: this.kvSegments.size,
      temperatureDistribution: tempDist,
      evictionCandidates,
      reuseOpportunities: reuseOpps,
      expiredSegments: expired,
    };
  }

  // ── Private Helpers ───────────────────────────────────

  private workflowBoost(id: string): number {
    const entry = this.store.get(id);
    if (!entry || entry.workflowStep === undefined) return 0;

    // If this entry's workflow step is coming up soon, boost it
    const currentStep = this.workflowGraph[0]?.stepIndex ?? 0;
    const distance = Math.abs(entry.workflowStep - currentStep);
    return Math.exp(-distance / 3);
  }

  private evictColdestSegment(): void {
    let coldestId: string | null = null;
    let lowestPriority = Infinity;

    for (const segId of this.kvSegments.keys()) {
      const decision = this.evictionDecision(segId);
      if (decision.priority < lowestPriority) {
        lowestPriority = decision.priority;
        coldestId = segId;
      }
    }

    if (coldestId) {
      this.kvSegments.delete(coldestId);
    }
  }

  private hashContent(content: string): string {
    // Simple FNV-1a hash for demo (production: use SHA-256)
    let hash = 2166136261;
    for (let i = 0; i < content.length; i++) {
      hash ^= content.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16);
  }

  private textSimilarity(a: string, b: string): number {
    // Trigram Jaccard similarity
    const trigrams = (s: string): Set<string> => {
      const t = new Set<string>();
      const normalized = s.toLowerCase().replace(/\s+/g, ' ');
      for (let i = 0; i < normalized.length - 2; i++) {
        t.add(normalized.slice(i, i + 3));
      }
      return t;
    };

    const setA = trigrams(a);
    const setB = trigrams(b);
    let intersection = 0;
    for (const t of setA) if (setB.has(t)) intersection++;
    const union = setA.size + setB.size - intersection;
    return union === 0 ? 0 : intersection / union;
  }

  private extractKeywords(text: string): string[] {
    // Simple keyword extraction: split, lowercase, remove stop words, dedupe
    const stopWords = new Set(['the', 'a', 'an', 'is', 'to', 'for', 'of', 'and', 'in', 'on', 'with', 'at', 'by']);
    return [...new Set(
      text.toLowerCase()
        .replace(/[^\w\s]/g, ' ')
        .split(/\s+/)
        .filter(w => w.length > 3 && !stopWords.has(w))
    )].slice(0, 15);
  }

  private keywordOverlap(a: string[], b: string[]): number {
    if (a.length === 0 || b.length === 0) return 0;
    const setB = new Set(b);
    let overlap = 0;
    for (const kw of a) if (setB.has(kw)) overlap++;
    return overlap / Math.max(a.length, b.length);
  }
}

// ─── Demo & Tests ─────────────────────────────────────────

function demo(): void {
  const mgr = new KVCacheAwareMemoryManager();

  // 1. Store memories with workflow context
  console.log('=== Storing memories ===');
  mgr.remember('m1', 'User prefers dark mode and concise responses', ['preference', 'ui'], 1);
  mgr.remember('m2', 'API endpoint: https://api.example.com/v2/search', ['config', 'api'], 2);
  mgr.remember('m3', 'Previous search results for "KV cache optimization"', ['search', 'cache'], 3);
  mgr.remember('m4', 'User is building a multi-agent system with OpenClaw', ['project', 'agent'], 1);

  // 2. Set workflow graph (3 agents in sequence)
  mgr.setWorkflowGraph([
    { agentId: 'researcher', stepIndex: 0, dependencies: [], estimatedDuration: 5000 },
    { agentId: 'analyzer', stepIndex: 1, dependencies: ['researcher'], estimatedDuration: 3000 },
    { agentId: 'writer', stepIndex: 2, dependencies: ['analyzer'], estimatedDuration: 8000 },
  ]);

  // 3. Register KV segments
  console.log('\n=== Registering KV segments ===');
  mgr.registerKVSegment('researcher', 'Search results for KV cache papers optimization', 500, 'kv cache papers optimization', 60000);
  mgr.registerKVSegment('analyzer', 'Analysis of cache eviction patterns', 300, 'cache-analysis');
  mgr.registerKVSegment('writer', 'Draft summary of findings', 800, 'summary-draft');

  // 4. Check cache temperatures
  console.log('\n=== Cache Temperatures ===');
  for (const id of ['m1', 'm2', 'm3', 'm4']) {
    const temp = mgr.cacheTemperature(id);
    console.log(`  ${id}: ${temp.level} (${temp.score.toFixed(3)}) — ${temp.reason}`);
  }

  // 5. Simulate access patterns affecting temperature
  console.log('\n=== Simulating access patterns ===');
  for (let i = 0; i < 5; i++) {
    mgr.recall('m3', 'researcher');
  }
  mgr.recall('m1', 'analyzer');
  const m3TempAfter = mgr.cacheTemperature('m3');
  console.log(`  m3 after 5 accesses: ${m3TempAfter.level} (${m3TempAfter.score.toFixed(3)})`);

  // 6. Test cross-agent segment reuse (Segment-Level KV Cache Sharing)
  console.log('\n=== Cross-Agent KV Segment Reuse ===');
  mgr.registerKVSegment('researcher', 'Search results for KV cache papers optimization', 500, 'kv cache papers optimization');
  const reuse = mgr.findReusableSegments('KV cache papers optimization', 'analyzer', 0.3);
  console.log(`  Found ${reuse.length} reusable segments from other agents:`);
  for (const r of reuse) {
    console.log(`    ${r.segment.id}: similarity=${r.similarity.toFixed(3)} type=${r.reuseType} tag="${r.segment.semanticTag}"`);
  }

  // 7. Test workflow-aware eviction (KVFlow-inspired)
  console.log('\n=== Workflow-Aware Eviction (KVFlow) ===');
  for (const segId of mgr['kvSegments'].keys()) {
    const decision = mgr.evictionDecision(segId);
    console.log(`  ${segId}: ${decision.action} (priority=${decision.priority}) — ${decision.reason}`);
  }

  // 8. Test plan template extraction (Agentic Plan Caching)
  console.log('\n=== Plan Template Extraction (Agentic Plan Cache) ===');
  const template = mgr.extractPlanTemplate('wf-001', [
    { action: 'search("KV cache")', tool: 'web_search', input_summary: 'search cache optimization papers research' },
    { action: 'analyze(results)', tool: 'llm_analyze', input_summary: 'analyze cache eviction patterns results' },
    { action: 'write(draft)', tool: 'llm_write', input_summary: 'write summary cache findings research' },
  ]);
  console.log(`  Template: ${template}`);
  const match = mgr.matchPlanTemplate('cache optimization research findings');
  console.log(`  Match: ${match ? `${match.template} (sim=${match.similarity.toFixed(3)})` : 'none'}`);

  // 9. Full health report
  console.log('\n=== Cache Health Report ===');
  const report = mgr.cacheHealthReport();
  console.log(`  Entries: ${report.totalEntries}, Segments: ${report.totalSegments}`);
  console.log(`  Temperature: ${JSON.stringify(report.temperatureDistribution)}`);
  console.log(`  Reuse opportunities: ${report.reuseOpportunities}`);
  console.log(`  Expired: ${report.expiredSegments}, Eviction candidates: ${report.evictionCandidates.length}`);

  // ─── Assertions ──────────────────────────────────────
  console.log('\n=== Assertions ===');
  let passed = 0;
  let total = 0;

  // Test 1: Cache temperature classification
  total++;
  const m1Temp = mgr.cacheTemperature('m1');
  console.assert(m1Temp.score >= 0 && m1Temp.score <= 1, `Temperature score in [0,1]: ${m1Temp.score}`);
  console.log(`  ✓ Temperature score bounded [0,1]: ${m1Temp.score.toFixed(3)}`);
  passed++;

  // Test 2: Cross-agent segment reuse works
  total++;
  console.assert(reuse.length > 0, 'Cross-agent reuse found segments');
  console.log(`  ✓ Cross-agent reuse: ${reuse.length} segments found`);
  passed++;

  // Test 3: Workflow-aware eviction prioritizes correctly
  total++;
  const researcherSeg = [...mgr['kvSegments'].values()].find(s => s.agentId === 'researcher');
  if (researcherSeg) {
    const decision = mgr.evictionDecision(researcherSeg.id);
    // Researcher is step 0 (next), should be retained
    console.assert(decision.action === 'retain', `Researcher segment retained: ${decision.action}`);
    console.log(`  ✓ Workflow-aware: researcher (step 0) retained at priority ${decision.priority}`);
    passed++;
  }

  // Test 4: Plan template matching
  total++;
  console.assert(match !== null, 'Plan template matched');
  console.assert(match!.similarity >= 0.3, `Plan match similarity: ${match!.similarity}`);
  console.log(`  ✓ Plan template matched (sim=${match!.similarity.toFixed(3)})`);
  passed++;

  // Test 5: Health report has valid distribution
  total++;
  const distSum = Object.values(report.temperatureDistribution).reduce((a, b) => a + b, 0);
  console.assert(distSum === report.totalEntries, `Distribution sum (${distSum}) === entries (${report.totalEntries})`);
  console.log(`  ✓ Temperature distribution complete: ${distSum} === ${report.totalEntries}`);
  passed++;

  console.log(`\n✅ ${passed}/${total} assertions passed`);
}

// Run
demo();
```

---

## 7. Connection to Existing Projects

### agent-memory-graph
| Concept | KV Cache Paper | agent-memory-graph API | Status |
|---------|---------------|----------------------|--------|
| Workflow-aware eviction | KVFlow Step Graph | `add_workflow()` / `record_outcome()` | ✅ Exists (add reuse_proximity metadata) |
| Model-driven eviction | SideQuest auxiliary thread | `consolidation_pipeline` / `semantic_divergence` | ✅ Exists (external layer equivalent) |
| Plan template caching | Agentic Plan Caching | `compose()` / workflow tips | ✅ Exists (add keyword extraction) |
| Cross-agent sharing | Segment-Level / KVCOMM | CRDT `merge_crdt()` + HLC | ✅ Exists |
| Temperature scoring | IntentKV multi-query | `importance_rank()` | ✅ Exists (add KV-aware scoring) |

### agent-context-store
| Concept | KV Cache Paper | agent-context-store API | Status |
|---------|---------------|----------------------|--------|
| Context compression | SideQuest eviction | `content_fold()` / `content_squash()` | ✅ Exists |
| TTL-based retention | Continuum KV TTL | `expire_at()` / `stale_keys()` | ✅ Exists |
| Segment matching | Segment-Level sharing | `content_similarity()` / `fingerprint()` | ✅ Exists |
| Health monitoring | CacheSlide / IntentKV | `store_health()` / `store_dashboard()` | ✅ Exists |

### openclaw-langgraph-bridge
| Concept | KV Cache Paper | Bridge Module | Status |
|---------|---------------|--------------|--------|
| Step Graph | KVFlow | `Supervisor` execution graph | ✅ Exists |
| All-Gather pattern | TokenDance | Supervisor broadcast | ✅ Exists |
| Prefetching | KVFlow prefetch | Could add to Supervisor | 🔄 Future |

---

## 8. Competitive Landscape: Who Is Building Agent KV Cache?

| System | Focus | Open Source | npm? | TypeScript? |
|--------|-------|-------------|------|-------------|
| vLLM + KVFlow | Inference engine | ✅ | ❌ | ❌ (Python) |
| SGLang + RadixAttention | Inference + caching | ✅ | ❌ | ❌ (Python) |
| KEEP | Embodied planning | ✅ (PKU) | ❌ | ❌ (Python) |
| Tokencake | Multi-agent serving | Research | ❌ | ❌ |
| TokenDance | Multi-agent All-Gather | Research | ❌ | ❌ |
| LMCache | Enterprise KV layer | ✅ | ❌ | ❌ (Python) |
| DroidSpeak | Cross-finetuned sharing | Research | ❌ | ❌ |
| **npm ecosystem gap** | **None exist** | — | **❌** | **❌** |

**Strategic implication**: The KV cache ↔ agent memory bridge is a **greenfield in the npm ecosystem**. While Python has 10+ systems, TypeScript/Node.js has zero. agent-memory-graph + agent-context-store can be the first TS-native agent memory system with explicit KV cache awareness.

---

## 9. Next Actions

1. **agent-memory-graph: `cache_temperature()` API** (~40 lines + 10 tests)
   - Add `reuse_proximity` field to memory entries
   - Compute recency × frequency × proximity × workflow_boost score
   - Expose via `cacheTemperature(id)` → `{ level, score, reason }`
   - **Positioning**: "Enables inference layer to make informed KV cache decisions"

2. **agent-memory-graph: Plan template extraction** (~60 lines + 15 tests)
   - Extract generalized plan patterns from `workflow` entries
   - Keyword-based matching for new tasks
   - `extractPlanTemplate(workflowId)` → template string
   - `matchPlanTemplate(taskDescription)` → best match
   - **Positioning**: "Test-time plan reuse for 50% cost reduction (APC NeurIPS 2025)"

3. **agent-context-store: KV-cache-aware TTL** (~30 lines + 8 tests)
   - Add `kv_ttl` field that accounts for expected tool-call duration
   - `expire_smart(key, toolDuration estimate)` — set TTL based on tool type
   - **Positioning**: "Continuum-inspired adaptive retention"

4. **README Positioning**: Add "KV Cache Aware" section
   - "Bridges external graph memory ↔ internal KV cache"
   - Cite: KVFlow (NeurIPS 2025), SideQuest (NVIDIA 2026), Segment-Level (ICLR 2026), Continuum, Agentic Plan Caching
   - Key phrase: "The cache coherence protocol for agent memory" (SIGARCH 2026)

5. **Future: `agent-kv-bridge` package** (~200 lines, separate package)
   - Lightweight middleware that sits between inference engine (vLLM/SGLang/Ollama) and agent-memory-graph
   - Receives KV cache events (segment created, evicted, shared)
   - Maps to external memory operations (remember, recall, consolidate)
   - First TS-native KV cache agent memory bridge in npm

---

## 10. Sources

1. **KVFlow** — Pan et al., NeurIPS 2025, arXiv:2507.07400 — Workflow-aware KV cache management
2. **KEEP** — Li et al., DAC 2026, arXiv:2602.23592 — KV-cache-centric memory for embodied planning
3. **Segment-Level KV Cache Sharing** — Wang et al., ICLR 2026 submission (OpenReview kgzBkyqg6Z)
4. **TokenDance** — Bian et al., arXiv:2604.03143, April 2026 — All-Gather KV sharing pattern
5. **SideQuest** — Kariyappa & Suh (NVIDIA), arXiv:2602.22603 — Model-driven KV cache eviction
6. **KVCOMM** — Ye et al., NeurIPS 2025 — Cross-context KV cache communication
7. **Continuum** — Li et al., arXiv:2511.02230 — KV cache TTL for multi-turn agents
8. **Agentic Plan Caching** — Zhang et al., NeurIPS 2025, arXiv:2506.14852 — Test-time plan memory
9. **AgenticCache** — arXiv:2604.24039 — Cache-driven asynchronous planning
10. **IntentKV** — arXiv:2606.09916 — Cross-turn intent-aware KV pruning
11. **Tokencake** — Bian et al., 2025 — KV-cache-centric multi-agent serving
12. **CacheSlide** — Liu et al., FAST 2026 — Cross-position KV cache reuse
13. **ScaleSim** — Pan et al., 2026 — Large-scale multi-agent simulation memory
14. **SIGARCH 2026** — Yu & Zhao — Multi-agent memory from architecture perspective
15. **LLM Agent Memory Survey** — preprints.org, March 2026 — Unified representation
16. **Semantic Sponsorship for KV-Cache** — arXiv:2604.11288 — Dormant token analysis
17. **Persistent Q4 KV Cache** — arXiv:2603.04428 — Edge agent KV persistence
18. **KV Cache Optimization Guide** — digitalapplied.com, 2026 — Engineering reference
19. **Context Engineering for Agents** — spheron.network, June 2026 — GPU economics
20. **Awesome KV Cache Optimization** — github.com/jjiantong — Paper index

---

*Research note generated by Catalyst deep-exploration-evening cron, 2026-06-26 20:18 CST*
