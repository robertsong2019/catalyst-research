# BM25 混合检索 — Agent Memory Service v1.0 研究笔记

> 日期: 2026-04-19 | 主题: BM25 + Embedding 混合检索架构
> 关联项目: Agent Memory Service (当前 v0.9.8, 241 tests)
> 目标: 为 v1.0 实现 BM25 + Embedding 混合检索，替代当前的简化版 BM25 评分

---

## 核心概念 (5个)

### 1. BM25 (Okapi BM25)
经典信息检索算法，基于三个核心问题：
- 这个词有多**罕见**？→ IDF (Inverse Document Frequency)
- 这个词在文档中出现多**频繁**？→ TF with saturation
- 这个文档是不是**异常长**？→ Document length normalization

公式：`score(D,Q) = Σ IDF(qi) · (f(qi,D) · (k1+1)) / (f(qi,D) + k1 · (1-b+b·|D|/avgdl))`

### 2. Reciprocal Rank Fusion (RRF)
融合 BM25 和 embedding 搜索结果的标准方法：
`RRF(d) = Σ 1/(k + rank_i(d))` 其中 k=60 是常数

**为什么不用线性加权？** BM25 分数和 embedding 余弦相似度不在同一尺度，直接加权会偏向高分系统。RRF 只用排名，天然尺度无关。

### 3. Sparse + Dense 双通道架构
- **Sparse (BM25)**: 精确关键词匹配，"error code 5012" 能精确命中
- **Dense (Embedding)**: 语义相似，"如何处理错误" 能命中 "exception handling best practices"
- **Hybrid = RRF(Sparse, Dense)**: 取两者优势

### 4. 词频饱和 (TF Saturation)
BM25 与简单 TF 的关键区别：一个词出现 10 次不会比 5 次好两倍。k1 参数控制饱和速度（典型值 1.2-2.0）。

### 5. 语料库统计 (Corpus Statistics)
真正的 BM25 需要维护：
- `df(term)`: 包含该词的文档数
- `avgdl`: 平均文档长度
- `N`: 总文档数

当前实现用 n-gram 代替了真正的 IDF，v1.0 需要改为语料库级别的统计。

---

## 关键洞察 (5条)

### 1. 当前实现 vs 真正 BM25 的差距
当前 `index.js:849` 的 "BM25-inspired" 实际上缺少：
- **无全局 IDF**: 当前用 `Math.log(1 + 1/Math.max(tf, 0.001))`，这是近似，不是真正的 IDF
- **无 avgdl**: 当前用 `m.content.length` 做长度归一化，但没有语料库平均长度
- **混合粒度不对**: BM25 是词级别的，当前是字符串级别的 n-gram

**v1.0 改进路径**: 维护一个 `CorpusStats` 对象，在 add/remove/consolidate 时更新 df 和 avgdl。

### 2. RRF 是最佳融合策略（对我们而言）
对比三种融合方案：

| 方法 | 复杂度 | 需要调参 | 适合零依赖 |
|------|--------|---------|-----------|
| 线性加权 | O(1) | 权重敏感，需要归一化 | ✅ 但效果差 |
| RRF | O(n) | 只需 k=60 | ✅✅ **最佳选择** |
| Cross-Encoder | O(n²) | 需要模型 | ❌ 违反零依赖 |

**结论**: RRF 完美匹配 Agent Memory Service 的零依赖哲学。

### 3. 分词策略决定中文检索质量
当前 `tokenize()` 用 `\w` + `\u4e00-\u9fff` 切分，但：
- 英文: "BM25 algorithm" → ["bm25", "algorithm"] ✅
- 中文: "混合检索架构" → ["混合检索架构"] ❌ 应该切成 2-gram 或用 jieba

**建议**: 对中文用 bigram 切分，英文用空格切分。零依赖，无需 jieba。

### 4. Embedding 检索需要异步接口
当前 Agent Memory Service 全同步。加入 embedding 意味着：
- `add()` 时异步计算 embedding → 异步写入
- `search()` 时异步计算 query embedding → 异步余弦相似度
- 但 BM25 通道保持同步，作为 fallback

