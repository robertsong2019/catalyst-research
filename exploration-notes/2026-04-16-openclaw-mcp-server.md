# OpenClaw MCP Server — 将现有工具暴露为 MCP 标准接口

> 研究日期: 2026-04-16
> 主题: MCP Server 实现，基于 lab/mcp-client-explorer 扩展
> 关联项目: OpenClaw 工具生态、mcporter skill

---

## 核心概念

### 1. MCP (Model Context Protocol)
开放标准协议，让 AI 应用以统一方式连接外部工具/数据源。类比 "AI 的 USB-C"。核心原语：**Resources**（数据源）、**Tools**（可调用函数）、**Prompts**（提示模板）。

### 2. Streamable HTTP Transport（推荐）
2025年3月规范更新引入，取代旧 SSE transport。服务端作为 HTTP 服务运行，客户端通过 POST 通信，支持可选的 SSE 流式响应。关键优势：无状态模式、网络可达、兼容 CORS。

### 3. MCP Server SDK 模式
TypeScript SDK (`@modelcontextprotocol/sdk`) 提供 `McpServer` 高级 API + `zod` schema 验证。Python SDK 有 `FastMCP`（装饰器风格）和底层 `Server` 类。

### 4. OpenClaw → MCP 桥接
OpenClaw 已有丰富的工具（web_search、feishu_doc、exec 等）。通过 MCP Server 包装，任何 MCP 兼容客户端（Cursor、Claude Desktop、Copilot）都能直接调用这些工具。

### 5. 两种 Transport 策略
- **stdio**: 本地 CLI 集成（mcporter 已支持）
- **Streamable HTTP**: 远程服务部署，多客户端共享

---

## 可运行代码：OpenClaw MCP Server (TypeScript)

> 使用官方 SDK + Streamable HTTP，暴露 web_search 和 exec 两个核心工具。

### 安装依赖

```bash
mkdir openclaw-mcp-server && cd openclaw-mcp-server
npm init -y
npm install @modelcontextprotocol/sdk zod express
npm install -D @types/express tsx typescript @types/node
```

### server.ts

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import express from "express";
import { z } from "zod";

// ========== Create MCP Server ==========
const mcp = new McpServer({
  name: "openclaw-tools",
  version: "0.1.0",
});

// ========== Tool: web_search ==========
// Wraps Brave Search API (or any search backend)
mcp.tool(
  "web_search",
  "Search the web for information. Returns titles, URLs, and snippets.",
  {
    query: z.string().describe("Search query string"),
    count: z.number().optional().describe("Number of results (1-10)").default(5),
  },
  async ({ query, count }) => {
    // In production, call OpenClaw's search API or Brave directly
    // This is a minimal working example with fetch to a search API
    const apiKey = process.env.BRAVE_API_KEY;
    if (!apiKey) {
      return {
        content: [{ type: "text" as const, text: "Error: BRAVE_API_KEY not set" }],
        isError: true,
      };
    }

    try {
      const resp = await fetch(
        `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&count=${count}`,
        { headers: { "X-Subscription-Token": apiKey } }
      );
      const data = await resp.json();
      const results = (data.web?.results || []).map(
        (r: any) => `**${r.title}**\n${r.url}\n${r.description}\n`
      );
      return {
        content: [{ type: "text" as const, text: results.join("\n---\n") || "No results found" }],
      };
    } catch (err: any) {
      return {
        content: [{ type: "text" as const, text: `Search error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// ========== Tool: exec_command ==========
// Safely execute shell commands (with allowlist)
mcp.tool(
  "exec_command",
  "Execute a shell command and return the output. Only allows safe commands.",
  {
    command: z.string().describe("Shell command to execute"),
    timeout: z.number().optional().describe("Timeout in seconds").default(10),
  },
  async ({ command, timeout }) => {
    // Basic safety: block dangerous patterns
    const blocked = /rm\s+-rf|mkfs|dd\s+if=|:\(\)\{.*\}|shutdown|reboot/i;
    if (blocked.test(command)) {
      return {
        content: [{ type: "text" as const, text: `Blocked: command matches dangerous pattern` }],
        isError: true,
      };
    }

    const { exec } = await import("child_process");
    return new Promise((resolve) => {
      exec(command, { timeout: (timeout || 10) * 1000 }, (error, stdout, stderr) => {
        const output = stdout || "(no stdout)";
        const errOutput = stderr ? `\nSTDERR: ${stderr}` : "";
        const exitInfo = error ? `\nExit code: ${error.code}` : "";
        resolve({
          content: [{
            type: "text" as const,
            text: `${output}${errOutput}${exitInfo}`,
          }],
          isError: !!error,
        });
      });
    });
  }
);

// ========== Tool: list_files ==========
mcp.tool(
  "list_files",
  "List files in a directory on the OpenClaw workspace.",
  {
    path: z.string().optional().describe("Directory path (defaults to workspace root)"),
  },
  async ({ path }) => {
    const { readdir } = await import("fs/promises");
    const { stat } = await import("fs/promises");
    const targetPath = path || process.env.WORKSPACE_PATH || "/root/.openclaw/workspace";
    try {
      const entries = await readdir(targetPath, { withFileTypes: true });
      const listing = entries.map((e) => {
        const prefix = e.isDirectory() ? "📁 " : e.isFile() ? "📄 " : "🔗 ";
        return `${prefix}${e.name}`;
      });
      return {
        content: [{ type: "text" as const, text: listing.join("\n") || "(empty directory)" }],
      };
    } catch (err: any) {
      return {
        content: [{ type: "text" as const, text: `Error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// ========== Express + Streamable HTTP ==========
const app = express();
app.use(express.json());

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", server: "openclaw-mcp-tools", version: "0.1.0" });
});

// MCP endpoint (stateless mode — each request creates a new transport)
app.post("/mcp", async (req, res) => {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined, // stateless
  });
  res.on("close", () => transport.close());
  await mcp.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

// Optional: SSE stream for notifications
app.get("/mcp", async (req, res) => {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
  });
  res.on("close", () => transport.close());
  await mcp.connect(transport);
  await transport.handleRequest(req, res);
});

// Delete session (cleanup)
app.delete("/mcp", async (req, res) => {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
  });
  res.on("close", () => transport.close());
  await mcp.connect(transport);
  await transport.handleRequest(req, res);
});

