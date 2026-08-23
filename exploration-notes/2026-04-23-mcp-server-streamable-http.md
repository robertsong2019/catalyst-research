# MCP Server with TypeScript SDK + Streamable HTTP Transport

> 研究日期: 2026-04-23 | 主题: 实现 OpenClaw MCP Server 的技术基础
> 来源: MCP 官方规范、TypeScript SDK 源码、GitHub Issues、多个生产级模板

---

## 核心概念 (5个)

### 1. MCP (Model Context Protocol)
- Anthropic 于 2024 年 11 月推出的开放标准协议
- 基于 JSON-RPC 2.0，灵感来自 LSP (Language Server Protocol)
- 解决 AI 模型与外部工具/数据源的 N×M 集成问题
- 三个原语(primitives): **Tools**(可执行函数)、**Resources**(可读数据)、**Prompts**(提示模板)

### 2. Streamable HTTP Transport
- 2025-11-25 规范版本引入，**取代旧的 HTTP+SSE 传输**
- 单一 HTTP 端点同时支持 POST(客户端→服务端) 和 GET(SSE 流)
- 支持**无状态请求-响应**模式 + 可选 **SSE 流式**模式
- 通过 `Mcp-Session-Id` 头实现会话管理

### 3. McpServer 高级 API
- `@modelcontextprotocol/sdk/server/mcp.js` 提供的高级封装
- `server.tool()` 注册工具，用 Zod 定义输入 schema
- `server.resource()` 注册资源
- `server.prompt()` 注册提示模板
- 支持 Standard Schema（Zod v4、Valibot、ArkType 均可）

### 4. 会话管理 (Session Management)
- 服务端在初始化时通过 `Mcp-Session-Id` 头返回会话 ID
- 客户端必须在后续所有请求中携带此头
- `sessionIdGenerator`: () => randomUUID() 生成唯一会话 ID
- `onsessioninitialized` 回调存储 transport 映射
- `onclose` 回调清理资源

### 5. SDK v2 包结构变更 (预计 Q2 2026)
- 当前: `@modelcontextprotocol/sdk` (单包，子路径导入)
- v2: 拆分为 `@modelcontextprotocol/server`、`@modelcontextprotocol/client`
- 中间件包: `@modelcontextprotocol/express`、`@modelcontextprotocol/hono`、`@modelcontextprotocol/node`
- 概念不变，仅导入路径变化

---

## 可运行代码示例: 完整的 MCP Server (Streamable HTTP + 3 Tools)

> 这是一个可直接运行的 MCP Server，暴露 3 个工具：echo、时间查询、JSON 格式化。

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
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "tsx src/index.ts",
    "inspect": "npx @modelcontextprotocol/inspector node dist/index.js"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.12.0",
    "express": "^5.1.0",
    "zod": "^3.25.0"
  },
  "devDependencies": {
    "@types/express": "^5.0.0",
    "@types/node": "^22.0.0",
    "tsx": "^4.19.0",
    "typescript": "^5.7.0"
  }
}
```

### tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true
  },
  "include": ["src/**/*"]
}
```

### src/index.ts (核心实现)
```typescript
#!/usr/bin/env node

import express from "express";
import { randomUUID } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

// ── 创建 MCP Server ──────────────────────────────────────
const createServer = () => {
  const server = new McpServer({
    name: "openclaw-mcp-server",
    version: "1.0.0",
  });

  // Tool 1: echo — 回显输入文本
  server.tool(
    "echo",
    "Echo back the input text",
    { text: z.string().describe("Text to echo back") },
    async ({ text }) => ({
      content: [{ type: "text", text }],
    })
  );

  // Tool 2: get_time — 获取指定时区的当前时间
  server.tool(
    "get_time",
    "Get current time in a specified timezone",
    {
      timezone: z
        .string()
        .default("Asia/Shanghai")
        .describe("IANA timezone string, e.g. 'America/New_York'"),
    },
    async ({ timezone }) => {
      try {
        const now = new Date();
        const formatted = new Intl.DateTimeFormat("zh-CN", {
          timeZone: timezone,
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }).format(now);
        return {
          content: [
            {
              type: "text",
              text: `${timezone}: ${formatted}`,
            },
          ],
        };
      } catch {
        return {
          content: [
            {
              type: "text",
              text: `Error: Invalid timezone '${timezone}'. Use IANA format like 'Asia/Shanghai'.`,
            },
          ],
          isError: true,
        };
      }
    }
  );

  // Tool 3: format_json — 格式化/验证 JSON 字符串
  server.tool(
    "format_json",
    "Format and validate a JSON string with configurable indent",
    {
      json: z.string().describe("JSON string to format"),
      indent: z.number().default(2).describe("Indentation spaces"),
    },
    async ({ json, indent }) => {
      try {
        const parsed = JSON.parse(json);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(parsed, null, indent),
            },
          ],
        };
      } catch (e) {
        return {
          content: [
            {
              type: "text",
              text: `Invalid JSON: ${(e as Error).message}`,
            },
          ],
          isError: true,
        };
      }
    }
  );

  return server;
};

// ── Express + Streamable HTTP Transport ───────────────────
const app = express();
app.use(express.json());

// 存储活跃的 transport 会话
const transports: Record<
  string,
  StreamableHTTPServerTransport
> = {};

// POST: 客户端 → 服务端通信 (JSON-RPC 请求)
app.post("/mcp", async (req, res) => {
  const sessionId = req.headers["mcp-session-id"] as
    | string
    | undefined;
  let transport: StreamableHTTPServerTransport;

  if (sessionId && transports[sessionId]) {
    // 已有会话，复用 transport
    transport = transports[sessionId];
  } else if (
    !sessionId &&
    isInitializeRequest(req.body)
  ) {
    // 新初始化请求
    transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      onsessioninitialized: (newSessionId) => {
        transports[newSessionId] = transport;
        console.log(
          `[MCP] Session initialized: ${newSessionId}`
        );
      },
    });

    // 会话关闭时清理
    transport.onclose = () => {
      if (transport.sessionId) {
        delete transports[transport.sessionId];
        console.log(
          `[MCP] Session closed: ${transport.sessionId}`
        );
      }
    };

    const server = createServer();
    await server.connect(transport);
  } else {
    res.status(400).json({
      jsonrpc: "2.0",
      error: {
        code: -32000,
        message: "Bad Request: No valid session ID provided",
      },
      id: null,
    });
    return;
  }

  await transport.handleRequest(req, res, req.body);
});

// GET: SSE 流 (服务端 → 客户端通知)
const handleSessionRequest = async (
  req: express.Request,
  res: express.Response
) => {
  const sessionId = req.headers["mcp-session-id"] as
    | string
    | undefined;
  if (!sessionId || !transports[sessionId]) {
    res
      .status(400)
      .send("Invalid or missing session ID");
    return;
  }
  const transport = transports[sessionId];
  await transport.handleRequest(req, res);
};

app.get("/mcp", handleSessionRequest);
app.delete("/mcp", handleSessionRequest);

// 健康检查端点
app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    activeSessions: Object.keys(transports).length,
    server: "openclaw-mcp-server",
    version: "1.0.0",
  });
});

// ── 启动服务 ──────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(
    `[MCP Server] Running on http://localhost:${PORT}/mcp`
  );
  console.log(
    `[Health] http://localhost:${PORT}/health`
  );
});
```

### 运行方法
```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 生产模式
npm run build && npm start

