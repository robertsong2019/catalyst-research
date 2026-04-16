# 多Agent框架集成模式深度研究

> 日期: 2026-04-15
> 主题: CrewAI/LangGraph/Google ADK + A2A 协议的集成架构
> 方法论: autoresearch — 明确指标、快速循环、积累性

---

## 核心概念 (5个)

### 1. 编排模型三范式

| 范式 | 代表框架 | 核心抽象 | 适用场景 |
|------|---------|---------|---------|
| **有向图 (Graph)** | LangGraph | StateGraph + Conditional Edges | 复杂有状态工作流、需要checkpointing |
| **角色团队 (Crew)** | CrewAI | Agent(role, goal, tools) + Task + Crew | 快速原型、内容生成、角色清晰的任务 |
| **对话式 (Chat)** | AutoGen | GroupChat + Speaker Selection | 研究、代码审查、需要讨论协商的任务 |

**关键差异在三个维度**: 编排模型、状态管理、通信模式。

### 2. Supervisor 模式（2026 生产级标配）

LangGraph 的 `langgraph-supervisor` 库提供了生产级 Supervisor 模式：
- Supervisor 用 LLM 决定路由到哪个 Worker
- Handoff 机制：`create_handoff_tool()` 自动生成委派工具
- 支持层级嵌套：Supervisor → Team → Agent
- 内置短期/长期记忆、Human-in-the-loop

**vs CrewAI**: CrewAI 的角色编排更直观，但状态管理不如 LangGraph 精细。
**vs Swarm**: 当需要 Worker 持续对话（不立即返回 Supervisor）时，用 Swarm 而非 Supervisor。

### 3. A2A 协议 — 跨框架通信标准

A2A (Agent-to-Agent) 已成为跨框架互操作的事实标准：
- **Agent Card**: `.well-known/agent.json` — Agent 的 DNS，描述能力
- **Task Lifecycle**: 发送 → 执行 → 流式/批量返回
- **Transport-agnostic**: HTTP/JSON + SSE，框架无关

**关键发现**: 
- Google ADK 原生支持 A2A（`to_a2a()` 一行转换）
- Microsoft Agent Framework 也通过 `A2AAgent` 支持 A2A
- CrewAI 已添加 A2A 支持
- LangGraph 尚未原生支持（社区集成存在）

### 4. MCP + A2A 双栈架构

```
┌─────────────────────────────────────┐
│           Application Layer          │
│  (CrewAI / LangGraph / ADK / Custom) │
├──────────────┬──────────────────────┤
│   MCP (纵向)  │   A2A (横向)          │
│ Agent → 工具  │ Agent → Agent         │
│ 97M+ 下载量   │ 50+ 企业支持          │
├──────────────┴──────────────────────┤
│          Transport Layer             │
│   (HTTP/SSE / STDIO / gRPC)         │
└─────────────────────────────────────┘
```

**生产实践**: LangGraph + MCP Server 的组合已成熟 — 每个 Worker Agent 绑定不同的 MCP Server，Supervisor 路由任务到对应 Worker。

### 5. 框架选择决策树

```
需要多Agent?
├── 否 → 单 Agent (ReAct / Tool Use)
├── 是
│   ├── 任务边界清晰、角色分工明确?
│   │   ├── 是 → CrewAI (快速原型)
│   │   └── 需要可审计状态? → LangGraph Supervisor
│   ├── 需要跨框架互操作?
│   │   ├── 是 → A2A 协议 + Google ADK
│   │   └── 否 → 单框架即可
│   └── 需要长时间运行 + 容错?
│       └── LangGraph (checkpointer + Time Travel)
```

---

## 代码示例: 零依赖 Multi-Agent Supervisor（可运行）

> 灵感来自 LangGraph Supervisor，但零依赖实现核心概念。
> 与 OpenClaw 的 `sessions_spawn` 模式高度对应。

