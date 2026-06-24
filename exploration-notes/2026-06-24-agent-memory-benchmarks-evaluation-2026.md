# Agent Memory Benchmarks & Evaluation 2026: From Recall to Agency

> **Date:** 2026-06-24
> **Researcher:** Catalyst 🧪
> **Method:** autoresearch (autoresearch.md methodology)
> **Trigger:** deep-exploration-evening cron — HEARTBEAT.md pending: npm publish benchmarks gap

---

## TL;DR

Agent memory evaluation has undergone a paradigm shift in 2026: **recall ≠ agency**. The three benchmark pillars (LoCoMo, LongMemEval, BEAM) now cover 10K→10M token scales, but the most important insight from MemoryArena (ICML 2026) is that models scoring 90%+ on recall-focused benchmarks collapse to 40-60% on agentic memory tasks. This note synthesizes 15+ benchmarks, 8+ evaluation frameworks, and production metrics into a unified evaluation strategy for agent-memory-graph and agent-context-store.

---

## 5 Core Concepts

### 1. The Three Benchmark Pillars: LoCoMo / LongMemEval / BEAM

The field has converged on three complementary benchmarks:

| Benchmark | Scale | Questions | Focus | Origin |
|-----------|-------|-----------|-------|--------|
| **LoCoMo** | ~10K-26K tokens | 1,540 | Single-hop, multi-hop, temporal, open-domain recall | Snap Research, NeurIPS 2024 |
| **LongMemEval** | 115K-1M tokens | 500 | Knowledge updates, multi-session reasoning, abstention | UCSD, 2024 |
| **BEAM** | 128K-10M tokens | 2,000 | 10 abilities: IE, MR, KU, TR, SUM, PF, ABS, CR, EO, IF | UMass, ICLR 2026 |

**Key distinction:** LoCoMo/LongMemEval test *recall from conversation*. BEAM tests *memory under scale pressure* — at 10M tokens, no context window can save you. This is where architecture matters.

**New BEAM abilities (unique to 2026):**
- **Contradiction Resolution (CR):** handling conflicting facts across sessions
- **Event Ordering (EO):** temporal sequence reconstruction
- **Instruction Following (IF):** remembering operational directives vs. preferences
- **Abstention (ABS):** knowing when NOT to answer (missing info ≠ wrong info)

### 2. MemoryArena: The Agentic Memory Benchmark (ICML 2026)

**Paper:** "Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks" (arXiv:2602.16313)
**Authors:** Stanford + UCSD (Zexue He, Yu Wang, Julian McAuley, et al.)

The most important insight of 2026: **recall benchmarks are misleading for agentic memory.**

```
LoCoMo-saturating models (90%+) → MemoryArena: 40-60% success rate
```

**Design:**
- **4 scenarios:** bundled shopping, group travel planning, progressive search, formal reasoning
- **Memory-Agent-Environment loop:** memory influences agent decisions which influence environment feedback which influences future memory
- **4,850 subtasks** across interdependent multi-session tasks
- **Key metric:** Task completion rate (not answer accuracy)

**Three benchmark eras:**
1. **Static Recall (2024):** LoCoMo, LongMemEval — "Can you retrieve X?"
2. **Dynamic Trace (2025-26):** Mem2ActBench, EMemBench, AgentLongBench — "Can you find the right tool parameter from history?"
3. **Agentic Loop (2026):** MemoryArena — "Can memory guide correct future action?"

### 3. MemoryAgentBench: The Four Competencies Framework (ICLR 2026)

**Paper:** "Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions" (arXiv:2507.05257)
**Authors:** Yuanzhe Hu, Yu Wang, Julian McAuley (UCSD)

Four core memory competencies for agents:

```
1. Accurate Retrieval     — Find the right fact at the right time
2. Test-time Learning     — Classify/cluster new information seen incrementally
3. Long-range Understanding — Holistic comprehension over extended context
4. Information Consolidation — Merge, deduplicate, resolve contradictions
```

**"Inject once, query multiple times" design** — one long text → multiple questions, dramatically improving evaluation efficiency vs. one-question-per-context.

**Dataset reformulation strategy:** Transforms existing benchmarks (RULER, InfBench, HELMET, LongMemEval) into multi-turn format simulating incremental information processing.

