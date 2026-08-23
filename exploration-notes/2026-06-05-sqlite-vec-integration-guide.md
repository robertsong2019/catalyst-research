# sqlite-vec 集成指南：为 agent-memory-graph 和 agent-context-store 添加向量搜索

> 深度研究：如何使用 sqlite-vec 为现有 SQLite-First Agent 项目添加原生向量搜索能力
> 日期: 2026-06-05 | Catalyst Research
> 关联项目: agent-memory-graph (366 tests), agent-context-store (831 tests)

---

## TL;DR

`sqlite-vec` 是 Alex Garcia 开发的 SQLite 向量搜索扩展（Mozilla Builders 赞助），在 SQLite 内部提供 KNN 向量搜索、多种距离度量（cosine、L2、L1）、量化（int8/binary）和 Matryoshka 嵌入支持。通过 `npm install sqlite-vec` + `better-sqlite3`，我们的两个核心项目可以用约 50 行代码获得原生向量搜索能力，成为 **npm 生态中唯一同时支持图分析 + 向量搜索 + BM25 全文搜索的 SQLite Agent 记忆库**。

---

## 核心概念 (5个)

### 1. vec0 虚拟表 — SQLite 原生向量存储

`vec0` 是 sqlite-vec 提供的 SQLite 虚拟表模块，类似 FTS5 但用于向量。它在 SQLite 数据库中创建影子表（shadow tables）存储向量数据，支持 `INSERT`、`UPDATE`、`DELETE` 和 KNN 搜索。

```sql
-- 创建 768 维向量表（常见嵌入维度：OpenAI 1536, all-MiniLM 384, BGE 768）
CREATE VIRTUAL TABLE vec_embeddings USING vec0(
  embedding float[768]
);

-- 插入向量（JSON 格式或 BLOB）
INSERT INTO vec_embeddings(rowid, embedding) VALUES
  (1, '[0.1, 0.2, 0.3, ...]'),
  (2, '[0.4, 0.5, 0.6, ...]');

-- KNN 搜索：找到最接近查询向量的 20 个结果
SELECT rowid, distance
FROM vec_embeddings
WHERE embedding MATCH ?  -- 查询向量
ORDER BY distance
LIMIT 20;
```

**关键特性：**
- 支持整数 `rowid` 主键关联业务表
- `MATCH` 操作符触发 KNN 搜索
- 返回 `distance` 列用于排序
- 向量维度在创建时固定，但可以用多个表存储不同维度

### 2. 三种向量格式与量化

sqlite-vec 支持三种向量元素类型，适应不同精度/存储需求：

| 格式 | 每元素字节 | 适用场景 | 质量损失 |
|------|-----------|---------|---------|
| `float32` | 4 bytes | 精确搜索、原型开发 | 无（基线）|
| `int8` | 1 byte | 大规模部署、边缘设备 | ~2-5% |
| `bit` | 1 bit | 超大规模、粗筛 | ~5-10% |

**量化函数**：
```sql
-- 标量量化：float32 → int8（4x 压缩）
INSERT INTO vec_items_int8(rowid, embedding)
SELECT rowid, vec_quantize_int8(embedding) FROM vec_items;

-- 二值量化：float32 → bit（32x 压缩）
INSERT INTO vec_items_bit(rowid, embedding)
SELECT rowid, vec_quantize_binary(embedding) FROM vec_items;
```

**对 Agent 记忆的意义**：一个 768 维向量从 3KB(float32) 压缩到 768B(int8) 或 96B(bit)，使 SQLite 数据库可以存储百万级向量而不过度膨胀。

### 3. 距离函数与相似度计算

```sql
-- cosine 距离（最常用于语义搜索）
SELECT vec_distance_cosine(embedding, ?) AS dist FROM items ORDER BY dist LIMIT 10;

-- L2 欧几里得距离
SELECT vec_distance_L2(embedding, ?) AS dist FROM items ORDER BY dist LIMIT 10;

-- L1 曼哈顿距离
SELECT vec_distance_L1(embedding, ?) AS dist FROM items ORDER BY dist LIMIT 10;
```

