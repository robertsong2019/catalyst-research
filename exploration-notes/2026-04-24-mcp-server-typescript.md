# MCP Server TypeScript SDK + Streamable HTTP 深度研究

> 2026-04-24 | 目标：为 OpenClaw MCP Server 实现提供技术基础

## 核心概念

### 1. MCP (Model Context Protocol) 架构
- **JSON-RPC 2.0** 协议，服务器暴露三类原语：Tools（动作）、Resources（数据）、Prompts（模板）
- 客户端通过 `initialize` 握手协商能力和协议版本
- 协议版本 `2025-06-18`（最新），SSE transport 已废弃，Streamable HTTP 为标准远程传输

### 2. Streamable HTTP Transport
- **单端点**设计（如 `/mcp`），同时处理 POST（客户端→服务器）和 GET（SSE 流）
- 服务器无需维护长连接，每个请求可创建新 server+transport 实例（stateless 模式）
- 支持多客户端连接，可选 SSE 流式响应
- 与旧 SSE transport 的区别：统一为单端点，不再需要 `/sse` + `/messages` 两个端点

### 3. TypeScript SDK 关键类
```
@modelcontextprotocol/sdk
├── server/mcp.js          → McpServer（高层 API，推荐）
├── server/streamableHttp.js → StreamableHTTPServerTransport
├── server/stdio.js        → StdioServerTransport
├── client/index.js        → Client
├── client/streamableHttp.js → StreamableHTTPClientTransport
└── types.js               → 类型定义
```

### 4. Zod Schema 验证
- 所有 tool 参数用 `zod` 定义 schema，SDK 自动校验
- 这是安全防线：防止非法参数注入

### 5. Session 管理
- Streamable HTTP 支持 session id（通过 `Mcp-Session-Id` header）
- 无状态模式：每次请求新建 server 实例，适合 serverless/容器化
- 有状态模式：复用 server 实例，支持通知和长连接

## 可运行代码示例

### 最小 MCP Server（Streamable HTTP + Express）

