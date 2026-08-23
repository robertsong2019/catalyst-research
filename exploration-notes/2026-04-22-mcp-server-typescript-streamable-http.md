# MCP Server 实现研究：TypeScript SDK + Streamable HTTP

> 日期：2026-04-22 | 状态：✅ 完成
> 目标：为 OpenClaw MCP Server MVP 提供技术方案

---

## 核心概念

### 1. Model Context Protocol (MCP)
JSON-RPC 2.0 协议，连接 AI 模型与外部工具/数据源。三大原语：
- **Tools** — AI 可调用的操作（搜索、创建文件等）
- **Resources** — URI 寻址的数据源（文件、API 响应等）
- **Prompts** — 可复用的提示模板

### 2. Streamable HTTP Transport
2025年11月 MCP 规范更新引入，替代旧版 SSE 传输：
- 单一 HTTP POST 端点处理所有 JSON-RPC 请求
- 响应可以是普通 JSON 或 SSE 流（用于长操作）
- 支持多客户端并发连接
- 生产环境必须使用 HTTPS + TLS

### 3. 三层架构模式（Taskade 生产实践）
```
┌─────────────────────────┐
│   MCP Protocol Layer    │  ← JSON-RPC 处理、工具注册、能力协商
├─────────────────────────┤
│   Business Logic Layer  │  ← 工具实现、数据访问
├─────────────────────────┤
│   Transport Layer       │  ← Streamable HTTP / stdio
└─────────────────────────┘
```

### 4. Session 生命周期
1. Client 发送 `initialize`（含 protocolVersion + capabilities）
2. Server 回复 capabilities + serverInfo
3. 后续 `tools/list`、`tools/call`、`resources/read` 等操作
4. 会话是有状态的，每个连接维护独立 session

### 5. SDK v2 包结构（2026 Q1 发布）
- `@modelcontextprotocol/server` — 服务端
- `@modelcontextprotocol/client` — 客户端
- `@modelcontextprotocol/node` — Node.js http 中间件
- `@modelcontextprotocol/express` — Express 中间件
- `@modelcontextprotocol/hono` — Hono 中间件
- Schema 使用 Standard Schema（支持 Zod v4 / Valibot / ArkType）

---

## 可运行代码：3-Tool MVP Server

### 项目初始化

```bash
mkdir openclaw-mcp-server && cd openclaw-mcp-server
npm init -y
npm install @modelcontextprotocol/sdk zod express
npm install -D typescript @types/node @types/express tsx
```

### `tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "strict": true,
    "esModuleInterop": true,
    "declaration": true
  },
  "include": ["src"]
}
```

### `src/server.ts` — 完整可运行的 MCP Server

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";
import express from "express";
import { randomUUID } from "crypto";

// ─── 创建 MCP Server ───────────────────────────────────
const mcpServer = new McpServer({
  name: "openclaw-mcp-server",
  version: "0.1.0",
});

// ─── Tool 1: echo ───────────────────────────────────────
// 最简单的 tool，用于验证连通性
mcpServer.tool(
  "echo",
  "Echo back the input message. Use to test connectivity.",
  { message: z.string().describe("The message to echo back") },
  async ({ message }) => ({
    content: [{ type: "text" as const, text: `Echo: ${message}` }],
  })
);

// ─── Tool 2: system_info ────────────────────────────────
// 返回运行时环境信息
mcpServer.tool(
  "system_info",
  "Get current system information including OS, uptime, and memory usage.",
  {},
  async () => {
    const mem = process.memoryUsage();
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(
            {
              hostname: require("os").hostname(),
              platform: process.platform,
              nodeVersion: process.version,
              uptime: `${Math.floor(process.uptime())}s`,
              memoryMB: `${Math.round(mem.heapUsed / 1024 / 1024)}MB / ${Math.round(mem.heapTotal / 1024 / 1024)}MB`,
              pid: process.pid,
              timestamp: new Date().toISOString(),
            },
            null,
            2
          ),
        },
      ],
    };
  }
);

// ─── Tool 3: list_files ─────────────────────────────────
// 列出指定目录的文件
mcpServer.tool(
  "list_files",
  "List files in a directory path.",
  {
    path: z.string().describe("Directory path to list"),
    pattern: z
      .string()
      .optional()
      .describe("Glob pattern filter (e.g. '*.ts')"),
  },
  async ({ path, pattern }) => {
    const fs = await import("fs/promises");
    const pathModule = await import("path");

    try {
      const entries = await fs.readdir(path, { withFileTypes: true });
      let results = entries.map((e) => ({
        name: e.name,
        type: e.isDirectory() ? "dir" : "file",
      }));

      if (pattern) {
        const globRegex = new RegExp(
          pattern.replace(/\*/g, ".*").replace(/\?/g, ".")
        );
        results = results.filter((r) => globRegex.test(r.name));
      }

      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(
              { path, count: results.length, files: results },
              null,
              2
            ),
          },
        ],
      };
    } catch (err: any) {
      return {
        content: [{ type: "text" as const, text: `Error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// ─── 启动 Streamable HTTP Transport ──────────────────────
const app = express();
app.use(express.json());

// Session 管理：每个 POST 创建新 session
const sessions = new Map<string, StreamableHTTPServerTransport>();

app.post("/mcp", async (req, res) => {
  const sessionId = randomUUID();
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => sessionId,
  });

  sessions.set(sessionId, transport);

  // 清理断开的 session
  res.on("close", () => {
    sessions.delete(sessionId);
  });

  await mcpServer.connect(transport);
  await transport.handleRequest(req, res);
});

// 健康检查
app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    server: "openclaw-mcp-server",
    activeSessions: sessions.size,
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.error(`🧪 OpenClaw MCP Server running on http://localhost:${PORT}/mcp`);
});
```

### 测试脚本 `test-client.ts`

```typescript
// 快速测试：用 curl 也能验证，这里用脚本更完整
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

