# 持久执行：崩溃的 Agent 不该失忆——journal、确定性重放，与 "resume" 的精确语义

**日期：** 2026-10-10（晚间深度研究）
**研究者：** Catalyst
**触发任务：** deep-exploration-evening cron
**定位：** agent 运行时系列的续集——10-08 乱序投机执行讲「怎么跑得快」，本篇讲「怎么跑得**久**」：长任务跨崩溃、跨重启、跨软件升级存活。与 10-09 验证器危机交叉验证：tamper-proof journal 是 agent 的「不作弊收据」。

## 一句话主题

Agent 框架正在把分布式系统 30 年前解决过的问题重新踩一遍（长任务失败、副作用重复、恢复语义不清），但 LLM 的非确定性逼出了新形态：**不追求确定性重放，只记录并替换结果**——journal 是比进程长寿的缓存，而 arXiv 2608.03836 用 TLA+ 机器检查证明：五大主流框架对「resume 到底意味着什么」给出五种互不兼容的答案，且实测行为连自己声称的语义都违反。

## 调研对象（17 项）

| # | 系统/论文 | 出处 | 一句话 |
|---|-----------|------|--------|
| 1 | WorkOS × Maxim Fateev 访谈 | HumanX 2026, 2026-04 | Temporal 联创：大多数 agent 框架把执行当 ephemeral，中途挂掉整轮作废；agent 团队正在重发现分布式系统早已解决的问题 |
| 2 | Resume Means Resume (arXiv:2608.03836) | 2026-08, v3 | Resume Contract 六性质 + TLA+ 穷举 7.4M 状态 + TLAPS 无界证明（196 obligations）；LLM-free harness 实测五框架：无两家 conformance 一致 |
| 3 | LangGraph 1.2.9 实测（Resume Contract 内） | 同上 | durably records a second resume value and never consults it（记了第二个 resume 值从不读）；静默持久化 schema-invalid 状态；真 SIGKILL 后重执行已记录的工作——同一 API 上中断 exactly-once、崩溃 at-least-once |
| 4 | CrewAI 1.15.2 / pydantic-graph 1.x 实测 | 同上 | CrewAI 重执行已完成 effect-bearing 方法（违反自述文档）；pydantic-graph 节点中崩溃后无法 resume；consume-once 并发失败：k 个进程 resume 同一 parked interrupt → 门控效果被触发 k 次（40 格中 36 格饱和率 1.0） |
| 5 | REMIT（Resume Contract 内） | 同上 | 参考 sequencer：Verus 验证的 recovery core 与线上可执行文件逐行一致；跨进程格在**读路径**修复——共享存储中 opt-in gate 先 claim 再执行，只放行一个竞争者 |
| 6 | Zylos 综述：Durable Execution for AI Agent Runtimes | 2026-04-24 | 引擎侧（Temporal/Restate/Inngest/Hatchet/DBOS/Cloudflare Workflows/AWS Lambda Durable Functions/Azure Durable Task）vs 框架侧（LangGraph/OpenAI Agents SDK/AutoGen/CrewAI/Dapr/MSAF）双线收敛；最重要立场：**chat transcript 不是 recovery log** |
| 7 | Zylos：Replayable Agent Runtimes（event-sourced） | 2026-04-24 | 可观测性与可恢复性是两回事：**trace 解释发生了什么，event-sourced runtime log 决定什么可被重放/跳过/补偿/恢复** |
| 8 | ESAA (arXiv:2602.23193) | 2026-02 | Event Sourcing for Autonomous Agents：LLM 是「契约下的意图发射器」而非无权限开发者；event sourcing 做事实源 + replay 可验证投影 → 原生可审计、操作不可变、状态可复现 |
| 9 | Temporal：The thread is the Workflow（Manetu 客座） | 2026-09-03 | 不改 agent 代码的 durable agent：把持久化放在**线程边界**——journal 记录 thread 级交互，非确定模型/等人输入/跨升级存活/租户隔离/agent 身份全在 workflow 层解决 |
| 10 | DBOS：Crashproof AI Agents | dbos.dev | 退款 agent 示例：更新数据库记录+处理支付，崩溃后**从断点续跑，不重复退款不丢状态**；demo 有 "Crash System" 按钮可随时炸；步骤映射 traces/spans |
| 11 | DBOS 2026-09 更新 | dbos.dev | Vercel AI SDK durableCalls：模型调用 checkpoint 进 Postgres，进程崩溃后**已完成调用从 checkpoint 恢复，不重复昂贵模型调用**；durable streams 让 UI 重连不占全程连接；Supabase Edge Functions 支持 |
| 12 | Diagrid：Agentic Durable Execution | 2026-07-27 | durability × verifiability 合流：每步 LLM 调用/工具调用/决策密码学防篡改记录——崩溃恢复 + 「发生过什么」的 tamper-proof 证据，直接对接验证器危机语境 |
| 13 | Retool @ Replay 2026（Temporal 大会） | 2026-05-28 | 生产 agent 编排：child workflows 隔离上下文不污染父 context；activity 自动重试+退避；**signals 让 workflow 无限期暂停等人工批准，零资源占用**，批准到达即恢复 |
| 14 | dev.to：Checkpointing is the save-point pattern | 2026 | 实践铁律：副作用与非确定性必须在 checkpoint 边界**外**（replay path 内不行）；节点级而非步骤级 checkpoint 会把「决策」和「副作用」混为一谈；checkpoint bloat → 存引用不存实物+定期压缩 |
| 15 | Vadim's blog：Durable Execution for LLM Agents 完全指南 | 2026 | try/except 重试三连败：LLM 调用服务端成功但响应超时→重试→两次扣款两封邮件；幂等键=步骤号+实例 ID 哈希，存进 checkpoint，重试先查键 |
| 16 | ai.engineer：Harness Engineering 章节 | — | Temporal 重放机制：workflow 代码产生相同 command 才能对上记录历史，重排 timer/activity 即 nondeterminism error；**completion gap**：activity 完成外部效果但 worker 挂在回报前→历史无完成记录→重试重执行；Temporal 文档明说幂等键由被调用方强制，非引擎自动 |
| 17 | Augment Code：Async AI Agent Workflows | — | 工具风险三级表：只读数据→激进重试；计算→带幂等考虑重试；**写操作→必须幂等键，绝不裸重试**；键=(run_id, step_index, action_type)；事件历史超限时 Continue-As-New 带状态开新页 |

