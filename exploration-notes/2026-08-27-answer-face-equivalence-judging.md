# Research #090 — Answer-Face 等价判分：exact 与 LLM judge 之间的确定性中间层

**日期**: 2026-08-27 20:09 (deep-exploration-evening)
**触发**: HEARTBEAT Next dev targets — C519 解锁 3 题暴露 answer-face 转述失配（标注"高风险勿轻动"→ 研究先行）；短语级 restrictor（table tennis/vintage films）方向困惑
**状态**: ✅ 完成 — 文献栈 4 篇 + 零依赖原型 26/26 全绿

---

## 一、问题定义

amg 的 exact_judge（词边界 + 屈折形态匹配器，C447）在 C517 达到 full-500 exact 0.444，但存在两个方向的失配：

1. **false-fail（漏给分）**: 答案语义正确但表面形式不同 — "January 5, 2023" vs "Jan 5th 2023"、"two hours" vs "120 minutes"、"$56,355" vs "56355 dollars"。C519 解锁的 3 题即此类。
2. **false-pass（错给分）**: 松弛判分引入的伪等价 — "tennis" vs "table tennis"（短语级 restrictor 的核心困惑：查询"table tennis"时命中"tennis"算不算对？）。

LLM judge（C462-464，mock-llm 0.318@C499）覆盖语义面但成本高且不可复现。问题：**能否用确定性规则层吃掉大部分表面形式失配，把 LLM judge 留给真正的语义题？**

## 二、文献栈（4 篇核心）

### 1. Bulian et al., EMNLP 2022 — "Tomayto, Tomahto. Beyond Token-level Answer Equivalence"（被引 152+）
- 首个对 token 级等价度量的系统性数据驱动分析，**23k 人工判分**（SQuAD 多系统候选）
- **核心贡献：答案等价（AE）的不对称定义** — 接受"等价于参考 **或优于参考**"的答案。candidate ⊇ reference（更具体）= 给分；candidate ⊂ reference（更弱/更泛）= 不给分
- 量化 F1 两个结构性缺陷：**伪渐进性**（0.7 分不代表 70% 对）与**问题盲**（同样的 token 差异在不同问题下等价性完全不同——"Paris" vs "Paris, France" 在 where 题等价、在 capital 题可能不等价）
- BEM（BERT 分类器，question+reference+candidate 三输入）显著优于 F1；应用：最小准确预测集缩减 2.6×
- 数据集开源：google-research-datasets/answer-equivalence-dataset；HF 复现 kortukov/answer-equivalence-bem

### 2. Li et al., EMNLP 2024 (PEDANTS) — "Cheap but Effective and Interpretable Answer Equivalence"（arXiv:2402.11161）
- 用 **Trivia 社区人工判分 rubric** 训练/评估规则式判分器（PEDANTS：Pipeline for Extraction and Detection of ANswers）
- 结论：**规则式 + 问题类型条件化**判分比 EM 和 BERTScore 更稳定、可解释、零推理成本——"cheap"是合法设计点
- 与 amg 哲学同构：零依赖、确定性、可单测。问题类型条件化 ≈ amg 的 form-gated 哲学在**判分侧**的镜像
- 包：github.com/zli12321/qa_metrics

### 3. Ho Thi et al., GEM@ACL 2026（arXiv:2504.11972）— LLM-as-a-Judge for Extractive QA at Scale
- 四数据集 × 多 LLM 家族 × prompt 变体系统研究
- **LLM judge 与人工相关性 0.85 vs EM 0.22 / F1 0.40**（全面碾压 token 度量）
- **分答案类型异质性：数字类答案最好，复杂实体（job title 类）最弱**
- 反直觉发现：无 self-preference bias（同模型自答自判不偏向）；zero-shot context-free judging 往往最好；prompt 措辞影响小

### 4. LongMemEval（Wu et al., ICLR 2025，arXiv:2410.10813）— amg 的目标基准
- 500 题、五能力（含 abstention——amg C448-C519 弧线正是挖的这条）
- 官方评测走 LLM judge 口径（amg C454 已内部核实："LLM judge 才是 leaderboard 可比口径"，kupdate 检索 hit 1.0 但抽取协议 0.0 的教训）
- **推论：amg 的 exact 0.444 与 leaderboard 不可直接比——中间层的价值不只是提分，是把 exact↔llm gap 分解为"normalization 可救"vs"真语义需判"两部分**

