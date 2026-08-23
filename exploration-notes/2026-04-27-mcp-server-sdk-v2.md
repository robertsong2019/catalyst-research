# MCP Server TypeScript SDK v2 — 深度研究笔记

> 日期: 2026-04-27
> 主题: Model Context Protocol Server 实现，基于 TypeScript SDK v2
> 关联项目: OpenClaw MCP Server MVP（3 tools）

---

## 核心概念

### 1. McpServer + registerTool（SDK v2 核心模式）
SDK v2 使用 `McpServer` 类 + `registerTool()` 方法注册工具。输入输出用 **Standard Schema**（Zod v4 / Valibot / ArkType）定义，不再用 JSON Schema 手写。

```ts
import { McpServer } from '@modelcontextprotocol/server';
import * as z from 'zod/v4';

const server = new McpServer({ name: 'my-server', version: '1.0.0' });

server.registerTool('tool-name', {
  description: 'What this tool does',
  inputSchema: z.object({ param: z.string() }),
  outputSchema: z.object({ result: z.number() }), // optional structured output
}, async ({ param }) => ({
  content: [{ type: 'text', text: 'result' }],
  structuredContent: { result: 42 }, // 可选：结构化输出
}));
```

### 2. Streamable HTTP Transport（替代旧 SSE）
Streamable HTTP 是 v2 推荐的远程传输方式：
- 客户端 POST JSON-RPC 到单一端点（如 `/mcp`）
- 服务端响应 `application/json` 或 `text/event-stream`（SSE）
- 支持有状态（sessionIdGenerator）和无状态模式
- 通过 `@modelcontextprotocol/node` 的 `NodeStreamableHTTPServerTransport` 实现

### 3. Middleware 适配器（Express / Hono / Node HTTP）
SDK v2 拆分为细粒度包：
- `@modelcontextprotocol/server` — 核心库
- `@modelcontextprotocol/node` — Node.js HTTP transport
- `@modelcontextprotocol/express` — Express 适配器
- `@modelcontextprotocol/hono` — Hono 适配器

### 4. Tool Annotations（行为声明式元数据）
工具可以声明 `annotations`：`readOnlyHint`、`destructiveHint`、`idempotentHint`、`openWorldHint`。客户端据此决定展示方式，不影响执行语义。

### 5. Elicitation（v2 新特性）
服务端可通过 `ctx.mcpReq.elicit()` 向客户端收集用户输入（表单或 URL 跳转），用于非敏感和敏感信息收集场景。

---

## 可运行代码示例：OpenClaw MCP Server MVP

以下是一个完整的、可独立运行的 MCP Server，暴露 3 个工具（memory-search、memory-get、workspace-read），通过 Streamable HTTP + Express 提供服务。

```ts
// openclaw-mcp-server.ts
// 运行: npx tsx openclaw-mcp-server.ts
// 依赖: npm i @modelcontextprotocol/server @modelcontextprotocol/node @modelcontextprotocol/express express zod

import { randomUUID } from 'node:crypto';
import { createMcpExpressApp } from '@modelcontextprotocol/express';
import { NodeStreamableHTTPServerTransport } from '@modelcontextprotocol/node';
import { McpServer } from '@modelcontextprotocol/server';
import * as z from 'zod/v4';

// --- 模拟数据（实际实现中对接 OpenClaw workspace） ---
const memoryStore: Record<string, string> = {
  'project-alpha': 'Project Alpha: Building agent memory service with 445 tests passing.',
  'mcp-server': 'MCP Server: TypeScript SDK v2 implementation, Streamable HTTP transport.',
  'taskflow': 'TaskFlow: Durable flow substrate for multi-agent orchestration.',
};

// --- 创建 MCP Server ---
const server = new McpServer(
  { name: 'openclaw-mcp-server', version: '0.1.0' },
  {
    instructions: [
      'OpenClaw MCP Server provides access to workspace memory and files.',
      'Always use memory-search before memory-get to find relevant keys.',
      'Results are limited to 100 entries.',
    ].join(' '),
  }
);

// Tool 1: memory-search — 语义搜索记忆
server.registerTool(
  'memory-search',
  {
    title: 'Memory Search',
    description: 'Search workspace memory entries by keyword. Returns matching keys and snippets.',
    inputSchema: z.object({
      query: z.string().describe('Search query keyword'),
      limit: z.number().optional().default(5).describe('Max results to return'),
    }),
    annotations: {
      readOnlyHint: true,
      openWorldHint: false,
    },
  },
  async ({ query, limit }) => {
    const lower = query.toLowerCase();
    const results = Object.entries(memoryStore)
      .filter(([, v]) => v.toLowerCase().includes(lower))
      .slice(0, limit)
      .map(([k, v]) => ({ key: k, snippet: v.slice(0, 120) }));

    return {
      content: [{ type: 'text', text: JSON.stringify(results, null, 2) }],
      structuredContent: { results },
    };
  }
);

// Tool 2: memory-get — 获取完整记忆条目
server.registerTool(
  'memory-get',
  {
    title: 'Memory Get',
    description: 'Retrieve a full memory entry by its key.',
    inputSchema: z.object({
      key: z.string().describe('Memory entry key'),
    }),
    annotations: {
      readOnlyHint: true,
      idempotentHint: true,
    },
  },
  async ({ key }) => {
    const value = memoryStore[key];
    if (!value) {
      return {
        content: [{ type: 'text', text: `Key "${key}" not found. Use memory-search first.` }],
        isError: true,
      };
    }
    return {
      content: [{ type: 'text', text: value }],
      structuredContent: { key, value },
    };
  }
);

// Tool 3: workspace-read — 读取工作区文件
server.registerTool(
  'workspace-read',
  {
    title: 'Workspace Read',
    description: 'Read a file from the workspace directory.',
    inputSchema: z.object({
      path: z.string().describe('Relative file path within workspace'),
    }),
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
    },
  },
  async ({ path }) => {
    // 安全检查：防止路径遍历
    if (path.includes('..')) {
      return {
        content: [{ type: 'text', text: 'Path traversal not allowed.' }],
        isError: true,
      };
    }
    // 实际实现: const content = await fs.readFile(resolve(WORKSPACE_ROOT, path), 'utf-8');
    return {
      content: [{
        type: 'text',
        text: `[Simulated] Contents of ${path}: This would return the actual file content.`,
      }],
    };
  }
);

// --- 启动 Streamable HTTP 服务 ---
async function main() {
  const port = Number(process.env.PORT ?? 3001);

  const transport = new NodeStreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID(), // 有状态模式
  });

  await server.connect(transport);

  // 使用 Express 适配器挂载
  const app = createMcpExpressApp({
    transport: () => transport,
  });

  app.listen(port, () => {
    console.log(`🧪 OpenClaw MCP Server running on http://localhost:${port}/mcp`);
  });
}

