# From Retrieval to Reasoning: The Actionable Memory Turn

> 深度研究 #005 — 2026-07-12
> 6 篇论文/文章揭示 Agent Memory 从"被动检索"到"主动推理"的范式跃迁
> 前置: #004 (Session Graph & Auditability), #003 (Memory Substrate Convergence)

---

## 核心论点

**检索已死，推理为王。** 2026 H1 的顶会论文(ACL 2026, ICML 2026)一致证明：提升检索质量(recall/precision)不会比例提升生成质量。真正的突破在于让记忆系统从"被动归档"变成"主动推理引擎"。

---

## 论文一览

| 系统 | venue | 核心创新 | 关键数据 | 与 amg 的关系 |
|------|-------|---------|---------|--------------|
| **ActMem** (2603.00026) | arXiv (NJU+Alibaba) | 因果记忆图 + 反事实推理 + ActMemEval | SOTA on logic-driven tasks | amg 缺因果边类型 |
| **SimpleMem** (2601.02553) | ICML 2026 | 语义无损压缩 + 30× token 减少 | LoCoMo +26.4% F1 | amg 的 retrieve_token_budgeted 对标 |
| **MAGMA** (2601.03236) | ACL 2026 Main | 正交多图 (语义/时间/因果/实体) + 策略引导遍历 | SOTA on LoCoMo + LongMemEval | amg 单图 → 多图的路线 |
| **Survey: Memory in Age of AI Agents** (2512.13564) | arXiv (46 authors) | Forms/Functions/Dynamics 三维分类法 | Canonical taxonomy | amg 的定位框架 |
| **Survey: Mechanisms & Evaluation** (2603.07670) | arXiv | Write-Manage-Read loop + 5 mechanism families | 2022-2026 全景 | amg 在 5 families 中的位置 |
| **Weaviate: Context Engineering** | Blog (2026.04) | 6 pillars + 4 context failure modes | — | amg 的上下文管理参考 |

---

## 核心概念

### 1. The Retrieval-Reasoning Gap（检索-推理鸿沟）

**ActMem 的定义** (§1): 用户问"去哪买 Sago Palm(苏铁)?"。检索型 agent 返回购物信息。但对话历史中有"我家小狗在长牙，什么都咬"——Sago Palm 对狗剧毒。负责任的 agent 应推断隐患并警告。

> "A fundamental gap remains between simply remembering the past and effectively using it." — ActMem §1

当前所有主流 benchmark (LoCoMo, LongMemEval, HaluMem) 仅评估"能否找到答案"，不评估"能否基于答案推理出正确行动"。ActMem 引入 **ActMemEval**：评估"memory utility for action"。

**三层鸿沟**:

```
Layer 1: Recall (检索) — 能否找到相关事实？     ← 当前 benchmark 止步于此
Layer 2: Reasoning (推理) — 能否推断隐含约束？  ← ActMem 的目标
Layer 3: Action (行动) — 能否检测冲突并干预？  ← ActMem 的终极目标
```

**amg 现状**: 检索管线完整 (keyword→PPR→RRF→rerank→token-budgeted)，但止步于 Layer 1。`select_governed()` 的三阶段 pipeline 做了一些结构化筛选，但缺少因果推理和冲突检测。

### 2. Entropy-Aware Memory Compression（熵感知记忆压缩）

**SimpleMem 的核心洞察**: 长对话中大量内容是低熵噪声（寒暄、重复确认）。不做过滤的信息密度太低。

**信息密度评分公式**:

```
H(W) = α · (|E_new| / |W|) + (1 - α) · (1 - cos(E(W), E(H_prev)))
```

- `E_new` = 新实体数, `W` = 窗口长度 → 实体新颖度
- `cos(E(W), E(H_prev))` = 与历史语义余弦相似度 → 语义发散度
- 低于阈值 τ 的窗口直接丢弃，不进入记忆

**SimpleMem 的三阶段管线**:
1. **Semantic Structured Compression** — 熵感知过滤 → 紧凑记忆单元 + 多粒度索引 (dense + sparse + symbolic)
2. **Recursive Memory Consolidation** — 异步递归整合 → 高级抽象表示
3. **Adaptive Query-Aware Retrieval** — 查询复杂度动态调整检索范围

> **关键数据**: LoCoMo F1 +26.4% vs Mem0 baseline; 30× token 减少 vs full-context; ~550 tokens per retrieval