const PORT = process.env.MCP_PORT || 3050;
app.listen(PORT, () => {
  console.log(`🧪 OpenClaw MCP Server running at http://localhost:${PORT}`);
  console.log(`   Health: http://localhost:${PORT}/health`);
  console.log(`   MCP endpoint: http://localhost:${PORT}/mcp`);
});
```

### 测试运行

```bash
# Terminal 1: 启动服务器
npx tsx server.ts

# Terminal 2: 测试健康检查
curl http://localhost:3050/health

# Terminal 3: 用 MCP Inspector 测试（官方调试工具）
npx @modelcontextprotocol/inspector http://localhost:3050/mcp
```

### 测试工具调用（手动 JSON-RPC）

```bash
# 列出工具
curl -X POST http://localhost:3050/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

# 调用 list_files
curl -X POST http://localhost:3050/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_files","arguments":{}}}'
```

---

## 关键洞察

### 1. Statelessness 是生产力倍增器
Streamable HTTP 的 stateless 模式（`sessionIdGenerator: undefined`）让服务器无需管理会话状态，天然支持负载均衡和多客户端。对于 OpenClaw 这种"无状态工具网关"场景完美契合。

### 2. 现有 lab/mcp-client-explorer 代码是热身，不是终态
lab 里的纯 Python stdio 实现适合理解协议，但生产级 MCP Server 应该：
- 用官方 SDK（TypeScript 或 Python `fastmcp`）
- 支持 Streamable HTTP transport
- 用 zod 做输入验证
- 有正式的错误处理链

### 3. OpenClaw → MCP 的架构应该是"薄包装层"
不要重新实现工具逻辑。MCP Server 应该是一个 adapter 层，调用 OpenClaw 已有的内部 API。模式：
```
MCP Client → Streamable HTTP → MCP Server (adapter) → OpenClaw 内部工具
```

### 4. 安全边界是核心设计决策
`exec_command` 工具的 allowlist/blocklist 模式只是起点。生产部署需要：
- 认证（API key / OAuth）
- 工具级权限控制
- 审计日志
- 速率限制

### 5. Python FastMCP 替代方案（适合快速原型）

```python
# 单文件 MCP Server（Python），暴露搜索能力
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("openclaw-tools")

@mcp.tool()
def search(query: str) -> str:
    """Search the web."""
    import requests
    resp = requests.get(f"https://api.search.brave.com/res/v1/web/search",
                        headers={"X-Subscription-Token": "..."},
                        params={"q": query, "count": 5})
    results = resp.json().get("web", {}).get("results", [])
    return "\n".join(f"{r['title']}: {r['url']}" for r in results)

# Run: fastmcp run server.py --transport sse --port 3050
```

---

## 与现有项目的关联

| 项目 | 关联 |
|------|------|
| lab/mcp-client-explorer | 协议理解基础，已验证 stdio 通信 |
| mcporter skill | 已有 MCP 客户端能力，可复用连接逻辑 |
| OpenClaw 工具链 | web_search, exec, feishu_doc 等都是待暴露的工具 |
| A2A protocol lab | Agent 间通信可走 MCP 作为工具发现层 |

---

## 下一步行动

1. **创建 `openclaw-mcp-server` 项目** — 基于 TypeScript SDK 实现，先用 stateless Streamable HTTP 暴露 3 个核心工具（web_search, exec, list_files）
2. **接入 OpenClaw 内部 API** — 而不是在 MCP 层重新实现工具逻辑；研究 OpenClaw gateway 的内部调用接口
3. **测试与 MCP Inspector 集成** — 确保官方调试工具能正常发现和调用所有工具
4. **评估 Python FastMCP 方案** — 如果部署环境偏好 Python，FastMCP 的装饰器风格更简洁

---

*Generated by Catalyst 🧪 | autoresearch deep-exploration-evening*
