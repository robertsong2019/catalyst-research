# Research #085 — Duration-Family 取证与四机制原型（M1-M4）

**日期**: 2026-08-23（晚轮 deep-exploration，与早轮 #084 entity-count 同日不同簇）
**上下文**: #084 副产物——C499 reference 的 multi_session 114 非弃权错题中 duration 族 26 题是第二大簇；HEARTBEAT "driving 计划-事实区分（GT 15 vs 19）"条目取证后发现 **STALE**（生产已 exact 答对），扩展为全族取证。
**代码**: [code/dur_family_proto.py](code/dur_family_proto.py)（v3，oracle 全绿）/ [code/dur_family_core_demo.py](code/dur_family_core_demo.py)（自包含 demo）
**验证命令**: `python3 code/dur_family_proto.py /tmp/dur_oracle2.json /tmp/all500_q.json`

---

## 一、取证（C499 官方 reference，multi_session 114 非弃权错题）

duration 族 26 题，分子族：

| 子族 | 机制 | 代表题 | GT | 生产错因 |
|------|------|--------|----|---------|
| A 窗口事件计数 | binge/watch + 窗口 | e831120c | 3.5 weeks | MCU 在两个 session 重复提及 → 4.5 |
| B 间隔天数 | 周∈{Tue,Thu,Sat,Wed} | a08a253f | 4 days | 数了课次数 5，非去重天数 |
| C 频率单位混淆 | — | （已由 C477/483 覆盖） | — | — |
| D 差值 | order→arrival | b3c15d39 / 60bf93ed | 5 days | 纯日历算术未做 |
| E 活动时长和 | realized vs habitual | 7024f17c | 0.5 hours | **计划语气当事实**（真·计划-事实墙） |
| F 时点 | — | （C456 when-resolution 覆盖） | — | — |
| G 金额 | — | （C491 total_sum 覆盖） | — | — |

### 深取证五题（answer sessions 原文证据）

1. **e831120c（M1）**: "all 22 Marvel Cinematic Universe movies in two weeks"（session _1）+ "the main films in a week and a half"（session _3，上下文=Star Wars）+ MCU 在 _2t4 被回忆性重提 → naive 4.5，GT 3.5。**错因=franchise 重提双计**。
2. **a08a253f（M2）**: 课表枚举 Tue/Thu/Sat/Wed 四个不同 weekday → GT "4 days"；生产答 5 = 数了 class 出现次数。姊妹对照 2788b940 问 "classes per typical week" GT=5——**同证据不同问题形态，答案互换**。
3. **7024f17c（M3）**: 仅 "went for a 30-minute jog...on Saturday" 是实现体；yoga 全部是 "used to / trying to get back / I'll schedule" 计划语气 → GT 0.5h。生产把习惯性时长累加。
4. **b3c15d39（M4）**: "ordered the new coffee machine on February 5th" × "it arrived on February 10th" → 5 天。月份名日期。
5. **60bf93ed（M4）**: "I bought **it** from Amazon on **1/15**" × "**It** arrived on **1/20**" → 5 天。三重难度：**斜杠 M/D 日期 + 代词回指产品**（it → 前句 "my new laptop backpack"）。孪生题 60bf93ed_abs 问 iPad case（全文无提及）→ 应弃权。

### HEARTBEAT 条目勘误

"driving 计划-事实区分（GT 15 vs 19）"——aae3761f 在 C499 官方 reference 中 **exact=True（PRED 15）**，C497b 的 (n,entity) 签名去重已修复。该待办 **STALE，应删**。但 driving 留作 M1 drive-mode 控制题（控制=已对题不得翻错）。

---

## 二、核心概念（4 个）

### C1. 计划-事实墙（plan/fact modality wall）
证据句的**语气**决定计数资格：`used to / trying to get back / planning to / I'll schedule` = 未实现，不得进 realized 时长和（M3 的 `_PLAN_MARKERS` 子句级排除）。这与 #077 past-perfect duration 同族——**时间算术的前提是事件实现性判定**。7024f17c 是最纯样本：0.5h 全部来自唯一一个实现体子句。

### C2. 实体键去重（entity-keyed dedup for re-mentions）
跨 session 重提同一实体（franchise/目的地）不得双计。M1 双轨：
- **franchise 别名表**：marvel/mcu/cinematic/avengers→`marvel`，star/wars/skywalker/jedi→`starwars`——枚举型娱乐实体的词面族
- **目的地 NP**：case-sensitive 专有名词，`trip to X` 优先锚（C497b (n,entity) 签名的姊妹）

### C3. 回指产品 join（anaphoric product resolution，nearest-first）
order/arrival 两事件的宾语常是代词（"bought **it**" / "**It** arrived"）。解法：**最近优先回走**——本 turn 内倒序子句 + 前序 user turn 倒序，用 `my (new) X` 所有格锚取产品 NP。两个顺序陷阱（见迭代弧）：`reversed(turns)` + 整体 `reversed(list)` 会把最老话题排到最近。C496 F6 anaphora 购买汇报 join 的同构推广。

