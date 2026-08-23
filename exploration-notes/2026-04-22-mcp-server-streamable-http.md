# MCP Server with TypeScript SDK + Streamable HTTP

> 研究日期: 2026-04-22 | 主题来源: HEARTBEAT.md 高优先级任务
> 方法论: autoresearch — 明确指标 → 快速循环 → 保留/回退

---

## 核心概念

### 1. Streamable HTTP Transport (替代旧版 SSE)
MCP 协议从 HTTP+SSE 迁移到 **Streamable HTTP**。核心变化：
- 客户端 POST JSON-RPC 请求到单一端点（如 `/mcp`）
- 服务器响应可以是普通 JSON 或 SSE 流
- **无状态模式**: `sessionIdGenerator: undefined`，每次请求创建新 transport
- **有状态模式**: 自定义 sessionIdGenerator 维护会话

### 2. McpServer 高层 API
`@modelcontextprotocol/sdk/server/mcp.js` 提供 `McpServer` 类，封装了底层 JSON-RPC 处理：
- `server.tool(name, schema, handler)` — 注册工具
- `server.resource(uri, handler)` — 注册资源
- `server.prompt(name, schema, handler)` — 注册提示模板
- Schema 使用 **Zod** 做输入验证

### 3. 三原语的分工 (Tools / Resources / Prompts)
- **Tools**: 模型控制 — LLM 决定何时调用
- **Resources**: 应用控制 — Host 决定何时拉取
- **Prompts**: 用户控制 — 人类决定何时触发

### 4. Express 集成模式
官方 SDK 提供 `createMcpExpressApp` 帮助函数，处理 CORS、JSON 解析等中间件。也可以手动集成 Express。

### 5. 认证方案
支持 Bearer Token、API Key、OAuth 2.0。Render 模板展示了 Bearer Token 中间件的实现模式。

---

## 可运行代码：3-Tool MCP Server MVP

> 成功标准：`npx tsx src/index.ts` 启动后，curl 可完成 initialize + tool call

```typescript
// src/index.ts — OpenClaw MCP Server MVP
import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

function createServer() {
  const server = new McpServer({
    name: "openclaw-mcp-server",
    version: "0.1.0",
  });

  // Tool 1: echo — 回显消息
  server.tool("echo", { message: z.string().describe("要回显的消息") }, async ({ message }) => ({
    content: [{ type: "text" as const, text: `Echo: ${message}` }],
  }));

  // Tool 2: time — 返回当前时间
  server.tool("current_time", { timezone: z.string().default("Asia/Shanghai").describe("时区") }, async ({ timezone }) => {
    const time = new Date().toLocaleString("zh-CN", { timeZone: timezone });
    return { content: [{ type: "text" as const, text: `当前时间 (${timezone}): ${time}` }] };
  });

  // Tool 3: search_memory — 搜索记忆
  server.tool(
    "search_memory",
    { query: z.string().describe("搜索关键词"), limit: z.number().default(5).describe("结果数量") },
    async ({ query, limit }) => {
      // MVP: 模拟搜索结果
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ query, limit, results: [`模拟结果: ${query} 的相关记忆条目`] }, null, 2),
        }],
      };
    }
  );

  return server;
}

const app = express();
app.use(express.json());

// Health check
app.get("/health", (_req, res) => res.json({ status: "ok" }));

// MCP endpoint (无状态模式)
app.post("/mcp", async (req, res) => {
  try {
    const server = createServer();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // 无状态
    });
    res.on("close", () => { transport.close(); server.close(); });
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    if (!res.headersSent) {
      res.status(500).json({ jsonrpc: "2.0", error: { code: -32603, message: "Internal error" }, id: null });
    }
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`OpenClaw MCP Server running at http://localhost:${PORT}/mcp`));
```

### package.json
```json
{
  "name": "openclaw-mcp-server",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "start": "npx tsx src/index.ts",
    "dev": "npx tsx watch src/index.ts"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.12.0",
    "express": "^4.21.0",
    "zod": "^3.24.0"
  },
  "devDependencies": {
    "tsx": "^4.19.0",
    "@types/express": "^5.0.0"
  }
}
```

### 测试命令
```bash
# 1. 初始化会话
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'

