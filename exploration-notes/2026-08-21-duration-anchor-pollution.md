# Research #079 — duration_sum 过求和取证：单位词锚污染与三修评估

> 2026-08-21 20:00 deep-exploration-evening · autoresearch 方法论
> 主题：HEARTBEAT Next dev targets「multi_session duration_sum 过求和（social media 59vs17、Hawaii 90vs15）」立项取证 + 修复假设 A/B
> 数据：/tmp/lme_s.json（500 题全量 haystack）+ /tmp/msagg/multi_evidence_roles.json（133 题 multi_session 切片）
> 代码：`code/duration_anchor_fix.py`（自包含，`--trace` 逐事件取证 / `--ab` 四臂 A/B，42s 含 277MB 加载）

---

## 1. 结论速览

| 臂 | 改动 | fired | fired-correct | prec | abstain-ok | hit |
|----|------|-------|---------------|------|------------|-----|
| A 生产 | — | 23 | 7 | 0.30 | 9 | 0.120 |
| **B = F1** | 单位词不作锚 | 22 | **10** | **0.45** | 9 | **0.143** |
| C = F1+F2 | + 泛词头不作传播锚 | 22 | 10 | 0.45 | 9 | 0.143 |
| D = F1+F2+F3 | + 同句对比取单值 | 22 | 10 | 0.45 | 9 | 0.143 |

**F1 单修：三个具名失败全部转正（59→17 ✓ / 90→15 ✓ / 18→8 ✓），第四题错误 fire 转诚实弃权，零正确损失**。F2/F3 在当前切片无活跃实例（零成本零增益）——C473 form-scoped 哲学再证。500 全量 duration_sum 分类的其余 6 题零回归；其中 gpt4_4cd9eba1 F1 后语义已对（'1 weeks' ≈ GT 'one week'）但被数字判分器误判——判分伪影第四案。

## 2. 根因解剖（全部实证，非假设）

### 2.1 F1：问题自带单位词是「万能噪声钥匙」
`_cnt_question_anchors("How many days did I take social media breaks in total?")` = {breaks, **days**, media, social}。`days` 不是停用词 → 任何含 "days" 的句子通过锚门：

- **social-media（GT 17，fire 59）**：真事件 = s21 "10-day break in mid-February" + s22 "a week-long break in mid-January" = 17 ✓。污染 = s38 法律会话（"Lodge the Notice of Appeal form... 28 days"、"this timeframe is 14 days instead of 28 days" = +42）——每句自带 "days" 直接放行，与 social media 主题零关联。
- **Hawaii+NYC（GT 15，fire 90）**：污染 = s17 国会程序会话（"notify congressional leaders 15 days before"、"designates... 60 days" = +75），同样全部经 `days` 放行。此前怀疑的 `city` 泛词传播（anchor_ok 旁路）**不是本例凶手**——s17 根本不在 anchor_ok 列表。
- **camping（GT 8，fire 18）**：同病，F1 后 8 ✓。

修法一行：`anchors = {a for a in anchors if a.rstrip('s') not in UNIT_ANCHOR_STOP}`（day/week/hour/month/year/minute/night/time 词族）。

### 2.2 F2：泛词地理头仍是 anchor_ok 旁路地雷
`city`（"New York City" 里的 capitalized token）混入 cap_anchors → 任何提到 "city" 的会话整体放行（其全部非意图句的时长入账）。当前 133 切片无活跃实例（幸运：9 个 anchor_ok 会话恰好无其他时长句），但 s17 型事故只差一个含 "city" + 时长的会话。修法：`cap_anchors -= {'city','cities'} | _CNT_GENERIC_HEADS`——"New York City" 仍由 `york` 锚住。

### 2.3 F3：同句对比（supersession）被读成加法
"this timeframe is 14 days instead of 28 days" 一句产出 +14 和 +28 两个事件。"A instead of B" = 替换语义（A 生效），C487「最新陈述胜」的句内同构。当前无独立活跃案例（F1 已把该句连会话逐出），**defer**。

### 2.4 完整性弃权经受住了全量考验
`_abs` 变体（Hawaii+Seattle，GT=not enough）生产正确弃权：全 haystack 无一句提及 Seattle → missing=['seattle'] → None。#075 i3 的合取完整性机制在 41 会话噪声下零误触发。