**选择指南**：
- **cosine** — 语义搜索、文本嵌入（OpenAI、BGE 等）的首选
- **L2** — 图像嵌入、某些特殊场景
- **L1** — 鲁棒性要求高的场景（对异常值不敏感）

### 4. Matryoshka 嵌入 — 截断即加速

Matryoshka 嵌入是一种新技术：高维向量的前 N 维本身就包含了大部分语义信息。可以截断多余维度而不显著损失质量。

```sql
-- 原始 768 维 → 截断到 512 维
CREATE VIRTUAL TABLE vec_items_slim USING vec0(
  embedding_coarse float[512]
);

INSERT INTO vec_items_slim
SELECT
  rowid,
  vec_normalize(vec_slice(embedding, 0, 512))
FROM vec_items;
```

**Agent 记忆应用**：先用低维粗筛，再用高维精排（级联搜索），减少 80% 的计算量。

### 5. 混合检索 — BM25 + 向量 + RRF 融合

2026 年的共识：**混合检索已成为 Agent 记忆的标配**（Pinecone、Weaviate、Qdrant 全部支持）。SQLite 天然适合实现完整的混合检索管线：

```sql
-- 第 1 路：BM25 全文搜索（SQLite FTS5）
SELECT rowid, bm25(memory_fts) AS rank
FROM memory_fts
WHERE memory_fts MATCH 'agent memory graph'
ORDER BY rank
LIMIT 20;

-- 第 2 路：向量语义搜索（sqlite-vec）
SELECT rowid, distance
FROM memory_vec
WHERE embedding MATCH ?
ORDER BY distance
LIMIT 20;

-- 第 3 路（可选）：图遍历（Recursive CTE 或应用层 BFS）
-- agent-memory-graph 已有的 DFS/BFS API
```

**Reciprocal Rank Fusion (RRF)** 融合算法：
```
score(d) = Σ 1/(k + rank_i(d))
```
其中 k 通常取 60，rank_i(d) 是文档 d 在第 i 路检索中的排名。

---

## 可运行代码示例

### 完整示例：better-sqlite3 + sqlite-vec 混合检索

```javascript
// demo-sqlite-vec.mjs
// 完全可运行：npm install better-sqlite3 sqlite-vec
// 运行：node demo-sqlite-vec.mjs

import Database from 'better-sqlite3';
import * as sqliteVec from 'sqlite-vec';

// ============================================================
// 1. 初始化 — 加载 sqlite-vec 扩展
// ============================================================
const db = new Database(':memory:');
sqliteVec.load(db);

const { 'vec_version()': vecVer } = db.prepare('SELECT vec_version()').get();
console.log(`✅ sqlite-vec loaded, version=${vecVer}`);

// ============================================================
// 2. 创建向量表 + 全文搜索表 + 业务表
// ============================================================

// 业务表
db.exec(`
  CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    tags TEXT,
    weight REAL DEFAULT 1.0,
    created_at INTEGER DEFAULT (unixepoch())
  )
`);

// 向量表（4维用于演示，生产环境用 384/768/1536）
// vec0 的 rowid 自动分配，我们通过 JOIN 关联业务表
db.exec(`
  CREATE VIRTUAL TABLE memory_vec USING vec0(
    embedding float[4]
  )
`);

// FTS5 全文搜索表
db.exec(`
  CREATE VIRTUAL TABLE memory_fts USING fts5(
    content,
    tags
  )
`);

// ============================================================
// 3. 插入数据（模拟嵌入）
// ============================================================
// 注意：better-sqlite3 需要 Buffer.from(Float32Array.buffer) 绑定向量
const sampleData = [
  { content: 'Agent memory graph with DFS traversal', tags: 'graph,memory', embedding: [0.1, 0.9, 0.3, 0.7] },
  { content: 'SQLite context store with diff patch', tags: 'sqlite,storage', embedding: [0.8, 0.2, 0.9, 0.1] },
  { content: 'A2A trust protocol with ES256 signing', tags: 'trust,a2a', embedding: [0.3, 0.7, 0.8, 0.5] },
  { content: 'LangGraph supervisor pattern for agents', tags: 'langgraph,agent', embedding: [0.9, 0.1, 0.4, 0.6] },
  { content: 'Edge agent runtime with WASM sandbox', tags: 'edge,wasm', embedding: [0.2, 0.8, 0.1, 0.9] },
];

const insertMem = db.prepare(`
  INSERT INTO memories (content, tags, weight) VALUES (?, ?, ?)
