# LLM驱动的Agent记忆架构：2026前沿研究与实践

> 日期: 2026-04-16
> 主题: Agent记忆系统的三层架构（Episodic/Semantic/Procedural）与实现模式
> 方法论: autoresearch — 明确指标、快速循环、积累性
> 关联项目: Agent Memory Service v0.7.0+, memory-manager skill

---

## 核心概念 (5个)

### 1. 三层记忆分类法（2026行业标准）

| 类型 | 存什么 | 类比 | 检索方式 |
|------|--------|------|---------|
| **Episodic（情景记忆）** | 具体事件、对话、操作序列 | 船的航行日志 | 时间窗口、最近N条、元数据过滤 |
| **Semantic（语义记忆）** | 事实、偏好、知识、实体关系 | 图书馆的索引卡 | 向量相似度 + 关键词 + 知识图谱遍历 |
| **Procedural（程序记忆）** | 工作流、工具使用模式、流程规则 | 骑自行车的技能 | 触发条件匹配、任务上下文关联 |

**关键洞察**: Mem0 v1.0.0 (2026年1月) 正式引入 Procedural Memory 作为第三种记忆类型。此前大多数框架只区分 Episodic 和 Semantic。程序记忆的独立性解决了"知道什么"和"知道怎么做"的分离问题。

### 2. 多层记忆框架 MLMF（Multi-Layer Memory Framework）

来源论文: *Multi-Layered Memory Architectures for LLM Agents* (2026-03)

三层分解:
- **Working Layer**: 当前会话的上下文窗口（类似人类工作记忆）
- **Episodic Layer**: 对话历史的压缩摘要，按时间线组织
- **Semantic Layer**: 从情景记忆中蒸馏出的结构化知识

检索流程:
```
User Query → Working Memory (优先)
          → Episodic Layer (时间窗口)
          → Semantic Layer (向量检索)
          → Merge + Rerank → Final Context
```

### 3. Mnemis: 双路由检索架构（Hierarchical Graph）

来源: *Mnemis: Dual-Route Retrieval on Hierarchical Graphs* (2026-02)

核心创新: Agent 上下文中只保留压缩后的"路由索引"（distilled text），原始完整文本存储在本地。需要详情时才展开。这使得长对话可以在有限 token 预算内高效管理。

```
[压缩路由索引] ← 在LLM上下文中（省token）
     ↓ 按需展开
[完整对话原文] ← 本地存储（检索时才拉取）
```

### 4. TA-Mem: 工具增强的自主记忆检索

来源: *TA-Mem: Tool-Augmented Autonomous Memory Retrieval* (2026-03)

创新点:
- **自适应分块**: 用 one-shot prompting 按"语义主题转换"切分长上下文
- **结构化提取**: 每块提取为 `{summary, keywords, entities, events}` 结构
- **工具化检索**: 把记忆检索本身作为工具调用，Agent 自主决定何时/如何检索

### 5. 混合检索管线（2026 生产级标配）

主流框架（Mem0, Zep/Graphiti, LangMem）的共同架构:

```
Query → ┌─ Semantic Search (embeddings)
        ├─ BM25 Keyword Match
        ├─ Entity Graph Traversal
        └─ Temporal Filtering
        → Merge → Rerank → Final Results
```

Mem0 v1.0 的关键增强:
- **Metadata filtering**: 按结构化元数据过滤，不再纯依赖语义相似度
- **Timestamp on update**: 支持时间回填，迁移场景下保持时序准确性
- **Actor-aware memory**: 多Agent系统中区分记忆的创建者

---

## 关键洞察 (5条)

### 洞察 1: "检索时不需要LLM推理" 是2026的重要趋势

Mem0 和 Zep/Graphiti 都在追求 query-time 无 LLM 推理。检索完全通过向量+关键词+图谱完成，只在最终合成答案时才调LLM。这大幅降低延迟和成本。

**对我们的意义**: Agent Memory Service 的检索层应该纯靠算法（向量/关键词/时间过滤），不依赖LLM。

