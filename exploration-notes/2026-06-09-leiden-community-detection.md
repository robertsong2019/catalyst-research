# Leiden Community Detection 算法深度研究

> 日期: 2026-06-09 | 主题: Leiden算法 → agent-memory-graph GraphRAG 最后一块拼图
> 来源: Traag et al. "From Louvain to Leiden" (Scientific Reports, 2019)

## 核心概念 (5个)

### 1. Modularity（模块度）
衡量图划分质量的标准指标。比较社区内实际边密度 vs 随机期望：
```
Q = (1/2m) Σ[A_ij - k_i*k_j/(2m)] * δ(c_i, c_j)
```
- `A_ij`: 邻接矩阵
- `k_i`: 节点i的度
- `m`: 总边数
- `δ`: 同社区为1否则为0

### 2. 三阶段迭代架构
Leiden 在 Louvain 两阶段基础上增加 **refinement phase**：
1. **Local Moving** — 节点贪心移至最优社区（用队列只处理邻居变化的节点）
2. **Refinement** — 每个社区内部再细分，只合并"充分连接"的子社区
3. **Aggregation** — 将社区聚合为超级节点，构建新图，重复

### 3. Well-Connected Communities 保证
Louvain 的致命问题：可能产出内部断裂的社区。Leiden 通过 refinement phase 保证：
- 所有社区是**单连接的**（任意两点有路径）
- 所有子集是**局部最优分配的**

### 4. Fast Local Move（快速局部移动）
Louvain 会反复遍历所有节点（包括不可能移动的）。Leiden 维护一个队列：
- 初始：所有节点入队
- 每次出队一个节点，尝试移动
- 如果移动了，将其**邻居**入队
- 队列空时停止 → 大幅减少无效遍历

### 5. Resolution Parameter (γ)
CPM (Constant Potts Model) 替代 modularity 可避免分辨率极限：
```
H = Σ_ij [A_ij - γ * n_i*n_j] * δ(c_i, c_j)
```
γ 越大 → 更多小社区；γ 越小 → 更少大社区。

## 可运行代码：TypeScript Leiden 实现

> 约200行，可直接集成到 agent-memory-graph。支持加权无向图。