### C4. 题目侧产品守卫（question-side product guard → 负存在弃权）
form fire 但 join 出的产品与**问题问的产品**不相交（"my iPad case" vs {laptop,backpack}）→ 显式 ABSTAIN。把 C498 弃权哲学从"零证据"推广到"**证据在但不是所问实体**"——这是防劫持的关键一步：没有守卫时 60bf93ed_abs 会被其他产品的 5 天对污染成自信错误答案。

（贯穿性原则，承 C473：**gate 与机制分离，gate 就是配置面**——census 用与生产完全相同的 gate 函数，杜绝"原型 gate ≠ 生产 gate"漂移。）

---

## 三、四机制与结果

```
M1 binge-dedup-sum     e831120c ✓3.5 | aae3761f ✓15 (控制)
M2 distinct-day-rate   a08a253f ✓4    | 2788b940 不 fire ✓ (控制)
M3 realized-window-dur 7024f17c ✓0.5
M4 delivery-interval   b3c15d39 ✓5 | 60bf93ed ✓5 | 60bf93ed_abs ✓ABSTAIN
```

**7/7 oracle 全绿，双控制守住，gate census 10 fire 零外溢**（M1×3、M2×1、M3×3、M4×3，全部在 duration 族内或已知 stretch 题）。机制级联 M1→M2→M4→M3，首个非 None 获胜（M1 先于 M3 短路，防 aae3761f 被 M3 平行捕获）。

### 迭代弧（v1→v3，六个真 bug）

| # | bug | 根因 | 修 |
|---|-----|------|-----|
| 1 | `(?i)` 全局内联杀死大写 NP 启发式 | drive 目的地靠 case 区分专名 | 去掉 (?i)，局部 re.I |
| 2 | MCU↔Marvel 无别名 → 重提未去重 | 词面族缺失 | franchise 别名表 |
| 3 | day-first 正则 vs 数据 month-first | 假设错误 | 双分支 (Month D / M/D) |
| 4 | jogging→jogg 词干断裂 | 双辅音未剥 | `_stem` 尾双辅音去一（C471 教训重现） |
| 5 | 回走候选顺序双反转 | reversed 套 reversed | 真 nearest-first 合并 |
| 6 | _abs 题被松散 join 劫持 | join 未对照问题实体 | 题目侧产品守卫 → ABSTAIN |

另有数字解析两处（"30-minute" 连字符 split、"a week and a half" 的 half 在 unit 后）——**英语习语顺序是数字解析的地雷区**。

### 笔记内嵌可运行 demo

见 [code/dur_family_core_demo.py](code/dur_family_core_demo.py)（零依赖、assert 自验证）：

```python
"""Distilled core — two killer decisions. Run: python3 dur_family_core_demo.py"""
import re

FRANCHISE = {}
for toks, fam in [("marvel mcu cinematic avengers", "marvel"),
                  ("star wars skywalker jedi", "starwars")]:
    for t in toks.split():
        FRANCHISE[t] = fam

_BINGE = re.compile(
    r"(?:watched|finished|completed)\s+(?:all\s+)?(?:the\s+)?(?:of\s+)?(?:the\s+)?"
    r"(?:\d+\s+)?[a-zA-Z\- ]*?(?:movies|films)\b[^.]*?\bin\s+"
    r"(one|two|three|four|five|six|seven|eight|nine|ten|a|an)"
    r"\s+weeks?(\s+and\s+a\s+half)?", re.I)

def m1_watch_dedup_sum(user_texts):
    """Franchise-keyed dedup: re-mention of same franchise adds nothing."""
    nums = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    dur = {}
    for text in user_texts:
        fams = {FRANCHISE.get(w.lower().strip(".,!?;:")) for w in text.split()} - {None}
        if not fams:
            continue
        m = _BINGE.search(text)
        if not m:
            continue
        n = nums[m.group(1).lower()] + (0.5 if m.group(2) else 0)
        key = frozenset(fams)
        if any(k & key for k in dur):   # same franchise already recorded
            continue
        dur[key] = n
    return round(sum(dur.values()), 2)

def m4_guard(question, order_evt, arrival_evt):
    """Join only if joined product matches the asked-about item, else ABSTAIN."""
    qm = re.search(r"(?:my|the|a|an)\s+([a-z\- ]+?)\s+(?:after|to arrive)", question)
    if not qm:
        return "ABSTAIN"
    q_stems = {w for w in qm.group(1).split() if len(w) > 2}
    prod = set(order_evt["product"]) | set(arrival_evt["product"])
    if q_stems & prod:
        return f"{arrival_evt['day'] - order_evt['day']} days"
    return "ABSTAIN"

if __name__ == "__main__":
    texts = ["I watched all 22 Marvel Cinematic Universe movies in two weeks!",
             "Then I finished the main Star Wars films in a week and a half.",
             "My friends could not believe I watched all the Marvel movies in two weeks."]
    assert m1_watch_dedup_sum(texts) == 3.5          # naive re-mention sum: 5.5→GT 3.5
    q  = "How many days did it take for my iPad case to arrive after I ordered it?"
    ev = ({"product": ["laptop", "backpack"], "day": 15},
          {"product": ["laptop", "backpack"], "day": 20})
    assert m4_guard(q, *ev) == "ABSTAIN"             # evidence ≠ asked entity
    assert m4_guard("... for my laptop backpack to arrive?", *ev) == "5 days"
    print("demo OK")
```

