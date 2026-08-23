# Multi-Session 答案侧聚合 — LongMemEval "How many" 的确定性路径

**Research #071** | 2026-08-18 20:00 (deep-exploration-evening) | 来源: HEARTBEAT Next dev target "multi_session 答案侧聚合（C467 头号确定性 headroom）"

## 背景与动机

C467 修正地图显示：multi_session evhit **0.955** vs exact **0.007** —— 证据已检回（500/500 有 answer_session_ids），答案侧聚合是唯一失败点。本笔记实证解剖 133 题 multi_session 的题型形态，原型验证零 LLM 聚合路径的真实 headroom，为 amg 答案侧机制族（C456 date resolution / C457 temporal arithmetic 之后的第三代）立项。

## 实证解剖（本地全量数据 /tmp/lme_s.json，非抽样）

133 题 multi_session 的形态分布（AnySearch+本地双源验证）：

| 子型 | n | 答案形态 | 例 |
|------|---|---------|----|
| **COUNT** (`How many`) | 67 | 数字为主 | "How many model kits have I worked on or bought?" → 5 |
| **SUM** (`How much total`/`What is the total`) | ~39 | $金额/数字 | "total money spent on bike-related expenses" → $185 |
| **AVG** | 3 | 小数 | "average age of me, my parents..." → 59.6 |
| **ARGMAX** (`Which...most`) | 2 | 实体 | "grocery store did I spend the most money at" → Thrive Market |
| 其他 What/When | 22 | 混合 | — |

**79.7% (106/133) 的答案是数字或数字开头**。GT 数值分布：COUNT 类集中在小值（≤5 占 31/67），duration 类可到 10+ 周。

关键失败模式（predicted_answer 全是检索文本复读）：amg 当前答案路径把检索回的 assistant 回复原样输出——"How many" 类问题需要的是**跨会话综合**（count distinct / sum / avg），RAG 复读结构性答不了。这正是 Hebb Mind 报告"oracle 检索 GPT-4o 也只到 82%"的另一半：**检索≠聚合，证据齐全≠答案可数**。

## 核心概念 (5)

### 1. multi_session = 聚合查询 (Aggregation Queries over Personal KG)
"How many X have I..." ≈ `SELECT COUNT(DISTINCT x) FROM entities WHERE type~X`；"total money on Y" ≈ `SUM(amount) WHERE category~Y`。这不是新发现——KBQA 领域 20 年前就有 COUNT/聚合逻辑式（VLDB'17 KBQA：复杂问题=二元事实问题组合；AutoQGS 从 SPARQL COUNT 生成 "How many" 问句）。**新语境是：个人记忆图上的聚合，证据是闲聊而非结构化三元组**。amg 的优势恰在结构侧：实体节点天然去重（C445 resolve_entity_variants）、bi-temporal 时间戳支持时窗过滤。

### 2. 计数语义学分四层 (Kostov & Křemen 2013, Count Aggregation in Semantic Queries)
在开放世界假设(OWA)下 distinct-count 有四种解释：basic count（数提及）、semantic count（数推理后的实体）、epistemic count（数"已知存在的"）、semantic tuple count。直接映射到本任务：**数提及≠数物品**——"the tripod I bought" 二次提及不能计 2。原论文用区间语义建模计数不确定性（[lower, upper]）。对 amg 的启示：确定性计数器应输出 epistemic 语义（只数有名字锚点的实体），模糊时输出区间或不 fire——与 C457 "unresolved anchor 不伪造" 同构。

### 3. 事件级去重 (Event-Level Dedup) — 跨会话聚合的核心坑
同一事件会在多个 session 被重述：MCU 马拉松 "in two weeks" 出现在两个 session（05e7_1 讲 22 部 Marvel、05e7_2 复述），朴素跨会话求和得 5.5 周，正确是 3.5。去重键 = (天数, 句中专有名词集合)：Marvel/MCU 两次提及值相同+专名重叠 → 同事件折叠；5-day Yellowstone 与 3-day Big Sur 专名不同 → 两个事件。**这与 C447 的实体跨会话 dedup 是同一个问题的数字版**。语义计数的本质就是"数事件不数提及"。

### 4. 用户回合≠助手回合的证据分层 (Role-Segmented Evidence)
实证发现：金额/时长/数量几乎只在 user turn 首次出现；assistant turn 是复述（"Congratulations on the new kits!"）或泛泛建议（含大量无关数字：列表编号、年份、价格区间）。**只扫 user turn 把噪声数字密度降一个量级**（C456 的 [Speaker] 前缀经验在 LME 的等价物是 role 字段过滤）。原型中 total_sum 精度 1.00 的主要功劳就是这个过滤器。

### 5. Form-Triggered 机制分型 (C456/C457 模式的第三代)
"How many" 不是一种题型而是至少三种机制的容器：**duration-SUM**（"How many days did I spend camping" → 时长抽取+类型过滤+求和）、**entity-COUNT**（"How many model kits" → 具名实例去重计数）、**abstract-COUNT**（"How many projects have I led" → 活动→类目映射，最难，边界在 LLM 领域）。问题形态决定机制（C457 教训），机制不自信就 fall-through 不伪造。这与 KBQA-o1（ICML'25，MCTS 逻辑式搜索）走的 LLM 路线互补：form-triggered rules 吃确定性子集，LLM judge（C462-464 已就位）吃剩余。

## 代码示例 (已验证可运行)