```javascript
// leiden.mjs — Leiden Community Detection (零依赖, 已验证可运行)
// 适用于 agent-memory-graph 的社区检测需求
// 验证: Karate Club 正确分为 2 社区, Node 0 和 33 在不同社区 ✅

function buildGraph(nodeCount, edges) {
  const adj = new Map();
  const degrees = new Float64Array(nodeCount);
  let totalWeight = 0;
  for (let i = 0; i < nodeCount; i++) adj.set(i, new Map());
  for (const e of edges) {
    adj.get(e.source).set(e.target, (adj.get(e.source).get(e.target) ?? 0) + e.weight);
    adj.get(e.target).set(e.source, (adj.get(e.target).get(e.source) ?? 0) + e.weight);
    degrees[e.source] += e.weight;
    degrees[e.target] += e.weight;
    totalWeight += e.weight;
  }
  return { nodeCount, adj, totalWeight: totalWeight / 2, degrees };
}

// Phase 1: Fast Local Move with oscillation guard
// 关键修复: 评估社区时先移除节点，避免 A→B→A 震荡导致无限循环
function localMovingPhase(graph, community) {
  const m = graph.totalWeight;
  if (m === 0) return false;
  const cw = new Float64Array(graph.nodeCount);
  for (let i = 0; i < graph.nodeCount; i++) cw[community[i]] += graph.degrees[i];

  // 随机顺序（Leiden 标准做法）
  const order = Array.from({length: graph.nodeCount}, (_, i) => i);
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }

  const inQ = new Uint8Array(graph.nodeCount);
  const q = [...order];
  for (const n of q) inQ[n] = 1;

  let improved = false;
  while (q.length > 0) {
    const node = q.shift();
    inQ[node] = 0;
    if (graph.degrees[node] === 0) continue;

    const cur = community[node];
    // ★ 关键: 先移除节点，再评估所有候选社区
    cw[cur] -= graph.degrees[node];

    let best = cur, bestGain = 0;
    // 留在当前社区也是候选
    let kiInCur = 0;
    for (const [nb, w] of graph.adj.get(node)) {
      if (community[nb] === cur) kiInCur += w;
    }
    bestGain = kiInCur / m - (cw[cur] * graph.degrees[node]) / (2 * m * m);

    // 邻居社区
    const seen = new Set();
    for (const [nb] of graph.adj.get(node)) {
      if (community[nb] !== cur) seen.add(community[nb]);
    }
    for (const tc of seen) {
      let kiIn = 0;
      for (const [nb, w] of graph.adj.get(node)) {
        if (community[nb] === tc) kiIn += w;
      }
      const gain = kiIn / m - (cw[tc] * graph.degrees[node]) / (2 * m * m);
      if (gain > bestGain) { bestGain = gain; best = tc; }
    }

    community[node] = best;
    cw[best] += graph.degrees[node];

    if (best !== cur) {
      improved = true;
      for (const [nb] of graph.adj.get(node)) {
        if (!inQ[nb]) { q.push(nb); inQ[nb] = 1; }
      }
    }
  }
  return improved;
}

// Phase 2: Refinement — 保证社区内部连接良好
function refinementPhase(graph, community) {
  const sub = new Int32Array(graph.nodeCount);
  for (let i = 0; i < graph.nodeCount; i++) sub[i] = i;
  const m = graph.totalWeight;
  if (m === 0) return sub;
  for (let node = 0; node < graph.nodeCount; node++) {
    const comm = community[node];
    const scw = new Map();
    let commDeg = 0;
    for (const [nb, w] of graph.adj.get(node)) {
      if (community[nb] === comm) {
        commDeg += w;
        if (sub[nb] !== sub[node]) scw.set(sub[nb], (scw.get(sub[nb]) ?? 0) + w);
      }
    }
    const threshold = (graph.degrees[node] * commDeg) / (2 * m);
    let bestSub = sub[node], bestW = threshold;
    for (const [sc, w] of scw) {
      if (w > bestW) { bestW = w; bestSub = sc; }
    }
    if (bestSub !== sub[node]) sub[node] = bestSub;
  }
  return sub;
}

// Phase 3: Aggregation
function aggregateGraph(graph, community) {
  const cm = new Map();
  let nid = 0;
  for (let i = 0; i < graph.nodeCount; i++) {
    if (!cm.has(community[i])) cm.set(community[i], nid++);
  }
  const mapping = new Int32Array(graph.nodeCount);
  for (let i = 0; i < graph.nodeCount; i++) mapping[i] = cm.get(community[i]);
  const edges = [];
  const seen = new Map();
  for (let i = 0; i < graph.nodeCount; i++) {
    for (const [j, w] of graph.adj.get(i)) {
      if (i < j) {
        const ci = mapping[i], cj = mapping[j];
        const key = Math.min(ci,cj) + '-' + Math.max(ci,cj);
        seen.set(key, (seen.get(key) ?? 0) + w);
      }
    }
  }
  for (const [key, weight] of seen) {
    const [s, t] = key.split('-').map(Number);
    edges.push({ source: s, target: t, weight });
  }
  return { graph: buildGraph(cm.size, edges), mapping };
}

// === 主函数 (含 dendrogram 回溯) ===
function leiden(nodeCount, edges, maxIter = 10) {
  let graph = buildGraph(nodeCount, edges);
  let community = new Int32Array(nodeCount);
  for (let i = 0; i < nodeCount; i++) community[i] = i;
  // dendrogram[origNode] → 聚合图节点ID = 最终社区ID
  let dendrogram = new Int32Array(nodeCount);
  for (let i = 0; i < nodeCount; i++) dendrogram[i] = i;

  for (let iter = 0; iter < maxIter; iter++) {
    const moved = localMovingPhase(graph, community);
    if (!moved && iter > 0) break;
    const refined = refinementPhase(graph, community);
    const { graph: ng, mapping } = aggregateGraph(graph, refined);
    // 通过 dendrogram 追踪原始节点 → 最终社区
    const nd = new Int32Array(nodeCount);
    for (let i = 0; i < nodeCount; i++) nd[i] = mapping[dendrogram[i]];
    dendrogram = nd;
    graph = ng;
    community = new Int32Array(graph.nodeCount);
    for (let i = 0; i < graph.nodeCount; i++) community[i] = i;
    if (graph.nodeCount <= 1) break;
  }
  const result = new Map();
  for (let i = 0; i < nodeCount; i++) result.set(i, dendrogram[i]);
  return result;
}

// === 测试: Karate Club ===
const edges = [
  [0,1],[0,2],[0,3],[0,4],[0,5],[0,6],[0,7],[0,8],[0,10],
  [0,11],[0,12],[0,13],[0,17],[0,19],[0,21],[0,23],
  [1,2],[1,3],[1,7],[1,13],[1,17],[1,19],[1,21],
  [2,3],[2,7],[2,8],[2,9],[2,13],[2,27],[2,28],[2,32],
  [3,7],[3,12],[3,13],[4,6],[4,10],[5,6],[5,10],[5,16],
  [6,16],[8,30],[8,32],[8,33],[9,33],[13,33],
  [14,32],[14,33],[15,32],[15,33],[18,32],[18,33],
  [19,33],[20,32],[20,33],[22,32],[22,33],
  [23,25],[23,27],[23,29],[23,32],[23,33],
  [24,25],[24,27],[24,31],[25,31],
  [26,29],[26,33],[27,33],[28,31],[28,33],
  [29,32],[29,33],[30,32],[30,33],[31,32],[31,33],[32,33],
].map(([s, t]) => ({ source: s, target: t, weight: 1 }));

const communities = leiden(34, edges);
const groups = new Map();
for (const [node, comm] of communities) {
  if (!groups.has(comm)) groups.set(comm, []);
  groups.get(comm).push(node);
}
console.log(`Communities: ${groups.size}`);
for (const [comm, nodes] of groups) {
  console.log(`  Community ${comm}: [${nodes.sort((a,b)=>a-b).join(', ')}]`);
}
console.log(`Node 0 (${communities.get(0)}) != Node 33 (${communities.get(33)}): ${communities.get(0) !== communities.get(33)}`);
```

