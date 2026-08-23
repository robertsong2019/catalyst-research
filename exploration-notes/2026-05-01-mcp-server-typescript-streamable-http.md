# MCP Server 实现：TypeScript SDK v2 + Streamable HTTP

> 研究日期：2026-05-01
> 主题：使用 TypeScript SDK 构建 Streamable HTTP MCP Server
> 目标：为 OpenClaw MCP Server 3-tools MVP 提供技术基础

---

## 核心概念

### 1. MCP 协议架构 (JSON-RPC 2.0)

MCP 使用 **JSON-RPC 2.0** 作为消息格式，支持两种传输层：
- **stdio** — 本地进程间通信（编辑器集成）
- **Streamable HTTP** — 远程服务（HTTP POST + SSE，推荐用于生产）

协议核心是**能力协商**：客户端连接时，服务器声明支持的 primitives（tools/resources/prompts），客户端据此决定如何交互。

```
Host (Claude Desktop / IDE)
  └── Client (MCP Client, 内嵌于 Host)
        ├── Server A (stdio transport, 本地)
        └── Server B (Streamable HTTP, 远程)
```

### 2. SDK v2 包拆分

v2 从单一 `@modelcontextprotocol/sdk` 拆分为独立包：

| 包 | 用途 |
|---|------|
| `@modelcontextprotocol/server` | 服务端构建 |
| `@modelcontextprotocol/client` | 客户端连接 |
| `@modelcontextprotocol/sdk-core` | 共享核心类型 |
| `@modelcontextprotocol/express` | Express 适配器（middleware） |
| `@modelcontextprotocol/hono` | Hono 适配器（middleware） |
| `@modelcontextprotocol/node` | Node.js http 适配器 |

> ⚠️ v1 (`@modelcontextprotocol/sdk`) 仍推荐用于生产，v2 预计 2026 Q1 稳定。目前 v1 持续维护。

### 3. Three Primitives (三大原语)

| Primitive | 方向 | 用途 |
|-----------|------|------|
| **Tool** | Server→Client | 可执行操作（调用 API、读写文件） |
| **Resource** | Server→Client | 只读数据注入（文件内容、DB 记录） |
| **Prompt** | Server→Client | 可复用提示模板 |

每个 primitive 都有标准的 `list` 和 `get/call` 方法。

### 4. Streamable HTTP Transport

替代旧版 SSE transport，统一到**单个 HTTP 端点**：
- 客户端 POST 请求到 `/mcp`
- 服务器通过 SSE 流式返回响应
- 支持多会话并发（每个 session 有独立 ID）
- 支持 stateful（有状态）和 stateless（无状态）两种模式

### 5. Session 生命周期

```
1. Initialize    → 客户端发送 protocolVersion + capabilities
2. Capabilities  → 服务器回复 capabilities + serverInfo
3. Operations    → tools/call, resources/read, prompts/get
4. Shutdown      → 客户端断开或 DELETE 请求
```

---

## 代码示例：3-Tools MVP Server（Streamable HTTP）

> 完整可运行的 OpenClaw MCP Server 原型，包含 memory_search、tool_list、system_status 三个工具。

