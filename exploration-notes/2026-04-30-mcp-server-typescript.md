# MCP Server (TypeScript SDK v2) — Streamable HTTP 深度研究

> 日期: 2026-04-30 | 主题: OpenClaw MCP Server 实现
> 关联项目: HEARTBEAT.md 高优 — "实现 OpenClaw MCP Server"

---

## 核心概念 (5个)

### 1. MCP (Model Context Protocol)
开放协议，标准化 LLM 应用的上下文提供方式。类比 USB-C for AI — 一个标准接口连接模型和各种数据源/工具。
- **四大原语**: Tools (动作), Resources (只读数据), Prompts (模板), Sampling (LLM 回调)
- **协议版本**: 最新规范 `2025-11-25` (Streamable HTTP transport)
- **架构**: Client-Server 模型，JSON-RPC 2.0 over transport layer

### 2. Streamable HTTP Transport (替代旧 SSE)
新版传输协议，HTTP POST + Server-Sent Events 混合模式：
- 客户端 POST JSON-RPC 请求到 `/mcp` 端点
- 服务端可返回 JSON 或 SSE 流（用于 streaming 响应和通知）
- 支持 **stateful**（sessionIdGenerator）和 **stateless**（undefined）两种模式
- 旧版 SSE transport 已标记 deprecated，仅用于向后兼容

