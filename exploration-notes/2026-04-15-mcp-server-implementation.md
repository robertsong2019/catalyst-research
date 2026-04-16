# MCP Server 实现研究笔记

> 日期: 2026-04-15
> 主题: Model Context Protocol (MCP) Server 实现模式
> 关联项目: OpenClaw MCP Server（HEARTBEAT 高优先级）

---

## 核心概念

1. **Transport 层双模式** — STDIO（本地/CLI）vs Streamable HTTP（远程/多客户端）。Streamable HTTP 比 SSE 节省 >50% CPU，是 2025-06-18 规范后的推荐方案。OpenClaw 场景需要同时支持两种：本地开发用 STDIO，远程暴露用 HTTP。

2. **Tool Schema 规范** — 每个 tool 必须有 `name` + `description` + `inputSchema`（JSON-Schema）。TypeScript 用 zod、Python 用 pydantic 做验证。2025-06-18 新增 **structured output**，不再只是纯文本。

3. **无状态架构（2025-11-25 规范更新）** — 每个 JSON-RPC 请求自带所有上下文，无需持久化握手状态。这让 serverless 部署成为可能，也意味着 OpenClaw 可以把 MCP Server 部署为 Vercel/AWS Lambda 函数。

4. **OAuth 2.1 安全模型** — 必须暴露 `.well-known/oauth-protected-resource`，支持 token 验证。对 OpenClaw 而言，已有 mcporter 做客户端，需要补充服务端 auth。

5. **MCP Inspector** — 官方调试工具（`npx @modelcontextprotocol/inspector`），可交互式测试 tool 发现、schema 验证、错误处理。CI 中可用 CLI 模式做契约测试。

---

## 可运行代码示例：OpenClaw 风格的 MCP Server 骨架

以下是一个将 OpenClaw 工具暴露为 MCP 接口的 Node.js 服务器骨架，可直接运行：

```ts
// openclaw-mcp-server.ts
// 安装: npm install @modelcontextprotocol/sdk zod
// 运行: npx tsx openclaw-mcp-server.ts

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "openclaw-mcp",
  version: "0.1.0",
});

// Tool 1: Web Search — 暴露 OpenClaw 的 web_search 能力
server.tool(
  "web_search",
  "Search the web using OpenClaw's built-in search",
  {
    query: z.string().describe("Search query string"),
    count: z.number().optional().default(5).describe("Number of results (1-10)"),
  },
  async ({ query, count }) => {
    // 实际实现中调用 OpenClaw gateway API
    const results = await fetch(
      `http://localhost:3000/api/tools/web_search?query=${encodeURIComponent(query)}&count=${count}`
    ).then(r => r.json());

    return {
      content: [{
        type: "text",
        text: JSON.stringify(results, null, 2),
      }],
    };
  }
);

// Tool 2: Memory Search — 暴露 OpenClaw 的记忆搜索
server.tool(
  "memory_search",
  "Search Catalyst's memory files for context about prior work",
  {
    query: z.string().describe("What to search for in memory"),
    maxResults: z.number().optional().default(5),
  },
  async ({ query, maxResults }) => {
    const results = await fetch(
      `http://localhost:3000/api/tools/memory_search`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, maxResults }),
      }
    ).then(r => r.json());

    return {
      content: [{
        type: "text",
        text: JSON.stringify(results, null, 2),
      }],
    };
  }
);

// Tool 3: Execute Shell Command
server.tool(
  "run_command",
  "Execute a shell command on the OpenClaw host",
  {
    command: z.string().describe("Shell command to execute"),
    timeout: z.number().optional().default(30).describe("Timeout in seconds"),
  },
  async ({ command, timeout }) => {
    // 实际实现中需要严格的安全校验
    const result = await fetch(`http://localhost:3000/api/tools/exec`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command, timeout }),
    }).then(r => r.json());

    return {
      content: [{
        type: "text" as const,
        text: `Exit code: ${result.exitCode}\n${result.stdout}\n${result.stderr}`,
      }],
    };
  }
);

// 启动
const transport = new StdioServerTransport();
await server.connect(transport);
console.error("OpenClaw MCP Server running on STDIO");
```

**快速验证方式：**
```bash
# 终端1: 启动 server（模拟模式，不需要真正的 gateway）
echo '{}' | npx tsx openclaw-mcp-server.ts

# 终端2: 用 MCP Inspector 调试
npx @modelcontextprotocol/inspector npx tsx openclaw-mcp-server.ts
```

---

## 关键洞察

1. **OpenClaw 已有 mcporter 做 MCP 客户端，缺的是服务端**。实现路径清晰：把 feishu_doc/web_search/memory_search/exec 等工具包装为 MCP server tool，让 Claude Desktop/Cursor 等第三方客户端能直接调用 OpenClaw 的能力。这比重新实现所有工具高效得多。

2. **Streamable HTTP 是远程部署的正确选择**。OpenClaw gateway 本身就是 HTTP 服务，在同一个进程中添加 `/api/mcp` 路由是最自然的集成方式，无需额外部署。session affinity 通过 `Mcp-Session-Id` header 处理。

3. **安全是最大挑战**。MCP 工具执行 shell 命令、读写文件，暴露为远程接口后必须有 OAuth 2.1 + RBAC。建议分阶段：先实现 STDIO 模式（本地信任），再添加 HTTP transport + OAuth。

4. **Structured Output (2025-06-18) 改变了 tool 设计**。不再只是返回文本，可以返回 schema-defined 的结构化数据，让 LLM 更容易解析。OpenClaw 的工具返回值应该重构为符合 MCP structured output 的格式。

5. **现有的 lab/mcp-client-explorer 代码可以复用**。HEARTBEAT 中提到基于它来构建，说明已有探索代码。建议先审计现有代码，看哪些 transport/auth 组件可直接复用。

---

## 下一步行动

1. **[本周]** 审计 `lab/mcp-client-explorer` 现有代码，梳理可复用组件
2. **[本周]** 实现最小可行的 STDIO MCP Server，暴露 3 个核心工具（web_search, memory_search, exec）
3. **[本周]** 用 MCP Inspector 验证 tool 发现和调用流程
4. **[下周]** 添加 Streamable HTTP transport，集成到 OpenClaw gateway 的 `/api/mcp` 路由
5. **[下周]** 添加 OAuth 2.1 验证，实现 RBAC 工具权限控制

---

## 参考资源

- [MCP Specification (2025-06-18)](https://modelcontextprotocol.io/specification/draft/schema)
- [TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
- [Vercel MCP 部署指南](https://vercel.com/docs/mcp/deploy-mcp-servers-to-vercel)
- [Streamable HTTP vs STDIO 性能对比](https://builder.aws.com/content/35A0IphCeLvYzly9Sw40G1dVNzc/mcp-transport-mechanisms-stdio-vs-streamable-http)
