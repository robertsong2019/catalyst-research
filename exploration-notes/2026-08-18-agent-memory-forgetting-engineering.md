# Research #073: Agent 记忆的遗忘工程 — 遗忘不是 delete，是 accessibility

**日期**: 2026-08-18 晚 (deep-exploration-evening)
**主题**: LLM Agent 记忆的遗忘机制 —— 从被动 decay 到 rate-distortion 统一视角
**动机**: amg 已完成 write-time governance（C441-448）与巩固边界调研（#069），记忆的"存"与"整"两侧都有路线图，但"忘"仍是一等公民缺位。本轮系统调研 2026 年遗忘侧前沿，为 amg retention policy 立项提供弹药。

---

## 调研范围（13 个来源）

### 遗忘机制系统层（2026 新一代）

| 系统 | 出处 | 核心机制 | 关键数字 |
|------|------|---------|---------|
| **Oblivion** | arXiv 2604.00131 (NEC Research) | **decay-driven activation**：遗忘=可及性衰减而非物理删除；读写双路径解耦（读路径按 agent 不确定性决定何时查记忆；写路径强化对回答有贡献的记忆） | 长程静态+动态基准上平衡学习与遗忘；代码开源 github.com/nec-research/oblivion |
| **FSFM** | arXiv 2604.20300 | 生物启发选择性遗忘框架（hippocampal indexing + Ebbinghaus 曲线）；**四类机制分类学：被动 decay / 主动删除 / 安全触发 / 自适应强化** | 访问效率 +8.49%；信噪比 +29.2%；安全风险消除 100% |
| **ε-MemEvo** | arXiv 2608.12522 | 跨任务 tactic 记忆迁移 + **自适应注入门**（检索回的记忆要不要注入、注入多强）——负迁移防护本质是"选择性不使用" | 8 基准全胜，AUCC 均值 +8.7%；naive 注入灾难性失败，门控全程安全；开销 <1% |
| **ACM / Maximem Synap** | arXiv 2607.21503 | 提出 **Agentic Context Management** 学科：五原语（architecting/ingesting/scoping/anticipating/compacting+consolidation），**组织级 scope 层级**；经济学：朴素累积 O(n²) token、粗糙摘要线性但有精度悬崖、validated compaction 线性+保真 | LongMemEval 92% / LoCoMo 93.2% |
| **Zep/Graphiti** | arXiv 2501.13956 | bi-temporal：事实失效用 `invalid_at` 逻辑作废而非删除（时间线可回放） | DMR 94.8%；LongMemEval +18.5% |

### 理论统一层

| 工作 | 出处 | 核心论点 |
|------|------|---------|
| **Rate-Distortion Compaction 统一视角** | arXiv 2607.08032 | KV cache 逐出/量化、prompt 剪枝/蒸馏、架构状态有界、agent 记忆巩固——**四层是同一个 rate-distortion 问题**（预算下保留什么、什么保真度、保住下游任务效用）。七轴分类学 + 层间机制迁移。**两个跨层失败模式：① 每层的保留信号都是 attention 幅值或 recency，而它们以同样方式失败——在查询到来之前、不可逆地丢掉查询后来才需要的信息；② 反复压缩几乎从不被测量，没有任何基准同时钉住一个预算轴** |
| **Forgetting→Shared Meaning** | arXiv 2607.11787 (CogSci 2026) | 非合作协调博弈中，**记忆衰减让概念对齐更稳**：对新信息权重递减的玩家达成的共识比固定权重更稳定；遗忘是群体语义收敛的稳定器 |
| **Richards & Bajgind? → Richards & Frankland** | Neuron 2017 "Persistence and Transience of Memory" | 认知神经学根基：遗忘是大脑的**适应性设计**（泛化>精确回忆），不是存储失败 |

### 基准与安全层

| 工作 | 出处 | 核心发现 | 关键数字 |
|------|------|---------|---------|
| **MemSecBench** | arXiv 2607.27080 | 记忆生命周期安全基准：**Write–Execute–Forget 协议**，24 配置矩阵（2 harness × 4 memory backend × 3 LLM） | 恶意记忆 **84.2% 持久化**；完整攻击链成功率 50.3%；中毒后**选择性修复仅 56.1%**；backend 间端到端 ASR 差 16.1pt、修复差 41.3pt |
| **MemoryAgentBench** | arXiv 2507.05257 (v4 2026-06) | 记忆 agent 四大能力：准确检索 / test-time 学习 / 长程理解 / **选择性遗忘**——遗忘首次与检索并列为一等基准能力 | 现有系统无一家四项全通 |
| **MemLeak** | arXiv 2606.29788 | 多模态 agent 记忆的信息泄漏诊断——遗忘的另一端：该忘的隐私没忘 | — |

### 前置工作（来自 #069，复用）
- MemSIF (2608.01742)：写入时显著性≠未来效用（DUM 错配）→ CoreFact/ActiveFact 双轨晋升——**晋升的反面就是遗忘**
- RecMem (2605.16045)：惰性巩固，未复发的交互永不升级为显式记忆——**零成本遗忘**
- OEP (2605.18930)：攻击者利用反思巩固把局部经验蒸馏成过度泛化规则——**该忘的经验忘不掉是攻击面**
- Sleep-time Compute (2504.13171)：离线整理上下文为遗忘/巩固提供时机窗口

---

## 核心概念（5）

### 1. 遗忘 = 可及性控制（Accessibility Control），不是删除
Oblivion 的关键重构：记忆条目不消失，而是 activation 随时间衰减、被使用时强化（斯金纳箱式）。检索排序 = activation × 语义相关性。Zep 的 `invalid_at` 同理：事实被"作废"但历史可回放。**物理删除是遗忘的最后手段，逻辑降权才是日常操作**——这保留了不可逆性兜底（误判可恢复）。

