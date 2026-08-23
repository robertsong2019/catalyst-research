# MCP Server 实现研究 — TypeScript SDK + Streamable HTTP

> 2026-04-18 | 来源: MCP官方TS SDK文档, rebecamdeprey.com安全实践, MCP Spec 2025-03-26

## 核心概念 (5个)

1. **McpServer 高级API** — `@modelcontextprotocol/sdk/server/mcp.js` 中的 `McpServer` 类，通过 `.tool()`, `.resource()`, `.prompt()` 注册能力，自动处理JSON-RPC协议细节
2. **Streamable HTTP Transport** — 替代旧SSE transport的新标准(2025-03-26 spec)，支持POST发送请求、GET接收SSE通知、DELETE关闭session，通过 `Mcp-Session-Id` 头管理会话
3. **Transport分离架构** — 同一个McpServer逻辑可以连接stdio(本地)或Streamable HTTP(远程)，业务代码不关心传输层
4. **中间件包** — SDK提供 `@modelcontextprotocol/express`, `@modelcontextprotocol/hono`, `@modelcontextprotocol/node` 三个薄适配层，不引入额外业务逻辑
5. **Stateful vs Stateless** — StreamableHTTP支持有状态(带session tracking)和无状态(简单API式)两种模式，无状态适合工具类服务

## 可运行代码：OpenClaw MCP Server 骨架

```typescript
// openclaw-mcp-server/src/index.ts
import express from "express";
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

// 1. 创建 MCP Server
const server = new McpServer({
  name: "openclaw-tools",
  version: "0.1.0",
});

// 2. 注册工具: 列出workspace文件
server.tool(
  "list-files",
  "List files in the OpenClaw workspace directory",
  { pattern: z.string().optional().describe("Glob pattern to filter files") },
  async ({ pattern }) => {
    const { glob } = await import("glob");
    const cwd = process.env.WORKSPACE_DIR ?? process.cwd();
    const files = await glob(pattern ?? "**/*", { cwd, nodir: true, ignore: "node_modules/**" });
    return {
      content: [{ type: "text", text: JSON.stringify(files.slice(0, 100), null, 2) }],
    };
  }
);

// 3. 注册工具: 读取文件内容
server.tool(
  "read-file",
  "Read a file from the workspace",
  { path: z.string().describe("Relative file path") },
  async ({ path: filePath }) => {
    const fs = await import("node:fs/promises");
    const cwd = process.env.WORKSPACE_DIR ?? process.cwd();
    const resolved = new URL(filePath, `file://${cwd}/`);
    // 防止路径穿越
    if (!resolved.pathname.startsWith(cwd)) {
      return { content: [{ type: "text", text: "Error: path traversal detected" }], isError: true };
    }
    const content = await fs.readFile(resolved, "utf-8");
    return { content: [{ type: "text", text: content }] };
  }
);

// 4. 注册资源: workspace文件作为resource
server.resource(
  new ResourceTemplate("workspace://{+path}", { list: async () => {
    const { glob } = await import("glob");
    const cwd = process.env.WORKSPACE_DIR ?? process.cwd();
    const files = await glob("**/*.md", { cwd, nodir: true });
    return { resources: files.map(f => ({ uri: `workspace://${f}`, name: f })) };
  }}),
  async (uri) => {
    const fs = await import("node:fs/promises");
    const cwd = process.env.WORKSPACE_DIR ?? process.cwd();
    const filePath = new URL(uri.href).searchParams.get("path") ?? "";
    const content = await fs.readFile(`${cwd}/${filePath}`, "utf-8").catch(() => "File not found");
    return { contents: [{ uri: uri.href, text: content }] };
  }
);

// 5. Wire up Streamable HTTP
const app = express();
app.use(express.json());

const transport = new StreamableHTTPServerTransport({
  sessionIdGenerator: () => crypto.randomUUID(),
});

await server.connect(transport);

app.all("/mcp", async (req, res) => {
  await transport.handleRequest(req, res, req.body);
});

// GET /mcp 用于SSE通知流
// POST /mcp 用于发送JSON-RPC请求
// DELETE /mcp 用于关闭session

const PORT = Number(process.env.PORT ?? 3100);
app.listen(PORT, () => {
  console.log(`✅ OpenClaw MCP Server running at http://localhost:${PORT}/mcp`);
});
```

### 初始化 & 测试

```bash
# 创建项目
mkdir openclaw-mcp-server && cd openclaw-mcp-server
npm init -y
npm install @modelcontextprotocol/sdk zod express glob
npm install -D @types/express tsx typescript

# 运行
WORKSPACE_DIR=~/.openclaw/workspace npx tsx src/index.ts

# 测试 - 初始化连接
curl -X POST http://localhost:3100/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": { "name": "test-client", "version": "1.0.0" }
    }
  }'

# 测试 - 调用工具
curl -X POST http://localhost:3100/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "Mcp-Session-Id: <from-init-response>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": { "name": "list-files", "arguments": { "pattern": "*.md" } }
  }'
```

## 关键洞察 (4条)

1. **SDK v2 已拆包为 monorepo** — `@modelcontextprotocol/sdk` 是主包，但也有 `@modelcontextprotocol/express`, `@modelcontextprotocol/hono`, `@modelcontextprotocol/node` 中间件包。对OpenClaw来说，直接用Express中间件包最自然。

2. **安全漏洞值得注意** — CVE-2025-66414 (cross-client response leak, fixed in 1.26.0) 和 DNS rebinding CVE。如果做OpenClaw MCP Server，必须用最新版SDK (≥1.26.0) 并启用 `enableDnsRebindingProtection`。

3. **Stateless模式适合工具型Server** — OpenClaw的工具(文件操作、记忆搜索、命令执行)天然无状态，不需要session tracking。用 `simpleStatelessStreamableHttp` 模式可以减少复杂度。

4. **与现有项目完美对齐** — OpenClaw已有完整的tool生态(MCP协议本身就是为了统一工具调用)，MCP Server本质上是把OpenClaw的能力暴露给外部AI client的标准方式。这是从"OpenClaw用别人的工具"到"别人用OpenClaw的工具"的关键一步。

## 下一步行动

1. **创建 `openclaw-mcp-server` 项目** — 基于上面的骨架代码，先实现3个核心工具(list-files, read-file, run-command)，用Express + Streamable HTTP
2. **验证与MCP Inspector兼容** — `npx @modelcontextprotocol/inspector` 连接测试
3. **设计工具权限模型** — 参考 `--scope destructive|read|write` 分级，与OpenClaw现有安全策略对齐

## 参考链接

- MCP TypeScript SDK: https://github.com/modelcontextprotocol/typescript-sdk
- MCP Spec 2025-03-26 Transports: https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
- 安全实践: https://rebeccamdeprey.com/blog/secure-mcp-server
- SDK文档: https://ts.sdk.modelcontextprotocol.io/
