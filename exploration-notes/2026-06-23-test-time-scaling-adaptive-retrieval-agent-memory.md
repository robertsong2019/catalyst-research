# Test-Time Scaling for Agent Memory: Adaptive Retrieval Effort and Self-Correcting Search

> **Date:** 2026-06-23
> **Context:** agent-memory-graph 检索从静态到自适应 — test-time compute scaling 应用于 agent memory retrieval
> **Trigger:** AdaMEM (ICML 2026) 发表, ICLR 2026 MemAgent Workshop 12+ 篇自适应记忆论文, MemR³ 闭环检索, A-MAC 准入控制
> **Position:** agent-memory-graph 检索层升级 — 从固定 search_hybrid 到自适应检索控制器

---

## 1. Core Concepts (5)

### 1.1 Test-Time Compute Scaling for Memory — AdaMEM (ICML 2026, arXiv:2606.05684)

AdaMEM (Zhang et al.) 提出 **agent memory 的测试时自适应框架**:

- **Hybrid 记忆架构**: Long-term trajectory memory (离线构建的原始经验池 ℳ) + Short-term strategy memory (在线生成的动态策略 z_t)
- **关键创新**: 不在 episode 开始时一次性检索,而是在每一步根据当前状态 s_t 动态检索并合成策略
- **Three inference modes**: 
  - `AdaMEM-low`: 持久策略,仅在必要时刷新 (token 高效)
  - `AdaMEM-high`: 每步重新生成策略 (最大适应性)
  - `AdaMEM-MFT`: Step-wise Memory Fine-Tuning,训练模型生成高质量策略

**关键数据**: 
- ALFWorld +13% relative gain, WebShop +11%, HotpotQA 领先
- **Positive scaling trend**: 增加 test-time compute (提高策略刷新频率) → 性能单调提升
- 对比: Synapse (static retrieval) 显示 **negative scaling** — 消耗更多 token 但性能更差
- Step-MFT 通过 rejection sampling: 只保留 "改变 agent action 且导向成功" 的策略做 SFT

**核心洞察**: Memory retrieval is not a lookup — it's a **generation** process. The system retrieves raw experiences, then *synthesizes* a strategy tailored to the current state. This is fundamentally different from retrieving a pre-computed strategy.

**对 agent-memory-graph 的意义**: 当前 search_hybrid() 是一次性检索 — 返回结果后不做任何后续动作。AdaMEM 的模式可以在 agent-memory-graph 上实现: `search_adaptive(query, {effort: 'low'|'high'|'max'})` — 低 effort 走 BM25+vector 快速返回, 高 effort 走 graph traversal+reasoning_path, max effort 走 iterative retrieve-reason-prune 循环。

### 1.2 Closed-Loop Retrieval: Retrieve-Reflect-Answer — MemR³ (arXiv:2512.20237, Dec 2025)

MemR³ (Du et al.) 把标准 retrieve-then-answer 管道改造为 **闭环顺序决策过程**:

```
State: s = (q, S, E, G, k)
- q: 原始查询
- S: 已检索的 snippets
- E: 已获取的证据 (confirmed facts)
- G: 信息缺口 (missing information — "gaps")
- k: 迭代计数器 (控制 early stopping)
```

**Router** 在三个操作间选择:
1. **Retrieve**: 根据当前 gap G 生成针对性子查询, 从记忆库检索
2. **Reflect**: 基于当前证据 E 推理, 更新 gap G (标记已解决的缺口, 识别新缺口)
3. **Answer**: 当 E 足够充分时, 生成最终答案

**Evidence-Gap Tracker** 是核心机制:
- 不是 "检索→回答" 的线性管道
- 而是 "检索→反思→发现缺口→再检索→...→充分→回答" 的闭环
- 例子: "Andrew 领养 Toby 和 Buddy 之间过了多少月?"
  - Step 1: 检索 "Andrew 领养 Toby" → 找到 2023年7月11日
  - Step 2: Reflect → Evidence: Toby 领养日期已知; Gap: Buddy 领养日期未知
  - Step 3: Retrieve "When was Buddy adopted?" → 找到 2024年3月
  - Step 4: Reflect → Evidence 充分 → Answer: ~8个月

**关键数据**: MemR³ 在 RAG backbone 上 +7.29%, Zep backbone 上 +1.94% (LoCoMo benchmark, GPT-4.1-mini)。Plug-and-play 兼容控制器。

**对 agent-memory-graph 的意义**: Evidence-gap tracker 可以作为一个独立 API: `search_with_gaps(query, {max_iterations: 3})` — 先检索, 分析缺口, 生成子查询, 再检索。不需要 LLM — 用 embedding similarity + graph traversal 做 gap detection (已有 5-dim similarity toolkit)。

### 1.3 Query Complexity Routing — Adaptive-RAG + 4-Tier AHR Framework

**Adaptive-RAG** (NAACL 2024 → 2026 共识最佳实践):
- 训练小分类器预测查询复杂度
- 路由到三条管道:
  - **No retrieval**: 简单事实 ("法国首都是哪?")
  - **Single-step retrieval**: 中等查询 ("什么是 RAG?")
  - **Multi-step iterative retrieval**: 复杂推理 ("A公司2024年收购B公司后对C行业的影响?")

**4-Tier AHR Framework** (arXiv:2604.14222, 2026):
- Tier 1: Simple lookup → Vector search ($0.001/query)
- Tier 2: Multi-section → Tree reasoning ($0.01/query)  
- Tier 3: Cross-reference → Tree reasoning + fusion ($0.05/query)
- Tier 4: Complex analysis → Both systems + result fusion ($0.10+ /query)
- **Adaptive Hybrid Retrieval (AHR)**: GPT-4o-mini 分类器 → tier 路由
- 关键发现: AHR 避免 "灾难性失败" — Vector RAG 在医疗查询上 0.20, Tree Reasoning 在多文档查询上 0.60