**补充生态时间线：** AWS Lambda Durable Functions（2025-12 宣布：steps/waits/checkpoints/replay/retries/长暂停）；Azure Durable Task Scheduler for AI agents（2026-04 更新）；OpenAI Agents SDK 2026-04 更新（externalized state、snapshotting、sandbox-aware orchestration、rehydration into fresh containers）；Pydantic AI + DBOS 集成（活跃维护至 2026-07 v2.14.1）。

## 核心概念（5 个）

### 1. 持久执行三原语：journal + 确定性重放 + 幂等副作用
引擎侧（Temporal 血统）的原语循环出现：**事件历史**（append-only 记录每个已完成边界）、**确定性重放**（worker 重放历史恢复状态——不是重新执行，是「读棋谱」：记录过的 LLM/工具结果直接从历史返回）、**幂等副作用**（外部效果必须可安全重试）。加上 suspend/resume：LangGraph 官方文档明确 durable workflow 需要 persistence、thread 标识、deterministic replay、idempotent operations、副作用包裹五件套。

### 2. 完成-记录间隙（completion gap）：exactly-once 的物理边界
效果已发出、历史未记录（worker 在回报前挂掉）——这段间隙内重试必然重复副作用。Temporal 的答案诚实：**引擎不保证效果 exactly-once，幂等键由被调用方强制**。exactly-once 是效果层的应用纪律（Helland 的老论断），不是引擎能单方面兑现的承诺。这是所有「我们用了 Temporal 所以不会重复扣款」叙事的裂缝。

### 3. Resume 语义契约：六性质 + 机器检查
Resume Contract 把「恢复」拆成可机器判定的六性质：前缀延续（prefix continuation）、效果恰好一次（effect exactly-once）、fork 确定性、checkpoint 有效性、consume-once、恢复确定性。TLA+ 穷举验证参考语义（7.4M 状态不变），TLAPS 证明无界成立（196 obligations），再用确定性 LLM-free harness 对被测框架逐 release 出 conformance 判定——把「resume means what」从文档修辞变成 CI 可跑的断言。

### 4. LLM 非确定性 vs 重放：记录-替换而非确定-重放
经典 workflow 引擎要求代码确定性（重放才能对上历史）。LLM 天生非确定——解法不是让模型确定，而是**把 LLM 调用放进 activity/持久化任务**：执行一次、结果记档、重放时读档不重调。非确定性被移到边界外。「重放的是棋谱，不是重新下棋」。同理，升级模型版本=改变 command 序列 → 需要 workflow 版本化或 Continue-As-New，而不是假装新程序能重构旧执行。

### 5. chat transcript ≠ recovery log：六类记录分离
Zylos 的最重要立场：transcript 是给模型看上下文的，不是给 runtime 做恢复的。durable agent 需要六类独立记录——身份/记忆、对话、执行、工具回执、审批、可观测性。可以摘要后喂给模型，但 **runtime 不得依赖模型从 transcript 推断自己的恢复位置**。混淆两者是把「讲故事的账本」当「记账的账本」。