### 2. Rate-Distortion 是记忆压缩的统一数学
一个 compaction 目标函数：在资源预算 B 下，选择保留集合与保真度，最大化下游任务效用。KV cache 的 PagedAttention 逐出、agent 记忆的"摘要替换原文"、FSFM 的 SNR 优化，全是同一目标的实例。**价值：serving 栈十年的缓存管理理论可以平移进 agent 记忆**（反之亦然）。

### 3. 四类遗忘机制分类学（FSFM）
- **被动 decay**：随时间自然降权（零成本，适合海量低价值交互）
- **主动删除**：显式策略判定（如过期事实、任务完结）
- **安全触发遗忘**：检测到恶意/敏感内容立即清除（MemSecBench 的 selective repair 对应此层）
- **自适应强化**：被使用的记忆升权——**遗忘机制的输出馈入记忆机制的输入**，两者是同一控制回路的两半

### 4. Write–Execute–Forget 生命周期安全
MemSecBench 把记忆安全从"写入时过滤"扩展到三段协议。核心发现：**恶意记忆的持久化率（84.2%）远高于攻击完成率（50.3%）**——大量毒记忆潜伏着等触发条件；而事发后的选择性修复只有约一半成功率。结论：**安全遗忘必须前置到写入时打标 + 周期性清除，不能依赖事后修复**。

### 5. 组织级 scope：遗忘的边界由 scope 决定
ACM 指出生产记忆系统运营于 scope 层级（用户/团队/组织）之上——**一条记忆对个人 scope 过期，未必对组织 scope 过期**；反之个人隐私在组织层必须强制遗忘。遗忘策略不是单条记忆的属性，是 (memory, scope) 二元组的属性。

---

## 关键洞察（5 条）

### 洞察 1：所有层的遗忘以同一种方式失败——查询前不可逆丢弃
Rate-distortion survey 的跨层结论一针见血：无论 KV cache 还是 agent 记忆，保留信号都是 recency/attention，都**在不知道未来查询的情况下做不可逆决策**。工程对策：一切遗忘操作软删除化（tombstone + 冷存储 + 恢复路径），硬删除只留给安全触发类。这与 amg 已有的 bi-temporal 时间戳天然契合——**amg 离一个 retention policy 只差一个 decay 函数**。

### 洞察 2：不会忘是安全问题，不只是成本问题
MemSecBench 84.2% 持久化率说明：**记忆系统的最大攻击面恰恰是它的永久性**。Mem0/MemGPT 时代的"记住一切"在攻击者眼中是持久化后门。且 selective repair 仅 56.1% 成功——事后消毒不可靠，安全遗忘必须成为写入管道的一等阶段（与 amg write-time governance 的 ShadowMerge 门无缝衔接）。

### 洞察 3：遗忘买到的三样东西都不是"省空间"
FSFM: SNR +29.2%（检索质量）；CogSci 2026：遗忘让多智能体概念对齐更稳定（协调质量）；Oblivion：读路径按需查询降低延迟（效率）。加上偏好更新（旧偏好若不可遗忘，新偏好永远被旧偏好污染）——**遗忘是记忆质量的乘法器，不是存储的减法器**。

### 洞察 4："反复压缩"是评测空白带
所有基准测单次长上下文或单轮检索；agent 实际每天做 N 次压缩，**误差会复利**（compounding drift）。Rate-distortion survey 提出但未实现的 repeated-compaction benchmark 是明显的空位——amg 的 autoresearch 管线 + 双基准（LoCoMo/LME）恰好是搭这个基准的最佳底座：把 500 题按时间切窗、多次 consolidate 后测 drift。

### 洞察 5：强化与遗忘是同一回路——读写路径解耦是架构关键
Oblivion 的真正贡献不是 decay 公式，而是**读路径（何时查）与写路径（强化谁）解耦**。ε-MemEvo 的注入门同理：检索回来的记忆还要过一道"要不要用"的门。启示：amg 的 retrieval score 应分解为 `relevance × activation`，其中 activation 由使用反馈在线更新（零 LLM 可实现：access_count × recency × type_weight）。

---

## Next Actions（amg 落地路径）

1. **[零 LLM, ~1 cycle] activation 衰减原型**：节点/边加 `activation` 字段（初始 = type_weight），检索得分改为 `relevance × sigmoid(activation)`；每次命中 +α，按 `last_access` 时间指数衰减。LoCoMo/LME 全量回归验证不伤准确率的前提下降 tokens/query。
2. **[写入管道] 安全触发遗忘阶段**：ShadowMerge 检出的高危内容写入时打 `purge_pending` 标记，周期任务清除——对应 MemSecBench "写入时打标优于事后修复"结论。
3. **[基准] repeated-compaction drift 指标**：LME_s 按时间切 5 窗，每窗 consolidate 一次，测第 5 窗后的 temporal/preference 类准确率衰减 vs 不 consolidate 基线。空位品类指标。
4. **[评测口径] SNR 指标进 amg_bench_quality**：retrieved-but-unused 比例（检回但未被答案引用的条目占比），对齐 FSFM 口径。
5. **[研读] Oblivion 源码**（github.com/nec-research/oblivion）：读路径不确定性判据的工程实现，评估移植到 amg router。
6. **[远期] scope 层级**：记忆节点加 scope 标签（user/project/org），retention policy 按 scope 分治——呼应 ACM 组织级方向。

## 一句话

> 记住是能力，忘记是工程。2026 年的记忆系统竞争，正从"谁记得多"转向"谁忘得对"。