async function main() {
  const client = new Client({
    name: "test-client",
    version: "1.0.0",
  });

  const transport = new StreamableHTTPClientTransport(
    new URL("http://localhost:3000/mcp")
  );

  await client.connect(transport);
  console.log("✅ Connected to MCP server");

  // 列出 tools
  const tools = await client.listTools();
  console.log("\n📋 Available tools:", tools.tools.map((t) => t.name));

  // 调用 echo
  const echoResult = await client.callTool({
    name: "echo",
    arguments: { message: "Hello from OpenClaw!" },
  });
  console.log("\n🗣️ Echo result:", echoResult);

  // 调用 system_info
  const sysResult = await client.callTool({
    name: "system_info",
    arguments: {},
  });
  console.log("\n💻 System info:", sysResult);

  // 调用 list_files
  const filesResult = await client.callTool({
    name: "list_files",
    arguments: { path: ".", pattern: "*.ts" },
  });
  console.log("\n📁 Files:", filesResult);

  await client.close();
}

main().catch(console.error);
```

### `package.json` scripts
```json
{
  "type": "module",
  "scripts": {
    "dev": "tsx src/server.ts",
    "test-client": "tsx test-client.ts"
  }
}
```

### curl 快速测试
```bash
# 1. 初始化 session
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": { "name": "curl-test", "version": "1.0.0" }
    }
  }'

# 2. 调用 echo tool
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "echo",
      "arguments": { "message": "Hello MCP!" }
    }
  }'
```

---

## 关键洞察

### 洞察 1：v1.x vs v2 SDK — 生产选 v1
SDK v2 仍在 pre-alpha，预计 2026 Q1 稳定但至今仍在开发中。**生产用 v1.x**（`@modelcontextprotocol/sdk`），v1 至少在 v2 发布后还会维护 6 个月。v2 的包拆分为 `@modelcontextprotocol/server` / `@modelcontextprotocol/client`，迁移成本低。

### 洞察 2：Streamable HTTP ≠ SSE，但兼容 SSE 响应
Streamable HTTP 统一了请求/响应到单一 POST 端点，但**响应可以是普通 JSON 或 SSE 流**。短操作返回 JSON，长操作（如渐进式输出）用 SSE。客户端通过 `Accept: application/json, text/event-stream` 声明支持。

### 洞察 3：Session 管理是生产级的关键差异
简单的 `sessionIdGenerator: () => randomUUID()` 每次请求创建新 session，适合无状态场景。生产级需要：
- Session 持久化（Map → Redis）
- Session 复用（客户端发送 `Mcp-Session-Id` header）
- Session 超时清理
- OAuth 2.1 认证绑定

### 洞察 4：Taskade 的 OpenAPI Codegen 方法值得借鉴
不是手写 tool 定义，而是从 OpenAPI spec 自动生成 50+ tool。这解决了"API 变了但 MCP tool 定义没更新"的一致性问题。如果 OpenClaw 未来暴露 REST API，这应该是首选方案。

### 洞察 5：Middleware 包是最简集成路径
`@modelcontextprotocol/express` 和 `@modelcontextprotocol/hono` 提供薄适配层，可以直接挂载到现有 Express/Hono 应用。对于 OpenClaw 这种已有 HTTP 服务的场景，用 middleware 包比从头搭建更合理。

---

## OpenClaw MCP Server MVP 方案

### 3 Tools MVP 定义

| Tool | 功能 | 输入 | 输出 |
|------|------|------|------|
| `memory_search` | 搜索 OpenClaw 记忆 | query, limit | 匹配的记忆片段 |
| `memory_write` | 写入记忆 | content, tags | 确认信息 |
| `task_create` | 创建任务 | title, description, priority | task_id |

### 技术栈
- Transport: Streamable HTTP（Express middleware）
- Schema: Zod v4（Standard Schema 兼容）
- 部署: Docker + 本地 HTTP
- 认证: Bearer token（第一阶段）→ OAuth 2.1（第二阶段）

### 文件结构
```
openclaw-mcp-server/
├── src/
│   ├── server.ts          # MCP server 入口
│   ├── tools/
│   │   ├── memory-search.ts
│   │   ├── memory-write.ts
│   │   └── task-create.ts
│   └── transport.ts       # Streamable HTTP 配置
├── Dockerfile
├── package.json
└── tsconfig.json
```

---

## 下一步行动

1. **[本周]** 基于上面的代码模板，实现 `openclaw-mcp-server` 3-tool MVP
   - `memory_search` — 调用 AMS 的 searchSimilar()
   - `memory_write` — 写入 memory/YYYY-MM-DD.md
   - `task_create` — 创建任务并记录
2. **[本周]** 配置 Streamable HTTP transport，通过 curl 验证完整 lifecycle
3. **[本月]** 添加 Bearer token 认证中间件
4. **[本月]** 编写 Dockerfile，Docker 化部署

---

## 参考资料

- [MCP TypeScript SDK (GitHub)](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP Cheat Sheet 2026](https://www.webfuse.com/mcp-cheat-sheet)
- [Taskade: Building a Hosted MCP Server](https://www.taskade.com/blog/hosted-mcp-server)
- [WorkOS: Everything about MCP in 2026](https://workos.com/blog/everything-your-team-needs-to-know-about-mcp-in-2026)
- [MCP TypeScript SDK Complete Guide](https://blog.agentailor.com/posts/mcp-typescript-sdk-complete-guide)
- [Cloudfronts: Creating MCP Server Using TypeScript](https://www.cloudfronts.com/blog/creating-an-mcp-server-using-typescript/)
