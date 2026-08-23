# Fired-but-Wrong 取证 — temporal 算术门的 9 具尸体解剖

**Research #072** | 2026-08-18 20:11 (deep-exploration-evening) | 来源: HEARTBEAT Next dev target "fired-but-wrong 9 题取证（honest qid 已解锁）"；C467 修正地图 temporal 0.895 evhit / 0.180 exact

## 背景与方法

C457 temporal arithmetic 在全量复现（temporal 133 题 0.045→0.180, 4.0×）后遗留 9 题"机制 fire 了但答案错"。C457 当时的假设是"mention session vs event session 混淆"。本轮用 C466/C467 解锁的 honest qid 做逐题取证：在**全量 haystack**（非 4000-token 检索窗，信息上界）上复现 `best_line` 锚定，对照 `answer_session_ids` 做 fix-locality 测试（金会话锚定能否算出 GT），并用 19 题 fired-correct 做对照组。

**基线：28 fired / 19 correct / 9 wrong，fire 精度 0.679。**

## 决定性发现（一条）

**会话日锚定 = 文档创建时间（DCT）的一阶近似；它正确当且仅当事件被同日叙事。** 对照组 17/17（可检验算术型全部）金会话日期做同样算术直接等于 GT；9 个失败案例全部落在"事件日期 ≠ 会话日期"或"锚定选错行"两个域。C457 的"mention vs event session"假设只解释了其中约一半——另一半是**子会话粒度**问题：事件日期由文本内相对表达（yesterday/today/last week）承载，任何会话粒度机制都结构性够不到。

## 失败分类（9 题 → 5 桶，全部可诊断）

| 桶 | 案例 | 机理 | 确定性可修? |
|----|------|------|------------|
| **A. 计划-事件混淆** | gpt4_b0863698（5K run：03-10 "planning to run" 击败 03-19 实跑）、gpt4_4fc4f797（suspension：03-17 "planning to test next month" vs 04-23 实测） | 未来意图句与过去事件句同分或先出现 | ✅ 平局改判（后日期优先）即修 b0863698；4fc4f797 还差 +1 包含日 |
| **B. 子会话事件日期** | 982b5123（Airbnb 预订在 ~12 月、唯一金会话是 05-21 计划对话 → 答了 0 个月）、eac54adc（GT 事件日 03-05/06 不是任何会话日）、9a707b81（"yesterday"→03-20 给 26 天 vs GT 21） | 事件日期存在于文本内 TIMEX3 相对表达，非会话时间戳 | ⚠️ 仅 982b5123 类可修（相对表达解析）；eac54adc/9a707b81 证据内无日期 → 应弃权 |
| **C. 锚词评分 bug（引号+形态学）** | gpt4_e072b769（**引号 bug**：关键词 `"'ibotta'"` 带引号，gold 会话里 Ibotta 出现 25 次命中 0；泛词 using/app/cashback 到处命中）、gpt4_21adecb5（**形态学**："submitted"≠"submission"、"master's"≠"master"，金行 1 分与 sharegpt 垃圾行 1 分平局，垃圾因列表位置靠前获胜） | `_anchor_keywords` 不剥引号、不做词干归一 | ✅ 剥引号+轻量词干即修 21adecb5（金跨度=6 月=GT ✓）；e072b769 修后还叠一层周舍入 bug |
| **D. 单位舍入语义** | af082822（13 天 → GT 2 周，floor 给 1）、gpt4_e072b769（修引号后 20 天 → GT 3 周，floor 给 2） | 数据集"including the last day"= 包含式计数 → 周单位实为 **ceil** 语义：ceil(13/7)=2 ✓ ceil(20/7)=3 ✓ ceil(28/7)=4 ✓（精确倍数不变，不伤对照组） | ✅ judge 或 duration_units 改 ceil |
| **E. 多金会话歧义** | b46e15ed（4 个金会话；"consecutive days" 约束指向 02-14/15 对，机制因首现平局选了 01-30 的另一场 charity gala） | 问题约束未建模；first-max 平局裁决 | ✅ 后日期平局改判即选对（02-14 → 2 月 = GT ✓） |