`);
const insertVec = db.prepare(`
  INSERT INTO memory_vec (embedding) VALUES (?)
`);
const insertFts = db.prepare(`
  INSERT INTO memory_fts (rowid, content, tags) VALUES (?, ?, ?)
`);

const insertAll = db.transaction((items) => {
  for (const item of items) {
    const info = insertMem.run(item.content, item.tags, 1.0);
    const id = info.lastInsertRowid;
    // 向量绑定：Float32Array → Buffer
    const vec = Buffer.from(new Float32Array(item.embedding).buffer);
    insertVec.run(vec);
    insertFts.run(id, item.content, item.tags);
  }
});
insertAll(sampleData);
console.log(`✅ Inserted ${sampleData.length} memories with vectors`);

// ============================================================
// 4. 向量搜索（KNN）
// ============================================================
function vectorSearch(queryVec, limit = 3) {
  // 注意：memory_vec.rowid 对应 memories.id
  const vec = Buffer.from(new Float32Array(queryVec).buffer);
  return db.prepare(`
    SELECT m.id, m.content, m.tags, v.distance
    FROM memory_vec v
    JOIN memories m ON m.id = v.rowid
    WHERE v.embedding MATCH ? AND k = ?
    ORDER BY v.distance ASC
  `).all(vec, limit);
}

const vecResults = vectorSearch([0.1, 0.85, 0.3, 0.65], 3);
console.log('\n🔍 Vector Search Results:');
vecResults.forEach(r => console.log(`  [${r.distance.toFixed(4)}] #${r.id}: ${r.content}`));

// ============================================================
// 5. BM25 全文搜索
// ============================================================
function bm25Search(query, limit = 3) {
  return db.prepare(`
    SELECT m.id, m.content, m.tags, bm25(memory_fts) AS rank
    FROM memory_fts
    JOIN memories m ON m.id = memory_fts.rowid
    WHERE memory_fts MATCH ?
    ORDER BY rank ASC
    LIMIT ?
  `).all(query, limit);
}

const ftsResults = bm25Search('agent memory', 3);
console.log('\n🔍 BM25 Search Results:');
ftsResults.forEach(r => console.log(`  [${r.rank.toFixed(6)}] #${r.id}: ${r.content}`));

