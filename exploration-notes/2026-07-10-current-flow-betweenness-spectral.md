# Current-Flow Betweenness & Spectral Graph Methods for Agent Memory

> Date: 2026-07-10
> Context: agent-memory-graph cycle 213 已完成 `_laplacian_pseudoinverse()` 基础设施
> Goal: 为 current-flow betweenness/closeness 实现提供完整理论+代码路径
> Status: ✅ 算法验证通过（5 个标准图 brute-force 交叉验证）

---

## 1. 核心概念 (5 个)

### 1.1 Current-Flow Betweenness (Brandes & Fleischer 2005)

传统 betweenness centrality 只考虑最短路径。**Current-flow betweenness** 将图建模为电路：每条边是一个电阻，信息像电流一样沿着**所有路径**同时传播。

**定义：** 对于节点 v，注入 1A 在 s，抽取 1A 在 t，v 的 current-flow betweenness 是所有 (s,t) 对中流过 v 的电流总和。

**数学公式：**

$$c_f(v) = \sum_{s \neq v, t \neq v, s < t} \frac{1}{2} \sum_{w \in N(v)} |p^{st}[v] - p^{st}[w]|$$

其中 p^st 是电势向量，p^st[v] = L⁺[v][s] - L⁺[v][t]，L⁺ 是 Laplacian 伪逆。

**关键区别：**
- Shortest-path betweenness: 只计算最短路径上的节点
- Current-flow betweenness: 考虑所有路径，更适合信息传播建模

### 1.2 Current-Flow Closeness (= Information Centrality)

**已在 cycle 213 实现！** NetworkX 中 `current_flow_closeness_centrality` 就是 Stephenson & Zelen (1989) 的 information centrality，agent-memory-graph 中已存在。

$$C_I(v) = \frac{n}{\sum_w R(v, w)}$$

其中 R(v,w) = L⁺_{vv} + L⁺_{ww} − 2L⁺_{vw} 是 effective resistance。

### 1.3 Laplacian Pseudoinverse (L⁺)

**已在 cycle 213 实现！** 这是整个谱图方法的瑞士军刀。

$$L^+ = (L + \frac{J}{n})^{-1} - \frac{J}{n}$$

其中 J 是全 1 矩阵，n 是节点数。

**已有 API：**
- `_laplacian_pseudoinverse()` — 内部方法
- `effective_resistance(a, b)` — 两节点间等效电阻
- `information_centrality()` — 节点信息流效率
- `natural_connectivity()` — 图韧性

### 1.4 Transfer Admittance 向量

这是实现 current-flow betweenness 的关键中间量：

$$T_{vw}[j] = L^+[v][j] - L^+[w][j]$$

物理含义：当从节点 j 注入 1A 电流时，边 (v,w) 上的电势差。

**重要性质：** 对 pair (s,t)，边 (v,w) 上的电流 = T_{vw}[s] − T_{vw}[t]

### 1.5 排序绝对差求和恒等式

这是一个将 O(n²) 配对求和优化为 O(n log n) 的组合恒等式：

$$\sum_{i < j} |a_i - a_j| = \sum_{k=0}^{m-1} a_{\text{sorted}}[k] \cdot (2k - m + 1)$$

**证明：** 排序后，元素 k 作为较大值出现在 k 个配对中（与 0..k-1 配对），作为较小值出现在 (m-1-k) 个配对中。净贡献 = k − (m-1-k) = 2k − m + 1。

**复杂度影响：** current-flow betweenness 从朴素 O(n⁴d) 降至 O(n²d log n)。

---

## 2. 可运行代码：完整验证实现

以下代码包含 L⁺ 计算、快速 CF-betweenness、Brute-force 交叉验证，覆盖 5 个标准测试图。