### 洞察 2: Procedural Memory 是 Agent 自我进化的关键

LangMem 的程序记忆允许 Agent **修改自己的 system prompt**。Agent 从用户反馈中学习什么有效，更新操作规则。这是从"记忆事实"到"学习技能"的跃迁。

**对我们的意义**: v0.7.0 应该考虑在现有 core/long/short 三层之外，增加 procedural 层，存储从操作中蒸馏出的工作流规则。

### 洞察 3: 记忆冲突解决是被忽视的核心问题

当新记忆与旧记忆矛盾时怎么办？Principia Agentica 提出的 Hybrid 方案中明确需要一个 **Conflict Resolution** 步骤:
- 语义记忆的事实可以被新事实覆盖（supersedes）
- 情景记忆按时间排序，不做覆盖（append-only）
- 需要追踪记忆来源（provenance）

### 洞察 4: Embedding 不应只在写入时生成

MLMF 论文指出 "enrichment-embedding asymmetry": 存储时扩展词汇能改善关键词搜索，但会**降低** embedding 搜索质量。建议:
- 关键词索引: 存储时做词汇扩展（同义词、实体提取）
- 向量索引: 存储时只 embed 原始内容，不做扩展
- 两个索引独立维护，检索时合并

### 洞察 5: 向量化记忆服务的最小可行架构

综合 Mem0/Zep/LangMem 的共同点，一个生产级记忆服务的最小组件:

```
┌─ Ingestion ─── LLM Extractor (事实/偏好/工作流)
├─ Storage ───── Vector Store + KV Store + Time Index
├─ Retrieval ─── Hybrid (Semantic + BM25 + Temporal)
├─ Evolution ─── Decay + Boost + Conflict Resolution
└─ API ───────── add() / search() / update() / delete()
```

---

## 代码示例: 三层混合记忆系统 (可运行)

