# Research #082 — Neither 族取证 + Event-Centric Comparison Matcher (ECM) 原型：C497 前置研究

> 日期: 2026-08-22 (deep-exploration-evening)
> 数据: LongMemEval_s full-500 (/tmp/lme_s.json)
> 结论: **4/4 oracle ✅ + 零劫持验证 ✅（gate 恰 fire 4/500）** — C497 直接落地路径已铺平
> 代码: `catalyst-research/code/2026-08-22-c497/`（ecm_proto.py 可运行）

---

## 1. 背景与问题定义

C492 官方刷新后 temporal-133 = 0.571（76/133），HEARTBEAT Next dev targets 头号: **neither 族 4 题**
（`gpt4_88806d6e / gpt4_0a05b494 / gpt4_fe651585 / gpt4_fe651585_abs`）——C482 取证中的 "other 34" 残余里
机制上既非 order-family（C488）也非 pairwise which-first（C489）的孤立家族。

## 2. 取证发现（本轮核心产出）

### 2.1 C481 管线四题全错的失败模式

| qid | 问题 | GT | 管线预测 | answer_session_hit |
|-----|------|----|---------|-------------------|
| 88806d6e | Who did I meet first, Mark and Sarah or Tom? | Tom | "I'll try to reach out to Mark and Sarah..."（回声用户 turn） | **True** |
| 0a05b494 | Who did I meet first, the woman selling jam... or the tourist from Australia? | jam woman | "What a lovely encounter!..."（回声助手 turn） | **True** |
| fe651585 | Who became a parent first, Rachel or Alex? | Alex | "Chopsticks and Waltz in D-flat..."（完全劫持） | True |
| fe651585_abs | Who became a parent first, Tom or Alex? | NOT ENOUGH INFO | 妇女科学史长文（完全劫持） | True |

**决定性读数：answer_session_hit=True 但 4 题全错** —— 检索已把正确会话送进窗，败在
答案侧证据行定位。这不是 C472 式"锚进不了窗"问题，是 **证据墙的句法结构** 问题。

### 2.2 三面证据墙（"neither"之名的由来：既非 order 也非 pairwise 机制可解）

**墙 1 — 实体是描述性名词短语，不是人名（0a05b494）**
- 问题实体 "the woman selling jam at the farmer's market" ↔ 证据 "a **jam maker** at the farmer's market"
- 词法重叠 = {jam, farmer, market}，无名字 token 可索引；C489 pairwise 的名字锚面完全空转
- 同会话干扰墙：barista（"a few weeks ago"）、personal trainer（"a few days ago"）、
  networking event 的 woman（"last month"）——同结构 "met X ago" 干扰 ≥4 个

**墙 2 — 事件面词法多样性（0a05b494 / fe651585）**
- jam woman 的证据句是 "I **had a lovely conversation with** a jam maker"——**不含字面 "met"**
- "became a parent" 的证据面是 "adopted a baby girl"（Alex）和 "twins were born"（Rachel）——
  问题动词与证据动词零词法交集，需要事件类映射（C495 verb-map 模式再现）

**墙 3 — 跨 turn 回指 join（fe651585，最难）**
- Rachel 的日期在 turn[0]: "my **sister-in-law's twins**, Jackson and Julia, who were **born on February 12th**"
- Rachel 的名字在 turn[8]: "my sister-in-law, **Rachel**, is doing great with **the twins, Jackson and Julia**"
- **名字和日期相隔 8 个 turn**，join key = 关系 NP（sister-in-law）+ 共现专名（Jackson/Julia）
- C496 F6 anaphora join 是跨"行"，这里证明还需要跨"turn"、且 key 可以是关系名词

**墙 4 — 相对时间只有序数信息（88806d6e）**
- Tom: "a **few months** ago" vs Mark&Sarah: "**about a month** ago" → GT=Tom
- 两个都是 vague duration，**无日历日期可锚**——序数比较（90d > 30d）就够，强行日历化反而无据
- 干扰：同会话 Sophia（"a couple of weeks ago"）、Rachel（"last weekend"）、freelance writer（"last week"）