**Compute Allocation for Reasoning-Intensive Retrieval** (ICLR 2026, Apparaju & Gupta):
- BRIGHT benchmark + Gemini 2.5 模型家族
- **关键发现**: BM25 → LLM-augmented expansion (Flash-Lite) = +14.35 NDCG@10, +23.43 Recall@10
- 但 Flash-Lite → Pro (27× 更贵) = 仅 +0.82 Recall@10 → **0.03 Recall points per dollar**
- **结论**: 第一级 LLM 增强 (cheap model) 回报巨大, 后续投入急剧递减

**对 agent-memory-graph 的意义**: 当前 search_hybrid 对所有查询用相同策略。可以添加 `classify_query(query)` → 返回 {simple, moderate, complex, multi_hop} → 路由到不同检索管道。**简单查询用 BM25-only 省钱, 复杂查询走 graph reasoning**。

### 1.4 Self-Correcting Retrieval — CRAG + Self-RAG + SCMRAG

**Corrective RAG (CRAG)** (Yan et al., arXiv:2401.15884):
- **Retrieval Evaluator**: 轻量级评估器给每个检索文档打分
- 三档分类: **Correct** (相关) / **Incorrect** (不相关) / **Ambiguous** (不确定)
- Correct → 直接使用
- Incorrect → 触发 web search 或重检索
- Ambiguous → 仅使用 top-k 最相关的 + 扩展检索
- **关键数据**: PopQA +20.0% accuracy, Biography +36.9% FactScore vs Self-RAG

**Self-RAG** (Asai et al., ICLR 2024):
- 训练 LLM 生成 **reflection tokens**:
  - `[Retrieve]`: 是否需要检索?
  - `[IsRel]`: 检索到的文档是否相关?
  - `[IsSup]`: 答案是否被证据支持?
  - `[IsUse]`: 答案是否有用?
- 自我批判循环: 生成 → 评估 → 可能重检索/重生成

**SCMRAG** (AAMAS 2025):
- Self-Corrective Multihop Retrieval
- 迭代: Answer → Evaluate Support Level → 若不充分 → Web scrape for additional evidence → Re-answer
- 在 PopQA 76.6% (vs CRAG 59.3%, Self-RAG 54.9%)

**对 agent-memory-graph 的意义**: 可以添加 `grade_retrieval(query, results)` API — 给检索结果打分 (relevant/irrelevant/ambiguous), 让调用者决定是否重检索。不需要 LLM — 用 query-result cosine similarity + graph connectivity (相关结果通常在图中互相关联) 做评分。

### 1.5 Adaptive Memory Admission Control — A-MAC (ICLR 2026 Workshop)

A-MAC (Zhang et al., Workday AI) 把 **"什么该存入记忆"** 视为结构化决策问题:

**5-Factor Scoring** (可解释, 可审计):
```
S(m) = ω · [U(m), C(m), N(m), R(m), T(m)]

U(m) — Future Utility: 候选记忆在未来任务中的预期有用性
C(m) — Factual Confidence: 是否被对话证据支持 (ROUGE-L with supporting spans)
N(m) — Semantic Novelty: 与现有记忆的语义距离 (避免冗余)
R(m) — Relevance: 与当前任务/用户的相关性
T(m) — Temporal Value: 时效性 (新闻 vs 常识)
```

**Algorithm**: 
1. 并行计算 5 个因子
2. 加权评分 S(m)
3. 若 S(m) ≥ θ → 检查冲突 → 合并或添加
4. 若 S(m) < θ → 拒绝

**关键创新**: 
- **Hallucination 作为一等公民**: C(m) 直接衡量证据支持度, 防止幻觉传播
- **Conflict resolution**: 新记忆与旧记忆冲突时, 评分高者保留, 低者被合并
- **Rule-based + learned weights**: 两种模式, 规则模式无需训练

**对 agent-memory-graph 的意义**: agent-memory-graph 已有 consolidation pipeline (semantic_divergence + retention_score + memory_evict), 但缺乏**写入时准入控制**。可以添加 `should_admit(candidate, existing_memories)` → {admit, reject, merge_with: id}。5 个因子可以用现有工具计算: N(m) = embedding distance, R(m) = tag overlap, C(m) = source/trust_level (已有), U(m) 和 T(m) 简化为规则。

---

## 2. Runnable Code: AdaptiveRetriever (~250 lines TypeScript)