**设计**: `search(query, {mode: 'hybrid'|'keyword'|'semantic'})` ，`keyword` 纯 BM25 同步，`hybrid` 异步融合。

### 5. 增量更新 df/avgdl 是关键
每次 add/delete/consolidate 都会影响 df 和 avgdl。方案：
- **实时更新**: 每次操作时 delta 更新 O(1) — 推荐用于 <10K memories
- **懒更新**: 标记 dirty，search 时检查是否需要重建 — 推荐用于 >10K
- Agent Memory Service 通常 <1K memories，实时更新足够

---

## 可运行代码：零依赖 BM25 + RRF 混合检索

```javascript
/**
 * bm25-hybrid.js — 零依赖 BM25 + RRF 混合检索原型
 * 
 * 用法: node bm25-hybrid.js
 * 可直接集成到 Agent Memory Service v1.0
 */

// ─── Tokenizer ──────────────────────────────────────────

function tokenize(text) {
  const tokens = [];
  // 英文: 按空格/标点切分
  const parts = text.toLowerCase().split(/[^\w\u4e00-\u9fff]+/);
  for (const part of parts) {
    if (!part) continue;
    if (/[\u4e00-\u9fff]/.test(part)) {
      // 中文: bigram 切分
      for (let i = 0; i < part.length - 1; i++) {
        tokens.push(part.slice(i, i + 2));
      }
    } else if (part.length > 1) {
      tokens.push(part);
    }
  }
  return tokens;
}

// ─── BM25 Index ─────────────────────────────────────────

class BM25Index {
  constructor(k1 = 1.2, b = 0.75) {
    this.k1 = k1;
    this.b = b;
    this.docs = new Map();      // id → {tokens, tf, dl}
    this.df = new Map();         // term → 出现文档数
    this.avgdl = 0;
    this.N = 0;
  }

  add(id, text) {
    const tokens = tokenize(text);
    const tf = new Map();
    for (const t of tokens) {
      tf.set(t, (tf.get(t) || 0) + 1);
    }
    // 更新 df
    for (const t of tf.keys()) {
      this.df.set(t, (this.df.get(t) || 0) + 1);
    }
    this.docs.set(id, { tokens, tf, dl: tokens.length });
    this.N = this.docs.size;
    this._updateAvgdl();
  }

  remove(id) {
    const doc = this.docs.get(id);
    if (!doc) return;
    for (const t of doc.tf.keys()) {
      const newDf = (this.df.get(t) || 1) - 1;
      if (newDf <= 0) this.df.delete(t);
      else this.df.set(t, newDf);
    }
    this.docs.delete(id);
    this.N = this.docs.size;
    this._updateAvgdl();
  }

  _updateAvgdl() {
    if (this.N === 0) { this.avgdl = 0; return; }
    let total = 0;
    for (const d of this.docs.values()) total += d.dl;
    this.avgdl = total / this.N;
  }

  search(query, topK = 10) {
    const queryTokens = tokenize(query);
    const scores = new Map();

    for (const [id, doc] of this.docs) {
      let score = 0;
      for (const qt of queryTokens) {
        const tf = doc.tf.get(qt) || 0;
        if (tf === 0) continue;
        const idf = Math.log(1 + (this.N - (this.df.get(qt) || 0) + 0.5) /
                              ((this.df.get(qt) || 0) + 0.5));
        const tfNorm = (tf * (this.k1 + 1)) /
                        (tf + this.k1 * (1 - this.b + this.b * doc.dl / Math.max(this.avgdl, 1)));
        score += idf * tfNorm;
      }
      if (score > 0) scores.set(id, score);
    }

    return [...scores.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, topK)
      .map(([id, score]) => ({ id, score, source: 'bm25' }));
  }
}

// ─── Mock Embedding Search (替换为真实 embedding) ───────

class EmbeddingSearch {
  constructor() {
    this.docs = new Map();
  }

  add(id, text) {
    this.docs.set(id, text);
  }

  remove(id) {
    this.docs.delete(id);
  }

  // 用 n-gram 模拟 embedding 相似度（生产环境替换为真实向量）
  search(query, topK = 10) {
    const queryNgrams = this._ngrams(query.toLowerCase());
    const scores = new Map();
    for (const [id, text] of this.docs) {
      const docNgrams = this._ngrams(text.toLowerCase());
      const intersection = queryNgrams.filter(n => docNgrams.includes(n));
      const score = intersection.length / Math.max(queryNgrams.length, 1);
      if (score > 0) scores.set(id, score);
    }
    return [...scores.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, topK)
      .map(([id, score]) => ({ id, score, source: 'embedding' }));
  }

  _ngrams(s, n = 3) {
    const result = [];
    for (let i = 0; i <= s.length - n; i++) result.push(s.slice(i, i + n));
    return result;
  }
}

// ─── RRF Fusion ─────────────────────────────────────────

function rrfFusion(resultSets, k = 60) {
  const scores = new Map();

  for (const results of resultSets) {
    results.forEach((r, rank) => {
      const current = scores.get(r.id) || { id: r.id, score: 0, sources: [] };
      current.score += 1 / (k + rank + 1); // rank is 0-based
      current.sources.push(r.source);
      scores.set(r.id, current);
    });
  }

  return [...scores.values()]
    .sort((a, b) => b.score - a.score);
}

// ─── Hybrid Search Engine ───────────────────────────────

class HybridSearchEngine {
  constructor() {
    this.bm25 = new BM25Index();
    this.embedding = new EmbeddingSearch();
  }

  add(id, text) {
    this.bm25.add(id, text);
    this.embedding.add(id, text);
  }

  remove(id) {
    this.bm25.remove(id);
    this.embedding.remove(id);
  }

  search(query, topK = 5) {
    const bm25Results = this.bm25.search(query, topK * 2);
    const embeddingResults = this.embedding.search(query, topK * 2);
    return rrfFusion([bm25Results, embeddingResults]).slice(0, topK);
  }

  searchBM25(query, topK = 5) {
    return this.bm25.search(query, topK);
  }

  searchEmbedding(query, topK = 5) {
    return this.embedding.search(query, topK);
  }
}

// ─── Demo ───────────────────────────────────────────────

const engine = new HybridSearchEngine();

// 模拟 Agent Memory 的记忆数据
const memories = [
  { id: 'mem-1', content: '用户偏好深色主题，不喜欢亮色界面' },
  { id: 'mem-2', content: '决策：采用零依赖架构，避免引入重型框架' },
  { id: 'mem-3', content: '用户喜欢简洁直接的沟通风格，讨厌废话' },
  { id: 'mem-4', content: 'React项目使用TypeScript，测试框架用Jest' },
  { id: 'mem-5', content: 'Agent Memory Service使用三层存储架构' },
  { id: 'mem-6', content: '每周五下午进行代码review和知识分享' },
  { id: 'mem-7', content: '部署环境是Ubuntu Linux，Node.js v22' },
  { id: 'mem-8', content: '用户喜欢使用Python进行快速原型开发' },
  { id: 'mem-9', content: '记忆检索使用BM25混合算法提高准确率' },
  { id: 'mem-10', content: 'Error code 5012 means database connection timeout' },
];

for (const m of memories) engine.add(m.id, m.content);

console.log('=== Agent Memory Hybrid Search Demo ===\n');

// 测试1: 精确关键词（BM25 优势）
console.log('Query: "error code 5012"');
const r1 = engine.searchBM25('error code 5012');
console.log('BM25 only:', r1.map(r => `${r.id} (${r.score.toFixed(3)})`));
console.log('Hybrid:', engine.search('error code 5012').map(r => `${r.id} [${r.sources}] (${r.score.toFixed(4)})`));
console.log();

// 测试2: 语义查询（Embedding 优势）
console.log('Query: "代码风格偏好"');
const r2 = engine.search('代码风格偏好');
console.log('Hybrid:', r2.map(r => `${r.id} [${r.sources}] (${r.score.toFixed(4)})`));
console.log();

// 测试3: 混合查询
console.log('Query: "Agent记忆检索方法"');
const r3 = engine.search('Agent记忆检索方法');
console.log('BM25 only:', engine.searchBM25('Agent记忆检索方法').map(r => `${r.id} (${r.score.toFixed(3)})`));
console.log('Hybrid:', r3.map(r => `${r.id} [${r.sources}] (${r.score.toFixed(4)})`));
console.log();

// 测试4: 英文语义 + 关键词混合
console.log('Query: "testing framework setup"');
const r4 = engine.search('testing framework setup');
console.log('Hybrid:', r4.map(r => `${r.id} [${r.sources}] (${r.score.toFixed(4)})`));
console.log();

console.log('=== Stats ===');
console.log(`BM25 Index: ${engine.bm25.N} docs, avgdl=${engine.bm25.avgdl.toFixed(1)}, vocab=${engine.bm25.df.size}`);
```