`code/msagg_proto.py` — 零 LLM 三机制原型，oracle 证据会话（answer_session_ids）上实测：

```
FORM              N  FIRED  CORRECT   PREC    HIT
duration_sum     12      7        1   0.14  0.083
entity_count     48     21        4   0.19  0.083
none             61      0        0   0.00  0.000
total_sum        12      4        4   1.00  0.333

OVERALL: 133 questions | fired 32 | correct 9 | hit 0.068 (baseline exact multi=0.008)
```

**exact 0.008 → 0.068（8.5×），全部确定性零 API**。一次迭代即有 total_sum 精度 1.00。正确样本：$185 bike 总支出、17 days 社交媒体休息、projects=2 ×2、museums=2。

设计决策（每条对应一条实证）：
- **oracle 证据测量**：用 answer_session_ids 圈定会话，隔离"聚合机制纯度"——生产管线天花板 ≈ mechanism_hit × evhit(0.955)
- **user-turn-only 扫描**：total_sum 4/4 精度的根基
- **句级 target-family 共现过滤**：camping 题只计含 camping 词族的句子（"7-day road trip" 不算 camping）
- **事件键 (days, 专名集) 去重**：同事件跨会话折叠
- **不 fire 就 None**：无伪造 fall-through（C457 规则），61 题 'none' 类直接放行给现有管线

失败模式（全部可诊断、可修）：
1. **同值不同专名键**：Marvel vs MCU 两次提及被当两事件（6.5 vs 3.5 周）→ 去重键需专名重叠检测而非集合相等
2. **量纲污染**："20 gallon tank" 被当 20 个 tank → 显式计数需单位守卫（gallon/lb/$/mph 黑名单）
3. **具名实例噪声**：fam 句中品牌词（Vallejo/AK Interactive）被计为套件 → 实例模式需"名词紧邻"约束
4. **target 词族过宽**："camping trips" 的 "trips" 放行了 road trip → 时长短语需头词中心性（camping 修饰 trip 时才算）
5. ~~判分器 $5,850 逗号~~ 已修（+1 free，工程教训：判分器和机制同步开发）

## 关键洞察 (4)

1. **"How many" 的答案是"已声明的数字"或"具名实例的基数"，两者都可确定性提取**。67 题 COUNT 中 GT≤5 的有 31 题——用户在会话里亲口数过或列过清单（"three fiction novels - A, B, C"）。检索把清单检回来了，聚合器只需句法重组。这解释了为什么 evhit 0.955 而 exact 0.007：**证据里写着答案的原料，但答案本身从没被任何 turn 说过**——RAG 的"找一段话抄"范式在这里结构性失效，记忆系统的差异化战场在综合。

2. **计数的不确定性应该升为一等公民**（Kostov 区间语义）：5 个套件中 4 个有专名锚点+1 个只有代词提及（"this kit"），诚实的输出是 "4-5" 或 epistemic=4。当前 exact judge 二元判分惩罚区间答案，但 LLM judge（C462-464）可以评"包含真值"。**确定性机制输出区间 + LLM judge 判包含 = 两代答案侧机制的组合拳**，比单押任一边都强。

3. **跨会话去重是聚合侧的"实体解析"**，与索引侧的 resolve_entity_variants (C445) 同构但独立：索引侧按表面变体合并节点，聚合侧按 (值, 事件指纹) 合并计数。C447 的教训（子串污染 love→lovely）在数字域的等价物是**量纲污染**（20-gallon ≠ 20 tanks）——两域共享"词边界+形态匹配"的防御模式，可抽象为 amg 的通用 matching layer。

4. **市场信号：所有记忆系统都在检索侧卷（Hebb Mind R@10 99.2%），答案侧聚合是无人区**。LongMemEval leaderboard 的 judge 口径掩盖了这一点（LLM reader 做了聚合但没人拆开归因）。amg 的 C467 evidence-session coverage 指标恰好提供了归因工具——**"检索非瓶颈，聚合才是"这个论断本身就是博客/README 的差异化叙事**，竞品（TencentDB-Agent-Memory 21.5k★）没有公开这个层面的分析。

## 下一步行动 (3)

1. **[Cycle 468 候选] 三修一加**：①事件去重键升级（同值+专名重叠→同事件，预计 MCU 类全修）②显式计数单位黑名单（gallon/pound/dollar/mph/percent）③具名实例"名词紧邻"约束 → 重跑 oracle 133 题，目标 hit 0.068→0.15+；然后接 amg 真实检索管线（evhit 0.955 天花板）跑 per-question-haystack A/B
2. **[数据侧] duration-SUM 形态扩展**：61 题 'none' 中含 "What is the total/average" 变体，detect_form 增加 What-路由（AVG/ARGMAX 各 3/2 题先做，量小精度高）
3. **[叙事侧] 博客候选第三篇**："检索不是记忆"（when retrieval is not remembering）——C467 evhit 0.955 vs exact 0.007 的归因故事 + 本笔记 8.5× 原型数据，与 "temporal arithmetic without an LLM"（C457）组成零 LLM 答案侧三部曲

## 质量自评

- ✅ 可运行代码：msagg_proto.py 实测 8.5× 提升，失败模式全部可诊断
- ✅ 独到见解：计数四层语义/事件级去重/角色分层证据/聚合无人区叙事，均非检索可得的综合
- ✅ 项目关联：直接立项 Cycle 468，衔接 C445/C447/C456/C457/C467 五代机制谱系
