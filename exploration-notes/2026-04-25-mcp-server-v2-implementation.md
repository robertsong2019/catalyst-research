# MCP Server v2 SDK 实现指南 — OpenClaw MCP Server MVP

> 研究日期: 2026-04-25
> 状态: ✅ 完成
> 关联: HEARTBEAT 高优先级 — 实现 OpenClaw MCP Server
> 前序研究: 2026-04-17-mcp-server-typescript.md

---

## 核心概念（5个）

### 1. SDK v2 包架构（2026 Q1 稳定版）
```
@modelcontextprotocol/server   → McpServer + ResourceTemplate + StdioServerTransport
@modelcontextprotocol/client   → Client 构建库
@modelcontextprotocol/node     → NodeStreamableHTTPServerTransport
@modelcontextprotocol/express  → createMcpExpressApp（快速集成 Express）
@modelcontextprotocol/hono     → Hono 适配器
```
**关键变化**: v2 使用 `registerTool()` 替代 v1 的 `server.tool()`，Schema 用 Standard Schema（Zod v4 / Valibot / ArkType）。

### 2. Streamable HTTP Transport（生产必选）
```typescript
import { NodeStreamableHTTPServerTransport } from '@modelcontextprotocol/node';
import { createMcpExpressApp } from '@modelcontextprotocol/express';

// 有状态模式（支持通知、sampling）
const transport = new NodeStreamableHTTPServerTransport({
  sessionIdGenerator: () => randomUUID()
});

// 无状态模式（简单 API，水平扩展友好）
const transport = new NodeStreamableHTTPServerTransport({
  sessionIdGenerator: undefined
});
```

### 3. Tool 注册模式（Zod v4 Schema）
```typescript
import * as z from 'zod/v4';

server.registerTool(
  'tool-name',
  {
    title: 'Display Name',
    description: 'What this tool does',
    inputSchema: z.object({ param: z.string() }),
    outputSchema: z.object({ result: z.string() }), // 可选
    annotations: { readOnlyHint: true }              // 可选
  },
  async ({ param }) => ({
    content: [{ type: 'text', text: `Result: ${param}` }],
    structuredContent: { result: param }  // 配合 outputSchema
  })
);
```

### 4. Context 参数（通知 + 服务器发起请求）
```typescript
async ({ name }, ctx) => {
  // 发送日志通知给客户端
  await ctx.mcpReq.log('info', `Processing ${name}`);
  
  // 服务器发起请求（如 elicitation）
  const result = await ctx.mcpReq.send({
    method: 'elicitation/create',
    params: { mode: 'form', message: '...', requestedSchema: {...} }
  });
  
  return { content: [{ type: 'text', text: 'done' }] };
}
```

### 5. 部署模式：有状态 vs 无状态 vs 持久化
| 模式 | sessionIdGenerator | 适用场景 | 扩展性 |
|------|-------------------|---------|--------|
| 无状态 | `undefined` | 纯工具调用 | 🟢 任意 LB |
| 有状态（内存） | `() => randomUUID()` | 通知/sampling | 🟡 粘性会话 |
| 有状态（持久化） | `() => randomUUID()` + `eventStore` | 生产环境 | 🟢 任意 LB |

---

## 可运行代码：OpenClaw MCP Server MVP（3 Tools）

> 依赖: `@modelcontextprotocol/server`, `@modelcontextprotocol/node`, `@modelcontextprotocol/express`, `zod`, `express`, `cors`