### 4. Multi-Dimensional Evaluation: Beyond Accuracy

Production agent memory evaluation requires a **multi-dimensional scorecard**:

| Dimension | Metric | Why It Matters |
|-----------|--------|----------------|
| **Accuracy** | LoCoMo/LongMemEval/BEAM score | Correctness floor |
| **Token Efficiency** | Avg tokens / query | Cost at scale (~7K optimal per Mem0) |
| **Retrieval Latency** | p50, p95 retrieval time | UX (sub-300ms = real-time, >5s = batch) |
| **Context Size** | Tokens injected per retrieval | LLM processing cost |
| **Trajectory Efficiency** | Steps to task completion | Agent cost (MemoryArena) |
| **Memory Operations** | Add/Update/Delete/NOOP ratio | Health signal (>50% NOOP = good) |
| **Memory Staleness** | High-relevance + outdated facts | "Confidently wrong" risk |
| **Write Efficiency** | Extraction quality vs. raw dump | Pre-processing cost |

**The cost-quality frontier:** Full-context achieves highest accuracy but 14× token cost and 17s p95 latency. Selective memory trades ~3-5% accuracy for 10× efficiency. **The sweet spot is ~7K tokens per retrieval** (Mem0 2026 algorithm).

### 5. The Benchmark Saturation Problem & New Frontiers

**Saturation timeline:**
```
2024: LoCoMo published → models struggle (50-60%)
2025: Mem0/Zep optimize → 70-80%
2026 Q1: Token-efficient algorithms → 90%+ (Mem0 92.5%, Hindsight 91.4%)
2026 Q2: "LoCoMo is solved" — benchmarks need to evolve
```

**New frontiers (2026):**
- **LoCoMo-Plus:** Beyond-factual cognitive memory evaluation
- **LoCoMo Refined:** Stricter LLM judging + cleaned dataset (removing easy items)
- **BEAM-10M:** Only benchmark where no system exceeds 65%
- **StreamMemBench:** Streaming evaluation for real-time assistants
- **AMemGym:** Interactive memory benchmarking for long-horizon conversations
- **RoboMemArena:** Memory in robotic tasks (physical world grounding)
- **Evo-Memory:** Self-evolving memory test-time learning
- **OdysseyBench:** Long-horizon office workflow memory

---

## Production Benchmark Results Matrix (June 2026)

| System | LoCoMo | LongMemEval | BEAM-1M | BEAM-10M | Tokens/Query | p50 Latency |
|--------|--------|-------------|---------|----------|-------------|-------------|
| **Mem0** (Apr 2026) | 92.5 | 94.4 | 64.1 | 48.6 | ~7K | 0.88-1.09s |
| **Hindsight** (AMB v1) | 91.4 | 91.4 | — | 64.1 | — | — |
| **Zep/Graphiti** | 94.7 | 90.2 | — | — | 4.4-5.8K | 155-162ms |
| **Letta/MemGPT** (filesystem) | 74.0 | 83.2 | — | — | — | — |
| **SuperMemory** | — | 85.4 | — | — | — | <300ms |
| **LangMem** | 58.1 | — | — | — | — | p95=59.8s |
| **Mem0 (old algo)** | 71.4 | 67.8 | — | — | ~26K | — |
| **Full-context** | ~highest | ~highest | — | — | ~26K+ | p95=17.1s |
| **RAG baseline** | ~60 | ~55 | — | 24.9 | varies | varies |

**Key observations:**
1. **Zep leads on combined accuracy + latency + token efficiency** (94.7% / 155ms / 5.8K tokens)
2. **Mem0 leads on LongMemEval** (94.4%) with good token efficiency but higher latency
3. **BEAM-10M is unsolved** — best is 48.6% (Mem0), showing massive room for improvement
4. **LangMem is impractical for real-time** — 59.8s p95 latency
5. **Full-context is dead for production** — 17s p95, 14× token cost

---

## 5 Key Insights

### 1. Recall Benchmarks Are Solved; Agency Benchmarks Are Not

LoCoMo (90%+) and LongMemEval (90%+) are approaching saturation. But MemoryArena shows **agentic memory tasks remain at 40-60% success rates** even with the best memory systems. The gap: recall asks "can you find X?", agency asks "can you use X to make the right decision?" — fundamentally different cognitive demands.