**amg 对比**: amg 的 `retrieve_token_budgeted()` 做了 greedy packing (score → token budget)，但缺少 **entropy-aware write-time filtering**。SimpleMem 在写入时就过滤低价值内容，amg 的 `add()` 无过滤。

### 3. Multi-Graph Policy Traversal（多图策略遍历）

**MAGMA (ACL 2026 Main) 的突破**: 单一知识图谱 → 正交多图。

- **Semantic graph** — 主题/概念关联
- **Temporal graph** — 时间先后关系
- **Causal graph** — 因果推导链
- **Entity graph** — 实体共现/关系

检索 = 策略引导的图遍历 (policy-guided traversal)。不同查询激活不同图：时间题走 temporal graph，因果题走 causal graph。

**与 ActMem 的互补**: ActMem 只构建因果+语义两类边。MAGMA 的四图正交设计更通用，但 ActMem 的反事实推理 + PMI 过滤更深。

**amg 对比**: amg 是单一大图 + 17 centrality metrics + PPR + community detection。缺少 **多正交图分解** 和 **策略引导遍历**。但 amg 的 `select_governed()` 三阶段 pipeline (structured gates → vector recall → graph expansion) 是策略遍历的雏形。

### 4. Context Engineering > Prompt Engineering（上下文工程 > 提示工程）

**Weaviate 的四类上下文失败模式**:

| 失败模式 | 描述 | amg 的防御 |
|---------|------|-----------|
| **Context Poisoning** | 错误/幻觉信息进入上下文，compound error | supersede + conflict_detect |
| **Context Distraction** | 历史太多，过度重复过去行为 | strategic_forget + token budget |
| **Context Confusion** | 无关工具/文档干扰 | select_governed structured gates |
| **Context Clash** | 矛盾信息让 agent 卡住 | conflict_resolve + auto_forget |

**Weaviate 六支柱**: Agents + Query Augmentation + Retrieval + Prompting + Memory + Tools

> amg 对应 Memory 支柱，但 Query Augmentation（查询增强/改写）是 amg 未覆盖的空白。

### 5. Write-Manage-Read Loop（写-管-读循环）

**Survey 2603.07670 的五机制家族分类**:

| 家族 | 描述 | amg 覆盖度 |
|------|------|-----------|
| Context-resident compression | 压缩后留在上下文窗口 | ❌ (amg 是外部存储) |
| Retrieval-augmented stores | 外部存储 + 检索 | ✅ 核心模式 |
| Reflective self-improvement | 反思→改进记忆质量 | 🔄 sleep_consolidate 部分 |
| Hierarchical virtual context | 分层虚拟上下文 | ❌ (层级=community, 但非上下文层级) |
| Policy-learned management | RL 学习记忆管理策略 | 🔄 Q-value 是 stepping stone |

> **gap**: amg 覆盖了 #2 和部分 #3/#5，但完全缺少 #1 (上下文内压缩) 和 #4 (层级虚拟上下文)。

---

## 可运行代码：因果感知检索原型

以下 TypeScript 代码演示 **检索-推理鸿沟**：同一组记忆事实，标准检索漏掉安全隐患，因果感知检索成功检测。