```python
"""
Current-Flow Betweenness Centrality — Pure Python Implementation
Verified against brute-force on K3, P4, S5, C4, K4.
"""

def laplacian_pseudoinverse_simple(adj_matrix):
    """Pure Python Laplacian pseudoinverse for small graphs.
    
    Uses L⁺ = (L + J/n)⁻¹ - J/n
    via Gauss-Jordan elimination with partial pivoting.
    """
    n = len(adj_matrix)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                L[i][j] = -adj_matrix[i][j]
                L[i][i] += adj_matrix[i][j]
    jn = 1.0 / n
    M = [[L[i][j] + jn for j in range(n)] for i in range(n)]
    # Augmented matrix [M | I]
    aug = [[M[i][j] for j in range(n)] + [
        1.0 if i == j else 0.0 for j in range(n)
    ] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pv = aug[col][col]
        for j in range(2 * n):
            aug[col][j] /= pv
        for row in range(n):
            if row != col and aug[row][col] != 0:
                factor = aug[row][col]
                for j in range(2 * n):
                    aug[row][j] -= factor * aug[col][j]
    inv = [[aug[i][n + j] for j in range(n)] for i in range(n)]
    return [[inv[i][j] - jn for j in range(n)] for i in range(n)]


def current_flow_betweenness(adj_matrix):
    """Fast current-flow betweenness using sorted-identity optimization.
    
    Complexity: O(n² · d · log n) where d = average degree.
    
    Returns dict: node_index -> normalized betweenness score in [0, 1].
    """
    n = len(adj_matrix)
    if n < 3:
        return {i: 0.0 for i in range(n)}
    
    L_plus = laplacian_pseudoinverse_simple(adj_matrix)
    
    # Build neighbor lists
    neighbors = [[] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if adj_matrix[i][j] > 0:
                neighbors[i].append(j)
    
    betweenness = [0.0] * n
    
    for v in range(n):
        for w in neighbors[v]:
            if w <= v:
                continue  # process each undirected edge once
            
            # Contribution to v: T[j] = L⁺[v][j] - L⁺[w][j] for j ≠ v
            T_v = [L_plus[v][j] - L_plus[w][j]
                   for j in range(n) if j != v]
            T_v.sort()
            m = n - 1
            for k in range(m):
                betweenness[v] += T_v[k] * (2 * k - m + 1)
            
            # Contribution to w: T[j] = L⁺[w][j] - L⁺[v][j] for j ≠ w
            T_w = [L_plus[w][j] - L_plus[v][j]
                   for j in range(n) if j != w]
            T_w.sort()
            for k in range(m):
                betweenness[w] += T_w[k] * (2 * k - m + 1)
    
    # 1/2 factor from the definition:
    # c_f(v) = (1/2) Σ_w Σ_{s<t} |T[s] - T[t]|
    # No extra factor: each undirected edge visited once,
    # contributing separately to v and w.
    for v in range(n):
        betweenness[v] /= 2.0
    
    # Normalize: 2/[(n-1)(n-2)]
    norm = 2.0 / ((n - 1) * (n - 2))
    return {v: betweenness[v] * norm for v in range(n)}


def cf_betweenness_brute(adj_matrix):
    """Brute-force ground truth: iterate all pairs explicitly."""
    n = len(adj_matrix)
    if n < 3:
        return {i: 0.0 for i in range(n)}
    L_plus = laplacian_pseudoinverse_simple(adj_matrix)
    neighbors = [[] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if adj_matrix[i][j] > 0:
                neighbors[i].append(j)
    betweenness = [0.0] * n
    for s in range(n):
        for t in range(s + 1, n):
            p = [L_plus[v][s] - L_plus[v][t] for v in range(n)]
            for v in range(n):
                if v == s or v == t:
                    continue
                flow = sum(abs(p[v] - p[w]) for w in neighbors[v])
                betweenness[v] += flow / 2.0
    norm = 2.0 / ((n - 1) * (n - 2))
    return {v: betweenness[v] * norm for v in range(n)}


# === VERIFICATION SUITE ===
graphs = {
    "K3 (triangle)": [
        [0, 1, 1], [1, 0, 1], [1, 1, 0]
    ],
    "P4 (path)": [
        [0, 1, 0, 0], [1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0]
    ],
    "S5 (star)": [
        [0, 1, 1, 1, 1], [1, 0, 0, 0, 0],
        [1, 0, 0, 0, 0], [1, 0, 0, 0, 0], [1, 0, 0, 0, 0]
    ],
    "C4 (cycle)": [
        [0, 1, 0, 1], [1, 0, 1, 0], [0, 1, 0, 1], [1, 0, 1, 0]
    ],
    "K4 (complete)": [
        [0, 1, 1, 1], [1, 0, 1, 1], [1, 1, 0, 1], [1, 1, 1, 0]
    ],
}

for name, adj in graphs.items():
    brute = cf_betweenness_brute(adj)
    fast = current_flow_betweenness(adj)
    match = all(abs(brute[k] - fast[k]) < 1e-10 for k in brute)
    b_str = {k: round(v, 6) for k, v in sorted(brute.items())}
    f_str = {k: round(v, 6) for k, v in sorted(fast.items())}
    print(f"{name}:")
    print(f"  Brute: {b_str}")
    print(f"  Fast:  {f_str}")
    print(f"  ✅ Match" if match else "  ❌ MISMATCH")
    print()
```

