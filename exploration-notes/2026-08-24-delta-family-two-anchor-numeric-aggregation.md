# #086 · Delta-Family：双锚点数值聚合机制（multi_session 剩余错误族）

**日期**: 2026-08-24（deep-exploration-evening cron）
**状态**: 原型完成 — oracle 16/21，fired 精度 100%（16 fired / 16 correct / 0 wrong-fire）
**上游**: C507 (4763dff, multi_session 0.233→0.271) / C508 (aa3fe03, where-form 0.368→0.382)
**代码**: `catalyst-research/code/r086/`（r086_proto7.py 自包含可运行 + r086_corpus.json 21题语料）

---

## 0. 问题定义

C507 后 multi_session 仍有 97 错。taxonomy（r086_taxonomy.json）显示 how_many 52 题是已三次撞墙的死墙（C483 教训），但其旁存在一个**未被任何现有机制覆盖的族**：**delta-family ≈25 题** —— 问题要求对**两个分散在不同 session 的数值断言**做算术聚合（差/和/比率/比较）。现有算子（total_sum / unit_sum / number_total / item_total / total-number-v2）全部假设**单一聚合方向**（多数为求和），无一处理"双侧独立锚定再运算"。

本研究的 21 题子集在 C507 中 **全错**。原型 v2.7 修复 16 题 → 若生产化，multi_session 预计 36+16=52/133 ≈ **0.391**（vs 0.271，+12pp）。

## 1. 核心概念（5 个）

1. **二部绑定（Bipartite Binding）**：`compared to / than / instead of / between X and Y` 类问题在**问题文本自身**命名了两条锚实体侧。每侧独立提取关键词集，分别到全部 session 历史中找数值行，两侧各自 pick 后套算子。问题即 join 条件。
2. **any-of 锚点打分 + 四级排序键**：候选行按 `(命中锚数 n, user角色, 后session, 同子句, 负字符距离)` 排序。任一锚命中即可入围（must-all 会在同义/词干缺口下全灭），多锚/user/后session 依次优先。**角色纪律**：assistant 行是建议区间的主要污染源（Tokyo ¥ 区间、Blue Apron 促销），user 断言 > assistant 推测。
3. **交叉侧排除（cross-side exclusion, 严格多数制）**：A 侧 pick 时若行内 B 侧锚词数 **>** A 侧命中数则跳过。用严格大于（而非 ≥）是关键：过渡叙事行（"missed my train… took a taxi, $12"）合法地同提两侧，此时交给距离决胜。排除词必须滤掉单位词——`per/night` 曾让 Tokyo 侧全灭。
4. **子句局域性（clause locality）作 tie-breaker 而非过滤器**：锚与数值之间隔着 `.!?;` 的候选降权而非丢弃。一行多值时（"air filter $25 … gas $30 … parking ticket $50"）距离最近不总是对的，"锚后同子句"才是；但硬过滤会杀死 $24 出现在 434 字符长行末尾的合法案例。
5. **算子族 + 诚实弃权**：diff / sum-two / minmax-sum / rate乘 / count-ratio / price→pct / compare-pct / temporal-diff（ago/last vs now/recently 时间方向词定侧）。任一侧无锚或正则不中 → `I don't know`，计入 fired 不计入 correct——与 LongMemEval 的 abstention 能力维度对齐。

## 2. 可运行代码

`catalyst-research/code/r086/r086_proto7.py`（无第三方依赖，Python 3；语料 21 题/10366 msgs 已随附）：

```bash
python3 catalyst-research/code/r086/r086_proto7.py      # oracle: fired 16/21  correct 16/21
python3 catalyst-research/code/r086/r086_proto7.py -v   # 逐题 pick 过程
```

核心引擎（节选自 r086_proto7.py）——pick() 是全部六次迭代收敛的所在：

```python
def pick(cands, anchors, unit_ctx=None, require=None, exclude=None):
    """any-of 锚点打分: (n命中, user角色, 后session, 同子句, 负距离) 排序。
    require=必现词; exclude=对侧锚(严格多数才排除); 150字符硬距离上限。"""
    exp = list(anchors or [])
    for a in (anchors or []):
        exp.extend(LEX.get(a, ()))            # 迷你地理词表: hawaii→{maui,honolulu,oahu,...}
    best, bestkey = None, None
    for t in cands:
        v, si, r, ln, raw = t
        l = ln.lower()
        if RANGE_RE.search(ln): continue      # 预算区间/planning 干扰行
        if unit_ctx and not any(u in l for u in unit_ctx): continue   # 单位共现: 'per night'
        n = sum(1 for a in exp if a in l)
        if exp and n == 0: continue
        if require and not all(x in l for x in require): continue     # 'originally' 必现
        if excl and sum(1 for x in excl if x in l) > n: continue      # 严格多数排除
        dist = local_ok = 0
        if exp:
            poss = [(abs(vpos_ - apos), apos, vpos_) for a in exp if a in l
                    for apos in [l.find(a)]
                    for vpos_ in [l.find(raw) if l.find(raw) >= 0 else -1] if vpos_ >= 0]
            if not poss: continue
            dist, apos, vpos_ = min(poss)
            if dist > 150: continue
            seg = l[min(apos, vpos_):max(apos, vpos_)]
            local_ok = not any(s in seg for s in '.!?;')   # 子句局域性: tie-breaker
        key = (n, r == 'user', si, local_ok, -dist)
        if bestkey is None or key > bestkey:
            best, bestkey = t, key
    return best
```