```javascript
// three-layer-memory.js — 零依赖的三层Agent记忆系统
// 运行: node three-layer-memory.js

import { createHash, randomUUID } from 'node:crypto';

// ─── 简化向量工具（生产环境用 proper embedding） ───

// 简单的 bag-of-words 向量化（仅用于演示，生产环境用 embedding API）
function tokenize(text) {
  return text.toLowerCase().replace(/[^\w\u4e00-\u9fff]/g, ' ').split(/\s+/).filter(Boolean);
}

function cosineSimilarity(a, b) {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  let dot = 0, magA = 0, magB = 0;
  for (const k of keys) {
    const va = a[k] || 0, vb = b[k] || 0;
    dot += va * vb; magA += va * va; magB += vb * vb;
  }
  return magA && magB ? dot / (Math.sqrt(magA) * Math.sqrt(magB)) : 0;
}

function toVector(text) {
  const tokens = tokenize(text);
  const vec = {};
  tokens.forEach(t => vec[t] = (vec[t] || 0) + 1);
  return vec;
}

// ─── 三层记忆引擎 ───

class ThreeLayerMemory {
  constructor() {
    // Episodic: append-only 事件时间线
    this.episodic = [];
    // Semantic: 事实知识库（带向量索引）
    this.semantic = new Map(); // id → { content, vector, metadata, updatedAt }
    // Procedural: 工作流规则
    this.procedural = new Map(); // id → { trigger, actions, confidence, usageCount }
  }

  // ── Episodic: 追加事件 ──
  addEvent(content, metadata = {}) {
    this.episodic.push({
      id: randomUUID(),
      content,
      timestamp: Date.now(),
      metadata
    });
  }

  queryEpisodic({ since, limit = 5, filter } = {}) {
    let events = this.episodic;
    if (since) events = events.filter(e => e.timestamp >= since);
    if (filter) events = events.filter(e => 
      Object.entries(filter).every(([k, v]) => e.metadata[k] === v)
    );
    return events.slice(-limit);
  }

  // ── Semantic: 添加事实 ──
  addFact(content, metadata = {}) {
    const id = randomUUID();
    const existing = [...this.semantic.values()].find(
      f => f.content === content
    );
    if (existing) {
      existing.updatedAt = Date.now();
      existing.metadata = { ...existing.metadata, ...metadata };
      return existing.id;
    }
    this.semantic.set(id, {
      id, content, vector: toVector(content),
      metadata: { ...metadata, createdAt: Date.now() },
      updatedAt: Date.now()
    });
    return id;
  }

  // 混合检索: 语义 + 关键词
  searchFacts(query, { topK = 3, tagFilter } = {}) {
    const qVec = toVector(query);
    const qTokens = new Set(tokenize(query));
    
    let results = [...this.semantic.values()];
    if (tagFilter) {
      results = results.filter(r => 
        r.metadata.tags?.some(t => tagFilter.includes(t))
      );
    }

    return results
      .map(r => {
        const semScore = cosineSimilarity(qVec, r.vector);
        const kwScore = tokenize(r.content).filter(t => qTokens.has(t)).length / 
                        Math.max(qTokens.size, 1);
        return { ...r, score: 0.7 * semScore + 0.3 * kwScore };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, topK);
  }

  // ── Procedural: 学习工作流 ──
  learnProcedure(trigger, actions, { confidence = 0.5 } = {}) {
    const existing = [...this.procedural.values()].find(
      p => p.trigger === trigger
    );
    if (existing) {
      // 强化已有程序
      existing.actions = actions;
      existing.confidence = Math.min(1.0, existing.confidence + 0.1);
      existing.usageCount++;
      return existing.id;
    }
    const id = randomUUID();
    this.procedural.set(id, {
      id, trigger, actions, confidence,
      usageCount: 1,
      learnedAt: Date.now()
    });
    return id;
  }

  matchProcedure(context) {
    const ctxVec = toVector(context);
    return [...this.procedural.values()]
      .map(p => ({
        ...p,
        matchScore: cosineSimilarity(ctxVec, toVector(p.trigger)) * p.confidence
      }))
      .filter(p => p.matchScore > 0.1)
      .sort((a, b) => b.matchScore - a.matchScore);
  }

  // ── 统一检索: 从所有层获取上下文 ──
  retrieve(query, { episodicLimit = 3, semanticLimit = 3, includeProcedural = true } = {}) {
    const context = {
      recentEvents: this.queryEpisodic({ limit: episodicLimit }),
      relevantFacts: this.searchFacts(query, { topK: semanticLimit }),
      applicableProcedures: includeProcedural ? this.matchProcedure(query) : []
    };
    return context;
  }
}

// ─── 演示 ───

const memory = new ThreeLayerMemory();

// 情景记忆: 记录事件
memory.addEvent('用户要求部署 v2.3.0 到生产环境', { session: 'deploy-001', type: 'task' });
memory.addEvent('部署成功，耗时 3 分钟', { session: 'deploy-001', type: 'result' });
memory.addEvent('用户反馈 API 响应变慢', { session: 'perf-001', type: 'complaint' });

// 语义记忆: 存储事实
memory.addFact('生产环境部署流程: build → test → staging → canary → full rollout', 
  { tags: ['deploy', 'process'] });
memory.addFact('v2.3.0 引入了新的缓存层，预期降低 40% 延迟', 
  { tags: ['version', 'performance'] });
memory.addFact('用户偏好: 部署前先在 staging 环境验证', 
  { tags: ['preference', 'deploy'] });

// 程序记忆: 学习工作流
memory.learnProcedure(
  '部署新版本到生产环境',
  ['确认版本号', '运行测试套件', '推送到 staging', '等待 10 分钟观察', '执行 canary 发布', '全量发布'],
  { confidence: 0.8 }
);
memory.learnProcedure(
  '排查性能问题',
  ['检查最近部署变更', '查看 APM 监控', '分析慢查询日志', '检查缓存命中率'],
  { confidence: 0.6 }
);

// 模拟检索
console.log('=== 查询: "部署 v2.4.0" ===');
const deployContext = memory.retrieve('部署 v2.4.0 到生产');
console.log('📋 最近事件:', deployContext.recentEvents.map(e => e.content));
console.log('📚 相关事实:', deployContext.relevantFacts.map(f => `${f.content} (score: ${f.score.toFixed(2)})`));
console.log('🔧 适用流程:', deployContext.applicableProcedures.map(p => 
  `${p.trigger} → ${p.actions.join(' → ')} (confidence: ${p.confidence})`));

console.log('\n=== 查询: "API 性能慢" ===');
const perfContext = memory.retrieve('API 响应变慢');
console.log('📋 最近事件:', perfContext.recentEvents.map(e => e.content));
console.log('📚 相关事实:', perfContext.relevantFacts.map(f => `${f.content} (score: ${f.score.toFixed(2)})`));
console.log('🔧 适用流程:', perfContext.applicableProcedures.map(p => 
  `${p.trigger} (match: ${p.matchScore.toFixed(2)})`));

console.log('\n=== 记忆统计 ===');
console.log(`Episodic: ${memory.episodic.length} events`);
console.log(`Semantic: ${memory.semantic.size} facts`);
console.log(`Procedural: ${memory.procedural.size} procedures`);
```

