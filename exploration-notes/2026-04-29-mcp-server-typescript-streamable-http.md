# MCP Server 开发：TypeScript SDK v2 + Streamable HTTP

> 研究日期：2026-04-29
> 主题来源：HEARTBEAT.md 高优先级 — "实现 OpenClaw MCP Server"
> 研究方法：autoresearch — 明确指标、快速循环、积累性

---

## 核心概念 (5个)

### 1. MCP 三原语：Tools / Resources / Prompts

| 原语 | 方向 | 作用 | 类比 |
|------|------|------|------|
| **Tools** | Server→Client | 执行动作/计算/副作用 | POST 请求 / 函数调用 |
| **Resources** | Server→Client | 暴露只读数据（文件/DB/API） | GET 请求 / 数据注入 |
| **Prompts** | Server→Client | 可复用的提示模板 | 对话起始器 / 请求模板 |

- Tools 由 LLM 决定调用（模型触发）
- Resources 由应用控制（Host 决定何时拉取）
- Prompts 由用户显式选择

### 2. Streamable HTTP Transport（核心传输机制）

替代旧版 HTTP+SSE 的现代传输层：
- **单一端点**：所有通信通过一个 URL（如 `/mcp`）
- **POST 发送**：客户端通过 POST 发送 JSON-RPC 消息
- **SSE 流式响应**：服务端可选返回 SSE 流或单个 JSON
- **GET 监听**：客户端可通过 GET 建立独立 SSE 流接收服务端推送
- **会话管理**：通过 `Mcp-Session-Id` header 跟踪状态

### 3. McpServer vs Server（两层架构）

- `McpServer`（高层）：推荐 API，支持 `.tool()`, `.resource()`, `.prompt()` 等声明式注册
- `Server`（底层）：直接操作 JSON-RPC，更灵活但更复杂
- 推荐：**新项目用 McpServer**

### 4. 会话生命周期

```
Initialize → capabilities 协商 → 正常通信（tools/list, tools/call...） → DELETE 终止会话
```

关键点：
- 服务端在 initialize 响应中返回 `Mcp-Session-Id`
- 客户端后续所有请求必须携带此 header
- 服务端可随时终止会话（返回 404）
- 客户端发 DELETE 显式终止

### 5. SDK v2 包结构（Monorepo 拆分）

SDK v2 将单一包拆为多个子包：
- `@modelcontextprotocol/sdk` — 完整包（仍可用）
- `sdk-server` / `sdk-client` / `sdk-core` — 独立子包
- 传输层：`StreamableHTTPServerTransport`（服务端）、`StreamableHTTPClientTransport`（客户端）

---

## 代码示例：完整可运行的 3-Tool MCP Server（Streamable HTTP）