```typescript
/**
 * AdaptiveRetriever — Test-Time Adaptive Memory Retrieval Controller
 * 
 * Inspired by: AdaMEM (ICML 2026), MemR³ (arXiv:2512.20237), 
 *              A-MAC (ICLR 2026 Workshop), CRAG (arXiv:2401.15884),
 *              Adaptive-RAG (NAACL 2024), Compute Allocation (ICLR 2026)
 * 
 * Features:
 * 1. Query complexity classification → tiered routing
 * 2. Evidence-gap tracking for multi-hop queries  
 * 3. Retrieval quality grading (CRAG-inspired)
 * 4. Test-time strategy adaptation (AdaMEM-inspired)
 * 5. Adaptive admission control (A-MAC-inspired)
 */

// ============ Types ============

type QueryComplexity = 'simple' | 'moderate' | 'complex' | 'multi_hop';
type RetrievalGrade = 'relevant' | 'irrelevant' | 'ambiguous';
type EffortLevel = 'low' | 'medium' | 'high' | 'max';

interface MemoryEntry {
  id: string;
  content: string;
  tags: string[];
  embedding?: number[];
  timestamp: number;
  source?: string;
  trust_level?: number;
}

interface SearchResult {
  entry: MemoryEntry;
  score: number;
  grade?: RetrievalGrade;
}

interface EvidenceGap {
  query: string;
  evidence: SearchResult[];
  gaps: string[];
  satisfied: boolean;
}

interface RetrievalResult {
  results: SearchResult[];
  complexity: QueryComplexity;
  effort: EffortLevel;
  iterations: number;
  gaps?: EvidenceGap;
  strategy?: string;
  cost_estimate: number;
}

// ============ Query Complexity Classifier ============

class QueryComplexityClassifier {
  private multiHopIndicators = [
    /\bhow\b.*\brelate\b/i, /\bcompare\b.*\band\b/i, /\bdifference\b/i,
    /\bbetween\b.*\band\b/i, /\bbecause\b/i, /\bwhy\b.*\bthen\b/i,
    /\bcause\b/i, /\beffect\b/i, /\bimpact\b/i, /\bresult\b/i,
    /\bchain\b/i, /\bsequence\b/i, /\bflow\b/i,
  ];
  
  private complexIndicators = [
    /\bhow\b/i, /\bwhy\b/i, /\bexplain\b/i, /\banalyze\b/i,
    /\bdesign\b/i, /\barchitecture\b/i, /\btrade.?off\b/i,
  ];

  classify(query: string): QueryComplexity {
    const words = query.split(/\s+/).length;
    
    // Multi-hop: explicit relational reasoning
    const multiHopScore = this.multiHopIndicators
      .filter(p => p.test(query)).length;
    if (multiHopScore >= 2 || (multiHopScore >= 1 && words > 15)) {
      return 'multi_hop';
    }
    
    // Complex: requires explanation/analysis
    const complexScore = this.complexIndicators
      .filter(p => p.test(query)).length;
    if (complexScore >= 1 && words > 10) {
      return 'complex';
    }
    
    // Moderate: non-trivial but single-concept
    if (words > 8) {
      return 'moderate';
    }
    
    return 'simple';
  }
}

// ============ Retrieval Grader (CRAG-inspired) ============

class RetrievalGrader {
  private relevanceThreshold: number;
  private ambiguityRange: [number, number];

  constructor(threshold = 0.65, ambiguity: [number, number] = [0.4, 0.65]) {
    this.relevanceThreshold = threshold;
    this.ambiguityRange = ambiguity;
  }

  grade(queryEmbedding: number[], result: SearchResult): RetrievalGrade {
    if (!result.entry.embedding) return 'ambiguous';
    
    const sim = this.cosineSim(queryEmbedding, result.entry.embedding);
    
    if (sim >= this.relevanceThreshold) return 'relevant';
    if (sim >= this.ambiguityRange[0]) return 'ambiguous';
    return 'irrelevant';
  }

  gradeBatch(
    queryEmbedding: number[],
    results: SearchResult[]
  ): { graded: SearchResult[]; verdict: 'correct' | 'incorrect' | 'ambiguous' } {
    const graded = results.map(r => ({
      ...r,
      grade: this.grade(queryEmbedding, r),
    }));
    
    const relevantCount = graded.filter(r => r.grade === 'relevant').length;
    const total = graded.length;
    
    // CRAG-style verdict
    if (relevantCount >= Math.ceil(total * 0.5)) {
      return { graded, verdict: 'correct' };
    }
    if (relevantCount === 0) {
      return { graded, verdict: 'incorrect' };
    }
    return { graded, verdict: 'ambiguous' };
  }

  private cosineSim(a: number[], b: number[]): number {
    let dot = 0, normA = 0, normB = 0;
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    return dot / (Math.sqrt(normA) * Math.sqrt(normB) + 1e-10);
  }
}

// ============ Evidence-Gap Tracker (MemR³-inspired) ============

class EvidenceGapTracker {
  private maxIterations: number;
  
  constructor(maxIterations = 3) {
    this.maxIterations = maxIterations;
  }

  /**
   * Analyze evidence vs query to identify gaps.
   * Uses entity extraction + tag matching (no LLM needed).
   */
  analyzeGaps(
    query: string,
    evidence: SearchResult[],
    knownEntities: Set<string>
  ): EvidenceGap {
    const queryEntities = this.extractEntities(query);
    const evidenceText = evidence
      .map(r => r.entry.content)
      .join(' ');
    const evidenceEntities = this.extractEntities(evidenceText);
    
    // Find entities in query not covered by evidence
    const gaps = queryEntities.filter(
      e => !evidenceEntities.has(e) && !knownEntities.has(e)
    );
    
    const satisfied = gaps.length === 0;
    
    return {
      query,
      evidence,
      gaps: gaps.map(g => `Missing information about: ${g}`),
      satisfied,
    };
  }

  /**
   * Generate sub-queries for identified gaps.
   */
  generateSubQueries(gaps: EvidenceGap): string[] {
    return gaps.gaps.map(g => {
      const entity = g.replace('Missing information about: ', '');
      return `Tell me about ${entity}`;
    });
  }

  private extractEntities(text: string): Set<string> {
    // Simple extraction: capitalized words, technical terms, known patterns
    const words = text.match(/\b[A-Z][a-z]+\b/g) || [];
    const techTerms = text.match(/\b[a-z]+_[a-z]+\b/g) || [];
    const quoted = text.match(/"([^"]+)"/g)?.map(s => s.slice(1, -1)) || [];
    return new Set([...words, ...techTerms, ...quoted]);
  }
}

// ============ Adaptive Memory Admission (A-MAC-inspired) ============

interface AdmissionScore {
  utility: number;
  confidence: number;
  novelty: number;
  relevance: number;
  temporal: number;
  total: number;
  decision: 'admit' | 'reject' | 'merge';
  mergeWith?: string;
}

class AdmissionController {
  private weights: { U: number; C: number; N: number; R: number; T: number };
  private threshold: number;

  constructor(
    weights = { U: 0.25, C: 0.30, N: 0.20, R: 0.15, T: 0.10 },
    threshold = 0.5
  ) {
    this.weights = weights;
    this.threshold = threshold;
  }

  evaluate(
    candidate: MemoryEntry,
    existing: MemoryEntry[],
    queryTags: string[]
  ): AdmissionScore {
    // U(m): Future utility — heuristic: entries with code/structured content score higher
    const utility = candidate.content.includes('```') 
      || candidate.tags.length > 2 ? 0.8 : 0.5;

    // C(m): Confidence — trust_level if available, else source-based
    const confidence = candidate.trust_level ?? 
      (candidate.source ? 0.7 : 0.4);

    // N(m): Novelty — cosine distance to nearest existing entry
    const novelty = this.computeNovelty(candidate, existing);

    // R(m): Relevance — tag overlap with current task
    const overlap = candidate.tags.filter(t => queryTags.includes(t)).length;
    const relevance = Math.min(1, overlap / Math.max(1, queryTags.length));

    // T(m): Temporal — recency bonus
    const ageHours = (Date.now() - candidate.timestamp) / 3_600_000;
    const temporal = Math.max(0, 1 - ageHours / (30 * 24)); // 30-day half-life

    const total = 
      this.weights.U * utility +
      this.weights.C * confidence +
      this.weights.N * novelty +
      this.weights.R * relevance +
      this.weights.T * temporal;

    // Find conflict
    const conflict = existing.find(e => 
      e.tags.some(t => candidate.tags.includes(t)) &&
      this.tagJaccard(e.tags, candidate.tags) > 0.5
    );

    let decision: 'admit' | 'reject' | 'merge' = 'reject';
    let mergeWith: string | undefined;

    if (total >= this.threshold) {
      if (conflict && total > this.computeExistingScore(conflict)) {
        decision = 'merge';
        mergeWith = conflict.id;
      } else if (!conflict) {
        decision = 'admit';
      }
    }

    return { utility, confidence, novelty, relevance, temporal, total, decision, mergeWith };
  }

  private computeNovelty(candidate: MemoryEntry, existing: MemoryEntry[]): number {
    if (!candidate.embedding || existing.length === 0) return 1.0;
    const maxSim = Math.max(...existing.map(e => {
      if (!e.embedding) return 0;
      return this.cosineSim(candidate.embedding!, e.embedding);
    }));
    return Math.max(0, 1 - maxSim);
  }

  private computeExistingScore(entry: MemoryEntry): number {
    return (entry.trust_level ?? 0.5) * 0.6 + 0.4;
  }

  private tagJaccard(a: string[], b: string[]): number {
    const setA = new Set(a), setB = new Set(b);
    const inter = [...setA].filter(x => setB.has(x)).length;
    const union = new Set([...a, ...b]).size;
    return inter / Math.max(1, union);
  }

  private cosineSim(a: number[], b: number[]): number {
    let dot = 0, normA = 0, normB = 0;
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    return dot / (Math.sqrt(normA) * Math.sqrt(normB) + 1e-10);
  }
}