## 三、核心概念

1. **不对称等价（asymmetric equivalence）**: 判分方向不是"相同"而是"等价或改进"。candidate 比参考更具体/信息更全 → 给分（IMPROVES）；candidate 比参考更弱/更泛 → 不给分（PARTIAL）。这一条直接回答短语级 restrictor 的方向困惑：**"tennis" 作为 "table tennis" 的候选是更弱的答案（PARTIAL，不给分），反过来 "table tennis" 作为 "tennis" 的候选是改进（IMPROVES，给分）**。
2. **问题类型条件化（question-type conditioning）**: 同样的 token 差异在不同问题类型下等价性不同（F1 的问题盲缺陷）。判分器必须先路由问题类型（date/number/entity）再用类型专属规则——与 amg 检索侧 form 分类器（C473"form 分类器即配置面"）完全同构，只是从检索搬到判分。
3. **判分谱系（judging spectrum）**: EXACT → NORM_EQ（归一化等价）→ IMPROVES（不对称包含）→ PARTIAL → INCOMPATIBLE → NEEDS_JUDGE。前三者计分，后三者不计。**NEEDS_JUDGE 是一等公民判决**——把"确定性层判不了"显式转交上层（LLM judge），而不是假装判了。这是 abstention 弧线（silence ≠ 0 claim，C514）在判分侧的延续：**判分器也需要诚实弃权**。
4. **单位语义域（unit semantic domains）**: 数值答案的等价性 = (值, 单位域) 联合匹配。时间单位规范化到秒（2 hours ≡ 120 minutes）、货币符号必须一致（$5 ≢ 5 euros）、距离单位不换算（5 miles ≢ 5 km）。值相同单位不同 ≠ 等价——amg C483 counting 单位纪律的判分侧对应物。

## 四、可运行代码

**文件**: `code/answer_equiv_judge.py`（零依赖 Python 3.10+，~300 行）

```python
from answer_equiv_judge import judge
judge("What sport does he play?", "tennis", "table tennis")   # ('PARTIAL', {...})      不给分
judge("How long did it take?", "two hours", "120 minutes")     # ('NORM_EQ', {...})      给分
judge("How much did it cost?", "It cost $56,355", "56355 dollars")  # ('IMPROVES', ...)  给分
judge("How much?", "$5", "5 euros")                            # ('INCOMPATIBLE', {...}) 不给分
judge("Who planned it?", "she planned it herself", "Rachel")   # ('NEEDS_JUDGE', {...})  转交 LLM
```

三层架构：T0 exact strip → T1 归一化 multiset 相等（数字词/序数/货币/月份折叠/敬称/缩写）→ T2 问题类型守护的不对称检查（数值签名 / 日期元组 / 内容词包含）。

**实测 26/26 全绿**（2026-08-27），用例覆盖 amg 实际失配形态：
- 17 credit：日期折叠（Jan 5th 2023 ≡ January 5, 2023）、时间规范化（two hours ≡ 2 hours ≡ 120 minutes）、货币吸附（$56,355 → "56355|usd"）、敬称（Dr. ≡ Doctor）、缩写（NYC ≡ New York City）、排序不变性（23rd of March 2019 ≡ March 23, 2019）
- 9 non-credit：近失陷阱（tennis vs table tennis=PARTIAL）、数值差（7 vs 17）、货币冲突（$ vs euros）、距离单位冲突、4 个 NEEDS_JUDGE 守卫（代词 coref、相对时间 yesterday/last summer、频率副词 once a week vs weekly）

调试中修掉的 5 个真 bug（每个都是 amg 生产移植时的预演）：货币符号被 tokenizer 当分隔符吞掉（$5 失去币种）；日 regex `\d+` 吞 4 位年份（"March 2019" 解析出日=2019）；"d of month" 回看不穿 "of"；residue 含已被签名消费的单位词（hours/minutes 误判 IMPROVES）；"what day" 未路由 date 型。

## 五、关键洞察