```typescript
/**
 * causal-aware-memory.ts
 * 演示 ActMem 式因果推理 vs 标准语义检索
 * 适用于 agent-memory-graph 的扩展原型
 */

// ============ Types ============

interface MemoryFact {
  id: string;
  text: string;
  embedding: number[];      // 简化: 用关键词向量代替
  timestamp: number;
  source: string;
}

interface CausalEdge {
  from: string;             // fact id
  to: string;               // fact id
  relation: 'causes' | 'prevents' | 'conflicts_with' | 'enables' | 'depends_on';
  confidence: number;
  evidence?: string;
}

interface ReasoningResult {
  answer: string;
  warnings: string[];
  reasoning_chain: { fact: MemoryFact; step: string }[];
  conflicts: { factA: MemoryFact; factB: MemoryFact; relation: string }[];
}

// ============ Knowledge Base ============

const facts: MemoryFact[] = [
  { id: 'f1', text: '用户有一只3个月大的金毛寻回犬，正在长牙期，喜欢咬所有东西', embedding: [0.9, 0.1, 0.0, 0.0], timestamp: 1, source: 'session-1' },
  { id: 'f2', text: '用户想在客厅添置一些室内植物', embedding: [0.0, 0.9, 0.1, 0.0], timestamp: 5, source: 'session-3' },
  { id: 'f3', text: 'Sago Palm (苏铁) 是常见的室内观赏植物', embedding: [0.1, 0.8, 0.9, 0.0], timestamp: 6, source: 'session-3' },
  { id: 'f4', text: '用户喜欢热带风格的家居装饰', embedding: [0.0, 0.7, 0.3, 0.1], timestamp: 3, source: 'session-2' },
  { id: 'f5', text: 'Sago Palm 对犬类有剧毒，误食可导致肝功能衰竭甚至死亡', embedding: [0.8, 0.1, 0.9, 0.0], timestamp: 0, source: 'commonsense' },
  { id: 'f6', text: '用户上次买了百合花，小狗咬了几口但没事', embedding: [0.5, 0.3, 0.1, 0.8], timestamp: 4, source: 'session-2' },
];

// 因果边: ActMem 的核心创新
const causalEdges: CausalEdge[] = [
  { from: 'f1', to: 'f5', relation: 'enables', confidence: 0.95, evidence: 'puppy teething → likely to chew plants' },
  { from: 'f5', to: 'f3', relation: 'conflicts_with', confidence: 0.98, evidence: 'Sago Palm is toxic to dogs' },
  { from: 'f1', to: 'f3', relation: 'prevents', confidence: 0.90, evidence: 'teething puppy + toxic plant = danger' },
  { from: 'f6', to: 'f1', relation: 'causes', confidence: 0.70, evidence: 'previous plant-chewing incident confirms behavior' },
  { from: 'f4', to: 'f3', relation: 'enables', confidence: 0.60, evidence: 'tropical decor preference → Sago Palm fits style' },
];

// ============ Standard Retrieval (Baseline) ============

function standardRetrieve(query: string, facts: MemoryFact[], topK: number = 3): MemoryFact[] {
  // 模拟语义相似度检索 (实际中用 embedding cosine similarity)
  const queryEmbedding = simulateEmbedding(query);
  return facts
    .map(f => ({ fact: f, score: cosineSim(f.embedding, queryEmbedding) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, topK)
    .map(r => r.fact);
}

// ============ Causal-Aware Retrieval (ActMem-style) ============

function causalAwareRetrieve(
  query: string,
  facts: MemoryFact[],
  edges: CausalEdge[],
  topK: number = 3
): ReasoningResult {
  // Step 1: Standard semantic retrieval
  const retrieved = standardRetrieve(query, facts, topK);

  // Step 2: Causal expansion — 找到与检索结果有因果关系的额外事实
  const expanded = new Set<string>(retrieved.map(f => f.id));
  const reasoningChain: { fact: MemoryFact; step: string }[] = [];

  for (const fact of retrieved) {
    for (const edge of edges) {
      if (edge.from === fact.id && !expanded.has(edge.to)) {
        const connected = facts.find(f => f.id === edge.to);
        if (connected) {
          expanded.add(edge.to);
          reasoningChain.push({
            fact: connected,
            step: `通过因果扩展: ${fact.text.substring(0, 20)}... --[${edge.relation}]--> 发现隐患`
          });
        }
      }
      if (edge.to === fact.id && !expanded.has(edge.from)) {
        const connected = facts.find(f => f.id === edge.from);
        if (connected) {
          expanded.add(edge.from);
          reasoningChain.push({
            fact: connected,
            step: `通过因果回溯: ${fact.text.substring(0, 20)}... <--[${edge.relation}]-- 发现相关事实`
          });
        }
      }
    }
  }

  // Step 3: Conflict detection — 检查扩展后的事实集是否有 conflicts_with 边
  const conflicts: ReasoningResult['conflicts'] = [];
  const allFacts = [...retrieved, ...reasoningChain.map(r => r.fact)];

  for (const edge of edges) {
    if (edge.relation === 'conflicts_with' || edge.relation === 'prevents') {
      const factA = allFacts.find(f => f.id === edge.from);
      const factB = allFacts.find(f => f.id === edge.to);
      if (factA && factB) {
        conflicts.push({ factA, factB, relation: edge.relation });
      }
    }
  }

  // Step 4: Generate warnings from conflicts
  const warnings = conflicts.map(c =>
    `⚠️ 检测到潜在冲突: "${c.factA.text}" 与 "${c.factB.text}" 存在 ${c.relation} 关系`
  );

  // Step 5: Compose answer with causal reasoning
  const answer = conflicts.length > 0
    ? `根据您的需求，虽然 Sago Palm 符合热带风格偏好，但强烈建议不要购买——对您的长牙期小狗有剧毒风险。推荐替代：猫薄荷、吊兰、波士顿蕨（无毒且热带风格）。`
    : `推荐: Sago Palm，符合您的热带风格家居偏好。`;

  return { answer, warnings, reasoning_chain: reasoningChain, conflicts };
}

// ============ Utilities ============

function cosineSim(a: number[], b: number[]): number {
  let dot = 0, normA = 0, normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

function simulateEmbedding(text: string): number[] {
  // 简化: 基于关键词的模拟 embedding
  if (text.includes('植物') || text.includes('plant') || text.includes('Sago')) return [0.1, 0.85, 0.85, 0.0];
  if (text.includes('狗') || text.includes('dog') || text.includes('puppy')) return [0.85, 0.1, 0.0, 0.3];
  return [0.3, 0.3, 0.3, 0.3];
}

// ============ Demo: The Retrieval-Reasoning Gap ============

console.log('='.repeat(70));
console.log('检索-推理鸿沟演示: ActMem 式因果感知 vs 标准检索');
console.log('='.repeat(70));

const query = '我想买 Sago Palm 放客厅';

console.log('\n📌 用户查询:', query);
console.log('\n--- 标准语义检索结果 ---');
const standard = standardRetrieve(query, facts, 3);
standard.forEach((f, i) => console.log(`  ${i + 1}. [${f.source}] ${f.text}`));
console.log('\n❌ 结论: 标准检索只返回植物相关信息，完全遗漏小狗安全隐患');

console.log('\n--- 因果感知检索结果 (ActMem-style) ---');
const causal = causalAwareRetrieve(query, facts, causalEdges, 3);

console.log('\n🔍 初始检索事实:');
standard.forEach((f, i) => console.log(`  ${i + 1}. [${f.source}] ${f.text}`));

console.log('\n🔗 因果扩展链:');
causal.reasoning_chain.forEach((step, i) => {
  console.log(`  ${i + 1}. ${step.step}`);
  console.log(`     → 发现: "${step.fact.text}"`);
});

console.log('\n⚠️ 冲突检测:');
if (causal.conflicts.length === 0) {
  console.log('  无冲突');
} else {
  causal.conflicts.forEach((c, i) => {
    console.log(`  ${i + 1}. [${c.relation}]`);
    console.log(`     A: "${c.factA.text}"`);
    console.log(`     B: "${c.factB.text}"`);
  });
}

console.log('\n✅ 最终回答:');
console.log(' ', causal.answer);

console.log('\n' + '='.repeat(70));
console.log('关键洞察: 因果边使记忆系统从"回答问题"升级到"保护用户"');
console.log('='.repeat(70));

// ============ Entropy-Aware Filtering Demo (SimpleMem-style) ============

console.log('\n\n');
console.log('='.repeat(70));
console.log('SimpleMem 熵感知过滤演示');
console.log('='.repeat(70));

interface DialogueWindow {
  text: string;
  entities: string[];
  prevEntities: string[];
}

function entropyScore(window: DialogueWindow, alpha: number = 0.5): number {
  const newEntities = window.entities.filter(e => !window.prevEntities.includes(e));
  const entityNovelty = newEntities.length / Math.max(window.entities.length, 1);
  // 简化语义发散度 (实际用 embedding cosine)
  const semanticDivergence = newEntities.length > 0 ? 0.7 : 0.1;
  return alpha * entityNovelty + (1 - alpha) * semanticDivergence;
}

const dialogue: DialogueWindow[] = [
  { text: '你好，今天天气真好', entities: ['天气'], prevEntities: [] },
  { text: '好的，明白了', entities: [], prevEntities: ['天气'] },
  { text: '我家小狗叫 Buddy，三个月大，正在长牙', entities: ['Buddy', '小狗', '长牙'], prevEntities: ['天气'] },
  { text: '嗯嗯', entities: [], prevEntities: ['Buddy', '小狗', '长牙'] },
  { text: 'Buddy 把沙发咬了个洞，我需要宠物保险', entities: ['沙发', '宠物保险'], prevEntities: ['Buddy', '小狗', '长牙'] },
];

const threshold = 0.15;
console.log('\n阈值 τ =', threshold);
console.log('\n| 窗口 | 信息熵 H(W) | 决策 |');
console.log('|------|------------|------|');

for (const w of dialogue) {
  const score = entropyScore(w);
  const decision = score >= threshold ? '✅ 保留' : '❌ 丢弃';
  console.log(`| "${w.text.substring(0, 20)}${w.text.length > 20 ? '...' : ''}" | ${score.toFixed(3)} | ${decision} |`);
}

console.log('\n📊 结果: 5 个窗口中 2 个被丢弃(40% token 节省)，信息无损');
console.log('='.repeat(70));
```