---

## 与现有项目关联

### Agent Memory Service (`projects/agent-memory-service/`)
- 当前版本有 core/long/short 三层 + decay/boost 机制
- **差距分析**:
  - ✅ 已有: 分层存储、权重衰减、语义去重（hash）
  - ❌ 缺少: 程序记忆层、混合检索（BM25+向量）、元数据过滤、多Agent actor区分
  - ❌ 缺少: LLM驱动的记忆提取（当前依赖外部调用）

### memory-manager skill
- 当前做压缩检测和快照，可以增强为记忆提取层
- **机会**: 将 LLM 记忆提取逻辑封装为 memory-manager 的一部分

### Hindsight 多策略检索（中优先级待办）
- 与 MLMF/Mnemis 的多层检索直接相关
- **建议**: 参考混合检索管线设计，实现 Semantic + BM25 + Temporal 三路合并

---

## 下一步行动

1. **Agent Memory Service v0.7.0**: 在现有 core/long/short 基础上增加 `procedural` 层，支持工作流规则的存储和匹配
2. **混合检索实现**: 为 `searchFacts()` 增加 BM25 关键词匹配路径，与现有向量检索合并
3. **LLM 记忆提取器**: 参考TA-Mem的自适应分块，实现一个 `extractMemories(conversation)` 函数，从对话中自动提取事实/偏好/工作流
4. **参考框架**: 深入研究 Mem0 v1.0 API 设计和 LangMem 的程序记忆实现，考虑兼容性

---

## 参考资源

| 资源 | 类型 | 链接 |
|------|------|------|
| Mem0 v1.0 State of Memory 2026 | 技术博客 | https://mem0.ai/blog/state-of-ai-agent-memory-2026 |
| MLMF: Multi-Layer Memory Framework | 论文 (2026-03) | 见 Awesome-AI-Memory repo |
| Mnemis: Dual-Route Retrieval | 论文 (2026-02) | 见 Awesome-AI-Memory repo |
| TA-Mem: Tool-Augmented Memory Retrieval | 论文 (2026-03) | 见 Awesome-AI-Memory repo |
| Awesome-AI-Memory | 论文合集 | https://github.com/IAAR-Shanghai/Awesome-AI-Memory |
| Agent Memory Paper List | 论文合集 | https://github.com/Shichun-Liu/Agent-Memory-Paper-List |
| Principia Agentica: Hybrid Memory | 技术博客 | https://principia-agentica.io/blog/2025/09/19/memory-in-agents-episodic-vs-semantic-and-the-hybrid-that-works/ |
| Best AI Agent Memory Systems 2026 | 框架对比 | https://vectorize.io/articles/best-ai-agent-memory-systems |

---

*autoresearch quality check: ✅ 包含可运行代码示例 ✅ 5条独到洞察 ✅ 与 Agent Memory Service v0.7.0+ 直接关联*