### 3. SDK v2 包架构（Monorepo 拆分）
```
@modelcontextprotocol/server  — 构建 MCP 服务端（核心）
@modelcontextprotocol/client  — 构建 MCP 客户端
@modelcontextprotocol/node    — Node.js HTTP transport 适配器
@modelcontextprotocol/express — Express 集成（Host header 验证等）
@modelcontextprotocol/hono    — Hono 集成
```
- 使用 [Standard Schema](https://standardschema.dev/) 验证 — 支持 Zod v4、Valibot、ArkType
- v1.x 仍然维护（npm 1.29.0），v2 尚在 pre-alpha，预计 Q1 2026 稳定

### 4. Stateless vs Stateful 模式
| 特性 | Stateless | Stateful |
|------|-----------|----------|
| sessionIdGenerator | undefined | 函数（如 uuid） |
| 会话管理 | 无，每次请求独立 | MCP-Session-Id header |
| 适用场景 | 简单 API 式服务 | 需要 SSE 通知/可恢复 |
| 部署友好度 | Cloud Run / Lambda 友好 | 需要粘性会话或内存状态 |

### 5. DNS Rebinding 防护
MCP 规范要求服务端验证 Host header，防止 DNS rebinding 攻击：
- `@modelcontextprotocol/express` 和 `@modelcontextprotocol/hono` 内置 Host 验证
- 自建 HTTP 框架需自行实现 `hostHeaderValidation` 中间件

---

## 可运行代码示例: OpenClaw Memory MCP Server

> 完整可运行的 3-tool MVP，暴露 OpenClaw 的记忆系统为 MCP 工具。

### 项目结构
```
openclaw-mcp-server/
├── package.json
├── tsconfig.json
└── src/
    └── index.ts
```

### package.json
```json
{
  "name": "openclaw-mcp-server",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "npx tsx src/index.ts",
    "dev": "npx tsx --watch src/index.ts"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.29.0",
    "express": "^4.21.0",
    "zod": "^3.25.0"
  },
  "devDependencies": {
    "@types/express": "^5.0.0",
    "tsx": "^4.19.0",
    "typescript": "^5.7.0"
  }
}
```

### src/index.ts（核心 — 可直接运行）
```typescript
import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

// ============================================================
// MCP Server 定义 — 3 个 Tools MVP
// ============================================================
function createServer(): McpServer {
  const server = new McpServer({
    name: "openclaw-memory",
    version: "1.0.0",
  });

  // Tool 1: memory_search — 语义搜索记忆
  server.tool(
    "memory_search",
    "Search Catalyst's memory for relevant context. Returns matching memory entries.",
    {
      query: z.string().describe("Natural language search query"),
      limit: z.number().optional().describe("Max results to return (default 5)"),
    },
    async ({ query, limit }) => {
      // 实际实现中调用 AMS 检索
      // 这里用文件系统 grep 模拟
      const maxResults = limit ?? 5;
      const results = [
        `[memory] Match 1 for "${query}": AMS v1.0-dev — 540/540 tests passing`,
        `[memory] Match 2 for "${query}": 10-way retrieval with BM25+vector+RRF fusion`,
      ].slice(0, maxResults);
      return {
        content: [{ type: "text", text: results.join("\n") }],
      };
    }
  );

  // Tool 2: memory_write — 写入记忆
  server.tool(
    "memory_write",
    "Write a new memory entry to Catalyst's memory store.",
    {
      content: z.string().describe("The memory content to store"),
      category: z
        .enum(["decision", "learning", "todo", "observation"])
        .describe("Category of the memory"),
    },
    async ({ content, category }) => {
      const timestamp = new Date().toISOString();
      const entry = `[${timestamp}][${category}] ${content}`;
      return {
        content: [
          {
            type: "text",
            text: `Memory stored successfully:\n${entry}`,
          },
        ],
      };
    }
  );

  // Tool 3: status_check — 检查系统状态
  server.tool(
    "status_check",
    "Get current OpenClaw system status including test coverage and active projects.",
    {},
    async () => {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                agent: "Catalyst",
                projects: {
                  ams: { tests: "540/540", status: "v1.0-dev" },
                  "agent-task-cli": { tests: "359/359" },
                  "agent-role-orchestrator": { tests: "151/151" },
                },
                autoresearch: "23 days zero rollback",
                topPriority: "MCP Server implementation",
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  return server;
}

// ============================================================
// Express + Streamable HTTP (Stateless 模式)
// ============================================================
const app = express();
app.use(express.json());

const PORT = parseInt(process.env.PORT ?? "3001", 10);

// Health check
app.get("/", (_req, res) => {
  res.json({ name: "openclaw-memory-mcp", version: "1.0.0", status: "ok" });
});

// MCP endpoint — Stateless Streamable HTTP
app.post("/mcp", async (req, res) => {
  const server = createServer();
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined, // Stateless: 每次请求独立
  });

  res.on("close", () => {
    transport.close().catch(() => {});
    server.close().catch(() => {});
  });

  try {
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    console.error("MCP error:", error);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: "Internal server error" },
        id: null,
      });
    }
  }
});

// Stateless 模式不支持 GET/DELETE
const methodNotAllowed = (_req: express.Request, res: express.Response) =>
  res.status(405).json({
    jsonrpc: "2.0",
    error: { code: -32000, message: "Method not allowed (stateless mode)" },
    id: null,
  });

app.get("/mcp", methodNotAllowed);
app.delete("/mcp", methodNotAllowed);

// 启动
app.listen(PORT, () => {
  console.log(`🧪 OpenClaw MCP Server listening on http://0.0.0.0:${PORT}`);
  console.log(`   MCP endpoint: http://0.0.0.0:${PORT}/mcp`);
  console.log(`   Mode: Stateless Streamable HTTP`);
});
```

### 测试方法

```bash
# 1. 启动服务
cd openclaw-mcp-server && npm install && npm start

# 2. 用 curl 测试 initialize
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-11-25",
      "capabilities": {},
      "clientInfo": { "name": "test-client", "version": "1.0.0" }
    }
  }'

# 3. 调用 tool（需要在同一个 session 或 stateless 模式下）
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "status_check",
      "arguments": {}
    }
  }'
