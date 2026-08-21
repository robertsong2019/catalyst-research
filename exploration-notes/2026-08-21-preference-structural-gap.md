# Research #080 — preference 30q 结构性缺口取证：词法不可达 + 生成原生类目的完整判决

> 2026-08-21 20:28 deep-exploration-evening · autoresearch 方法论
> 主题：HEARTBEAT Next dev targets「preference 30q 0.000 结构性缺口取证（先确认检索侧 vs 答案侧，evhit 0.567 六类最低）」
> 数据：/tmp/lme_s.json（277MB 全量）+ /tmp/c481/lme_s_full500_c481.json（C481 官方 reference）
> 代码：`code/preference_profile_scan.py`（自包含，6 臂 + 决定性诊断，~3min 含加载）

---

## 1. 结论速览

**判决：single-session-preference 是端到端生成原生类目——检索桥与答案侧双双超越零 LLM 机制的可表达范围。** 这是继 C455（LoCoMo cat5 名字拓扑）、C467（preference hit 结构零）之后第三面零 LLM 墙，且这次是全类目级的。

| 面 | 证据 | 数字 |
|----|------|------|
| 度量伪影 | GT = 合成元描述，字面不在 haystack | 26/30 GT 以 "The user would prefer…" 开头；exact/hit 结构性 0 |
| 答案侧 | echo 协议答非所问（回放建议文本 ≠ 用户画像） | correct_llm 1/30；answered 30/30 弃权 0 |
| 检索桥 | 问题=类别词（"show or movie"），证据=具体实体（"stand-up comedy on Netflix"） | **答案会话 unique 词法 best 仅 4/30**（词干归一零增益） |
| 答案重建 | 即使 oracle 给对会话，GT 实体也不可抽取 | GT 实体 100% 字面在答案会话：**0/30**；≥70% 仅 7/30 |
| Recency | 无强时序先验 | 答案会话位置 median 0.66，末 20% 仅 8/30 |

## 2. 六臂实验全表（session 定位 / 实体覆盖）

| 臂 | 设计 | top-k session hit | ent-cov≥0.7 |
|----|------|-------------------|-------------|
| A 生产窗口 | C481 reference answer_session_hit | **17/30** | 0/30 |
| B 全扫+词重叠 | 全 haystack 用户行按问题词重叠排序 | 11/30 | 0/30 |
| C +marker 门 | 仅第一人称偏好陈述行 | 6/30 | 0/30 |
| D +实体加成 | C + 大写实体命中 0.5 加分 | 8/30 | 0/30 |
| E 两级法 | 会话级主题聚合定位→会话内 marker 抽取 | 4/30 (top1) | 0/30 |
| F 上界诊断 | 答案会话=唯一词法最优会话 | **4/30** | — |

**负结果链**：marker 门损害排序（11→6，偏好行常非主题重叠行）；两级聚合更差（E 4/30——问题词在会话级也近乎零重叠）；所有词法变体的实体覆盖全部 0/30。**生产窗口 17/30 已高于任何朴素词法上界的一半以上**，其信号来自 keyword 加权+全消息（含 assistant 回声），词法侧已接近自然极限。

## 3. 外部证据（Tavily 配额已恢复）

- **LongMemEval 原文**（arXiv 2410.10813v2）：single-session-preference 定义为 "utilize the user information to **generate a personalized response**"——按设计就是生成任务；题目由 GPT-4o 提议+人工筛（yield ~5%）。**论文自认 judge 在 preference 与 abstention 上与人类专家偏差最大**（open-ended），总体 agreement ≥90% 但此类目最弱。
- **SOTA 也是 preference 最弱**（mnemoverse 两跑）：0.20 与 0.565，同期 ssu 0.94/ssa 0.94/KU 0.82——类目级普遍困难，amg 的 0.03 落后但绝非孤例。
- **检索桥可被轻量嵌入解决**（rohitg00/agentmemory 纯检索实测）：preference R@5 **BM25-only 60.0% → +all-MiniLM-L6-v2 向量 83.3%**（全类目最低升幅最大）。384 维本地小嵌入（~90MB）≠ LLM——ollama/qwen 不是必要条件。
- 判分口径警示：mnemoverse 两跑 overall 0.62 vs 0.79（judge prompt 未冻结）——未来 preference 计分必须钉 judge prompt hash。

## 4. 核心概念