**运行方式：**
```bash
node leiden.mjs  # 零依赖
```

**实际输出（已验证 ✅）：**
```
Communities: 2
  Community 0: [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 16, 17, 19, 21]
  Community 1: [8, 14, 15, 18, 20, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33]
Node 0 (0) != Node 33 (1): true
```

## 关键洞察 (5条)

### 1. Refinement Phase 是 Leiden 的灵魂
Louvain → Leiden 的关键差异就一个：在 aggregation 前加了一步 refinement。这步把每个社区内部再细分，只合并"充分连接"的部分。**代码量不大，效果巨大**。对 agent-memory-graph 来说，这意味着 GraphRAG 的社区一定是内部连通的，不会出现语义无关的节点被归到一起。

### 2. JS/TS 生态没有原生 Leiden 实现
- Python: `leidenalg`（最成熟，基于 igraph）
- R: `leiden` 包 + Seurat 内置
- C++: Memgraph, cuGraph
- **JS/TS: 空白**。`graphology-communities-louvain` 只有 Louvain
- 这意味着 agent-memory-graph 实现自己的 Leiden 是**真正的差异化**，npm 上没有竞品

### 3. Fast Local Move 对大规模图至关重要
agent-memory-graph 可能有数万节点（记忆节点）。队列机制意味着复杂度从 O(n²) 降到接近 O(n)。关键实现：**只在邻居变化时才重新评估节点**。

### 4. Leiden 可与 GraphRAG 的社区摘要完美配合
工作流：
```
Leiden 检测社区 → 每个社区生成 LLM 摘要 → 查询时先匹配社区再搜索
```
agent-memory-graph 已有 `community_summary()` 和 `search_graphrag()` 4种模式，只差 Leiden 替代现有的简单社区检测。

### 5. γ 参数可做自适应调参
不同类型的图（社交网络 vs 知识图谱 vs 记忆图）需要不同的 γ。可以设计自适应策略：
- 先用 γ=1.0 跑一轮
- 如果社区数 < 2 或社区大小差异 > 10x，调整 γ
- 目标：每个社区 50-200 节点（适合 LLM 摘要的窗口大小）

### 6. ⚡ 震荡陷阱: Fast Local Move 的关键修复
原始代码中 `modularityGain()` 在节点仍分配给当前社区时计算增益，导致 A→B→A 无限震荡（实测会卡死）。**修复方法**: 评估前先将节点从当前社区移除（`cw[cur] -= degrees[node]`），这样留在当前社区也变成一个候选。这个 bug 非常隐蔽——Louvain 的标准实现没有这个问题因为它每轮只遍历一次，但 fast local move 的队列机制放大了震荡。**结论: 实现社区检测时，先移除再评估是防止震荡的正确做法。**

## 下一步行动

1. **集成到 agent-memory-graph** — 将上述 ~200 行实现作为 `src/community/leiden.ts`，替换现有简单社区检测，运行 `npm test` 确认 811+ tests 全部通过
2. **~~添加 dendrogram 支持~~ ✅ 已完成** — 完整版代码已含 dendrogram 追踪，支持多粒度社区发现
3. **Benchmark 对比** — 在 agent-memory-graph 的测试图上对比 Leiden vs 现有方法，记录 modularity 和连通性指标到 `experiments.tsv`

## 参考文献

- Traag, V.A., Waltman, L. & van Eck, N.J. "From Louvain to Leiden: guaranteeing well-connected communities." *Scientific Reports* 9, 5233 (2019). https://www.nature.com/articles/s41598-019-41695-z
- Wikipedia: Leiden algorithm — https://en.wikipedia.org/wiki/Leiden_algorithm
- leidenalg (Python) — https://leidenalg.readthedocs.io/
- graphology-communities-louvain (JS) — https://github.com/graphology/graphology-communities-louvain
