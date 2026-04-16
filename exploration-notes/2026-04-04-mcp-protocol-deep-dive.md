# MCP (Model Context Protocol) 深度学习笔记

**日期**: 2026-04-04
**主题**: AI Agent 编程 — MCP 协议架构与实践
**学习时长**: ~2 小时
**来源**: modelcontextprotocol.io 官方文档、规范、开发指南

---

## 一、MCP 是什么？

MCP (Model Context Protocol) 是一个开放协议，为 AI 应用与外部工具/数据源之间的**上下文交换**提供标准化方式。可以理解为 **"AI 的 USB-C 接口"** — 一个统一的连接标准。

关键定位：
- MCP **只管协议**，不管 AI 应用如何使用 LLM 或管理上下文
- 基于 JSON-RPC 2.0
- 当前最新规范版本：2025-11-25

---

## 二、架构概览

### 核心参与者

```
┌─────────────────────────────────────┐
│         MCP Host (AI 应用)           │
│   例: Claude Desktop, VS Code,      │
│       OpenClaw, Cursor              │
│                                     │
│  ┌──────────┐ ┌──────────┐ ┌─────┐ │
│  │ Client 1 │ │ Client 2 │ │ C3  │ │
│  └────┬─────┘ └────┬─────┘ └──┬──┘ │
└───────┼────────────┼──────────┼─────┘
        │            │          │
   ┌────▼────┐  ┌────▼────┐  ┌──▼──────┐
   │ Server A│  │ Server B│  │Server C │
   │ (本地)   │  │ (本地)   │  │(远程)   │
   │ 文件系统 │  │ 数据库   │  │ Sentry  │
   └─────────┘  └─────────┘  └─────────┘
```

- **Host**: AI 应用本身，协调多个 Client
- **Client**: 每个 Client 维护一个与 Server 的 1:1 连接
- **Server**: 提供上下文和能力的程序，可本地或远程运行

### 两层架构

| 层 | 职责 |
|---|---|
| **数据层 (Data Layer)** | JSON-RPC 2.0 消息、生命周期管理、原语(Tools/Resources/Prompts) |
| **传输层 (Transport Layer)** | Stdio（本地进程通信）或 Streamable HTTP（远程通信） |

### 传输方式

1. **Stdio**: 标准输入/输出流，用于本地进程直接通信，零网络开销
2. **Streamable HTTP**: HTTP POST + SSE（Server-Sent Events），支持远程、OAuth 认证

---

## 三、三大 Server 原语（Primitives）

这是 MCP 最核心的概念 — 定义了 Server 能向 AI 应用提供什么：

### 1. Tools（工具）— 模型控制

```json
{
  "name": "searchFlights",
  "description": "Search for available flights",
  "inputSchema": {
    "type": "object",
    "properties": {
      "origin": { "type": "string" },
      "destination": { "type": "string" },
      "date": { "type": "string", "format": "date" }
    },
    "required": ["origin", "destination", "date"]
  }
}
```

- AI 模型根据上下文自动决定何时调用
- 可以写入数据库、调 API、修改文件
- **需要用户审批**（设计上强调人类监督）

### 2. Resources（资源）— 应用控制

- 只读数据源：文件内容、数据库 schema、API 响应
- 每个 Resource 有唯一 URI（如 `file:///path/to/doc.md`）
- 支持静态资源和模板资源（带参数）
- 应用端决定如何使用这些数据

### 3. Prompts（提示）— 用户控制

- 可复用的交互模板，用户显式调用
- 类似斜杠命令（/plan-vacation）
- 参数化模板，展示如何最好地使用该 Server

### 控制权对比

| 原语 | 谁控制 | 触发方式 |
|------|--------|---------|
| Tools | 模型 | AI 自动调用 |
| Resources | 应用 | 应用检索 |
| Prompts | 用户 | 用户显式选择 |

---

## 四、Client 原语

Server 也可以利用 Client 的能力，实现更丰富的交互：

### 1. Sampling（采样）

Server 可以请求 Client 的 LLM 做推理 — **不需要自己集成 LLM**。

典型场景：旅行 Server 收集 47 个航班选项 → 请求 Client 的 AI 分析推荐最佳航班。

关键安全设计：双层人类审批（请求审批 + 响应审批）。

### 2. Elicitation（询问）

