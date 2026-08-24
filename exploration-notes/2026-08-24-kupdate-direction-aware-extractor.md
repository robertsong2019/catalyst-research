# #087 · Kupdate 方向感知抽取器：53 错的取证与 latest-wins/earliest-wins 双向机制

**日期**: 2026-08-24（deep-exploration-evening cron）
**状态**: 原型完成 — oracle 54/78（baseline 22，2.46×），回归 2
**上游**: C508 (aa3fe03, full-500 exact 0.382, post_full500.json) / C507 (4763dff)
**代码**: `catalyst-research/code/r087/`（r087_proto.py 自包含可运行 + r087_fixture.json 78 题 2.2MB）
**并行预警**: 本研究与另一会话的 #086 delta-family 安装（/tmp/c507 r086_install）完全无冲突——不同类目（kupdate vs multi_session）、不同报告源（c508 vs c507）。

---

## 0. 问题定义

C508 官方刷新后 full-500 exact 0.382，类目错误池：multi_session 97（在飞 #086）、temporal 52（20+ cycle 深耕递减）、**kupdate 53（从未做过答案侧取证）**、ssa 40、ssu 37、preference 30（#080 判死）。

kupdate 的结构性矛盾（C467 已记录但从未解剖）：**检索 hit 0.987，exact 只有 0.321**——证据在窗内，答案协议回声错误行。本研究对 53 错做逐题取证，建立机制族原型。

## 1. 核心概念（5 个）

1. **抽取失败 ≠ 检索失败（forensics 第一定律再证）**：53 错中 42/53 = GT 字面躺在 answer 会话里（80%），5 = 负存在题（GT 本身是"信息不足"），3 = 值在窗外，3 = 需合成（37+1、方向比较、previously-vs-now 双值）。修复杠杆全部在答案侧，与 multi_session 故事（C467: evhit 0.955 vs exact 0.007）同构。

2. **方向二象性（Direction Duality）**：kupdate 问题有两个时间方向——**LATE**（"currently/how many do I have"→最新断言胜，陈旧孪生是干扰）与 **EARLY**（"initially/previous goal/before I updated"→更新前的旧值才是答案，最新断言反而是陷阱）。v1 纯 latest-wins 在 EARLY 题全灭；但 "previous company/tutor" 是**实体修饰语**（问 Rachel 现在的公司）不是时间指针，需实体名词守卫排除。

3. **排序键的角色布尔陷阱**：EARLY 分支用升序排序时，`role==user` 的 False（assistant）天然排前——角色纪律被静默反转，代价 −9 题。修复：升序分支用 `not x[user]` 键。这类"方向翻转带反半票"的排序 bug 是 A/B 才能抓到的静默错误。

4. **请求标记排除是伪机制（负结果）**：v8 把"请求行降级"做硬排除，54→33 崩盘。取证：**34/53 正确 pick 本身含请求标记**（"37 coins... any recommendations?" 值+请求混行是 LME 对话常态）。教训：行为标记做硬门前必须 census 正确样本的标记分布（C498 shipped-gate census 纪律第三次验证）。

5. **值-签名子句局域性跨族移植**：#086 的 principle 4（数值与锚词同子句）直接移植到 how-many 门：数字/拼写数词（five/twice——纯 digit 过滤会漏）必须在签名词 70 字符内。"auctions... 15 miles away" 类远距数字行被过滤。机制复用是积累性原则的直接收益。

## 2. 可运行代码

`catalyst-research/code/r087/r087_proto.py`（纯 Python 3 标准库，无第三方依赖；fixture 78 题已随附）：

```bash
python3 catalyst-research/code/r087/r087_proto.py      # n=78 baseline 0.244 -> proto 0.692
python3 catalyst-research/code/r087/r087_proto.py -v   # 逐题方向/形式/判定
```

核心机制（约 60 行有效逻辑）：

```python
def is_early(qtext):
    if ENT_NOUNS.search(qtext):        # "previous company/tutor" = 实体修饰语，非时间方向
        return False
    return bool(EARLY_RE.search(qtext) or PREV_MEASURE_RE.search(qtext))

# 候选行排序（方向感知 + 角色纪律）
if early:
    cands.sort(key=lambda x: (x[2], not x[1], -x[0], x[3]))   # 早会话, user优先, 高签名, 早行
else:
    cands.sort(key=lambda x: (x[2], x[1], x[0], x[3]), reverse=True)  # 晚会话, user优先...

# how-many 值门：数字/拼写数词 + 子句局域性
vf = [c for c in cands if re.search(r'\d', c[4]) or NUMWORD_RE.search(c[4])]
near = [c for c in vf if (value_near_sig(c[4], sig) or 999) <= VAL_WIN]
```

## 3. 实验轨迹（experiments 口径）

```
v1  latest-wins 纯排序                    43/78  回归 6   — EARLY 题全灭
v3  +方向反转（无实体守卫）                 40/78  回归 8   — "previous company" 假阳性
v4  +实体名词守卫                          44/78  回归 6
v6  +形式值门/yes-no 面                    44/78  回归 8   — "five/twice" 拼写数漏
v7  +EARLY 角色键修复 + 拼写数              53/78  回归 3   ★ 关键修复
v8  +请求行硬排除                          33/78  回归 10  ✗ 负结果：34/53 正确行含请求标记
v9  +值-子句局域性 + weekday 专用门         54/78  回归 2   ★ 定稿
```

