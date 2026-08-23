# LLM-as-Judge for Agent Memory Benchmarks — amg cat5/kupdate 残差的语义判分立项

**Research #069** | 2026-08-17 20:00 (deep-exploration-evening) | 来源: HEARTBEAT Next dev target "cat5+多跳残余→LLM judge 立项"

## 背景与动机

amg 双基准现状的已知瓶颈（C454/C455）：
- **LME_s x50 首跑**: kupdate acc 0.0 但 retrieval_hit 1.0 — 检索侧完美，抽取协议（exact_judge 词边界匹配）判 0。"LLM judge 才是 leaderboard 可比口径"
- **LoCoMo cat5（对抗）**: C455 证伪了名字拓扑路线 — cat5 证据全指向主体自己的 turn，谓词级语义匹配（嵌入/LLM judge）是唯一剩余路径
- 熵门 sweep（C454）对纯事实型 split 无增益 → 答案侧（判分协议）是下一个杠杆，而非检索侧

本笔记立项：调研判分协议设计空间，产出可运行的 judge 原型。

## 核心概念 (5)

### 1. 参考锚定二元判定 (Reference-Anchored Binary Verdict)
LongMemEval leaderboard 原生协议 = **gpt-4o binary accuracy**（ProsusAI/MemEval 复现时明确对齐）。MT-Bench 后续研究（Adaline 2026 综述）：**有正确参考答案时，参考锚定打分一致比 prompt-only 打分可靠**。对 amg：judge 只输出 CORRECT/WRONG，无分数梯度 — 直接规避 score-ID bias 和 rubric-order bias（Li et al., arXiv:2506.22316：judge 对 rubric 顺序/分数编号排列敏感，GPT-4o 偏好打 4、Qwen3-32B 偏好打 5）。

### 2. 判据级多数投票 (Criterion-Level Majority Voting)
Memora（arXiv:2604.20006, "From Recall to Forgetting"）的评估设计：每题拆成原子判据（memory-presence / forgetting-absence 两组二元判据），**3 个异构 judge（GPT-4.1 + Claude Haiku 4.5 + Gemini 2.5 Flash）各投一票取多数**，达到 88.3% 人类一致率、Cohen's κ 0.86–0.90。关键：判据是原子的（单一事实点），不是整题开放打分 — 原子性让 judge 的可靠区间最大化。

### 3. Forgetting-Aware Memory Accuracy (FAMA)
Memora 提出：`FAMA = max(0, MPA − λ·(1−FAA))`，其中 MPA=有效记忆判据命中率，FAA=过期记忆排除率。**标准 accuracy 系统性高估记忆系统** — 记忆 agent 的 FAMA 折损随时间线拉长而增大（A-Mem 月度 −29.5、季度 −37.9），因为"保留旧记忆而无遗忘机制会放大不一致"。与 amg 的 knowledge_freshness_report + forgetting_forecast 叙事直接同构 → 可作为 amg 差异化指标（我们的 bi-temporal 谱系天然支持过期判据生成）。

### 4. 可靠性≠效度 (Reliability ≠ Validity / κ-Deflation)
arXiv:2606.19544（21 judge 大规模审计）：① **kappa deflation** — 所有 judge 的 exact-match 一致率虚高，机会校正后（Cohen's κ）差距可达 **41.2 个百分点**；② **consistency–bias paradox** — test-retest 最稳定的 judge 反而可能是最偏的（Qwen 3 8B、Gemini 2.5 Flash 落在"一致但偏"象限）。实践含义：**报告 test-retest 一致性作为 judge 验证是误导**，必须报 κ + 与人工标签的校准；分歧率 >20–25% 时重审 rubric（Adaline 实践阈值，原型已内置）。

### 5. 公平评估框架的度量分层 (MemEval: F1 + Judge + Tokens 三列)
ProsusAI/MemEval 标准化了 amg 一直手工做的事：同一 LLM、同一 embedding、同一判分管线、端到端 token 计费（ingestion+retrieval+answer）。**LoCoMo 1986q 参考数字**（judge=gpt-5.2 三维均值，LLM=gpt-4.1-mini）：
- PropMem 0.823 / OpenClaw 0.725 / Full-Context 0.709 / Mem0 0.497
- **cat5 Adversarial 列**：Graphiti 0.873（全场最高，KG 结构对对抗题有真实优势）/ PropMem 0.794 / OpenClaw 0.528 / Mem0 0.629
- 公平性注记：Zep 商业版 94.7% 用的是 LLM-judge accuracy，Mem0 论文独立复测 Zep token-F1 仅 0.35–0.50 — **指标口径不同，数字不可互换**（amg 发 README 时必须双列 F1+Judge 并注明口径）

## 代码示例 (已验证可运行)

`code/llm_judge_amg.py` — amg_bench_quality 判分器原型，实测输出：

```
=== amg LLM-Judge 原型 [MOCK(词F1)] — 6 cases ===
[CORRECT] 'Where does Janet prefer to work?' <- 'She usually works from quiet coffee...'  (kupdate 形态)
[CORRECT] 'What did Janet buy last week?'    <- 'Janet bought a new laptop last week.'    (exact=1 基线)
[WRONG  ] "When is Janet's sister's birthday?" <- "I'm not sure about that."  (abstain→WRONG, cat5 幻觉检查)
[WRONG  ] "What is Janet's favorite cuisine?"  <- 'She really enjoys Mexican tacos.'  (实体替换→WRONG, cat5 对抗核心)
=== exact_judge 对照校准 ===
{"agree": 6, "divergence_rate": 0.0, "verdict": "rubric OK"}
```