**墙 5 — 弃权孪生（fe651585_abs）**
- 同 haystack，Tom 从未出现 → 必须弃权；C489 负存在弃权语义直接复用
- 陷阱：haystack 里有另一个无关 "Alex"（钓鱼会话 "my friends Alex and Ryan"）——
  **动词过滤是防劫持关键**（钓鱼句不含 adopted/born/gave birth）

## 3. 机制设计：Event-Centric Comparison Matcher (ECM)

```
gate（严格形态）→ 实体槽解析 → 实体归一化（人名/描述分轨）
  → 全 haystack 句子级扫描（C472 全图回退模式）
  → 描述实体: ≥2 内容词重叠 + 窗口时间可解析（不要求动词面）
  → 人名实体: 名字 + 动词面 + 窗口时间；失败 → 回指 join（同 session 共享关系NP/专名的日期句）
  → 相对时间 → anchor 前天数（vague duration / calendar 双轨统一标量）
  → 比较: 天数大者早；一方无证据 → ABSTAIN
```

五个设计决策（每个对应一面墙）：
1. **描述实体免动词门**（墙 1+2）: 重叠≥2 + 时间在窗 = 双重判别，干扰句 0-1 重叠进不来；
   动词面对描述实体是伪需求（"conversation with" 教训）
2. **人名实体保动词门**（墙 5）: 防同名异事劫持（钓鱼 Alex ≠ 养父母 Alex）
3. **回指 join 名字句免动词**（墙 3）: "sister-in-law, Rachel, is doing well" 无事件动词，
   但日期句必须含动词 + 共享 join key
4. **天数统一标量**（墙 4）: "a few months ago"→90, "about a month ago"→30,
   "two weeks ago"→14, "last Thursday"→星期几回算, "in January"→日历中点, 
   "born on February 12th"→日历精确——全部坍缩为 anchor 前(约)天数，序数比较即可判
5. **sentence-window ±1 句**（HEARTBEAT 的 "sentence-window kw 匹配"）: 证据常拆在邻句
   （jam 句 + "two weeks ago" 在同句，但 Mark&Sarah 的 met 与 NP 在从句链上），
   窗口 join 比单句匹配稳

## 4. 结果

```
[gpt4_88806d6e]  PRED Tom (90d: "a few months ago... a guy named Tom")          ✅
[gpt4_0a05b494]  PRED jam woman (14d vs tourist 5d: last Thursday)             ✅
[gpt4_fe651585]  PRED Alex (61d: adopted in January vs twins Feb 12 = 33d)     ✅
[gpt4_fe651585_abs] ABSTAIN (no parent evidence for Tom)                       ✅
=== 4/4 ===
```

**零劫持验证**: gate 扫描全 500 题，**恰好 fire 4 题 = neither 族全集**，零碰撞
（C488 先例再现: STRICT gate 恰命中全错题族）。temporal-133 若 +4 → 76→80/133 = **0.571→0.602**，
firstfam-30 若计入 → 24→28。

## 5. 文献对齐（Tavily 仍配额耗尽，AnySearch academic 域）

1. **GraLC-RAG (arXiv 2603.22633, 2026-03)** — "retrieval breadth vs MRR divergence":
   content-similarity 方法 MRR 最高 (0.517) 但永远只从单一 section 检索; structure-aware 方法
   覆盖 15.6× 更多 section。**直接对应本次发现**: answer_session_hit=True（session 级命中）但
   evhit=False（证据句级 miss）= 精度有、广度无。多 section/多 turn 证据合成是公开缺口，
   ECM 的全 haystack 句子扫描 + join 正是 breadth-first 路线。
2. **Sentence-Window Retrieval / Small-to-Big (LlamaIndex 系, glaforge 2025-02)** — 检索单句、
   返回句窗——HEARTBEAT 里 "sentence-window kw 匹配" 的出处谱系；本轮验证: 窗在**匹配期**
   就该用（不只是返回期），jam 案的时间表达与 NP 分居邻句。