# 2. 调用 echo tool
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"echo","arguments":{"message":"hello catalyst"}}}'

# 3. 列出所有 tools
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/list","params":{}}'
```

---

## 关键洞察

### 洞察 1: 无状态 vs 有状态是核心设计决策
无状态模式（`sessionIdGenerator: undefined`）每个请求创建新 server+transport，适合 Serverless/云函数。有状态模式维护会话，适合长连接场景。**OpenClaw MCP Server 应该从无状态开始**，因为工具本身是独立的。

### 洞察 2: McpServer.tool() 的高层 API 比底层 Server class 更实用
底层 `Server` class 需要手动处理 `SetRequestHandler`，而 `McpServer` 的 `tool()`/`resource()`/`prompt()` 方法自动处理 schema 注册和 JSON-RPC 路由。**直接用 McpServer 高层 API，不要碰底层。**

### 洞察 3: 认证应在 Express 中间件层处理
SDK 本身不处理认证。Render 模板的模式是：在 Express middleware 中验证 Bearer Token，验证通过后才创建 transport。这让认证逻辑与 MCP 逻辑完全解耦。

### 洞察 4: Prompts 是被低估的原语
大多数 MCP 服务器只暴露 Tools，忽略了 Prompts。但 Prompts 可以编码专家工作流（如代码审查模板），让用户一键触发复杂流程。**OpenClaw 的 Agent Skill 本质上就是 Prompt + Tool 的组合**，天然适合用 MCP Prompt 暴露。

### 洞察 5: `createMcpExpressApp` 是官方推荐但较新的 API
可以直接用 `createMcpExpressApp({ allowedHosts })` 代替手动配置 Express，但手动配置更灵活。建议先用手动方式理解原理，再切换到官方 helper。

---

## 与现有项目关联

- **Agent Memory Service**: Tool `search_memory` 可以直接对接 AMS 的 `searchSimilar()` API
- **OpenClaw Skills**: 每个 Skill 可以暴露为 MCP Tool + Prompt 组合
- **Agent Trust Network**: MCP Resource 可以暴露信任元数据
- **A2A Protocol**: Agent Card 信息可以通过 MCP Resource 暴露给其他 Agent

---

## 下一步行动

1. **[本周] 初始化 openclaw-mcp-server 项目** — 用上面的 MVP 代码创建 `~/projects/openclaw-mcp-server/`，跑通 curl 测试
2. **[本周] 对接 AMS** — 把 `search_memory` tool 从模拟改为调用 AMS API
3. **[本周] 添加 Bearer Token 认证** — 参考 Render 模板模式
4. **[下周] 注册为 OpenClaw Skill** — 让 Catalyst 可以通过 MCP 调用自己的记忆服务
5. **[下周] 探索 MCP Inspector** — 用官方 Inspector UI 测试和调试

---

## 参考资料

- [Build Your First MCP Server (2026)](https://devtk.ai/en/blog/build-mcp-server-tutorial-2026/)
- [MCP TypeScript SDK Complete Guide](https://blog.agentailor.com/posts/mcp-typescript-sdk-complete-guide)
- [MCP Cheat Sheet 2026](https://www.webfuse.com/mcp-cheat-sheet)
- [Render MCP TypeScript Template](https://render.com/templates/mcp-server-typescript)
- [Cloudflare Remote MCP Servers](https://blog.cloudflare.com/remote-model-context-protocol-servers-mcp/)
- [MCP Prompts: The Primitives You're Not Using](https://dev.to/aws-heroes/mcp-prompts-and-resources-the-primitives-youre-not-using-3oo1)