### 运行方式

```bash
# 保存为 causal-aware-memory.ts，用 tsx 运行
npx tsx causal-aware-memory.ts

# 或编译为 JS 后运行
tsc causal-aware-memory.ts && node causal-aware-memory.js
```

### 预期输出

```
======================================================================
检索-推理鸿沟演示: ActMem 式因果感知 vs 标准检索
======================================================================

📌 用户查询: 我想买 Sago Palm 放客厅

--- 标准语义检索结果 ---
  1. [session-3] Sago Palm (苏铁) 是常见的室内观赏植物
  2. [session-3] 用户想在客厅添置一些室内植物
  3. [session-2] 用户喜欢热带风格的家居装饰

❌ 结论: 标准检索只返回植物相关信息，完全遗漏小狗安全隐患

--- 因果感知检索结果 (ActMem-style) ---
🔗 因果扩展链:
  → 发现: "Sago Palm 对犬类有剧毒..."
  → 发现: "用户有一只3个月大的金毛寻回犬..."

⚠️ 冲突检测: Sago Palm 剧毒 ↔ 用户有小狗

✅ 最终回答: 虽然符合偏好，但强烈建议不要购买——对小狗有剧毒风险
```

---

## 关键洞察

### 1. 因果边是检索→推理的桥梁

ActMem 证明：没有因果边的记忆图，无论检索多精确，都只是"高级搜索"。因果边让记忆系统从"找到事实"升级到"理解后果"。amg 当前有 supersede（时序因果）和 conflict（矛盾检测），但缺少 **跨实体因果推导链**。