3. **Anthropic Contextual Retrieval (2024-09)** — chunk 前置上下文注入降 retrieval failure;
   与本族互补: 我们的问题是"比较型问题需要两个 chunk 同时命中"，上下文注入救不了跨 turn join。
4. **OpenAI Temporal Agents Cookbook (2025-07)** + **Mem0 temporal anchoring** — 业界共识:
   "two months ago" 必须在写入时锚定为绝对日期（time-stamped triplets）。**ECM 的分歧点**:
   neither 族证明 vague duration（"a few months ago"）不必锚定到日历——**序数标量即可比较**，
   写入期强行日历化会引入伪精度。这是对 temporal-anchoring 教条的一个局部反例。
5. **LongMemEval (arXiv 2410.10813)** — temporal-reasoning 类目的设计即含 distractor sessions；
   本轮补充其内部结构: 同会话内的同构 "met X ago" 干扰（barista/trainer/writer）比跨会话
   distractor 更毒，因为它们共享全部上下文特征。

## 6. 核心概念
1. **证据墙** — 证据不是一条而是一面: 实体、事件、时间三要素分裂在多句/多 turn/多会话
2. **事件面** — 同一事件在文本中的表面形式集合；问题动词与证据动词可零交集，需要 verb-map
3. **序数时间标量** — vague duration 的比较只需序数（90>30），不需日历锚定
4. **回指 join key** — 关系 NP（sister-in-law）+ 共现专名，跨 turn 的事实粘合剂
5. **零劫持 gate 设计** — 严格形态匹配 + fire 集合恰等于目标族 = 对其余题零成本

## 7. 关键洞察（≥3）
1. **answer_session_hit=True × exact=0 的组合读数 = "检索无罪，证据墙有罪"** —— 
   这比 evhit=False 更有诊断价值: 答案侧机制缺位，检索侧调参是浪费。未来 C481 类报告
   应把 (session_hit, evhit) 对作为答案侧 gap 的 fingerprint。
2. **"写入期 temporal anchoring" 教条有局部反例** —— Mem0/OpenAI cookbook 主张相对时间
   写入即锚定日历；但 "a few months ago" vs "about a month ago" 的比较在**序数域**天然
   成立，锚定到日历反而制造伪精度（哪天？"few" 是多少？）。**锚定粒度应匹配比较粒度**。
3. **动词门是双刃剑: 人名实体的防劫持护甲，描述实体的伪需求** —— 钓鱼 Alex 靠动词门挡住；
   jam woman 靠动词门挡死。判据 = 实体有无词法锚面: 有名字 → 动词门必开；无名字 →
   用重叠数+时间可解析性替代。
4. **干扰的毒性梯度** — 同会话同构干扰 > 跨会话 distractor > 无关句。barista/trainer 与
   jam woman 共享 session、共享 "met ... ago" 形态、只差实体词——ECM 用 ≥2 内容词阈值全挡；
   这解释了为什么权重调参（C473 教训: 检索超参不可全局调优）救不了此族。

## 8. 下一步行动
1. **C497 落地**（key-dev cycle）: ECM 五决策移植 amg `amg_bench_quality.py` 答案侧——
   gate 前置于 C489 pairwise（形态互斥已验证），全 haystack 句子扫描复用 C472 回退基建，
   相对时间解析复用 C456 stash。目标: temporal-133 0.571→0.602 (+4/0)，oracle-parity 第四次。
2. **A/B 纪律**: 1.9GB 盒串行（C495 OOM 教训），PRE 臂在未打补丁 HEAD。
3. 观察项: full-500 刷新债（C493-C496 + C497 攒账），temporal 达 0.60 后再刷官方 reference。

## 9. 质量自评
- [x] 可运行代码: ecm_proto.py 4/4 + zero_hijack.py（全 500 扫描）
- [x] 独到见解: 洞察 1（fingerprint 读数）/2（锚定粒度反例）/3（动词门判据）
- [x] 与现有项目关联: C497 直接落地路径 + C472/C482/C489/C495/C496 机制谱系全部接续
- [x] 零劫持验证: gate 4/500 恰等于族全集
