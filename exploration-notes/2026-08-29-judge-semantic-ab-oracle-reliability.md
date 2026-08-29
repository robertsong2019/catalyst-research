# Research #092 — judge_semantic A/B 的 oracle 校准协议：LLM 判分器可靠性量化

**日期**: 2026-08-29 20:00 (deep-exploration-evening)
**触发**: HEARTBEAT 关键路径 #3 首位 — "judge_semantic() A/B（#090 判分器落地候选：C519 解锁 3 题 + kupdate 12 rescue 题 + C526 census 新证据：58 题 GT 串全 haystack 不存在=引用式判分结构性死亡，天然评测题集；**llm 标签当 oracle**）" — "llm 标签当 oracle" 这半句此前是未审计的假设 → 研究先行
**状态**: ✅ 完成 — 文献栈 6 篇（全部验证原文/摘要）+ 零依赖原型 21/21 全绿

---

## 一、问题定义

#090 造好了确定性判分层（answer_equiv_judge.py 三层架构，26/26），C526 证实 58 题 GT 串在语料中不存在（引用式判分结构性死亡），judge_semantic 上位为最大杠杆。落地前的 A/B 方法学悬而未决：**用 LLM 判分标签当 oracle 来验证确定性判分层，这个 oracle 本身有多可靠？噪音多大时 A/B 结论开始失真？需要什么统计工具才能合法地宣称"v1 优于 v0"？**

三个具体子问题：
1. LLM judge 的一致率文献读数（0.85~0.98）对 amg 的 500 题意味着多少错标签？
2. 原始一致率（exact agreement）够不够作为 A/B 指标？
3. 判分结论对 prompt 措辞、解码温度、trial 次数的敏感度有多高？

## 二、文献栈（6 篇核心）

### 1. Wu et al., ICLR 2025 (LongMemEval) — Table 6 元评估（从论文 HTML 原文验证）
- **官方 judge = prompt-engineered gpt-4o-2024-08-06，逐题二值 yes/no，按题型分 prompt**
- 元评估（30 题/类 × 7 类 × 2 生成模型）：**GPT-4o judge 人工一致率总均 0.98**，分类型读数：ss-user 1.00 / ss-assistant 1.00 / **ss-preference 0.90（最弱，"开放性答案"）** / multi-session 1.00 / kupdate 1.00 / temporal 1.00 / **abstention 0.97**
- **判分指令本身含不对称规则**："response contains the correct answer or all intermediate steps → yes；**only contains a subset of the information required → no**"——superset 给分、subset 不给分，与 #090 的 Bulian 不对称等价同构
- 这是"llm 标签当 oracle"的**协议合法性证明**：leaderboard 分数本来就定义为 judge 分数——oracle 不是近似真理，**oracle 就是协议本身**

### 2. Yagubyan et al., 2026 — "The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge"（arXiv:2606.13685）
- 29 任务 × 2 OpenAI judge × 50 配对 trial + 50 点评 trial/题：**配对偏好平均翻转率 13.6%**，28% 的题翻转率 >20%，最差一题 56%
- GPT-4o-mini 有显著首位偏置（72% A-majority）；**跨 judge 一致仅 76%（κ=0.51）**
- **语义等价的 prompt 模板互换 → 25% 的题多数决翻转**；温度 0 降低但不消除不一致
- 点评式（pointwise）分数差距小且聚合不显著——**配对-点评鸿沟：judge 常在自己标量分都无证据时硬选赢家**
- 可靠性曲线：**多数决恢复 50-trial 基准判定到 95% 概率需 11 个 trial**（高方差题 15 个）
- 结论：多 trial 聚合 + 位置随机化 + 显式不确定性报告应成标准实践

### 3. Norman et al., 2026 — "Reliability without Validity"（arXiv:2606.19544，21 judge × 9 provider × 541k 判决）
- **exact-match agreement 普遍虚高：与 Cohen's κ 的差距（κ 缩水）在 MT-Bench 上达 33-41 个百分点**——机会校正不是装饰品
- judge 排名跨基准漂移最多 14 位；**consistency-bias paradox：test-retest >0.95 与严重位置偏置 >0.10 在两个生产 judge 上共存**——稳定 ≠ 无偏
- 单一 rubric 下 verbosity bias 很小（<0.011）——偏置读数强烈依赖测量协议
- 交付 **Minimum Viable Validation Protocol**（一致率、一致性、偏置审计三协议分立）