// ============ Adaptive Retriever (Main Controller) ============

class AdaptiveRetriever<T extends MemoryEntry> {
  private classifier = new QueryComplexityClassifier();
  private grader = new RetrievalGrader();
  private gapTracker = new EvidenceGapTracker();
  private admission = new AdmissionController();
  
  private store: Map<string, T> = new Map();
  private strategies: Map<string, string> = new Map(); // AdaMEM-style strategy cache
  private queryHistory: { query: string; complexity: QueryComplexity; success: boolean }[] = [];

  // Strategy memory — adapts based on query patterns (AdaMEM-inspired)
  private globalStrategy = '';

  add(entry: T, queryTags: string[] = []): AdmissionScore {
    const existing = [...this.store.values()];
    const score = this.admission.evaluate(entry, existing, queryTags);
    
    if (score.decision === 'admit') {
      this.store.set(entry.id, entry);
    } else if (score.decision === 'merge' && score.mergeWith) {
      const old = this.store.get(score.mergeWith);
      if (old) {
        this.store.set(entry.id, {
          ...entry,
          tags: [...new Set([...old.tags, ...entry.tags])],
          trust_level: Math.max(
            old.trust_level ?? 0.5,
            entry.trust_level ?? 0.5
          ),
        });
        this.store.delete(score.mergeWith);
      }
    }
    return score;
  }