### 验证结果

```
K3 (triangle):
  Brute: {0: 0.333333, 1: 0.333333, 2: 0.333333}
  Fast:  {0: 0.333333, 1: 0.333333, 2: 0.333333}
  ✅ Match

P4 (path):
  Brute: {0: 0.0, 1: 0.666667, 2: 0.666667, 3: 0.0}
  Fast:  {0: 0.0, 1: 0.666667, 2: 0.666667, 3: 0.0}
  ✅ Match

S5 (star):
  Brute: {0: 1.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
  Fast:  {0: 1.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
  ✅ Match

C4 (cycle):
  Brute: {0: 0.333333, 1: 0.333333, 2: 0.333333, 3: 0.333333}
  Fast:  {0: 0.333333, 1: 0.333333, 2: 0.333333, 3: 0.333333}
  ✅ Match

K4 (complete):
  Brute: {0: 0.25, 1: 0.25, 2: 0.25, 3: 0.25}
  Fast:  {0: 0.25, 1: 0.25, 2: 0.25, 3: 0.25}
  ✅ Match
```

**物理直觉验证：**
- **K₃**: 每个节点只有 1 对其他节点，电流分流到 2 条路径，flow = 1/3 ✅
- **P₄**: 树结构 = 唯一路径，端点不承担中介角色 = 0，中间节点承担所有流 ✅
- **S₅**: 所有电流必经中心节点 = 1.0，叶节点从不是中介 = 0 ✅
- **C₄**: 对称环，所有节点等价 = 1/3 ✅
- **K₄**: 完全对称，电流均匀分散 = 1/4 ✅

---

## 3. agent-memory-graph 集成方案

### 3.1 实现路径（~120 行 src）

在 `memory_graph.py` 中添加 `current_flow_betweenness_centrality()` 方法：

```python
def current_flow_betweenness_centrality(self, *, include_quarantined: bool = False
                                        ) -> dict[str, float]:
    """Current-flow (random-walk) betweenness centrality for nodes.
    
    Models information spread as electrical current through all paths,
    not just shortest paths. Equivalent to random-walk betweenness
    (Newman 2005).
    
    Uses the Laplacian pseudoinverse and sorted-absolute-difference
    identity for O(n²d log n) computation.
    
    Based on Brandes & Fleischer (2005), STACS 2005, LNCS 3404.
    """
    # 1. Get nodes, check connectivity
    # 2. Compute L⁺ via existing _laplacian_pseudoinverse()
    # 3. For each node v, for each neighbor w > v:
    #    - Compute T[j] = L⁺[v][j] - L⁺[w][j] for j ≠ v
    #    - Sort T, apply identity: Σ_k T[k] × (2k - m + 1)
    #    - Accumulate to betweenness[v] and betweenness[w]
    # 4. Divide by 2 (definition factor)
    # 5. Normalize by 2/[(n-1)(n-2)]
```

