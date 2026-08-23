# MCP Server 开发：TypeScript SDK + Streamable HTTP

> 研究日期：2026-04-30
> 主题：使用 MCP TypeScript SDK 构建远程 MCP Server（Streamable HTTP Transport）
> 关联项目：OpenClaw MCP Server（HEARTBEAT 高优先级）

---

## 核心概念

### 1. MCP 三层原语（Primitives）
- **Tools** — LLM 可调用的函数（主要交互方式），带 Zod schema 验证
- **Resources** — 静态/动态数据源，AI 读取上下文用（URI 模板匹配）
- **Prompts** — 可复用的交互模板，用户显式调用

### 2. Streamable HTTP Transport
- 基于 HTTP POST + Server-Sent Events (SSE)
- 支持有状态（sessionIdGenerator）和无状态两种模式
- 兼容负载均衡器、代理、CDN
- 替代旧版 HTTP+SSE（已废弃，仅向后兼容）

### 3. SDK v2 包结构（Monorepo 拆分）
- `@modelcontextprotocol/server` — 服务端核心（McpServer, ResourceTemplate, completable）
- `@modelcontextprotocol/client` — 客户端
- `@modelcontextprotocol/node` — Node.js transport（NodeStreamableHTTPServerTransport）
- `@modelcontextprotocol/express` — Express 集成（createMcpExpressApp）

### 4. JSON-RPC 2.0 会话生命周期
1. Client 发送 `initialize`（协议版本 + capabilities）
2. Server 响应自身 capabilities + serverInfo
3. 进入正常请求/通知交互
4. 连接断开会话结束（有状态模式）

### 5. 高级能力：Sampling & Elicitation
- **Sampling**：Tool handler 可反向请求 client 端 LLM 补全（递归 agent 工作流）
- **Elicitation**：Tool handler 可向用户请求输入（表单/确认/URL 跳转）

---

## 可运行代码示例：OpenClaw 风格 MCP Server MVP

```typescript
// openclaw-mcp-server/index.ts
// 一个完整的 MCP Server，暴露 3 个工具：查询记忆、搜索、执行命令

import { randomUUID } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/server";
import { NodeStreamableHTTPServerTransport } from "@modelcontextprotocol/node";
import { createMcpExpressApp } from "@modelcontextprotocol/express";
import { z } from "zod/v4";

// 1. 创建 MCP Server
const server = new McpServer({
  name: "openclaw-mcp-server",
  version: "0.1.0",
});

// 2. 注册 Tool: 查询记忆
server.registerTool(
  "query_memory",
  {
    description: "Search Catalyst's memory for relevant context about past work and decisions.",
    inputSchema: { query: z.string().describe("Search query"), limit: z.number().optional().default(5) },
  },
  async ({ query, limit }) => {
    // 实际实现会调用 memory_search
    const mockResults = [
      { score: 0.95, text: `Memory match for "${query}": AMS v1.0-dev has 540/540 tests passing.` },
      { score: 0.82, text: `Related: agent-task-cli at 359/359 tests, zero rollback rate for 23 days.` },
    ].slice(0, limit);
    return {
      content: mockResults.map((r) => ({ type: "text" as const, text: `[${r.score}] ${r.text}` })),
    };
  }
);

// 3. 注册 Tool: Web 搜索
server.registerTool(
  "web_search",
  {
    description: "Search the web for latest information on a topic.",
    inputSchema: { query: z.string().describe("Search query"), count: z.number().optional().default(5) },
  },
  async ({ query, count }) => {
    return {
      content: [
        { type: "text" as const, text: `Web search results for "${query}" (top ${count}):\n1. Example result from tavily...\n2. Another result...` },
      ],
    };
  }
);

// 4. 注册 Tool: 获取系统状态
server.registerTool(
  "get_status",
  {
    description: "Get current system status including active projects and test coverage.",
    inputSchema: {},
  },
  async () => {
    const status = {
      projects: {
        "ams": { tests: "540/540", phase: "v1.0-dev" },
        "agent-task-cli": { tests: "359/359" },
        "agent-role-orchestrator": { tests: "151/151" },
      },
      autoresearch: { rollbackRate: "0%", streakDays: 23 },
      timestamp: new Date().toISOString(),
    };
    return {
      content: [{ type: "text" as const, text: JSON.stringify(status, null, 2) }],
    };
  }
);

// 5. 注册 Resource: 项目清单
server.resource("projects://list", async (uri) => {
  return {
    contents: [
      {
        uri: uri.href,
        text: JSON.stringify([
          { name: "AMS", status: "active", tests: "540/540" },
          { name: "agent-task-cli", status: "active", tests: "359/359" },
          { name: "agent-role-orchestrator", status: "active", tests: "151/151" },
        ]),
      },
    ],
  };
});

// 6. 注册 Prompt: 代码审查助手
server.prompt(
  "code_review",
  { code: z.string().describe("Code to review"), language: z.string().optional().describe("Programming language") },
  async ({ code, language }) => {
    return {
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: `Review the following ${language ?? ""} code for bugs, style issues, and improvements:\n\n\`\`\`${language ?? ""}\n${code}\n\`\`\``,
          },
        },
      ],
    };
  }
);