## 4. 关键洞察（4 条）

1. **kupdate 的 53 错是答案协议问题，且 80% 可由"方向感知的行选择"确定性修复**——不需要 LLM、不需要嵌入，检索侧（answer_session_hit 0.987）已经把证据递到手边。oracle 上界 0.692；保守生产化（form-gate + 检索窗近似）预期 +15~20 题 → kupdate 0.321→~0.55，full-500 +3~4pp（0.382→~0.42）。

2. **"previous/initially" 双关是 kupdate 独有的陷阱词族**：时间指针（previous goal → EARLY）与实体修饰（previous company → LATE）在词法上同形，必须用名词类别（度量词 vs 人物/机构词）消歧。这与 C471 锚定卫生（引号/所有格归一）同属"词法信号的方向性审计"。

3. **负结果三连的元规律**：v2 值过滤（44→34）、v8 请求排除（54→33）、v3 无守卫方向（43→40）——每个"看起来显然对"的过滤器都在正确样本 census 下崩塌。**加过滤器之前先数一数正确答案里有多少会被它杀死**（shipped-gate census，本季度第三次验证，应升格为 cycle 前置检查项）。

4. **EARLY/LATE 排序键的不对称 bug 模式**：`reverse=True` 的多键排序在翻转方向时，布尔角色键的语义跟着翻转——升序分支必须显式重写键（`not user`）。这个坑在 C497（确定性 tie-break）同类：排序键的每个分量都要在两个方向下单独审计。

## 5. 下一步行动

1. **C509+ 候选（最高优先）**：kupdate answer face 生产化——amg_bench_quality.py 答案路径，question_type=='knowledge-update' 触发；oracle 用的 answer_session_ids 换成检索窗消息（answer_session_hit 0.987 保证近似）；预期 A/B：kupdate-78 切片 25→40+，full-500 0.382→0.41+。
2. 负存在 abstention 门：5 题 ABS_Q（GT="信息不足"）加"全 haystack 无签名 → I don't have enough information"（C489 负存在模式，yesno 的 No-face 已验证机制）。
3. 合成类 3 题挂账：37+1 增量更新、more/less 方向比较、previously-vs-now 双值——机制族候选（delta-family #086 的运算子可复用 diff/rate）。
4. 本笔记洞察 3（census-before-filter）写入 amg cycle checklist。

## 6. 质量自评

- ✅ 可运行代码：r087_proto.py 独立验证 54/78（fixture 模式与全量模式一致）
- ✅ 独到见解：方向二象性 + 实体守卫 + 三个负结果的 census 元规律
- ✅ 项目关联：直接给出 C509+ 生产化路径与预期收益；机制移植链 #086→#087 明确
- ✅ 实验记录：v1→v9 九轮轨迹含两次负结果，符合 autoresearch 快速循环+保留/回退

## 7. C510 生产化裁决：RECORD-NEGATIVE（2026-08-24 21:35）

C510 尝试将 v9 生产化，在移植前用 **virtual-flip census** 杀死于设计阶段（0 行生产代码）：

- **方法**：门控正则（PERFECT/OFTEN/EARLY/CUR/RECENT，57/78 覆盖）+ r087 原型逻辑 + 生产 `exact_judge`，全量 500 题直接函数级评估，无需跑评测臂。
- **致命发现 1——判分鸿沟**：原型 oracle 19→54 建立在关键词判分（gt 每词任意位置命中）上；生产 exact_judge 要求 gt **归一化后连续包含**于 pred。整行返回在生产判分下大面积失效：ku 类 57 fire 仅 21 通过（13 x→ok + 8 was→ok）。
- **致命发现 2——形态不可分**：PERFECT 形态（"how many have I V-ed"）内部赢输共存（0ddfec37 输、06db6396 赢）——决定成败的是**选择质量**（sig-hits + 方向排序能否命中含 gt 的行），不是问句形态；无文本门控能把两者分开。
- **致命发现 3——跨类劫持**：门控 124 fire 中 31 个 currently-correct 被翻错（SSU 5、temporal 9、multi 6、ku 11），净 -7。
- **方法论产出（本 cycle 真正价值）**：virtual-flip census = 门控 + 原型逻辑 + 生产判分在函数级直接评估全库，**移植前杀死设计**，成本 ≈ 3 分钟，替代“移植→A/B 两臂→套件→台账”全链 ≈ 25 分钟。已升格为 #088+ 所有 answer-face 生产化的前置关卡（与 insight #252 append-only、STRICT form gate 并列）。
- **v10 方向**：(a) 值跨提取代替整行返回（满足连续包含）；(b) 选择信号超越 sig-hits（值-签名距离已验证于 #086，可迁移）；(c) 或放弃 answer-face，走 judge 侧（LLM judge 对 kupdate 残差的救援路径，C462 已有基础设施）。