### 3.2 测试方案（~150 行 tests）

```python
class TestCurrentFlowBetweennessCentrality:
    """Tests for current_flow_betweenness_centrality()."""

    def test_empty_graph(self):
        mg = MemoryGraph(":memory:")
        assert mg.current_flow_betweenness_centrality() == {}

    def test_single_node(self):
        mg = MemoryGraph(":memory:")
        mg.add_node("a")
        result = mg.current_flow_betweenness_centrality()
        assert result == {"a": 0.0}

    def test_triangle_k3_symmetric(self):
        """K₃: all nodes equal by symmetry."""
        mg = MemoryGraph(":memory:")
        mg.add_node("a"); mg.add_node("b"); mg.add_node("c")
        mg.add_edge("a", "b"); mg.add_edge("b", "c"); mg.add_edge("a", "c")
        result = mg.current_flow_betweenness_centrality()
        assert all(abs(v - 1/3) < 1e-6 for v in result.values())

    def test_path_p4_middle_higher(self):
        """P₄: middle nodes B,C > endpoints A,D = 0."""
        mg = MemoryGraph(":memory:")
        for nid in ["a", "b", "c", "d"]:
            mg.add_node(nid)
        mg.add_edge("a", "b"); mg.add_edge("b", "c"); mg.add_edge("c", "d")
        result = mg.current_flow_betweenness_centrality()
        assert abs(result["a"]) < 1e-6  # endpoint
        assert abs(result["d"]) < 1e-6  # endpoint
        assert result["b"] > result["a"]
        assert result["c"] > result["d"]
        assert abs(result["b"] - 2/3) < 1e-6

    def test_star_center_dominant(self):
        """S₅: center = 1.0, leaves = 0."""
        mg = MemoryGraph(":memory:")
        for nid in ["center", "l1", "l2", "l3", "l4"]:
            mg.add_node(nid)
        for leaf in ["l1", "l2", "l3", "l4"]:
            mg.add_edge("center", leaf)
        result = mg.current_flow_betweenness_centrality()
        assert abs(result["center"] - 1.0) < 1e-6
        for leaf in ["l1", "l2", "l3", "l4"]:
            assert abs(result[leaf]) < 1e-6

    def test_quarantine_exclusion(self):
        """Quarantined nodes are excluded."""
        mg = MemoryGraph(":memory:")
        mg.add_node("a"); mg.add_node("b"); mg.add_node("c")
        mg.add_edge("a", "b"); mg.add_edge("b", "c")
        mg.quarantine_node("a")
        # Only b-c edge → 2 nodes → all zero
        result = mg.current_flow_betweenness_centrality()
        assert all(v == 0.0 for v in result.values())

    def test_does_not_modify_graph(self):
        """Verify no side effects."""
        mg = MemoryGraph(":memory:")
        mg.add_node("a"); mg.add_node("b"); mg.add_node("c")
        mg.add_edge("a", "b"); mg.add_edge("b", "c"); mg.add_edge("a", "c")
        edge_count_before = mg.count_edges()
        mg.current_flow_betweenness_centrality()
        assert mg.count_edges() == edge_count_before
```

---

## 4. 关键洞察 (5 条)

### 4.1 Current-Flow Betweenness ≡ Random-Walk Betweenness

Newman (2005) 证明两者数学等价。这意味着它度量的是"随机游走者经过节点的期望次数"。**对 agent memory：** PPR 检索过程类似随机游走，current-flow betweenness 直接预测了记忆节点在检索中的中介重要性。

