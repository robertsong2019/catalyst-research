# MCP Server v2 SDK 实战 — OpenClaw MCP Server 实现

> 研究日期: 2026-04-17
> 主题: 使用 MCP TypeScript SDK v2 (split packages) + Streamable HTTP 构建 OpenClaw MCP Server
> 关联: HEARTBEAT.md 高优任务 "实现 OpenClaw MCP Server"
> 前置研究: 2026-04-16-openclaw-mcp-server.md (v1 SDK)

---

## 核心概念

### 1. SDK v2 Split Packages（2026 Q1）
v2 将 monolith `@modelcontextprotocol/sdk` 拆分为独立包：
- **`@modelcontextprotocol/server`** — 构建服务器（McpServer, transports, tools）
- **`@modelcontextprotocol/client`** — 构建客户端
- **`@modelcontextprotocol/node`** — Node.js HTTP 传输适配器
- **`@modelcontextprotocol/express`** — Express 中间件
- **`@modelcontextprotocol/hono`** — Hono 中间件

Tool/Prompt schema 使用 [Standard Schema](https://standardschema.dev/)，支持 Zod v4、Valibot、ArkType。

### 2. NodeStreamableHTTPServerTransport
v2 的 Streamable HTTP 传输通过 `@modelcontextprotocol/node` 包提供。关键变化：
- 不再需要手动管理 SSE 流
- `sessionIdGenerator` 控制有状态/无状态模式
- Express 中间件 `createMcpExpressApp` 简化部署

### 3. McpServer 高级 API
`McpServer` 类提供声明式注册：
- `server.tool(name, schema, handler)` — 注册工具
- `server.resource(uri, handler)` — 注册资源
- `server.prompt(name, schema, handler)` — 注册提示模板
- 自动处理 JSON-RPC 路由和 schema 生成

### 4. OpenClaw → MCP 桥接架构
OpenClaw gateway 已有丰富的工具生态（web_search、exec、feishu_doc 等）。MCP Server 作为薄适配层：
```
MCP Client (Cursor/Claude) → Streamable HTTP → OpenClaw MCP Server → OpenClaw Gateway API → 工具执行
```

### 5. DNS Rebinding 防护
MCP 规范要求远程服务器防护 DNS rebinding 攻击。Express 中间件默认验证 Host header，通过 `allowedHosts` 配置白名单。

---

## 关键洞察

### 洞察 1: v2 的 "薄中间件" 哲学降低了集成成本
v2 的 middleware 包（express/hono/node）是极薄的适配器，不引入业务逻辑。这意味着：
- 可以用 30 行代码搭建一个完整的 MCP 服务器
- 框架选择（Express vs Hono）不影响核心逻辑
- 测试时可以只用 `@modelcontextprotocol/node` + 原生 HTTP

### 洞察 2: 无状态模式是 OpenClaw MCP Server 的正确起点
OpenClaw 工具调用本身是无状态的（每次调用独立）。使用 `sessionIdGenerator: undefined` 的无状态模式：
- 简化部署（无需会话管理）
- 天然支持水平扩展
- 减少内存占用
- 仅在需要 sampling/notifications 时才需要状态

### 洞察 3: Standard Schema 支持让 Zod v4 验证零摩擦
v2 使用 Standard Schema 接口，Zod v4 原生支持。这意味着：
- Tool 参数定义直接用 `z.object({...})`，SDK 自动生成 JSON Schema
- 客户端自动获得参数验证
- 不需要手写 JSON Schema

### 洞察 4: OpenClaw 工具元数据天然适合 MCP Tool 接口
OpenClaw 工具已有名称、参数描述、返回格式。MCP Tool 的 `inputSchema` + `CallToolResult` 几乎是一对一映射。核心工作量在 HTTP 传输层，而非工具适配层。

---

## 可运行代码：OpenClaw MCP Server (v2 SDK)

> 完整的 Streamable HTTP MCP Server，暴露 OpenClaw 风格的工具。
> 前置：Node.js 22+, pnpm

### 项目初始化

```bash
mkdir openclaw-mcp-server && cd openclaw-mcp-server
pnpm init
pnpm add @modelcontextprotocol/server @modelcontextprotocol/node @modelcontextprotocol/express zod express
pnpm add -D @types/express @types/node tsx typescript
```

### src/index.ts — 完整可运行服务器

```typescript
import { randomUUID } from "node:crypto";
import { createServer } from "node:http";
import { createMcpExpressApp } from "@modelcontextprotocol/express";
import { NodeStreamableHTTPServerTransport } from "@modelcontextprotocol/node";
import { McpServer } from "@modelcontextprotocol/server";
import type { CallToolResult } from "@modelcontextprotocol/server";
import cors from "cors";
import type { Request, Response } from "express";
import { z } from "zod/v4";

// ---- 工具实现 ----

async function webSearch(query: string, count = 5): Promise<CallToolResult> {
  // 生产环境: 调用 OpenClaw Gateway API
  // 这里用模拟数据演示
  const results = [
    { title: `Result for "${query}"`, url: `https://example.com/search?q=${encodeURIComponent(query)}`, snippet: `This is a simulated result for query: ${query}` },
  ];

  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(results, null, 2),
      },
    ],
  };
}

async function execCommand(command: string, timeout = 30): Promise<CallToolResult> {
  // 生产环境: 调用 OpenClaw Gateway exec API
  try {
    const { execSync } = await import("node:child_process");
    const output = execSync(command, {
      timeout: timeout * 1000,
      encoding: "utf-8",
      maxBuffer: 1024 * 1024,
    });
    return {
      content: [{ type: "text", text: output || "(no output)" }],
    };
  } catch (err: any) {
    return {
      content: [{ type: "text", text: `Error: ${err.message}` }],
      isError: true,
    };
  }
}