```typescript
// openclaw-mcp-server/src/index.ts
import { randomUUID } from 'node:crypto';
import { createMcpExpressApp } from '@modelcontextprotocol/express';
import { NodeStreamableHTTPServerTransport } from '@modelcontextprotocol/node';
import type { CallToolResult } from '@modelcontextprotocol/server';
import { McpServer } from '@modelcontextprotocol/server';
import cors from 'cors';
import type { Request, Response } from 'express';
import * as z from 'zod/v4';

const PORT = parseInt(process.env.PORT || '3000', 10);

// ===== Tool 1: read_file — 读取工作区文件 =====
// 模拟 OpenClaw 的文件读取能力

// ===== Tool 2: run_command — 执行 shell 命令 =====
// 模拟 OpenClaw 的 exec 能力

// ===== Tool 3: search_memory — 搜索记忆 =====
// 模拟 OpenClaw 的 memory_search 能力

function createServer(): McpServer {
  const server = new McpServer(
    { name: 'openclaw-mcp-server', version: '0.1.0' },
    {
      instructions: [
        'OpenClaw MCP Server — 暴露 Catalyst 的核心能力给 MCP 客户端。',
        'Tool 1 (read_file): 读取工作区文件内容',
        'Tool 2 (run_command): 执行 shell 命令并返回输出',
        'Tool 3 (search_memory): 语义搜索 MEMORY.md 和 memory/ 目录',
      ].join('\n'),
    }
  );

  // --- Tool 1: read_file ---
  server.registerTool(
    'read_file',
    {
      title: 'Read File',
      description: 'Read file contents from the OpenClaw workspace. Supports text files with line range.',
      inputSchema: z.object({
        path: z.string().describe('File path relative to workspace root'),
        offset: z.number().optional().describe('Start line (1-indexed)'),
        limit: z.number().optional().describe('Max lines to read'),
      }),
      annotations: { readOnlyHint: true },
    },
    async ({ path, offset, limit }): Promise<CallToolResult> => {
      try {
        const fs = await import('node:fs/promises');
        const fullPath = `${process.env.WORKSPACE_ROOT || '/root/.openclaw/workspace'}/${path}`;
        const content = await fs.readFile(fullPath, 'utf-8');
        const lines = content.split('\n');
        const start = (offset ?? 1) - 1;
        const end = limit ? start + limit : lines.length;
        const sliced = lines.slice(start, end).join('\n');
        return {
          content: [{ type: 'text', text: sliced }],
          structuredContent: {
            path,
            totalLines: lines.length,
            returnedLines: Math.min(end - start, lines.length - start),
          },
        };
      } catch (err: any) {
        return {
          content: [{ type: 'text', text: `Error reading file: ${err.message}` }],
          isError: true,
        };
      }
    }
  );

  // --- Tool 2: run_command ---
  server.registerTool(
    'run_command',
    {
      title: 'Run Command',
      description: 'Execute a shell command in the workspace and return stdout/stderr.',
      inputSchema: z.object({
        command: z.string().describe('Shell command to execute'),
        timeout: z.number().optional().describe('Timeout in seconds (default 30)'),
      }),
      annotations: { readOnlyHint: false, destructiveHint: false },
    },
    async ({ command, timeout }): Promise<CallToolResult> => {
      try {
        const { execFile } = await import('node:child_process');
        const result = await new Promise<{ stdout: string; stderr: string; code: number }>(
          (resolve, reject) => {
            const proc = execFile(
              'bash',
              ['-c', command],
              {
                cwd: process.env.WORKSPACE_ROOT || '/root/.openclaw/workspace',
                timeout: (timeout ?? 30) * 1000,
                maxBuffer: 1024 * 1024,
              },
              (err, stdout, stderr) => {
                resolve({
                  stdout: stdout?.toString() || '',
                  stderr: stderr?.toString() || '',
                  code: err ? (err as any).code ?? 1 : 0,
                });
              }
            );
          }
        );
        const output = [
          result.stdout && `STDOUT:\n${result.stdout}`,
          result.stderr && `STDERR:\n${result.stderr}`,
          result.code !== 0 && `Exit code: ${result.code}`,
        ]
          .filter(Boolean)
          .join('\n\n');
        return {
          content: [{ type: 'text', text: output || 'Command completed successfully (no output)' }],
          structuredContent: { exitCode: result.code },
        };
      } catch (err: any) {
        return {
          content: [{ type: 'text', text: `Error: ${err.message}` }],
          isError: true,
        };
      }
    }
  );

  // --- Tool 3: search_memory ---
  server.registerTool(
    'search_memory',
    {
      title: 'Search Memory',
      description: 'Semantic search across MEMORY.md and memory/ directory for context recall.',
      inputSchema: z.object({
        query: z.string().describe('Search query'),
        maxResults: z.number().optional().describe('Max results (default 5)'),
      }),
      annotations: { readOnlyHint: true },
    },
    async ({ query, maxResults }): Promise<CallToolResult> => {
      try {
        const fs = await import('node:fs/promises');
        const path = await import('node:path');
        const wsRoot = process.env.WORKSPACE_ROOT || '/root/.openclaw/workspace';
        const memDir = path.join(wsRoot, 'memory');

        // Simple keyword search (production: use embedding search via AMS)
        const results: { file: string; snippet: string; score: number }[] = [];
        const keywords = query.toLowerCase().split(/\s+/);

        const files = ['MEMORY.md', ...(await fs.readdir(memDir)).map(f => `memory/${f}`)];
        for (const file of files.slice(0, 20)) {
          try {
            const content = await fs.readFile(path.join(wsRoot, file), 'utf-8');
            const lower = content.toLowerCase();
            const score = keywords.reduce(
              (s, kw) => s + (lower.includes(kw) ? 1 : 0), 0
            );
            if (score > 0) {
              // Extract first matching line as snippet
              const lines = content.split('\n');
              const matchLine = lines.find(l => keywords.some(kw => l.toLowerCase().includes(kw)));
              results.push({ file, snippet: (matchLine || lines[0]).slice(0, 200), score });
            }
          } catch {}
        }

        results.sort((a, b) => b.score - a.score);
        const top = results.slice(0, maxResults ?? 5);

        if (top.length === 0) {
          return { content: [{ type: 'text', text: 'No matching memories found.' }] };
        }

        return {
          content: [
            {
              type: 'text',
              text: top.map((r, i) => `## ${i + 1}. ${r.file} (score: ${r.score})\n${r.snippet}`).join('\n\n'),
            },
          ],
          structuredContent: { results: top, total: results.length },
        };
      } catch (err: any) {
        return {
          content: [{ type: 'text', text: `Error: ${err.message}` }],
          isError: true,
        };
      }
    }
  );

  return server;
}

