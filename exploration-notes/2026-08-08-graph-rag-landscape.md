# Graph RAG 真实图景：2024-2026 从狂欢到清醒再到分化

**日期:** 2026-08-08
**主题:** Graph RAG / Knowledge Graph + LLM 检索增强生成的技术演进、成本崩溃与范式分化

---

## 核心概念

### 1. Graph RAG ≠ Microsoft GraphRAG
Graph RAG 是一个范式名称（用知识图谱增强 RAG），不是一个特定产品。Microsoft GraphRAG（2024.04）只是最知名的实现。2026 年，Graph RAG 已经分化出至少 5 个不同流派，各自解决不同问题。

### 2. 成本悬崖（Cost Cliff）
2024 年初，索引一个 5GB 法律数据集需要 $33,000 的 LLM 调用费用。到 2025 年中，LazyGraphRAG 将索引成本降到原来的 0.1%（$33）。18 个月内成本下降 1000 倍，这改变了 Graph RAG 的经济学方程式。

### 3. 时序知识图谱（Temporal Knowledge Graph）
传统知识图谱只记录"什么是真的"，时序知识图谱记录"什么时候是真的"。Graphiti（Zep 开源引擎）给每条边加了 validity window（有效期），让 Agent 能区分"昨天的真相"和"今天的真相"。

### 4. Agentic Search vs Graph RAG
Claude Code 的 Boris Cherny 在 2026.01 公开表示：早期 Claude Code 用 vector RAG，但发现 agentic search（grep + glob + 多轮搜索）效果更好。这对整个 Graph RAG 领域构成了一个 existential question：如果 Agent 自己能搜索，还需要预建图吗？

### 5. DCI（Direct Corpus Interaction）
Contextual AI 提出的范式：不构建静态图，Agent 直接通过终端工具（rg, find, sed）与原始语料交互，根据推理状态动态调整搜索策略。在 BRIGHT benchmark 上比 ColBERT-v2 和 BGE-M3 高出 12%，且无需离线索引。

---

## 关键洞察

### 洞察 1: Graph RAG 的原始架构被证明过度设计
Microsoft 原版 GraphRAG 在索引阶段就做完整实体抽取 + 关系抽取 + 社区检测（Leiden 算法）+ 社区摘要生成——全用 LLM 完成。2025-2026 的研究表明，很多场景下 GraphRAG 甚至不如 vanilla RAG。问题不在于图本身，而在于索引阶段的 LLM 噪声传播和成本浪费。

### 洞察 2: 六个清晰的赢家和输家已经浮现
**赢家：**
- **LazyGraphRAG**（批量分析/研究场景）：索引成本 = 向量 RAG 水平，延迟到查询时才做 LLM 推理
- **时序知识图谱**（Graphiti/Zep）：Agent 记忆场景的杀手锏，94.7% LoCoMo 准确率
- **HippoRAG2**（ICML 2025）：模仿海马体记忆机制，比迭代检索便宜 10-30x、快 6-13x
- **PathRAG**：用流式路径剪枝解决图噪声问题，在 6 个数据集上全面超越 GraphRAG 和 LightRAG
- **Agentic Search**（Claude Code 模式）：简单粗暴但有效
- **DCI**（Contextual AI）：零索引、Agent 直接搜索原始语料

**输家：**
- Microsoft GraphRAG 原版架构（$33K 索引成本场景）
- LangChain + Neo4j 的教程式 Graph RAG 管线（2025 年的标准建议，2026 年被推翻）
- 纯向量 RAG（在多跳推理任务上系统性落后）

### 洞察 3: 记忆冲突解决是新战场
2026.06 的 arxiv 论文（FactConsolidation benchmark）揭示：即使最强的 RAG 系统 HippoRAG2 在单跳事实合并上只有 54% 准确率。多跳版本（FC-MH）几乎所有系统都是 0-7%。知识图谱系统（GraphRAG、Cognee、Graphiti）在 7-28% 之间——架构复杂度并不能解决事实冲突，反而引入了更多 LLM 判断节点和噪声传播路径。

### 洞察 4: Mem0 从图中退回——一个重要信号
Mem0 在 v3 中移除了图存储层，改用 spaCy 做实体链接 + 向量检索。原因是他们自己的论文数据显示：图变体（Mem0g）在 LOCOMO 上只比纯向量版高 1.5 分（68.44 vs 66.88），但搜索慢 3x、token 消耗多 2x。Letta 的"文件系统即记忆"实验更是用裸文件达到了 74.0%，超过所有专用记忆系统。这说明：**图的收益取决于场景，不是普适的。**

