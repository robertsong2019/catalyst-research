# 深度探索：AI Agent 编程（2026-04-06）

> 方向：AI Agent Programming — 自主编程 Agent 的架构、框架与生态
> 耗时：约 2 小时深度阅读与整理

---

## 一、领域概览

AI Agent 编程是指让 AI 自主完成软件工程任务（写代码、调试、重构、测试、PR），而非仅仅作为代码补全工具。2025-2026 年这个领域爆发式增长，形成了三大范式：

1. **自主编码 Agent**（Autonomous Coding Agent）— Claude Code、OpenAI Codex、Deep Agents
2. **多 Agent 协作框架**（Multi-Agent Framework）— CrewAI、LangGraph、AutoGen
3. **Agent 编排与运行时**（Agent Orchestration Runtime）— LangGraph、OpenClaw

---

## 二、核心玩家深度分析

### 2.1 Claude Code（Anthropic）

**定位：** 终端/IDE/Desktop/Web 全平台的自主编码 Agent

**架构特点：**
- 读取整个代码库，跨文件编辑
- 可运行 shell 命令（测试、lint、构建）
- **CLAUDE.md** — 项目级指令文件，类似 AGENTS.md，让 Agent 了解项目约定
- **Auto Memory** — 自动学习构建命令、调试经验等
- **MCP（Model Context Protocol）** — 开放标准，连接外部数据源（Google Drive、Jira、Slack）
- **Sub-agents** — 主 Agent 协调多个子 Agent 并行工作
- **Hooks** — 文件编辑后自动格式化、提交前运行 lint 等生命周期钩子
- **Agent SDK** — 可构建自定义 Agent，完全控制编排、工具访问、权限

**关键洞察：**
- 多平台同一引擎（Terminal/VS Code/JetBrains/Desktop/Web/iOS）
- Unix 哲学：可组合、可管道（`tail -200 app.log | claude -p "分析异常"`）
- 计划任务（Cloud Scheduled Tasks）— 定时执行 PR review、CI 分析、依赖审计
- Remote Control — 手机继续桌面上的工作

### 2.2 OpenAI Codex

**定位：** 云端并行软件工程 Agent

**架构特点：**
- 基于 codex-1（o3 的软件工程优化版本）
- 每个任务在独立云沙箱中运行，预加载代码库
- 可并行处理多个任务
- 通过 AGENTS.md 文件引导 Agent 理解代码库
- 可验证输出：引用终端日志和测试结果

**关键洞察：**
- 沙箱隔离（默认禁用互联网）— 安全第一
- codex-mini — 低延迟版本用于 CLI 场景
- "信任但验证"设计哲学 — Agent 完成任务，人审查后合并
- 实际使用场景：重构、重命名、写测试、搭建新功能、调试

### 2.3 Deep Agents（LangChain）

**定位：** 开箱即用的 Agent Harness，受 Claude Code 启发

**架构特点：**
- **Planning** — `write_todos` 任务分解与进度跟踪
- **Filesystem** — `read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep`
- **Shell Access** — `execute` 运行命令（带沙箱）
- **Sub-agents** — `task` 委派工作，隔离上下文窗口
- **Context Management** — 对话过长时自动摘要，大输出保存到文件
- **MCP 支持** — 通过 `langchain-mcp-adapters`

**关键洞察：**
- "信任 LLM"模型 — Agent 可以做工具允许的任何事情，在工具/沙箱层面设限
- 基于 LangGraph，支持 streaming、persistence、checkpointing
- Provider agnostic — 可用任何支持 tool calling 的 LLM
- 有 CLI 版本，类似 Claude Code 的终端体验

---

## 三、多 Agent 框架对比

### 3.1 CrewAI

**核心理念：** Role-playing autonomous agents（角色扮演自主 Agent）

**两个核心概念：**
- **Crews** — Agent 团队，通过角色协作完成任务
  - 自然自主决策
  - 动态任务委派
  - 专业化角色与目标
- **Flows** — 生产级事件驱动工作流
  - 精细控制执行路径
  - 安全一致的状态管理
  - 条件分支与业务逻辑

**架构特点：**
- 完全独立，不依赖 LangChain
- `@start()` 和 `@listen()` 装饰器模式
- 结构化状态管理（Pydantic BaseModel）
- 可视化 Flow（`flow.plot()` 生成 HTML）

