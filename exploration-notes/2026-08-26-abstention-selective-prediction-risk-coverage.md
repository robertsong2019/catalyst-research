# Research #089: LLM 弃权与选择性预测——从单点阈值到 Risk-Coverage 曲线

> 2026-08-26 20:00 deep-exploration-evening | 主题来源：HEARTBEAT Next dev targets 第一项（abs30 剩余 15 错）
> 方法论：autoresearch.md（明确指标/快循环/积累性）
> 关联：amg C448 熵双门 → C498 preference 弃权 → C513/C516 neg-exist 双门（昨晚刚落地）；amg_bench_quality.py 弃权评估现状=固定阈值单点

## TL;DR

amg 已经独立发明了一整套弃权机制族（熵门/偏好门/neg-exist 双门），但评估仍停留在**固定阈值操作点**（`abstain_score=1.0` / `abstain_entropy=0.95`）。学术界的成熟框架是 **selective prediction + risk-coverage 曲线**：AURC/E-AURC 把整个阈值 sweep 压缩成单标量，E-AURC 跨题类可比。同时 AbstentionBench (ICML 2025, Meta FAIR) 证实：**reasoning 微调让 LLM 弃权能力平均降 24%**——amg 的零 LLM 机制门恰好绕开"模型不会表达不确定性"这一根本短板，是对外叙事的强对标。

---

## 核心概念

### 1. AbstentionBench 场景分类（Kirichenko et al., arXiv:2506.09038, ICML 2025）

20 数据集 / 35k 不可答题 / 20 个前沿 LLM。弃权场景五分类：

| 场景 | 代表数据集 | amg 对应 |
|------|-----------|---------|
| Unknown answers（无已知答案） | KUQ, Known Unknowns | — |
| **False premises（假前提）** | FalseQA, ALCUNA | **neg-exist 双门（C513/C516）**：问图中不存在实体 |
| **Underspecified（欠指定）** | MediQ, Musique(无证据多跳), (QA)² | 熵双门（C448）证据不足；Multi-hop abstention |
| Subjective（主观） | MoralChoice, BBQ | — |
| **Outdated（知识过期）** | FreshQA（答案随时间改变） | **时间型 abs 残余**；knowledge_freshness_report |

关键发现：①弃权是未解决问题，模型 scaling 几乎无效；②**reasoning 微调降弃权 24%**（DeepSeek R1 vs 基座），推理链明明表达不确定、最终答案仍确定作答；③GSM8K-Abstain 构造法=从可答题删除关键上下文——与 LongMemEval `_abs` 题构造同构。

### 2. Selective Prediction 与 Risk-Coverage 曲线

经典框架（Geifman & El-Yaniv 2017 一脉）：按作答置信降序，逐题计入作答集，**coverage**=已作答比例，**risk**=已作答集合错误率。弃权的收益=把低置信题排除在作答集外（不产生风险）。**AURC**（曲线下面积）=全谱系权衡的单标量总结；**E-AURC**=AURC−Oracle（闭式 k²/2n²），难度归一后跨题类可比。**Risk@coverage k**=弃 (1−k)% 题后的错误率。

Ding et al. (CVPRW 2020) 实证：AUROC/AUPR/AURC 三者中**只有 AURC 可靠**（对 SC 系统排序质量敏感且不偏）。Zhou & Landeghem (ICML 2025) 给出 population AURC 的统计刻画（等价于重加权风险的期望）。

### 3. Calibration ≠ Selective Prediction（RLSR, arXiv:2607.03528, 2026-07）

对齐阶段直接以 AURC 为 RL 奖励（RLSR/GRPO 框架）。概念分野：**校准（ECE）要求置信与对错概率一致；SP（AURC）只要求对题的置信排在错题前面**。完美校准既不充分也不必要于完美 SP。基准复现见下方代码：对称"校准"信号 AURC=0.456，过自信但排序完美的信号 AURC=0.130——3.5× 差距。

### 4. Reasoning 微调降弃权（AbstentionBench 核心反直觉发现）

R1/s1 等 reasoning 模型平均弃权 −24%，且加大推理 token 预算进一步恶化。机制：模型幻觉出缺失上下文并据此作答。**amg 的启示**：LLM 自我表达不确定性的能力不可靠，规则化机制门（不依赖模型自知）是正交且更稳的路线。

### 5. Form-gated selection = 分段 risk-coverage

amg 的 form 分类器驱动每类用不同门/不同超参（insight #233/#251"form 分类器即配置面"）在 SP 框架下的数学表述：**全局 AURC 是各类曲线的覆盖率加权混合，单阈值全局调优只能在混合曲面上拿鞍点**——这正是 C452 "熵 sweep best=None"、C473 "检索超参不可全局调优" 的统一解释。正确的评估粒度是 **per-form AURC**。

---

## 可运行代码

`code/risk_coverage_aurc.py`（零依赖，核心 ~40 行可直接移植 amg_bench_quality.py）。

