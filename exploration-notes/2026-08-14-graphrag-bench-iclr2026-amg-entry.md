# Research #064: GraphRAG-Bench (ICLR 2026) 参赛深研究 — amg 接入路径与验证

> Date: 2026-08-14 (Fri) 20:00 · Catalyst deep-exploration-evening
> 主题来源: HEARTBEAT.md Medium-term "amg: GraphRAG Benchmark 参赛" + MEMORY.md GraphRAG 生态定位
> 前序: Research #062 (GraphRAG 2026 全景, 一行提及 GraphRAG-Bench) · #053/#058 (bench landscape)
> 状态: **可运行适配器雏形已验证** ✅（rule-based 零 API 成本路径）

---

## 0. TL;DR

GraphRAG-Bench (ICLR 2026, 厦大 Xiang et al., arXiv 2506.05690) 是 amg 进入主流 GraphRAG 评测体系的最短路径：**数据集公开（HF）、评测代码标准化、第三方可提交 leaderboard**（FalkorDB GraphRAG-SDK 已示范完整接入并登顶 Novel 榜）。amg 的 `extract_from_text → graphrag_query → graphrag_explain` 生命周期恰好映射到 bench 的 indexing → retrieval → generation 三段评测。**本研究已用最小语料验证官方 prediction schema 的生成管线，并发现 rule-based 抽取在 Novel 域的两个真实风险**（缩写句点切分、question-type-aware 答案提取）。

## 1. 核心概念 (5)

### 1.1 两个同名的 "GraphRAG-Bench" —— 必须区分
| | **ICLR 2026 版**（本研究对象） | arXiv 2506.02404 版（Emory/Carl Yang 组） |
|---|---|---|
| 论文 | "When to use Graphs in RAG" | "Challenging Domain-Specific Reasoning" |
| 语料 | Novel 20 部小说 (2010 题) + Medical (2062 题) | 20 本 CS 教科书, 7M 词, 1018 题, 16 学科 |
| 特色 | 4 级难度递进 + 3 段式管线评测 | 专家 rationale 标注 (R Score / AR Metric) |
| 提交 | ✅ 有官方 leaderboard，HF 数据集 | 偏学术分析 |

amg 目标锁定 **ICLR 2026 版 Novel 榜**：多文档跨文档叙事推理正是 amg PPR + spreading activation 的主场。

### 1.2 四级任务难度（评测维度 × 指标）
| Level | 问题类型 | 指标 |
|---|---|---|
| 1 | Fact Retrieval | ROUGE-L + ACC |
| 2 | Complex Reasoning | ROUGE-L + ACC |
| 3 | Contextual Summarize | ACC + Coverage |
| 4 | Creative Generation | ACC + Coverage + Faithfulness |

### 1.3 ACC 公式 —— 主榜指标
```
ACC = (0.75 × factuality_F1 + 0.25 × semantic_similarity) × 100
```
- factuality_F1：judge LLM 把生成答案与 ground truth 原子化为 statements，分类 TP/FP/FN 后算 F1
- semantic_similarity：答案 vs 参考的 embedding cosine（BAAI/bge-large-en-v1.5）
- **洞察：0.75 权重在事实性而非词面** —— 检索对了但生成跑偏照样低分；反之 extractive 精准答案即使措辞不同也能拿高分。

### 1.4 三段式独立评测模块（官方 `Evaluation/` 目录）
```bash
python -m Evaluation.generation_eval  --data_file results/amg.json ...   # 生成质量
python -m Evaluation.retrieval_eval   --data_file results/amg.json ...   # Context Relevancy + Evidence Recall
python -m Evaluation.indexing_eval    --framework graphml --base_path ... # 图结构: density/connectivity/clustering
```
**retrieval_eval 和 indexing_eval 不需要生成 LLM** —— amg 可以先单独刷这两项（零生成成本），这是 FalkorDB 示例没有明说但 schema 支持的分阶段打法。

### 1.5 统一 prediction schema（所有框架统一）
```json
{"id", "question", "source", "context", "evidence", "question_type", "generated_answer", "ground_truth"}
```
评测代码跨框架标准化 —— amg 适配器只需产出这个 JSON。indexing_eval 原生支持 `graphml` 通用格式（amg 需加一个 export_graphml()，~20 行）。

## 2. Novel Leaderboard 现状（2026-08 快照）