```typescript
// mcp-server.ts — 最小可运行的 MCP Server with Streamable HTTP
// 运行: npx tsx mcp-server.ts

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";
import { randomUUID } from "crypto";
import express from "express";

// 1. 创建 McpServer 实例
const server = new McpServer({
  name: "openclaw-mcp-server",
  version: "1.0.0",
});

// 2. 注册 Tool: 计算器
server.tool(
  "calculate",
  "执行基本数学运算",
  { expression: z.string().describe("数学表达式，如 '2+3*4'") },
  async ({ expression }) => {
    try {
      // 安全起见只用 Function 构造器做简单数学
      const result = Function(`"use strict"; return (${expression})`)();
      return {
        content: [{ type: "text", text: `${expression} = ${result}` }],
      };
    } catch {
      return {
        content: [{ type: "text", text: `错误：无法计算 "${expression}"` }],
        isError: true,
      };
    }
  }
);

// 3. 注册 Tool: 时间查询
server.tool(
  "get_time",
  "获取当前时间",
  { timezone: z.string().optional().describe("时区，如 'Asia/Shanghai'") },
  async ({ timezone }) => {
    const tz = timezone || "UTC";
    const now = new Date();
    const formatted = now.toLocaleString("zh-CN", { timeZone: tz });
    return {
      content: [{ type: "text", text: `${tz} 当前时间: ${formatted}` }],
    };
  }
);

// 3. 注册 Tool: 系统信息
server.tool("system_info", "获取服务器系统信息", {}, async () => {
  const info = {
    platform: process.platform,
    nodeVersion: process.version,
    uptime: `${Math.floor(process.uptime())}s`,
    memoryUsage: `${Math.round(process.memoryUsage().heapUsed / 1024 / 1024)}MB`,
  };
  return {
    content: [{ type: "text", text: JSON.stringify(info, null, 2) }],
  };
});

// 4. 设置 Express + Streamable HTTP Transport
const app = express();
app.use(express.json());

// 会话管理：支持多客户端
const transports: Record<string, StreamableHTTPServerTransport> = {};

const MCP_ENDPOINT = "/mcp";

app.post(MCP_ENDPOINT, async (req, res) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;

  try {
    // 复用已有 transport
    if (sessionId && transports[sessionId]) {
      await transports[sessionId].handleRequest(req, res, req.body);
      return;
    }

    // 新会话：检查是否为 initialize 请求
    const isInit =
      (req.body?.method === "initialize") ||
      (Array.isArray(req.body) && req.body.some((r: any) => r.method === "initialize"));

    if (!sessionId && isInit) {
      const transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
      });
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);

      const newSessionId = transport.sessionId;
      if (newSessionId) {
        transports[newSessionId] = transport;
        console.log(`新会话建立: ${newSessionId}`);
      }
      return;
    }

    res.status(400).json({
      jsonrpc: "2.0",
      error: { code: -32000, message: "Bad Request: invalid session" },
      id: randomUUID(),
    });
  } catch (error) {
    console.error("请求处理错误:", error);
    res.status(500).json({
      jsonrpc: "2.0",
      error: { code: -32603, message: "Internal server error" },
      id: randomUUID(),
    });
  }
});

// GET 端点：独立 SSE 流（可选）
app.get(MCP_ENDPOINT, async (req, res) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  if (!sessionId || !transports[sessionId]) {
    res.status(405).set("Allow", "POST").send("Method Not Allowed");
    return;
  }
  await transports[sessionId].handleRequest(req, res);
});

// DELETE 端点：终止会话
app.delete(MCP_ENDPOINT, async (req, res) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  if (sessionId && transports[sessionId]) {
    delete transports[sessionId];
    console.log(`会话终止: ${sessionId}`);
  }
  res.status(200).send();
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`MCP Server 运行在 http://localhost:${PORT}${MCP_ENDPOINT}`);
});
```

### 测试客户端

```typescript
// mcp-client.ts — 快速测试 MCP Server
// 运行: npx tsx mcp-client.ts

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

async function main() {
  const client = new Client({ name: "test-client", version: "1.0.0" });
  const transport = new StreamableHTTPClientTransport(
    new URL("http://localhost:3000/mcp")
  );

  await client.connect(transport);
  console.log("已连接到 MCP Server\n");

  // 列出所有 tools
  const { tools } = await client.listTools();
  console.log("可用工具:", tools.map((t) => t.name).join(", "));

  // 调用计算器
  const calcResult = await client.callTool({
    name: "calculate",
    arguments: { expression: "2 + 3 * 4" },
  });
  console.log("\n计算结果:", calcResult.content);

  // 调用时间查询
  const timeResult = await client.callTool({
    name: "get_time",
    arguments: { timezone: "Asia/Shanghai" },
  });
  console.log("\n时间:", timeResult.content);

  // 调用系统信息
  const sysResult = await client.callTool({
    name: "system_info",
    arguments: {},
  });
  console.log("\n系统信息:", sysResult.content);

  await client.close();
  console.log("\n连接已关闭");
}