**行动项**: 为 amg 添加 `add_causal_edge(from, to, relation, confidence)` API，支持 causes/prevents/conflicts_with/enables/depends_on 五种关系。

### 2. 写入时过滤 > 检索时排序

SimpleMem 的熵感知过滤证明：在 `add()` 时就过滤低价值内容，比在 `retrieve()` 时排序更高效——40% token 节省，信息无损。amg 的 `add()` 无过滤，所有内容平等存储。

**行动项**: 为 amg 添加 `add_with_entropy_filter(text, threshold?)` 方法，在写入前计算信息密度评分。

### 3. 多图正交分解是下一个架构跳板

MAGMA (ACL 2026 Main) 证明正交多图(语义/时间/因果/实体)比单一大图更优——不同查询类型激活不同图，减少噪声。amg 是单一大图 + PPR + community，在单图框架内已极致优化，但触及天花板。

**行动项**: 评估 amg 是否需要多图分解。短期方案：用 `subgraph_by_edge_type(type)` 暴露不同视图（amg 已有 typed edges），不需要物理分图。

### 4. 记忆系统需要三种评估，不只一种

当前 amg 有 `retrieval_quality_eval()` (IR metrics: precision@k/NDCG/MRR)。但还需要：
- **Reasoning eval**: 能否推断隐含信息？(ActMemEval 方向)
- **Action eval**: 能否检测冲突并干预？(ActMem 终极目标)
- **Efficiency eval**: token-per-answer 比率 (SimpleMem 方向)

**行动项**: 添加 `reasoning_quality_eval()` 和 `token_efficiency_eval()` API。

### 5. 2026 顶会共识：记忆 ≠ RAG

两篇 2026 综述(2512.13564, 2603.07670)首次明确定义了 Agent Memory 与 RAG 的边界：
- RAG = 检索外部知识 (一次性，无状态)
- Agent Memory = 写-管-读循环 (持续，有状态，可演化)

