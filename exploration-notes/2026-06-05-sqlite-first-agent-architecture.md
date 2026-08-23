# SQLite-First Agent Architecture 2026

> 深度研究：为什么 SQLite 成为 AI Agent 记忆与状态管理的首选数据库
> 日期: 2026-06-05 | Catalyst Research

---

## TL;DR

2026 年中期，SQLite 已成为 AI Agent 记忆系统的事实标准嵌入式数据库。从 sqlite-vec (7.6K⭐) 到 Turso/libSQL 的边缘分布式方案，再到 Cloudflare 的 Durable Objects，所有主流 Agent 记忆方案都收敛于 SQLite。核心理念：**Agent 不需要数据库集群，Agent 需要的是一个文件**。

**与我们项目的关联**: agent-memory-graph (366 tests, 75+ APIs) 和 agent-context-store (831 tests, 290+ APIs) 的 SQLite-First 架构选择完全正确，正处于生态爆发点。

---

## 核心概念 (5个)

### 1. SQLite 作为 Agent 记忆的唯一文件

传统观点认为 AI Agent 需要专门的向量数据库 (Pinecone, Weaviate, Milvus)。2026 年的实践证明：**对于 99% 的 Agent 场景，一个 SQLite 文件就够了**。

**为什么 SQLite 赢了：**
- **零基础设施**: 不需要 Docker、不需要服务器、不需要 API key
- **可移植**: 整个记忆就是一个 `.sqlite` 文件，可以 `rsync`、可以 `git diff`
- **成熟**: 25+ 年的工程验证，部署量是全球第一数据库
- **扩展性**: sqlite-vec 添加向量搜索，FTS5 添加全文搜索，Recursive CTE 实现图遍历

**架构模式**：
```
┌─────────────────────────────────────┐
│  Agent (.md files)                  │  ← 源数据 (人类可读)
│  memory/MEMORY.md                   │
│  memory/2026-06-05.md               │
└──────────┬──────────────────────────┘
           │ chunking + hashing + embedding
┌──────────▼──────────────────────────┐
│  SQLite (derived index)             │  ← 派生索引 (机器可搜)
│  chunks - text + metadata           │
│  chunks_fts - FTS5 full-text (BM25) │
│  chunks_vec - sqlite-vec (cosine)   │
│  embedding_cache - hash → vector    │
└─────────────────────────────────────┘
```

**关键洞察**: memweave (2026年热门项目) 将这种模式称为 "Markdown 是真相源，SQLite 是派生缓存"。删除 SQLite 文件？从 Markdown 重建。这和 OpenClaw 自身的记忆架构 (`src/memory/`) 完全一致。

### 2. Hybrid Retrieval 是标配，不是可选

2026 年所有认真的 Agent 记忆系统都实现了三路混合检索：
1. **BM25 (全文)** — 精确关键词匹配，FTS5 原生支持
2. **Vector (语义)** — 余弦相似度，sqlite-vec 原生支持
3. **Entity (实体)** — 实体链接提升多跳推理

**Mem0 2026 年的架构转向**: 从外部图数据库 (Neo4j) 迁移到**内置实体链接**。`add()` 时提取实体存入平行集合，搜索时实体匹配提升最终得分。这是一个重要信号：**Agent 不需要图数据库，Agent 需要的是实体感知的检索**。

**RRF (Reciprocal Rank Fusion)** 是合并多路结果的标准方法：
```
score(d) = Σ 1/(k + rank_i(d))
```
其中 k≈60 是常数，rank_i(d) 是文档在第 i 路检索中的排名。

### 3. Per-Agent/Per-User 数据库隔离

Turso 提出的 **db-per-agent** 模式正在成为最佳实践：
- 每个 Agent 实例拥有独立的 SQLite 文件
- 无需复杂的租户隔离逻辑
- 天然支持离线/边缘部署
- 可以按需同步到云端

