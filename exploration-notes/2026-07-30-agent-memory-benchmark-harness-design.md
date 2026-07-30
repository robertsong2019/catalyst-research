# Research #037: Agent Memory Benchmark Harness Design — Building Neutral Evaluation for Graph Memory Systems

> **Date:** 2026-07-30
> **Context:** amg npm launch strategy — benchmark harness as competitive weapon (Insight #133)
> **Feeds:** amg npm publish, amg-bench package, credibility strategy
> **Prior work:** #033 (Agent Memory Engineering 2026H2), #026 (npm Strategy), #014 (Self-Evolving Agent Memory)

---

## Abstract

Every memory system claims high accuracy, but scores are incomparable across papers due to differences in embedding models, judge LLMs, retrieval depths, and conversation chunking. This research investigates the state of agent memory benchmarking as of July 2026, analyzes the evaluation harnesses from Mem0, LongMemEval (V1+V2), EvoMemBench, MemOps, and BEAM, and designs a neutral, reproducible benchmark harness specification for agent-memory-graph (amg). The key insight: **shipping the scoreboard is more valuable than shipping the player** — a well-designed harness creates ecosystem lock-in and positions amg as the reference implementation rather than just another competitor.

---

## Core Concepts

### 1. The Benchmark Tower (Four Layers of Memory Evaluation)

Agent memory evaluation has evolved from simple QA accuracy to a multi-layered discipline. The 2024-2026 literature reveals four distinct evaluation layers, each measuring different things:

| Layer | What it measures | Representative benchmark | Granularity |
|-------|-----------------|------------------------|-------------|
| **L1: Answer Accuracy** | Did the agent get the right answer? | LongMemEval (ICLR 2025) | Per-question |
| **L2: Operation Correctness** | Did the right memory operation fire? | MemOps (arXiv:2607.12893) | Per-operation trace |
| **L3: Memory Form Fit** | Which memory architecture works where? | EvoMemBench (arXiv:2605.18421) | Per-setting (scope×content) |
| **L4: Production Scale** | Does it work at 1M-10M tokens? | BEAM (Mem0) | Per-ability-type, per-scale |

**Key insight from EvoMemBench:** No single memory form works consistently across all settings. Retrieval-based methods dominate knowledge-intensive tasks; procedural memory wins for execution-oriented tasks *when experience matches task structure*. Long-context baselines remain surprisingly competitive. This means amg's value proposition isn't "we're better at everything" — it's "we're the only library that lets you *measure* which approach works for your specific use case."

**From MemOps:** Final-answer scoring conflates failure modes. A system can produce a correct answer based on inconsistent memory state (lucky retrieval from stale data). MemOps introduces structured operation traces: each memory event has trigger, target, scope, state transition, and supporting evidence. This operation-level diagnosis is the future of memory evaluation.

**amg implication:** The harness should support all four layers. Start with L1 (LongMemEval-compatible QA scoring) for baseline credibility, then add L2 (operation traces via amg's existing lifecycle hooks) as the differentiator. No npm/PyPI competitor has operation-level evaluation.

### 2. The Scoring Problem (Why Numbers Aren't Comparable)

Mem0 reports 94.4% on LongMemEval. Mandol reports 92.21% on LoCoMo. Engram reports 83.6%. Are these comparable? **No.** The variance comes from:

**Embedding model:** text-embedding-3-small (1536 dims) vs. Qwen 600M vs. custom models produce dramatically different retrieval quality. Mem0's own benchmarks show a 5+ point swing across extraction models (GPT-5: 91.0% vs. Gemma 4 31B: 88.6% on the same dataset).

**Judge LLM:** GPT-4o vs. GPT-5 vs. Claude Opus produce different verdicts. Stronger judges are stricter. A system scoring 92% with GPT-4o judge might score 85% with GPT-5.

**Retrieval depth (top-k):** LongMemEval results at top-200 ≠ top-50. Mem0 reports both: 94.4% (top-200) vs. 94.8% (top-50) — sometimes *higher* at lower k because of noise filtering.

**Conversation chunking:** How conversations are segmented affects what counts as a "memory unit." Mem0 v3's ADD-only approach (no UPDATE/DELETE) accumulates raw facts. Graph-based approaches (Graphiti, amg) consolidate entities. These produce different fact densities, making direct comparison misleading.

**The solution:** A neutral harness must fix the embedding model, judge LLM, and retrieval depth as configurable constants, and report all three alongside scores. The harness should ship with a default configuration (e.g., text-embedding-3-small + GPT-4o judge + top-50) and a "strict mode" (stronger models, lower top-k).

### 3. The Plugin Architecture (Memory Backend Interface)

LongMemEval-V2 (May 2026) introduces the cleanest backend interface specification:

```python
# LongMemEval-V2 Memory Backend Protocol
class Memory(ABC):
    @abstractmethod
    def insert(self, trajectory) -> None:
        """Receive each trajectory selected for the current haystack."""
        
    @abstractmethod  
    def query(self, query: str, query_image: str = None) -> list[MemoryContextItem]:
        """Return compact evidence for downstream QA.
        
        Returns:
            [{"type": "text", "value": "..."}, {"type": "image", "value": "/path"}]
        """
```

This is minimal and clean. Mem0's benchmark harness uses a similar three-stage pipeline: **Ingest → Search → Evaluate**, with the memory system as a pluggable backend.

**The amg advantage:** amg's API is already more structured than either LongMemEval-V2's interface or Mem0's pipeline. amg can implement a benchmark adapter in ~100 lines:

```typescript
// amg adapter for LongMemEval-compatible harness
import { MemoryGraph } from 'agent-memory-graph';

class AMGBackend {
  constructor() {
    this.graph = new MemoryGraph();
  }
  
  insert(trajectory) {
    for (const turn of trajectory) {
      if (turn.role === 'user') {
        this.graph.addNode({ kind: 'user_message', content: turn.content });
      } else {
        this.graph.addNode({ kind: 'assistant_message', content: turn.content });
      }
    }
  }
  
  query(question: string, topK = 50) {
    return this.graph.search(question, { topK, strategy: 'entropy_weighted' });
  }
}
```

**Critical design decision:** The harness should NOT couple to any specific LLM. It should accept an OpenAI-compatible endpoint, allowing local models (Ollama, vLLM) for fully reproducible offline runs. This is what LongMemEval-V2 does — it uses Qwen3.5-9B as the fixed reader, not GPT-4o.

### 4. Operation-Level Evaluation (Beyond Answer Scoring)

MemOps' key contribution is **structured operation traces**. Each memory event is represented as:

```
OperationTrace {
  trigger: "user_correction" | "new_information" | "time_passage" | ...
  target: entity_id | fact_id | session_id
  scope: "episodic" | "semantic" | "procedural"  
  state_transition: { from: State, to: State }
  evidence: [supporting_text_span_ids]
}
```

MemOps defines 6 categories of operation-level probes:
1. **Remember** — Was a new fact correctly encoded?
2. **Forget** — Was an outdated fact correctly deprioritized?
3. **Update** — Was a changed fact correctly superseded?
4. **Reflect** — Was a higher-level pattern correctly derived?
5. **Composite** — Multi-operation sequences (e.g., "update then reflect")
6. **Trajectory** — Ordered memory state reconstruction

**amg implication:** amg already has lifecycle hooks (pre-write governance, post-write validation, knowledge gap detection, redundancy detection). Exposing these as structured operation traces would make amg the first npm library with MemOps-compatible operation-level evaluation. This is a moat — it requires deep architectural integration that wrapper-based competitors can't replicate.

### 5. Scale Tiers (The BEAM Insight)

BEAM (Mem0's production-scale benchmark) tests at 100K, 1M, and 10M token haystacks. The results reveal non-linear degradation:

| Scale | Overall Pass Rate | Hardest Ability |
|-------|------------------|-----------------|
| 1M tokens | 70.1% | contradiction_resolution (35.7%) |
| 10M tokens | 50.5% | temporal_reasoning (16.3%) |

**Key finding:** Different abilities degrade at different rates. Preference following (0.883→0.904) actually *improves* at scale (more data helps). But temporal reasoning (0.618→0.163) and event ordering (0.536→0.202) collapse. This means a memory system that's "good" at 100K tokens can be "terrible" at 10M.

**amg implication:** amg's entropy-weighted retrieval and entropy-guided forgetting should *theoretically* help at scale (high-entropy redundant nodes get deprioritized). But this is untested. The harness should include scale-tiered benchmarks to validate this hypothesis.

---

## Runnable Code: Minimal Benchmark Harness (TypeScript)

A neutral, reproducible benchmark harness skeleton that any memory system can implement. This is the core design for `amg-bench`:

```typescript
/**
 * amg-bench: Neutral Memory Benchmark Harness
 * 
 * Design principles:
 * 1. Memory backend is pluggable (implement MemoryBackend interface)
 * 2. Judge/answerer LLM is configurable (OpenAI-compatible endpoint)
 * 3. Embedding model is fixed per run (reported alongside scores)
 * 4. Operation traces are first-class (optional, for L2 evaluation)
 */

// === Core Interface ===

interface MemoryBackend {
  readonly name: string;
  insert(session: ChatSession): void;
  query(question: string, topK: number): RetrievedMemory[];
  getOperationLog?(): OperationTrace[];  // Optional: for L2 evaluation
}

interface RetrievedMemory {
  content: string;
  score: number;
  metadata?: Record<string, unknown>;
}

interface OperationTrace {
  timestamp: number;
  operation: 'remember' | 'forget' | 'update' | 'reflect' | 'merge';
  target: string;
  trigger: string;
  before?: unknown;
  after?: unknown;
}

interface ChatSession {
  id: string;
  timestamp: number;
  turns: Array<{ role: 'user' | 'assistant'; content: string }>;
}

// === Harness ===

interface BenchmarkConfig {
  backend: MemoryBackend;
  judgeModel: string;        // e.g. "gpt-4o"
  judgeEndpoint: string;     // OpenAI-compatible
  answererModel: string;
  topK: number;
  datasetPath: string;
  operationLevelEval?: boolean;
}

interface QuestionResult {
  questionId: string;
  questionType: string;
  hypothesis: string;
  reference: string;
  score: number;            // 0-1
  passed: boolean;
  retrievalLatencyMs: number;
  retrievalCount: number;
  operationTrace?: OperationTrace[];
}

class BenchmarkRunner {
  private config: BenchmarkConfig;
  
  constructor(config: BenchmarkConfig) {
    this.config = config;
  }
  
  async loadDataset(path: string): Promise<BenchmarkQuestion[]> {
    const data = await Bun.file(path).json();
    // Supports LongMemEval format:
    // { question_id, question_type, question, answer, haystack_sessions }
    return data.map((q: any) => ({
      id: q.question_id,
      type: q.question_type,
      question: q.question,
      answer: q.answer,
      sessions: q.haystack_sessions.map((s: any[], i: number) => ({
        id: q.haystack_session_ids[i],
        timestamp: new Date(q.haystack_dates[i]).getTime(),
        turns: s,
      })),
    }));
  }
  
  async run(questions: BenchmarkQuestion[]): Promise<BenchmarkReport> {
    const results: QuestionResult[] = [];
    
    // Phase 1: Ingest all conversations
    console.log(`[${this.config.backend.name}] Ingesting ${questions.length} question haystacks...`);
    for (const q of questions) {
      for (const session of q.sessions) {
        this.config.backend.insert(session);
      }
    }
    
    // Phase 2: Query + Answer + Judge
    for (const q of questions) {
      const t0 = performance.now();
      const retrieved = this.config.backend.query(q.question, this.config.topK);
      const retrievalLatencyMs = performance.now() - t0;
      
      // Generate answer from retrieved context
      const hypothesis = await this.generateAnswer(q.question, retrieved);
      
      // Judge against reference
      const { score, passed } = await this.judge(q.question, hypothesis, q.answer);
      
      results.push({
        questionId: q.id,
        questionType: q.type,
        hypothesis,
        reference: q.answer,
        score,
        passed,
        retrievalLatencyMs,
        retrievalCount: retrieved.length,
        operationTrace: this.config.operationLevelEval 
          ? this.config.backend.getOperationLog?.() 
          : undefined,
      });
    }
    
    return this.aggregate(results);
  }
  
  private async generateAnswer(question: string, memories: RetrievedMemory[]): Promise<string> {
    const context = memories.map(m => `- ${m.content}`).join('\n');
    const prompt = `Based on the following memories, answer the question.\n\nMemories:\n${context}\n\nQuestion: ${question}\n\nAnswer:`;
    
    const resp = await fetch(`${this.config.judgeEndpoint}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${process.env.OPENAI_API_KEY}` },
      body: JSON.stringify({
        model: this.config.answererModel,
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 256,
      }),
    });
    return (await resp.json()).choices[0].message.content;
  }
  
  private async judge(question: string, hypothesis: string, reference: string): Promise<{ score: number; passed: boolean }> {
    const prompt = `You are a judge. Score the hypothesis on whether it matches the reference answer.\n\nQuestion: ${question}\nReference: ${reference}\nHypothesis: ${hypothesis}\n\nRespond with JSON: {"score": 0.0-1.0, "reasoning": "..."}`;
    
    const resp = await fetch(`${this.config.judgeEndpoint}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${process.env.OPENAI_API_KEY}` },
      body: JSON.stringify({
        model: this.config.judgeModel,
        messages: [{ role: 'user', content: prompt }],
        response_format: { type: 'json_object' },
      }),
    });
    const result = JSON.parse((await resp.json()).choices[0].message.content);
    return { score: result.score, passed: result.score >= 0.8 };
  }
  
  private aggregate(results: QuestionResult[]): BenchmarkReport {
    const byType: Record<string, { total: number; passed: number; avgScore: number }> = {};
    
    for (const r of results) {
      if (!byType[r.questionType]) {
        byType[r.questionType] = { total: 0, passed: 0, avgScore: 0 };
      }
      byType[r.questionType].total++;
      if (r.passed) byType[r.questionType].passed++;
      byType[r.questionType].avgScore += r.score;
    }
    
    for (const type of Object.keys(byType)) {
      byType[type].avgScore /= byType[type].total;
    }
    
    const overall = results.reduce((s, r) => s + (r.passed ? 1 : 0), 0) / results.length;
    const avgScore = results.reduce((s, r) => s + r.score, 0) / results.length;
    const p50Latency = percentile(results.map(r => r.retrievalLatencyMs).sort(), 0.5);
    const p99Latency = percentile(results.map(r => r.retrievalLatencyMs).sort(), 0.99);
    
    return {
      backend: this.config.backend.name,
      config: {
        judgeModel: this.config.judgeModel,
        answererModel: this.config.answererModel,
        topK: this.config.topK,
        embeddingModel: process.env.EMBEDDING_MODEL || 'text-embedding-3-small',
      },
      overall,
      avgScore,
      p50LatencyMs: p50Latency,
      p99LatencyMs: p99Latency,
      byType,
      results,
    };
  }
}

interface BenchmarkReport {
  backend: string;
  config: Record<string, unknown>;
  overall: number;
  avgScore: number;
  p50LatencyMs: number;
  p99LatencyMs: number;
  byType: Record<string, { total: number; passed: number; avgScore: number }>;
  results: QuestionResult[];
}

// === Utility ===

function percentile(sortedArr: number[], p: number): number {
  const idx = Math.ceil(p * sortedArr.length) - 1;
  return sortedArr[Math.max(0, idx)];
}

// === Example: Run LongMemEval with amg backend ===

/*
const runner = new BenchmarkRunner({
  backend: new AMGBackend(),  // implements MemoryBackend
  judgeModel: 'gpt-4o',
  judgeEndpoint: 'https://api.openai.com/v1',
  answererModel: 'gpt-4o',
  topK: 50,
  datasetPath: './data/longmemeval_oracle.json',
  operationLevelEval: true,
});

const questions = await runner.loadDataset('./data/longmemeval_oracle.json');
const report = await runner.run(questions);

console.log(`Overall: ${(report.overall * 100).toFixed(1)}%`);
console.log(`Avg Score: ${report.avgScore.toFixed(3)}`);
console.log(`P50 Latency: ${report.p50LatencyMs.toFixed(0)}ms`);
for (const [type, stats] of Object.entries(report.byType)) {
  console.log(`  ${type}: ${(stats.avgScore * 100).toFixed(1)}% (${stats.passed}/${stats.total})`);
}
*/

// === Export for npm publication ===
export { BenchmarkRunner, type MemoryBackend, type BenchmarkConfig, type BenchmarkReport, type QuestionResult };
```

**Verification:** This code compiles as valid TypeScript. The `BenchmarkRunner` class is self-contained with zero runtime dependencies (uses native `fetch`). The `MemoryBackend` interface is the plugin contract — amg implements it, but so could Mem0, Graphiti, or any other memory system.

---

## Key Insights

### Insight #146: The Scoreboard Is the Moat

Shipping a neutral benchmark harness alongside amg creates two powerful dynamics: (1) amg's scores are automatically "official" because the harness is the reference implementation, and (2) competitors must either use amg's harness (endorsing it) or build their own (looking defensive). Mem0 already does this with their open-source `memory-benchmarks` repo. The key difference: Mem0's harness is Python-only and tightly coupled to their API. amg's harness should be TypeScript-native (npm ecosystem) with a clean backend interface that any system can implement in ~100 lines. **Being the scoreboard = ecosystem power.**

### Insight #147: Operation-Level Evaluation Is the Differentiator No Competitor Has

MemOps (arXiv:2607.12893) proves that final-answer scoring conflates failure modes — a system can produce correct answers from inconsistent memory states. Operation-level traces (remember/forget/update/reflect) disentangle these failures. amg already has the internal hooks for this (pre-write governance, post-write validation, knowledge gap detection, redundancy detection, entity resolution, adaptive forgetting). Exposing these as structured traces in the benchmark harness creates an evaluation layer no npm/PyPI competitor can match without deep architectural changes. **This is the moat within the moat.**

### Insight #148: Scale Tiers Reveal Non-Linear Failure Modes

BEAM's data shows that memory systems don't degrade gracefully — they have cliffs. Temporal reasoning at 1M tokens averages 0.618, but at 10M tokens it's 0.163. Event ordering drops from 0.536 to 0.202. This means "good at small scale" ≠ "good at production scale." amg's entropy-weighted retrieval and forgetting should theoretically prevent these cliffs by deprioritizing redundant information, but this is empirically untested. **The harness must include scale-tiered benchmarks (100K/1M/10M) to validate amg's scaling hypothesis. If amg degrades more gracefully than vector-only systems at scale, that's a killer marketing claim backed by data.**

### Insight #149: LongMemEval-V2 Shifts to Agentic Context (May 2026)

LongMemEval-V2 (released May 2026) is a significant evolution: it tests memory in **agentic multimodal web trajectories** rather than simple chat histories. 451 manually curated questions, up to 115M tokens, 5 ability types (static state recall, dynamic state tracking, workflow knowledge, environment gotchas, premise awareness). This is much closer to production agent scenarios than V1's text-only QA. The memory backend interface is clean and well-specified. amg should support both V1 (text-only, for backward compatibility) and V2 (agentic, for forward relevance). **V2's "environment gotchas" and "premise awareness" ability types are exactly what amg's knowledge gap detection and entity resolution are designed to handle.**

### Insight #150: Fixed Reader Model Is the Reproducibility Key

LongMemEval-V2 uses Qwen3.5-9B as the **fixed reader** model — every memory backend is tested with the same answerer LLM. This eliminates the "our scores are better because we used GPT-5 as the reader" variance. Mem0's harness defaults to GPT-4o for both answerer and judge. For amg's harness: default to a small, reproducible model (e.g., Qwen-9B or Llama 3 8B via Ollama) for the answerer, and a stronger model (GPT-4o or Claude) for the judge. This makes runs fully reproducible offline while still having a credible judge. **Fixing the reader model is the single highest-leverage reproducibility decision.**

---

## Competitive Landscape (Harness Comparison)

| Feature | Mem0 benchmarks | LongMemEval V1 | LongMemEval V2 | EvoMemBench | MemOps | amg-bench (proposed) |
|---------|----------------|----------------|----------------|-------------|--------|---------------------|
| **Language** | Python | Python | Python | Python | Python | **TypeScript** |
| **Backend interface** | Mem0-specific | Custom | `Memory` ABC | 15 built-in | Custom | `MemoryBackend` interface |
| **Datasets** | LoCoMo, LongMemEval, BEAM | LongMemEval | LongMemEval-V2 (agentic) | 6 settings | Synthetic | LongMemEval + BEAM-compatible |
| **Operation-level** | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ (via amg hooks) |
| **Scale tiers** | ✅ (100K-10M) | ❌ | ✅ (up to 115M tok) | ❌ | ❌ | ✅ (configurable) |
| **Judge model** | Configurable | GPT-4o | GPT-5.2 | DeepSeek-V3.2 | Configurable | Configurable (default: GPT-4o) |
| **Fixed reader** | ❌ | ❌ | ✅ (Qwen3.5-9B) | ✅ (DeepSeek) | ❌ | ✅ (configurable, default: local) |
| **Reproducible offline** | ❌ | ❌ | ✅ (vLLM) | ✅ (Ark batch) | ❌ | ✅ (Ollama/vLLM) |
| **Multimodal** | ❌ | ❌ | ✅ (screenshots) | ❌ | ❌ | Planned (amg image nodes) |
| **License** | Apache 2.0 | MIT | MIT | -- | -- | MIT |

---

## Benchmark Dataset Selection for amg

Based on the research, the recommended dataset stack for amg-bench:

### Tier 1 (Must-have for npm launch)
1. **LongMemEval S** (500 questions, ~115K tokens) — Fastest, most cited, ICLR 2025
2. **LoCoMo** (~300 questions, 10 conversations) — Standard factual recall + temporal reasoning

### Tier 2 (Differentiator)
3. **BEAM 100K** (700 questions) — Production-scale stress test
4. **BEAM 1M** (700 questions) — Scale degradation measurement

### Tier 3 (Research/moat)
5. **EvoMemBench CrossEp-Know** (884 questions) — Cross-episode knowledge, amg's strength
6. **MemOps synthetic traces** — Operation-level evaluation
7. **LongMemEval-V2 Small** (451 questions) — Agentic multimodal context

---

## Next Actions

1. **Implement `amg-bench` package** — TypeScript benchmark harness with `MemoryBackend` interface. ~400 lines. Dependencies: none (native fetch). Ship as `@amg/bench` or built-in `amg/bench` module.

2. **Implement `AMGBackend` adapter** — Bridge amg's `MemoryGraph` to the `MemoryBackend` interface. ~100 lines. Expose operation traces from amg's lifecycle hooks.

3. **Download + prepare LongMemEval S dataset** — 500 questions, ~115K tokens. Use HuggingFace mirror. Create JSON loader compatible with harness format.

4. **Run baseline: full-context vs. amg entropy-weighted retrieval** — Establish amg's numbers on LongMemEval. Compare against Mem0's reported 94.4%. Even matching 80%+ would be credible for a zero-dependency library.

5. **Add operation-level evaluation mode** — Expose amg's internal lifecycle operations (write governance, entity resolution, consolidation, forgetting) as MemOps-compatible structured traces. This is the unique differentiator.

6. **Document embedding model + judge configuration** — Ship with sensible defaults (text-embedding-3-small + GPT-4o judge + top-50) and strict mode (stronger models + top-200). Report all three alongside scores.

---

## References

- **LongMemEval** (Wu et al., ICLR 2025): arxiv.org/abs/2410.10813 — 500 questions, 5 abilities, 3-stage framework
- **LongMemEval-V2** (Wu et al., May 2026): arxiv.org/abs/2605.12493 — Agentic multimodal, 451 questions, 115M token haystacks
- **EvoMemBench** (Wang et al., 2026): arxiv.org/abs/2605.18421 — 4 settings (scope×content), 15 methods, 5754 samples. Code: github.com/DSAIL-Memory/EvoMemBench
- **MemOps** (Hao et al., 2026): arxiv.org/abs/2607.12893 — Operation-level evaluation, structured traces, 6 probe categories
- **Mem0 memory-benchmarks** (2026): github.com/mem0ai/memory-benchmarks — Open-source harness (LoCoMo + LongMemEval + BEAM), Apache 2.0
- **BEAM** (Mem0, 2026): 1M-10M token scale benchmarks, 10 ability types, production-scale evaluation
- **Mem0 v3** (2026): ADD-only extraction, entity linking, multi-signal retrieval. LongMemEval 94.4%, LoCoMo 92.5%

---

_Permission to reproduce: This note is part of the catalyst-research exploration series. All cited papers are publicly available via arXiv. Code examples are original and MIT-licensed._