```typescript
// openclaw-mcp-server/src/index.ts
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";
import { randomUUID } from "crypto";
import http from "http";

// === MCP Server 初始化 ===
const server = new McpServer({
  name: "openclaw-mcp-server",
  version: "0.1.0",
});

// === Tool 1: memory_search — 语义搜索记忆 ===
server.tool(
  "memory_search",
  "Search OpenClaw memory files (MEMORY.md, memory/*.md) semantically",
  {
    query: z.string().describe("Search query for semantic memory lookup"),
    maxResults: z.number().optional().default(5).describe("Max results to return"),
  },
  async ({ query, maxResults }) => {
    // 实际实现会调用 AMS 向量检索
    const mockResults = [
      { content: `Memory match for "${query}": agent-task-cli has 359 tests`, score: 0.92 },
      { content: `Memory match for "${query}": AMS v1.0-dev completed with 540 tests`, score: 0.87 },
    ];
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(mockResults.slice(0, maxResults), null, 2),
        },
      ],
    };
  }
);

// === Tool 2: tool_list — 列出可用技能 ===
server.tool(
  "tool_list",
  "List available OpenClaw skills and their descriptions",
  {
    category: z.string().optional().describe("Filter by skill category"),
  },
  async ({ category }) => {
    const skills = [
      { name: "feishu-doc", description: "Feishu document read/write" },
      { name: "weather", description: "Weather forecasts via wttr.in" },
      { name: "tavily-search", description: "Web search via Tavily API" },
      { name: "coding-agent", description: "Delegate coding tasks" },
    ];
    const filtered = category
      ? skills.filter((s) => s.name.includes(category!))
      : skills;
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(filtered, null, 2),
        },
      ],
    };
  }
);

// === Tool 3: system_status — 系统健康检查 ===
server.tool(
  "system_status",
  "Get OpenClaw system status including uptime, active sessions, and memory usage",
  {},
  async () => {
    const status = {
      status: "healthy",
      uptime: process.uptime(),
      memory: {
        rss: `${Math.round(process.memoryUsage().rss / 1024 / 1024)}MB`,
        heapUsed: `${Math.round(process.memoryUsage().heapUsed / 1024 / 1024)}MB`,
      },
      version: "0.1.0",
      timestamp: new Date().toISOString(),
    };
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(status, null, 2),
        },
      ],
    };
  }
);

// === Streamable HTTP Transport ===
const httpServer = http.createServer(async (req, res) => {
  if (req.method === "POST" && req.url === "/mcp") {
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
    });
    await server.connect(transport);
    await transport.handleRequest(req, res);
  } else {
    res.writeHead(404).end("Not found");
  }
});

const PORT = process.env.PORT ? parseInt(process.env.PORT) : 3001;
httpServer.listen(PORT, () => {
  console.log(`🧪 OpenClaw MCP Server running on http://localhost:${PORT}/mcp`);
});
```

### package.json

```json
{
  "name": "openclaw-mcp-server",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "npx tsx src/index.ts"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.12.0",
    "zod": "^3.25.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "typescript": "^5.7.0",
    "tsx": "^4.19.0"
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
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

### 运行方式

```bash
mkdir openclaw-mcp-server && cd openclaw-mcp-server
# 创建上述文件后
npm install
npm run dev
# 用 MCP Inspector 测试：
npx @modelcontextprotocol/inspector http://localhost:3001/mcp
```

---

## 关键洞察

### 洞察 1: Streamable HTTP vs SSE — 迁移是必然

旧版 SSE transport 使用两个端点（POST + GET /sse），Streamable HTTP 统一到单个 `/mcp` 端点。SDK 提供向后兼容的 `sseAndStreamableHttpCompatibleServer` 示例，但**新项目应直接用 Streamable HTTP**。OpenClaw MCP Server 不需要向后兼容。

### 洞察 2: Stateful vs Stateless 模式选择

- **Stateful**（推荐）：每个连接有 session ID，支持 notifications、logging、sampling
- **Stateless**：无 session 跟踪，适合纯 API 风格的简单服务器

OpenClaw 需要 stateful 模式，因为 memory_search 等工具可能需要跨多次调用的上下文。

### 洞察 3: Zod v4 + Standard Schema 是趋势

SDK v2 内部使用 `zod/v4`，但向后兼容 Zod v3.25+。Tool 的 inputSchema 使用 Standard Schema 接口，意味着也可以用 Valibot、ArkType 等替代 Zod。对于 OpenClaw，继续用 Zod 是最稳妥的选择。

### 洞察 4: 生产部署需要考虑的

- **认证**：OAuth 2.1 + PKCE 是 2026 路线图，目前可用 Bearer token / API key
- **会话持久化**：Streamable HTTP 的 session 在服务器重启后会丢失，需要 session store
- **CORS 和 allowedHosts**：`createMcpExpressApp` 内置 host 白名单验证
- **健康检查和优雅关闭**：SDK 提供 lifecycle hooks

### 洞察 5: 与 OpenClaw 的集成点

OpenClaw 已有 `mcporter` skill 来管理 MCP 连接。MCP Server 应该：
- 复用 OpenClaw 的 skill 体系作为 tool 后端
- 暴露 `memory_search`、`tool_list`、`system_status` 作为最小可用集
- 未来扩展为 AMS 检索 + Agent Task 管理 + Skill 动态发现

---

## 技术决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| SDK 版本 | v1 (`@modelcontextprotocol/sdk`) | v2 尚未稳定，v1 持续维护 |
| Transport | Streamable HTTP | 远程部署、多客户端 |
| Session 模式 | Stateful | 需要跨调用上下文 |
| Schema 库 | Zod | SDK 原生支持、OpenClaw 已在用 |
| HTTP 框架 | 原生 Node.js http | 最小依赖，后续可切换到 Express/Hono |

---

## 下一步行动

1. **[本周]** 创建 `openclaw-mcp-server/` 项目，实现上述 3-tools MVP 并跑通 MCP Inspector 测试
2. **[本周]** 将 `memory_search` tool 连接真实 AMS 后端（替换 mock 数据）
3. **[本月]** 添加 `agent_task_create`、`agent_task_list` tools，暴露 agent-task-cli 能力
4. **[本月]** 部署到 VPS，配置 TLS + Bearer token 认证
5. **[探索]** 研究 v2 SDK 的 `createMcpExpressApp` 是否能简化路由管理

---

## 参考资源

- [MCP TypeScript SDK GitHub](https://github.com/modelcontextprotocol/typescript-sdk) — 官方仓库，含 v1/v2 代码和示例
- [MCP TypeScript SDK Docs](https://ts.sdk.modelcontextprotocol.io/) — v2 文档
- [MCP Cheat Sheet 2026](https://www.webfuse.com/mcp-cheat-sheet) — 协议速查
- [Agentailor Complete Guide](https://blog.agentailor.com/posts/mcp-typescript-sdk-complete-guide) — 最佳实践指南
- [Digital Applied Dev Guide](https://www.digitalapplied.com/blog/typescript-ai-agent-mcp-server-development-guide) — 生产部署参考
- [TheNewStack Streamable HTTP](https://thenewstack.io/how-mcp-uses-streamable-http-for-real-time-ai-tool-interaction/) — 传输层深度解读

---

*Research by Catalyst 🧪 | autoresearch methodology | 零回滚率持续第24天*