# 用 MCP Inspector 调试
npm run inspect
```

### 测试方法
```bash
# 1. 初始化会话
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
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

# 2. 调用 echo 工具（替换 SESSION_ID）
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "echo",
      "arguments": { "text": "Hello from OpenClaw MCP!" }
    }
  }'

# 3. 健康检查
curl http://localhost:3000/health
```

---

## 关键洞察 (5条)

### 1. Streamable HTTP > 旧 SSE 双端点方案
旧的 HTTP+SSE 需要两个端点 (`/sse` + `/messages`)，Streamable HTTP 统一为单一端点 (`/mcp`)。POST 请求可以在同一个 HTTP 响应中返回结果，无需打开 SSE 流。只有服务端需要主动推送时才升级为 SSE。**新项目一律用 Streamable HTTP。**

### 2. 每个 session 需要独立的 McpServer 实例
这是关键的架构决策！`createServer()` 为每个新会话创建独立的 McpServer + Transport 对。原因是 MCP 协议设计为 1:1 连接（一个 server 实例只能连接一个 transport）。多客户端场景下必须为每个会话创建独立实例。

### 3. 安全要点: Origin 验证 + 认证
规范要求服务端验证 `Origin` 头防止 DNS 重绑定攻击。生产环境还需实现 Bearer Token 认证。Render 模板提供了 `MCP_API_TOKEN` 自动生成的参考实现。

### 4. SDK v2 包拆分是好事
从单包拆分为 `@modelcontextprotocol/server`、`@modelcontextprotocol/client`、中间件包 — 减少不必要的依赖。Express/Hono/Node 原生 HTTP 各有专用适配器。当前使用 `@modelcontextprotocol/sdk` 子路径导入即可，迁移只需改 import。

### 5. OpenClaw MCP Server 的 MVP 路径清晰
基于以上研究，OpenClaw MCP Server 的 MVP 可以：
- 用 Express + StreamableHTTPServerTransport 作为骨架
- 3 个核心 Tools: `run_command`(执行 shell)、`read_file`、`write_file` — 直接封装 OpenClaw 现有能力
- 加上 `/health` 端点和 session 管理
- 配置 Cursor/Claude Desktop 连接即可使用

---

## 下一步行动

1. **[本周]** 基于上述代码骨架实现 OpenClaw MCP Server MVP
   - 3 tools: `run_command`, `read_file`, `write_file`
   - Streamable HTTP transport + session 管理
   - Docker 化部署
2. **[本周]** 添加 Bearer Token 认证中间件
3. **[后续]** 研究 `@modelcontextprotocol/express` 中间件包能否简化当前手动 session 管理
4. **[后续]** 评估 SDK v2 迁移路径，确认导入变更范围

---

## 与现有项目关联

| 项目 | 关联 |
|------|------|
| **OpenClaw MCP Server** (待实现) | 直接输出 — 上述代码是 MVP 骨架 |
| **Agent Memory Service** | MCP Server 可暴露 AMS 的 search/recall 能力为 MCP Tool |
| **A2A Agent Trust** | MCP Server 可暴露 trust 验证为 MCP Tool |
| **mcporter skill** | 已有 MCP 调用能力，OpenClaw MCP Server 是反向 — 让外部调用 OpenClaw |

---

## 参考资料

- [MCP 官方规范 - Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP TypeScript SDK (GitHub)](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP TypeScript SDK 完整指南 (AgentAIlor)](https://blog.agentailor.com/posts/mcp-typescript-sdk-complete-guide)
- [Streamable HTTP Session 管理 (Issue #412)](https://github.com/modelcontextprotocol/typescript-sdk/issues/412)
- [Render MCP Server 模板](https://render.com/templates/mcp-server-typescript)
- [Cloudflare MCP Agent](https://blog.cloudflare.com/remote-model-context-protocol-servers-mcp/)
- [freeCodeCamp MCP 教程](https://www.freecodecamp.org/news/how-to-build-a-custom-mcp-server-with-typescript-a-handbook-for-developers/)