**项目结构：**
```
my_project/
├── src/my_project/
│   ├── main.py      # 入口
│   ├── crew.py      # Agent 定义
│   ├── tools/       # 自定义工具
│   └── config/
│       ├── agents.yaml  # Agent 角色配置
│       └── tasks.yaml   # 任务配置
```

### 3.2 LangGraph

**核心理念：** 以图（Graph）的形式编排 Agent，低级别控制

**核心能力：**
- **Durable Execution** — 故障后持久化，可恢复
- **Human-in-the-loop** — 任何执行点可中断、检查、修改
- **Comprehensive Memory** — 短期工作记忆 + 长期持久记忆
- **Streaming** — 实时流式输出
- **Production Deployment** — 通过 LangSmith 部署

**架构模式：**
```python
from langgraph.graph import StateGraph, MessagesState, START, END

graph = StateGraph(MessagesState)
graph.add_node(mock_llm)
graph.add_edge(START, "mock_llm")
graph.add_edge("mock_llm", END)
graph = graph.compile()
```

**设计灵感：** Google Pregel + Apache Beam + NetworkX

---

## 四、架构模式总结

### 4.1 单 Agent 深度执行模式
- 代表：Claude Code、Codex CLI
- 特点：一个 Agent 拥有完整工具链（文件读写、Shell、搜索）
- 适合：代码编写、重构、调试等单人可完成的任务

### 4.2 多 Agent 协作模式
- 代表：CrewAI Crews、Claude Code Sub-agents
- 特点：多个专业化 Agent 分工协作
- 适合：研究+报告、多模块并行开发

### 4.3 图编排模式
- 代表：LangGraph、CrewAI Flows
- 特点：以有向图定义执行流，支持条件分支、循环
- 适合：复杂业务流程、需要精确控制的生产系统

### 4.4 Harness 模式
- 代表：Deep Agents、OpenClaw
- 特点：预置工具集（规划、文件、Shell、子Agent），开箱即用
- 适合：快速搭建自定义 Agent

---

## 五、关键技术趋势

1. **Agent Memory 成为标配**
   - 短期：对话上下文
   - 长期：CLAUDE.md / auto memory / checkpointing
   - 跨会话：文件系统持久化

2. **Sandbox 安全模型**
   - Codex：云沙箱，默认离线
   - Claude Code：权限分级，hooks 控制
   - Deep Agents：工具层限权

3. **MCP（Model Context Protocol）成为连接标准**
   - 让 Agent 连接外部工具和数据源
   - 类似 USB-C for AI tools

4. **AGENTS.md / CLAUDE.md 模式**
   - 项目根目录放置 Agent 指令文件
   - 告诉 Agent 项目结构、测试命令、编码规范
   - 已被 Codex、Claude Code 等广泛支持

5. **Human-in-the-loop 是必须的**
   - 所有框架都支持中断、审查、修改
   - Agent 完成任务，人类审查后合并

6. **Sub-agent 编排**
   - 主 Agent 分解任务，子 Agent 并行执行
   - 隔离上下文窗口，避免 token 溢出

---

## 六、框架选择建议

| 场景 | 推荐框架 |
|------|----------|
| 个人编码辅助 | Claude Code / Codex CLI |
| 快速搭建自定义 Agent | Deep Agents |
| 多角色协作 | CrewAI |
| 复杂生产工作流 | LangGraph |
| 需要持久化+恢复 | LangGraph |
| 研究原型 | CrewAI Flows |

---

## 七、对 OpenClaw 的启示

作为个人 Agent 平台，OpenClaw 的定位和这些框架有交集但侧重不同：

- **相同点：** Sub-agents、MCP、工具调用、cron 调度
- **差异点：** OpenClaw 更注重个人助手全场景（消息、文档、记忆），而非专注编码
- **可借鉴：**
  - Deep Agents 的 auto-summarization 和 context management
  - CrewAI 的 Flow 可视化
  - Claude Code 的 auto memory 学习模式
  - AGENTS.md 标准化项目指令

---

## 八、关键资源

- Claude Code 文档：https://code.claude.com/docs
- OpenAI Codex：https://openai.com/index/introducing-codex/
- CrewAI 文档：https://docs.crewai.com
- LangGraph 文档：https://docs.langchain.com/oss/python/langgraph/overview
- Deep Agents：https://github.com/langchain-ai/deepagents
- MCP 协议：https://modelcontextprotocol.io

---

*探索完成时间：2026-04-06 20:10 CST*
