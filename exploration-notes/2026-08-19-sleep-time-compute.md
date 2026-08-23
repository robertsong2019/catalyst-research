# Research #076 — Sleep-time Compute：Agent 空闲期如何从成本中心变成资产

> 2026-08-19 20:45 deep-exploration-evening
> 主题：把推理/记忆整理从用户等待的峰值搬到系统空闲的谷值——sleep-time compute 范式、三层落地、不可能三角约束与失败模式
> 调研来源 14+：Letta/Berkeley 论文、LightMem、RecMem、MemoryCPT、A-MEM、StateLM/Pensieve、CCC 不可能三角、Language Models Need Sleep、Karpathy autoresearch、Mem0 2026 报告等（见 §6）

---

## 1. 问题起点

你的 Agent 一天里 95% 的时间在干什么？在等用户。聊天 Agent 的会话占空比通常 <5%，编码 Agent 在两次任务之间整夜空闲。与此同时 test-time compute（o1/R1 式"想久一点再答"）已经撞到延迟与成本的墙：用户等 3 分钟是不可接受的，GPU 在峰值时段是最贵的。

Letta + UC Berkeley（Charles Packer / Charlie Snell 等，arXiv:2504.13171，2025-04）提出的 **sleep-time compute** 给出一个调度层面的答案：把"深度思考"从查询到达之后挪到查询到达之前——系统空闲时预先消化上下文、预计算可能被问到的量。这不是新模型能力，而是**计算调度的范式转移**：从"反应式智能"到"前瞻式智能"。

## 2. 核心概念（5）

### 2.1 Sleep-time Compute（睡眠期计算）
模型在空闲期对持久化上下文离线推理：预判用户可能问什么、预先重表示（re-represent）上下文、预计算中间量。查询到来时用极小的 answer-time 预算作答。论文数据（Stateful GSM-Symbolic / Stateful AIME）：
- 同精度下 test-time compute 需求 **降至 1/5**
- 固定 test-time 预算下，加大 sleep-time 可再提精度 **+13%（GSM）/ +18%（AIME）**
- Multi-Query 场景（一个上下文配套多个相关问题），预计算可摊销，**单查询成本降 2.5×**
- SWE 案例：编码 agent 夜间预读 PR + 仓库，白天修 bug 的步数预算显著下降

### 2.2 可预测性（Predictability）是收益的决定变量
论文最重要的负结果：**sleep-time compute 的收益与"查询可预测性"强相关**。可预测（会反复问同一上下文的问题）→ 收益巨大；不可预测 → 预计算白做，甚至负迁移（预表示把模型引向错误方向）。本质是一个投资决策：预计算的价值 ≈ P(问题被问到) × 单次增益 − 整理成本。低质量"预习"比不预习更糟。

### 2.3 记忆巩固的在线/离线解耦
记忆系统的 write–manage–read 循环中，manage 段天然适合搬离线：
- **LightMem（ACL 2026）**：SLM 在线写入 MTM（中短期记忆），离线用大上下文 LLM 做批量巩固——情景记忆 → 去标识化的语义知识，增量合并进 LTM 图（不整库重建）。在线零巩固开销，离线只处理增量批次。
- **RecMem（ACL 2026 Findings）**：recurrence 式巩固，处理 lost-in-the-middle 与证据利用不足。
- **MemoryCPT（2026）**：两段式——QAD（查询无关蒸馏，把记忆构建流水线蒸馏进小模型，离线）+ QAR（查询感知检索与摘要，在线）。
- **A-MEM（2026-02）**：更进一步用 GRPO RL 让 agent 学出非显然的记忆策略（溢出前抢先摘要、冗余条目选择性遗忘、概念主动关联）——巩固策略本身可学习。

### 2.4 上下文空间 vs 权重空间的巩固光谱
巩固发生在哪一层，风险/回报同步上升：
1. **上下文重写**（Letta sleep-time agent 重写 in-context memory）——可逆、便宜，但受窗口限制
2. **外部记忆整理**（LightMem/LTM 图、MID-storeS）——持久、可审计，但引入检索质量依赖
3. **权重内化**（"Language Models Need Sleep", 2026：把 in-context 记忆蒸馏进新增 expert 权重，用模型自己的 rollouts 做自我蒸馏）——最高回报，但触碰灾难性遗忘
神经科学对应：海马体→新皮层的 systems consolidation（慢波睡眠重放）。ICLR 2026 MemAgents workshop 把"类海马-新皮层巩固机制"列为公开问题。

### 2.5 不可能三角（CCC, Context Channel Capacity 2026）
**零遗忘、在线学习、有限参数三者不可兼得**（对序列状态学习者的形式化证明）。推论：sleep-time 不是锦上添花而是结构性必需——既然在线时段无法同时满足学习质量与稳定性，就必须存在一个离线时段来承担"有损但可控"的整合。睡觉不是偷懒，是三角约束下的工程解。Mem0 2026 报告补了一个运营视角的坑：**staleness ≠ decay**——高频检索的记忆在事实变化后变成"自信地错误"，衰减管低相关记忆，高相关记忆的过期需要显式的失效机制。

## 3. 关键洞察（5）