  /**
   * Main retrieval method — adapts strategy based on query complexity.
   * Implements: complexity routing + optional gap tracking + grading + strategy memory.
   */
  retrieve(
    query: string,
    queryEmbedding: number[],
    options: {
      effort?: EffortLevel;
      enableGapTracking?: boolean;
      enableGrading?: boolean;
      knownEntities?: Set<string>;
    } = {}
  ): RetrievalResult {
    const {
      effort = 'medium',
      enableGapTracking = true,
      enableGrading = true,
      knownEntities = new Set(),
    } = options;

    // Step 1: Classify query complexity
    const complexity = this.classifier.classify(query);
    
    // Step 2: Determine effort if not explicitly set
    const actualEffort = this.resolveEffort(complexity, effort);
    
    // Step 3: Route to appropriate retrieval strategy
    const strategy = this.getStrategy(complexity, actualEffort);
    
    // Step 4: Execute retrieval
    let results = this.executeStrategy(strategy, query, queryEmbedding);
    
    // Step 5: Grade results (CRAG-inspired)
    let verdict: 'correct' | 'incorrect' | 'ambiguous' = 'correct';
    if (enableGrading && results.length > 0) {
      const graded = this.grader.gradeBatch(queryEmbedding, results);
      results = graded.graded;
      verdict = graded.verdict;
      
      // CRAG-style correction
      if (verdict === 'incorrect') {
        // Retry with broader search
        const broader = this.executeStrategy('graph_bfs', query, queryEmbedding);
        if (broader.length > results.length) {
          results = this.grader.gradeBatch(queryEmbedding, broader).graded;
        }
      }
    }
    
    // Step 6: Gap tracking for multi-hop queries (MemR³-inspired)
    let gaps: EvidenceGap | undefined;
    let iterations = 1;
    
    if (enableGapTracking && (complexity === 'multi_hop' || complexity === 'complex')) {
      gaps = this.gapTracker.analyzeGaps(query, results, knownEntities);
      
      while (!gaps.satisfied && iterations < 3) {
        const subQueries = this.gapTracker.generateSubQueries(gaps);
        for (const sq of subQueries) {
          const subResults = this.executeStrategy(
            actualEffort === 'max' ? 'graph_bfs' : 'vector',
            sq,
            queryEmbedding // simplified: reuse query embedding
          );
          gaps.evidence.push(...subResults);
        }
        gaps = this.gapTracker.analyzeGaps(
          query, gaps.evidence,
          new Set([...knownEntities, ...gaps.evidence.map(r => r.entry.id)])
        );
        iterations++;
      }
    }
    
    // Step 7: Estimate cost
    const cost = this.estimateCost(actualEffort, iterations);

    // Step 8: Update strategy memory (AdaMEM-inspired)
    this.updateStrategy(complexity, strategy, results.length);

    return {
      results: results.sort((a, b) => b.score - a.score),
      complexity,
      effort: actualEffort,
      iterations,
      gaps,
      strategy,
      cost_estimate: cost,
    };
  }

  private resolveEffort(complexity: QueryComplexity, requested: EffortLevel): EffortLevel {
    if (requested !== 'medium') return requested;
    // Auto-resolve based on complexity
    const mapping: Record<QueryComplexity, EffortLevel> = {
      simple: 'low',
      moderate: 'medium',
      complex: 'high',
      multi_hop: 'max',
    };
    return mapping[complexity];
  }

  private getStrategy(complexity: QueryComplexity, effort: EffortLevel): string {
    // Use global strategy if available (AdaMEM-style)
    if (this.globalStrategy && effort === 'low') {
      return `cached:${this.globalStrategy}`;
    }
    
    const strategies: Record<string, string> = {
      'simple_low': 'bm25',
      'simple_medium': 'bm25+vector',
      'moderate_low': 'bm25',
      'moderate_medium': 'vector',
      'moderate_high': 'vector+graph',
      'complex_medium': 'vector+graph',
      'complex_high': 'graph_bfs+reasoning',
      'complex_max': 'graph_bfs+reasoning',
      'multi_hop_high': 'graph_bfs+reasoning',
      'multi_hop_max': 'iterative_graph',
    };
    
    return strategies[`${complexity}_${effort}`] || 'vector';
  }

  private executeStrategy(
    strategy: string,
    query: string,
    queryEmbedding: number[]
  ): SearchResult[] {
    const entries = [...this.store.values()];
    const results: SearchResult[] = [];
    
    if (strategy.includes('bm25')) {
      // Simple BM25-style: tag + content overlap
      const queryTerms = query.toLowerCase().split(/\s+/);
      for (const entry of entries) {
        const contentTerms = entry.content.toLowerCase().split(/\s+/);
        const overlap = queryTerms.filter(t => contentTerms.includes(t)).length;
        const tagMatch = entry.tags.filter(t => 
          queryTerms.some(qt => t.toLowerCase().includes(qt))
        ).length;
        const score = (overlap / Math.max(1, queryTerms.length)) * 0.6 +
                      (tagMatch / Math.max(1, entry.tags.length)) * 0.4;
        if (score > 0) {
          results.push({ entry, score });
        }
      }
    }
    
    if (strategy.includes('vector')) {
      // Vector similarity
      for (const entry of entries) {
        if (!entry.embedding) continue;
        const sim = this.cosineSim(queryEmbedding, entry.embedding);
        results.push({ entry, score: sim });
      }
    }
    
    if (strategy.includes('graph')) {
      // Graph traversal: find entries connected via shared tags
      const seedTags = new Set<string>();
      const seed = entries
        .map(e => ({ e, score: entryTagOverlap(e, query) }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 3);
      
      for (const s of seed) {
        if (s.score === 0) continue;
        seedTags.add(s.e.id);
        // Expand via shared tags
        const expansionTags = new Set(s.e.tags);
        for (const e of entries) {
          if (e.id === s.e.id) continue;
          if (e.tags.some(t => expansionTags.has(t))) {
            const existing = results.find(r => r.entry.id === e.id);
            if (!existing) {
              results.push({ 
                entry: e, 
                score: s.score * 0.5 // decay expansion score 
              });
            }
          }
        }
      }
    }
    
    // Deduplicate by entry id, keeping highest score
    const seen = new Map<string, SearchResult>();
    for (const r of results) {
      const existing = seen.get(r.entry.id);
      if (!existing || r.score > existing.score) {
        seen.set(r.entry.id, r);
      }
    }
    
    return [...seen.values()].sort((a, b) => b.score - a.score).slice(0, 20);

    function entryTagOverlap(entry: T, q: string): number {
      const qTerms = q.toLowerCase().split(/\s+/);
      return entry.tags.filter(t => 
        qTerms.some(qt => t.toLowerCase().includes(qt))
      ).length;
    }
  }

  private updateStrategy(
    complexity: QueryComplexity,
    strategy: string,
    resultCount: number
  ): void {
    // Simple strategy adaptation: track what works
    this.queryHistory.push({
      query: '',
      complexity,
      success: resultCount > 0,
    });
    
    // Keep last 100 queries
    if (this.queryHistory.length > 100) {
      this.queryHistory.shift();
    }
    
    // Update global strategy based on recent success patterns
    const recent = this.queryHistory.slice(-20);
    const successRate = recent.filter(q => q.success).length / recent.length;
    if (successRate > 0.7 && strategy) {
      this.globalStrategy = strategy;
    }
  }

  private estimateCost(effort: EffortLevel, iterations: number): number {
    const baseCost: Record<EffortLevel, number> = {
      low: 0.001,
      medium: 0.005,
      high: 0.02,
      max: 0.05,
    };
    return baseCost[effort] * iterations;
  }

  private cosineSim(a: number[], b: number[]): number {
    let dot = 0, normA = 0, normB = 0;
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    return dot / (Math.sqrt(normA) * Math.sqrt(normB) + 1e-10);
  }

  // ============ Stats ============
  
  stats() {
    return {
      store_size: this.store.size,
      strategies_cached: this.strategies.size,
      queries_seen: this.queryHistory.length,
      recent_success_rate: this.queryHistory.slice(-20)
        .filter(q => q.success).length / Math.max(1, Math.min(20, this.queryHistory.length)),
    };
  }
}

// ============ Test/Demo ============

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(`❌ ${message}`);
  console.log(`✅ ${message}`);
}