### 4.2 排序绝对差恒等式是通用优化

朴素 O(n⁴d) 降至 O(n²d log n)。这个恒等式不仅适用于 CF-betweenness，也可用于 agent-memory-graph 中任何需要配对绝对差求和的场景（如某些 graph kernel 计算）。

### 4.3 Current-Flow Closeness 已实现（= Information Centrality）

NetworkX 中 `current_flow_closeness_centrality` = Stephenson & Zelen information centrality，**已在 cycle 213 实现为 `information_centrality()`**。CF centrality 家族中 **只需再实现 betweenness 即完成套件**。

### 4.4 Laplacian Pseudoinverse ROI 极高

一次 O(n³) 的 L⁺ 计算支撑 7+ 个指标：effective resistance ✅, information centrality ✅, natural connectivity ✅, CF-betweenness ⬜, Kirchhoff index ⬜, spectral clustering ⬜, communicability ⬜。

### 4.5 CF-Betweenness 与 PPR 检索互补

- 高 PPR + 高 CF-betweenness = **核心枢纽**（信息汇聚 + 必经之路）
- 高 PPR + 低 CF-betweenness = **信息孤岛**（自身重要但不在主路径上）
- 低 PPR + 高 CF-betweenness = **隐形桥梁**（自身不突出但是关键连接点）

这为 `graph_rerank()` 提供新的排序信号 → cycle 214 集成目标。

---

## 5. 下一步行动

### 5.1 立即：实现 current_flow_betweenness_centrality() — Cycle 214
- **代码量：** ~120 行 src + ~150 行 tests (~15-20 test cases)
- **依赖：** `_laplacian_pseudoinverse()` ✅ 已就绪
- **复杂度：** O(n²d log n)
- **验证：** K₃=1/3, P₄=2/3/0, S₅=1.0/0 (brute-force 已交叉验证)

### 5.2 近期：Edge current-flow betweenness
- 代码量 ~80 行，同一 L⁺ 基础设施
- 识别 agent memory 中的"关键边"（哪些记忆连接是信息瓶颈）

### 5.3 集成：graph_rerank() 第 6 种信号
- 当前支持: degree / eigenvector / betweenness / closeness / pagerank
- 新增: `current_flow_betweenness` → 更丰富的重排序

### 5.4 中期：Kirchhoff index
- Kirchhoff index = n × tr(L⁺) = Σ_{i<j} R(i,j) — 一行代码
- 全局图连通性度量，可用于 `health_check()` 报告

---

## 6. 参考文献

1. **Brandes & Fleischer (2005)** — "Centrality Measures Based on Current Flow", STACS 2005, LNCS 3404. 原始论文。
2. **Newman (2005)** — "A measure of betweenness centrality based on random walks", Social Networks 27:39-54. 证明 CF-betweenness ≡ random-walk betweenness.
3. **Stephenson & Zelen (1989)** — "Rethinking centrality", Social Networks 11:1-37. Information centrality 定义。
4. **NetworkX 3.6.1** — 参考实现 `current_flow_betweenness_centrality()`，使用 flow_matrix_row 迭代器。

---

## 笔记质量自评

| 维度 | 状态 | 说明 |
|------|------|------|
| 核心概念 | ✅ 5 个 | L⁺, CF-betweenness, CF-closeness, transfer admittance, 排序恒等式 |
| 可运行代码 | ✅ 完整 | L⁺ + 快速 CF-betweenness + brute-force + 5 图验证，全部通过 |
| 独到见解 | ✅ 5 条 | PPR互补、排序通用优化、已有实现复用、ROI分析、随机游走等价 |
| 下一步行动 | ✅ 4 个 | 从 immediate (cycle 214) 到中期 (Kirchhoff index) |
| 项目关联 | ✅ 强 | 直接连接 cycle 213 基础设施，为 cycle 214 铺路 |