## 3. 核心概念（4）

### 3.1 单位词是「主题均匀分布词」——分布决定锚资格
"days" 出现在法律/国会/牙医/健身/飞行一切主题里。**token 的锚资格由语料内分布决定：跨主题均匀分布的词携带零主题信息**。这与 TF-IDF 的 idf 直觉同源，但在 gate 语境下是硬规则：单位词、频率词、极高频名词在锚集外。C447 的子串污染（love→lovely）是 tokenization 层的同类病——**词汇层的每次「什么算匹配」决策都需要分布证据**。

### 3.2 原型→生产的精度预算随 haystack 规模非线性坍缩
#075 原型在 oracle 证据会话（n=2~3）上 `days` 作锚零害——证据会话里含 "days" 的句子恰是真事件句。生产跑 41 会话，`days` 从无害变致命（42+75 垃圾天）。**机制的质量评估必须在生产规模 n 上做**：任何 gate 的假阳性率 × haystack 大小 = 期望噪声事件数。C477/C483 已在 full-haystack 上 A/B（所以 59/90 才被记账为失败），但 #075 原型阶段的 prec 数字不可外推——原型指标是机制上限，不是管线预期。

### 3.3 残差分桶的精度排序（修复路线图依据）
F1 后 counting 家族 fired-wrong = 12，按桶：
- **total_sum 货币族 ×4**（$2440vs185 / $56355vs5850 / $8750vs3750 / $8940vs720）——**过求和同病新器官**：total_sum 无锚门、无会话纪律，回声双计（$8750/3750≈2.33×）+ 窗口违例+ 范围违例（workshops-only）。这是 duration 锚纪律在货币域的移植需求，量化后成为 counting 族新的最大确定性 headroom。
- unit_sum ×2：driving 19vs15（计划腿混入，C483 遗留定量确认：多出的 4h ≈ 一段计划路程）+ education 4vs10（区间解析缺段）。
- number_total ×3（scale 签名漏抓 69vs99 / 跨播客 16vs27 / reach 单位 50vs12000）。
- duration_sum 残 ×1（MCU 4.5vs3.5，#075 已知事件签名去重缺口）。
- freq_days ×1（5vs4）。

### 3.4 abstain-correct 占比 47%（9/19）——负存在继续一等公民
B 臂 19 个 correct 里 9 个来自诚实弃权。aggregation 域里「算不出」与「算得出」同样值钱（insight #245 在新家族的再现），且弃权零检索成本。

## 4. 代码（可运行）

归档 `code/duration_anchor_fix.py`（`--trace` / `--ab` 双模式，含 F1/F2/F3 可切开关的 patched `_cnt_duration_sum`）。核心修法：

```python
UNIT_ANCHOR_STOP = {u.rstrip('s') for u in (
    'day', 'days', 'week', 'weeks', 'hour', 'hours', 'month',
    'months', 'year', 'years', 'minute', 'minutes', 'night',
    'nights', 'time', 'times')}

def patched_duration_sum(question, sessions, f2=False, f3=False):
    ...
    # F1: measurement units are not topical anchors
    anchors = {a for a in _cnt_question_anchors(question)
               if a.rstrip('s') not in UNIT_ANCHOR_STOP}
    are = _cnt_anchor_re(anchors)
    ...
    cap_anchors = {w.lower()
                   for w in re.findall(r"\b[A-Z][a-z]+\b", question)
                   if w.lower() in anchors}
    if f2:   # F2: generic heads can't propagate sessions
        cap_anchors -= {'city', 'cities'} | _CNT_GENERIC_HEADS
    ...
    durs = _cnt_durations_days(sent)
    if f3 and len(durs) > 1 and CONTRAST_RE.search(sent):
        durs = durs[:1]   # "14 days instead of 28" = supersession
```

取证模式输出（--trace，逐事件溯源到句）：