main().catch(console.error);
```

### 运行方式

```bash
mkdir openclaw-mcp-server && cd openclaw-mcp-server
npm init -y
npm i @modelcontextprotocol/server @modelcontextprotocol/node @modelcontextprotocol/express express zod
# 将上面代码保存为 openclaw-mcp-server.ts
npx tsx openclaw-mcp-server.ts
# 测试: curl -X POST http://localhost:3001/mcp \
#   -H "Content-Type: application/json" \
#   -H "Accept: application/json, text/event-stream" \
#   -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'
```

---

## 关键洞察

### 洞察 1: SDK v2 从 "Builder 模式" 转向 "声明式注册"
v1 使用链式 `.tool()`, `.resource()`, `.prompt()` 方法；v2 用 `registerTool()` + Zod schema 声明输入输出。**outputSchema + structuredContent** 是 v2 的亮点——允许客户端程序化消费工具输出，而非仅解析文本。

### 洞察 2: Streamable HTTP 是 SSE v2 的替代，不是增量升级
旧的 HTTP+SSE（2024-11-05 协议）已被完全替代。新传输协议：
- 单一端点处理 POST（发消息）和 GET（监听通知）
- 支持 SSE 流式和 JSON 直接响应两种模式
- 有状态/无状态可配置，适配不同部署拓扑（单机 vs K8s 水平扩展）

### 洞察 3: Standard Schema 接口让 SDK 不绑定特定验证库
SDK v2 采用 [Standard Schema](https://standardschema.dev/) 接口，Zod v4、Valibot、ArkType 都可以用。这意味着 OpenClaw MCP Server 可以选择任何已集成的库，不被迫引入 Zod。但 Zod v4 生态最成熟，推荐作为默认。

### 洞察 4: Tool Annotations 是 MCP 的 "自描述协议"
`readOnlyHint`、`destructiveHint` 等注解让客户端在不执行工具的情况下理解其副作用。这对 OpenClaw 的安全策略（Red Lines）天然适配——可以在调用前检查 annotations 决定是否需要用户审批。

### 洞察 5: Elicitation 是 v2 的隐藏杀手锏
服务端可以通过 `elicit()` 向用户收集信息（表单或 URL 跳转）。这解决了 MCP 工具需要运行时参数的关键缺口——比如工具需要 API Key，不再需要预配置，可以运行时安全收集。

---

## 与 OpenClaw 现有项目的关联

| 项目 | 关联点 |
|------|--------|
| Agent Memory Service | MCP Tool `memory-search` / `memory-get` 可以直接对接 AMS API |
| agent-task-cli | MCP Tool `workspace-read` 可以暴露 CLI 的任务管理能力 |
| OpenClaw Gateway | MCP Server 可以作为 Gateway 的一个插件/扩展点 |
| mcporter skill | 已有 MCP 调用能力，MCP Server 是互补方向（提供而非消费） |

---

## 下一步行动

1. **[本周]** 初始化 `openclaw-mcp-server` 项目，实现上述 MVP 代码，对接真实 workspace 文件读取
2. **[本周]** 用 `mcporter` 测试自建 MCP Server 的连通性
3. **[下周]** 对接 AMS 的 searchByTimeRange API 作为第 4 个 tool
4. **[下周]** 研究 OAuth 认证集成（`--oauth` 模式），用于远程部署场景

---

## 参考资料

- [MCP TypeScript SDK v2 GitHub](https://github.com/modelcontextprotocol/typescript-sdk) — main branch, pre-alpha
- [MCP Transports Spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) — Streamable HTTP 协议规范
- [Server Guide](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/server.md) — v2 服务端开发指南
- [Examples Index](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/examples/server/README.md) — 11 个可运行示例
- [Standard Schema](https://standardschema.dev/) — 跨库 schema 接口标准