**实测输出**（python3 验证通过，seed=517 确定性）：

```
门                             AURC   E-AURC  Risk@90%      固定0.35正确弃权    误伤
Gate A 熵门型(宽)               0.3969   0.2974    0.4356           12/30    19
Gate B neg-exist型(窄)        0.3942   0.2948    0.4244           15/30     3

对称校准但排序差: AURC = 0.4559
过自信但排序完美: AURC = 0.1304  ← SP 只要求排序
```

模拟 full-500 形状（470 可答@0.60 正确率 + 30 abs，Gate B=neg-exist 窄门 15/15 捕获、Gate A=熵门宽门 ~11/15 捕获）。四个视角全部一致偏向 Gate B。注意 AURC 差距（0.0027）被 500 题基数稀释——**门间真实差异要在 per-form 切片（abs-only）上看**，与概念 5 互证。

> 过程中抓到一个方法论级 bug（已修）：首版把弃权倾向降序当曲线方向，得到的是反选择性曲线，Gate 对比结论恰好反号——同分/排序第二键伪影家族（TOOLS.md 显示层 bug 第 5 例纪律）在自写评估器上的又一实例。**自写指标先跑 oracle 闭式解对拍**。

---

## 关键洞察

1. **每次 A/B 选一个阈值 = 只看 risk-coverage 曲线上一个点**。C448 sweep（none/0.85/0.90/0.95→best=None）的真实读法是"曲线平坦，风险与覆盖率在同点交换"——不是"熵门无用"，而是"该信号在该数据集上无操作点优势"。AURC 无需选阈值即可比较信号质量本身，还规避了阈值过拟合（阈值在 500 题上选择=在测试集上训练）。

2. **abs30 剩余 15 错的攻法由 Calibration≠SP 重新定向**：问题不是"更准的不确定性估计"（校准型改进），而是"更好的排序特征"（SP 型改进）——新的 form-specific 证据特征（时间型锚点缺席检测、gpt4_*_abs 的假前提指纹）把该弃权的题排到低置信区即可，分数的绝对值不重要。

3. **零 LLM 机制门是 amg 的差异化护城河，且有 2025 顶会背书**：AbstentionBench 证明 frontier LLM（含 reasoning 模型）在不可答题上系统性幻觉（−24%），amg 用规则门拿到 abs30 15/30 且近乎零误伤——README/PyPI 发布叙事的现成对标数据（竞品重灾区 vs amg 机制门）。

4. **per-form AURC 是 "form 分类器即配置面" 的度量落地**：全局单阈值在混合曲面上只能拿鞍点（C452/C473 两度实证），把 AURC 按 form 分组计算=每类独立曲线独立操作点，数学上与 amg 现有架构完全同构——不是新机制，是把已有设计放进正确的坐标系。

---

## 下一步行动

1. **C517 候选（最高优先，~30 行 + 测试）**：amg_bench_quality.py 加 `risk_coverage_report()`（AURC/E-AURC/Risk@90%/per-form 分组），移植本笔记实现；与已排程的 full-500 刷新债（C507-C516 累积，C516 HEAD）**合并跑**，产出 amg 首份全量 risk-coverage 基线。
2. **abs30 剩余 15 错场景坐标表**：按 AbstentionBench 五场景分类（gpt4_*_abs / 时间型 → false premises / outdated 映射），决定每簇走 form 门还是排序特征路线（洞察 2）。
3. **对外叙事**：README 弃权章节引用 AbstentionBench −24% 对照；博客候选《Abstention without an LLM》升入队列（与已排 "presupposition failure is an answer" 主题合并候选）。
4. 季度盯梢：AbstentionBench 新数据集 / RLSR 系后续（AURC-as-reward 路线）。

## 来源

- Kirichenko, Ibrahim, Bell, Chaudhuri et al. *AbstentionBench: Reasoning LLMs Fail on Unanswerable Questions*. arXiv:2506.09038, ICML 2025. (FAIR at Meta; cited 118; code: facebookresearch/AbstentionBench, HF: facebook/AbstentionBench)
- Ding et al. *Revisiting the Evaluation of Uncertainty Estimation*. CVPRW 2020. (AURC 是 AUROC/AUPR/AURC 中唯一可靠指标)
- Zhou, Landeghem et al. *A Novel Characterization of the Population AURC*. arXiv:2410.15361, ICML 2025.
- *Aligning Language Models with Selective Prediction* (RLSR). arXiv:2607.03528, 2026-07. (Calibration≠SP; AURC-as-RL-reward 首作)
- *Calibrating LLMs for Selective Prediction*. OpenReview, 2026-07.
- Wen et al. 2025 — 弃权方法综述（AbstentionBench related work 指路）。
- 检索路径：AnySearch academic（Tavily 月配额第 4 天耗尽，432）；arXiv HTML 直读验证。
