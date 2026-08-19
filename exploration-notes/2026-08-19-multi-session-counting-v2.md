# Research #075 — multi_session counting v2：三修一加实装与精度换血

> 2026-08-19 20:19 deep-exploration-evening · autoresearch 方法论
> 主题：Research #071 原型（8.5×）的「三修一加」落地迭代 + What-路由扩展
> 数据：/tmp/msagg/multi_evidence_roles.json（133 题 multi_session，oracle evidence sessions）
> 代码：`code/msagg_proto_v2.py`（自包含可运行，`python3 msagg_proto_v2.py [--wrong]`）

---

## 1. 结论速览

| 版本 | fired | correct | hit | precision | 判定 |
|------|-------|---------|-----|-----------|------|
| v1 (#071) | 32 | 9 | 0.068 | 0.28 | baseline |
| i1 激进版（cluster 覆盖一切） | 58 | 15* | 0.113 | 0.26 | **回退**（*含 2 个判分幻影；43 个错误 fire） |
| i2 保守版（月份域+紧实例） | 24 | 12 | 0.090 | 0.50 | 保留方向 |
| **i3 终版（NP-全词族+判分修正）** | **28** | **12** | **0.090** | **0.43** | **保留** |

**hit 0.068→0.090（+32% 相对），precision 0.28→0.43（+54% 相对）**。未达 #071 设定的 0.15 目标——但换取了精度翻倍与结构化弃权语义（下详）。目标 0.15 的缺口分析见 §5。

## 2. 核心概念（5）

### 2.1 会话锚传播只对专名安全（activity 词污染）
Hawaii 题的 "10-day" 句不含任何锚词（"With my family, we had to plan everything out for the 10-day..."），句级锚过滤会丢掉它；解法是把锚匹配传播到会话级。但 camping 题立即反噬：'camping' 一词出现在讨论 Utah 公路旅行/New Zealand 装备的会话里，会话级传播把 7-day Utah（非 camping）放进来（pred 8→15）。**修法：只有问题中以大写形式出现的锚（Hawaii/NYC/Seattle）才允许会话级传播**——专名锚标记"主题纯"的会话，活动词锚不标记。这与 C473 的教训（检索超参不可全局调优）同族：**作用域本身是需要学习的超参**。

### 2.2 量纲黑名单是数字域的词边界防御
"20-gallon community tank" 中 20 是容积修饰语不是 tank 计数。数字紧跟测量单位（gallon/lb/mph/mile/...）→ 测量修饰，跳过。这是 C447 子串污染（love→lovely）在数字域的精确同构：**"N-unit + noun" 结构中 N 修饰的是 unit 不是 noun**。修后 tanks 题 explicit 路径正确关闭，交给实例簇（1-gallon/5-gallon/20-gallon 三个 scale 签名 = GT 3 ✓）。

### 2.3 实例计数的三个证据方向（bidirectional instance anchoring）
具名实例出现在三种句法位置，单方向抓不全：
- **前置修饰**："my black **Fender Stratocaster** electric guitar"（CAP run + 名词）
- **同位语后置**："my acoustic guitar, a **Yamaha FG800**"（名词 + apposition）——单看向前窗口永远抓不到
- **规模签名**："1/72 scale **B-29** bomber"、"5-piece **Pearl Export**"——N/N-scale、N-piece、N-gallon 这类规模标记是强实例指纹，甚至能豁免句族过滤（Tiger I tank 句不含 kit/model 词仍可计数）
另外：**处置意图保留所有权**——"thinking of selling my old drum set" 里的 Pearl Export 必须计入（GT 4 含它）；获取意图才排除。C469 的 realized-vs-intended 墙在**答案侧计数**里细化为"获取意图排除、处置意图保留"。

### 2.4 合取完整性弃权（conjunction completeness abstention）
"plants for tomatoes **and** cucumbers"：番茄 5 + 黄瓜 3 = 8 ✓；但 chili 变体里 chili 从未与 plants 共现 → 子类型缺失 → **不 fire**（GT 恰是 information-not-enough）。同构应用于地点合取："traveling in Hawaii **and** in Seattle"——Seattle 零事件 → 弃权（GT 也是 not-enough）。**合取问题的每个合取支都要有证据，缺支即弃权**——这是 C457 "unresolved anchor 不伪造"在聚合域的推广，本次实测两次命中 GT 的弃权语义。

### 2.5 句子型 GT 的判分陷阱（phantom correct）
GT 为完整句子时（"I currently own 4 musical instruments. I've had ... for 3 years"），子串判分让 pred='3' 侥幸命中 GT 里的 "3 years"。i1 的 15 个 correct 里 2 个是此类幻影。修法：句子型 GT 抽取**首个数字主张**（five→5.0）。这与 C465-467 的度量效度发现同谱系——**零 LLM 协议的 exact 判分在答案侧、类别侧、GT 侧三处都有伪影**，发布数字前必须三处都修。

## 3. 实验链（keep/rollback 全记录，autoresearch 纪律）

| 轮 | 改动 | 结果 | 判定 |
|----|------|------|------|
| i1 | 三修一加全套 + What-路由 + cluster 覆盖所有类别 | 15/58=0.113 但 prec 0.26 | **回退**（噪声 fire 换 hit，且 2 幻影） |
| i2-F1 | 锚传播置于收集前（顺序 bug） | Hawaii 10-day 找回 | keep |
| i2-F2 | 锚改词边界匹配（'star'∈'started' 子串 bug） | MCU 家族句修正 | keep |
| i2-F4 | 实例抽取大清洗（缩写/月份/星期/句首词 + 邻接约束 + CLUSTER_OK 白名单） | entity fired 34→5，**过保守** | 部分保留 |
| i2-F5 | 单位头名词墙（hours/minutes/pages/points/times → None） | -8 错误 fire，0 正确损失 | keep |
| i2-i3 | NP 全词族（"museums or galleries" 两词都入族；千分位数字） | number_total 0→2 correct | keep |
| i3-F | 判分 GT 首数字主张 | 揭穿 2 幻影 | keep |
| 实验 | CLUSTER_OK 扩至 venue/event 类 | 0 变化（Art Cube 类邻接仍抓不到） | 弃（venue+date 键才是正解，见 §6） |

正确机制清单（12 个 correct 的构成）：duration 4（camping-锚+意图门 8✓ / Japan-日期区间 11✓ / Hawaii-会话传播+合取弃权 15✓ / social-media 17✓）；total_sum 4（v1 机制零回归）；number_total 2（siblings 3+1=4✓ 等）；entity 1（tanks scale 签名 3✓）；argmax 1（TikTok follower 聚合✓）。

## 4. 代码（可运行）

归档 `code/msagg_proto_v2.py`（自包含，含 eval harness 与 --wrong 取证模式）。核心——合取完整性弃权 + 量纲黑名单：

```python
UNIT_BLACKLIST = {'gallon', 'pound', 'lb', 'mph', 'mile', 'kg', 'ounce', ...}

def entity_count(question, sessions):
    fam, subtypes = _np_fam(question)          # NP 全部内容词入族
    ...
    for em in NUM_ADJ_FAM.finditer(sent):      # "N ... <fam-noun>"
        n = _num(em.group(1))
        after = sent[em.end(1):em.start(2)].strip().lower().strip(' -')
        parts = after.split()
        if parts and parts[0].rstrip('s') in {u.rstrip('s') for u in UNIT_BLACKLIST}:
            continue                            # ② "20-gallon tank" = 测量修饰
        if subtypes:                            # ⑧ 合取子类型归账
            st = next((s for s in subtypes if re.search(r'\b'+s+r's?\b', low)), None)
            if st: subtype_counts[st].append(n)
        else:
            explicit_counts.append(n)
    if subtypes:                                # 合取完整性：缺支 → 弃权
        vals = [max(subtype_counts[s]) for s in subtypes if subtype_counts.get(s)]
        if len(vals) < len(subtypes):
            return None                         # chili 从未出现 → 不伪造
        return str(int(sum(vals)))              # 5 + 3 = 8
```

duration 侧的会话锚传播 + 意图门 + 日期区间（三个 fix 的协作）：

```python
# F1: 专名锚才会话级传播（'camping' 出现在装备会话 → 不传播；'Hawaii' → 传播）
cap_anchors = {w.lower() for w in re.findall(r'\b[A-Z][a-z]+\b', question) if w.lower() in anchors}
...
for si, sent in _sents(sessions):
    if sent.endswith('?') or INTENT_RE.search(sent):   # ⑤ 计划≠已发生（C469 墙的缓解）
        continue
    if are and not are.search(sent) and not sess['anchor_ok']:
        continue
    for days, _ in extract_durations_days(sent):       # 含 full-day/all-day = 1
        sess['events'].append(round(days, 1))
    dr = extract_daterange_days(sent)                  # ⑦ "April 15th to 22nd" = 7 天
    if dr is not None:
        sess['events'].append(round(dr, 1))
```

## 5. 关键洞察（5）

1. **聚合机制的精度-覆盖曲线比斜率重要**。i1（覆盖优先）与 i3（精度优先）correct 只差 2-3，但错误 fire 差 30。在真实管线里 fall-through 答案本来就几乎全错（exact 0.007），所以纯 hit 视角 i1 更优；但**可审计的确定性机制一旦错误 fire，用户对整个机制的信任崩塌**——Mem0 的 93.4 自称分与独立复现 49-73.8 的落差就是前车之鉴。精度优先 + 显式弃权是 amg 差异化定位的正确取舍。
2. **"How many" 的可解子集边界现在有了实测地图**：可解（显式自报计数/规模签名实例/金额求和/日期区间）；不可解零 LLM（re-watch 谓词、pages-left 差算、habitual hours、抽象类目金额 luxury、指代实例 "that one in Cedar Creek"）。48 题 entity_count 里 ~20 题属后者——**这不是工程缺口，是 KBQA 20 年前就知道的谓词语义墙**（C455/C469 之后第四面同族墙的实证地图）。
3. **日期区间是免费的 duration 证据**："from April 15th to 22nd" 一类表达不含 day/week 词，v1 全漏；解析后 Japan 题 4+7=11 ✓（且 22-15=7 的排他计数约定与 GT 默认口径一致——C471 round-half-up 教训的再次印证：**约定要拟合数据，不要凭直觉**）。
4. **实例计数的下一步不是更好的 regex，是换 key**：venue+date 复合键（"Natural History Museum on 2/8"）一次解决 museums-Feb（2✓）与 museums-Dec（0→弃权✓）两题；couple 键（"Sarah and Tom's wedding"）解决 weddings。邻接句法分析在 45 字符窗口里 whack-a-mole，事件签名键才是稳定抽象——与 C445 resolve_entity_variants 的"变体合并"哲学一致。
5. **判分器与研究机制必须同步开发**（#071 教训重演+扩展）：本轮又发现 GT 侧幻影（句子型 GT 的子串命中）。三处伪影（答案句选择/类目标签/GT 解析）已全部实测定位——**零 LLM 基准的 exact 数字在发布前需要一道"判分器审计"清单**，这是博客候选 "when the metric can't fire" 的续篇素材。

## 6. 下一步行动

1. **[C474 规格更新] 分层接入**：prec≥0.5 的机制先入管线（duration_sum 0.67 / total_sum 1.00 / number_total 0.50 / argmax 0.50 ≈ 11 correct 的机制族），entity_count 保持原型级（0.20）等 venue+date 键重构。形式触发沿用 C456/C457/C473 模式（detect_form 即配置面）。
2. **[v3 候选] venue+date / couple 复合事件键**：替换邻接窗口抽取，预计 museums×2 + weddings + art-events 4 题回归正确；同时给 duration 的 MCU 残余（4.5w vs 3.5w，多出一个 7 天事件）做同款事件签名去重。
3. **[管线 A/B] oracle→真实检索**：机制族接 per-question-haystack 评估器（C454 基建），天花板 = oracle hit × evhit 0.955 ≈ 0.086 overall 贡献——multi_session 轴 exact 0.007→~0.08+ 的量级提升。
4. **[叙事] 博客三部曲第三篇素材就绪**："检索不是记忆"——evhit 0.955 vs exact 0.007 + 本轮精度-覆盖曲线 + 四面零 LLM 墙地图。

## 7. 质量自评

- ✅ 可运行代码：msagg_proto_v2.py 自包含（5 轮迭代全记录于文件头注释），A/B 与 --wrong 取证模式内置
- ✅ 独到见解：专名锚传播的纯度条件 / 处置意图保留所有权 / 合取完整性弃权 / GT 判分幻影第三处 / 精度-覆盖取舍论证
- ✅ 项目关联：直接更新 C474 实现规格（分层接入 + venue+date 键）；与 C445/C447/C456/C457/C469/C471/C473 七代机制谱系衔接
- ⚠️ 局限：hit 0.090 未达 0.15 目标（缺口 = venue 键未实装 + MCU 去重残余 + avg 双题未调）；56+ 题小样本上的超参（UNIT_BLACKLIST、CLUSTER_OK、45 字符窗口）需 full-500 验证；oracle 口径尚非管线口径