Server 可以向用户请求额外信息：
```json
{
  "method": "elicitation/requestInput",
  "params": {
    "message": "Please confirm your booking:",
    "schema": {
      "type": "object",
      "properties": {
        "confirmBooking": { "type": "boolean" },
        "seatPreference": { "type": "string", "enum": ["window", "aisle"] }
      }
    }
  }
}
```

### 3. Roots（根目录）

Client 告知 Server 应该关注哪些目录边界（`file://` URI）。这是**协调机制**而非安全边界。

---

## 五、生命周期与能力协商

MCP 是**有状态协议**，需要明确的生命周期管理：

```
Client                    Server
  │                         │
  │── initialize ──────────▶│  (协商协议版本+能力)
  │◀── initialize response ─│
  │                         │
  │── initialized ─────────▶│  (确认，开始正常通信)
  │                         │
  │   ... 正常请求/响应 ...   │
  │                         │
  │── 关闭连接 ─────────────▶│
```

能力协商决定双方能用哪些功能：
- Server 声明：是否支持 tools/resources/prompts/notifications
- Client 声明：是否支持 sampling/elicitation

---

## 六、Tasks（实验性）— 2025-11-25 新特性

Tasks 是**持久化的状态机**，用于包装耗时操作：

- 支持昂贵计算、批处理、多步骤工作流
- 两阶段响应：立即返回 task ID → 轮询获取结果
- 任务状态：`working` → `completed` / `failed` / `cancelled` / `input_required`
- 支持双向：Client 和 Server 都可以创建/接收 Tasks

```
Client: tools/call + { task: { ttl: 60000 } }
Server: 返回 { task: { taskId, status: "working", pollInterval: 5000 } }
Client: 轮询 tasks/get → 最终 tasks/result 获取结果
```

工具级别控制：每个 Tool 可以声明 `taskSupport: "required" | "optional" | "forbidden"`

---

## 七、MCP Registry — 生态系统

- 官方集中式 Server 元数据仓库（Preview 阶段）
- 反向 DNS 命名（如 `io.github.user/server-name`）
- GitHub/DNS 验证确保命名空间安全
- 不托管代码，只存元数据，指向 npm/PyPI/Docker Hub

---

## 八、构建 MCP Server 的实践

### Python (FastMCP)
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather")

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location."""
    # ... 实现
    pass

def main():
    mcp.run(transport="stdio")
```

FastMCP 利用 Python 类型提示和 docstring 自动生成 Tool 定义。

### 部署路径选择

| 场景 | 推荐路径 |
|------|---------|
| 包装云 API | Remote (Streamable HTTP) |
| 需要交互式 UI | MCP Apps |
| 需要访问用户机器 | MCP Bundles (.mcpb) |
| 快速原型 | Local stdio → 后续升级到 MCPB |

### 重要坑点

- **Stdio 模式下千万别用 `print()`/`console.log()`** — 会污染 JSON-RPC 消息！
- 必须用 stderr 或日志库输出调试信息

---

## 九、设计哲学（精要）

1. **Server 应极其容易构建** — Host 承担复杂编排，Server 专注单一能力
2. **高度可组合** — 多个 Server 无缝协同，共享协议
3. **Server 看不到完整对话，也不知道其他 Server** — Host 控制隔离
4. **渐进式添加功能** — 核心协议最小化，能力按需协商

---

## 十、与 OpenClaw 的关系

思考 MCP 如何与当前的 OpenClaw 架构关联：

- OpenClaw 本身可以视为 MCP Host
- OpenClaw 的 Skills 系统与 MCP Server 的 Tools/Resources 有概念重叠
- mcporter skill 已经在桥接 MCP 协议
- 未来趋势：MCP 成为 AI Agent 的标准工具接口，所有 Agent 框架都会适配

### 潜在实践方向

1. **将 OpenClaw 技能包装为 MCP Server** — 让其他 AI 应用也能使用
2. **用 MCP Registry 发布自建 Server** — 贡献生态
3. **利用 Tasks 特性处理长耗时操作** — 更好的异步任务管理

---

## 关键洞察

1. **MCP 不是 Agent 框架，是 Agent 的"手和眼"** — 它解决的是连接问题，不是推理问题
2. **安全性是第一公民** — 每个设计决策都考虑了人类监督和数据隔离
3. **生态正在快速成熟** — Registry、MCP Apps、MCP Bundles 都在快速迭代
4. **Server 生态将像 npm 一样爆发** — 标准化接口 + 易构建 = 网络效应

---

*下次探索方向建议：MCP Apps 的交互式 UI 机制、或 Agent-to-Agent 协议（A2A）与 MCP 的关系*