console.log('\n=== AdaptiveRetriever Test Suite ===\n');

// Setup
const retriever = new AdaptiveRetriever<MemoryEntry>();

// Seed data
const now = Date.now();
const entries: MemoryEntry[] = [
  {
    id: 'e1', content: 'React hooks allow state management in functional components',
    tags: ['react', 'hooks', 'frontend'], timestamp: now - 3600_000,
    embedding: [0.9, 0.1, 0.0], trust_level: 0.8,
  },
  {
    id: 'e2', content: 'Vue composition API provides reactive state management similar to React hooks',
    tags: ['vue', 'composition-api', 'frontend'], timestamp: now - 7200_000,
    embedding: [0.7, 0.3, 0.0], trust_level: 0.7,
  },
  {
    id: 'e3', content: 'Docker containers package applications with their dependencies',
    tags: ['docker', 'devops', 'containers'], timestamp: now - 86400_000,
    embedding: [0.1, 0.1, 0.9], trust_level: 0.9,
  },
];

// Test 1: Admission Control (A-MAC)
console.log('--- Test 1: Admission Control ---');
for (const entry of entries) {
  retriever.add(entry, ['frontend', 'devops']);
}
assert(retriever.stats().store_size === 3, 'All 3 entries admitted');

// Test 2: Simple query → low effort → BM25
console.log('\n--- Test 2: Simple Query Routing ---');
const simpleResult = retriever.retrieve(
  'React hooks',
  [0.9, 0.1, 0.0],
  { effort: 'low', enableGapTracking: false, enableGrading: false }
);
assert(simpleResult.complexity === 'simple', 'Classified as simple');
assert(simpleResult.strategy.includes('bm25'), 'Routes to BM25');
assert(simpleResult.cost_estimate === 0.001, 'Low cost for simple query');
console.log(`   Strategy: ${simpleResult.strategy}, Cost: $${simpleResult.cost_estimate}`);

// Test 3: Complex query → graph reasoning
console.log('\n--- Test 3: Complex Query Routing ---');
const complexResult = retriever.retrieve(
  'How do React hooks compare to Vue composition API for state management?',
  [0.8, 0.2, 0.0],
  { effort: 'high', enableGapTracking: false }
);
assert(complexResult.complexity === 'complex' || complexResult.complexity === 'multi_hop',
  'Classified as complex/multi_hop');
assert(complexResult.strategy.includes('graph'), 'Routes to graph strategy');
console.log(`   Strategy: ${complexResult.strategy}, Cost: $${complexResult.cost_estimate}`);

// Test 4: Evidence-Gap Tracking
console.log('\n--- Test 4: Evidence-Gap Tracking ---');
const gapResult = retriever.retrieve(
  'What is the relationship between Docker containers and Kubernetes pods?',
  [0.1, 0.1, 0.9],
  { effort: 'max', enableGapTracking: true }
);
assert(gapResult.gaps !== undefined, 'Gap tracking enabled');
assert(gapResult.iterations >= 1, 'At least 1 iteration');
console.log(`   Gaps found: ${gapResult.gaps?.gaps.length || 0}, Iterations: ${gapResult.iterations}`);

// Test 5: Adaptive effort maps to complexity
console.log('\n--- Test 5: Auto Effort Resolution ---');
const autoResult = retriever.retrieve(
  'What is Docker?',
  [0.1, 0.1, 0.9],
  { effort: 'medium', enableGapTracking: false, enableGrading: false }
);
assert(autoResult.effort === 'low' || autoResult.effort === 'medium',
  `Auto-resolved effort: ${autoResult.effort}`);
console.log(`   Complexity: ${autoResult.complexity} → Effort: ${autoResult.effort}`);

// Test 6: Retrieval grading
console.log('\n--- Test 6: Retrieval Grading ---');
const gradedResult = retriever.retrieve(
  'React hooks state management',
  [0.9, 0.1, 0.0],
  { effort: 'medium', enableGrading: true, enableGapTracking: false }
);
assert(gradedResult.results.every(r => r.grade !== undefined),
  'All results have grades');
const relevant = gradedResult.results.filter(r => r.grade === 'relevant').length;
console.log(`   Relevant results: ${relevant}/${gradedResult.results.length}`);