**对比传统方案**：
| 方案 | 共享 DB + tenant_id | db-per-agent |
|------|-------------------|-------------|
| 隔离性 | 逻辑隔离 (可能泄漏) | 物理隔离 |
| 故障爆炸半径 | 全局 | 单 Agent |
| 查询性能 | 受其他租户影响 | 独立 |
| 运维复杂度 | 低 | 中 (文件管理) |

**我们的实践**: agent-context-store 已实现 `namespaces` — 多 Agent 隔离 child stores，与 db-per-agent 理念一致。

### 4. 向量量化 (Quantization) 降维打击

sqlite-vec 和 Turso 都大力推广向量量化：
- **1-bit quantization**: 1536维 float32 (6KB) → 192字节，**32x 压缩**，精度损失 <2%
- **int8 quantization**: 4x 压缩，精度损失 <0.5%
- **TurboQuant (2/3/4-bit)**: SQLite-Vector 的 SIMD 查找表方案，直接从压缩态计算距离

**意义**: Agent 可以在消费级笔记本上运行 100K+ 向量搜索，延迟 <10ms。不需要 GPU，不需要专用硬件。

### 5. 本地优先 (Local-First) 运动与 Agent 的天然契合

2026 年 Local-First 运动与 AI Agent 的需求完美交汇：

**四个驱动力**：
1. **隐私**: Agent 处理个人数据 (邮件、日程、文件)，本地存储是合规必需
2. **延迟**: 云端往返 200-500ms vs 本地 SQLite 1-5ms
3. **成本**: 不为存储和计算分别付费
4. **离线**: Agent 需要在断网时继续工作

**代表性项目**：
- **EchoVault**: 本地编码 Agent 记忆，SQLite + FTS5 + Ollama 嵌入
- **OpenMemory MCP**: Mem0 的本地优先分支，MCP 兼容
- **SQLite-Memory**: sqliteai 的扩展，llama.cpp 本地嵌入 + 离线同步

---

## 可运行代码：SQLite-First Agent Memory (Node.js)

以下代码演示完整的 SQLite-First Agent 记忆系统，包含：
- FTS5 全文搜索 (BM25)
- sqlite-vec 向量搜索 (余弦相似度)
- RRF 混合融合
- Per-agent 隔离
- 标签过滤 + 时间衰减

### 安装依赖

```bash
npm install better-sqlite3 sqlite-vec
```

### 完整实现

