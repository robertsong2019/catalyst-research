# AI Agent 编程：深度探索笔记

**日期：** 2026-04-02
**方向：** AI Agent 编程
**时长：** ~1.5 小时
**重点：** Agent 框架生态、MCP 协议、架构模式对比

---

## 一、核心概念：什么是 AI Agent？

Agent = LLM + 工具调用循环 + 状态管理

与普通 Chatbot 的关键区别：
- **自主决策** — Agent 决定调用什么工具、何时停止
- **多步推理** — 将复杂任务分解为步骤
- **工具使用** — 连接外部系统（API、文件、数据库）
- **状态持久化** — 跨对话保持上下文

---

## 二、2025-2026 主流 Agent 框架对比

### 1. OpenAI Agents SDK
**来源：** OpenAI 官方，Swarm 的生产级升级
**核心原语（极简设计）：**
- `Agent` — LLM + 指令 + 工具
- `Handoffs` — Agent 间委托/转交
- `Guardrails` — 输入输出验证、安全检查

**特点：**
- Python-first，学习曲线极低
- 内置 tracing（可视化调试）
- MCP server 集成（直接调用 MCP 工具）
- Sessions 支持跨轮次记忆
- Realtime Agents — 基于 gpt-realtime-1.5 的语音 Agent
- Human-in-the-loop 内置机制

```python
from agents import Agent, Runner
agent = Agent(name="Assistant", instructions="You are helpful")
result = Runner.run_sync(agent, "Write a haiku about recursion")
```

**适用场景：** 快速原型、OpenAI 生态深度绑定项目

---

### 2. LangChain + LangGraph + Deep Agents
**LangChain** 是框架层，**LangGraph** 是运行时层，**Deep Agents** 是"开箱即用"的 Agent harness。

**Deep Agents 核心能力（值得关注的新方向）：**
- **任务规划** — `write_todos` 工具，自动分解任务
- **虚拟文件系统** — `ls/read_file/write_file/edit_file`，解决上下文窗口溢出
- **可插拔后端** — 内存、本地磁盘、LangGraph Store、沙箱（Modal/Daytona/Deno）
- **子 Agent 生成** — `task` 工具，为上下文隔离生成专用子 Agent
- **长期记忆** — 基于 LangGraph Memory Store 跨线程持久化

```python
from deepagents import create_deep_agent
agent = create_deep_agent(tools=[get_weather], system_prompt="...")
agent.invoke({"messages": [{"role": "user", "content": "..."}]})
```

**层次关系：**
```
Deep Agents (harness - 开箱即用)
    └── LangChain (框架 - 自定义 Agent)
        └── LangGraph (运行时 - 复杂工作流)
```

**适用场景：** 需要复杂多步任务、上下文管理、生产级持久化

---

### 3. Model Context Protocol (MCP)
**来源：** Anthropic 发起的开放协议
**定位：** Agent 与外部工具/数据的标准通信协议（类似 Agent 世界的 USB 接口）

**架构：**
```
MCP Host (AI 应用，如 Claude Desktop / VS Code)
  └── MCP Client (每个连接一个)
        └── MCP Server (提供工具/资源/提示)
```

**两层设计：**
- **数据层** — JSON-RPC 2.0，定义工具调用、资源访问、生命周期管理
- **传输层** — Stdio（本地进程）或 Streamable HTTP（远程服务）

**三大服务端原语：**
1. **Tools** — 可执行函数（查询数据库、调用 API）
2. **Resources** — 上下文数据源（文件内容、数据库 schema）
3. **Prompts** — 交互模板（system prompt、few-shot 示例）

**三大客户端原语：**
1. **Sampling** — 请求宿主 LLM 补全（服务端不需要自带 LLM）
2. **Elicitation** — 向用户请求额外信息/确认
3. **Logging** — 调试日志

**最新协议版本：** 2025-06-18
**关键特性：** 能力协商（初始化握手）、动态工具发现（`tools/list`）、实时通知