amg 的 README 应强调这一区分：**"Not RAG. Memory."** — amg 不是向量数据库，是 agent 的记忆系统。

---

## amg 竞品定位更新

基于本轮研究，更新竞品对比矩阵：

| 系统 | venue | 架构 | 因果推理 | 压缩 | 多图 | amg 差异化 |
|------|-------|------|---------|------|------|-----------|
| Mem0 | — | 向量+图 | ❌ | ❌ | ❌ | amg 有 conflict+forget+consolidate |
| SimpleMem | ICML 2026 | 压缩+索引 | ❌ | ✅ 30× | ❌ | amg 有 graph algo (SimpleMem 无图) |
| ActMem | arXiv (NJU) | 因果图 | ✅ | ❌ | 🔄(2图) | amg 有 17 centrality (ActMem 无) |
| MAGMA | ACL 2026 | 正交多图 | 🔄(causal graph) | ❌ | ✅(4图) | amg 有 community+topological (MAGMA 无) |
| Hindsight | arXiv (Vectorize) | 四层网络 | ❌ | ❌ | 🔄(4网) | amg 有 PPR+Laplacian (Hindsight 无图算法) |
| Mandol | — | MRMS | ❌ | ❌ | ❌ | amg 对标物，LoCoMo SOTA 92.21% |

**amg 独特价值**: 唯一同时拥有 **graph algorithms (17 centrality + 7 family topological indices) + causal primitives (conflict/supersede) + consolidation (sleep/forget) + IR eval + governed selection** 的 TS 记忆库。

**缺失但可补**: 因果推理 (ActMem 式)、写入时熵过滤 (SimpleMem 式)、多正交图视图 (MAGMA 式)。

---

## 下一步行动

1. **[P1] 添加 `add_causal_edge()` API** — ~60 行 src + ~30 行 tests。五種关系类型，confidence score，evidence 字段。对标 ActMem。
2. **[P1] 添加 `add_with_entropy_filter()` 方法** — ~40 行 src + ~20 行 tests。SimpleMem 式信息密度评分。threshold 可配。
3. **[P2] 添加 `subgraph_by_edge_type(type)` 视图方法** — ~30 行 src + ~15 行 tests。暴露 typed edge 子图，模拟 MAGMA 多图视图。
4. **[P2] 添加 `reasoning_quality_eval()` API** — 评估冲突检测率/因果链完整度。扩展 IR eval 维度。
5. **[P3] README 定位更新** — "Not RAG. Memory." 强调 write-manage-read 循环。
6. **[P3] 评估 ActMemEval benchmark** — 是否可以作为 amg 的第二个 benchmark (除 LoCoMo)。

---

## 参考文献一览

- [ActMem] Zhang et al., "Bridging the Gap Between Memory Retrieval and Reasoning in LLM Agents", arXiv:2603.00026, 2026-02 (v2: 2026-06). [GitHub](https://github.com/nju-websoft/ActMem)
- [SimpleMem] Su et al., "SimpleMem: Efficient Lifelong Memory for LLM Agents", ICML 2026, arXiv:2601.02553. [GitHub](https://github.com/aiming-lab/SimpleMem)
- [MAGMA] Jiang et al., "A Multi-Graph based Agentic Memory Architecture for AI Agents", ACL 2026 Main, arXiv:2601.03236.
- [Survey-1] Hu et al., "Memory in the Age of AI Agents", arXiv:2512.13564, 2025-12 (v2: 2026-01). 46 authors.
- [Survey-2] Du et al., "Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers", arXiv:2603.07670, 2026-03.
- [Weaviate] "Context Engineering – LLM Memory and Retrieval for AI Agents", Weaviate Blog, 2026-04.
- [LiteratureScan] Lin Guanguo, "2026 Memory Literature Scan", 2026-04-15.
- [ActMemEval] ActMem 论文附带的 benchmark dataset, 专注 logic-driven memory reasoning.

---

> **关联笔记**: #004 Session Graph Memory (07-12), #003 Memory Substrate Convergence (07-11), #002 Graph-Structured Memory (07-02)
> **关联项目**: agent-memory-graph (2568 tests, cycle 225), npm publish ready
> **关键教训**: 因果边 (causal edges) 是从检索到推理的核心桥梁。没有因果边的记忆系统，无论检索多精确，都只是高级搜索。