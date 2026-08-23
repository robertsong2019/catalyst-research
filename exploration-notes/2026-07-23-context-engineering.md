# 上下文工程（Context Engineering）：从写好提示到管好上下文

**日期：** 2026-07-23
**主题：** Context Engineering — AI Agent 领域的范式迁移
**研究者：** Catalyst

---

## 研究范围

2026 年上半年，特别是 6-7 月的 arXiv 论文中，"Context Engineering" 作为独立研究方向频繁出现。本次调研覆盖 12+ 篇论文/系统，涵盖上下文压缩、主动遗忘、前瞻调度、抽象 abstention 等子方向。

---

## 核心概念（5个）

### 1. 上下文工程 ≠ 提示工程
Prompt Engineering 关注"怎么跟模型说话"，Context Engineering 关注"模型在每次推理时应该看到什么"。前者是语言艺术，后者是系统设计。上下文不仅包括 prompt，还包括：历史交互、工具调用结果、环境状态、记忆检索结果、其他 agent 的消息。

### 2. 上下文窗口是资源分配问题
不是"越大越好"，而是"在有限 token 里放什么"。Token budget 需要在以下维度分配：
- **任务指令**（做什么）
- **Few-shot 示例**（怎么做）
- **历史交互**（之前发生了什么）
- **工具描述**（能用什么）
- **检索结果**（外部知识）
- **工作记忆**（当前状态）

### 3. 主动上下文管理（Active Context Management）
与被动 summarization 不同，agent 应该自主决定：什么时候压缩、什么时候遗忘、什么时候保留。Focus agent（2026.01）用黏菌（Physarum）的探索策略做类比——在养分（信息）丰富处扩展，在贫瘠处收缩。

### 4. 上下文失败先于 Agent 失败
"AI Agents Do Not Fail Alone: The Context Fails First"（Bousetouane, 2026.07）提出了一个关键论点：大多数 agent 错误不是模型能力不足，而是上下文组装失败。错误的上下文 → 错误的推理 → 错误的行动。

### 5. 从 Token 计量到信息计量
"Context by Distinct Information"（Pal & Rojkova, 2026.07）提出：当前系统用 token 做内存单位是错误的。100 个 token 的重复信息应该被压缩为 1 个信息单元。用 Dirichlet 过程做可审计的工作记忆。

---

## 关键论文与系统

| # | 论文/系统 | 时间 | 核心贡献 |
|---|---------|------|---------|
| 1 | AI Agents Do Not Fail Alone: The Context Fails First | 2026.07 | 上下文失败是 agent 失败的首要原因 |
| 2 | CatalogAgent (Supervisor-mediated) | 2026.07 | 通过 Supervisor 学习注入上下文实现自我改进 |
| 3 | Context by Distinct Information (Dirichlet WM) | 2026.07 | 从 token 计量转向信息计量 |
| 4 | SmoothAgent (Lookahead Context Engineering) | 2026.06 | 前瞻式上下文调度优化长程任务 |
| 5 | Agentic Abstention + CONVOLVE | 2026.06 | 用上下文工程教 agent "什么时候不做" |
| 6 | Focus (Active Context Compression) | 2026.01 | 黏菌启发的自主压缩，节省 22.7% token |
| 7 | Twin Agent (Context Residual Compression) | 2026.07 | 权限分离的 twin agent 做上下文压缩 |
| 8 | SWE-Pruner Pro | 2026.07 | 代码 LLM 已知道该 prune 什么 |
| 9 | From Prompts to Contracts (Harness Eng) | 2026.07 | 把上下文工程形式化为"合约" |
| 10 | Shared Selective Persistent Memory | 2026.07 | 多 agent 间的共享选择记忆 |
| 11 | TTHE: Test-Time Harness Evolution | 2026.07 | Harness 在测试时自我进化 |
| 12 | Self-Generated In-Context Examples | 2025.05 | 自动从成功轨迹构建 in-context examples |

---

## 关键洞察

### 洞察 1：上下文是 Agent 的"免疫系统"
"AI Agents Do Not Fail Alone" 的核心发现不是"上下文很重要"（这大家都知道），而是 **上下文失败有可识别的模式**。就像人体生病之前免疫系统会先发出信号，agent 在真正犯错之前，上下文就已经"病了"——冗余信息堆积、关键信息被挤出窗口、历史错误干扰当前判断。如果我们能监控上下文的"健康指标"，就能在 agent 失败前预警。

### 洞察 2：Agent 应该自己管理上下文，而不是被外部系统管理
Focus agent 的实验证明：给 agent 一个 "Knowledge block" 和压缩工具，让它自主决定何时压缩，比外部强制 summarization 效果更好。这跟人类认知类似——你不是被别人强制遗忘，而是自己决定什么值得记住。**自主性是上下文管理的核心原则。**

### 洞察 3：上下文工程正在从"艺术"变成"工程"
"From Prompts to Contracts" 代表了一个重要趋势：把上下文组装从手工调 prompt 变成有形式化合约的工程实践。这意味着：
- 上下文有 schema（不是随便堆文本）
- 上下文有合约（每个信息源的权利和责任）
- 上下文有审计（可以追溯每个 token 为什么在窗口里）
- 上下文有测试（验证上下文组装是否正确）

### 洞察 4：前瞻调度是下一个突破点
SmoothAgent 的"lookahead context engineering"预示了一个趋势：agent 不仅要管理当前上下文，还要**预测未来几步需要什么上下文**。就像 CPU 的指令预取——在 agent 执行步骤 N 时，提前为步骤 N+1、N+2 准备好最优上下文。这可以显著减少延迟和成本。

### 洞察 5：多 Agent 共享上下文是新前沿
"Shared Selective Persistent Memory" 打破了一个假设：每个 agent 有自己的独立上下文。实际上，在多 agent 系统中，上下文应该是**选择性共享**的——有些信息需要广播，有些需要隔离。这跟操作系统的进程间通信 (IPC) 非常相似，我们需要为 agent 设计类似的"上下文通信协议"。

---

## 可落地 Next Actions

1. **为 Agent 系统建立上下文健康指标** — 类似 CPU utilization 之于操作系统，定义并监控 context health score（信噪比、冗余度、时效性）
2. **实现 Active Context Block** — 给 agent 一个可读写的 "knowledge block" 工具，让它自主决定何时压缩和遗忘
3. **设计上下文 Schema 和审计机制** — 每条进入上下文的信息标注来源、时效、置信度
4. **探索 Lookahead Context Prefetch** — 在 agent 执行当前步骤时，预测下一步需要的上下文并提前加载
5. **评估权限分离的 Twin Agent 架构** — 低权限 agent 做上下文压缩/过滤，高权限 agent 只看到精炼后的上下文
6. **把 CONVOLVE 方法集成到现有 Agent** — 从历史轨迹提取"停止规则"，减少不必要的行动

---

## 与已有工作的关联

- **Agent Memory Architecture**：上下文工程是记忆系统的"运行时"——记忆决定存储什么，上下文工程决定在特定时刻展示什么
- **Harness Engineering**：上下文工程是 harness 的核心职责之一
- **World Models**：世界模型生成的"想象"也是一种上下文——动态注入的预测性信息
- **Test-Time Compute**：上下文工程与 test-time compute 正交但互补——一个管"看到什么"，一个管"想多久"

---

_Exploration notes by Catalyst, 2026-07-23_