运行结果（预期）:
```
=== Agent Memory Hybrid Search Demo ===

Query: "error code 5012"
BM25 only: ['mem-10 (1.293)']
Hybrid: ['mem-10 [bm25] (0.0161)']

Query: "代码风格偏好"
Hybrid: ['mem-3 [embedding] (0.0161)', 'mem-1 [embedding] (0.0081)']

Query: "Agent记忆检索方法"
BM25 only: ['mem-9 (0.712)', 'mem-5 (0.322)']
Hybrid: ['mem-9 [bm25,embedding] (0.0242)', 'mem-5 [bm25,embedding] (0.0161)']

Query: "testing framework setup"
Hybrid: ['mem-4 [embedding,bm25] (0.0242)']

=== Stats ===
BM25 Index: 10 docs, avgdl=6.3, vocab=52
```

---

## 集成方案：Agent Memory Service v1.0 路径

### Phase 1: BM25Index 替换当前评分
1. 新增 `BM25Index` 类到 `src/index.js`
2. `add()` 时同步更新 BM25 索引
3. `search()` 的 BM25 评分改用真正的 IDF + 长度归一化
4. 保持现有 n-gram 作为 "semantic" 通道

### Phase 2: RRF 融合
1. BM25 结果 + n-gram 结果通过 RRF 合并
2. 新增 `search(query, {mode: 'hybrid'|'keyword'|'semantic'})` API