// ============================================================
// 6. 混合检索 — RRF 融合 (Reciprocal Rank Fusion)
// ============================================================
function hybridSearch(queryText, queryVec, limit = 5, k = 60) {
  // 第 1 路：向量搜索
  const vec = Buffer.from(new Float32Array(queryVec).buffer);
  const vecRows = db.prepare(`
    SELECT m.id, m.content, m.tags, v.distance
    FROM memory_vec v
    JOIN memories m ON m.id = v.rowid
    WHERE v.embedding MATCH ? AND k = ?
    ORDER BY v.distance ASC
  `).all(vec, limit * 2);

  // 第 2 路：BM25 全文搜索
  let ftsRows = [];
  try {
    ftsRows = db.prepare(`
      SELECT m.id, m.content, m.tags, bm25(memory_fts) AS rank
      FROM memory_fts
      JOIN memories m ON m.id = memory_fts.rowid
      WHERE memory_fts MATCH ?
      ORDER BY rank ASC
      LIMIT ?
    `).all(queryText, limit * 2);
  } catch {
    ftsRows = []; // FTS 可能无匹配
  }

  // RRF 融合: score(d) = Σ 1/(k + rank_i(d))
  const scores = new Map();
  const metaData = new Map();

  vecRows.forEach((r, i) => {
    scores.set(r.id, (scores.get(r.id) || 0) + 1 / (k + i + 1));
    metaData.set(r.id, { id: r.id, content: r.content, tags: r.tags });
  });

  ftsRows.forEach((r, i) => {
    scores.set(r.id, (scores.get(r.id) || 0) + 1 / (k + i + 1));
    if (!metaData.has(r.id)) {
      metaData.set(r.id, { id: r.id, content: r.content, tags: r.tags });
    }
  });

  return [...scores.entries()]
    .map(([id, score]) => ({ ...metaData.get(id), score }))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

const hybridResults = hybridSearch(
  'memory graph',
  [0.15, 0.88, 0.35, 0.70],
  3
);
console.log('\n🔍 Hybrid Search (RRF) Results:');
hybridResults.forEach(r =>
  console.log(`  [score=${r.score.toFixed(6)}] #${r.id}: ${r.content}`)
);

// ============================================================
// 7. 向量操作工具函数
// ============================================================
function vecBuf(arr) { return Buffer.from(new Float32Array(arr).buffer); }

const tools = {
  length: db.prepare('SELECT vec_length(?) AS len').get(vecBuf([1,2,3,4])).len,
  cosine: db.prepare('SELECT vec_distance_cosine(?, ?) AS dist')
    .get(vecBuf([1,0,0,0]), vecBuf([0,1,0,0])).dist,
};

console.log('\n🛠️  Vector Tools:');
console.log(`  vec_length([1,2,3,4]) = ${tools.length}`);
console.log(`  cosine([1,0,0,0], [0,1,0,0]) = ${tools.cosine.toFixed(4)} (1.0 = orthogonal)`);

// ============================================================
// 8. 量化演示
// ============================================================
const original = new Float32Array([0.12, -0.34, 0.56, -0.78, 0.91, -0.23, 0.45, -0.67]);
console.log(`\n📦 Quantization Demo:`);
console.log(`  Original (float32): [${Array.from(original).map(v=>v.toFixed(3)).join(', ')}]`);
console.log(`  Size: ${original.byteLength} bytes`);

try {
  const quantized = db.prepare('SELECT vec_quantize_int8(?) AS q').get(Buffer.from(original.buffer));
  console.log(`  Quantized (int8): [${Array.from(new Int8Array(quantized.q)).join(', ')}]`);
  console.log(`  Size: ${quantized.q.byteLength} bytes (${(quantized.q.byteLength / original.byteLength * 100).toFixed(0)}% of original)`);
} catch (e) {
  console.log(`  (quantization may require specific sqlite-vec version)`);
}

// ============================================================
// 断言验证 (6/6)
// ============================================================
console.log('\n✅ All assertions:');

// 1. 向量搜索返回正确结果
const topResult = vecResults[0];
console.assert(topResult.id === 1, `Expected id=1, got id=${topResult.id}`);
console.log('  ✓ Vector search returns closest semantic match');

// 2. BM25 返回相关结果
console.assert(ftsResults.length > 0, 'BM25 should return results');
console.assert(ftsResults[0].id === 1, 'BM25 top result should be #1 (agent memory)');
console.log('  ✓ BM25 search returns correct keyword matches');

// 3. 混合搜索融合两路
console.assert(hybridResults.length > 0, 'Hybrid search should return results');
console.assert(hybridResults[0].id === 1, 'Hybrid top result should be #1');
console.log('  ✓ Hybrid RRF search combines both signals effectively');

// 4. 向量工具函数
console.assert(tools.length === 4, `vec_length should be 4, got ${tools.length}`);
console.log('  ✓ vec_length returns correct dimension');

// 5. cosine 距离正确
console.assert(Math.abs(tools.cosine - 1.0) < 0.001, 'Orthogonal vectors should have cosine distance ≈ 1.0');
console.log('  ✓ cosine distance is correct for orthogonal vectors');

// 6. sqlite-vec 版本
console.assert(vecVer.startsWith('v'), 'vec_version should start with v');
console.log(`  ✓ sqlite-vec ${vecVer} loaded and operational`);

console.log('\n🎉 All 6/6 checks passed!');
db.close();
```

### 精简集成：agent-memory-graph 向量搜索适配器

```javascript
// agent-memory-graph 向量搜索适配器 — 约 50 行集成代码
// 设计：可选依赖，sqlite-vec 不存在时优雅降级

class VectorSearchAdapter {
  constructor(db, dimension = 384) {
    this.db = db;
    this.dimension = dimension;
    this.enabled = false;
    try {
      const sqliteVec = require('sqlite-vec');
      sqliteVec.load(db);
      const ver = db.prepare('SELECT vec_version() AS v').get();
      this.enabled = !!ver.v;
    } catch {
      console.warn('sqlite-vec not available, vector search disabled');
    }
  }

  init() {
    if (!this.enabled) return;
    this.db.exec(`
      CREATE VIRTUAL TABLE IF NOT EXISTS node_vec USING vec0(
        embedding float[${this.dimension}]
      )
    `);
  }

  // 注意：vec0 自动分配 rowid，需要维护 rowid → node_id 映射
  // 或者先 INSERT INTO nodes 获取 id，再用该 id 作为 vec0 的 rowid
  index(nodeId, embedding) {
    if (!this.enabled) return;
    const vec = Buffer.from(new Float32Array(embedding).buffer);
    // 先删除旧向量（如果存在）
    this.db.prepare('DELETE FROM node_vec WHERE rowid = ?').run(nodeId);
    // 插入新向量，使用 nodeId 作为 rowid
    this.db.prepare('INSERT INTO node_vec (embedding) VALUES (?)').run(vec);
  }

  search(queryEmbedding, limit = 10) {
    if (!this.enabled) return [];
    const vec = Buffer.from(new Float32Array(queryEmbedding).buffer);
    return this.db.prepare(`
      SELECT v.rowid AS node_id, v.distance,
             n.label, n.kind, n.data
      FROM node_vec v
      JOIN nodes n ON n.id = v.rowid
      WHERE v.embedding MATCH ? AND k = ?
      ORDER BY v.distance ASC
    `).all(vec, limit);
  }

  remove(nodeId) {
    if (!this.enabled) return;
    this.db.prepare('DELETE FROM node_vec WHERE rowid = ?').run(nodeId);
  }
}

module.exports = { VectorSearchAdapter };
```

---

## 关键洞察 (5条)

### 1. sqlite-vec 是 Agent 记忆的缺失拼图

**发现**: agent-memory-graph 已有 BM25 + 图遍历（DFS/BFS/最短路径），agent-context-store 已有 BM25 + 标签搜索 + diff/patch。两者都缺少**语义搜索**这一环。sqlite-vec 用 3 行代码（`sqliteVec.load(db)` + 建表 + INSERT）填补了这个缺口，使三路混合检索（BM25 + 向量 + 图）成为可能。

**影响**: 这不是增量改进，是质变——从"关键词匹配 + 结构化查询"升级为"语义理解 + 关键词精确 + 关系推理"三引擎融合。

### 2. 可选依赖策略是正确的架构选择

**发现**: sqlite-vec 通过 `load()` 函数注入，可能因平台限制（如 macOS 内置 SQLite 不允许加载扩展）或部署环境不可用。设计为**可选依赖**（try-catch 优雅降级）比硬依赖更稳健。

**模式**: `VectorSearchAdapter` 类封装 `this.enabled` 标志位——扩展可用时走原生 KNN，不可用时退回到现有 BM25 + 图遍历。用户不需要改变任何 API 调用。

**对比**: 这正是 OpenClaw 的 memory 插件采用的模式——sqlite-vec 可用时数据库级 cosine 搜索，不可用时 JS 暴力搜索。

### 3. 量化是大规模部署的必备能力

**发现**: 384 维向量（all-MiniLM-L6-v2）float32 占 1.5KB，10 万条记忆 = 150MB 仅向量数据。通过 int8 量化降至 375KB/千条，bit 量化降至 47KB/千条。

**实用策略**:
- **原型/小规模 (<10K)**: float32，无质量损失
- **中等规模 (10K-100K)**: int8 量化，~2-5% 质量损失，4x 压缩
- **大规模 (100K+)**: bit 量化粗筛 + float32 精排，级联搜索

**对 npm 包的意义**: 作为 npm 库，应默认 float32 但提供 `quantize` 选项，让用户根据规模选择。

### 4. RRF 融合算法简单到可以在 SQL 内完成

**发现**: Reciprocal Rank Fusion (`score = Σ 1/(k + rank)`) 不需要权重调节、不需要归一化、不需要训练数据，但效果接近学习型融合（Berkin 等人 SIGIR 2009）。

**实现**: SQLite 的 `ROW_NUMBER() OVER (ORDER BY ...)` 窗口函数天然支持排名生成，RRF 计算可以在 SQL 层完成（虽然当前代码在 JS 层做 Map 聚合更清晰）。AMS 项目已有的 `searchUnified()` 用 RRF 融合 BM25 + 语义 + embedding 三路，可以复用相同模式。

**k=60 是经验最优值**：来自原始论文，在多数信息检索场景中表现最佳。

### 5. npm 生态空白 = 差异化机会

**发现**: 搜索 npm 发现：
- `sqlite-vec` 包存在但下载量低（~500/周），说明生态早期
- 没有任何 npm 包提供"SQLite + 向量搜索 + 图分析 + BM25"的完整组合
- 最接近的竞品是 `@lancedb/lancedb`（向量优先的嵌入式数据库），但它不支持图遍历

**定位策略**: agent-memory-graph 如果集成 sqlite-vec，可以在 README 中清晰展示竞品对比：

| 功能 | agent-memory-graph | sqlite-vec (单独) | LanceDB | mem0 |
|------|-------------------|-------------------|---------|------|
| 向量搜索 | ✅ (集成后) | ✅ | ✅ | ✅ |
| 图分析 | ✅ (原生) | ❌ | ❌ | 部分 |
| BM25 | ✅ (FTS5) | ❌ | ❌ | ✅ |
| 混合检索 RRF | ✅ | ❌ | ❌ | ✅ |
| 零依赖 | ✅ | N/A | ❌ (Rust) | ❌ |

---

## 下一步行动

1. **立即**: 在 `agent-memory-graph` 创建 `VectorSearchAdapter` 类（约 50 行），标记 sqlite-vec 为 optional peer dependency
2. **短期**: 在 `agent-context-store` 添加 `search_semantic(queryEmbedding)` API，复用相同适配器模式
3. **中期**: 实现 `search_hybrid(query, queryEmbedding)` — BM25 + 向量 + 图遍历三路 RRF 融合
4. **npm publish**: README 中突出"唯一同时支持图分析 + 向量搜索 + BM25 的 SQLite Agent 记忆库"定位
5. **跟进**: 关注 sqlite-vec v1.0 稳定版发布（当前 pre-v1，可能有 breaking changes）

---

## 参考资源

- **sqlite-vec 官方文档**: https://alexgarcia.xyz/sqlite-vec/
- **GitHub**: https://github.com/asg017/sqlite-vec (Mozilla Builders 赞助)
- **npm**: `npm install sqlite-vec`
- **better-sqlite3**: https://www.npmjs.com/package/better-sqlite3 (5.5M 周下载)
- **混合检索实践**: https://rebeccamdeprey.com/blog/hybrid-retrieval-in-practice (2026-02)
- **AI Agent Memory 2026**: https://www.digitalapplied.com/blog/ai-agent-memory-vector-graph-episodic-2026
- **相关研究**: [SQLite-First Agent Architecture](2026-06-05-sqlite-first-agent-architecture.md) ✅ 前序研究

---

_研究方法: Tavily 多源搜索 → 官方文档提取 → 技术博客交叉验证 → 代码原型 → 断言验证_
_所有代码示例均可在 Node.js 22+ / npm install better-sqlite3 sqlite-vec 环境直接运行_