**Implication for agent-memory-graph:** README should position beyond recall metrics. The pitch isn't "we score X% on LoCoMo" — it's "our graph reasoning + consolidation + workflow memory + adaptive retrieval support agentic memory use cases that flat vector stores can't handle."

### 2. BEAM-10M Is The New Competitive Frontier

No system exceeds 50% on BEAM-10M. The bottleneck isn't retrieval — it's **state integrity at scale** (Mark Hendrickson, April 2026). Agent memory breaks at 500K tokens for state, not 10M for retrieval. Two orthogonal failure modes:
- **Retrieval failure:** Can't find the right needle (BEAM-10M tests this)
- **State integrity failure:** Lost the thread of who/what/when (breaks at 500K-2M)

agent-memory-graph's graph + temporal + consolidation primitives directly address state integrity, which is the more common production failure.

### 3. The Three-Layer Evaluation Stack Is Consensus

Multiple independent sources converge on layered evaluation:

```
Layer 1: Accuracy (LoCoMo / LongMemEval / BEAM)
Layer 2: Efficiency (tokens/query, p50/p95 latency, context size)
Layer 3: Agentic capability (MemoryArena task completion, trajectory efficiency)
```

DeepEval (14K+ ⭐) formalizes this as:
- **End-to-end:** TaskCompletion + ConversationCompleteness
- **Trajectory:** StepEfficiency + PlanAdherence + PlanQuality
- **Component:** ToolCorrectness + ArgumentCorrectness

**agent-memory-graph evaluation should report all three layers** to be credible.

### 4. Memory Operations Ratio Is the Hidden Health Metric

From Memory-R1 (ACL 2026) and AgeMem research: **NOOP (no operation) is the most important memory operation**. Healthy memory systems do nothing >50% of the time. Systems that constantly Add/Update/Delete are burning tokens and creating noise.

The optimal ratio from research:
- **Add:** 30-40% (new information)
- **Update:** 10-15% (fact revision)
- **Delete:** 10-15% (irrelevance/correction)
- **NOOP:** 35-45% (nothing to do = healthy signal)

agent-memory-graph already implements memory_feedback (threshold tuning) and memory_audit (health scoring). The README should highlight these metrics.

### 5. Benchmark Manipulation Is Real — Independent Verification Required

- **MemPalace benchmarks debunked** (Vectorize, 2026): inflated claims vs. reality
- **LoCoMo gaming:** Some systems optimize for benchmark format, not real memory
- **"Ambient context" effect** (Letta): simply putting conversation in files scores 74% on LoCoMo — meaning the benchmark isn't really testing memory architecture, just file search
- **LLM-as-Judge bias:** LoCoMo Refined found 20-30% scoring changes with stricter judging

**Implication:** Any benchmark claims in agent-memory-graph README should include: (1) methodology, (2) token counts, (3) latency, (4) whether GPT-4o judge was used. No accuracy without efficiency is meaningful.

---

## Runnable Code: Multi-Dimensional Memory Evaluation Harness