**适用场景：** 标准化工具集成、跨平台 Agent 互操作

---

### 4. OpenAI Responses API + 内置工具
OpenAI 的新 API 原语，取代 Assistants API（2026 中退役）：

- **Web Search** — 实时网络搜索，带引用
- **File Search** — RAG 管道，开箱即用
- **Computer Use** — CUA 模型，自动化 GUI 操作

**Responses API = Chat Completions 超集 + 内置工具**

---

## 三、架构模式总结

### 模式 A：单 Agent + 工具
```
User → Agent → Tool Call → Result → Agent → Response
```
最简单，适合大多数场景。

### 模式 B：多 Agent 委托（Handoffs）
```
Orchestrator Agent
  ├── Specialist Agent A (如：代码生成)
  ├── Specialist Agent B (如：测试)
  └── Specialist Agent C (如：部署)
```
每个 Agent 有独立的指令和工具集，按需转交。

### 模式 C：子 Agent 生成（Deep Agents 风格）
```
Main Agent
  ├── Task 1 → Spawn Sub-Agent (隔离上下文)
  ├── Task 2 → Spawn Sub-Agent
  └── Merge Results
```
关键创新：子 Agent 有独立的上下文窗口，避免主 Agent 上下文溢出。

### 模式 D：MCP 标准（跨平台互操作）
```
AI Application (Host)
  ├── MCP Client → MCP Server (Filesystem)
  ├── MCP Client → MCP Server (Database)
  └── MCP Client → MCP Server (Sentry)
```
通过标准协议连接任意工具，不依赖特定框架。

---

## 四、关键洞察与趋势

### 1. 上下文管理是核心竞争力
Agent 的最大瓶颈不是模型能力，而是上下文窗口管理。Deep Agents 的虚拟文件系统方案（大内容写到文件、按需读取）是一个优雅的解决方案。

### 2. MCP 正在成为行业标准
不仅是 Anthropic 在推，OpenAI Agents SDK 也原生支持 MCP。工具调用的标准化意味着：写一次 MCP Server，所有 Agent 框架都能用。

### 3. Agent Harness 是新战场
从"框架"到"harness"的演变：不只是提供工具调用循环，还提供：
- 自动任务分解
- 沙箱执行环境
- 长期记忆
- 子 Agent 编排

这很像从"Web 框架"到"全栈框架"的演变。

### 4. Guardrails 成为一等公民
OpenAI Agents SDK 把安全护栏作为核心原语。生产环境中，Agent 的可控性和可观测性比能力更重要。

### 5. Computer Use 还在早期
OSWorld 基准 38.1%，WebArena 58.1%。GUI 自动化有潜力，但可靠性不够，适合辅助而非全自动。

---

## 五、对我们的实践启示

### OpenClaw 自身的定位
OpenClaw 实际上已经实现了上述多个模式：
- **单 Agent + 工具** — 主 Agent + 各种 skill
- **子 Agent 生成** — `sessions_spawn` 隔离上下文
- **MCP 集成** — 通过 mcporter 调用 MCP server
- **上下文管理** — MEMORY.md + daily notes 体系

### 可探索的方向
1. **实现 MCP Server** — 把 OpenClaw 的能力暴露为 MCP Server，让其他 Agent 框架也能调用
2. **Deep Agents 风格的虚拟文件系统** — 处理长上下文任务时自动卸载到文件
3. **Guardrails 模式** — 为外部操作添加更结构化的安全验证

---

## 六、参考资源

- MCP 架构文档：https://modelcontextprotocol.io/docs/learn/architecture
- OpenAI Agents SDK：https://openai.github.io/openai-agents-python/
- LangChain Deep Agents：https://docs.langchain.com/oss/python/deepagents/overview
- OpenAI Responses API 公告：https://openai.com/index/new-tools-for-building-agents/

---

*探索完成时间：2026-04-02 20:30 CST*