### 4. TMLR 2026 — "A Systematic Evaluation of Bias Mitigation Strategies in LLM-as-a-Judge Pipelines"（arXiv:2604.23178）
- 9 种去偏策略 × 5 judge × 3 基准：**风格偏置才是主导偏置（0.10-0.76，markdown > plain prose），远超位置偏置（≤0.04）**
- verbosity 异质且 length-aware：Gemini/Llama 偏长（+0.24~+0.44）、Claude 偏短（−0.12）、GPT-4o 中性
- **头条实用结论：中档模型 + 正确去偏 > 裸奔 frontier**——Gemini 2.5 Flash + Combined Budget 达全场最高一致（71.0%, κ=0.549），价格约 1/15
- 启示：判分可靠性不必买最贵的模型；**缩小被判决面是比提示工程更强的去偏**

### 5. Ye et al., ICLR 2025 — "Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge"（CALM 框架，arXiv:2410.02736）
- 12 类偏置的系统分类学 + 自动量化框架：self-preference、verbosity、fallacy oversight 等
- 价值：偏置要有**分型的检测协议**，不能读一个总分——amg 的分型 confusion 矩阵是同构思路

### 6. Shi et al., IJCNLP 2025 — "A Systematic Study of Position Bias in LLM-as-a-Judge"（arXiv:2406.07791）
- 位置偏置的三指标（含 repetition stability）；**多数决在简单实例上增强可靠性**——多 trial 聚合的有效边界

## 三、核心概念

1. **Oracle 是协议不是真理（oracle = protocol, not truth）**: LongMemEval 的"正确"由官方 judge 协议定义，Table 6 的 0.98 度量的是协议与人类的漂移而非 judge 的错误率。因此 judge_semantic A/B 的目标是 **agreement-with-protocol**，且分类型噪音底（preference 0.10 / abstention 0.03 / 其余≈0）是任何针对 oracle 的 A/B 的**分辨率极限**——噪音底以下的 rescue 主张原则上不可证明。
2. **Chance-corrected 比较底座（κ + McNemar）**: 不平衡数据（本域 ~90% 题不给分）使原始一致率虚高——本 harness 实测 raw 0.90 → κ 0.44（33-41pp 缩水的缩影）。判分器 A vs B 的合法检验是 **discordant pairs 上的 McNemar 精确二项检验**，不是 raw delta；κ 负责"这个判分器整体比抛硬币好多少"，McNemar 负责"B 是否显著优于 A"。
3. **点评式判分是偏置文献的 calm 区（pointwise calm zone）**: 位置偏置（配对专属）、风格/长度偏置（配对排序）、self-preference（判自己的输出）几乎都是 pairwise 现象；LongMemEval 判分是 **pointwise 二值 + 题型分 prompt + 短抽取式答案**——攻击面最小。残余风险 = 模板敏感性（25%）+ 解码抖动 → 对策：钉 prompt hash（#080 纪律）+ 温度 0 + 仅 NEEDS_JUDGE 带多 trial 多数决。
4. **确定性级联是极限形式的去偏（cascade-as-debiasing）**: TMLR 2026 证明"中档模型+去偏 > 裸奔 frontier"；确定性 T0/T1/T2 层是这条逻辑的极限——**零翻转、零模板敏感、零风格偏置**，每判掉一题就把 LLM 的被判决面缩小一题。最便宜的可靠 judge 是根本不调模型的那部分；LLM 留给 NEEDS_JUDGE 带，那里 0.98 的人工一致率才值得付噪音成本。
5. **多数决的不动点（majority fixed point）**: k=3 多数决的有效翻转率 3p²(1−p)+p³ 在 **p<0.5 时 < p（降噪）、p>0.5 时 > p（放大）**——先校准 oracle 分型翻转率、再决定是否集成，盲目 k=3 对坏 judge 是噪声放大器。

## 四、可运行代码

**文件**: `code/judge_ab_harness.py`（零依赖 Python 3.10+，~420 行，21 用例自测全绿）