### 洞察 1：这是调度革命，不是模型革命
Sleep-time compute 没有发明新算法，它改变的是**计算的时段**。经济学上等价于把算力从"用户等待的峰值电价"搬到"系统空闲的谷价"。夜间 GPU 便宜且无人等待延迟——同样的 token，价值不同。Agent 系统的下一个竞争力指标可能是"空闲期利用率"。

### 洞察 2：预计算是投机，可预测性是汇率
所有 sleep-time 收益都建立在一个赌注上：未来查询与已有上下文相关。个人助理（问题围绕同一用户的历史）是最佳场景；开放域客服（问题不可预测）收益趋零甚至为负（负迁移）。设计前的第一问不是"怎么离线整理"，而是"我的查询分布可预测吗"。

### 洞察 3：巩固崩塌是真实风险
Turing Post 引述 2026-06 "Rethinking Continual Experience Internalization"：经验内化做得不好时，重复学习循环会**坍缩而非复利**——agent 越学越差。离线巩固不是"多跑几遍摘要"就安全，错误信号会被放大固化进长期记忆/权重。巩固管道本身需要 eval 与回滚（与 amk 写时治理同构）。

### 洞察 4：我们已经在运行原始形态的 sleep-time agent，只是没把它当一等公民
OpenClaw 的 heartbeat/cron、Claude Code 的后台任务、Karpathy 的 autoresearch（单 GPU 过夜跑 ~100 个实验，把 nanochat speedrun 从 2.02h 压到 1.80h，改进人类没发现的架构/超参组合）——都是 sleep-time compute 的雏形。差别在于：有没有为空闲期设计**专门的整理目标**（而不是碰巧有任务跑）；有没有摊销机制（多查询复用）；有没有防负迁移的守门。

### 洞察 5：空闲期是把"在线学习"从不可能三角里拆出来的杠杆
CCC 不可能三角禁止同时要零遗忘 + 在线学习 + 有限参数。sleep-time 把第三角的冲突显式化：在线时段只做无状态的读 + 轻写，所有有状态、有损、需要验证的整合推迟到离线时段做。这与人脑"白天编码、夜间重放"同构——也意味着**白天敢不敢只做轻写，取决于夜里的巩固管道有多可靠**。

## 4. 与既有研究的连接

- 与 Research #072（遗忘工程）：遗忘决定"扔什么"，sleep-time 决定"何时扔、何时整合"——写时治理 vs 睡时整理是同一生命周期两端
- 与 write-time-governance 博文：写时治理的规则可以在 sleep-time 阶段批量重放审计
- 与巩固即边界博文：边界识别（何时触发巩固）是 sleep-time 调度器的核心输入
- 与 StateLM Pensieve（read-note-delete，52% vs 5%）：上下文自管理本身可以被建模为 sleep-time 的微循环

## 5. Next Actions（可落地）

1. **今晚就能做**：给 OpenClaw 加一个 nightly cron（00:30）：读当日 memory/*.md → 提炼进 MEMORY.md（带来源引用）→ 扫描 error-patterns.md 高频项 → 生成"昨日巩固报告"。这就是一个最小可行的 sleep-time agent。
2. **加摊销**：探索笔记统一存 markdown + frontmatter（主题标签），夜间 cron 预生成主题索引，检索时零成本复用（Multi-Query 摊销的本地版）。
3. **防负迁移守门**：夜间整理产出先写 staging（memory/staging/），白天首次使用时验证（引用的行号/事实抽查），通过才晋升正式记忆。巩固崩塌的保险丝。
4. **量化空闲期利用率**：在 dashboard 里记录 agent 每日 token 消耗按"在线应答 vs 离线整理"分桶，两周后决定离线预算扩到多少。
5. **实验**：把 amk 检索预热（索引构建、实体链接）改为夜间预跑 + 缓存，测 p95 检索延迟变化。

## 6. 来源清单（14）

1. Lin, Snell et al., *Sleep-time Compute: Beyond Inference Scaling at Test-time*, arXiv:2504.13171 (2025) — 核心论文
2. Letta blog: *Sleep-time Compute* + MemGPT 2.0 sleep-time agents 文档 (2025-04)
3. letta-ai/sleep-time-compute GitHub（复现代码 + Stateful AIME/GSM/SWE-Features 数据）
4. LightMem: *Lightweight LLM Agent Memory with Small Language Models*, ACL 2026 — 在线/离线解耦巩固
5. RecMem: *Recurrence-based Memory Consolidation*, ACL 2026 Findings (CUHK)
6. MemoryCPT: QAD+QAR 端到端记忆流水线 (2026)
7. A-MEM: RL 学习记忆操作策略 (2026-02)
8. StateLM / Pensieve paradigm: read-note-delete 自管理上下文 (2026)
9. CCC: Context Channel Capacity 不可能三角 (2026)
10. *Language Models Need Sleep: Self-Modify and Consolidate Memories* (2026) — 权重空间巩固
11. Mem0, *State of AI Agent Memory 2026* — staleness vs decay、生产化数据
12. Karpathy autoresearch (2026-03) — 过夜自主实验循环
13. Turing Post FOD#155: *Continual Learning in LLMs: Why AI Models Need Sleep* (2026-06) — 巩固崩塌
14. ICLR 2026 MemAgents workshop — 海马-新皮层巩固公开问题；及神经科学 systems consolidation 背景