```python
#!/usr/bin/env python3
"""
Zero-Dependency Multi-Agent Supervisor Pattern
Inspired by LangGraph's create_supervisor, but self-contained.

Demonstrates: Supervisor routing, Worker specialization, State management
"""

import json
import re
from typing import Callable
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str  # "user" | "supervisor" | agent_name
    content: str


@dataclass  
class AgentState:
    messages: list = field(default_factory=list)
    next: str = "supervisor"
    iterations: int = 0
    max_iterations: int = 10


class Worker:
    """A specialized worker agent with specific tools."""
    
    def __init__(self, name: str, description: str, 
                 handler: Callable[[str], str]):
        self.name = name
        self.description = description
        self.handler = handler
    
    def execute(self, task: str) -> str:
        return self.handler(task)


class Supervisor:
    """Routes tasks to workers based on keyword matching.
    
    In production, this would use an LLM with structured output.
    Here we use simple rules for zero-dependency demo.
    """
    
    def __init__(self, workers: list[Worker]):
        self.workers = {w.name: w for w in workers}
        self.routing_rules: dict[str, list[str]] = {}
    
    def add_route(self, worker_name: str, keywords: list[str]):
        """Add routing rule: if any keyword appears, route to this worker."""
        self.routing_rules[worker_name] = keywords
    
    def route(self, message: str) -> tuple[str | None, Worker | None]:
        """Decide which worker to route to, or None to finish."""
        msg_lower = message.lower()
        for worker_name, keywords in self.routing_rules.items():
            if any(kw in msg_lower for kw in keywords):
                return worker_name, self.workers[worker_name]
        return None, None  # No matching worker → FINISH


class MultiAgentOrchestrator:
    """Orchestrates supervisor + workers with state management."""
    
    def __init__(self, supervisor: Supervisor):
        self.supervisor = supervisor
        self.history: list[dict] = []
    
    def run(self, user_input: str, verbose: bool = True) -> str:
        state = AgentState(messages=[Message("user", user_input)])
        
        while state.iterations < state.max_iterations:
            state.iterations += 1
            current_msg = state.messages[-1].content
            
            # Supervisor routes
            worker_name, worker = self.supervisor.route(current_msg)
            
            if worker is None:
                if verbose:
                    print(f"  [supervisor] → FINISH (iteration {state.iterations})")
                break
            
            if verbose:
                print(f"  [supervisor] → {worker_name}")
            
            # Worker executes
            result = worker.execute(current_msg)
            state.messages.append(Message(worker_name, result))
            
            if verbose:
                preview = result[:80].replace('\n', ' ')
                print(f"  [{worker_name}] {preview}...")
            
            self.history.append({
                "iteration": state.iterations,
                "worker": worker_name,
                "input_preview": current_msg[:50],
                "output_preview": result[:50],
            })
        
        # Return last worker result or supervisor summary
        if len(state.messages) > 1:
            return state.messages[-1].content
        return "No worker could handle this task."


# === Demo: Research + Code + Writer Team ===

def research_handler(task: str) -> str:
    """Simulated research agent."""
    findings = []
    if "python" in task.lower():
        findings.append("Python 3.13 introduced free-threaded mode (no-GIL)")
    if "ai" in task.lower() or "agent" in task.lower():
        findings.append("A2A protocol enables cross-framework agent communication")
        findings.append("MCP is the standard for agent-tool integration")
    if "framework" in task.lower():
        findings.append("LangGraph: graph-based, production state management")
        findings.append("CrewAI: role-based teams, fastest prototyping")
    if not findings:
        findings.append("General research: topic requires further investigation")
    return "Research findings:\n" + "\n".join(f"- {f}" for f in findings)


def code_handler(task: str) -> str:
    """Simulated code agent."""
    return (
        "# Generated code based on research\n"
        "from typing import TypedDict\n\n"
        "class AgentCard(TypedDict):\n"
        "    name: str\n"
        "    description: str\n"
        "    capabilities: list[str]\n\n"
        "def create_agent_card(name: str, desc: str) -> AgentCard:\n"
        f"    return {{'name': name, 'description': desc, 'capabilities': []}}\n"
        f"# Ready for A2A protocol integration"
    )


def writer_handler(task: str) -> str:
    """Simulated writer agent."""
    return (
        "# Multi-Agent Integration Report\n\n"
        "## Summary\n"
        "Based on research and code analysis, the recommended approach "
        "is a Supervisor pattern with LangGraph for orchestration, "
        "MCP for tool access, and A2A for cross-framework communication.\n\n"
        "## Key Recommendation\n"
        "Start with CrewAI for rapid prototyping, migrate critical paths "
        "to LangGraph as complexity grows."
    )


def main():
    # Create workers
    workers = [
        Worker("research_agent", "Searches and analyzes information", research_handler),
        Worker("code_agent", "Generates and executes code", code_handler),
        Worker("writer_agent", "Synthesizes findings into reports", writer_handler),
    ]
    
    # Setup supervisor with routing rules
    supervisor = Supervisor(workers)
    supervisor.add_route("research_agent", ["research", "find", "search", "what is", "analyze"])
    supervisor.add_route("code_agent", ["code", "implement", "build", "create", "write a script"])
    supervisor.add_route("writer_agent", ["report", "summarize", "write", "document"])
    
    # Create orchestrator
    orchestrator = MultiAgentOrchestrator(supervisor)
    
    # Run example tasks
    tasks = [
        "Research the latest AI agent frameworks and find key differences",
        "Write code to implement an agent card for A2A protocol",
    ]
    
    for task in tasks:
        print(f"\n{'='*60}")
        print(f"Task: {task}")
        print(f"{'='*60}")
        result = orchestrator.run(task)
        print(f"\nFinal result:\n{result[:200]}...\n")
    
    # Print execution history
    print(f"\n{'='*60}")
    print("Execution History (JSON):")
    print(json.dumps(orchestrator.history, indent=2))


if __name__ == "__main__":
    main()
```

**运行方式**: `python3 multi_agent_supervisor.py` — 零依赖，Python 3.10+

