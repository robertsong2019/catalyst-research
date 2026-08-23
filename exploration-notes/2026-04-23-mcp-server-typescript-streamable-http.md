# MCP Server: TypeScript SDK + Streamable HTTP

> 研究日期: 2026-04-23 | 关联任务: OpenClaw MCP Server 3-tools MVP

## 核心概念 (5个)

### 1. MCP (Model Context Protocol)
开放协议标准，让 AI 应用（Claude、ChatGPT、VS Code Copilot 等）通过统一接口连接外部系统。类比 USB-C：一个标准，连接一切。支持 tools（动作）、resources（只读数据）、prompts（交互模板）。

### 2. McpServer + Standard Schema
v2 SDK 的核心类 `McpServer`，配合 Zod v4/Valibot/ArkType 定义 schema。使用 `registerTool()`、`registerResource()`、`registerPrompt()` 注册能力。schema 校验自动完成。

### 3. Streamable HTTP Transport
远程部署的传输层（vs stdio 用于本地进程）。支持两种模式：
- **有状态**: `sessionIdGenerator: () => randomUUID()` — 支持 session 恢复
- **无状态**: `sessionIdGenerator: undefined` — 简单但不支持恢复
- 可选 `enableJsonResponse: true` 返回 JSON 而非 SSE 流

### 4. Split Packages (Monorepo)
v2 SDK 拆分为多个包：
- `@modelcontextprotocol/server` — 核心 server 库
- `@modelcontextprotocol/client` — client 库
- `@modelcontextprotocol/node` — Node.js HTTP transport 适配
- `@modelcontextprotocol/express` — Express 集成
- `@modelcontextprotocol/hono` — Hono 集成

### 5. Tool Annotations
工具行为标注：`destructiveHint`、`readOnlyHint`、`idempotentHint` 等。客户端据此决定是否自动执行或需确认。不影响执行语义，仅影响展示。

---

## 可运行代码示例

### MVP: 3-tool Streamable HTTP MCP Server

```ts
// server.ts — 可直接运行的 MCP Server MVP
import { randomUUID } from 'node:crypto';
import { createServer } from 'node:http';
import { McpServer } from '@modelcontextprotocol/server';
import { NodeStreamableHTTPServerTransport } from '@modelcontextprotocol/node';
import * as z from 'zod/v4';

const server = new McpServer(
  { name: 'openclaw-mcp', version: '0.1.0' },
  {
    instructions:
      'OpenClaw MCP Server. Use list_tools to discover capabilities, ' +
      'search_memory for semantic search, and run_command for shell execution.'
  }
);

// Tool 1: 搜索记忆
server.registerTool(
  'search_memory',
  {
    title: 'Search Memory',
    description: '语义搜索 OpenClaw 记忆库，返回相关笔记片段',
    inputSchema: z.object({
      query: z.string().describe('搜索关键词'),
      limit: z.number().optional().default(5).describe('返回条数')
    }),
    annotations: { readOnlyHint: true }
  },
  async ({ query, limit }) => {
    // 实际实现可调用 memory_search API
    const results = [
      { score: 0.95, text: `匹配结果: "${query}" — 相关记忆片段...` }
    ];
    return {
      content: [{
        type: 'text',
        text: JSON.stringify(results.slice(0, limit), null, 2)
      }]
    };
  }
);

// Tool 2: 执行命令
server.registerTool(
  'run_command',
  {
    title: 'Run Command',
    description: '在 OpenClaw workspace 执行 shell 命令',
    inputSchema: z.object({
      command: z.string().describe('要执行的命令'),
      timeout: z.number().optional().default(30).describe('超时秒数')
    }),
    annotations: { destructiveHint: true }
  },
  async ({ command, timeout }) => {
    try {
      const { execSync } = await import('node:child_process');
      const output = execSync(command, {
        timeout: timeout * 1000,
        cwd: '/root/.openclaw/workspace',
        maxBuffer: 1024 * 1024
      });
      return {
        content: [{ type: 'text', text: output.toString('utf-8') }]
      };
    } catch (err: any) {
      return {
        content: [{ type: 'text', text: `Error: ${err.message}` }],
        isError: true
      };
    }
  }
);

// Tool 3: 系统状态
server.registerTool(
  'system_status',
  {
    title: 'System Status',
    description: '获取 OpenClaw 系统当前状态（运行时间、内存、磁盘）',
    inputSchema: z.object({}),
    annotations: { readOnlyHint: true }
  },
  async () => {
    const os = await import('node:os');
    const status = {
      hostname: os.hostname(),
      uptime: `${(os.uptime() / 3600).toFixed(1)}h`,
      mem: {
        total: `${(os.totalmem() / 1e9).toFixed(1)}GB`,
        free: `${(os.freemem() / 1e9).toFixed(1)}GB`,
        usage: `${((1 - os.freemem() / os.totalmem()) * 100).toFixed(1)}%`
      },
      cpus: os.cpus().length,
      timestamp: new Date().toISOString()
    };
    return {
      content: [{ type: 'text', text: JSON.stringify(status, null, 2) }]
    };
  }
);

// 启动 Streamable HTTP server
async function main() {
  const port = parseInt(process.env.PORT || '3001');

  const transport = new NodeStreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID()
  });

  await server.connect(transport);

  const httpServer = createServer(async (req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

    await transport.handleRequest(req, res);
  });

  httpServer.listen(port, () => {
    console.log(`🧪 OpenClaw MCP Server running on http://localhost:${port}/mcp`);
  });
}

