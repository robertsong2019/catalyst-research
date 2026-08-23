# MCP Server TypeScript SDK v2 + Streamable HTTP 深度研究

> 研究日期: 2026-04-28
> 目标: 掌握 MCP TS SDK v2 的 Streamable HTTP transport，为 OpenClaw MCP Server MVP 实现做准备

---

## 核心概念 (5个)

### 1. McpServer — 高层 API 入口
`@modelcontextprotocol/server` 的核心类。注册 tools/resources/prompts 后连接 transport 即可运行。
```ts
const server = new McpServer({ name: 'my-server', version: '1.0.0' });
```
支持 `capabilities` 选项开启 logging、tasks 等能力。

### 2. Streamable HTTP Transport — 网络部署标准
替代旧版 HTTP+SSE，是 MCP 2025-06-18 规范的标准远程传输方式：
- 单一 HTTP endpoint（如 `/mcp`）处理 POST/GET/DELETE
- POST 发送 JSON-RPC 消息，响应可以是 SSE 流或纯 JSON
- GET 可选开启 SSE 流用于服务器推送通知
- 支持有状态(session)和无状态(stateless)两种模式

### 3. Session 管理
- **有状态**: `sessionIdGenerator: () => randomUUID()` — 支持通知、resumability
- **无状态**: `sessionIdGenerator: undefined` — 每次 POST 创建新 transport，简单但无通知
- **JSON 模式**: `enableJsonResponse: true` — 不用 SSE，纯 JSON 响应

### 4. Middleware 包 — 框架适配
SDK v2 将 transport 逻辑拆分为独立包：
- `@modelcontextprotocol/node` — NodeStreamableHTTPServerTransport
- `@modelcontextprotocol/express` — createMcpExpressApp() + Host 校验
- `@modelcontextprotocol/hono` — Hono 框架适配

