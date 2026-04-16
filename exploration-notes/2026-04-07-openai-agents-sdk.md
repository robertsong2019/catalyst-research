# OpenAI Agents SDK 深度学习笔记

**日期：** 2026-04-07
**主题：** AI Agent 编程 — OpenAI Agents SDK 架构与设计模式
**来源：** https://openai.github.io/openai-agents-python/

---

## 一、SDK 概览

OpenAI Agents SDK 是 Swarm（实验性项目）的生产级升级版，设计理念：
- **足够有用但原语极少** — 学习成本低，表达能力强
- **开箱即用但可定制** — 默认行为合理，细节可控

核心原语只有 3 个：
1. **Agent** — 配备指令和工具的 LLM
2. **Handoffs / Agents as Tools** — Agent 间委托和协作
3. **Guardrails** — 输入输出验证和安全检查

安装：`pip install openai-agents`

---

## 二、Agent 编排（Orchestration）

两种核心编排方式，可混合使用：

### 2.1 LLM 驱动编排
让 LLM 自主规划、推理和决策：
- **Agents as Tools（管理器模式）**：管理 Agent 保持对话控制权，通过 `Agent.as_tool()` 调用专家 Agent
  - 适合：需要一个 Agent 拥有最终答案，合并多个专家输出
- **Handoffs（交接模式）**：分诊 Agent 将对话路由给专家，专家接管后续交互
  - 适合：专家需要直接响应用户，保持 prompt 聚焦

**最佳实践：**
- 投资好的 prompt — 明确工具用途和参数
- 监控并迭代 — 看哪里出错就改哪里
- 允许 Agent 自省和改进（循环+自我批评）
- 专业化 > 通用化 — 让每个 Agent 擅长一件事
- 投资评估（evals）来训练和改进

### 2.2 代码驱动编排
通过代码控制流程，更确定性和可预测：
- **结构化输出分类** → 根据 LLM 分类结果选 Agent
- **链式处理**：研究 → 大纲 → 写作 → 评审 → 改进
- **评估循环**：while 循环 + 评估 Agent 反馈
- **并行执行**：`asyncio.gather` 同时跑多个独立任务

---

## 三、工具系统（Tools）

五种工具类型：

| 类型 | 说明 |
|------|------|
| **Hosted OpenAI Tools** | 托管在 OpenAI 服务器：WebSearch, FileSearch, CodeInterpreter, HostedMCP, ImageGen |
| **Local Runtime Tools** | 本地执行：ComputerTool（GUI自动化）, ShellTool, ApplyPatchTool |
| **Function Tools** | 任意 Python 函数 → 工具，自动 schema 生成 + Pydantic 校验 |
| **Agents as Tools** | 将 Agent 作为可调用工具 |
| **Codex Tool (实验性)** | 从工具调用中运行工作区范围的 Codex 任务 |

### Tool Search（工具搜索）
- 延迟加载大量工具，模型按需加载子集
- `tool_namespace()` 将相关工具分组（如 CRM、billing、shipping）
- 每个命名空间建议 < 10 个函数
- 减少工具 schema 的 token 消耗

### ShellTool 双模式
- **Hosted Container**：OpenAI 托管容器执行，支持 skills 引用
- **Local Runtime**：本地进程执行

---

## 四、Handoffs 深入

Handoff 本质上是暴露给 LLM 的工具（如 `transfer_to_refund_agent`）。

关键配置：
- `on_handoff`：回调函数，在 handoff 触发时执行（如预加载数据）
- `input_type`：Pydantic 模型，定义 handoff 时 LLM 需提供的结构化参数
- `input_filter`：控制下一个 Agent 能看到的对话历史
- `is_enabled`：动态启用/禁用 handoff

### Input Filter 模式
`HandoffInputData` 包含：
- `input_history`：run 开始前的输入
- `pre_handoff_items`：handoff 前的项目
- `new_items`：当前轮次生成的项目
- `run_context`：运行时上下文

内置过滤器：`handoff_filters.remove_all_tools` — 移除历史中的所有工具调用

### 嵌套 Handoff（Beta）
`RunConfig.nest_handoff_history=True` — 将之前对话压缩为摘要消息，用 `<CONVERSATION HISTORY>` 块包裹

---