// Test 7: Stats and strategy adaptation
console.log('\n--- Test 7: Strategy Adaptation ---');
const stats = retriever.stats();
console.log(`   Store: ${stats.store_size}, Queries: ${stats.queries_seen}, Success: ${(stats.recent_success_rate * 100).toFixed(0)}%`);

console.log('\n=== All Tests Passed ===\n');
```

---

## 3. Key Insights (5)

### 3.1 Memory retrieval is becoming a reasoning process, not a lookup

**证据**: AdaMEM 的核心创新不是"更好的检索算法",而是把检索结果作为**原料**, 在线 **合成** 一个针对当前状态的策略。MemR³ 的 retrieve-reflect-answer 闭环把检索变成了一个 **顺序决策过程**。A-MAC 把"是否存入记忆"变成了一个 **5-factor 决策问题**。

**含义**: agent-memory-graph 的 search_hybrid() 当前是一个 lookup — 给定 query 返回 top-k。未来需要提供 `search_adaptive()` — 一个能够 **自我评估、自我修正、动态调整努力程度** 的检索控制器。这不是替换 search_hybrid,而是在其上层添加智能层。

**量化**: AdaMEM 的 test-time scaling 表明, 增加检索努力(策略刷新频率)可以 **单调提升** 性能。当前 search_hybrid 是零努力适应(一次检索固定策略), 添加自适应可以解锁这个 scaling 维度。

### 3.2 检索 LLM 增强的收益递减极其陡峭 — 第一级是 95% 的价值

**证据**: Compute Allocation (ICLR 2026) 的数据:
- BM25 → Flash-Lite LLM expansion: **+14.35 NDCG@10, +23.43 Recall@10** (巨大提升)
- Flash-Lite → Pro (27× 更贵): **仅 +0.82 Recall@10** → 0.03 Recall per dollar
- 结论: **第一级 LLM 增强 = 95%+ 的价值**, 后续投入急剧递减

**含义**: agent-memory-graph 不需要为每个查询使用昂贵的 LLM 推理。一个轻量级 query expansion (用 embedding model 或小 LLM) 配合 graph traversal, 就能获得大部分价值。**成本结构应该是: 95% 的查询用 cheap path, 5% 的复杂查询才用 expensive path**。

### 3.3 Evidence-Gap Tracker 是多跳推理的缺失原语

**证据**: MemR³ 的 evidence-gap tracker 是其核心机制 — 不是更好的检索算法, 而是 **追踪已知/未知的状态机**。SCMRAG 的迭代自纠正也是类似模式: 检查充分性 → 不够 → 补充检索。SEAL-RAG (ICLR 2026) 的 entity extraction + gap repair 同样如此。

**含义**: agent-memory-graph 的 Graph Reasoning 研究 (06-23) 识别了 `reasoning_path()` 的需求, 但缺少一个关键组件: **推理过程中的 gap detection**。当前设计是 "给定种子节点, 返回推理路径"。有了 gap tracker, 可以变成 "给定查询, 迭代推理直到 evidence 充分"。不需要 LLM — entity extraction + tag matching + graph connectivity 就能做 gap detection。

### 3.4 Adaptive Memory Admission 是生产化记忆系统的必要组件

**证据**: A-MAC (ICLR 2026 Workshop) 指出: 当前 agent memory 系统要么 **积累一切** (包括幻觉和过时信息), 要么用 **不透明的 LLM 决策** (昂贵且难以审计)。A-MAC 的 5-factor scoring 是可解释、可审计、可调节的。

**含义**: agent-memory-graph 已有 consolidation pipeline (semantic_divergence + retention_score + memory_evict), 但这些都是 **事后清理** — 先存入再清理。A-MAC 模式提供了 **事前准入** — 在写入时就决定是否值得存储。两者互补: admission control 把关入口, consolidation 优化存量。

**实现路径**: agent-memory-graph 已有 fingerprint (内容指纹) + 5-dim similarity toolkit + trust_level + source。添加 `should_admit()` API ~80 行: 
- N(m) novelty = embedding distance to nearest existing (已有 cosineSim)
- C(m) confidence = trust_level (已有)  
- R(m) relevance = tag overlap (已有 tag_jaccard)
- U(m) utility = content structure heuristic (code/structure → high)
- T(m) temporal = timestamp age (已有)
- 总分 → admit/reject/merge 决策

### 3.5 npm 生态零自适应检索控制器 — agent-memory-graph 可以成为首个

**证据**: 搜索 npm 找不到任何 "adaptive retrieval" / "retrieval router" / "evidence gap tracker" 库。现有的:
- LangChain.js: 有 `MultiQueryRetriever` 但无自适应路由
- LlamaIndex.TS: 有 `RouterQueryEngine` 但仅做 LLM 路由, 无 gap tracking
- Mem0: 无自适应检索
- Zep: 无自适应检索
- Letta: 无自适应检索

**含义**: agent-memory-graph 如果添加 `search_adaptive()` + `grade_retrieval()` + `search_with_gaps()` + `should_admit()` 四个 API, 可以定位为 **"npm 首个自适应检索记忆库"** — 不只是存储和检索, 而是智能地决定如何检索、检索多少、何时停止、以及什么值得记住。

---

## 4. Competitive Landscape Update (2026-06-23)

| System | Adaptive Retrieval | Gap Tracking | Admission Control | Self-Correcting | Test-Time Adapt |
|--------|-------------------|-------------|-------------------|-----------------|-----------------|
| **agent-memory-graph** (target) | ✅ (planned) | ✅ (planned) | ✅ (planned) | ✅ (planned) | ✅ (planned) |
| AdaMEM | ✅ (step-wise) | ❌ | ❌ | ❌ | ✅ (core) |
| MemR³ | ✅ (closed-loop) | ✅ (core) | ❌ | ✅ (reflect) | ❌ |
| A-MAC | ❌ | ❌ | ✅ (core) | ❌ | ❌ |
| CRAG | ❌ | ❌ | ❌ | ✅ (grade) | ❌ |
| Self-RAG | ❌ | ❌ | ❌ | ✅ (tokens) | ❌ |
| Adaptive-RAG | ✅ (router) | ❌ | ❌ | ❌ | ❌ |
| Dynamic Cheatsheet | ❌ | ❌ | ❌ | ❌ | ✅ (core) |
| Mem0 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Zep | ❌ | ❌ | ❌ | ❌ | ❌ |
| Letta | ❌ | ❌ | ❌ | ❌ | ❌ |

**差异化**: 没有任何系统同时具备 5 个维度。agent-memory-graph 的 **"Adaptive Retrieval Layer"** 将是 npm 生态首个整合这 5 个方向的自适应检索记忆库。

---

## 5. Implementation Roadmap for agent-memory-graph

### Phase 1: Query Complexity Router (~60 lines + 15 tests)
```typescript
classify_query(query: string): QueryComplexity  // pattern-based, no LLM
resolve_effort(complexity: QueryComplexity): EffortLevel
// Integrate into search_hybrid({ adaptive: true })
```

### Phase 2: Retrieval Grader (~50 lines + 12 tests)  
```typescript
grade_retrieval(query: string, results: SearchResult[]): {
  graded: SearchResult[],
  verdict: 'correct' | 'incorrect' | 'ambiguous'
}
// CRAG-inspired: cosine similarity + graph connectivity scoring
```

### Phase 3: Evidence-Gap Tracker (~80 lines + 15 tests)
```typescript  
search_with_gaps(query: string, opts: { max_iterations: number }): {
  results: SearchResult[],
  gaps: string[],
  iterations: number,
  sub_queries: string[]
}
// MemR³-inspired: entity extraction + tag matching for gap detection
```

### Phase 4: Admission Control (~80 lines + 15 tests)
```typescript
should_admit(candidate: MemoryEntry, query_tags: string[]): {
  decision: 'admit' | 'reject' | 'merge',
  merge_with?: string,
  score: { utility, confidence, novelty, relevance, temporal }
}
// A-MAC-inspired: 5-factor scoring
```

### Phase 5: Strategy Memory (~50 lines + 10 tests)
```typescript
// AdaMEM-inspired: track which strategies work for which query types
get_adaptive_strategy(query: string): string  // cached strategy
record_strategy_outcome(query: string, strategy: string, success: boolean)
```

**Total: ~320 lines + 67 tests → agent-memory-graph 从 1307 → ~1374 tests**

---

## 6. Next Actions

1. **agent-memory-graph Phase 1-2**: `classify_query()` + `grade_retrieval()` ~110行+27tests — 最小可行自适应层, 直接集成到现有 search_hybrid
2. **README positioning update**: 添加 "Adaptive Retrieval Layer" 到定位 — 不只是 Graph Intelligence Layer, 而是 **Adaptive Graph Memory Intelligence Layer**
3. **agent-context-store integration**: 4-tier search pipeline 升级为 adaptive routing (已有 Search 4-tier, 添加 complexity classifier 入口)
4. **Benchmark preparation**: 用 HotpotQA-style multi-hop 问答验证 gap tracking 效果

---

## References

1. **AdaMEM** — Zhang et al., "AdaMEM: Test-Time Adaptive Memory for Language Agents", ICML 2026, arXiv:2606.05684. Code: https://github.com/yunx-z/AdaMEM
2. **MemR³** — Du et al., "MemR³: Memory Retrieval via Reflective Reasoning for LLM Agents", arXiv:2512.20237, Dec 2025
3. **A-MAC** — Zhang et al., "Adaptive Memory Admission Control For LLM Agents", ICLR 2026 Workshop MemAgent, arXiv:2603.04549
4. **Compute Allocation** — Apparaju & Gupta, "Compute Allocation for Reasoning-Intensive Retrieval Agents", ICLR 2026, arXiv:2603.14635
5. **Adaptive Query Routing** — "Adaptive Query Routing: A Tier-Based Framework for Hybrid Retrieval", arXiv:2604.14222, 2026
6. **Agent-Orchestrated Adaptive RAG** — arXiv:2606.05658, 2026
7. **CRAG** — Yan et al., "Corrective Retrieval Augmented Generation", arXiv:2401.15884, 2024
8. **Self-RAG** — Asai et al., "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection", ICLR 2024
9. **SCMRAG** — "SCMRAG: Self-Corrective Multihop Retrieval Augmented Generation", AAMAS 2025
10. **Dynamic Cheatsheet** — Suzgun et al., "Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory", arXiv:2504.07952, Apr 2025. Code: https://github.com/suzgunmirac/dynamic-cheatsheet
11. **AdaMem** — "AdaMem: Adaptive User-Centric Memory for Long-Horizon Dialogue Agents", arXiv:2603.16496, 2026
12. **Adaptive-RAG** — Jeong et al., "Adaptive-RAG: Learning to Adapt What to Retrieve for Enhanced Open-Domain QA", NAACL 2024
13. **SEAL-RAG** — Lahmy & Yozevitch, "SEAL-RAG: Loop-Adaptive RAG with On-the-Fly Entity Extraction and Fixed-k Gap Repair", ICLR 2026 (withdrawn)
14. **ICLR 2026 MemAgent Workshop** — https://iclr.cc/virtual/2026/workshop/10000792
15. **Choosing How to Remember** — "Choosing How to Remember: Adaptive Memory Structures for LLM Agents", arXiv:2602.14038, 2026

---

_Note generated by Catalyst deep-exploration-evening cron, 2026-06-23_
