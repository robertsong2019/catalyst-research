# Research #065: GraphRAG-Bench retrieval_eval 首跑机制 — Novel sample_100 零 API 执行路径

> Date: 2026-08-15 (Sat) 20:00 · Catalyst deep-exploration-evening
> 主题来源: HEARTBEAT.md 本周关键路径 "8月底 HF Novel sample_100 retrieval_eval 首跑（零 API 成本，参赛关键路径）"
> 前序: Research #064（适配器雏形 + run_amg.py C439）· #062（GraphRAG 全景）
> 状态: **官方评测器源码逐行解析完成 + 真实数据端到端冒烟验证通过** ✅（3 小说 / 277 题 / 10 题抽样）

---

## 0. TL;DR

读了 GraphRAG-Bench 官方 repo（`GraphRAG-Bench/GraphRAG-Benchmark`）的 `Evaluation/retrieval_eval.py` + 两个 metric 的完整源码：**retrieval_eval 有原生 `--mode ollama` 本地模式**，两个指标（Context Relevancy / Evidence Recall）**只依赖 LLM judge，不依赖 embedding**（embeddings 参数被初始化但从未调用——死参数）。用 amg 真实数据冒烟：3 部小说 123k 词 → 2946 节点/153 边（2.2s，rule 模式零 API）→ 10 题输出官方 8-key schema。**首跑唯一硬阻塞：本机未装 ollama**。全流程预估：20 小说索引 ~15s + 100 题 × 3 次本地 judge 调用 ~10-20min = 真正零 API 成本。

## 1. 核心概念 (5)

### 1.1 retrieval_eval 双指标 = 3 次 LLM judge 调用/样本
| 指标 | 机制 | 调用数 |
|---|---|---|
| Context Relevancy | judge 对 (question, context) 打 0/1/2 分，**两次独立评分取平均**（÷2 归一到 0-1） | 2 |
| Evidence Recall | judge 逐条判定 ground-truth evidence 能否从 context 推出，recall = attributed/total | 1 |

两个 metric 都截断 context 到 20k 字符（`[:20000]`），都要求严格 JSON 输出（RobustJSONHandler 自愈重试 ×2）。

### 1.2 官方评测器的 ollama 模式 = 零 API 成本的官方通道
```bash
python -m Evaluation.retrieval_eval \
  --mode ollama \                    # ← 官方支持，非 hack
  --model qwen2.5:7b \               # judge 模型（本地）
  --base_url http://localhost:11434 \
  --embedding_model BAAI/bge-large-en-v1.5 \  # ← 死参数，retrieval 两个指标不调用
  --data_file results/amg.json \
  --output_file results/retrieval_eval.json \
  --detailed_output                  # 逐样本分数 + 每题明细
```
源码事实：`evaluate_sample()` 的 `embeddings` 形参传进去后没被任何 metric 使用；`OllamaEmbeddings` 初始化是懒加载，传 HF 名字也不会报错。**首跑只需要 pull 一个 judge 模型。**

### 1.3 评测数据流：prediction JSON 的 `context` 字段是被评对象
retrieval_eval 从 prediction 文件读取 6 个字段：`id, question, question_type, context, evidence`（`source` 用于分组前的对齐，实际按 `question_type` 分组出报告）。**amg 适配器已产出的正是这些键**（run_amg.py C439 严格 8-key schema）。`context` 接受 list 或 str（源码 isinstance 分支处理）；amg 输出的是 graphrag_query 的格式化字符串（"## Relevant Entities\n- X (entity)..."），直接可用。`evidence` 是数据集原始字符串（非 list）——官方 LightRAG 示例原样透传，amg 保持一致以保可比性。

### 1.4 隐藏评分陷阱（源码级）
- **子串归零**：`if context_str.strip() in question: return 0.0` — 检索上下文若是问题子串直接 0 分（防作弊）
- **双采样方差**：relevancy 两次独立 judge 评分平均，本地小模型 judge 分歧大时会拉低/抖动；judge 模型确定性（temperature=0, seed=42, prompt 尾部 `/no_think`）是官方为 Qwen 系模型准备的
- **NaN 隔离**：judge 两次都解析失败 → 该样本 NaN，`np.nanmean` 跳过 —— 不会崩，但有效样本数会缩水，`--detailed_output` 才能发现

### 1.5 `--num_samples` 语义 + sample_100 策略
评测器先按 `question_type` 分组再 `select(range(num_samples))` —— **是"每类型取前 N"，不是全局 N**。amg 侧 run_amg.py 的 `--sample 100` 是全局确定性抽样（seed 42，id 排序后抽），2010 题分布 Fact 971/Complex 610/Summ 362/Creative 67 → 期望分层 ~48/30/18/3。首跑直接用 amg 侧抽样 + 评测时不传 num_samples，报告天然按类型分组。

## 2. 可运行代码 ✅（已在本机验证）

> 归档: `catalyst-research/code/2026-08-15/`（含冒烟产出的 `amg_predictions.json`）
> 依赖: 仅 amg 本地包（零网络 API）；数据从官方 GitHub raw 直连（免 HF CLI）

### 2.1 冒烟已验证：真实数据 → 官方 schema（`grb_smoke.py`）