main();
```

### 运行方式

```bash
# 安装依赖
npm init -y
npm install @modelcontextprotocol/server @modelcontextprotocol/node zod

# 运行
npx tsx server.ts

# 测试 (用 MCP 客户端或 curl)
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

### 用 Express 集成（生产推荐）

```ts
import express from 'express';
import { createMcpExpressApp } from '@modelcontextprotocol/express';
import { NodeStreamableHTTPServerTransport } from '@modelcontextprotocol/node';

const app = express();
const mcpApp = createMcpExpressApp(server);
app.use('/mcp', mcpApp);
app.listen(3001);
```

---

## 关键洞察 (4条)

### 1. v2 SDK 是 breaking change，但架构更优
v2 拆分为 server/client/middleware 包，Standard Schema 支持（不锁定 Zod）。v1.x 继续维护 6 个月。**新项目直接用 v2，别犹豫。**

### 2. Streamable HTTP 是远程部署的唯一选择
stdio 只适合本地进程通信（Claude Desktop、CLI）。OpenClaw MCP Server 作为远程服务，必须用 Streamable HTTP。有状态模式支持 session 恢复，但增加复杂度 — MVP 先用无状态。

### 3. Tool Annotations 是安全层
`destructiveHint: true` 的工具客户端会弹确认。这对 OpenClaw 的 `run_command` 尤为重要 — 防止 AI 自主执行破坏性命令。设计 MCP tools 时就要考虑标注。

### 4. Express/Hono middleware 是薄适配层
官方明确说 middleware 包不引入业务逻辑，只做 HTTP 请求到 MCP transport 的桥接。这意味着可以轻松切换框架。推荐 Hono（更轻量）或 Express（生态更大）。

---

## 与现有项目关联

| 项目 | 关联点 |
|------|--------|
| OpenClaw MCP Server (HEARTBEAT) | 直接落地 — 这就是 MVP 的技术蓝图 |
| Agent Memory Service | `search_memory` tool 可调用 AMS API |
| A2A Agent Trust | MCP resource 可暴露 Agent Card |
| mcporter skill | mcporter 已有 MCP client 能力，可互操作 |

---

## 下一步行动

1. **【本周】创建 openclaw-mcp-server 项目**，用上面代码作为骨架，`npm init` + TypeScript + tsconfig
2. **【本周】实现 3 个 real tools**: `search_memory`（接 AMS）、`run_command`（接 OpenClaw exec）、`system_status`（接 session_status）
3. **【下周】添加 Express/Hono 包装**，部署到 VPS，测试与 Claude/ChatGPT 的连接
4. **【下周】设计 tool 权限模型** — 哪些 tool 需要 `destructiveHint`，是否需要 OAuth

---

## 参考

- [MCP 官方文档](https://modelcontextprotocol.io/docs)
- [TypeScript SDK v2 (GitHub)](https://github.com/modelcontextprotocol/typescript-sdk)
- [Server Guide](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/server.md)
- [Streamable HTTP 示例](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/examples/server/src/simpleStreamableHttp.ts)
- [MCP Spec - Transport](https://modelcontextprotocol.io/specification/latest/basic/transitions)
