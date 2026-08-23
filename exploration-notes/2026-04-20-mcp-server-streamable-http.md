# MCP Server + Streamable HTTP 深度研究

> 日期: 2026-04-20 | 研究者: Catalyst | 方法论: autoresearch
> 关联项目: OpenClaw MCP Server (HEARTBEAT.md 高优先级)

---

## 核心概念 (5个)

### 1. Model Context Protocol (MCP)
开放标准协议，让 AI 模型以统一方式连接外部工具、数据源和服务。基于 **JSON-RPC 2.0**，2024年11月由 Anthropic 开源，2025年12月捐赠给 Linux 基金会下的 Agentic AI Foundation。2026年3月达到 **9700万月下载量**，5800+ 服务器，已成为 AI agent 工具集成的事实标准。

三大原语 (primitives)：
- **Tools** — 模型可调用的函数（类似 function calling）
- **Resources** — 模型可读取的数据源（文件、API 响应等）
- **Prompts** — 预定义的提示模板

### 2. Streamable HTTP Transport
MCP 的远程传输层，替代了早期的 HTTP+SSE。核心机制：
- 客户端通过 **HTTP POST** 发送 JSON-RPC 请求
- 服务器通过 **Server-Sent Events (SSE)** 流式返回响应
- 支持无状态模式（每个请求创建新 session）和有状态模式（保持 session）
- 支持 OAuth 2.1 认证

对比 stdio transport（本地进程间通信），Streamable HTTP 适合远程部署、多客户端并发。

### 3. SDK v2 包结构（2025年12月重构）
TypeScript SDK 从单一包拆分为模块化结构：

| 包 | 用途 |
|---|------|
| `@modelcontextprotocol/sdk` | 兼容旧版的统一入口 |
| `@modelcontextprotocol/sdk-server` | 服务端核心 |
| `@modelcontextprotocol/sdk-client` | 客户端核心 |
| `@modelcontextprotocol/sdk-core` | 共享类型和工具 |
| `@modelcontextprotocol/express` | Express 中间件 |
| `@modelcontextprotocol/hono` | Hono 中间件 |
| `@modelcontextprotocol/node` | Node.js HTTP transport |

### 4. Session 生命周期
1. **Initialize** — 客户端发送 `initialize` + 协议版本 + 能力声明
2. **Capability Exchange** — 服务器回复自己的能力
3. **Operation** — 正常的 tools/call, resources/read 等操作
4. **Shutdown** — 连接关闭

协议版本：`2025-06-18`（最新规范），`2025-11-25`（最大变更集：async tasks, elicitation, server-side agent loops）

### 5. OpenClaw MCP Server 设计要点
为 OpenClaw 构建 MCP Server 需要：
- 选择 **Streamable HTTP** 作为 transport（支持远程客户端）
- 实现 3 个 MVP tools（对应 HEARTBEAT.md 的任务）
- 使用 Express 或 Hono 作为 HTTP 框架
- 集成 OpenClaw 的现有 API

---

## 代码示例 — 可运行的 MCP Server (Streamable HTTP)

### 完整可运行示例：OpenClaw MCP Server MVP

```typescript
// openclaw-mcp-server/src/index.ts
// 依赖: npm install express @modelcontextprotocol/sdk zod

import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

// ========================================
// 1. 创建 MCP Server 实例
// ========================================
function createMcpServer() {
  const server = new McpServer({
    name: "openclaw-mcp-server",
    version: "0.1.0",
  });

  // ----------------------------------------
  // Tool 1: status — 检查 OpenClaw 状态
  // ----------------------------------------
  server.tool(
    "status",
    "Get OpenClaw gateway status and active sessions",
    {},
    async () => {
      // 实际实现会调用 OpenClaw API
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              status: "running",
              activeSessions: 3,
              uptime: "72h",
              version: "1.0.0-mvp",
            }, null, 2),
          },
        ],
      };
    }
  );

  // ----------------------------------------
  // Tool 2: search-memory — 搜索记忆
  // ----------------------------------------
  server.tool(
    "search_memory",
    "Search OpenClaw memory files for relevant context",
    {
      query: z.string().describe("Search query for memory lookup"),
      maxResults: z.number().optional().describe("Max results to return (default 5)"),
    },
    async ({ query, maxResults = 5 }) => {
      // 模拟记忆搜索结果
      const results = [
        {
          file: "memory/2026-04-19.md",
          snippet: `Found relevant note about "${query}"`,
          score: 0.92,
        },
      ].slice(0, maxResults);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(results, null, 2),
          },
        ],
      };
    }
  );

  // ----------------------------------------
  // Tool 3: run-command — 执行命令
  // ----------------------------------------
  server.tool(
    "run_command",
    "Execute a shell command via OpenClaw and return output",
    {
      command: z.string().describe("Shell command to execute"),
      timeout: z.number().optional().describe("Timeout in seconds (default 30)"),
    },
    async ({ command, timeout = 30 }) => {
      // 安全检查：阻止危险命令
      const blocked = ["rm -rf /", "drop database", "format"];
      if (blocked.some(b => command.toLowerCase().includes(b))) {
        return {
          content: [
            {
              type: "text",
              text: `⚠️ Command blocked for safety: "${command}"`,
            },
          ],
          isError: true,
        };
      }

      // 实际实现会用 exec 工具
      return {
        content: [
          {
            type: "text",
            text: `[dry-run] Would execute: "${command}" (timeout: ${timeout}s)`,
          },
        ],
      };
    }
  );

  return server;
}

// ========================================
// 2. Express + Streamable HTTP Transport
// ========================================
const app = express();
app.use(express.json());

// MCP endpoint
app.post("/mcp", async (req, res) => {
  try {
    const server = createMcpServer();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // 无状态模式
    });

    res.on("close", () => {
      transport.close();
      server.close();
    });

    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    console.error("MCP request error:", error);
    res.status(500).json({ error: "Internal server error" });
  }
});

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "openclaw-mcp-server" });
});

// ========================================
// 3. 启动服务器
// ========================================
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🧪 OpenClaw MCP Server running on http://localhost:${PORT}`);
  console.log(`   MCP endpoint: POST http://localhost:${PORT}/mcp`);
  console.log(`   Health check:  GET  http://localhost:${PORT}/health`);
});
```

### 测试脚本

```bash
#!/bin/bash
# test-mcp-server.sh — 测试 MCP Server

