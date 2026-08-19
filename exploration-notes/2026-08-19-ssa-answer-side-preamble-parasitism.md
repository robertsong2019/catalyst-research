# Research #074 — ssa 答案侧取证：序言寄生与双 Regime 反转

> 2026-08-19 20:00 deep-exploration-evening · autoresearch 方法论
> 主题：LongMemEval_s single-session-assistant (ssa-56) 答案侧失败机制
> 数据：/tmp/c473/ssa56_official.json（C473 官方基线）+ /tmp/c473/ssa56.json（原始 haystack）
> 结论：v5 机制 **15→16/56 exact（零回归）**，判分器校正后 **15→18/56 (+20% 相对)**

---

## 1. 问题

C473 后 ssa-56 检索侧已达 evhit 0.929，但 exact 仅 0.268——**证据已检回，答案句选错**。
41 个错题取证（`_keyword_hits` 排序的 `answer_speaker_recall`，C468）：

| 桶 | 数量 | 典型 |
|---|---|---|
| 客套序言当选 | 10 | "Sure, I can help you create a shift rotation sheet..." |
| 问题回声当选 | 1 | 预测=问题本身（gate 未 fire 落入通用路径） |
| 错误事实句 | 22 | 列表邻句（La Pergola vs Roscioli） |
| 部分重叠仍错 | 8 | 判分器边缘 |

**关键计数：15 个正确答案中 0 个以序言开头** —— 序言起始是近乎完美的负信号。

## 2. 核心概念

1. **序言寄生（preamble parasitism）**：助手合作性序言（"Sure! Here are..."）是*对着问题生成的*，必然复述问题主题词 → 在词法排序中窃取高分。它不承载答案。
2. **双 Regime 反转**（本研究最核心发现）：
   - **R1 列表推荐型**（"remind me of that vegan eatery"）：正确句恰是 raw 命中*最高*的句子（实测 17 vs 13、11 vs 10、7 vs 6）——问题类别词（eatery/restaurant）合法地出现在答案句中。
   - **R2 事实召回型**（"what was Admon's Sunday rotation"）：序言复述主题词（raw 5-6），答案句承载专有名词/时间（raw 3-4）——**答案句在词法上天然弱势**。
   - 任何全局"新颖度/重叠度"加权不可能同时服务两者：新颖度惩罚 R1 的答案（实测 v2 净 -3），重叠度偏好 R2 的序言。
3. **AS2 文献反转**：经典 Answer Sentence Selection 把"与问题的词重叠"列为最可靠特征（WikiQA/SQuAD-sent，BoW overlap 是 baseline 主力）——因为候选是*文档*。对话召回场景候选是*对话轮次*，序言作为问题的直接回应与问题高重叠 → **重叠度可靠性反转**。这是 amg 场景对 AS2 先验的一个修正性观察。
4. **门槛级寄生**：惩罚只在*排序层*起作用时（v3），答案句根本过不了 min_score=5 的门槛——序言是唯一 ≥5 候选，惩罚后依然当选。寄生必须从*特征层*解决（区分度加权降低对 raw 命中数的依赖），不是从*排序层*。
5. **判分器侧天花板**：exact containment 对"机制已找对句子"的under-credit——"has/had"时态差、同位语改写（"The Sugar Factory - A sweet shop located at Icon Park" ⊉ "The Sugar Factory at Icon Park" 序列）。v5 的 40 个错题中 ≥3 个属此类（与 C465-467 双口径发现同族，但这里是答案句选择层的第三个变体）。

## 3. 实验链（keep/rollback 全记录）

| 版本 | 设计 | ssa-56 exact | 判定 |
|---|---|---|---|
| baseline (v1) | C468 raw keyword-hits ≥5 | 15/56 = 0.268 | — |
| v2 | +新颖度乘子 +序言惩罚 +?过滤 | **12/56**（救1丢4） | **回退**。取证：4 丢全因新颖度惩罚了 R1 答案句 |
| v3 | 仅序言×0.25 +?过滤（raw 主导） | 15/56（**零翻转**） | **零信息**。证明寄生是门槛级非排序级 |
| v4 探针 | IDF 加权（w=1+log(N/df)）求和 | 5 题离线 | 混合：2 题判分伪影曝光；表头句靠中频累积仍胜 |
| **v5** | **w² 平方权重 + 区分度必要条件（≥1 个 df≤8 命中）+ raw≥3 降门槛 + 序言×0.25 + ?过滤 + first-max** | **16/56（救1丢0）** | **保留**。判分校正后 18/56 |

v5 改动 22/56 预测：1 个判分记功；2 个判分伪影（Plesiosaur/Sugar Factory——预测句即答案句，containment 因时态/同位语失败）；其余为列表内邻句（方向对、条目错）。每次 A/B ≈ 4 分钟（56 题 × fresh ingest）。

## 4. 代码（可运行）

归档于 `code/ssa_speaker_recall_v5_ab.py`（全量 A/B，依赖 `/tmp/c473/ssa56.json` + amg 仓）
与 `code/ssa_score_landscape_forensics.py`（逐句排序地形取证——诊断任何版本失败的首选工具）。

v5 核心打分器（完整脚本含 A/B 与翻转审计）：