// 7. 启动 Streamable HTTP Transport (Express)
const transport = new NodeStreamableHTTPServerTransport({
  sessionIdGenerator: () => randomUUID(), // 有状态模式
});

const app = createMcpExpressApp(transport);
const PORT = process.env.PORT ? parseInt(process.env.PORT) : 3001;

await server.connect(transport);

app.listen(PORT, () => {
  console.log(`🧪 OpenClaw MCP Server running on http://localhost:${PORT}/mcp`);
  console.log(`   Transport: Streamable HTTP (stateful)`);
  console.log(`   Tools: query_memory, web_search, get_status`);
  console.log(`   Resources: projects://list`);
  console.log(`   Prompts: code_review`);
});
```

### 运行方式

```bash
# 初始化项目
mkdir openclaw-mcp-server && cd openclaw-mcp-server
npm init -y
npm install @modelcontextprotocol/server @modelcontextprotocol/node @modelcontextprotocol/express zod
npm install -D @types/node typescript tsx

# 运行
npx tsx index.ts

# 测试（另一终端）— 发送 JSON-RPC 初始化请求
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'

# 调用工具
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_status","arguments":{}}}'
```

---

## 关键洞察

### 洞察 1：Streamable HTTP 已取代旧的 HTTP+SSE，是远程 MCP Server 的唯一推荐传输
2025年3月 MCP spec 第二版引入 Streamable HTTP，OpenAI 同日宣布支持 MCP——这是 MCP 的拐点。旧 HTTP+SSE 仅保留向后兼容。新项目必须用 Streamable HTTP。

### 洞察 2：SDK v2 拆分为 monorepo（server/client/node/express），导入路径更清晰
旧版 `@modelcontextprotocol/sdk` 的一个大包被拆分为职责明确的子包。这影响了依赖管理和 tree-shaking。OpenClaw MCP Server 应直接用 v2 新包。

### 洞察 3：McpServer.registerTool() 的 schema 用 Zod v4，同时向后兼容 v3.25+
SDK 内部 import `zod/v4`，但用户代码可用 `zod/v3` 或 `zod/v4`。注意 v4 的 API 有变化（如 `.optional().default()` 链式调用）。

### 洞察 4：有状态 vs 无状态的选择直接影响部署架构
- 有状态（`sessionIdGenerator`）→ 支持采样、通知、会话恢复，但需要 sticky session
- 无状态（`sessionIdGenerator: undefined`）→ 简单 API 风格，支持水平扩展
- OpenClaw MCP Server 建议先用有状态模式，后续生产化时考虑无状态 + 外部 session store

### 洞察 5：2026 路线图中的 Triggers/Tasks/Skills 将改变 MCP 架构
MCP 创始人透露即将推出：
- **Triggers**：MCP 版 webhook，Server 可主动通知 Client
- **Tasks**：长时间运行任务的原生支持（agentic 通信）
- **Skills over MCP**：将领域知识打包进 MCP Server
这些对 OpenClaw 的 agent orchestration 有直接价值。

---

## 下一步行动

1. **立即**：基于本示例代码创建 `lab/openclaw-mcp-server/` 项目，接入真实的 memory_search 和 web_search
2. **本周**：实现 3 个 MVP tools（query_memory, web_search, exec_command），用 MCP Inspector 验证
3. **后续**：研究 OAuth 2.1 集成（`@modelcontextprotocol/express` 内置支持），为远程部署做准备
4. **关注**：MCP spec 2026 路线图中的 Tasks 和 Triggers 原语，评估对 OpenClaw TaskFlow 的影响

---

## 参考资源

- TypeScript SDK 官方文档：https://ts.sdk.modelcontextprotocol.io/
- SDK GitHub：https://github.com/modelcontextprotocol/typescript-sdk
- MCP Spec：https://github.com/modelcontextprotocol/modelcontextprotocol
- MCP 2026 路线图演讲：https://www.youtube.com/watch?v=kAVRFYgCPg0
- WorkOS MCP 全面解析：https://workos.com/blog/everything-your-team-needs-to-know-about-mcp-in-2026
- MCP Cheat Sheet：https://www.webfuse.com/mcp-cheat-sheet
