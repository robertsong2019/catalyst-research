# MCP Server 实现模式深度研究

> 研究日期：2026-04-19 | 主题：OpenClaw MCP Server 实现模式（从研究到实现）
> 状态：✅ 包含可运行代码示例
> 前置研究：[2026-04-18 MCP Server 技术选型](2026-04-18-mcp-server-typescript-streamable-http.md)

---

## 核心概念

### 1. SDK v2 包架构（最新）
2026年4月的 SDK 已完成包拆分，`@modelcontextprotocol/sdk` 单体包被取代：

```
@modelcontextprotocol/server    → 核心库 (McpServer, ResourceTemplate, completable)
@modelcontextprotocol/node      → Node.js HTTP transport (NodeStreamableHTTPServerTransport)
@modelcontextprotocol/express   → Express 集成 (createMcpExpressApp)
@modelcontextprotocol/hono      → Hono 集成 (Edge Runtime 友好)
```

关键变化：**`server.registerTool()` 替代旧 `server.tool()`**，新 API 支持 `title`、`outputSchema`、`annotations`。

### 2. 注册模式：registerTool vs tool
旧 API（v1）：
```typescript
server.tool('name', 'description', { query: z.string() }, async ({ query }) => ({ ... }));
```

新 API（v2）：
```typescript
server.registerTool('name', {
  title: 'Display Name',           // UI 友好名称
  description: 'When to use this', // LLM 理解的描述
  inputSchema: z.object({ ... }),  // Zod v4 schema
  outputSchema: z.object({ ... }), // 可选：结构化输出
}, async (input, ctx) => ({ ... }));
```

新 API 的优势：
- `title` 字段让 MCP Inspector 等 UI 工具展示更友好
- `outputSchema` 让 LLM 知道返回结构，减少幻觉
- `ctx` 参数提供 `ctx.sessionId`、`ctx.mcpReq`（sampling 等高级功能）

### 3. 多会话 HTTP 服务器模式
Streamable HTTP 生产部署需要**每会话独立 transport + server 实例**：

```
客户端 A → Express route → new Transport + new Server → 独立状态
客户端 B → Express route → new Transport + new Server → 独立状态
```

这是关键设计决策：不能用共享的 server 实例处理多个客户端。

### 4. Elicitation（确认机制）
2025-11-25 规范新增：服务器可以主动向用户请求确认，用于：
- 破坏性操作前确认（删除、重写）
- 需要用户输入的场景
- 类似 `confirm()` 但通过 MCP 协议标准化

### 5. Task API（长时间运行任务）
服务器可以注册"任务"——长时间运行的操作，客户端可以轮询状态：
- `registerToolTask` 注册任务工具
- `TaskStore` 持久化任务状态
- `InMemoryTaskMessageQueue` 任务消息队列

---

## 可运行代码示例

### 示例 1：完整的多会话 MCP Server（Streamable HTTP）

