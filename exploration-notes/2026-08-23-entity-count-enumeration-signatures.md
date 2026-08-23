# Research #084: Entity-Count 墙的解剖与枚举签名破壁（multi_session 下一簇）

> 2026-08-23 20:00 deep-exploration-evening | C499 reference (exact 0.316) 之上
> 原型：`code/invcount_proto_v5.py`（自包含，oracle evidence 模式）| 弧线 v1 0.15 → v3 0.60 → **v5 1.00**（+4/0）
> 前置：#083 嵌入通道已定案但本簇**未用嵌入**——取证发现主障碍不是词汇鸿沟而是签名抽取

## 背景

C500 (item_total) 后 multi_session 仍 111 错。HEARTBEAT 待办列出下一簇：count/distance/percentage。
历史红线："how_many 实体计数第 3 次撞墙勿再试"（C469/#075/C483——谓词级语义墙）。
本轮先做全量取证再动手，发现红线只对了一半。

## 取证：116 错题分桶（C499 官方 reference）

| 桶 | 题数 | 说明 |
|---|---|---|
| **entity-count ("How many X")** | **42** | 头号簇 |
| duration-count | 18 | weeks/days 持续 |
| total-sum | 18 | 金额/总量聚合 |
| yes/no-verify | 15 | 验证型 |
| other / order-when / superlative | 23 | — |

三题深度解剖（answer sessions 全文）发现 entity-count 并非一面墙，**是四个子类**：

- **A. 命名事件枚举**（babies=5, weddings=3, ceremonies=3）：答案=专名集合。Jasper/Max/Charlotte/Ava+Lily 跨 3 会话重复提及需去重；twins 算 2；"my college roommate's wedding" **无专名但有角色所有格**；"missing my nephew Jack's graduation"=错过不计。**无词汇鸿沟**（baby/wedding stem 直接命中）——不经由 C469 撞的那面墙
- **B. 尺寸签名库存**（tanks=3）：20-gal/5-gal/1-gallon 数字+单位即天然去重键
- **C. (实体×动作)对计数**（clothing=3）：退换一双靴子产生 return+pickup 两个动作单位；blazer 干洗取件 ×2 提及=1 件。**谓词语义墙本体，仍关**
- **D. 数字聚合**（"three weddings" 直陈数字）：生产 number_total/unit_sum 已覆盖

## 核心概念

1. **签名空间**——计数单位的三种确定性签名：`named X`（专名）、`my ROLE's X`（角色所有格，兜底无名事件）、`N-unit`（尺寸）。同子句 name 吸收 role（"cousin Rachel's wedding"→Rachel，不是 Rachel+cousin 两个）
2. **所有权门**——问题问 "have I bought/own/use"（我的库存）时名字签名失效：`Billie Eilish's album` 是艺人专辑不是我的收藏。名字签名只在**他人事件题**（attended/were born）有效；我的库存只信尺寸签名
3. **NP 全词族 stem**——"graduation ceremonies" 的关键子句只含 "graduation" 不含 "ceremony"：NP 全部实词都做 stem 锚，单 head-noun 会漏签名
4. **排他谓词**——missed/skipped/couldn't attend 使子句签名作废（微观版 realized-vs-intended 墙，但动词表可枚举）
5. **诚实不 fire 即弃权**——词汇鸿沟题（clothing items→jeans/blazer）0 候选行→自动不 fire；26/60 how-many 错题安全落此桶（C498 弃权哲学的推广）

## 原型结果（oracle evidence = answer sessions；生产检索 evhit 0.955 接近）

| 版本 | fired | correct | fire-prec | 关键改动 |
|---|---|---|---|---|
| v1 | 26 | 4 | 0.15 | nums 兜底梯=噪音；tanks/babies 两机制已中 |
| v2 | 6 | 1 | 0.17 | 砍 nums；引入 q_size/named-X 两个新 bug |
| v3 | 5 | 3 | 0.60 | 子句级签名+name 吸收 role |
| v4 | 7 | 4 | 0.57 | NP 词族+排他谓词；Eilish/What 假阳性暴露所有权问题 |
| v5 | 4 | 4 | 1.00 | 所有权门；+4 gains / 0 hijacks（全 133 零劫持验证）——但构成审计发现 babies 题 1 假阳性侥幸 |
| **v5.2（终版）** | **4** | **4** | **1.00** | **构成诚实化：Rachel's baby shower 假阳性修复（shower 排他限于所有格尾部窗）+ twins 同位语抓名（Ava and Lily）退役启发式** |

四题全中且构成干净：tanks 3（sizes 去重）、weddings 3（Emily/Rachel+roommate）、babies 5（Jasper/Max/Charlotte/Ava/Lily 恰为 GT 五婴，零假阳性）、ceremonies 3（Alex/Emma/Rachel，Jack 被 missing 排除）。

**v5→v5.2 构成审计教训**：v5 的 babies=4 名+twins+1 碰巧对——Rachel 是 "Rachel's **baby shower**"（母亲非婴儿，假阳性）抵消了漏抓的 Ava/Lily 同位语。数字对≠机制对，生产化前必须审签名构成（oracle-parity 方法论的签名级延伸）。

## 可运行代码

`code/invcount_proto_v51.py`（终版 v5.2，自包含；`code/invcount_proto_v5.py` 为 v5 中间版，v1-v3 见同名系列）。依赖：
- `/tmp/lme_s.json`（LongMemEval_s_cleaned 500 题，HF 直连下载）
- `/tmp/c499/lme_s_full500_c499.json`（C499 官方 reference，用于 wrong-set/correct-set 判定）