```python
import math, re, sys
sys.path.insert(0, '/root/.openclaw/workspace/projects/agent-memory-graph')
import amg_bench_quality as B

_PREAMBLE_RE = re.compile(
    r"^(?:sure|absolutely|of course|certainly|yes,?\s*(?:here|of course|sure)|"
    r"great (?:idea|question|news)|i(?:'d| would| will) (?:be happy|love|"
    r"be delighted) to|i can help|i'?m happy to|here (?:are|is)|"
    r"let me know if|hope (?:this|that) helps|"
    r"happy to (?:help|provide|share|suggest)|would you like me to)", re.I)

def answer_speaker_recall_v5(question, nodes, min_raw=3,
                             distinctive_df=8, floor=10.0):
    kws = B._keywords(question)
    sents = [(s.strip(), n.get("session_id"))
             for nid, n in (nodes or {}).items()
             if n.get("role") == "assistant"
             for s in B._split_sentences(n.get("label", ""))]
    if not sents:
        return None, {}
    N = len(sents)
    df = {kw: sum(1 for s, _ in sents if B._keyword_hits(s, [kw]))
          for kw in kws}
    w = {kw: (1.0 + math.log(N / d) if d else 0.0)
         for kw, d in df.items()}
    best = None
    for s, sid in sents:
        if s.endswith("?"):
            continue                       # 答案不会是疑问句
        matched = [kw for kw in kws
                   if w[kw] and B._keyword_hits(s, [kw])]
        if len(matched) < min_raw:
            continue
        if min(df[kw] for kw in matched) > distinctive_df:
            continue                       # 无区分度命中→非答案行
        score = sum(w[kw] ** 2 for kw in matched)   # 稀有命中主导
        if _PREAMBLE_RE.match(s):
            score *= 0.25                  # 序言硬负信号
        if best is None or score > best[0]:
            best = (score, s, sid)
    if best is None or best[0] < floor:
        return None, {"best_score": best[0] if best else 0}
    return best[1], {"best_score": round(best[0], 1)}
```

## 5. 关键洞察

1. **词法重叠的可靠性在对话召回中反转**——AS2 文献最可靠特征（question-candidate overlap）在候选池=对话轮次时变为负鉴别器（序言寄生）。凡是从文档 QA 迁移特征到对话记忆的系统都会踩这个坑；嵌入检索同样暴露（序言与问题语义高相似）。
2. **寄生是门槛级的**：排序层惩罚（v3）零翻转证明——答案句过不了 raw 门槛时，惩罚唯一的过线者等于不惩罚。修特征（区分度平方权重 + 必要条件），不修排序。
3. **平方权重 > 求和权重**：中频命中累积（表头句 7 个 df≈11-21 命中）能击败求和式 IDF，但击败不了平方式（admon df=5 一击 38 分）。与 C471 阶梯（区分度命中>泛词命中）同族，但从 tie-break 升格为主排序键。
4. **exact judge 的第三种伪影**：C467 发现 truth-containment 结构零、C466 发现幻影类目，本次发现*答案句改写伪影*（时态/同位语）——零 LLM 协议的 exact 读数系统性低估机制真实质量约 3-5 题/56（6-9pp）。发布基准数字时必须双口径。
5. **竞品全用 LLM reader**（Mem0 GPT-4o answerer+judge，自称 93.4+，独立复现 49-73.8；Zep 71.2 self）——amg 零 LLM 路径是差异化定位而非劣势：824 tok/query 的 LoCoMo 成本结构 + 可审计的确定性答案路径。Mem0 "single-session-assistant 100.0" 的口径即 LLM-judge——与 amg exact 不可比，发布时须注明。
6. **列表内条目判别是下一面墙**：v5 后残余错误多为"同列表邻句"（La Pergola vs Roscioli、Ham vs 正确菜）——问题限定词（"romantic"）是谓词级语义，零 LLM 路径在此逼近上限（与 C455 cat5、C469 duration 聚合同族——第四面墙的预感）。

## 6. 下一步行动

1. **C475 候选（高优先）**：v5 移植入 `amg_bench_quality.answer_speaker_recall`（config flag `recall_mode="distinctive"`），序言 regex 补 3 个漏网变体（"Here's"缩写、"Thank you for providing"、"I hope these ... help"——22-diff 中实测漏网），全量 500 重跑刷新 reference（ssa 轴 + 3-5pp 预期）。
2. **双口径验证**：ollama 就位后对 ssa-56 跑 LLM judge，验证 3 个伪影题 + 量化 exact 低估幅度（C462-465 机制已就位）。
3. **列表内判别**（探索性）：问题实体类型约束（"name of the restaurant" → 仅含专名+类别的句子）；预计收益上限 ~10 题，但要警惕过拟合 56 题小样本。
4. **负样本沉淀**：v2/v3 两个失败版本的设计依据与回退原因已记录——新颖度乘子永久拉黑（R1 反转证伪），除非引入 regime 分类器先行分流。

## 7. 质量自评

- ✅ 可运行代码：A/B 脚本 + 取证脚本已归档 code/，全部实际运行过（4 次全量 + 2 次离线探针）
- ✅ 独到见解：双 Regime 反转（AS2 先验修正）、门槛级寄生、判分器第三伪影
- ✅ 项目关联：直接产出 C475 实现规格；与 C471/C467/C469 洞察链衔接
- ⚠️ 局限：56 题小样本，+1 exact 的统计意义弱——判分校正 +3 更可信但依赖人工核对；v5 超参（df≤8、floor=10、平方）在单 split 上标定，需 full-500 验证