```typescript
// openclaw-mcp-server/src/index.ts
// 可直接运行的完整 MCP Server

import { randomUUID } from "node:crypto";
import { createMcpExpressApp } from "@modelcontextprotocol/express";
import { NodeStreamableHTTPServerTransport } from "@modelcontextprotocol/node";
import type { CallToolResult, ResourceLink } from "@modelcontextprotocol/server";
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/server";
import * as z from "zod/v4";
import http from "node:http";

// ─── 配置 ───────────────────────────────────────────────
const PORT = parseInt(process.env.PORT || "3000", 10);
const API_KEY = process.env.OPENCLAW_API_KEY || "dev-key-change-me";

// ─── 模拟数据层（实际项目替换为 OpenClaw API 调用）───
interface MemoryEntry {
  id: string;
  content: string;
  tags: string[];
  timestamp: number;
}

const memoryStore = new Map<string, MemoryEntry>();

function seedData() {
  const entries = [
    { id: "mem-1", content: "Agent Memory Service v0.9.8 — 241 tests, 三层存储+语义检索", tags: ["agent", "memory"], timestamp: Date.now() - 86400000 },
    { id: "mem-2", content: "MCP协议 97M+ 下载量，成为工具访问标准", tags: ["mcp", "protocol"], timestamp: Date.now() - 172800000 },
    { id: "mem-3", content: "A2A协议 — Agent间的HTTP，50+企业支持", tags: ["a2a", "protocol"], timestamp: Date.now() - 259200000 },
  ];
  for (const e of entries) memoryStore.set(e.id, e);
}
seedData();

// ─── Server 工厂函数（每会话独立实例）──────────────────
function createServer(): McpServer {
  const server = new McpServer(
    {
      name: "openclaw-mcp-server",
      version: "0.1.0",
    },
    {
      capabilities: { logging: {} },
      instructions: "OpenClaw MCP Server — 暴露记忆搜索、系统状态和项目管理能力。搜索前先用 list_memories 了解可用数据。",
    }
  );

  // ── Tool 1: 搜索记忆 ──────────────────────────────────
  server.registerTool(
    "search_memories",
    {
      title: "Search Memories",
      description: "在 Catalyst 记忆系统中搜索相关上下文。支持关键词和标签过滤。",
      inputSchema: z.object({
        query: z.string().describe("搜索关键词"),
        tags: z.array(z.string()).optional().describe("按标签过滤"),
        limit: z.number().optional().default(5).describe("最大返回数量"),
      }),
    },
    async ({ query, tags, limit = 5 }): Promise<CallToolResult> => {
      const q = query.toLowerCase();
      let results = [...memoryStore.values()].filter(
        (m) =>
          m.content.toLowerCase().includes(q) ||
          m.tags.some((t) => t.includes(q))
      );
      if (tags && tags.length > 0) {
        results = results.filter((m) =>
          tags.some((t) => m.tags.includes(t))
        );
      }
      results = results.slice(0, limit);

      if (results.length === 0) {
        return {
          content: [{ type: "text", text: `未找到与 "${query}" 相关的记忆。` }],
        };
      }

      return {
        content: results.map((r) => ({
          type: "text" as const,
          text: `[${r.id}] ${r.content}\n  标签: ${r.tags.join(", ")} | 时间: ${new Date(r.timestamp).toISOString()}`,
        })),
      };
    }
  );

  // ── Tool 2: 系统状态 ──────────────────────────────────
  server.registerTool(
    "system_status",
    {
      title: "System Status",
      description: "查询 OpenClaw 系统当前状态。返回活跃项目、定时任务、记忆统计。",
      inputSchema: z.object({
        component: z.enum(["all", "projects", "memory", "cron"]).optional().default("all").describe("查询的组件"),
      }),
    },
    async ({ component }): Promise<CallToolResult> => {
      const stats = {
        projects: "10 个核心项目（6 已完成，4 进行中）",
        memory: `${memoryStore.size} 条记忆（模拟数据）`,
        cron: "4 个定时任务活跃（deep-exploration, tech-briefing, ...）",
      };

      if (component !== "all") {
        return {
          content: [{
            type: "text",
            text: `📊 ${component}: ${stats[component as keyof typeof stats] ?? "未知组件"}`,
          }],
        };
      }

      return {
        content: [{
          type: "text",
          text: Object.entries(stats)
            .map(([k, v]) => `📊 ${k}: ${v}`)
            .join("\n"),
        }],
      };
    }
  );

  // ── Tool 3: 列出记忆 ──────────────────────────────────
  server.registerTool(
    "list_memories",
    {
      title: "List Memories",
      description: "列出所有可用记忆条目。用于了解数据概览后再精确搜索。",
      inputSchema: z.object({
        offset: z.number().optional().default(0).describe("分页偏移"),
        limit: z.number().optional().default(10).describe("每页数量"),
      }),
    },
    async ({ offset = 0, limit = 10 }): Promise<CallToolResult> => {
      const all = [...memoryStore.values()]
        .sort((a, b) => b.timestamp - a.timestamp)
        .slice(offset, offset + limit);

      return {
        content: [{
          type: "text",
          text: all.length > 0
            ? all.map((m) => `- [${m.id}] ${m.tags.join(",")}: ${m.content.slice(0, 60)}...`).join("\n")
            : "无记忆条目",
        }],
      };
    }
  );

  // ── Resource: 记忆条目 ────────────────────────────────
  server.registerResource(
    "memory-entries",
    new ResourceTemplate("memory://{id}", {
      list: async () => ({
        resources: [...memoryStore.values()].map((m) => ({
          uri: `memory://${m.id}`,
          name: m.tags.join(", "),
        })),
      }),
    }),
    {
      title: "Memory Entries",
      description: "Individual memory entries by ID",
      mimeType: "application/json",
    },
    async (uri) => {
      const id = uri.pathname?.replace("/", "") ?? "";
      const entry = memoryStore.get(id);
      return {
        contents: [
          {
            uri: uri.href,
            text: entry ? JSON.stringify(entry, null, 2) : `{"error": "Memory ${id} not found"}`,
          },
        ],
      };
    }
  );

  // ── Prompt: 研究助手 ──────────────────────────────────
  server.registerPrompt(
    "research_assistant",
    {
      title: "Research Assistant",
      description: "启动一个研究助手对话，先搜索相关记忆再回答问题",
      argsSchema: z.object({
        topic: z.string().describe("研究主题"),
      }),
    },
    async ({ topic }) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: `我需要深入研究「${topic}」。请先用 search_memories 工具搜索相关上下文，然后结合你的知识给出深度分析。`,
          },
        },
      ],
    })
  );

  return server;
}