设计决策（每条对应一条研究结论）：
- **二元 rubric + "Do not reward verbosity / Do not infer missing facts"** — Deepchecks 式显式失败条件
- **参考答案后置于 prompt 尾部** — 规避 rubric-before-answer 的 recency 比较效应
- **temperature=0 + max_tokens=8** — 判定输出形态钳制
- **ERROR 不计入多数票，全 ERROR 返回 ERROR** — 不让基础设施故障污染准确率
- **calibration_report() 内置 divergence>25% 重审阈值** — 对 C447 的 exact_judge 与新 judge 并行跑，分歧样本即人工抽检清单
- **mock 降级模式** — 本机 ollama 未装（双首跑①同一 blocker），管线在 mock 下可全链路验证；`--real` 切真实 ollama 端点（qwen2.5:7b）
- 诚实注记：mock 是词 F1 代理，**语义救回（指代/同义改写）只能由真 LLM judge 展示** — mock 的作用是管线与统计聚合验证

## 关键洞察 (4)

1. **kupdate 0.0 不是 amg 的病，是协议的病，但修协议要防"通胀"**：MemEval LongMemEval 表里所有系统的 K-Update 都是最低分之一（PropMem 0.528 / SimpleMem 0.475 / Full-Context 0.202），知识更新本来就是全场最难的类别。换 LLM judge 后 amg 的 kupdate 预期从 0.0 → 0.2-0.5 区间，但**必须同时报 exact 口径**，否则"数字提升"不可归因（是系统变好还是 judge 变松？）。双口径报告是唯一诚实解。

2. **cat5 的 LLM judge 数字会好看，但要警惕 Graphiti 效应的反面**：MemEval 中 Graphiti 在 Adversarial 列 0.873 领先靠的是 KG 结构性拒答。amg 已有熵双门 abstention（C448），**判分协议要保证 abstain 被判 WRONG 而非 CORRECT**（原型已验证此语义）——这是对抗题判 0 成本幻觉的关键。C452/C454 的熵门结论"门是任务相关的"在此闭环：cat5 是门的正收益区。

3. **多轮辩论式 judge 会放大偏置**（EMNLP 2025），Memora 的 3-judge 单轮多数票即可到 κ≈0.87 — amg 不需要复杂 judge 编排，**原子判据 + 单轮多数票**就是可靠性与成本的甜点。且 judge 模型须与被测生成器异构（防 self-preference，Li et al. 2506.22316 的选型：judge 与 generator 不同家族）。

4. **FAMA 是 amg 的叙事机会窗口**：Memora 证明"遗忘感知"指标能重排系统名次（Nemori 因遗忘折损小反超 A-Mem/MemoryOS）。amg 的 bi-temporal（valid_at/invalid_at）+ forgetting_forecast + knowledge_freshness_report 是全行业少有的能**原生生成过期判据**的谱系 — 把 FAMA 式评估做进 amg-bench，是把已有 API 变成 benchmark 差异化卖点的最短路径（对标 TencentDB-Agent-Memory 竞争压力）。

## 与现有项目关联

- **amg-bench (`amg_bench_quality` / `locomo_bench_quality`)**: judge 模块直接插入 run_eval 的 judge 参数位；C454 的 exact_judge 保留为口径 A，LLM judge 为口径 B
- **熵双门 abstention (C448)**: judge 协议定义 abstain=WRONG，与门的 abstention 语义（best≤weak ∧ entropy≥thr）形成评估闭环
- **GraphRAG-Bench 双首跑①**: ollama 是共同 blocker — 装 ollama 后 `--real` 模式与 retrieval_eval 同时解锁
- **README/publish**: MemEval 公平性注记（judge accuracy ≠ token F1）必须写进 amg README 的 benchmark 对比表脚注

## 下一步行动 (3)

1. **[dev, ~1 cycle] `llm_judge_amg.py` 落地进 amg 真身仓**：包装为 `amg_bench_quality.judge_llm()`（stdlib-only，与 amg 零依赖风格一致），CLI 加 `--judge llm --judge-model qwen2.5:7b`，双口径输出（exact/llm 两列 + divergence 报告）。先 mock 全链路测试，ollama 就位后 LME_s x50 复跑对照 kupdate/preference 两列。
2. **[infra, human/1 命令] 安装 ollama + `ollama pull qwen2.5:7b`** — 同时解锁双首跑①与 judge 实测（同一 blocker 第二次出现在关键路径上，值得升级优先级）。
3. **[research→blog] FAMA 式遗忘感知评估 for amg**：用 bi-temporal 谱系生成 forgetting-absence 判据，在 LoCoMo/LME_s 上跑 FAMA 变体 — 候选博客《Benchmarking Forgetting: 遗忘感知评估如何重排记忆系统名次》，与 amg forgetting_forecast 形成产品+叙事双输出。

## 质量自评

- [x] 可运行代码：6 case 全部预期判定通过（含 cat5 实体替换→WRONG、abstain→WRONG 两个关键语义），mock 模式零依赖可跑，`--real` 留 ollama 接口
- [x] 独到见解：双口径归因诚实性 / abstain=WRONG 对抗闭环 / Graphiti 效应反面 / FAMA 叙事窗口（4 条，均非检索结果直接可得）
- [x] 项目关联：直连 C448/C454/C455 三条近期结论 + 双首跑 blocker + README 口径脚注
- 素材来源：Zep eval 指南 / ProsusAI-MemEval (GitHub) / arXiv:2604.20006 (Memora) / arXiv:2606.19544 (kappa deflation) / arXiv:2506.22316 (scoring bias) / IJCNLP-2025 position bias / Adaline+Deepchecks 实践
