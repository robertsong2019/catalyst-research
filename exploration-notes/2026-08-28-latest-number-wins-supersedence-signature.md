# Research #091 — latest-number-wins：supersedence 签名与答题时 recency 仲裁

**日期**: 2026-08-28 20:00 (deep-exploration-evening)
**触发**: HEARTBEAT 关键路径 #3 首位 — "latest-number-wins（a2f3aa27 "1250→1300 followers"，数字行内 recency 比较，40+ 题人口，C524 首选但风险高一档）"→ 风险高一档 → 研究先行（C512 教训：机制投影前先摸清触发面）
**状态**: ✅ 完成 — 文献栈 5 篇 + 零依赖原型 12/12 全绿

---

## 一、问题定义

LME kupdate 形态（真实题 a2f3aa27）：session 2 说 "I hit 1250 followers"，session 8 说 "1300 followers now"。问 "How many followers does Alex have?"——两条都检索得到、都无矛盾标记，正确答案是 **seq 更大的那条**。amg 现状：检索/rerank 按相关性排序，旧值可能因"更中心"而压过新值；C523 quant_rerank 已用 (-hits, -seq) 在数量子型上买了"kupdate 新值优先"，但那是 rerank 启发式，不是显式的版本判定。

核心难题不是"选最新的"（排序容易），而是**"什么时候两个数值是同一事实的两个版本（supersedence），什么时候是两个共存的不同事实（coexistence）"**——选错方向的代价双向：
- **该合不合（miss）**: 应选新值却两值并存 → 答旧值或随机
- **不该合硬合（hijack）**: Raj 的 1250 followers 与 Priya 的 1300 followers 被错误判为同一事实版本 → 人名域被劫持

这就是"风险高一档"的来源：quant_rerank 只在"数量型且 top 行无数字"时触发，latest-number-wins 要面对任意数值行，触发面大一个数量级。

## 二、文献栈（5 篇核心）

### 1. Rasmussen et al., 2025 (Zep/Graphiti) — "A Temporal Knowledge Graph Architecture for Agent Memory"（arXiv:2501.13956）
- 生产级时序记忆的参照实现：**bi-temporal 边 + 写时失效**。每条边 4 个时间戳：valid_from / valid_to / observed / recorded——世界为真时间与系统已知时间分离（SQL:2011 bitemporal 的记忆版）
- **核心机制：矛盾不覆写（contradictions invalidate, they do not overwrite）**——新信息与旧事实矛盾时，旧边 valid_to 被关闭，历史完整可审计。"A graph that can't represent when a fact was true will eventually serve an agent two contradictory facts and let it pick — the single most common cause of agent hallucination"
- LongMemEval +18.5%、延迟 −90%——时序处理不仅提分还省 token
- 代价：**失效判定发生在写入时**，需要 LLM 抽取矛盾对；amg 的 append-only 会话流走答题时确定性仲裁可以零 LLM 成本拿到同款效果（见洞察 1）

### 2. Piryani, Mert & Jatowt, 2026 (RecencyQA) — "How often do Answers Change? Estimating Recency Requirements in QA"（arXiv:2603.16544）
- **recency–stationarity 二维分类学**：(i) 答案多久变一次（小时/年/永不）× (ii) 该更新频率是 context-invariant（stationary）还是 context-dependent（non-stationary）
- 首个同时标注 recency + stationarity 的数据集（4,031 题）；实证：**non-stationary 题显著更难，且更新频率越高越难；给非平稳题注入时间上下文增益 >+40%**
- 关键概念工具：**recency demand 是问题的属性，不是事实的属性**——"Twitter CEO" 低频平稳，"美国通胀率" 高频且非平稳。amg 的 form 分类器（12 counting forms）天然是 recency demand 的载体：counting form 的 recency 语义应该进签名
- 数据集表单确认谱系：TimeQA 20k / SituatedQA 12k / TempLAMA 50k / StreamingQA 410k / FreshQA 600 / PATQA 6,172