---

## 关键洞察 (5条)

### 1. LangGraph Supervisor 已取代手动图编排

`langgraph-supervisor` 库让 Supervisor 模式变成 10 行代码的事。不需要手动定义 StateGraph 的 nodes/edges。但**注意**: LangGraph 团队现在推荐用 tool-calling supervisor 模式而非这个库，因为 tool-calling 给更多上下文控制权。

**与 OpenClaw 的对应**:
- OpenClaw `sessions_spawn` = LangGraph `create_react_agent` (创建 Worker)
- OpenClaw main session = Supervisor
- OpenClaw `subagents steer` = Handoff back to supervisor

### 2. 框架混合使用正在成为常态

2026 年的最佳实践不再是"选一个框架"，而是**框架混合**：
- CrewAI 处理研究和合成（快速、角色化）
- LangGraph 处理执行（确定性、可审计、Human-in-loop）
- 交接点是**结构化 JSON 对象** — 框架无关、可调试

**对 OpenClaw 的启示**: OpenClaw 可以作为"元编排层"，通过 A2A 协议连接不同框架的 Agent。

### 3. A2A 是真正的游戏改变者

A2A 协议解决了框架锁定的核心问题：
- Google ADK: `to_a2a(root_agent)` 一行暴露为 A2A 服务
- Microsoft Agent Framework: `A2AAgent` 包装器
- CrewAI: 已支持 A2A
- LangGraph: 社区集成中

**Agent Card 是 Agent 的 DNS** — 标准 JSON 格式描述能力，让 Agent 发现成为可能。

### 4. 本地模型的多 Agent 门槛

关键发现: **多 Agent 流水线需要协调者使用 32B+ 参数模型**。Worker 可以用 7B 小模型（专注单域任务）。但规划瓶颈在协调者级别 — 70B supervisor + 7B workers > 四个 32B agents。

**对边缘部署的启示**: Edge Agent Runtime 的 Supervisor 模块需要更强的模型支持。

### 5. 状态管理是框架的核心差异化

| 框架 | 状态管理 | 适用场景 |
|------|---------|---------|
| LangGraph | 内置 Checkpointing + Time Travel | 长时间运行、需要回滚 |
| CrewAI | 任务输出顺序传递 | 短期工作流 |
| AutoGen | 对话历史（内存） | 研究讨论 |
| Google ADK | Session State + 可插拔后端 | 云原生部署 |

**OpenClaw 优势**: 天然有 session 状态 + memory 系统，可复用。

---

## 下一步行动 (3个)

### 1. 实现 OpenClaw → LangGraph/CrewAI 桥接原型 (本周)
- 用 `sessions_spawn` 创建 Worker（subagent 模式）
- 主 session 作为 Supervisor，用 A2A 协议通信
- 目标: 一个 OpenClaw agent 能编排 CrewAI/LangGraph 的 worker

### 2. 设计 Agent Card Schema for OpenClaw
- 参考 A2A 规范，定义 OpenClaw Agent 的标准能力描述
- 发布为 `.well-known/agent.json`
- 让外部框架能发现和调用 OpenClaw 的工具

### 3. MCP + A2A 双栈集成实验
- 将 OpenClaw 现有工具（web_search, memory_search, exec）暴露为 MCP Server
- 同时暴露为 A2A Agent Card
- 验证与 LangGraph/CrewAI 的双向通信

---

## 框架对比速查 (2026 Q2)

| 维度 | LangGraph v1.0 | CrewAI v1.8 | Google ADK | AutoGen v2 |
|------|---------------|-------------|------------|------------|
| **编排** | 有向图 + 条件边 | 角色团队 + Flows | 层级 Agent 树 | 对话式 GroupChat |
| **学习曲线** | 2-3 周 | 1 周 | 1-2 周 | 1-2 周 |
| **状态** | Checkpointing | 顺序传递 | Session + 可插拔 | 对话历史 |
| **A2A 支持** | 社区 | ✅ 原生 | ✅ 原生 | ❌ |
| **MCP 支持** | ✅ langchain-mcp-adapters | ✅ | ✅ | ❌ |
| **生产就绪** | ✅ GA | ✅ GA | ✅ | ✅ GA |
| **最佳场景** | 复杂有状态工作流 | 快速角色化原型 | 跨框架互操作 | 研究/讨论 |

---

## 与现有项目关联

- **OpenClaw MCP Server** (待实现) → 本研究的 MCP + A2A 双栈是核心架构
- **A2A Protocol Lab** (已完成) → 可直接用 A2A 协议做跨框架通信
- **Agent Trust Network** → 在 A2A Agent Card 中嵌入信任元数据
- **Edge Agent Mesh** → Supervisor 模式适用于 Mesh 的协调者选举
- **Agent Memory Service** → LangGraph 的 Checkpointer 可参考记忆分层设计

---

*研究耗时: ~30 min | 来源: 10+ 技术文章 + 官方文档 | 方法论: autoresearch*