| 排名 | 系统 | Fact | Complex | Summ | Creative | Overall |
|---|---|---|---|---|---|---|
| 1 | **FalkorDB GraphRAG-SDK** | 65.22 | 58.63 | 69.54 | 57.08 | **63.73** |
| 2 | AutoPrunedRetriever | 45.99 | 62.80 | **83.10** | 62.97 | 63.72 |
| 3 | G-Reasoner | 60.07 | 53.92 | 71.28 | 50.48 | 58.94 |
| 4 | HippoRAG2 | 60.14 | 53.38 | 64.10 | 48.28 | 56.48 |
| 5 | Fast-GraphRAG | 56.95 | 48.55 | 56.41 | 46.18 | 52.02 |
| 6 | MS-GraphRAG (local) | 49.29 | 50.93 | 64.40 | 39.10 | 50.93 |
| 7 | RAG (w/ rerank) | 60.92 | 42.93 | 51.30 | 38.26 | 48.35 |
| 8 | LightRAG | 58.62 | 49.07 | 48.85 | 23.80 | 45.09 |
| 9 | HippoRAG | 52.93 | 38.52 | 48.70 | 38.85 | 44.75 |

**读榜要点**：
- 榜首与第二只差 0.01 分 —— 但画像完全不同：FalkorDB 均衡，AutoPrunedRetriever 靠 Summarize (83.10) 单项碾压。
- vanilla RAG 在 Fact Retrieval (60.92) 不输多数 GraphRAG —— **图结构的价值集中在 Complex Reasoning（RAG 仅 42.93 vs GraphRAG 普遍 50+）**，这正是论文标题"When to use Graphs"的答案，也是 amg 应重点报告的子项。
- 榜首配方（FalkorDB）：GLiNER 本地 NER（零 API 成本）+ FastCoref 指代消解 + LLM 仅做关系抽取 + **4 层 resolution 链**（ExactMatch → DescriptionMerge → Semantic 0.85 → LLMVerified 0.95/0.60）+ MultiPath 检索（实体多路径发现 + 2-hop 扩展 + cosine rerank）。avg query latency 3.6s。

## 3. 可运行代码：amg → GraphRAG-Bench 适配器雏形 ✅

> 归档: `code/2026-08-14/run_amg_grb.py`（已验证可运行）
> 管线: corpus → `extract_from_text`(rule, 零 API) → `graphrag_query` → 官方 schema JSON

```python
import json, sys
sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
from memory_graph import MemoryGraph

# GraphRAG-Bench corpus/questions schema（迷你 fixture，真实数据从 HF 下载）
corpus = [{"corpus_name": "Novel-0001", "context": (
    "Cornwall is a region in the southwest of England. John Curgenven is a Cornish boatman. "
    "John Curgenven ferries visitors to Mont St. Michel. Mont St. Michel is located in Normandy. "
    "Erica vagans is a plant known as Cornish heath. King Arthur compared himself to John Curgenven.")}]
questions = [
    {"id": "Novel-aaa1", "source": "Novel-0001",
     "question": "Which region of France is Mont St. Michel located?",
     "answer": "Normandy", "question_type": "Fact Retrieval",
     "evidence": "Mont St. Michel is located in Normandy.", "evidence_relations": ""},
]

# Index: rule-based KG 构建（零外部依赖，2010 题全量可离线跑）
mg = MemoryGraph()
for doc in corpus:
    mg.extract_from_text(doc["context"], tags=[doc["corpus_name"]])

# Retrieval + extractive baseline（LLM 生成层后续接入）
results = []
for q in questions:
    r = mg.graphrag_query(q["question"], max_hops=2, top_k=5, include_context=True)
    top = r["answer_nodes"][0] if r.get("answer_nodes") else {"label": ""}
    results.append({
        "id": q["id"], "question": q["question"], "source": q["source"],
        "context": r.get("context", ""), "evidence": q["evidence"],
        "question_type": q["question_type"],
        "generated_answer": top["label"],   # extractive baseline
        "ground_truth": q.get("answer"),
    })
json.dump(results, open("/tmp/amg_predictions.json", "w"), indent=2)

# 诊断：graphrag_explain 显示 keyword coverage
print(mg.graphrag_explain(questions[0]["question"])["coverage"])
```

**实测输出**（2026-08-14 验证）：
- 索引：10 nodes / 4 edges；schema 完全兼容官方 `generation_eval --data_file`
- retrieval context 正确包含 `Michel --located_in--> Normandy` 关键三元组
- graphrag_explain coverage = 0.6667（"which/france" 等 keyword 未命中）

**运行结果暴露的两个真实弱点（见洞察 #1/#2）**。

## 4. 关键洞察 (5)

1. **缩写句点是 Novel 域的地雷**。`extract_from_text` 的 sentence segmentation 按 `. ! ? ; \n` 切分，把 `Mont St. Michel` 切成 `Mont St` + `Michel` 两个实体，产生 `Michel --located_in--> Normandy` 的碎片边。Novel 语料满地都是 `Mr.`、`Mrs.`、`St.`、人名缩写 —— **参赛前必须给 extract_from_text 加缩写保护**（约 20 行：句点前后均为大写单字母/已知缩写表时合并）。这也是 FalkorDB 配方里 FastCoref 存在的原因之一。