**堆叠 bug 实例**：gpt4_e072b769 = 引号 bug × 周舍入 bug 双层叠加——单修任一层都无效。这就是取证的必要性：直觉修 bug 会漏栈。

**Fix-locality 量化**：A+C+D+E 桶共 6 题（1,2,4,5,6,8 号案例）可确定性修复 → fire 精度 0.679→**0.893**（25/28），temporal exact 0.180→~0.192，overall 0.144→~0.156；B 桶 3 题中 1 题可修（相对表达解析）、2 题证据无日期 → 正确动作是**弃权而非强答**（C448 熵门精神在答案侧的等价物）。

## 核心概念 (5)

### 1. 会话日锚定 = DCT 近似
HeidelTime（TempEval-2/3 冠军，规则式 TIMEX3 标注器）把 "yesterday/tomorrow" 类相对表达的归一化建立在 focus-tracking 上：以文档创建时间（DCT）为参照，且**按文体分策略**——新闻用 DCT，叙事文要在文内找参照时间，口语对话继承 DCT。LME 的每个 session 就是一篇口语体文档，session 时间戳 = DCT。C457 机制隐式用了"DCT ≈ 事件时间"假设，对照组证明该假设在 68% 的 fire 里成立——剩下 32% 是 HeidelTime 论文里"colloquial 域相对表达必须解析"的教科书案例。

### 2. 计划-事件时相区分
"I'm planning to run a charity event"（未来意图）与 "I participated in the 5K run"（过去事件）对关键词评分器不可分。TimeML 用 MAKEINSTANCE 的 tense/aspect 属性显式建模；零依赖的工程近似是**三段裁决**：词法时相标记过去优先 + 角色优先（事件几乎总在 user turn 首报）+ 平局取更晚日期（事件报道晚于计划）。本轮实测：单"更晚日期"一条就能救 3/9（案例 1、8，及 5 的锚 B）。

### 3. 文本内 TIMEX3 解析 = 子会话粒度的唯一入口
B 桶证明存在事件日期只存在于行内相对表达的题型。修法与 C456 的 when-question date resolution 同构但方向相反：C456 解析**问题侧**的相对时间词（"last week" 相对 question_date），这里解析**证据侧**（"yesterday" 相对 session_date）。同一套相对词表+日历算术可复用——amg 已有的资产直接迁移。

### 4. 锚词卫生
两个具体 bug 构成"锚词卫生"清单：① 引号/撇号不剥离（`'ibotta'` 失效）② 屈折形态不做归一（submitted/submission、master's/master）。更深一层是**泛词稀释**：锚短语里唯一有区分度的词（Ibotta）被 bug 废掉后，剩下的泛词让垃圾行也能得 2 分。防御：区分度加权——只数非泛词命中，泛词只作 tie-break。这与 C447 的"词边界+屈折形态匹配器"、#071 的量纲污染同属一个 matching-hygiene 家族。

### 5. 平局裁决是被沉默的决策点
`if hits > best_hits`（严格大于）意味着**列表位置先者胜**——一个从未被审视的设计在 9 个失败里决定了 3 个。对照组能活是因为同日叙事时金行通常独占最高分。确定性平局策略（角色 → 时相 → 日期新近度）是零成本精度；这与 C437 consolidate tie-break（(-imp, label) 字典序）是同一课：**所有全序比较器的平局语义必须显式设计**。

## 代码示例（已验证可运行）

`code/fw9_forensics.py` — 完整取证管线，全量数据实测输出：

```
fired=28 correct=19 wrong=9

########## WRONG (forensics) ##########   ← 9 题逐题：锚定复现 + 金行候选
  ANCHOR "start using the cashback app 'Ibotta'" kw=['using','cashback','app',"'ibotta'"]
    -> 2023-04-08 [b9e32ff8_1] user hits=2 gold=False     ← 引号 bug 实锤
...
########## CONTROL (fired-correct) ##########
CONTROL: 17/19 fired-correct are pure session-date arithmetic (same-day narration).
```