// ===== Express + Streamable HTTP 启动 =====
async function main() {
  const server = createServer();
  const transport = new NodeStreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID(),
  });

  await server.connect(transport);

  const app = createMcpExpressApp(transport);
  app.use(cors());

  const httpServer = app.listen(PORT, () => {
    console.log(`🧪 OpenClaw MCP Server running on http://localhost:${PORT}/mcp`);
    console.log(`   Transport: Streamable HTTP (stateful)`);
    console.log(`   Tools: read_file, run_command, search_memory`);
  });

  // Graceful shutdown
  process.on('SIGINT', async () => {
    console.log('\nShutting down...');
    httpServer.close();
    process.exit(0);
  });
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
```

### package.json
```json
{
  "name": "openclaw-mcp-server",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "start": "tsx src/index.ts",
    "dev": "tsx watch src/index.ts"
  },
  "dependencies": {
    "@modelcontextprotocol/server": "^2.0.0",
    "@modelcontextprotocol/node": "^2.0.0",
    "@modelcontextprotocol/express": "^2.0.0",
    "express": "^5.0.0",
    "cors": "^2.8.5",
    "zod": "^3.25.0"
  },
  "devDependencies": {
    "tsx": "^4.19.0",
    "@types/express": "^5.0.0",
    "@types/cors": "^2.8.0"
  }
}
```

### 测试 MCP Server（用 curl）
```bash
# 启动服务
PORT=3000 WORKSPACE_ROOT=/root/.openclaw/workspace npx tsx src/index.ts

# 列出 tools
curl -X POST http://localhost:3000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'

# 调用 read_file
curl -X POST http://localhost:3000/mcp \
  -H 'Content-Type: application/json' \
  -H 'MCP-Session-Id: <from-init-response>' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"MEMORY.md","limit":10}}}'
```

---

## 关键洞察（4条）

### 1. v2 的 `registerTool` 是最大的 API 变化
v1 用 `server.tool(name, schema, handler)` — v2 用 `server.registerTool(name, {inputSchema, ...}, handler)`。Schema 直接用 Zod v4 对象而非手动 JSON Schema。这意味着更少的样板代码和类型安全。

### 2. `createMcpExpressApp` 是 Express 集成的捷径
不需要手动处理 `/mcp` 路由和 SSE 流——`createMcpExpressApp(transport)` 一行搞定。还可以叠加 CORS、auth 中间件。Hono 也有等价适配器。

### 3. `structuredContent` 是新特性，值得关注
Tool 返回值现在支持 `structuredContent`（配合 `outputSchema`），让客户端可以拿到结构化数据而非纯文本。OpenClaw 的工具返回值天然是结构化的，这个特性完美契合。

### 4. 无状态模式是 MVP 的最佳起点
OpenClaw MCP Server 初期不需要通知/sampling，用 `sessionIdGenerator: undefined` 即可。省去会话管理复杂度，后续需要时再升级。如果需要水平扩展，加 `eventStore` 接数据库。

---

## 下一步行动（3个）

1. **[本周] 创建 `openclaw-mcp-server` 项目** — 用上面的代码初始化项目，`npm install`，跑通 `read_file` tool
2. **[本周] 接入真实 AMS embedding search** — `search_memory` 从关键词搜索升级为调用 Agent Memory Service 的 `search()` API
3. **[下周] 添加 auth 中间件** — 用 `requireBearerAuth` 或 API key 验证，保护 MCP Server 不被未授权访问

---

## 与现有项目关联

| 项目 | 关联 |
|------|------|
| Agent Memory Service | `search_memory` tool 直接调用 AMS API |
| agent-task-cli | `run_command` 可集成 task 管理 |
| OpenClaw Gateway | MCP Server 可作为 Gateway 的一个 plugin 暴露 |
| HEARTBEAT.md | 本周高优先级 ✓ |