```
[SOCIAL-MEDIA GT=17] anchors=['breaks', 'days', 'media', 'social']
    EV s21 + 10.0 [10-day] ...cut down on social media... 10-day break
    EV s22 +  7.0 [a week] ...week-long break from it in mid-January
    EV s38 + 28.0 [28 days] Lodge the Notice of Appeal form...
    EV s38 + 14.0 [14 days] ...14 days instead of 28 days.   <- F3 残差类
    EV s38 + 28.0 [28 days] (同句第二匹配)
  production = '59 days'   F1-patched = '17 days'
```

## 5. 关键洞察（4）

1. **问题文本里最高频的词是问题自己的单位词**。"How many days..." 的锚集必含 "days"，而 days 是全语料主题均匀词——**提问词汇法与锚提取在单位词上必然自噬**。这不是 bug 是结构：任何「从问题词构造证据过滤器」的机制（检索 query 构造同族！）都要先剥掉问题自身的量纲词汇。C473「form 分类器即配置面」在此具体化为：**form 决定 unit，unit 必须从 anchor 词汇表中扣除**。
2. **原型上限 ≠ 管线预期，规模是精度的隐变量**。#075 oracle prec 0.67 → 生产 arm A prec 0.30：差距不在机制移植，在 haystack 3→41 会话的假阳性放大。方法论修正：原型阶段就该在噪声注入（全 haystack）口径下报 prec，否则集成 A/B 一定会「突然」发现整族失败。这也解释了 C477→C483 为什么每轮都在 full-haystack 上重验——该纪律本次再产出 +3。
3. **判分伪影第四案：GT 单词数字**。gpt4_4cd9eba1 F1 后预测 '1 weeks'，GT 'one week'——语义已对，digit 正则判错。继答案侧（幻影命中）、类目侧（_classify_question 419/500 误标）、GT 句子侧（首数字主张）之后，GT 词汇侧第四处。发布前判分器审计清单再 +1：GT word-number 归一化（one→1）。
4. **「同病异器官」是修复路线的优先级信号**。total_sum 4 题与 duration_sum 3 题共享过求和病理（回声/窗口/范围违例）但器官不同（无锚门 vs 有锚门）。把已验证的器官（锚纪律/会话签名去重/意图门）移植到缺失器官，比在新器官上发明新机制便宜——**机制的边际成本递减，且移植自带 A/B 方法论**。

## 6. 下一步行动

1. **[C490 规格] F1 落地生产** `_cnt_duration_sum`（+F2 一行 hardening，诚实标注零实测增量）：锚集扣单位词族；全量 suite + 官方 dual-judge 真实管线 A/B（C481 协议）；预期 multi_session fired-prec 0.30→0.45、temporal-133 零翻转。F3 defer 至出现活跃案例。
2. **[C491 候选] total_sum 货币族过求和取证**：4 具名题（$2440/$56355/$8750/$8940），同一 trace 方法论；假设桶 = 回声双计（签名去重移植）+ 时间窗解析+ 范围门。修复后 counting 族 headroom 移至 unit_sum driving 计划/事实。
3. **[判分器] GT word-number 归一化**（one/two/three... → digits），四处伪影清单收口。
4. **[记录] 参照非时长残差类**（"three weeks ago" 时点参照 / "one day" 愿景 / "once a week" 频率）：当前被锚门侥幸挡住，锚门收紧后任何一类的活跃 fire 都该回到这个清单。

## 7. 质量自评

- ✅ 可运行代码：duration_anchor_fix.py 自包含双模式，实测 --ab 42s / --trace 38s，四臂数字可复现
- ✅ 独到见解：单位词=主题均匀词的分布资格判据 / 原型-生产规模坍缩（精度预算公式）/ 判分伪影第四案 / 同病异器官移植论
- ✅ 项目关联：直接产出 C490 实现规格 + C491 立项素材；与 C447（子串污染）、C473（form 即配置面）、C477/C483（分层接入/单位纪律）、#075（原型谱系）七代衔接
- ✅ autoresearch 纪律：A/B 四臂全记录，F1 keep / F2 hardening / F3 defer 有判据；零回归在 133 切片 + 500 全量 duration 分类双口径验证
- ⚠️ 局限：133 切片上的 GT-first-number 判分与 C481 官方 dual-judge 口径未完全对齐（C490 落地时用官方协议复核）；arm 表初版把 abstain-correct 混入 precision 已修正（0.86→0.45 的诚实数字）
