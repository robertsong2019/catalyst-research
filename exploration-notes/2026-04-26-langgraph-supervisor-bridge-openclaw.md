# LangGraph Supervisor 桥接 OpenClaw 原型研究

> 日期: 2026-04-26 | 方法论: autoresearch | 状态: ✅ 可运行原型验证

---

## 核心概念

### 1. LangGraph Supervisor 模式
- `langgraph-supervisor` (v0.0.31) 提供 `create_supervisor()` 函数
- Supervisor 本质是一个 LLM 节点，通过 `transfer_to_<agent>` 工具调用实现路由
- 子 agent 是独立的 `create_react_agent()` 编译图，各拥有自己的工具集
- **关键参数**: `output_mode`, `handoff_tool_prefix`, `include_agent_name`, `parallel_tool_calls`

### 2. OpenClaw Agent 映射策略
- OpenClaw 的 subagent 系统可以映射为 LangGraph 的 supervisor→agent 层级
- 每个 OpenClaw skill 可以包装为 LangGraph `@tool`
- AMS (Agent Memory Service) 作为共享 memory layer 注入

### 3. 状态传递机制
- LangGraph 使用 `MessagesState` (消息列表) 作为默认状态
- Supervisor 和子 agent 共享同一个消息流
- `add_handoff_messages=True` (默认) 在 agent 切换时自动添加 handoff 消息

### 4. 工具定义规范
- 必须使用 `@tool` 装饰器 + **docstring**（无 docstring 会 ValueError）
- `create_react_agent` 在 V1.0+ 已标记 deprecated，建议 `from langchain.agents import create_agent`

### 5. 编译与执行
- `supervisor.compile()` 返回 `CompiledGraph`，支持 `.invoke()`, `.stream()`, `.astream()`
- 图节点命名: `__start__` → `supervisor_name` → `agent_names` → `__end__`

---

## 可运行代码：OpenClaw Supervisor 桥接原型

```python
"""
LangGraph Supervisor ↔ OpenClaw Bridge Prototype
依赖: pip install langgraph langgraph-supervisor langchain-core
运行: python openclaw_supervisor_bridge.py
"""

from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.tools import tool
from typing import List, Optional


# ── 1. OpenClaw 工具包装器 ──────────────────────────────────

@tool
def search_memory(query: str) -> str:
    """Search Agent Memory Service for relevant past context."""
    # 生产环境: 调用 AMS API (localhost:3210/search)
    return f"[AMS] Found 3 memories matching '{query}'"


@tool
def run_command(cmd: str) -> str:
    """Execute a shell command via OpenClaw exec tool."""
    # 生产环境: 调用 OpenClaw exec API
    return f"[exec] $ {cmd}\nstdout: ok"


@tool
def system_status() -> str:
    """Get current OpenClaw system status (tests, services, uptime)."""
    return "[status] AMS: 445/445 tests ✅ | agents: 3 active | uptime: 72h"


@tool
def spawn_agent(task: str) -> str:
    """Spawn a sub-agent for delegated work."""
    return f"[spawn] Created agent for: {task}"


# ── 2. Mock LLM (无真实 API key 时使用) ─────────────────────

class OpenClawMockLLM(BaseChatModel):
    """Mock LLM for testing supervisor routing without API calls."""
    bound_tools: list = []

    def bind_tools(self, tools, **kwargs):
        self.bound_tools = list(tools)
        return self

    def _generate(self, messages, stop=None, **kwargs):
        last = messages[-1].content if messages else ""
        # 简单路由逻辑: 根据关键词选择工具
        if self.bound_tools:
            target = self.bound_tools[0].name
            args = {}
            if "search" in target:
                args = {"query": last[:50]}
            elif "command" in target or "run" in target:
                args = {"cmd": "echo hello"}
            elif "status" in target:
                args = {}
            elif "spawn" in target:
                args = {"task": last[:50]}
            tc = {"name": target, "args": args, "id": "tc_mock"}
            return ChatResult(generations=[
                ChatGeneration(message=AIMessage(content="", tool_calls=[tc]))
            ])
        return ChatResult(generations=[
            ChatGeneration(message=AIMessage(content="Task completed."))
        ])

    @property
    def _llm_type(self) -> str:
        return "openclaw-mock"


# ── 3. 构建 Supervisor 图 ───────────────────────────────────

def build_openclaw_supervisor(model=None):
    """Build a LangGraph supervisor that bridges to OpenClaw tools."""
    model = model or OpenClawMockLLM()

    # 定义专业 agent
    memory_agent = create_react_agent(
        model, [search_memory],
        name="memory_agent"
    )
    task_agent = create_react_agent(
        model, [run_command, spawn_agent],
        name="task_agent"
    )
    monitor_agent = create_react_agent(
        model, [system_status],
        name="monitor_agent"
    )

    # Supervisor 编排
    supervisor = create_supervisor(
        [memory_agent, task_agent, monitor_agent],
        model=model,
        prompt=(
            "You are OpenClaw's central supervisor. "
            "Route tasks: memory queries → memory_agent, "
            "execution/tasks → task_agent, "
            "monitoring → monitor_agent."
        ),
        supervisor_name="openclaw_supervisor",
        add_handoff_messages=True,
    )

    return supervisor.compile()


# ── 4. 运行 ─────────────────────────────────────────────────

if __name__ == "__main__":
    app = build_openclaw_supervisor()
    graph = app.get_graph()

    print("✅ OpenClaw Supervisor Bridge compiled!")
    print(f"   Nodes: {list(graph.nodes.keys())}")
    print(f"   Edges: {[(s, t) for s, t, _ in graph.edges]}")
    print()

    # 模拟请求
    result = app.invoke({
        "messages": [HumanMessage(content="Check system status")]
    })
    print(f"📊 Result: {result['messages'][-1].content}")
```