```typescript
// mcp-server-demo/index.ts
import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

// 创建 MCP server 实例的工厂函数（无状态模式：每次请求新建）
function createServer() {
  const server = new McpServer({
    name: "openclaw-demo",
    version: "1.0.0",
  });

  // Tool 1: echo - 回显输入
  server.tool("echo", { message: z.string().describe("要回显的消息") }, async ({ message }) => {
    return {
      content: [{ type: "text", text: `[echo] ${message}` }],
    };
  });

  // Tool 2: calculate - 简单计算器
  server.tool(
    "calculate",
    {
      expression: z.string().describe("数学表达式，如 '2+3*4'"),
    },
    async ({ expression }) => {
      // 安全评估：只允许数字和基本运算符
      if (!/^[\d+\-*/().\s]+$/.test(expression)) {
        return {
          content: [{ type: "text", text: "错误：只支持数字和 + - * / ( )" }],
          isError: true,
        };
      }
      const result = Function(`"use strict"; return (${expression})`)();
      return {
        content: [{ type: "text", text: `${expression} = ${result}` }],
      };
    }
  );

  // Tool 3: list_notes - 演示资源读取
  const notes = new Map<string, string>();
  notes.set("todo", "完成 MCP Server MVP");
  notes.set("idea", "Agent Trust Network");

  server.tool("list_notes", {}, async () => {
    const list = Array.from(notes.entries())
      .map(([k, v]) => `- **${k}**: ${v}`)
      .join("\n");
    return {
      content: [{ type: "text", text: list || "(无笔记)" }],
    };
  });

  return server;
}

// Express 应用
const app = express();
app.use(express.json());

// MCP 端点 - 处理 POST（客户端请求）和 GET（SSE 流）
app.post("/mcp", async (req, res) => {
  try {
    const server = createServer();
    const transport = new StreamableHTTPServerTransport({});
    res.on("close", () => {
      transport.close();
      server.close();
    });
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (err) {
    console.error("MCP request error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// 可选：GET 端点用于 SSE 流（服务器→客户端通知）
app.get("/mcp", async (req, res) => {
  const server = createServer();
  const transport = new StreamableHTTPServerTransport({});
  res.on("close", () => {
    transport.close();
    server.close();
  });
  await server.connect(transport);
  await transport.handleRequest(req, res);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`MCP Server running at http://localhost:${PORT}/mcp`);
});
```

### package.json
```json
{
  "name": "mcp-server-demo",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "tsx index.ts",
    "test": "curl -X POST http://localhost:3000/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1.0.0\"}}}'"
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

### 测试脚本
```bash
#!/bin/bash
# test-mcp.sh - 快速验证 MCP Server

BASE="http://localhost:3000/mcp"
HEADER="Content-Type: application/json"
ACCEPT="Accept: application/json, text/event-stream"

echo "=== 1. Initialize ==="
curl -s -X POST "$BASE" -H "$HEADER" -H "$ACCEPT" -d '{
  "jsonrpc": "2.0", "id": 1, "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "test-client", "version": "1.0.0"}
  }
}' | jq .

echo -e "\n=== 2. List Tools ==="
curl -s -X POST "$BASE" -H "$HEADER" -H "$ACCEPT" -d '{
  "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
}' | jq .

echo -e "\n=== 3. Call echo ==="
curl -s -X POST "$BASE" -H "$HEADER" -H "$ACCEPT" -d '{
  "jsonrpc": "2.0", "id": 3, "method": "tools/call",
  "params": {"name": "echo", "arguments": {"message": "Hello MCP!"}}
}' | jq .

echo -e "\n=== 4. Calculate ==="
curl -s -X POST "$BASE" -H "$HEADER" -H "$ACCEPT" -d '{
  "jsonrpc": "2.0", "id": 4, "method": "tools/call",
  "params": {"name": "calculate", "arguments": {"expression": "2+3*4"}}
}' | jq .
```

## 关键洞察

### 洞察 1: 无状态模式是生产最优解
每次 HTTP 请求创建新 `McpServer` + `StreamableHTTPServerTransport` 实例，自然支持水平扩展。不需要 session 亲和性，适合 serverless 和 K8s 部署。代价是不支持服务器主动通知——但大多数 tool 场景不需要。

### 洞察 2: Zod Schema 即 API 契约 + 安全边界
SDK 用 zod schema 自动生成 JSON Schema（用于 `tools/list` 响应），同时自动校入参。一个定义同时解决文档、校验、安全三个问题。OpenClaw MCP Server 应该充分利用这个模式。

### 洞察 `3: Streamable HTTP 替代 SSE 是正确方向
旧 SSE 需要两个端点（`/sse` 建流 + `/messages` 发请求），状态管理复杂。Streamable HTTP 单端点 + 可选 SSE 流，简单得多。SDK 已标记 SSE transport 为 deprecated。

### 洞察 4: McpServer 高层 API vs Server 底层 API
- `McpServer`（推荐）：`server.tool()`, `server.resource()`, `server.prompt()` 声明式注册
- `Server`（底层）：手动处理 `CallToolRequest` 等，更灵活但更复杂
- OpenClaw 应该用 McpServer 高层 API，除非需要自定义 capability 协商

### 洞察 5: OpenClaw 集成路径清晰
OpenClaw 已有 `mcporter` skill（MCP 客户端）。实现 MCP Server 后，OpenClaw 既是 MCP 客户端也是 MCP 服务器——可以作为 Agent Mesh 的中间层，将内部 tools 暴露给外部 MCP 客户端。

## Transport 对比

| 特性 | stdio | Streamable HTTP | SSE (deprecated) |
|------|-------|-----------------|-------------------|
| 端点 | stdin/stdout | 单个 HTTP 端点 | 两个端点 |
| 多客户端 | ❌ | ✅ | ✅ |
| 部署 | 本地 CLI | HTTP 服务器 | HTTP 服务器 |
| 流式响应 | ❌ | ✅ (可选SSE) | ✅ |
| 适合场景 | 本地工具 | 生产远程服务 | 已废弃 |

## 与现有项目关联

- **OpenClaw mcporter**：已是 MCP 客户端，新 MCP Server 补全双向能力
- **Agent Memory Service**：可作为 MCP Resource 暴露，让外部 agent 通过标准协议查询记忆
- **A2A Agent Trust**：MCP tools 可暴露 trust 查询和验证能力
- **HEARTBEAT.md**：本周最高优先级任务，研究已完成，可进入实现阶段

## 下一步行动

1. **[实现]** 用以上模板创建 `openclaw-mcp-server` 项目，3 tools MVP：
   - `memory_search` — 搜索 Agent Memory
   - `tool_list` — 列出可用 OpenClaw tools
   - `execute_task` — 委派任务给 sub-agent
2. **[验证]** 用 mcporter 客户端或 curl 测试脚本验证所有 3 个 tools
3. **[部署]** Docker 化 + 环境变量配置，准备接入 OpenClaw gateway

## 参考资料

- [MCP Spec - Transports](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [TypeScript SDK Complete Guide](https://blog.agentailor.com/posts/mcp-typescript-sdk-complete-guide)
- [MCP TS Starter](https://github.com/madhukarkumar/mcp-ts-starter)
- [Cloudfronts Tutorial](https://www.cloudfronts.com/blog/creating-an-mcp-server-using-typescript/)
- [heise MCP TypeScript Example](https://www.heise.de/en/background/Model-Context-Protocol-Application-example-in-TypeScript-10553218.html)