### 3. Dhingra et al., TACL 2022 (TempLAMA) — "Time-Aware Language Models as Temporal Knowledge Bases"
- 时序知识的诊断数据集（50k）：专挑**答案随时间变化的关系**，用 temporal scope（[begin, end]）标注每个事实的有效窗口
- 证明：给 LM 输入注入时间戳（timestamp conditioning）能系统性改善时序事实的记忆与检索
- 对 amg 的映射：LME haystack 的 session 序就是 timestamp conditioning 的离散版——**"在什么时候说的"必须进检索特征**，amg 的 bi-temporal APIs (5) 已有存储面，缺的是答题面的消费

### 4. Vu et al., 2024 (FreshQA/FreshLLMs, Findings ACL) — "Refreshing Large Language Models with Search Engine Augmentation"
- 新鲜度四分类：never-changing / slow / fast / **false-premise**。false-premise 类是"前提已失效"的题——与 amg 弃权家族（C448-C516）的 presupposition-failure 形态完全同构
- 持续更新基准的设计：ground truth 本身随时间漂移，评测器必须知道"答案的版本"
- 对 latest-number-wins 的启示：**有些题的正确行为不是选版本而是宣布前提死亡**——kupdate 里 "not anymore" 后的提问，答案不是任何历史值

### 5. Zhang & Choi, 2021 (SituatedQA, NeurIPS D&B)
- 同一问题在不同 temporal/geographic 语境下答案不同（12k）："Who won the last FIFA World Cup" 按 context year 换答案
- 把"语境决定答案"从时序维正式化——与 #090 的问题盲缺陷、amg form-gated 哲学三度收敛：**答案不是句子的函数，是 (句子, 语境) 的函数**
- 补充：EMNLP 2023 "Mitigating Temporal Misalignment by Discarding Outdated Facts" 给出可预测"事实易变度"（fact-changeability）的路线——易变事实才需要版本管理，稳定事实无须操心

## 三、核心概念

1. **Supersedence 签名（supersedence signature）**: 判定"两个数值行是否同一事实的版本"的三元组 **(canonical entity, normalized predicate, unit domain)**。三要素全同 + 数值不同 = 版本冲突（新 seq 胜）；任一不同 = 共存事实（互不劫持）。单位语义域直接继承 #090 判分侧结论（time 归一化可合并、currency/distance 按币种/单位分域不换算）——**判分侧的单位纪律搬到检索侧变成版本边界**，一个洞察两处落地。
2. **写时失效 vs 答题时仲裁（write-time invalidation vs answer-time resolution）**: Zep 在写入时用 LLM 判矛盾并关窗——每个写入付一次判定成本，查询时干净；amg 走答题时：append-only 保存一切，查询时按签名分组取 max(seq)——零写入成本、全链审计，代价是签名碰撞风险（census 可测）。**amg 的会话流天然是 transaction time 轴，seq 就是免费的系统时钟**。
3. **撤回不是覆写（retraction is not overwrite）**: 显式撤回（"I don't rent in Tokyo anymore"）不带新值时，正确行为是 **INVALIDATED → 弃权**，绝不是回吐旧值。只有当撤回之后又出现新事实，撤回才被取代。这是 FreshQA false-premise 类 + amg 弃权弧线（C513 presupposition failure is an answer）在版本管理里的直接延续：**版本链的终端可以是"无"，而"无"必须显式表达**。
4. **域多义交给问题（domain ambiguity delegates to the question）**: "$90k salary" 与 "€90k salary" 共存不互斥；问 "how much does he earn" 无单位提示 → MULTI_DOMAIN 弃权或列表返回；问 "in dollars" → 域被问题选中。"the question is the join condition"（#086 博文候选）的又一实例：**问题的单位提示是版本仲裁的第四个输入**。
5. **Recency demand 分型（per-form recency semantics）**: RecencyQA 证明 recency 需求随问题类型变化。amg 12 个 counting form 天然携带 recency 语义——latest-number-wins 不该是无差别的全局重排，而应 **form-gated**（与 C506 嵌入 side-channel 的 form-gate 同构）：只在 recency 敏感 form（数量当前值型）启用，历史对比型（"how many followers did he have in session 2"）反而要禁用。