1. **合成元描述 GT**（synthesized meta-description）：GT 不抽取自语料而是从用户画像生成（"The user would prefer responses that…"）——truth-containment 类度量结构性归零，判分必须走 LLM judge。
2. **类别-实体词汇鸿沟**（category-entity vocabulary mismatch）：问题用品类词（hotel/show/activities），证据陈述具体品牌/媒介（Adobe Premiere Pro、stand-up comedy）——方向与一般 QA 相反：一般 QA 问实体找实体，preference 问类别找实体。
3. **两级定位-抽取范式**（locate-then-extract）：本类目中两级法失效的根因是第一级（词法定位）就不可行——范式没错，缺的是语义相似度这一层黏合剂。
4. **嵌入 ≠ LLM**：384 维 MiniLM 是检索侧黏合剂（R@5 +23pp），答案侧合成才是 LLM 边界。把两者混为一谈会高估解锁成本。
5. **结构零的第三案**（structural zero, case 3）：C455 cat5（谓词级语义）、C467 preference hit——度量在任务定义下不可能触发，读数为伪影而非能力缺口。

## 5. 代码

`code/preference_profile_scan.py` —— 六臂 + 决定性诊断一体（`python3 preference_profile_scan.py [--data /tmp/lme_s.json]`），3 分钟内复现本笔记所有数字。核心两段：

```python
# 检索桥上界诊断：答案会话是否为唯一词法最优（F 臂）
scores = [(len(qt & bag_of_user_terms(sess)), sid) for sid, sess in sessions]
best = max(s for s, _ in scores)
winners = [sid for s, sid in scores if s == best]
reachable = len(winners) == 1 and winners[0] in ans_ids  # → 4/30：词法不可达

# GT 实体答案会话包含度（答案协议可行性）
ge = gt_entities(q['answer'])                       # 剥 "The user would prefer…" 模板词
cov = sum(e in answer_session_text.lower() for e in ge) / len(ge)
# → 100% 包含 0/30：oracle 会话也抽不出 GT 实体
```

## 6. 关键洞察

1. **词法不可达有精确度量**：unique-lexical-best 4/30（F 臂）是类别级词汇鸿沟的单数字判据——比"命中率低"强一个数量级的表述，且可移植到任何类目/任何数据集做"零 LLM 可行性预检"。
2. **marker 噪声定律**：第一人称偏好标记在长会话里 60-80 命中/会话（"I'm thinking of" 到处都是）——存在性≠可辨别性；证据存在只排除"数据缺失"假说，不构成检索可行性。
3. **度量伪影三连的规律**：三个结构零（C455 cat5/C467 hit/本例 exact）全部出现在"GT 与机制表示空间不同构"处——判分器选择前先问 GT 是抽取物还是合成物。
4. **嵌入式检索是 amg 哲学兼容的最短路径**：外部实测 BM25 60%→+MiniLM 83% R@5；amg 的 form 分类器即配置面（C473）天然支持"仅 preference/ssa form 启用嵌入通道"的可选 side-channel——不需要放弃零 LLM 主干。
5. **SOTA 弱区=叙事机会**：preference 是全场最弱类目（SOTA 0.2-0.57），amg 若以"嵌入通道+诚实弃权"拿到 0.3-0.5，即在该类目与 SOTA 同段位——README 差异化的新素材。

## 7. 下一步行动

1. **C490 候选 A（零 LLM 止损，~20 行）**：preference form-gate（recommend/suggest/any tips/advice/what should/any ideas → 30/30 命中本类目）+ 检索侧无强词法信号（F 臂 < 50%）→ 诚实弃权 "no locatable preference in memory"。30 错答→30 弃权：exact 不涨但消灭幻觉答，abstention_rate 与 honest-attribution 叙事对齐（C448 熵门答案侧推广的第三实例）。需 form-gate 零劫持验证（500 全量其余 470 题）。
2. **C491+ 候选 B（嵌入 side-channel）**：可选依赖 `sentence-transformers`（all-MiniLM-L6-v2，本地 90MB），仅 preference/ssa form 触发语义检索通道；外部数据预期 R@5 60→83%。架构=amg 可选加速器（同 OTel 可选依赖先例）。
3. **ollama 解锁联动**：答案侧合成与 LLM judge 双双 gate 在 `ollama pull qwen2.5:7b`（与 GraphRAG-Bench 双首跑①、cat5+多跳同一 blocker）——一次解锁四条线。
4. **判分纪律**：任何后续 preference 计分先钉 judge prompt（C462-464 的 judge_llm 已有 prompt 常量，加 hash 记录）。

## 8. 质量自评

- 可运行代码 ✅（六臂一体，3 分钟复现全部数字）
- 独到见解 ✅（unique-lexical-best 判据 / marker 噪声定律 / 度量伪影三连规律 / 嵌入≠LLM 边界切分）
- 项目关联 ✅（直接映射 C490 弃权门与 C491 嵌入通道两个候选；README 差异化素材）
- 方法论对齐 ✅（明确指标、快速循环、负结果保留——F/E/C 三臂负结果全部入笔记）
