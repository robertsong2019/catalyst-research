# MCP Server 实现：TypeScript SDK + Streamable HTTP

> 研究日期：2026-04-18 | 主题：OpenClaw MCP Server 技术选型
> 状态：✅ 包含可运行代码示例

---

## 核心概念

### 1. Model Context Protocol (MCP) 三原语
MCP 定义三个核心原语（primitives），所有服务通过它们暴露能力：
- **Tools**：LLM 可调用的函数（查询数据、触发操作）
- **Resources**：只读数据，URI 标识（文件内容、数据库记录）
- **Prompts**：可复用的交互模板

### 2. Streamable HTTP Transport
2025-03-26 规范引入，替代旧的 SSE transport：
- 客户端 POST JSON-RPC 请求到单一 HTTP endpoint
- 服务器通过 SSE 流式返回响应
- 支持 stateful（有 sessionId）和 stateless 两种模式
- 生产环境必须使用 HTTPS/TLS

### 3. TypeScript SDK v2 架构（2026 Q1 预发布）
SDK 从单体包拆分为模块化包：
```
@modelcontextprotocol/server   — 核心服务库（McpServer, tools/resources/prompts）
@modelcontextprotocol/node     — Node.js HTTP transport
@modelcontextprotocol/express  — Express 集成
@modelcontextprotocol/hono     — Hono 集成
```
v1.x 仍在维护（bug fix + 安全更新），v2 预计 2026 Q1 stable。

### 4. Session 管理模式
- **Stateful**：`sessionIdGenerator: () => randomUUID()` — 支持会话恢复和多请求关联
- **Stateless**：`sessionIdGenerator: undefined` — 无状态，适合无状态扩展
- 有状态模式在负载均衡器后面需要 sticky session，是 2026 roadmap 重点改进方向

### 5. 协议版本演进
| 版本 | 日期 | 关键变更 |
|------|------|---------|
| 2024-11-05 | Nov 2024 | 初始版本，stdio + SSE |
| 2025-03-26 | Mar 2025 | Streamable HTTP 替代 SSE，OAuth 2.1 |
| 2025-06-18 | Jun 2025 | 移除 JSON-RPC batching，structured output，elicitation |
| 2025-11-25 | Nov 2025 | 当前版本，MCP-Protocol-Version header |

---

## 可运行代码示例

### 最小可运行 MCP Server（Streamable HTTP）

```typescript
// minimal-mcp-server.ts
// npm install @modelcontextprotocol/server @modelcontextprotocol/node @modelcontextprotocol/express express zod
import { randomUUID } from 'node:crypto';
import { createMcpExpressApp } from '@modelcontextprotocol/express';
import { NodeStreamableHTTPServerTransport } from '@modelcontextprotocol/node';
import type { CallToolResult } from '@modelcontextprotocol/server';
import { McpServer } from '@modelcontextprotocol/server';
import * as z from 'zod/v4';

const PORT = parseInt(process.env.PORT || '3000', 10);

// 创建 MCP 服务器
const server = new McpServer({
  name: 'openclaw-mcp-server',
  version: '0.1.0',
});

// Tool 1: 系统状态查询
server.registerTool(
  'system_status',
  {
    title: 'System Status',
    description: '查询系统当前状态信息',
    inputSchema: z.object({
      component: z.string().describe('组件名称，如 "memory", "agents", "cron"'),
    }),
  },
  async ({ component }): Promise<CallToolResult> => {
    const statusMap: Record<string, string> = {
      memory: '✅ Memory service v0.9.6 运行中 (188 tests)',
      agents: '✅ 6 个核心项目已完成',
      cron: '✅ 4 个定时任务活跃',
    };
    const status = statusMap[component] ?? `❓ 未知组件: ${component}`;
    return {
      content: [{ type: 'text', text: status }],
    };
  }
);

// Tool 2: 记忆搜索
server.registerTool(
  'search_memory',
  {
    title: 'Search Memory',
    description: '在 Catalyst 记忆系统中搜索相关上下文',
    inputSchema: z.object({
      query: z.string().describe('搜索查询'),
      limit: z.number().optional().default(5).describe('返回结果数量'),
    }),
  },
  async ({ query, limit }): Promise<CallToolResult> => {
    // 实际实现会调用 memory_search API
    return {
      content: [{
        type: 'text',
        text: `搜索 "${query}" (limit: ${limit}) — 需要接入实际记忆服务`,
      }],
    };
  }
);

// 创建 Express 应用并挂载 MCP
const app = createMcpExpressApp({
  transport: new NodeStreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID(), // stateful mode
  }),
  server,
});

app.listen(PORT, () => {
  console.log(`🧪 OpenClaw MCP Server running on http://localhost:${PORT}`);
  console.log(`   MCP endpoint: POST http://localhost:${PORT}/mcp`);
});
```

### 运行方式

```bash
# 初始化项目
mkdir openclaw-mcp-server && cd openclaw-mcp-server
npm init -y
npm install @modelcontextprotocol/server @modelcontextprotocol/node @modelcontextprotocol/express express zod
npm install -D typescript @types/node @types/express tsx