## 四、可运行代码

**文件**: `code/fact_versions.py`（零依赖 Python 3.10+，~240 行，含 12 用例自测）

```python
from fact_versions import Fact, Retraction, resolve, resolve_with_hint

facts = [
    Fact("alex", "followers", 1250, "count", 2, "s2", "I hit 1250 followers"),
    Fact("alex", "followers", 1300, "count", 8, "s8", "1300 followers now"),
]
r = resolve(facts, [], "alex", "followers")
# → Resolution(status='LATEST_WON', value=1300, superseded=[{value:1250, seq:2,...}])

# 显式撤回 → 弃权而非旧值
resolve([Fact("lee","rent",1200,"$",3,"s3")],
        [Retraction("lee","rent",9,"s9","moved out")], "lee", "rent").status
# → 'INVALIDATED'（answerable=False）

# 单位域隔离：$ 与 € 共存，问题提示选域
resolve_with_hint(facts=[...$90k..., ...€90k...], [], "kim", "salary", "usd").domain
# → 'currency:usd'
```

三层结构：`unit_domain()`（值+单位 → 语义域+规范化值，time 换算 / currency·distance 分域）→ `_signature()`（三元组 supersedence 签名）→ `resolve()`（按签名分组 → 撤回检查 → max(seq) 胜出，superseded 链全程保留）。

**实测 12/12 全绿**（2026-08-28 20:07），用例覆盖：
- 6 credit 形态：1250→1300 版本冲突（LME 原题形态）、2h≡120min 时间归一化、值不变重复（NO_CHANGE 非冲突）、$90k/€90k 域多义 + 单位提示选域、递进链全审计（70→68→65kg）、撤回后新值胜
- 6 non-credit 防御：显式撤回无替代 → INVALIDATED、撤回早于事实无效、followers/following 谓词劫持陷阱、Raj/Priya 实体劫持陷阱、5 miles/8 km 距离分域、空集门前弃权

## 五、关键洞察

1. **版本判定应该发生在答题时而不是写入时（对 amg 而言）**: Zep 写时失效要为每次写入付 LLM 矛盾判定，且判定质量锁死在写入那一刻（误杀不可逆，只能靠 valid_to 重开窗补救）；amg 的 append-only 会话流 + seq 时钟让答题时仲裁变成确定性分组排序——**零 LLM、可单测、superseded 链天然审计**。C512 已证过一次"写时摊销未必赢"（嵌入摊销 1.02× 回退），这次是同一原理的反向案例：写时省下的查询成本 < 答题时签名分组的确定性收益。
2. **"风险高一档"的解药是签名而不是阈值**: HEARTBEAT 标注 latest-number-wins 风险高，因为直觉实现（数字行 recency 重排）无法区分"新值"与"另一个事实的值"。supersedence 签名把这个模糊判断变成三要素精确匹配——实体域（人名劫持防御）、谓词域（followers≠following）、单位域（$≠€、miles≠km）。**触发面大不可怕，可怕的是无签名的触发**。
3. **判分侧与检索侧的单位纪律是同一条边界**: #090 在判分侧发现 "$5 ≢ 5 euros、5 miles ≢ 5 km"，#091 在检索侧发现同一纪律恰好定义了版本边界（跨域永不互斥）。两次独立收敛说明这是单位语义的真实结构而非工程巧合——**unit domain 是可以写进 README 的统一原语**（judge 侧做等价，retrieval 侧做版本）。
4. **撤回终点是弃权家族的新成员**: 版本链终端的 INVALIDATED 状态与 C513/C514 的 neg-exist 弃权机制互补——neg-exist 门处理"库里从头没有"，INVALIDATED 处理"曾经有但现在没了"。FreshQA 把 false-premise 单列为一个类别，说明这不是边角案例而是基准的固定考点。amg abs30 面（10→15，C516）之后，**"失效前提"是弃权面的下一个自然人口**。
5. **C523 已经隐式验证了 recency 信号的价值**: quant_rerank 的 (-hits, -seq) 排序在数量子型拿到 +11/−0——seq 排序不是理论赌注而是已兑现的增量。latest-number-wins 是它的显式化与一般化：从"rerank 启发式偏爱新行"升级为"签名仲裁 + superseded 链 + 撤回处理"。**先例已付学费，C524 是收获而非赌博**——风险从"未知是否有效"降级为"签名碰撞率是否可控"，而后者 census 一测便知。