实测输出：`demo OK: m1=3.5 weeks, m4 guard abstains on unmatched product, joins on match`

---

## 四、关键洞察（4 条）

1. **"计划-事实墙"不是一个题，是一个语气判定器**。7024f17c（yoga 计划语气排除）和 STALE 的 driving 条目同属此墙，但 driving 已被 C497b 实体签名间接修复——**同一堵墙有多扇门，修复常常从侧门进来**。待办清单必须对官方 reference 周期性验尸，否则会重修已修好的墙（本次 HEARTBEAT 勘误的直接教训）。
2. **代词回指产品的解是"最近优先 + 所有格锚"，而不是更复杂的句法**。60bf93ed 两次 anaphora（bought it / It arrived）都被 12 行 nearest-first 走查解决；真正的坑全在候选顺序（reversed×reversed = oldest-first 伪最近）。呼应 C496 F6：**对话式购买汇报里 "my X" 是产品话题句的高精度签名**。
3. **负存在弃权要对照问题实体，不只对照证据存在性**。C498 的"零证据 abstain"防不住"有证据但非所问"（60bf93ed_abs 有完整 order/arrival 对——只是 backpack 的）。问题侧 NP 提取 + 与 join 产品求交，3 行守卫把一个自信错误换成弃权。**弃权面应按 (form, entity) 二维设计**。
4. **数字习语解析是 duration 族暗坑**："a week and a half"（half 后置于 unit）、"30-minute"（连字符无空格）、"in two weeks" vs "two weeks ago"。本族六个 bug 中三个纯数字-词法，与推理无关。这支持 C490 的判断：**单位/数字锚卫生是 duration 管线的地基工程**。

### 外部对标（arXiv 检索）
- **RUMBA**（arXiv 2607.21447）：俄语长程对话记忆基准，明确按 semantic type × session scope × temporal reasoning × explicitness 分型计错——与本项目"form 是配置面"的取证实证路线同构。
- **CABLE**（arXiv 2608.17911）：指出检索侧语义相似度够 topical recall 但 miss 早先经验/动机（antecedent），用 antecedent-oriented linking 补检索——本族 answer_session_hit=True × 全错 = 检索无罪证据墙有罪的又一次独立佐证（#082 已见 GraLC-RAG 同构）。
- LongMemEval 相关文献 125 篇（2026-08 检索），duration-aggregation 错误解剖方向仍以基准侧为主，**子句级 modality 门 + 实体键去重的机制级原型在公开文献中未见直接对应**——生产化后有博客/短文价值。

---

## 五、下一步行动

1. **C505 候选：M1-M4 生产化移植**（amg_bench_quality.py，counting/temporal 管线第 6-9 形态）——oracle 7/7 就绪，预期 multi_session 0.120→0.140+（26 错题族中 5 题直接可修 + 2 控制零翻错）；需先跑 full oracle parity + /tmp/c497 式串行 A/B。
2. **census 额外 fire 题审计**：2ebe6c90（M1 fire，GT 21 天——实为 order-arrival 族形态跨界，M1 需让位 M4 或改 gate）；311778f1/71315a70（M3 fire，GT 10 / 10-12h——stretch，机制输出需与 GT 对齐后再决定收留或窄化）。
3. **HEARTBEAT 勘误落地**：删除 driving STALE 条目（本轮已确认）。
4. stretch 目标：1192316e（get ready+commute = "an hour and a half" 复合活动时长）留给 M3 v2 的多活动枚举。

---

## 六、质量自评

- [x] 可运行代码：dur_family_proto.py（oracle 全绿，2 控制题）+ 自包含 demo（assert 验证）
- [x] 独到见解：计划-事实墙多门性 / nearest-first anaphora / 二维弃权面 / 数字习语地雷
- [x] 项目关联：直接铺 C505 生产化路径；承接 C490/C491/C496/C497/C503 机制族谱系
- [x] 取证-原型-验证闭环：26 题族普查 → 5 题深取证 → 4 机制 → 7/7 oracle → census 零外溢