### 5. Standard Schema — 灵活的 Schema 验证
Tool 的 `inputSchema` / `outputSchema` 使用 [Standard Schema](https://standardschema.dev/) 协议，支持 Zod v4、Valibot、ArkType 等。

---

## 代码示例: 最小可运行 MCP Server (Streamable HTTP, Stateless)

```ts
// mcp-server.ts — 最小 MVP: 3 tools, Streamable HTTP, 无状态
import { createMcpExpressApp } from '@modelcontextprotocol/express';
import { NodeStreamableHTTPServerTransport } from '@modelcontextprotocol/node';
import type { CallToolResult } from '@modelcontextprotocol/server';
import { McpServer } from '@modelcontextprotocol/server';
import type { Request, Response } from 'express';
import * as z from 'zod/v4';

function createServer() {
  const server = new McpServer(
    { name: 'openclaw-mcp', version: '0.1.0' },
    { capabilities: { logging: {} } }
  );

  // Tool 1: echo
  server.registerTool('echo', {
    description: 'Echo back the input',
    inputSchema: z.object({ message: z.string() }),
  }, async ({ message }): Promise<CallToolResult> => ({
    content: [{ type: 'text', text: message }]
  }));

  // Tool 2: current-time
  server.registerTool('current-time', {
    description: 'Get current ISO timestamp',
    inputSchema: z.object({ tz: z.string().optional() }),
  }, async ({ tz }): Promise<CallToolResult> => ({
    content: [{ type: 'text', text: new Date().toISOString() + (tz ? ` (${tz})` : '') }]
  }));

  // Tool 3: add
  server.registerTool('add', {
    description: 'Add two numbers',
    inputSchema: z.object({ a: z.number(), b: z.number() }),
  }, async ({ a, b }): Promise<CallToolResult> => ({
    content: [{ type: 'text', text: String(a + b) }]
  }));

  return server;
}

const app = createMcpExpressApp();

app.post('/mcp', async (req: Request, res: Response) => {
  const server = createServer();
  const transport = new NodeStreamableHTTPServerTransport({
    sessionIdGenerator: undefined, // 无状态模式
  });
  try {
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: '2.0',
        error: { code: -32603, message: 'Internal server error' },
        id: null,
      });
    }
  }
  res.on('close', () => { transport.close(); server.close(); });
});

app.get('/mcp', (_req: Request, res: Response) => {
  res.writeHead(405).end(JSON.stringify({
    jsonrpc: '2.0', error: { code: -32000, message: 'Method not allowed' }, id: null
  }));
});

app.delete('/mcp', (_req: Request, res: Response) => {
  res.writeHead(405).end(JSON.stringify({
    jsonrpc: '2.0', error: { code: -32000, message: 'Method not allowed' }, id: null
  }));
});

const PORT = Number(process.env.PORT || 3000);
app.listen(PORT, () => {
  console.log(`🧪 OpenClaw MCP Server listening on :${PORT}/mcp`);
});
```

### 运行方式

```bash
# package.json 依赖
npm install @modelcontextprotocol/server @modelcontextprotocol/node @modelcontextprotocol/express express zod @cfworker/json-schema

# 运行
npx tsx mcp-server.ts

# 测试 (用 curl 模拟 MCP client)
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

# 调用 echo tool
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"echo","arguments":{"message":"hello catalyst"}}}'
```

---

## 关键洞察 (5条)

### 1. 无状态模式是最简 MVP 路径
Stateless 模式下每次 POST 创建新的 server + transport 实例，无状态维护，天然支持水平扩展。对于不需要服务器推送通知的简单工具服务，这是最优起步方案。

### 2. SDK v2 的包拆分是架构升级信号
从单一 `@modelcontextprotocol/sdk` 拆分为 server/client/node/express/hono 多包，意味着：
- Transport 逻辑与业务逻辑彻底解耦
- 可以只用 `@modelcontextprotocol/server` + `@modelcontextprotocol/node` 最小依赖
- Express/Hono 适配器极薄，自己写路由也很简单

### 3. Standard Schema 解锁了灵活的验证生态
不再绑定 Zod 特定版本。Valibot (更小bundle)、ArkType (类型推导更强) 都是选项。对 OpenClaw 场景，Zod v4 生态最成熟。

### 4. 安全模型需从一开始考虑
规范明确要求：
- 校验 Origin header 防 DNS rebinding
- 本地绑定 127.0.0.1
- 实现认证 (Bearer Auth / OAuth)
OpenClaw MCP Server 应在 MVP 阶段就加入 Bearer token 认证。

### 5. 有状态模式的三种扩展策略
对于需要会话的场景，SDK 给出了清晰路径：
- **Stateless**: 无状态，最简
- **Persistent storage**: session 存数据库，任意节点可处理
- **Pub/sub routing**: 本地内存状态 + 消息路由
OpenClaw 可先从 stateless 起，后续按需升级。

---

## 与现有项目关联

| 项目 | 关联点 |
|------|--------|
| **OpenClaw MCP Server** | 直接目标 — 以上代码即为 MVP 雏形 |
| **Agent Memory Service** | 可作为 MCP tool 暴露 memory search/write |
| **mcporter skill** | 现有 MCP 调用能力，新 server 可被其发现和调用 |
| **LangGraph bridge** | LangGraph agent 可通过 MCP client 调用 OpenClaw tools |

---

## 下一步行动

1. **创建 `openclaw-mcp-server` 项目** — 基于 stateless 模式，3 tools (echo, memory-search, agent-status)
2. **添加 Bearer token 认证** — 使用 `requireBearerAuth` 或自定义中间件
3. **集成 AMS** — 将 memory search 封装为 MCP tool
4. **部署测试** — Docker 化 + 端点暴露，用 mcporter 验证连通性
5. **注册到 OpenClaw** — 通过 mcporter config 添加为可用 MCP server

---

## 参考资料

- [MCP Transport 规范](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [TypeScript SDK v2 GitHub](https://github.com/modelcontextprotocol/typescript-sdk)
- [SDK Server Guide](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/server.md)
- [Stateless 示例](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/examples/server/src/simpleStatelessStreamableHttp.ts)
- [Stateful 示例](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/examples/server/src/simpleStreamableHttp.ts)