## 五、Guardrails（护栏）

三类护栏：

### Input Guardrails
- 只在 **第一个 Agent** 运行
- 两种执行模式：
  - **Parallel**（默认）：与 Agent 并行执行，延迟低但可能已消耗 token
  - **Blocking**：先完成检查再启动 Agent，节省成本

### Output Guardrails
- 只在 **最终产出 Agent** 运行
- 始终在 Agent 完成后执行

### Tool Guardrails
- 在每个函数工具调用时执行（最细粒度）
- 输入/输出各一个 guardrail
- 可 `reject_content` 或 `allow`

**Tripwire 机制：** 任何 guardrail 触发 tripwire → 立即抛出异常并停止执行

---

## 六、Session 管理

SDK 内置会话记忆，自动维护对话历史：

### 内置实现

| 实现 | 适用场景 |
|------|----------|
| SQLiteSession | 本地开发、简单应用 |
| AsyncSQLiteSession | 异步 SQLite |
| RedisSession | 分布式部署、低延迟 |
| SQLAlchemySession | 生产级、已有数据库 |
| DaprSession | 云原生、Dapr sidecar |
| OpenAIConversationsSession | OpenAI 服务端存储 |
| OpenAIResponsesCompactionSession | 长对话自动压缩 |
| AdvancedSQLiteSession | SQLite + 分支/分析 |
| EncryptedSession | 加密包装器 |

### 关键特性
- **自动合并**：每次 run 前自动获取历史，run 后自动存储新项目
- **SessionSettings**：控制获取历史数量（`limit=N`）
- **session_input_callback**：自定义历史与新输入的合并逻辑
- **pop_item**：撤销/修正最近的消息

### Compaction Session
包装另一个 session 后端，自动压缩长对话：
- `compaction_mode="auto"` 默认选择最安全的方式
- 注意：压缩可能阻塞流式传输

---

## 七、架构设计洞察

### 设计哲学
1. **Python-first**：用 Python 语言特性编排，而非学习新抽象
2. **最小原语**：Agent + Tool + Handoff + Guardrail 覆盖大部分场景
3. **渐进式复杂度**：从简单开始，按需添加

### 与其他框架对比（思考）
- **vs LangGraph**：LangGraph 用图/状态机定义流程，更结构化但学习曲线陡；Agents SDK 更轻量
- **vs CrewAI**：CrewAI 强调角色协作和任务分解；Agents SDK 更底层、更灵活
- **vs 直接 API 调用**：Agents SDK 处理了 agent loop、tool calling 循环、tracing 等样板代码

### 适用场景判断
- 简单 chatbot → 直接 API 调用
- 多专家协作 → Agents SDK（Handoffs / Agents as Tools）
- 复杂工作流图 → LangGraph
- 需要精细控制 → 代码编排 + Agents SDK

---

## 八、关键代码模式速查

### 基础 Agent
```python
from agents import Agent, Runner
agent = Agent(name="Assistant", instructions="You are helpful")
result = Runner.run_sync(agent, "Hello")
```

### Agent as Tool（管理器模式）
```python
research_agent = Agent(name="Researcher", ...)
writer_agent = Agent(name="Writer", ...)
manager = Agent(
    name="Manager",
    tools=[research_agent.as_tool(), writer_agent.as_tool()]
)
```

### Handoff（交接模式）
```python
billing = Agent(name="Billing", handoff_description="处理账单问题")
refund = Agent(name="Refund", handoff_description="处理退款请求")
triage = Agent(name="Triage", handoffs=[billing, refund])
```

### 带会话记忆
```python
from agents import Agent, Runner, SQLiteSession
session = SQLiteSession("user_123")
result = await Runner.run(agent, "Hello", session=session)
# 下一轮自动记忆
result = await Runner.run(agent, "Follow up", session=session)
```

---

## 九、下一步探索方向

- [ ] 实际搭建一个多 Agent 项目试玩
- [ ] 研究 MCP (Model Context Protocol) 集成
- [ ] 了解 Realtime Agent（语音 Agent）架构
- [ ] 对比 Google ADK、Anthropic tool use 的设计差异
- [ ] 研究 Agent evals（评估）的最佳实践

---

*学习时间：约 40 分钟文档阅读 | 笔记整理：Catalyst 🧪*