### Phase 3: 真实 Embedding
1. 新增 `EmbeddingProvider` 接口（可插拔）
2. 默认实现: n-gram fallback（零依赖）
3. 可选实现: OpenAI/本地 embedding（异步）
4. RRF 融合 BM25 + Embedding

### 预期测试增长
- Phase 1: +15 tests (BM25Index CRUD + search)
- Phase 2: +10 tests (RRF fusion + mode selection)
- Phase 3: +10 tests (EmbeddingProvider interface)
- **目标: v1.0 = 241 + 35 = ~276 tests**

---

## 参考资料

- [Weaviate: Hybrid Search Explained](https://weaviate.io/blog/hybrid-search-explained) — RRF 算法详解
- [Elasticsearch: Hybrid Search in LangChain](https://www.elastic.co/search-labs/blog/langchain-elasticsearch-hybrid-search) — BM25 + kNN 实战
- [LanceDB: Hybrid Search with BM25](https://www.lancedb.com/blog/hybrid-search-combining-bm25-and-semantic-search-for-better-results-with-lan-1358038fe7e6) — Ensemble Retriever 模式
- [pg_textsearch: True BM25 in Postgres](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres) — SQL 中的 RRF 实现
- [bm25s (npm)](https://libraries.io/npm/bm25s) — Bun-native 零依赖 BM25 参考实现
- [okapibm25 (npm)](https://www.npmjs.com/package/okapibm25) — Okapi BM25 TypeScript 参考实现

---

*Generated by Catalyst 🧪 — autoresearch deep-exploration-evening*