### 洞察 5: 2026 年的正确决策树
按查询类型选架构，而不是按技术热度选：
1. **单点事实查询** → 向量 RAG + BM25 混合搜索（成本最低）
2. **多跳推理** → HippoRAG2 或 PathRAG（图的价值真实存在）
3. **全局摘要/主题分析** → LazyGraphRAG（成本可控）
4. **Agent 长期记忆** → Graphiti/Zep（时序是关键维度）
5. **代码搜索** → Agentic Search（grep + glob 够了）
6. **<100K tokens 的小语料** → 跳过 RAG，直接全塞上下文窗口

---

## 系统对比表

| 系统 | 发表 | 索引成本 | 查询成本 | 核心创新 | 最佳场景 |
|------|------|---------|---------|---------|---------|
| Microsoft GraphRAG | 2024.04 | 极高（$33K/5GB） | $0.02-0.10/query | 社区检测 + 分层摘要 | 全局主题分析（已被替代） |
| LazyGraphRAG | 2024.12 | 极低（0.1% of 原版） | 可控预算 | 延迟 LLM 推理到查询时 | 批量研究分析 |
| LightRAG | 2025.05 | 中等 | 低 | 双层检索（实体+关系） | 成本敏感型项目 |
| HippoRAG2 | ICML 2025 | 极低（3.2M tokens） | 低 | 海马体模拟 + Personalized PageRank | 多跳 QA |
| PathRAG | 2025.02 | 中等 | 低 | 流式路径剪枝 | 噪声多的图数据 |
| Graphiti/Zep | 2025.01 | N/A | N/A | 双时序模型（valid + transaction time） | Agent 记忆 |
| DCI | 2026 | 零（无索引） | Agent 自主控制 | 直接语料交互 | 不确定查询模式 |
| Agentic Search | 2026 | 零（无索引） | Agent 自主控制 | grep/glob + 多轮 | 代码/文档搜索 |

---

## 关键论文/系统清单

1. **Microsoft GraphRAG** (Edge et al., 2024) — 原始架构，社区检测 + 分层摘要
2. **LazyGraphRAG** (Microsoft, 2024.12) — 成本崩溃的关键论文
3. **HippoRAG / HippoRAG2** (Gutiérrez et al., NeurIPS 2024 / ICML 2025) — 海马体记忆模拟
4. **LightRAG** (Guo et al., 2025) — 轻量级图 RAG，成本大幅降低
5. **PathRAG** (2025.02) — 流式路径剪枝，解决图噪声
6. **Graphiti/Zep** (Rasmussen et al., 2025.01) — 时序知识图谱
7. **TG-RAG** (arxiv 2510.13590) — 时序敏感的 Graph RAG
8. **FactConsolidation Benchmark** (arxiv 2606.01435) — 记忆冲突解决基准
9. **Awesome-GraphRAG** (DEEP-PolyU, GitHub) — 最全的 Graph RAG 论文列表
10. **Mem0 Paper** (arxiv 2504.19413) — 图 vs 向量的实证对比
11. **DCI / Contextual AI** (2026) — 无索引 Agent 搜索范式
12. **Agentic GraphRAG** (Neo4j NODES 2026) — Agent 自主构建图 + 自适应检索
13. **LinearRAG** (ICLR 2026) — 无关系抽取的轻量图 RAG
14. **HyperGraphRAG** (Luo et al., 2025) — 超图捕获高阶关系

---

## 可落地的 Next Actions

1. **如果你在构建 Agent 记忆系统：** 优先评估 Graphiti（时序维度是刚需）。先用 Letta 的"文件系统"方案做 baseline，再判断图带来的增量是否值得复杂度。
2. **如果你在构建企业 QA 系统：** 从 LazyGraphRAG 开始，而不是原版 GraphRAG。索引成本可控，查询质量在全局问题上不输原版。
3. **如果你在构建代码搜索/文档搜索：** 先试 Agentic Search（grep + glob + LLM 多轮），不要预设需要图。Claude Code 的实践证明这够了。
4. **如果你在评估现有 RAG 系统：** 加入 FactConsolidation benchmark 作为评估维度。纯准确率不够，你需要知道系统在事实冲突时的行为。
5. **如果你是研究者：** 多跳事实合并（FC-MH）是一个几乎空白的领域——最强系统也只有 7%。这里有巨大的研究空间。

---

## 博文信息
- **标题：** Graph RAG 的真实图景：$33,000 到 $33 的 18 个月，谁赢了谁死了
- **保存路径：** `posts/graph-rag-landscape-2026-08.html`