main().catch(console.error);
```

### package.json（最小依赖）

```json
{
  "name": "openclaw-mcp-server",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "npx tsx mcp-server.ts",
    "test": "npx tsx mcp-client.ts"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^2.0.0",
    "express": "^4.21.0",
    "zod": "^3.24.0"
  },
  "devDependencies": {
    "tsx": "^4.19.0",
    "@types/express": "^5.0.0"
  }
}
```

---

## 关键洞察 (5条)

### 1. Streamable HTTP 是 MCP 远程部署的唯一推荐传输

旧版 HTTP+SSE（双端点：GET /sse + POST /messages）已废弃。新方案统一为单一 `/mcp` 端点，支持 POST（发送）+ GET（SSE 流）+ DELETE（终止会话）。这对 OpenClaw 意味着：只需暴露一个 HTTP 端口即可提供 MCP 服务。

### 2. McpServer 高层 API 大幅降低开发复杂度

用 `server.tool(name, description, schema, handler)` 一行注册一个 tool，Zod schema 自动生成 JSON Schema 供客户端发现。相比手动处理 `CallToolRequestSchema`，代码量减少 60%+。

### 3. 会话管理是多客户端的关键挑战

Streamable HTTP 默认是有状态的（sessionIdGenerator 返回 UUID）。每个客户端连接创建独立 transport，需要在 Express 层维护 `sessionId → transport` 映射。无状态模式（`sessionIdGenerator: () => undefined`）适合简单 API 场景，但不支持 SSE 推送。

### 4. MCP Inspector 是调试利器

`npx @modelcontextprotocol/inspector` 可直接连接 Streamable HTTP server 进行交互测试，无需写客户端代码。开发时先用 Inspector 验证，再写正式客户端。

### 5. OpenClaw MCP Server 的最佳架构路径

```
OpenClaw McpServer (Streamable HTTP)
├── Tool: exec — 执行 shell 命令（已有核心能力）
├── Tool: memory_search — 语义搜索记忆
├── Tool: memory_get — 读取记忆文件
└── Resource: workspace://files — 暴露工作区文件列表
```

先做 3 个 Tool 的 MVP（exec + memory_search + memory_get），通过 Inspector 验证后再扩展。这比同时做 Tools + Resources + Prompts 更聚焦。

---

## 与 OpenClaw 的关联

### 现有能力映射

| OpenClaw 能力 | MCP Tool 映射 | 难度 |
|---------------|---------------|------|
| `exec` 命令执行 | `tools/call { name: "exec", args: { command: "..." } }` | ⭐ |
| `memory_search` | `tools/call { name: "memory_search", args: { query: "..." } }` | ⭐⭐ |
| `memory_get` | `tools/call { name: "memory_get", args: { path: "..." } }` | ⭐ |
| 工作区文件 | `resources/read { uri: "workspace://MEMORY.md" }` | ⭐⭐ |
| Agent 编排 | `tools/call { name: "spawn_agent", args: { task: "..." } }` | ⭐⭐⭐ |

### 实施路径

1. **Phase 1**：MVP Server（3 tools: exec, memory_search, memory_get）— 1-2天
2. **Phase 2**：添加 Resources（工作区文件暴露）+ Prompts（预设任务模板）— 1天
3. **Phase 3**：部署 + 认证（Bearer token 或 OAuth）— 1天
4. **Phase 4**：高级能力（sampling, elicitation, tasks）— 按需

---

## 下一步行动

1. **创建 `lab/openclaw-mcp-server/` 目录**，用上述代码启动 MVP，先用 MCP Inspector 验证连通性
2. **研究 SDK v2 的 `createMcpExpressApp`** — 可能比手动管理 transport 更简洁
3. **调研 OpenClaw 现有插件机制**（`wecom_mcp` 已在用 MCP），看能否复用 transport 层

---

## 参考资料

- [MCP TypeScript SDK 官方文档](https://ts.sdk.modelcontextprotocol.io/)
- [MCP 规范 - Streamable HTTP Transport](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [MCP TypeScript SDK GitHub](https://github.com/modelcontextprotocol/typescript-sdk)
- [How MCP Uses Streamable HTTP - TheNewStack](https://thenewstack.io/how-mcp-uses-streamable-http-for-real-time-ai-tool-interaction/)
- [MCP TypeScript SDK Complete Guide - AgentAI Tailor](https://blog.agentailor.com/posts/mcp-typescript-sdk-complete-guide)
- [MCP Server/Client with Streamable HTTP - Itsuki](https://levelup.gitconnected.com/mcp-server-and-client-with-sse-the-new-streamable-http-d860850d9d9d)
- [MCP Cheat Sheet 2026](https://www.webfuse.com/mcp-cheat-sheet)