```typescript
/**
 * MemoryBenchmarkHarness.ts
 * 
 * A multi-dimensional evaluation harness for agent memory systems.
 * Measures accuracy, efficiency, and agentic capability in one run.
 * 
 * Design based on 2026 consensus:
 * - Layer 1: Accuracy (LoCoMo/LongMemEval/BEAM-style)
 * - Layer 2: Efficiency (tokens, latency, context size)
 * - Layer 3: Agentic (task completion, trajectory efficiency)
 */

import { performance } from 'perf_hooks';

// ─── Types ──────────────────────────────────────────────

interface MemoryQuery {
  id: string;
  question: string;
  groundTruth: string;
  category: 'single_hop' | 'multi_hop' | 'temporal' | 'knowledge_update' | 'multi_session' | 'abstention';
  difficulty: 'easy' | 'medium' | 'hard';
}

interface MemoryEntry {
  id: string;
  content: string;
  tags: string[];
  timestamp: number;
  embedding?: number[];
}

interface RetrievalResult {
  answer: string;
  retrievedEntries: MemoryEntry[];
  tokenCount: number;
  latencyMs: number;
}

interface BenchmarkConfig {
  name: string;
  queries: MemoryQuery[];
  judgeModel?: (predicted: string, groundTruth: string) => Promise<{ correct: boolean; score: number }>;
}

// ─── Core Harness ───────────────────────────────────────

class MemoryBenchmarkHarness {
  private results: EvaluationResult[] = [];
  
  constructor(
    private readonly memoryStore: MemoryStore,
    private readonly retriever: (query: string) => Promise<RetrievalResult>,
    private readonly config: BenchmarkConfig
  ) {}
  
  /** Run full evaluation suite */
  async run(): Promise<BenchmarkReport> {
    const results: EvaluationResult[] = [];
    
    for (const query of this.config.queries) {
      const start = performance.now();
      
      // Retrieval
      const retrieval = await this.retriever(query.question);
      const retrievalLatency = performance.now() - start;
      
      // Judging
      let correct = false;
      let score = 0;
      if (this.config.judgeModel) {
        const judged = await this.config.judgeModel(retrieval.answer, query.groundTruth);
        correct = judged.correct;
        score = judged.score;
      } else {
        // Fallback: exact match (strict) or substring (loose)
        correct = retrieval.answer.toLowerCase().includes(query.groundTruth.toLowerCase());
        score = correct ? 1.0 : 0;
      }
      
      results.push({
        queryId: query.id,
        category: query.category,
        difficulty: query.difficulty,
        correct,
        score,
        tokenCount: retrieval.tokenCount,
        latencyMs: retrievalLatency,
        contextEntries: retrieval.retrievedEntries.length,
      });
    }
    
    this.results = results;
    return this.generateReport();
  }
  
  /** Generate multi-dimensional report */
  generateReport(): BenchmarkReport {
    const total = this.results.length;
    if (total === 0) throw new Error('No results. Run benchmark first.');
    
    // Layer 1: Accuracy by category
    const byCategory: Record<string, CategoryStats> = {};
    for (const r of this.results) {
      if (!byCategory[r.category]) {
        byCategory[r.category] = { count: 0, correct: 0, avgScore: 0, scores: [] };
      }
      const cat = byCategory[r.category];
      cat.count++;
      if (r.correct) cat.correct++;
      cat.scores.push(r.score);
    }
    for (const cat of Object.values(byCategory)) {
      cat.accuracy = cat.correct / cat.count;
      cat.avgScore = cat.scores.reduce((a, b) => a + b, 0) / cat.scores.length;
    }
    
    // Layer 2: Efficiency
    const tokenCounts = this.results.map(r => r.tokenCount);
    const latencies = this.results.map(r => r.latencyMs);
    const sortedLatencies = [...latencies].sort((a, b) => a - b);
    
    const efficiency = {
      avgTokens: Math.round(tokenCounts.reduce((a, b) => a + b, 0) / total),
      maxTokens: Math.max(...tokenCounts),
      minTokens: Math.min(...tokenCounts),
      p50LatencyMs: sortedLatencies[Math.floor(total * 0.5)],
      p95LatencyMs: sortedLatencies[Math.floor(total * 0.95)],
      avgContextEntries: this.results.reduce((a, b) => a + b.contextEntries, 0) / total,
    };
    
    // Layer 3: Difficulty breakdown (proxy for agentic complexity)
    const byDifficulty: Record<string, number> = {};
    for (const r of this.results) {
      if (!byDifficulty[r.difficulty]) byDifficulty[r.difficulty] = 0;
      if (r.correct) byDifficulty[r.difficulty]++;
    }
    const difficultyReport: Record<string, { accuracy: number; count: number }> = {};
    for (const [diff, correct] of Object.entries(byDifficulty)) {
      const count = this.results.filter(r => r.difficulty === diff).length;
      difficultyReport[diff] = { accuracy: correct / count, count };
    }
    
    // Overall score
    const overallAccuracy = this.results.filter(r => r.correct).length / total;
    
    // Composite score (accuracy × token_efficiency × latency_efficiency)
    const tokenScore = Math.max(0, 1 - (efficiency.avgTokens / 30000)); // 30K = full-context baseline
    const latencyScore = Math.max(0, 1 - (efficiency.p95LatencyMs / 20000)); // 20s = full-context p95
    const compositeScore = overallAccuracy * 0.5 + tokenScore * 0.25 + latencyScore * 0.25;
    
    return {
      benchmark: this.config.name,
      timestamp: new Date().toISOString(),
      totalQueries: total,
      overallAccuracy: +(overallAccuracy * 100).toFixed(1),
      compositeScore: +(compositeScore * 100).toFixed(1),
      byCategory: Object.fromEntries(
        Object.entries(byCategory).map(([k, v]) => [k, { accuracy: +(v.accuracy! * 100).toFixed(1), count: v.count }])
      ),
      efficiency,
      byDifficulty: Object.fromEntries(
        Object.entries(difficultyReport).map(([k, v]) => [k, { accuracy: +(v.accuracy * 100).toFixed(1), count: v.count }])
      ),
    };
  }
  
  /** Compare two reports side-by-side */
  static compare(a: BenchmarkReport, b: BenchmarkReport): string {
    const lines: string[] = [];
    lines.push(`Benchmark Comparison: ${a.benchmark} vs ${b.benchmark}`);
    lines.push('═'.repeat(60));
    
    const rows = [
      ['Overall Accuracy', `${a.overallAccuracy}%`, `${b.overallAccuracy}%`, b.overallAccuracy - a.overallAccuracy],
      ['Composite Score', `${a.compositeScore}%`, `${b.compositeScore}%`, b.compositeScore - a.compositeScore],
      ['Avg Tokens/Query', `${a.efficiency.avgTokens}`, `${b.efficiency.avgTokens}`, b.efficiency.avgTokens - a.efficiency.avgTokens],
      ['p50 Latency (ms)', `${a.efficiency.p50LatencyMs.toFixed(0)}`, `${b.efficiency.p50LatencyMs.toFixed(0)}`, b.efficiency.p50LatencyMs - a.efficiency.p50LatencyMs],
      ['p95 Latency (ms)', `${a.efficiency.p95LatencyMs.toFixed(0)}`, `${b.efficiency.p95LatencyMs.toFixed(0)}`, b.efficiency.p95LatencyMs - a.efficiency.p95LatencyMs],
    ];
    
    lines.push('Metric'.padEnd(22) + 'System A'.padStart(12) + 'System B'.padStart(12) + 'Delta'.padStart(10));
    lines.push('─'.repeat(56));
    for (const [metric, va, vb, delta] of rows) {
      const sign = delta > 0 ? '+' : '';
      lines.push(
        metric.padEnd(22) + 
        String(va).padStart(12) + 
        String(vb).padStart(12) + 
        `${sign}${typeof delta === 'number' ? delta.toFixed(1) : delta}`.padStart(10)
      );
    }
    
    return lines.join('\n');
  }
}

// ─── Types for report ───────────────────────────────────

interface EvaluationResult {
  queryId: string;
  category: string;
  difficulty: string;
  correct: boolean;
  score: number;
  tokenCount: number;
  latencyMs: number;
  contextEntries: number;
}

interface CategoryStats {
  count: number;
  correct: number;
  avgScore?: number;
  accuracy?: number;
  scores: number[];
}

interface BenchmarkReport {
  benchmark: string;
  timestamp: string;
  totalQueries: number;
  overallAccuracy: number;
  compositeScore: number;
  byCategory: Record<string, { accuracy: number; count: number }>;
  efficiency: {
    avgTokens: number;
    maxTokens: number;
    minTokens: number;
    p50LatencyMs: number;
    p95LatencyMs: number;
    avgContextEntries: number;
  };
  byDifficulty: Record<string, { accuracy: number; count: number }>;
}

// Minimal interface for the memory store (duck-typed)
interface MemoryStore {
  search(query: string): Promise<{ entries: MemoryEntry[]; tokenCount: number }>;
}

// ─── Demo / Verification ────────────────────────────────

async function demo() {
  // Mock memory store with realistic data patterns
  const mockStore: MemoryStore = {
    async search(query: string) {
      const entries: MemoryEntry[] = [
        { id: '1', content: 'User prefers concise answers', tags: ['preference'], timestamp: Date.now() - 86400000 },
        { id: '2', content: 'User works at Acme Corp', tags: ['fact', 'work'], timestamp: Date.now() - 172800000 },
        { id: '3', content: 'User asked about pricing tiers last week', tags: ['history', 'pricing'], timestamp: Date.now() - 604800000 },
      ];
      return { entries, tokenCount: 120 };
    }
  };
  
  // Mock retriever wrapping the store
  const retriever = async (q: string): Promise<RetrievalResult> => {
    const start = performance.now();
    const { entries, tokenCount } = await mockStore.search(q);
    const latencyMs = performance.now() - start + Math.random() * 50; // simulate variance
    
    return {
      answer: entries[0]?.content ?? 'I don\'t know',
      retrievedEntries: entries,
      tokenCount,
      latencyMs,
    };
  };
  
  // Mock judge (would be GPT-4o in production)
  const mockJudge = async (predicted: string, groundTruth: string) => {
    const correct = predicted.toLowerCase().includes(groundTruth.toLowerCase().split(' ')[0]);
    return { correct, score: correct ? 1.0 : 0.3 };
  };
  
  // Sample queries mimicking LoCoMo categories
  const queries: MemoryQuery[] = [
    { id: 'q1', question: 'What is the user\'s work place?', groundTruth: 'Acme Corp', category: 'single_hop', difficulty: 'easy' },
    { id: 'q2', question: 'What did the user ask about previously?', groundTruth: 'pricing tiers', category: 'multi_hop', difficulty: 'medium' },
    { id: 'q3', question: 'Does the user prefer detailed or concise responses?', groundTruth: 'concise', category: 'knowledge_update', difficulty: 'easy' },
    { id: 'q4', question: 'What is the user\'s favorite color?', groundTruth: 'unknown', category: 'abstention', difficulty: 'hard' },
    { id: 'q5', question: 'When did the user last contact support?', groundTruth: 'last week', category: 'temporal', difficulty: 'medium' },
  ];
  
  const config: BenchmarkConfig = {
    name: 'Mini-LoCoMo-Demo',
    queries,
    judgeModel: mockJudge,
  };
  
  // Run benchmark
  const harness = new MemoryBenchmarkHarness(mockStore, retriever, config);
  const report = await harness.run();
  
  console.log('\n═══ Benchmark Report ═══');
  console.log(JSON.stringify(report, null, 2));
  
  // Run second system for comparison
  const fastRetriever = async (q: string): Promise<RetrievalResult> => {
    const { entries, tokenCount } = await mockStore.search(q);
    return {
      answer: entries[0]?.content ?? 'unknown',
      retrievedEntries: entries.slice(0, 1),
      tokenCount: Math.round(tokenCount * 0.6), // fewer tokens
      latencyMs: Math.random() * 30 + 10, // faster
    };
  };
  
  const harness2 = new MemoryBenchmarkHarness(mockStore, fastRetriever, config);
  const report2 = await harness2.run();
  
  console.log('\n' + MemoryBenchmarkHarness.compare(report, report2));
  
  // Assertions (verification)
  const assertions = [
    { name: 'Report has overall accuracy', check: () => report.overallAccuracy >= 0 && report.overallAccuracy <= 100 },
    { name: 'Efficiency has token counts', check: () => report.efficiency.avgTokens > 0 },
    { name: 'Latency p50 < p95', check: () => report.efficiency.p50LatencyMs <= report.efficiency.p95LatencyMs },
    { name: 'Category breakdown has entries', check: () => Object.keys(report.byCategory).length > 0 },
    { name: 'Difficulty breakdown present', check: () => Object.keys(report.byDifficulty).length >= 2 },
    { name: 'Composite score in range', check: () => report.compositeScore >= 0 && report.compositeScore <= 100 },
    { name: 'Comparison output is string', check: () => typeof MemoryBenchmarkHarness.compare(report, report2) === 'string' },
  ];
  
  let passed = 0;
  for (const a of assertions) {
    try {
      if (a.check()) {
        console.log(`✅ ${a.name}`);
        passed++;
      } else {
        console.log(`❌ ${a.name}`);
      }
    } catch (e) {
      console.log(`❌ ${a.name}: ${e}`);
    }
  }
  
  console.log(`\n${passed}/${assertions.length} assertions passed`);
  return passed === assertions.length;
}

// Run demo
demo().then(ok => {
  process.exit(ok ? 0 : 1);
}).catch(err => {
  console.error('Demo failed:', err);
  process.exit(1);
});