```python
python3 code/judge_ab_harness.py --selftest   # 21/21
python3 code/judge_ab_harness.py --demo       # A/B + oracle 噪音扫描

# 核心 API：
judge_v1(q, ref, cand)   # 'CREDIT' | 'NO_CREDIT' | 'NEEDS_JUDGE'（#090 三层简化移植）
OracleJudge(seed, trials, noise_scale)  # 分型噪音底按 LongMemEval Table 6 校准的模拟 oracle
cohens_kappa(pred, oracle)              # chance-corrected 一致率
mcnemar_exact(b, c)                     # 配对判分器比较的精确二项 p 值
bootstrap_credit_ci(credits, truth)     # credit 准确率 95% CI
```

判分层四守护：数字签名一票否决（7≠17）、货币域冲突（币种规范化后 $5≠5eur）、**不对称包含**（cand⊂ref 更弱不给分 / ref⊂cand superset 给分——与官方协议"subset→no"逐字对齐）、软相似臂（difflib 替身，嵌入臂的生产位）；无守护命中的词面不可解一律 NEEDS_JUDGE（诚实弃权）。

**Demo 读数**（22 例，形态取自 C519/C526 真实失配面）：

```
oracle 噪音   v1 κ    Δ一致率  rescue  hijack  McNemar p   判决
x0.0         0.560   +0.318   7/T0      0     0.0156     B>A
x1.0(官方)   0.488   +0.318   7/T0      0     0.0156     B>A
x2.0         0.384   +0.227   6/T0      1     0.0312     B>A
v1 confusion=(tp7, fp0, fn5, tn10)  NEEDS_JUDGE=9
```

官方校准噪音下 v1 显著优于 v0 且零 false-pass；**x2.0 噪音时出现 1 个假 hijack——v1 构造上 fp=0，这个 hijack 纯属 oracle 噪音伪造**（洞察 3 的实验证据）。

**调试中修掉的 5 个真 bug**（每个都是生产移植预演）：κ 测试预期写反（0.444 是 90% 基率下的正确值，测试却在验证"高 κ"——先算机会一致再写断言）；不对称包含方向搞反（"table tennis" 作候选是 IMPROVES 给分，弱方向才是 ref=table-tennis/cand=tennis）；货币词未在归一化层规范（"$56,355" vs "56355 dollars" 因 usd/dollars 字面不同掉进 NEEDS_JUDGE）；0.45-0.75 低相似带误设 NO_CREDIT（"Rachel" vs "she planned it herself" 词面零重叠但语义对——确定性层该弃权而非错杀）；多数决测试噪音参数推过 p=0.5 不动点（6.0× 使 preference 翻转率 0.6，k=3 反向放大）。

## 五、关键洞察

1. **"llm 标签当 oracle"是协议合法的，但分型噪音底要写进结论里**：LongMemEval 的 leaderboard 分数定义为 judge 分数，所以 A/B 对 oracle 的读数是"与协议的一致率"。preference 层 0.90 的人工一致率意味着该层任何 <10% 的 rescue/hijack 差异都在 oracle 噪音底以下——**rescue 主张必须按题型分层申报，全题平均读数会淹没这个分辨率极限**。这把 amg 的 census 分层纪律（#083 每臂 sanity）从检索侧搬到了判分侧。
2. **A/B 的合法统计不是可选装饰**：90% 基率下 raw agreement 0.90 对应 κ≈0.44；判分器比较必须 McNemar。amg 现有 calibration_by_category（C465）读的是原始一致率——落地 judge_semantic 时升级为 κ + McNemar + 分型 confusion（本 harness 的 run_ab 输出直接可移植为 `judge_ab_report()`）。
3. **Oracle 噪音会伪造 hijack**：demo x2.0 档的假 hijack 是实验证据——**oracle 是证据不是证明**，false-pass 主张要用确定性推理复核（"这题 v1 给分的机制路径是什么"），不能只信 oracle 标签。C518 的"−1=运行噪声"归因与此同源。
4. **Pointwise 二值判分 + 钉死的题型 prompt 是攻击面最小的 LLM 用法**：偏置文献的四大主角（位置/风格/长度/self-preference）几乎全是 pairwise 现象；LongMemEval 协议天然规避。残余风险（模板敏感性 25%、解码抖动）用 #080 的 prompt-hash 纪律 + 温度 0 + NEEDS_JUDGE 带限定多 trial 对冲——**不要全题 k=3（成本 ×k），也不要不投票（单 trial 13.6% 翻转是 pairwise 读数，pointwise 远稳但非零）**。
5. **Cascade-as-debiasing 是 amg 评估叙事的缺角**：竞品叙事是"LLM judge 准"（要买 frontier）；amg 叙事是"确定性层把 LLM 判决面缩到最小 + NEEDS_JUDGE 诚实弃权 + 分型校准报告"——TMLR 2026 的"中档+去偏>frontier"是外部证据。README 卖点第四根支柱：**deterministic judge with honest abstention, validated by protocol-aware A/B**。
6. **Subset-direction credit 是开放的协议问题（留给下游）**：官方指令"subset→no"与抽取式惯例（counting 题答裸数字算对）在 bare-number 形态上冲突——"30" vs GT "about 30 people" 算 subset（不给分）还是完整答案（给分）？Bulian 的不对称 AE 说更弱不给分，LME 实操似乎给分。**答案依赖 form**：counting form 裸数字=完整答案，entity form 缺 restrictor=更弱——镜像律（#090 洞察 1）第三次独立命中。需在 ollama 解锁后实测官方 judge 行为再定 v1 的 counting 特例。