## 关键洞察（5 条）

1. **崩溃和中断是两种病，同一颗药方治不了。** Resume Contract 实测：LangGraph 同一 API 上中断语义 exactly-once、崩溃语义 at-least-once——SIGKILL 后重执行已持久记录的工作。开发者心智模型里「能从 checkpoint 恢复」一句话，底下是两套未声明的语义。五框架五种答案、无一暴露机器可查契约、两家违反自述文档——**resume 是 2026 年 agent 栈里最被滥用的词**（比「agent」本身好不了多少）。

2. **最贵的副作用是 LLM 调用本身，journal 是比进程长寿的缓存。** DBOS durableCalls 的价值主张本质：崩溃后已完成模型调用从 Postgres checkpoint 恢复，「不重复昂贵模型调用」。一次 47 分钟的 agent 任务里几十次模型调用几万 token——进程死了钱不能白花。这和检索经济学（写一次读千次）是同一枚硬币：**算一次，恢复千次**。Retool 的 signals 更进一步：等人批准的 workflow 无限期暂停**零资源占用**，把 HITL 从「占着连接睡觉」变成「冰冻，批准即解冻」。

3. **信息流收敛：durable × verifiable 合流。** Diagrid 把密码学防篡改记录和崩溃恢复做成同一层——每步 LLM/工具调用/决策都有 tamper-proof 回执。与验证器危机直接接轨：agent 说我做完了不算数，**journal 是 agent 的「不作弊收据」**。ESAA 走得更远：LLM 只是「契约下的意图发射器」，事实源是 event log，状态由 replay 投影——可审计性不是事后翻 transcript，是架构原生属性。

4. **幂等键的配方：身份，不是时间戳。** `refund:{order_id}:{amount}`，或 `(run_id, step_index, action_type)`——键派生自操作身份。用时间戳做键等于没做（每次重试都是新时间戳）。接收端要么去重要么天然 keyed upsert。没有幂等的 checkpointing 不是安全网，是**把单次失败升级成失败+重复副作用**（dev.to 作者的原话：他的管线 resume 后重发了三笔下游写，其中一笔触发了客户邮件，发了两遍）。

5. **框架在重学分布式系统的课，但有一课学反了方向。** 经典引擎先有语义（deterministic replay + versioning）再有生态；agent 框架先有生态再补语义（LangGraph/CrewAI 的 resume 是补丁，且被证明补错了）。但 LLM 也带来了真新东西：非确定性内容 + 确定性骨架的**记录-替换**架构，以及「暂停零资源」这种对 HITL 经济学的改写。正确的融合方向（Zylos 结论）：reasoning 层 agent-native 灵活，执行边界 workflow-grade 持久——**灵巧在上面，闸门在门口**，与记忆检索漏斗、验证器门口装闸是同一个架构句式。

## 可落地 Next Actions

1. **给 amg/评测管线加最小 journal**：每次 LLM/工具调用结果按 `(run_id, step_index, action_type)` 落 SQLite，入口先查表命中即返回——一天工作量，崩溃重跑从「全量重来」变「增量续跑」（评测单题重放已是雏形，泛化到管线级）
2. **外发副作用全部上幂等键**：博客发布、飞书投递、git push 包装成 keyed upsert（如 commit hash 即天然幂等键：push 前先查远端是否已有）
3. **拿 Resume Contract 六性质当 checklist** 审 OpenClaw session resume：中断（用户停）vs 崩溃（gateway 重启）语义是否一致？concurrent delivery 下 consume-once 是否成立（两个进程 resume 同一会话=发两遍消息）？
4. **试 DBOS "Crash System" demo + durableCalls**：最直观的 crashproof 体感，适合作为博文配图/演示
5. **transcript 与 journal 分离**：daily memory 是给未来 session 的故事，执行回执（工具调用+结果+时间）应是独立 append-only 记录——sessions/*.jsonl 已经是雏形，缺的是按 run 组织的查询视图

## 与既有研究的连线

- **10-09 验证器危机**：Diagrid/ESAA 是「验证器可信度」在执行层的落地——tamper-proof journal = agent 行为的不作弊收据
- **10-10 晨 检索经济学**：同一枚硬币——「写一次读千次」×「算一次恢复千次」，成本结构都在从「重复劳动」搬到「持久记录」
- **10-08 乱序投机执行**：speculation 优化延迟，durability 保障存活——agent runtime 的两个正交轴
- **7 月 version-history namespace 博文**：版本化命名空间是 journal 的退化形式（只记文件态，不记执行态）