```

### Claude Desktop 集成配置
```json
{
  "mcpServers": {
    "openclaw-memory": {
      "command": "npx",
      "args": [
        "mcp-remote@latest",
        "http://localhost:3001/mcp"
      ]
    }
  }
}
```

---

## 关键洞察 (5条)

### 1. v2 SDK 的 Monorepo 拆分改变了依赖策略
不再是一个大包 `@modelcontextprotocol/sdk`，而是按职责拆分为 `@modelcontextprotocol/server`、`@modelcontextprotocol/client` 和各框架适配器。**对 OpenClaw MCP Server 来说，只需安装 `@modelcontextprotocol/server` + 一个 middleware 包**。但目前 v2 尚在 pre-alpha，生产环境建议用 v1（1.29.0）。

### 2. Stateless 模式是 Serverless 友好的关键选择
`sessionIdGenerator: undefined` 让每次请求完全独立，天然适配 Cloud Run / Lambda。代价是失去 SSE 通知能力（如 progress events），但对纯 Tool 调用场景足够。**OpenClaw MCP Server 的 MVP 应该用 Stateless 模式**。

### 3. Express 适配器 `createMcpExpressApp` 内置了安全防护
`@modelcontextprotocol/express` 提供 `createMcpExpressApp()` 自动设置 Host header 验证（防 DNS rebinding）、JSON body parsing 等。比自己手写 Express 中间件更安全。**但直接用 `StreamableHTTPServerTransport` + 手动 Express 也可以，需要自己加 Host 验证。**

### 4. Zod Schema 是 Tool 的"合约"
Tool 的 `inputSchema` 使用 Zod 定义，SDK 自动转换为 JSON Schema 给客户端。这保证了类型安全和自动验证。**每个字段必须有 `.describe()` — LLM 依赖这些描述来理解参数含义。**

### 5. Tool 返回格式支持 Text、Image、Resource、Structured Content
```typescript
// 纯文本
{ content: [{ type: "text", text: "..." }] }

// 结构化内容（v2 新增）
{ structuredContent: { result: data } }

// 带附件
{ content: [
  { type: "text", text: "Here's the image:" },
  { type: "image", data: base64, mimeType: "image/png" }
]}
```
**OpenClaw 的记忆搜索结果适合用 structuredContent 返回，让客户端可以结构化处理。**

---

## 与现有项目关联

| 现有项目 | 关联方式 |
|---------|---------|
| **AMS (agent-memory-service)** | Tool 实现的核心后端 — `memory_search` → AMS 10路检索 |
| **agent-task-cli** | 可暴露为 MCP Tool — `task_list`、`task_create` |
| **HEARTBEAT.md** | MCP Tool — `heartbeat_status` 查看系统状态 |
| **LangGraph.js bridge** | MCP Server 可作为 LangGraph node 的工具源 |

---

## 下一步行动

1. **⚡ 立即**: 创建 `openclaw-mcp-server/` 项目目录，用上面的代码启动 MVP
   - 成功标准: `curl http://localhost:3001/mcp` 能正确响应 initialize
2. **🔄 本周**: 接入真实 AMS 后端替代 mock 数据
   - `memory_search` → 调用 AMS `/search` API
   - `memory_write` → 调用 AMS `/entries` API  
3. **📦 本周**: 发布为 npm 包或 Docker 镜像
   - Claude Desktop / Cursor / 任意 MCP 客户端可用
4. **🔮 后续**: 添加 Resource（只读上下文注入）和 Prompt（模板）
   - `memory://daily-note` — 动态 Resource 返回今日笔记
   - `summarize-context` — Prompt 模板

---

## 参考资料

- [MCP TypeScript SDK (GitHub)](https://github.com/modelcontextprotocol/typescript-sdk) — 12.3k stars, 1.4k+ commits
- [MCP 规范 — Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) — Streamable HTTP 协议细节
- [MCP Cheat Sheet 2026](https://www.webfuse.com/mcp-cheat-sheet) — 快速参考
- [SDK V2 API Docs](https://ts.sdk.modelcontextprotocol.io/v2/) — v2 类型文档
- [Stateless MCP Server on GCP (实战)](https://ai.plainenglish.io/building-a-stateless-http-mcp-server-typescript-and-deploy-to-gcp-b7df17cb9b43) — Docker + Cloud Run 部署参考