// ─── 多会话 HTTP Server ──────────────────────────────────
const { app, closeAll } = createMcpExpressApp({
  serverFactory: createServer,  // ← 每个连接创建新 server 实例
  sessionIdGenerator: () => randomUUID(),
  // 认证中间件（可选）
  auth: {
    validateToken: async (token: string) => {
      if (token === API_KEY) return { userId: "catalyst" };
      throw new Error("Invalid API key");
    },
  },
});

const httpServer = app.listen(PORT, () => {
  console.log(`🧪 OpenClaw MCP Server`);
  console.log(`   Endpoint: http://localhost:${PORT}/mcp`);
  console.log(`   Transport: Streamable HTTP (stateful)`);
  console.log(`   Tools: search_memories, system_status, list_memories`);
  console.log(`   Resources: memory://{id}`);
  console.log(`   Prompts: research_assistant`);
});

// 优雅关闭
process.on("SIGINT", async () => {
  console.log("\n🛑 Shutting down...");
  await closeAll();
  httpServer.close();
  process.exit(0);
});
```

### 示例 2：最小化 MCP Client 测试脚本

```typescript
// test-client.ts — 无依赖测试脚本（Node.js 内置 fetch）
// 用法: npx tsx test-client.ts

const BASE_URL = "http://localhost:3000/mcp";
const headers = {
  "Content-Type": "application/json",
  Accept: "application/json, text/event-stream",
};

async function call(method: string, params: any, id: number) {
  const res = await fetch(BASE_URL, {
    method: "POST",
    headers,
    body: JSON.stringify({ jsonrpc: "2.0", id, method, params }),
  });
  // Handle SSE stream
  const text = await res.text();
  // Extract JSON from SSE if needed
  const lines = text.split("\n");
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      return JSON.parse(line.slice(6));
    }
  }
  return JSON.parse(text);
}

async function main() {
  // 1. Initialize
  const init = await call("initialize", {
    protocolVersion: "2025-11-25",
    capabilities: {},
    clientInfo: { name: "test-client", version: "1.0.0" },
  }, 1);
  console.log("✅ Initialized:", init.result?.serverInfo?.name);

  // 2. List tools
  const tools = await call("tools/list", {}, 2);
  console.log("🔧 Tools:", tools.result?.tools?.map((t: any) => t.name));

  // 3. Call search_memories
  const search = await call("tools/call", {
    name: "search_memories",
    arguments: { query: "agent", limit: 3 },
  }, 3);
  console.log("🔍 Search results:", JSON.stringify(search.result, null, 2));

  // 4. System status
  const status = await call("tools/call", {
    name: "system_status",
    arguments: { component: "all" },
  }, 4);
  console.log("📊 Status:", JSON.stringify(status.result, null, 2));
}

main().catch(console.error);
```

### 示例 3：安全中间件（生产级）

```typescript
// security.ts — Rate Limiting + Auth + Audit Log
import { Request, Response, NextFunction } from "express";

// 简单速率限制（生产环境用 redis）
const rateLimiter = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT = 100; // 每分钟请求数
const WINDOW_MS = 60_000;

export function rateLimit(req: Request, res: Response, next: NextFunction) {
  const ip = req.ip ?? "unknown";
  const now = Date.now();
  const entry = rateLimiter.get(ip);

  if (!entry || now > entry.resetAt) {
    rateLimiter.set(ip, { count: 1, resetAt: now + WINDOW_MS });
    return next();
  }

  if (++entry.count > RATE_LIMIT) {
    return res.status(429).json({ error: "Rate limit exceeded" });
  }
  next();
}

// 审计日志
export function auditLog(req: Request, res: Response, next: NextFunction) {
  const start = Date.now();
  res.on("finish", () => {
    const body = req.body;
    const method = body?.method ?? "unknown";
    console.log(`[AUDIT] ${new Date().toISOString()} | ${req.ip} | ${method} | ${res.statusCode} | ${Date.now() - start}ms`);
  });
  next();
}