# 运行
npx tsx minimal-mcp-server.ts
```

### 测试（curl）

```bash
# 1. 初始化连接
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

# 2. 调用 tool
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "system_status",
      "arguments": { "component": "memory" }
    }
  }'
```

---

## 关键洞察

### 洞察 1：SDK v2 的包拆分策略值得学习
旧 SDK（`@modelcontextprotocol/sdk`）是单体包，v2 拆分为 `server`/`node`/`express`/`hono`。这意味着 OpenClaw MCP Server 应该只依赖 `server` + `node`（或 `express`），保持依赖最小化。Hono 集成对 Edge Runtime 部署友好，未来可以考虑。

### 洞察 2：Stateful vs Stateless 的取舍
当前 HEARTBEAT 中的 MCP Server 是本地使用的，用 stateful 模式（有 sessionId）即可。但如果未来需要水平扩展（多实例），需要考虑 2026 roadmap 提到的无状态会话改进。**建议初始版本用 stateful，但设计好 session store 抽象层以便迁移。**

### 洞察### 洞察 3：OpenClaw 现有架构天然适合 MCP
OpenClaw 已经有 tools/skills/cron 等概念，直接映射到 MCP 原语：
- OpenClaw tools → MCP Tools
- OpenClaw skills → MCP Resources（只读参考）
- OpenClaw cron → MCP Tools（触发定时任务）
这意味着不需要大改架构，主要是增加一个 MCP transport layer。

### 洞察 4：Zod v4 是新标准
SDK v2 使用 `zod/v4`（Zod v4 的新导入路径）。这比 v3 有更好的 TypeScript 类型和更小的 bundle。新项目应该直接用 v4。

---

## 与现有项目关联

| 现有项目 | 关联方式 |
|---------|---------|
| Agent Memory Service | MCP Tool: `search_memory`, `store_memory` |
| Edge Agent Runtime | MCP Tool: `deploy_agent`, `agent_status` |
| A2A Protocol Lab | MCP Resource: 暴露 Agent Card |
| OpenClaw 本身 | MCP Server 作为外部接口，让其他 AI 工具消费 OpenClaw 能力 |

---

## 下一步行动

1. **[本周] 创建 `openclaw-mcp-server` 项目**：基于上面的代码示例初始化，实现 2-3 个核心 tools
2. **[本周] 实现 `search_memory` tool**：接入 Agent Memory Service 的 query() API
3. **[下周] 添加认证层**：使用 Bearer token 或 OAuth 2.1（参考 SDK examples）
4. **[下周] 部署测试**：验证 Claude Desktop / Cursor 能通过 MCP 连接到 OpenClaw

---

## 参考资料

- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) — 官方 SDK，含完整 examples
- [MCP Transports Spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) — Streamable HTTP 规范
- [MCP 2026 Roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/) — transport 演进方向
- [MCP Cheat Sheet](https://www.webfuse.com/mcp-cheat-sheet) — 快速参考