1. **判分与作答是同一问题的两面（镜像律）**：Bulian 的问题盲缺陷、PEDANTS 的问题类型条件化、amg 的 form-gated 检索（C473）是同一个原理的三次独立发现——**上下文（问题类型/form）决定等价语义**。amg 已有 12 个 counting form 分类器（C515）可直接复用为判分侧的类型路由器，`judge_semantic()` 几乎是免费的架构对齐。
2. **不对称性回答了 restrictor 的方向问题**：短语级 restrictor（HEARTBEAT 待办）此前只有"table tennis/vintage films，census 先行"的模糊方向。现在有判分原则：**restrictor 生成的候选必须满足 cand ⊇ ref**——向具体方向收窄合法，向泛化方向发散不合法。这与 C518 E3 所有格收窄（N-gallon 按"所有格收窄而非泛化名词复合"）不谋而合，是同一条原则的两次独立命中。
3. **LLM judge 不是均匀更强的（分类型读数）**：Ho Thi 2026 的数字题强/复杂实体弱分布，恰好映射 amg 的基准构成——counting/duration/temporal 家族（数字答案）的 exact↔llm 分歧可放心用规则层仲裁，ssa/role 面（复杂实体）的分歧必须留给 LLM。**C465 calibration_by_category 的分歧读数应该按答案类型分层，而不是整体读一个数**。
4. **NEEDS_JUDGE 是判分器的诚实弃权**：确定性层的最优策略不是"判对所有"而是"把能判的判对 + 把判不了的显式交出去"。代词 coref、相对时间锚定、频率副词同义——这些 amg 机制侧已有部分能力（C456 date grounding、C482 非对称信任门），判分层可以调机制侧的解析结果而非自己重新解析。**判分层与机制层共享锚定基础设施**，避免第三套日期解析器。
5. **exact 0.444 的水位里藏着一层"免费"提升**：T1 归一化层（数字词/序数/月份折叠/货币吸附）处理的形态正是 LME haystack 转述失配的主要形态（C519 3 题 + C465 kupdate 12 rescue 题都是这个形态）。与 PEDANTS 的可发表级先例对照，这个中间层本身就是 README 的一个卖点：**三分支判分（exact/semantic/llm）+ 判分器弃权**是竞品（LightHaru/TencentDB 系）没有的评估叙事。

## 六、下一步行动

1. **C520 候选（最高优先）**: `judge_semantic()` 落地 `amg_bench_quality.py` — 移植三层架构，复用 12-form 分类器做类型路由；先在 C519 解锁 3 题 + C465 kupdate 12 rescue 题上 A/B（llm-judge 标签当 oracle），预期 rescue 8-15 题且零 false-pass（有 $5≠5euros/7≠17 守卫）。
2. **短语级 restrictor 设计约束更新**: 生成方向必须 cand ⊇ ref（不对称原则）；"tennis→table tennis" 查询扩展合法、"table tennis→tennis" 非法。
3. **判分 rubric 固化**: 把 amg 判分规则写成显式 rubric 文档（对齐 PEDANTS 的社区 rubric 叙事），作为 README/发布材料——"deterministic judge with honest abstention"。
4. **防御性验证**: NEEDS_JUDGE 率本身是指标——如果 semantic 层 NEEDS_JUDGE > 15%，说明规则覆盖不足，宁可少 rescue 也不放宽（PEDANTS 稳定性教训：宽松规则层比没有规则层更糟）。

## 七、质量自评

- ✅ 可运行代码：26/26 自测全绿，零依赖，amg 生产可直接移植
- ✅ 独到见解：不对称等价 × form-gated 判分的镜像律（两个领域独立收敛）；NEEDS_JUDGE=判分器弃权与 abstention 弧线的统一
- ✅ 项目关联：直连 C519 解锁题、C520 候选、短语级 restrictor、C465 calibration 重读数、README 发布叙事
- 局限：日期仅覆盖月名模式（无 "5/6/2023" 歧义日期、无相对日期解析——机制侧 C456/C482 已有能力，判分层应调用而非重写）；ACRONYM 映射仅 NYC/USA/UK 三条示意（amg resolve_entity_variants C445 是真字典）

## 参考

- Bulian et al. 2022, aclanthology.org/2022.emnlp-main.20 · dataset: github.com/google-research-datasets/answer-equivalence-dataset
- Li et al. 2024 (PEDANTS), arXiv:2402.11161 · pkg: github.com/zli12321/qa_metrics
- Ho Thi et al. 2026, arXiv:2504.11972 (GEM@ACL) · code: github.com/Alab-NII/llm-judge-extract-qa
- Wu et al. 2025 (LongMemEval), arXiv:2410.10813 (ICLR)
- 检索路径：Tavily 432 配额错误第 4 天 → AnySearch academic (mcporter) + web_fetch 降级，全程零阻塞