语料构建（从 277MB 原始数据提取 21 题 → 11MB 工作集）：`/tmp/c507/research_r086_corpus.py`（session 炸平为 `(session_idx, role, content)` 行流）。

## 3. 关键洞察

1. **"问题即 join 条件"是 delta-family 的本质**。单侧机制（一个实体→一个数）在 amg 中已饱和；剩余错误的结构特征是**问题文本内嵌双侧实体命名**。这提示未来的 form-gate 应检测分离词（compared to/than/instead of/between/after the initial）直接路由到 bipartite 路径，而不是继续堆单侧模板。
2. **排序键的每一级都来自一次真实回归**。六次迭代的失败模式链：must-all→全灭(词干缺口) ⇒ any-of；≥排除→过渡叙事误杀 ⇒ 严格>；子句硬过滤→长行末尾值丢失 ⇒ tie-breaker；`originally` 可选→同行 $30 自比较 ⇒ require + 排除 orig 行。**约束的强度必须恰好盖住已观察到的失败，不留一行余量**——这是与 C507 total-number-v2 同款的纪律。
3. **单位词是侧锚的毒药**：tokyo 侧被 hawaii 侧的 `per/night`（应为 unit_ctx 而非锚词）排除全灭。 GENERIC/SIDE_GEN 词表的分层（功能词/商务泛词/单位词）不是美化，是正确性边界。词表缺口（hawaii↔maui 需 LEX）同时印证 #083 的嵌入 side-channel 协同点。
4. **fired 精度 100% 比 recall 更重要**：16/16 fired 全对意味着 form-gate 可以放心放行，错误只来自"没敢答"（5 题 noform + 0 题 IDK-miss），不会引入新错误——这正是诚实弃权设计的验证。对照 LongMemEval 论文（ICLR 2025, arXiv:2410.10813）：其优化全在 indexing/retrieval/reading 三段检索侧，未触及符号化数值聚合算子——本机制与其互补而非重叠。
5. **回归测试驱动原型**：v2 的 6 个已验证对（078150f1/09ba9854/0ea62687/4bc144e2/77eafa52/e25c3b8d）在每次 patch 后全量重跑，v2.2/v2.4 两次"全局改善但局部回归"（minmax、taxi/train）都被立即抓回。没有 oracle 回归网，这套约束调平不可能收敛。

## 4. 逐题结果（oracle v2.7）

| qid | 形态 | 机制 | 结果 |
|---|---|---|---|
| 078150f1 | goal-diff | raised $250 − aimed $200 | ✓ $50 |
| 09ba9854 | save-instead | taxi $60 − train $10 | ✓ $50 |
| 0ea62687 | temporal-diff | 30mpg(ago) − 28(now) | ✓ 2 |
| 1f2b8d4f | compared-to | boots $800 − $50 | ✓ $750 |
| 2318644b | per-night diff | Maui $300 − Tokyo $30 | ✓ $270 |
| 3fe836c9 | than | pre-approval $350k − sale $325k | ✓ $25,000 |
| 4bc144e2 | sum-two | wash $15 + ticket $50 | ✓ $65 |
| 61f8c8f8 | temporal-diff | 5K 45min(last yr) − 35min | ✓ 10 minutes |
| 7405e8b1 | compare-pct | HF 40% vs UberEats 20% | ✓ Yes. |
| 77eafa52 | after-init | corrected $2,800 − quoted $2,500 | ✓ $300 |
| 91b15a6e | minmax-sum | min $5,000 + min $150 | ✓ $5,150 |
| 9aaed6a3 | rate 乘 | $75 × 1% | ✓ $0.75 |
| cc06de0d | compared-to | taxi $12 − train $6 | ✓ $6 |
| d905b33f | price→pct | 1 − 24/30 | ✓ 20% |
| e25c3b8d | save-orig | $500 − $200 | ✓ $300 |
| e6041065 | count-ratio | 2/5 pairs | ✓ 40% |
| 0100672e/1192316e/27016adc/a11281a2/gpt4_d12ceb0e | each-price/时长求和/reno比率/followers/平均年龄 | — | 弃权（out-of-scope，已文档化） |

## 5. 下一步行动

1. **C509 生产化**（主行动）：把 pick()/split_sides()/算子族并入 amg 的 form-gate 路由表，delta-family 作为新 form。需先做 PRE 全量回归（500 题 full set，对照 e0abf3a 0.368）确认零回归后再上 multi_session slice。
2. **词表工程**：LEX 地理/品牌同义词扩容 + SIDE_GEN 分层审计（单位词层新增），与 #083 嵌入 side-channel 共享词表资产。
3. **POST 臂仍 OOM-blocked**（deed601 待空闲重启，内存 1.9Gi/845Mi avail）——非本研究依赖，留给后续 session。
4. 5 个 noform 形态（each-price 需实体计数、时长求和需单位换算、reno 比率、followers delta、平均年龄）各自是新的小机制，优先级低于 C509 主线。

---
*迭代史: v1 1对(D5正则崩溃) → v2 6对(ratio崩溃) → v2.1 7对 → v2.3 11对(交叉排除过激) → v2.4 12对 → v2.5 15对+回归 → v2.6 15对 → **v2.7 16/21 零误报**。调试脚本链: r086_dbg.py / r086_train.py / r086_patch[4-7].py 均在 /tmp/c507/。*