// Bearer Token 认证
export function authenticate(apiKey: string) {
  return (req: Request, res: Response, next: NextFunction) => {
    const auth = req.headers.authorization;
    if (!auth?.startsWith("Bearer ")) {
      return res.status(401).json({ error: "Missing Authorization header" });
    }
    if (auth.slice(7) !== apiKey) {
      return res.status(403).json({ error: "Invalid API key" });
    }
    next();
  };
}
```

---

## 关键洞察

### 洞察 1：多会话模式是核心区别
从 v1 的"单 server + 单 transport"到 v2 的"server 工厂模式"，这是最大的架构变化。`createMcpExpressApp({ serverFactory: createServer })` 意味着**每个 HTTP 连接创建独立的 MCP server 实例**，确保状态隔离。这对 OpenClaw 的多租户场景至关重要。

### 洞察 2：Resource + Prompt 是差异化因素
大多数 MCP Server 只暴露 Tools。但 OpenClaw 有丰富的知识体系（MEMORY.md、研究笔记、项目文档），通过 Resource（`memory://{id}`）和 Prompt（`research_assistant`）暴露这些，让 OpenClaw 不只是"工具集合"，而是"知识+能力"的完整 Agent 后端。

### 洞察 3：MCP Inspector 是开发必备
`npx @modelcontextprotocol/inspector` 提供可视化调试界面，能：
- 浏览所有注册的 tools/resources/prompts
- 手动调用 tool 并查看结果
- 检查 JSON-RPC 消息流
- **无需 LLM 即可完整测试 server**（这是关键——LLM 不在测试循环中）

### 洞察 4：Zod v4 的导入路径变化
`import * as z from 'zod/v4'` 而非 `import { z } from 'zod'`。这意味着 OpenClaw MCP Server 必须用 Zod v4，不能混用 v3。如果 Agent Memory Service（Python）的 schema 需要在 TS 侧重新定义，保持一致是关键。

### 洞察 5：Elicitation 是安全网
对于 `delete_memory`、`update_config` 等破坏性操作，Elicitation 让服务器可以要求客户端（即 LLM 应用）向用户确认。这是 OpenClaw MCP Server 区别于普通 API 的关键——不是盲执行，而是"带确认的智能接口"。

---

## 与现有项目关联

| 项目 | MCP Tool 映射 | 优先级 |
|------|-------------|--------|
| Agent Memory Service | `search_memories`, `list_memories`, `store_memory` | P0 |
| OpenClaw Gateway | `system_status`, `list_agents`, `list_sessions` | P0 |
| A2A Protocol Lab | Resource: `agent-card://{id}` | P1 |
| Edge Agent Runtime | `deploy_agent`, `agent_status` | P2 |
| Cron System | `list_cron_jobs`, `trigger_cron` | P1 |

---

## 实现路线图（3 步）

### Step 1: MVP（1-2天）
- 创建 `openclaw-mcp-server` 项目
- 实现 3 个核心 tools：`search_memories`, `system_status`, `list_memories`
- Streamable HTTP transport + MCP Inspector 验证
- **验证标准**: `npx @modelcontextprotocol/inspector` 能浏览并调用所有 tools

### Step 2: 接入真实数据（2-3天）
- `search_memories` → 调用 Agent Memory Service query() API
- `system_status` → 读取 OpenClaw Gateway 状态
- 添加 Resource 支持（记忆条目 URI）
- **验证标准**: Claude Desktop / Cursor 能通过 MCP 搜索到真实记忆

### Step 3: 生产化（3-5天）
- 安全层（Bearer token、rate limiting、audit log）
- Elicitation 支持（破坏性操作确认）
- Docker 部署 + CI/CD
- stdio 双模式（本地开发用 stdio，生产用 HTTP）
- **验证标准**: 外部 MCP 客户端稳定连接 24h 无断连

---

## 参考资料

- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) — 官方 SDK + examples
- [SDK Server Guide](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/server.md) — registerTool/RegisterResource/RegisterPrompt 完整 API
- [Secure MCP Server Tutorial](https://rebeccamdeprey.com/blog/secure-mcp-server) — 安全最佳实践（auth, rate limit, audit）
- [MCP Cheat Sheet 2026](https://www.webfuse.com/mcp-cheat-sheet) — 快速参考
- [Cloudflare Remote MCP](https://blog.cloudflare.com/remote-model-context-protocol-servers-mcp/) — 远程部署模式
- 前置研究: `2026-04-18-mcp-server-typescript-streamable-http.md` — 技术选型笔记