## 六、下一步行动

1. **Census 先行（insight #254 纪律）**: 对 full-500 跑同签名冲突扫描——抽取所有数值行，按 (entity, predicate, unit_domain) 签名分组，统计 (a) 多值同签名组的题目人口（对照 HEARTBEAT 估计的 40+ 题）(b) 签名碰撞导致的假合并数（hijack 暴露面）(c) 撤回形态出现次数。产出：C524 的精确触发面清单。
2. **C524 实现（census 绿灯后）**: `latest_number_wins` 以 form-gated 方式落地——只在数量当前值型 form 启用；A/B 于 kupdate + multi_session 子集，基线官方 0.476（C523）；预期主要增益在 multi_session 的 recency 对比题，零回归红线沿用 (+n/−0) 汇报纪律。
3. **撤回检测器（独立小件）**: "not anymore / moved out / paid off / sold" 模式 → Retraction 事件，喂给 INVALIDATED 弃权路径。与现有 abs 门（专有名词 C513 + 普通名词 C516）并列成第三种弃权来源：neg-exist（从未有）/ 版本失效（曾有过）/ 预设失败门（既有）。
4. **README 叙事素材**: "unit semantic domain as the supersedence boundary" 作为统一原语写进发布材料——judge 侧（#090 answer_equiv）与 retrieval 侧（#091 fact_versions）共用同一边界定义，这是竞品没有的架构一致性证据。

## 七、质量自评

- ✅ 可运行代码：12/12 自测全绿，零依赖，覆盖 LME 原题形态 + 双向劫持陷阱 + 撤回边界
- ✅ 独到见解：写时失效 vs 答题时仲裁的摊销分析（C512 先例反向印证）；单位域 = 判分/检索共享边界的两次独立收敛；"风险高一档"的签名化解法
- ✅ 项目关联：直连 C524（关键路径 #3 首位）、C523 先例、弃权家族第三成员、README 叙事、12-form 分类器复用点
- 局限：日期型事实未覆盖（"I moved to Tokyo in March" 的 supersedence 需要日期签名——C456/C482 已有日期锚定，但版本语义不同，留待 census 看人口再定）；谓词归一化在本原型里是手工字符串，生产需接 amg form 分类器；LME 官方 ground truth 的"哪个值算对"未逐题核验（census 阶段补）

## 参考

- Rasmussen et al. 2025 (Zep/Graphiti), arXiv:2501.13956 · github.com/getzep/graphiti · getzep.com/ai-agents/temporal-knowledge-graph/
- Piryani, Mert & Jatowt 2026 (RecencyQA), arXiv:2603.16544 · github.com/DataScienceUIBK/RecencyQA
- Dhingra et al. 2022 (TempLAMA), TACL, aclanthology.org/2022.tacl-1.15/
- Vu et al. 2024 (FreshQA/FreshLLMs), Findings ACL, aclanthology.org/2024.findings-acl.813
- Zhang & Choi 2021 (SituatedQA), NeurIPS D&B · situatedqa.github.io
- 补充: EMNLP 2023 "Mitigating Temporal Misalignment by Discarding Outdated Facts"; TKGQA survey arXiv:2406.14191
- 检索路径：Tavily 432 配额错误第 6 天 → AnySearch academic (mcporter) + web_fetch 降级，全程零阻塞