## 六、下一步行动

1. **judge_semantic() 落地 amg_bench_quality.py（最高优先，C527 候选）**：#090 三层 + 本篇四守护 + NEEDS_JUDGE 弃权；A/B 报告按本 harness 格式（分型 confusion + κ + McNemar + CI）；评测集 = C526 58 题 + kupdate 12 rescue + C519 3 题（73 题，oracle 标签待 ollama）。
2. **ollama 解锁后的 judge 协议**：prompt 逐题型钉 hash + 温度 0；先跑 preference 层（噪音底 0.10，最小可信差异 ≈ 9 个 discordant pairs @ McNemar α=0.05）；NEEDS_JUDGE 带限定 k=3 多数决。
3. **calibration_by_category 升级**：C465 的原始一致率读数补 κ 列——30 行改动，README honest-attribution 又一节。
4. **bare-number credit 的 form 特例**：查 LongMemEval 官方 judge 对 counting 题裸数字候选的实际行为（rag 复现或读 repo issue），决定 v1 是否给 counting form 开 subset 特例。

## 七、质量自评

- ✅ 可运行代码：21/21 自测全绿，零依赖，run_ab() 报告格式可直接移植 amg_bench_quality
- ✅ 独到见解：oracle=protocol 的分辨率极限论证；cascade-as-debiasing（外部证据 TMLR 2026）；oracle 噪音伪造 hijack 的实验证据；多数决不动点
- ✅ 项目关联：直连关键路径 #3 首位（judge_semantic A/B）、C465 升级、README 第四支柱、C526 的 58 题天然评测集
- 局限：模拟 oracle 的分型噪音底是 Table 6 的 30 题/类估计（抽样误差 ~±0.05）；difflib 软臂是嵌入臂的占位（真语义相似度待 sidechannel 依赖）；McNemar 在 b/c 小样本时功效有限（73 题规模下最小可检测差异偏大）

## 参考

- Wu et al. 2025 (LongMemEval), arXiv:2410.10813 (ICLR) — Table 6 元评估 + Figure 10 judge prompt（原文 HTML 验证）
- Yagubyan et al. 2026 (Coin Flip Judge), arxiv.org/abs/2606.13685
- Norman et al. 2026 (Reliability without Validity), arxiv.org/abs/2606.19544
- TMLR 2026 (Bias Mitigation Strategies), arxiv.org/abs/2604.23178
- Ye et al. 2025 (CALM, Justice or Prejudice), arxiv.org/abs/2410.02736 (ICLR)
- Shi et al. 2025 (Position Bias), arxiv.org/abs/2406.07791 (IJCNLP)
- 检索路径：Tavily 432 第 6 天 → AnySearch (mcporter) + web_fetch arXiv HTML 原文验证，全程零阻塞