BASE_URL="http://localhost:3000/mcp"

echo "=== Step 1: Initialize ==="
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": { "name": "test-client", "version": "1.0.0" }
    }
  }' | jq .

echo ""
echo "=== Step 2: List Tools ==="
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }' | jq .

echo ""
echo "=== Step 3: Call status tool ==="
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "status",
      "arguments": {}
    }
  }' | jq .

echo ""
echo "=== Step 4: Search memory ==="
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "search_memory",
      "arguments": { "query": "MCP server", "maxResults": 3 }
    }
  }' | jq .
```

---

## 关键洞察 (5条)

### 洞察 1: Streamable HTTP vs SSE — 迁移正在发生
2025年3月的规范更新中，Streamable HTTP 正式替代了 HTTP+SSE 作为推荐的远程传输方式。关键区别：
- Streamable HTTP 支持纯 HTTP（无 SSE 升级），简化了代理和防火墙场景
- 向后兼容：SDK 提供了 `sseAndStreamableHttpCompatibleServer.ts` 示例，同时支持两种传输
- **对 OpenClaw 的影响**：新项目应直接使用 Streamable HTTP，无需兼容旧 SSE

### 洞察 2: SDK v2 的模块化拆分改变了依赖策略
从单一 `@modelcontextprotocol/sdk` 拆分为独立的 server/client/core 包：
- 服务端项目只需 `@modelcontextprotocol/sdk-server`（或继续用统一包）
- Express 集成用 `@modelcontextprotocol/express`，Hono 用 `@modelcontextprotocol/hono`
- **对 OpenClaw 的影响**：推荐用 Express 中间件包，减少样板代码。`createMcpExpressApp()` 可替代手动 Express 设置

### 洞察 3: 无状态 vs 有状态 Session 的取舍
Streamable HTTP 支持两种模式：
- **无状态**（`sessionIdGenerator: undefined`）：每个请求独立，无需管理 session，适合简单工具服务
- **有状态**：保持 session，支持连续对话上下文，但需要 session 存储
- **对 OpenClaw 的影响**：MVP 先用无状态模式（3个独立工具），后续如需上下文关联再引入有状态

### 洞察 4: MCP 的 2026 路线图指向企业级
MCP 基金会 2026 路线图重点：
- **企业就绪**：审计日志、速率限制、细粒度权限（大多通过 extensions 实现）
- **Async Tasks**：长时间运行的任务异步执行（已在 2025-11-25 规范中引入）
- **Elicitation**：服务器可主动向用户请求输入（表单/URL 模式）
- **对 OpenClaw 的影响**：当前 MVP 不需要这些，但架构应预留扩展点

### 洞察 5: OpenClaw MCP Server 的差异化定位
现有 MCP 服务器大多是单一工具（天气、数据库等）。OpenClaw 的独特价值：
- **Agent 编排**：暴露 OpenClaw 的多 agent 管理能力为 MCP tools
- **记忆系统**：让任何 MCP 客户端都能搜索 OpenClaw 的记忆
- **跨平台桥接**：MCP 作为统一接口，让 Claude/ChatGPT/Gemini 都能调用 OpenClaw 能力
- **竞争差异化**：不是又一个工具服务器，而是"AI agent 的操作系统接口"

---

## 下一步行动 (3个)

### Action 1: 搭建 OpenClaw MCP Server 骨架 ⚡
- 用 Express + `@modelcontextprotocol/sdk` 创建项目
- 实现 3 个 MVP tools：`status`, `search_memory`, `run_command`
- 配置 Streamable HTTP transport（无状态模式）
- 写测试脚本验证 curl 调用
- **预计工时**: 2-3小时 | **成功标准**: curl 能成功调用 3 个 tools

### Action 2: 集成 OpenClaw Gateway API
- 将 mock 实现替换为真实的 Gateway API 调用
- `status` → 调用 gateway status
- `search_memory` → 调用 memory search
- `run_command` → 调用 exec（带安全审查）
- **依赖**: Action 1 完成 | **预计工时**: 2小时

### Action 3: Docker 化 + 部署
- 创建 Dockerfile
- 配置环境变量（端口、Gateway URL、认证密钥）
- 写 docker-compose.yml（与 OpenClaw Gateway 一起编排）
- **依赖**: Action 2 完成 | **预计工时**: 1小时

---

## 参考资源

- [MCP TypeScript SDK (GitHub)](https://github.com/modelcontextprotocol/typescript-sdk) — 官方 SDK，含完整示例
- [MCP Cheat Sheet 2026](https://www.webfuse.com/mcp-cheat-sheet) — 快速参考，含所有传输方式
- [WorkOS: Everything about MCP in 2026](https://workos.com/blog/everything-your-team-needs-to-know-about-mcp-in-2026) — 生态全景
- [CloudFronts: Creating MCP Server in TypeScript](https://www.cloudfronts.com/blog/creating-an-mcp-server-using-typescript/) — Streamable HTTP 实战教程
- [MCP 2026 Roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/) — 官方路线图
- [Clerk: Build MCP Server with Express](https://clerk.com/docs/expressjs/guides/ai/mcp/build-mcp-server) — 认证集成示例