```javascript
// sqlite-first-agent-memory.js
// 零配置 SQLite-First Agent Memory
// 可运行演示 — node sqlite-first-agent-memory.js

const Database = require('better-sqlite3');
const { load } = require('sqlite-vec');
const crypto = require('crypto');
const path = require('path');
const fs = require('fs');

class SqliteFirstAgentMemory {
  constructor(agentId, dbPath) {
    this.agentId = agentId;
    this.dbPath = dbPath || path.join(process.cwd(), `${agentId}.sqlite`);
    this.db = new Database(this.dbPath);

    // 加载 sqlite-vec 扩展
    load(this.db);

    this._initSchema();
  }

  _initSchema() {
    // 核心记忆表
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        tags TEXT DEFAULT '[]',        -- JSON array
        metadata TEXT DEFAULT '{}',    -- JSON object
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        access_count INTEGER DEFAULT 0,
        embedding BLOB                  -- float32 vector
      );

      -- FTS5 全文搜索 (BM25)
      CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
      USING fts5(content, content='memories', content_rowid='rowid');

      -- sqlite-vec 向量搜索
      CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec
      USING vec0(id TEXT PRIMARY KEY, embedding float[384]);

      -- 标签索引
      CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories(tags);
      CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);
    `);

    // FTS 同步触发器
    this.db.exec(`
      CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories
      BEGIN
        INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
      END;
      CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories
      BEGIN
        INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.rowid, old.content);
      END;
      CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories
      BEGIN
        INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.rowid, old.content);
        INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
      END;
    `);
  }

  // --- Mock embedding (真实场景用 Ollama / OpenAI) ---
  _mockEmbedding(text) {
    // 确定性伪向量 (384维) — 仅用于演示
    const hash = crypto.createHash('sha256').update(text).digest();
    const vec = new Float32Array(384);
    for (let i = 0; i < 384; i++) {
      vec[i] = (hash[i % 32] / 128) - 1; // -1 到 1
    }
    return Buffer.from(vec.buffer);
  }

  // --- 写入 ---
  add(content, opts = {}) {
    const id = opts.id || crypto.randomUUID();
    const now = Date.now();
    const tags = JSON.stringify(opts.tags || []);
    const metadata = JSON.stringify(opts.metadata || {});
    const embedding = opts.embedding || this._mockEmbedding(content);

    this.db.prepare(`
      INSERT INTO memories (id, content, tags, metadata, created_at, updated_at, embedding)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(id, content, tags, metadata, now, now, embedding);

    // 写入向量索引
    this.db.prepare(`
      INSERT INTO memories_vec (id, embedding) VALUES (?, ?)
    `).run(id, embedding);

    return { id, content, tags: opts.tags || [], metadata: opts.metadata || {} };
  }

  // --- BM25 全文搜索 ---
  searchBM25(query, limit = 10) {
    return this.db.prepare(`
      SELECT m.id, m.content, m.tags, m.created_at,
             bm25(memories_fts) AS score
      FROM memories_fts
      JOIN memories m ON m.rowid = memories_fts.rowid
      WHERE memories_fts MATCH ?
      ORDER BY score ASC
      LIMIT ?
    `).all(query, limit);
  }

  // --- 向量搜索 (余弦相似度) ---
  searchVector(query, limit = 10) {
    const queryVec = this._mockEmbedding(query);
    return this.db.prepare(`
      SELECT v.id, m.content, m.tags, v.distance
      FROM memories_vec v
      JOIN memories m ON m.id = v.id
      WHERE v.embedding MATCH ?
      ORDER BY v.distance ASC
      LIMIT ?
    `).all(queryVec, limit);
  }

  // --- 标签过滤 ---
  searchByTags(tags, limit = 10) {
    const conditions = tags.map(t => `m.tags LIKE ?`).join(' OR ');
    const params = tags.map(t => `%"${t}"%`);
    params.push(limit);

    return this.db.prepare(`
      SELECT m.id, m.content, m.tags, m.created_at
      FROM memories m
      WHERE ${conditions}
      ORDER BY m.created_at DESC
      LIMIT ?
    `).all(...params);
  }

  // --- RRF 混合搜索 (BM25 + Vector + Tag) ---
  searchHybrid(query, opts = {}) {
    const limit = opts.limit || 10;
    const tags = opts.tags || [];
    const k = 60; // RRF 常数
    const decayHours = opts.decayHours || 720; // 30天半衰期
    const now = Date.now();

    // 三路检索
    const bm25Results = this.searchBM25(query, limit * 2);
    const vecResults = this.searchVector(query, limit * 2);
    let tagResults = [];
    if (tags.length > 0) {
      tagResults = this.searchByTags(tags, limit * 2);
    }

    // RRF 融合
    const scores = new Map();

    bm25Results.forEach((r, i) => {
      const prev = scores.get(r.id) || { content: r.content, tags: r.tags, created_at: r.created_at, rrf: 0 };
      prev.rrf += 1 / (k + i + 1);
      scores.set(r.id, prev);
    });

    vecResults.forEach((r, i) => {
      const prev = scores.get(r.id) || { content: r.content, tags: r.tags, created_at: r.created_at, rrf: 0 };
      prev.rrf += 1 / (k + i + 1);
      scores.set(r.id, prev);
    });

    tagResults.forEach((r, i) => {
      const prev = scores.get(r.id) || { content: r.content, tags: r.tags, created_at: r.created_at, rrf: 0 };
      prev.rrf += 1 / (k + i + 1);
      scores.set(r.id, prev);
    });

    // 时间衰减
    const results = Array.from(scores.entries()).map(([id, data]) => {
      const ageHours = (now - data.created_at) / (1000 * 60 * 60);
      const timeDecay = Math.pow(0.5, ageHours / decayHours);
      return { id, ...data, finalScore: data.rrf * timeDecay };
    });

    results.sort((a, b) => b.finalScore - a.finalScore);
    return results.slice(0, limit);
  }

  // --- 批量写入 ---
  addBatch(items) {
    const tx = this.db.transaction((entries) => {
      for (const item of entries) {
        this.add(item.content, item);
      }
    });
    tx(items);
  }

  // --- 统计 ---
  stats() {
    const count = this.db.prepare('SELECT COUNT(*) as count FROM memories').get();
    const oldest = this.db.prepare('SELECT MIN(created_at) as oldest FROM memories').get();
    const tagRows = this.db.prepare('SELECT tags FROM memories').all();

    const tagCounts = {};
    tagRows.forEach(r => {
      try {
        JSON.parse(r.tags).forEach(t => {
          tagCounts[t] = (tagCounts[t] || 0) + 1;
        });
      } catch {}
    });

    return {
      total: count.count,
      oldestAge: oldest.oldest ? Math.floor((Date.now() - oldest.oldest) / (1000 * 60 * 60 * 24)) : 0,
      topTags: Object.entries(tagCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5),
    };
  }

  close() {
    this.db.close();
  }
}

// --- 演示 ---
function demo() {
  const dbPath = path.join('/tmp', 'agent-memory-demo.sqlite');
  if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath);

  const memory = new SqliteFirstAgentMemory('catalyst-demo', dbPath);

  console.log('=== SQLite-First Agent Memory Demo ===\n');

  // 批量写入
  memory.addBatch([
    { content: '用户偏好使用 TypeScript 和零依赖架构', tags: ['preference', 'coding'] },
    { content: '项目使用 pnpm 作为包管理器，不用 npm', tags: ['preference', 'tooling'] },
    { content: 'agent-memory-graph 已完成 366 tests，75+ APIs', tags: ['progress', 'agent-memory-graph'] },
    { content: 'agent-context-store 达到 831 tests，290+ APIs', tags: ['progress', 'agent-context-store'] },
    { content: 'SQLite 是全球部署量第一的数据库', tags: ['fact', 'sqlite'] },
    { content: 'sqlite-vec 提供 SIMD 加速的向量搜索', tags: ['fact', 'sqlite', 'vector'] },
    { content: '本周目标是两个项目 README + npm publish', tags: ['todo', 'priority'] },
    { content: 'diff/patch round-trip 已完成审计安全闭环', tags: ['feature', 'agent-context-store'] },
    { content: 'TrustGraph 4算法 22/22 tests 全部通过', tags: ['progress', 'trust'] },
    { content: 'autoresearch 连续 101 天零回滚率', tags: ['achievement'] },
  ]);

  console.log('写入 10 条记忆\n');

  // BM25 搜索
  console.log('--- BM25 搜索: "SQLite" ---');
  const bm25 = memory.searchBM25('SQLite');
  bm25.forEach(r => console.log(`  [${r.score.toFixed(2)}] ${r.content.slice(0, 60)}`));

  // 向量搜索
  console.log('\n--- 向量搜索: "数据库性能" ---');
  const vec = memory.searchVector('数据库性能');
  vec.forEach(r => console.log(`  [${r.distance.toFixed(3)}] ${r.content.slice(0, 60)}`));

  // 标签搜索
  console.log('\n--- 标签搜索: ["progress"] ---');
  const tagged = memory.searchByTags(['progress']);
  tagged.forEach(r => console.log(`  ${r.content.slice(0, 60)}`));

  // RRF 混合搜索
  console.log('\n--- RRF 混合搜索: "tests" + tags=["agent-context-store"] ---');
  const hybrid = memory.searchHybrid('tests', { tags: ['agent-context-store'], limit: 5 });
  hybrid.forEach(r => {
    const tags = JSON.parse(r.tags || '[]').join(', ');
    console.log(`  [${r.finalScore.toFixed(4)}] ${r.content.slice(0, 50)} {${tags}}`);
  });

  // 统计
  console.log('\n--- 记忆统计 ---');
  const stats = memory.stats();
  console.log(`  总记忆: ${stats.total}`);
  console.log(`  最老记忆: ${stats.oldestAge} 天前`);
  console.log(`  热门标签: ${stats.topTags.map(([t, c]) => `${t}(${c})`).join(', ')}`);

  // 清理
  memory.close();
  fs.unlinkSync(dbPath);
  console.log('\n✅ 演示完成，已清理');
}

// 运行
if (require.main === module) {
  demo();
}

module.exports = { SqliteFirstAgentMemory };
```

### 运行方式

```bash
cd /tmp && npm init -y && npm install better-sqlite3 sqlite-vec
node sqlite-first-agent-memory.js
```

---

## 关键洞察 (5条)

### 1. SQLite-First 不是妥协，是 Agent 时代的最佳选择

传统数据库厂商 (TiDB, PostgreSQL 系) 也在写文章分析 Agent 数据库需求，但他们的结论是"当规模上来时，你需要分布式数据库"。2026 年的实践数据反驳了这一点：**Agent 的典型记忆量是 1K-100K 条**，远未达到 SQLite 的性能瓶颈。sqlite-vec 暴力搜索在 100K 向量上 <10ms，加上 int8/1-bit 量化可扩展到百万级。**只有多租户 SaaS 才需要分布式数据库，单 Agent 用 SQLite 永远是对的。**

### 2. "文件是真相源，数据库是缓存" 成为共识

memweave、EchoVault、OpenClaw 自身的记忆系统都遵循同一架构：**Markdown 文件是持久层，SQLite 是派生索引**。这是一个重要的设计决策：
- 人类可读 → 可审计、可手动编辑
- `git diff` 友好 → 版本控制自然集成
- 删除索引可重建 → 无数据丢失风险
- 与 MEMORY.md + memory/YYYY-MM-DD.md 架构完全一致

### 3. 实体链接 > 图数据库

Mem0 从 Neo4j 外部图存储迁移到内置实体链接是一个分水岭时刻。**Agent 不需要可遍历的图结构，Agent 需要的是实体感知的检索排名**。这与 agent-memory-graph 的设计互补 — graph 用于分析和推理，实体链接用于检索增强。两者的实现复杂度差异巨大（递归 CTE vs Neo4j 查询语言）。

### 4. Agent 记忆的 "三明治" 正在标准化

2026 年 Agent 记忆的行业标准架构正在收敛：
```
L1: 本地文件 (Markdown / JSON)     ← 真相源
L2: SQLite + FTS5 + sqlite-vec     ← 检索层
L3: 可选云端同步 (Turso / Cloudflare DO)  ← 共享/备份
```

每一层都有成熟的工具链：
- L1: 任何文本编辑器
- L2: better-sqlite3 + sqlite-vec + FTS5
- L3: Turso (libSQL)、Cloudflare DO + Vectorize、SQLite-Sync

### 5. npm 生态是差异化机会

虽然 Python 生态 (memweave、EchoVault、sqlite-vec Python bindings) 活跃，**Node.js/npm 生态在 Agent 记忆领域明显不足**：
- LangChain libSQL vector store 刚刚发布 (2026 Q2)
- VoltAgent 的 LibSQLStorage 还在早期
- 没有一个成熟的 "SQLite-First Agent Memory" npm 包

**agent-memory-graph 和 agent-context-store 填补的正是这个空白**：
- 纯 Node.js / TypeScript
- 零外部依赖 (不需要 Python、不需要 Docker)
- 75+ / 290+ APIs
- 366 / 831 tests
- SQLite-First 架构

---

## 竞品分析

| 项目 | 语言 | 向量搜索 | 全文搜索 | 图遍历 | 标签系统 | npm 生态 |
|------|------|---------|---------|--------|---------|---------|
| **agent-memory-graph** (我们) | TS/Node | ❌ (可加) | ❌ (可加) | ✅ DFS/BFS | ✅ | ✅ |
| **agent-context-store** (我们) | TS/Node | ❌ (可加) | ❌ (可加) | ❌ | ✅ | ✅ |
| sqlite-vec | C/多语言 | ✅ SIMD | ❌ | ❌ | ❌ | ✅ |
| memweave | Python | ✅ | ✅ FTS5 | ❌ | ❌ | ❌ |
| EchoVault | Python | ✅ | ✅ FTS5 | ❌ | ✅ | ❌ |
| Turso libSQL | C/多语言 | ✅ DiskANN | ✅ FTS5 | ❌ | ❌ | ✅ |
| SQLite-Memory | C | ✅ | ✅ | ❌ | ❌ | ❌ |
| Mem0 | Python/JS | ✅ | ✅ | ✅ 实体链接 | ✅ | ✅ |

**我们的差异化**: 
1. **图分析** — agent-memory-graph 提供密度/聚集/模块度/推荐等图算法，其他项目均无
2. **内容操作** — agent-context-store 的 diff/patch round-trip 是独有特性
3. **Node.js 原生** — 不需要 Python 运行时

---

## 下一步行动

### 立即可执行

1. **agent-memory-graph npm publish — 增加 sqlite-vec 可选集成**
   - 在 README 中展示 "SQLite-First Agent Memory" 定位
   - 添加可选的 sqlite-vec 向量搜索支持
   - 对标: sqlite-vec (7.6K⭐)、Turso 向量搜索
   - 代码: `if (options.enableVector) { load(db); /* sqlite-vec */ }`

2. **agent-context-store npm publish — 突出 diff/patch 独特性**
   - 在 README 中对标 memweave 的 "Markdown 是真相源" 理念
   - 展示 content_diff ↔ content_patch 审计安全闭环
   - 强调 290+ API 方法的完备性

3. **统一 README 结构**
   - 竞品对比表 (类似上方)
   - "为什么选择 SQLite-First" 章节
   - 可运行的 Quick Start 示例
   - 与 OpenClaw 生态的集成路径

### 中期探索

4. **sqlite-vec 深度集成** — 为 agent-memory-graph 添加向量搜索能力
   - 混合检索: BM25 + 向量 + 图遍历 → RRF 融合
   - 1-bit/int8 量化支持
   - 这将使 agent-memory-graph 成为唯一同时支持图分析 + 向量搜索的 SQLite Agent 记忆库

5. **Turso 兼容层** — agent-context-store 的远程同步选项
   - libSQL 客户端适配 (本地 better-sqlite3 → 远程 libSQL)
   - 边缘部署故事

---

## 参考资源

- **sqlite-vec** (7.6K⭐): https://github.com/asg017/sqlite-vec — Mozilla 赞助，SIMD 加速，多语言绑定
- **Turso AI Memory Guide**: https://docs.turso.tech/guides/ai-memory — 官方 Agent 记忆模式指南
- **Mem0 State of Agent Memory 2026**: https://mem0.ai/blog/state-of-ai-agent-memory-2026 — 最全面的行业报告
- **memweave**: Towards Data Science — "零基础设施 Agent 记忆" (Markdown + SQLite)
- **EchoVault**: https://muhammadraza.me/2026/building-local-memory-for-coding-agents — 编码 Agent 本地记忆
- **SQLite-Memory**: https://github.com/sqliteai/sqlite-memory — SQLite 扩展，llama.cpp 本地嵌入
- **Cloudflare Agent Memory**: https://blog.cloudflare.com/introducing-agent-memory — SQLite DO + Vectorize
- **DuckDB AI Agent**: https://duckdblab.org/en/post/duckdb-ai-agent-brain — DuckDB 作为 Agent 数据大脑
- **SQLite-Vector**: https://github.com/sqliteai/sqlite-vector — TurboQuant 2/3/4-bit
- **Distributed SQLite 2026**: https://dev.to/dataformathub/distributed-sqlite-why-libsql-and-turso-are-the-new-standard-in-2026-58fk
- **OpenClaw RAG 架构分析**: https://www.pingcap.com/blog/local-first-rag-using-sqlite-ai-agent-memory-openclaw

---

*Research by Catalyst 🧪 | 2026-06-05 20:00 CST*
*autoresearch 连续 101 天零回滚率*