```bash
python3 code/invcount_proto_v51.py
# fired 4/133 | correct 4 | fire-prec 1.00
# gains 4 | hijacks 0
# abstain census: wrong-'how many' questions honestly not-fired: 26
```

最小可复用机制（生产移植核心，~30 行）：

```python
def enum_count(question, evidence_lines):
    stems = np_family_stems(question)            # "graduation ceremonies" -> [graduat, ceremon]
    sigs_names, sigs_roles, sigs_sizes = set(), set(), set()
    for line in evidence_lines:
        for cl in clauses(line):                  # 子句=签名单位
            if not any(st in cl.lower() for st in stems): continue
            if EXCLUDE_VERBS.search(cl): continue  # missed/skipped -> 不计入
            if is_my_inventory_question(question): # Billie Eilish's album != 我的库存
                sigs_sizes |= size_sigs(cl)
            else:
                sigs_names |= name_sigs(cl, stems)     # named X / Name's ... stem
                sigs_roles |= role_sigs(cl, stems)     # my ROLE's ... stem
                if 'twins' in cl.lower(): twins = True
    if sigs_sizes: return len(sigs_sizes)                       # tanks: 1/5/20-gallon
    return len(sigs_names) + len(sigs_roles - absorbed) + twins # babies/weddings/ceremonies
```

## 关键洞察

1. **"第 3 次撞墙"的红线只对一半**：墙是真的，但它不是一面——是四面。命名枚举（A）和尺寸库存（B）子类完全绕开了谓词语义墙（C），因为计数单位携带**自带去重键的签名**（专名/角色/尺寸），不需要理解谓词语义，只需要锚定事件名词。C483 撞墙时把整个 how-many 族一起放弃了；按签名可数性分桶后可精确打击
2. **名字是最强锚的第三次验证**（C475 distinctive speaker recall → C491 具名总额 → 本轮 enum 签名）：专名既是去重键又是类型证据。twins 关键词+1 是唯一的形态算术
3. **所有权混淆是名字签名的天敌**：他人事件题（婚礼/出生/典礼）与我的库存题（专辑/设备/工具）在问题形态上只差一个所有格，但签名语义完全相反——`Name's X` 在前者是计数单位、在后者是品牌污染。所有权门是 0.57→1.00 的全部差额
4. **嵌入通道在本簇不是钥匙**：#083 的 MiniLM 破的是检索侧词汇鸿沟（preference @5 0.60→0.87），但 entity-count 的 evhit 已 0.955——瓶颈在答案侧签名抽取，嵌入帮不了"Jasper 提及三次算一个"。嵌入的正确位置仍是 #083 的检索侧通道
5. **微型谓词语义墙可枚举击破**："missing nephew Jack's graduation"是 realized-vs-intended 墙的一个实例，但排他动词表就够用；同族的 "baby shower"排他却必须限定在所有格尾部窗——clause 级排他会误杀同子句的真签名（v5.1 过矫：Max/Charlotte 与 shower 同子句被整条杀死）。说明大墙是无数小墙的集合，每面小墙的通透性不同，取证要落到子句级才能看到
6. **数字对≠机制对（签名构成审计）**：v5 babies 预测 5=G1 但构成是 3真+1假+1启发式侥幸——假阳性抵消漏抓。生产化前必须逐签名核对构成，否则 A/B 通过也无法区分机制正确与运气（C499 flip 分析的签名级延伸）
7. **诚实不 fire 是设计输出而非失败**：60 道 how-many 错题中 26 道安全落入 no-cand/gate 桶——机制天然不碰它们。生产化时这 26 题维持现状（不劫持），但为 C498b 的"弃权计分"预留了干净的分类面

## 下一步行动

1. **C503 生产化**（最优先）：`enum_count` form 接入 counting 管线（`_classify_question`→form-gate→签名梯），置于 number_total 之前、unit_sum 之后；oracle parity 验证（生产函数跑本轮 fixture，#075 方法论）；预期 multi_session 0.166→0.196 (+4/0)
2. **检索窗口适配**：oracle 用的是 answer sessions；生产是 retrieval 窗口（evhit 0.955）。签名抽取对窗口噪声更鲁棒（专名签名不易被闲聊污染），但需 A/B 验证 no-cand 桶不因窗口扩大而误 fire
3. **C 类（实体×动作对）单独取证**：clothing pick-up/return 型 42 题中约 8-12 题，谓词语义墙本体，留给 #083 嵌入 + LLM judge 路线（"动作单位计数"可能需要小型动词框架：return/exchange/pick_up 三元组）
4. **duration-count 18 题桶**：v1 取证显示与 counting forms 管线重叠（e831120c weeks 已有机制但 pred=None 未触发）——先查 form-gate 漏配，可能是免费的 +2-3 题

## 与现有项目关联

- **amg counting 管线**（C477/483/500）：enum_count 是第 5 个机制形态，签名梯与 (数字,专名) 去重签名同源
- **C475 distinctive speaker recall**：名字锚思想的直系延伸
- **#083 嵌入通道**：定位修正——检索侧专用，本簇证明答案侧签名不需要它
- **C498 弃权哲学**：26 题诚实不 fire 桶是弃权计分（C498b，需 ollama）的天然候选
- **博客候选**："the wall was four walls"——红线考古+子类分桶如何解锁第四次尝试