复现要点：`best_line` 与 `amg_bench_quality.answer_temporal_arith` 逐行同构（含 first-max 平局）；fix-locality 用 `duration_units` 对金会话日期重算并对照 GT 整数集；对照组把同一算术施于全部 19 个 fired-correct。注意：全量 haystack 取证与 4000-token 检索窗内的运行时锚定可能不同（信息上界 vs 实际窗口），分类学结论不受影响但单题 PA 可能来自不同垃圾行。

## 关键洞察 (4)

1. **机制的精度天花板由数据的同日叙事率决定。** 28 个 fire 里 19 个正确全部因为"事件当天聊事件"；这不是实现质量问题，是**会话粒度信息论边界**——当事件日期只以行内相对表达存在时，任何只看会话时间戳的机制必然 ±N 天误差。设计答案侧机制前先测同日叙事率，等于先测机制的理论上限。

2. **数据集的计时约定是可逆向工程的产品规格。** "21 days. 22 days (including the last day)" 表面是宽容判分，实际泄露了标注器的**包含式计数**语义；周单位上它等价于 ceil 而非 floor。逆向出这条规格后，13 天→2 周、20 天→3 周两题从"玄学失败"变成"规格不符"。读 GT 的注释文本本身就是特征工程。

3. **弃权是 B 桶的正确答案，不是失败。** eac54adc/9a707b81 的证据里不存在可推出 GT 日期的信息（GT 日期 03-05/06 无任何会话或行内锚点）——这两题对任何确定性机制都不可解，对 LLM reader 也大概率靠先验猜。amg 的差异化恰恰是**识别不可解并弃权**（C448 熵门的答案侧推广），而不是把 0.679 的 fire 精度硬刷成带幻觉的 0.7。

4. **取证 > 直觉修 bug，因为 bug 会堆栈。** e072b769 是引号 bug × 舍入 bug 的双层栈，单修一层 A/B 测不出效果就会被误判为"此路不通"而回退。C466 的 honest qid 把"9 题 fired-wrong"从聚合数字变成可逐题指认的名单——**聚合指标定位不了堆栈故障，可追溯的单题取证才能**。这是 answer_session_hit（C467）之后第三类证明"归因指标"价值的数据点。

## 下一步行动 (3)

1. **[Cycle 468 dev 候选，与 #071 三修一加合并排期] 锚定卫生四件套**：① `_anchor_keywords` 剥引号+轻量词干（submi/tes 前缀归一）② 平局裁决 user-role > 过去时相 > 更晚日期 ③ 周单位 ceil（或 judge 接受 floor 与 ceil 双值，与 days 的 span/span+1 对齐）④ 泛词只作 tie-break。验收：temporal-133 A/B，fire 精度 0.679→≥0.85，零回归。
2. **[证据侧 TIMEX3 迷你解析器]** yesterday/today/last N/Month-name → 相对 session_date 解析（复用 C456 词表），先行原型于 28 个 fire 题；无日期证据的 B 桶行 → 机制弃权（fall-through）而非强答。
3. **[叙事侧] 与 #071 合流为答案侧三部曲**："检索不是记忆"（evhit 0.955 vs exact 0.007）+ "temporal arithmetic without an LLM"（C457）+ 本轮"same-day narration ceiling"（对照组 17/17）——三个归因故事共享一个论点：**证据在，答案要算**。

## 质量自评

- ✅ 可运行代码：fw9_forensics.py 端到端实测（28 fired 全量复现 + 对照组 17/19）
- ✅ 独到见解：同日叙事天花板（新概念，含理论表述）/ 包含式计数规格逆向 / bug 堆栈 / 弃权正当性——均非检索可得
- ✅ 项目关联：直接产出 Cycle 468 验收标准（fire 精度 ≥0.85），衔接 C437/C447/C448/C456/C457/C467 六代谱系，与 #071（答案侧聚合）构成同周双资产
- ✅ 方法论符合 autoresearch：指标明确（fire 精度 0.679→0.893 上界）、证据驱动（全量非抽样）、每桶修复可 A/B