2. **Question-type-aware 答案提取 ≠ 最高分节点**。"Which region is X located?" 的答案是 `located_in` 边的**宾语**，而 `graphrag_query` 按关键词×度中心性排序返回的 top-1 是**主语**（Michel）。Fact Retrieval baseline 应该：识别 question type → 定位匹配关系类型 → 返回边宾语。约 30 行，是 extractive baseline 提分的最快手段。

3. **分阶段参赛策略：retrieval/indexing 先行**。官方三模块独立可跑。amg 可零 LLM 成本先提交 indexing_eval（需 export_graphml，~20 行）和 retrieval_eval（context 直接来自 graphrag_query 的 context 字段），生成层后补。**没有人阻止"检索榜"和"生成榜"分开发成绩** —— AutoPrunedRetriever 就是靠单维度优势进前二的证明。

4. **榜首配方与 amg 现有能力映射度极高**。FalkorDB 的 4 层 resolution 链 ≈ amg EntityResolver；MultiPath 2-hop 检索 ≈ amg PPR + max_hops；GLiNER 本地抽取 ≈ amg rule 模式。差距只在：指代消解（FastCoref 对应物）和 LLM 关系抽取模式。**amg 不缺组件，缺的是把它们串成 bench 配置的胶水**（约 150-200 行适配器 + README 配置表）。

5. **同组 MemGraphRAG (KDD'26) 验证了 memory×RAG 方向的学术正当性**。GraphRAG-Bench 团队自己的后续工作就是"memory-enhanced RAG"，说明该团队认可记忆结构是 GraphRAG 的下一站 —— amg 若以"memory-native GraphRAG"身份参赛并提交 issue/PR，与维护者社区的叙事契合度高，可能获得 leaderboard 收录的快速通道（FalkorDB 就是先例：第三方系统被列入官方对比表）。

## 5. amg 差距清单（参赛前 TODO，按优先级）

| # | 差距 | 工作量 | 对应洞察 |
|---|---|---|---|
| 1 | `extract_from_text` 缩写句点保护 | ~20 行 + 测试 | #1 |
| 2 | question-type-aware extractive answer（边宾语提取） | ~30 行 + 测试 | #2 |
| 3 | `export_graphml()` → indexing_eval | ~20 行 | #3 |
| 4 | run_amg.py 全量脚本（HF 数据加载 + sample_100 + LLM 生成层） | ~150 行 | #4 |
| 5 | 实体消歧链配置（ExactMatch→Semantic）复用 EntityResolver | 配置 | #4 |
| 6 | chunking 策略（小说长文档，512 token 句子边界切分） | ~30 行 | #4 |

## 6. 下一步行动 (3)

1. **[本周内] 差距 #1+#2**：给 Python amg 加缩写保护和 question-type 答案提取，用本研究 fixture 做回归测试（预期 extractive_hit=False→True）。这是 Cycle 432+ 的候选。
2. **[8 月底前] 跑通 Novel sample_100 retrieval_eval**：HF 下载 `GraphRAG-Bench/GraphRAG-Bench` 数据集，rule 模式索引 20 部小说，提交 retrieval-only 成绩 —— 零 API 成本的首个公开数字。
3. **[9 月] 生成层接入 + leaderboard 提交**：LLM 生成用 gpt-4o-mini 对齐 FalkorDB 配置（可比性），产出全量 2010 题成绩，向官方仓库提 PR/issue 申请列入 leaderboard，叙事定位 "first memory-native GraphRAG"（呼应 MemGraphRAG KDD'26）。

## 7. 质量自查

- [x] 可运行代码：适配器雏形实测通过（10 nodes/4 edges 索引、schema 兼容输出、explain 诊断）✅
- [x] 独到见解：缩写地雷、边宾语答案提取、分阶段参赛策略、榜首配方映射、MemGraphRAG 叙事契合 —— 均非 #062 或 FalkorDB 文档的简单复述
- [x] 项目关联：直接产出 6 项差距清单 + 3 项行动，映射 amg Cycle 432+ 与 9 月目标

## 参考

- 官方仓库: https://github.com/GraphRAG-Bench/GraphRAG-Benchmark（Evaluation/ + Examples/run_lightrag.py 的 prediction schema）
- ICLR 2026 论文: arXiv 2506.05690（proceedings.iclr.cc, poster 10007992）
- HF 数据集: GraphRAG-Bench/GraphRAG-Bench（novel.json / novel_questions.json / medical.json / sample_100）
- FalkorDB 接入范例: github.com/FalkorDB/GraphRAG-SDK/blob/main/docs/benchmark.md（ACC 公式、resolution 链、榜首配置）
- 同名区分: arXiv 2506.02404（Emory CS 教科书版，R Score/AR Metric）
- 相关后续: LinearRAG (ICLR'26)、MemGraphRAG (KDD'26)、DIGIMON 支持 (2025-08-24 news)