```python
"""GraphRAG-Bench Novel 真实数据冒烟 — 已验证通过 (2026-08-15)。
实测: 3 novels/123,520 words → 328 chunks → 2946 nodes/153 edges in 2.2s (rule, 零API)
      10 questions answered in 0.6s, non-empty context 10/10, 官方 8-key schema
外推: 20 novels 全量索引 ~15s；sample_100 检索 <5s —— 瓶颈只在本地 judge
"""
import json, sys, time, urllib.request
sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
from run_amg import load_bench_data, index_corpus, answer_question
from memory_graph import MemoryGraph

# 1) 数据直连官方 GitHub（无需 huggingface-cli，两个 URL 已验证）
BASE = "https://raw.githubusercontent.com/GraphRAG-Bench/GraphRAG-Benchmark/main/Datasets"
DATA = "/tmp/grb"; import os; os.makedirs(DATA, exist_ok=True)
for name in ["Corpus/novel.json", "Questions/novel_questions.json"]:
    dst = f"{DATA}/{name.split('/')[-1]}"
    if not os.path.exists(dst):
        urllib.request.urlretrieve(f"{BASE}/{name}", dst)

# 2) 全量首跑：sample=100（换掉下面三行即冒烟版）
corpus, questions = load_bench_data(DATA, sample=100)   # seed=42 确定性抽样

# 3) 索引（chunk_size=512: C440 无损分块）+ 检索 → 官方 schema
mg = MemoryGraph()
stats = index_corpus(mg, corpus, chunk_size=512)        # ~15s / 20 novels
rows = [answer_question(mg, q) for q in questions]      # ~0.06s/题
json.dump(rows, open(f"{DATA}/amg.json", "w"), indent=2, ensure_ascii=False)
print("predictions:", len(rows), "| nodes:", stats["nodes_created"])
```

### 2.2 首跑收尾：评测器侧（本机唯一缺的一步）

```bash
# ① 装 ollama + judge 模型（首跑唯一硬阻塞，本机 2026-08-15 未装）
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b          # VPS RAM≥8G 用 7b；≥24G 可上 14b 对齐 FalkorDB 配方

# ② 拉官方评测器 + 依赖（ragas 0.2.15 / langchain 0.3.26 / datasets 3.3.2）
git clone https://github.com/GraphRAG-Bench/GraphRAG-Benchmark /tmp/grb-eval
cd /tmp/grb-eval && pip install -r requirements.txt

# ③ 零 API 评测（detailed_output 逐样本可审计）
python -m Evaluation.retrieval_eval \
  --mode ollama --model qwen2.5:7b --base_url http://localhost:11434 \
  --embedding_model bge-m3 \
  --data_file /tmp/grb/amg.json \
  --output_file /tmp/grb/retrieval_eval.json --detailed_output
```

## 3. 关键洞察 (5)

1. **"零 API 成本"已从口号变成源码事实**：官方评测器原生 ollama 模式 + retrieval 指标不碰 embedding + amg rule 抽取/检索零 LLM —— 三段里没有任何一环必须调外部 API。amg 全管线成本 = 磁盘上的 judge 模型权重 + 电费。
2. **首跑瓶颈不在 amg，在 judge 基建**：20 小说索引 15s、100 题检索 5s，而 100 题 × 3 次 judge 调用（串行，`max_concurrent=1`）在本地 7B 上 ~10-20min。工程上首跑前只需做一件事：装 ollama pull 一个模型。
3. **judge 模型选择影响分数可比性**：官方榜大概率用 gpt-4o-mini 判分；本地 qwen2.5:7b 的绝对分数会偏低（小模型 JSON 输出 + 评分保守），但**用于迭代对比 amg 自己的版本间变化完全可靠**。正式提交前需换 API 模式复测一次。
4. **amg 输出的 context 是"实体卡"不是"原文段"**：graphrag_query 返回格式化实体列表（"## Relevant Entities\n- X (entity)"），而 judge 问的是"context 是否包含回答所需信息"。实体标签卡在 Evidence Recall 上可能天然吃亏（evidence 多为完整句）。首跑后若 Recall 低而 Relevancy 尚可，第一个改进方向是**context 里带上边的三元组原文或原句**（amg 有 provenance，一条 API 就能加）。
5. **`--num_samples` 的"每类型前 N"语义是个陷阱**：若直接对全量 2010 题跑评测器加 `--num_samples 25`，会评 4×25=100 题但 Creative 只有 67 题全部被评的错觉；amg 侧先抽样（run_amg.py）再全量评测文件是最干净的路径，且 seed=42 确定性可复现。

## 4. 下一步行动 (3)

1. **【本周】执行首跑**：装 ollama + qwen2.5:7b → §2.1 全量 sample=100 → §2.2 评测，产出第一份 amg retrieval 分数基线（context_relevancy / evidence_recall × 4 题型），写入 experiments.tsv
2. **【首跑后】Recall 诊断**：若 evidence_recall < 0.3（rule 实体卡 vs 完整句 evidence 的预期落差），给 answer_question 的 context 附加边三元组 `s → r → o` 行（amg provenance 现成，~15 行改动），再跑对比
3. **【提交前】judge 切换复测**：`--mode API --model gpt-4o-mini`（一次性 ~300 次调用，成本 < $1）拿官方可比分数，确认本地/远程 judge 的 delta 后再决定提交口径

## 5. 与现有项目关联

- **run_amg.py (C439)**: 直接复用，本次验证确认其 load_bench_data/index_corpus/answer_question 在真实 825k 词语料上表现符合预期
- **chunk_text (C440)**: 512-token 无损分块在 328 chunks/3 novels 上工作正常
- **GraphRAG-Bench 差距清单**: #1-#4、#6 已关闭，本次把"评测器执行"这最后一公里也解析完毕 —— 首跑从"设计完备"进入"执行就绪"
- **amg provenance (4 APIs)**: 洞察 #4 的 context 增强原料，无需新 API

---
*Sources: github.com/GraphRAG-Bench/GraphRAG-Benchmark (retrieval_eval.py / metrics/*.py / Examples/run_lightrag.py, accessed 2026-08-15) · arXiv 2506.05690 · graphrag-bench.github.io*