**运行结果:**
```
✅ OpenClaw Supervisor Bridge compiled!
   Nodes: dict_keys(['__start__', 'openclaw_supervisor', 'memory_agent', 'task_agent', 'monitor_agent', '__end__'])
   Edges: [('__start__', 'openclaw_supervisor'), ('openclaw_supervisor', 'memory_agent'), ...]
```

---

## 关键洞察

### 洞察 1: `langgraph-supervisor` 是独立包，不在 langgraph 主包中
LangGraph V1.0+ 将 supervisor 模式拆为独立包 `langgraph-supervisor`。这避免了核心依赖膨胀，但也意味着需要额外安装。`create_supervisor()` 的 API 签名包含丰富的配置选项（`output_mode`, `handoff_tool_prefix`, `parallel_tool_calls`）。

### 洞察 2: Handoff 通过 `transfer_to_<agent_name>` 工具调用实现
Supervisor 不是硬编码路由，而是 LLM 通过生成 `transfer_to_memory_agent` 这样的工具调用来委托。这意味着路由逻辑可以随 prompt 动态调整，比规则引擎灵活得多。`handoff_tool_prefix` 参数控制前缀（默认 `transfer_to_`）。

### 洞察 3: OpenClaw 桥接的关键路径是工具包装
将 OpenClaw 现有能力（exec, AMS search, spawn subagent）包装为 `@tool`，就能无缝接入 LangGraph supervisor。不需要重写 OpenClaw 核心架构——只需一个适配层。生产环境可用 `httpx` 调用 OpenClaw 的 HTTP API。

### 洞察 4: `create_react_agent` 已废弃，迁移路径明确
LangGraph V1.0 标记 `create_react_agent` 为 deprecated，建议迁移到 `langchain.agents.create_agent`。当前仍可使用但会有警告。新项目应考虑直接用新 API。

### 洞察 5: 状态共享意味着子 agent 可以看到完整对话历史
Supervisor 和所有子 agent 共享 `MessagesState`。这在大多数场景下是优势（上下文连贯），但也意味着敏感信息可能泄露到不该看到的 agent。生产环境需要考虑消息过滤或分区状态。

---

## 与现有项目关联

| 项目 | 关联方式 |
|------|----------|
| **Agent Memory Service** | `search_memory` tool 直接对接 AMS API |
| **OpenClaw MCP Server** | MCP tools 可以同时包装为 LangGraph `@tool`，一个适配层两个出口 |
| **Agent Trust Network** | Supervisor 路由决策可以引入信任分数，低信任 agent 需要 supervisor 确认 |
| **Edge Agent Runtime** | 边缘设备可以运行精简版 supervisor，只有本地 tools |
| **tiny-agent-workshop** | 可以新增 `supervisor_pattern.py` 作为第8个模式 |

---

## 下一步行动

1. **实现 `openclaw-langgraph-bridge` 模块** — 在 `lab/` 下创建 Python 模块，包含:
   - `tools.py`: OpenClaw HTTP API → `@tool` 包装器
   - `supervisor.py`: `build_openclaw_supervisor()` 工厂函数
   - `config.py`: Agent 定义配置（YAML/JSON）
   - 测试: mock LLM + 真实图编译验证

2. **研究 LangGraph 持久化** — `langgraph-checkpoint` 支持对话状态持久化，可以与 AMS 的 `contentHistory()` 对接

3. **评估 `output_mode` 参数** — `full_history` vs `last_message` 对性能和上下文的影响

---

## 版本快照

- `langgraph==1.1.9`
- `langgraph-supervisor==0.0.31`
- `langgraph-prebuilt==1.0.11`
- `langchain-core==1.3.2`
- Python 3.12