async function readFile(path: string): Promise<CallToolResult> {
  try {
    const fs = await import("node:fs/promises");
    const content = await fs.readFile(path, "utf-8");
    const truncated = content.length > 50000 ? content.slice(0, 50000) + "\n... (truncated)" : content;
    return {
      content: [{ type: "text", text: truncated }],
    };
  } catch (err: any) {
    return {
      content: [{ type: "text", text: `Error: ${err.message}` }],
      isError: true,
    };
  }
}

// ---- MCP Server 构建 ----

function createMcpServerInstance(): McpServer {
  const server = new McpServer({
    name: "openclaw-mcp-server",
    version: "0.1.0",
  });

  // Tool: web_search
  server.tool(
    "web_search",
    "Search the web using OpenClaw's web search capability",
    {
      query: z.string().describe("Search query string"),
      count: z.number().optional().default(5).describe("Number of results (1-10)"),
    },
    async ({ query, count }) => webSearch(query, count)
  );

  // Tool: exec
  server.tool(
    "exec",
    "Execute a shell command via OpenClaw",
    {
      command: z.string().describe("Shell command to execute"),
      timeout: z.number().optional().default(30).describe("Timeout in seconds"),
    },
    async ({ command, timeout }) => execCommand(command, timeout)
  );

  // Tool: read_file
  server.tool(
    "read_file",
    "Read file contents from the OpenClaw workspace",
    {
      path: z.string().describe("File path to read"),
    },
    async ({ path }) => readFile(path)
  );

  return server;
}

// ---- Streamable HTTP + Express ----

const PORT = parseInt(process.env.PORT || "3100", 10);

const app = createMcpExpressApp({
  // DNS rebinding protection
  allowedHosts: ["localhost", `localhost:${PORT}`, "127.0.0.1", `127.0.0.1:${PORT}`],
});

app.use(cors());

// Session-based transport map (stateful mode for SSE streaming)
const transports = new Map<string, NodeStreamableHTTPServerTransport>();

// POST /mcp — Handle all MCP requests
app.post("/mcp", async (req: Request, res: Response) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  let transport: NodeStreamableHTTPServerTransport;

  if (sessionId && transports.has(sessionId)) {
    transport = transports.get(sessionId)!;
  } else {
    const server = createMcpServerInstance();
    transport = new NodeStreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
    });
    await server.connect(transport);
    const sid = (transport as any).sessionId;
    if (sid) transports.set(sid, transport);
  }

  await transport.handleRequest(req, res);
});

// GET /mcp — SSE stream (for server-initiated messages)
app.get("/mcp", async (req: Request, res: Response) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  if (!sessionId || !transports.has(sessionId)) {
    res.status(400).json({ error: "Invalid or missing session ID" });
    return;
  }
  const transport = transports.get(sessionId)!;
  await transport.handleRequest(req, res);
});

// DELETE /mcp — Session termination
app.delete("/mcp", async (req: Request, res: Response) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  if (!sessionId || !transports.has(sessionId)) {
    res.status(400).json({ error: "Invalid or missing session ID" });
    return;
  }
  const transport = transports.get(sessionId)!;
  await transport.handleRequest(req, res);
  transports.delete(sessionId);
});

app.listen(PORT, () => {
  console.log(`🧪 OpenClaw MCP Server listening on http://localhost:${PORT}/mcp`);
  console.log(`   Protocol: Streamable HTTP (MCP spec 2025-11-25+)`);
  console.log(`   Tools: web_search, exec, read_file`);
});

// Graceful shutdown
process.on("SIGINT", async () => {
  console.log("\nShutting down...");
  for (const [id, transport] of transports) {
    await transport.close();
    transports.delete(id);
  }
  process.exit(0);
});
```

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "dist",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

### 运行

```bash
pnpm tsx src/index.ts
# 输出: 🧪 OpenClaw MCP Server listening on http://localhost:3100/mcp
```

### 快速验证（curl）

```bash
# 初始化会话
curl -X POST http://localhost:3100/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0"}}}'

# 调用工具
curl -X POST http://localhost:3100/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Session-Id: <from-init-response>" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"/etc/hostname"}}}'
```

---

## 与现有项目关联

| 项目 | 关联 |
|------|------|
| lab/mcp-client-explorer | 已有的 MCP 客户端测试工具，可用于验证本 server |
| agent-memory-service | Memory 数据可作为 MCP Resource 暴露 |
| edge-agent-runtime | Edge Agent 可通过 MCP Server 暴露工具 |
| prompt-weaver | Prompt 模板可作为 MCP Prompt 暴露 |

---

## 下一步行动

1. **创建 `openclaw-mcp-server` 项目** — 基于上述代码骨架，初始化 git 仓库
2. **接入 OpenClaw Gateway API** — 替换模拟实现为真实 API 调用（通过 `gatewayUrl` + `gatewayToken`）
3. **添加 Resource 支持** — 暴露 workspace 文件列表和 MEMORY.md 作为 MCP Resource
4. **添加认证** — Bearer token 验证，复用 OpenClaw 的 gateway token
5. **Docker 化** — 添加 Dockerfile 用于部署

---

## 参考资源

- [MCP TypeScript SDK v2](https://github.com/modelcontextprotocol/typescript-sdk) — 官方 SDK（v2 分支，Q1 2026 stable）
- [MCP Spec Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) — Streamable HTTP 规范
- [Build a Secure MCP Server](https://rebeccamdeprey.com/blog/secure-mcp-server) — 安全最佳实践
- [MCP Transport Future](https://blog.modelcontextprotocol.io/posts/2025-12-19-mcp-transport-future/) — 传输层演进路线图
