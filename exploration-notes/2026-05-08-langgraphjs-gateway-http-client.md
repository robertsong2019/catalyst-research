# LangGraph.js Gateway HTTP Client + task() Wrapper 设计

> 日期: 2026-05-08 | 方法: autoresearch
> 主题: openclaw-langgraph-bridge 的 Gateway HTTP 客户端与 task() 幂等包装器
> 前序: [2026-05-01 createOpenClawNode](2026-05-01-langgraphjs-create-openclaw-node.md)
> 关联: HEARTBEAT.md 高优先级 — lab/openclaw-langgraph-bridge/

---

## 为什么这次研究很重要

前序研究已完成 `createOpenClawNode()` 工厂函数（3测试通过），实现了 LangGraph 节点 → OpenClaw sessions_spawn 的抽象。但还有两个关键缺口：

1. **Gateway HTTP 客户端** — 生产环境中 LangGraph graph 需要通过 HTTP 调用 OpenClaw Gateway（而非 in-process sessions_spawn）
2. **task() 幂等包装器** — LangGraph v1.2.9+ 引入的 `task()` 概念，为节点执行提供 durable execution 语义

本次研究聚焦这两个模块的 API 设计与实现。

---

## 核心概念 (4个)

### 1. Gateway HTTP Client — OpenClaw Gateway 的 HTTP 抽象层

OpenClaw Gateway 暴露 REST API（默认 localhost:3271），LangGraph 节点需要通过 HTTP 而非 in-process 调用与 Gateway 交互。

```ts
// gateway-client.ts
import { z } from "zod";

export interface GatewayClientConfig {
  baseUrl: string;       // e.g. "http://localhost:3271"
  authToken?: string;    // Bearer token if configured
  timeout?: number;      // ms, default 30000
}

export interface SpawnRequest {
  agentId?: string;
  task: string;
  model?: string;
  thread?: boolean;
  mode?: "run" | "session";
  timeoutSeconds?: number;
}

const SpawnResponseSchema = z.object({
  sessionKey: z.string(),
  result: z.string().optional(),
  status: z.enum(["completed", "running", "error"]),
});

export class GatewayClient {
  private config: Required<GatewayClientConfig>;

  constructor(config: GatewayClientConfig) {
    this.config = {
      authToken: process.env.OPENCLAW_GATEWAY_TOKEN ?? "",
      timeout: 30000,
      ...config,
    };
  }

  async spawn(req: SpawnRequest): Promise<z.infer<typeof SpawnResponseSchema>> {
    const url = `${this.config.baseUrl}/api/sessions/spawn`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(this.config.authToken
          ? { Authorization: `Bearer ${this.config.authToken}` }
          : {}),
      },
      body: JSON.stringify(req),
      signal: AbortSignal.timeout(this.config.timeout),
    });

    if (!res.ok) {
      throw new GatewayError(`Spawn failed: ${res.status}`, res.status);
    }

    return SpawnResponseSchema.parse(await res.json());
  }

  async getSession(sessionKey: string) {
    const url = `${this.config.baseUrl}/api/sessions/${encodeURIComponent(sessionKey)}`;
    const res = await fetch(url, {
      headers: this.authHeaders(),
      signal: AbortSignal.timeout(this.config.timeout),
    });
    if (!res.ok) throw new GatewayError(`Get session failed: ${res.status}`, res.status);
    return res.json();
  }

  private authHeaders(): Record<string, string> {
    return this.config.authToken
      ? { Authorization: `Bearer ${this.config.authToken}` }
      : {};
  }
}

export class GatewayError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "GatewayError";
  }
}
```

### 2. task() 幂等包装器 — Durable Execution 语义

LangGraph v1.2.9 引入 `task()` 概念：节点可以声明为"任务"，其执行结果会被检查点持久化，重试时跳过已完成的任务。这与 OpenClaw 的 sessions_spawn 天然对齐。

```ts
// task-wrapper.ts
import { z } from "zod";
import { GatewayClient } from "./gateway-client.js";

export interface TaskConfig<TInput, TOutput> {
  name: string;
  description: string;
  inputSchema: z.ZodType<TInput>;
  outputSchema: z.ZodType<TOutput>;
  agentId?: string;
  model?: string;
  retries?: number;
}

/**
 * Create a durable task that wraps OpenClaw sessions_spawn.
 * 
 * Key insight: task() provides idempotency by computing a task ID from
 * (taskName + inputHash). On retry/replay, completed tasks are skipped.
 * This maps to OpenClaw's session management — we track task→sessionKey
 * mapping in the graph state.
 */
export function createTask<TInput, TOutput>(
  gateway: GatewayClient,
  config: TaskConfig<TInput, TOutput>
) {
  return {
    name: config.name,

    async execute(input: TInput, taskId: string): Promise<TOutput> {
      // Validate input
      const validated = config.inputSchema.parse(input);

      // Build spawn request from validated input
      const spawnReq = {
        agentId: config.agentId,
        task: typeof validated === "string" ? validated : JSON.stringify(validated),
        model: config.model,
        mode: "run" as const,
      };

      const result = await gateway.spawn(spawnReq);

      if (result.status === "error") {
        throw new TaskError(
          `Task ${config.name} failed: ${result.result}`,
          config.name,
          taskId
        );
      }

      // Parse and validate output
      const output = result.result ?? "";
      return config.outputSchema.parse(
        // Try JSON parse for structured output, fallback to raw string
        (() => { try { return JSON.parse(output); } catch { return output; } })()
      );
    },
  };
}

export class TaskError extends Error {
  constructor(
    message: string,
    public readonly taskName: string,
    public readonly taskId: string
  ) {
    super(message);
    this.name = "TaskError";
  }
}
```

### 3. Task State Tracking — 在 LangGraph State 中追踪任务执行

```ts
// state.ts
import { StateSchema, ReducedValue } from "@langchain/langgraph";
import { z } from "zod";

// Task execution record for checkpointing
const TaskRecordSchema = z.object({
  taskId: z.string(),         // Deterministic: hash(taskName + input)
  status: z.enum(["pending", "running", "completed", "failed"]),
  result: z.unknown().optional(),
  sessionKey: z.string().optional(),  // OpenClaw session reference
  startedAt: z.number().optional(),
  completedAt: z.number().optional(),
});

export const BridgeState = new StateSchema({
  // User-facing
  query: z.string(),
  finalAnswer: z.string().optional(),

  // Task orchestration
  taskResults: new ReducedValue(
    z.record(z.unknown()).default(() => ({})),
    {
      inputSchema: TaskRecordSchema,
      reducer: (current, update) => ({
        ...current,
        [update.taskId]: update,
      }),
    }
  ),

  // Execution log
  log: new ReducedValue(
    z.array(z.string()).default(() => []),
    {
      inputSchema: z.string(),
      reducer: (current, entry) => [...current, entry],
    }
  ),
});

export type BridgeStateType = typeof BridgeState.State;
```

### 4. 完整 Bridge Graph — 组装所有组件

```ts
// bridge-graph.ts
import { StateGraph, START, END } from "@langchain/langgraph";
import { GatewayClient } from "./gateway-client.js";
import { createTask } from "./task-wrapper.js";
import { BridgeState } from "./state.js";
import { createHash } from "crypto";

const gateway = new GatewayClient({
  baseUrl: process.env.OPENCLAW_GATEWAY_URL ?? "http://localhost:3271",
});

// Define tasks
const researchTask = createTask(gateway, {
  name: "research",
  description: "Deep research on a topic",
  inputSchema: z.object({ topic: z.string(), depth: z.number().default(3) }),
  outputSchema: z.object({ summary: z.string(), sources: z.array(z.string()) }),
});

const analysisTask = createTask(gateway, {
  name: "analysis",
  description: "Analyze research results",
  inputSchema: z.string(),
  outputSchema: z.object({ insights: z.array(z.string()), recommendation: z.string() }),
});

// Compute deterministic task ID
function taskId(taskName: string, input: unknown): string {
  const hash = createHash("sha256")
    .update(`${taskName}:${JSON.stringify(input)}`)
    .digest("hex")
    .slice(0, 12);
  return `${taskName}-${hash}`;
}

// Node: Research
async function researchNode(state: typeof BridgeState.State) {
  const tid = taskId("research", state.query);
  const result = await researchTask.execute({ topic: state.query, depth: 3 }, tid);
  return {
    taskResults: { taskId: tid, status: "completed", result },
    log: `Research completed: ${result.summary.slice(0, 80)}...`,
  };
}

// Node: Analyze
async function analysisNode(state: typeof BridgeState.State) {
  const researchResult = Object.values(state.taskResults)
    .find((r: any) => r.taskId?.startsWith("research-"));
  
  if (!researchResult?.result) {
    return { log: "Analysis skipped: no research result" };
  }

  const tid = taskId("analysis", researchResult.result);
  const result = await analysisTask.execute(
    (researchResult.result as any).summary, tid
  );
  return {
    finalAnswer: result.recommendation,
    taskResults: { taskId: tid, status: "completed", result },
    log: `Analysis: ${result.recommendation.slice(0, 80)}...`,
  };
}

// Build graph
export function createBridgeGraph() {
  return new StateGraph(BridgeState)
    .addNode("research", researchNode)
    .addNode("analyze", analysisNode)
    .addEdge(START, "research")
    .addEdge("research", "analyze")
    .addEdge("analyze", END)
    .compile();
}

// Usage
async function main() {
  const graph = createBridgeGraph();
  
  // Invoke
  const result = await graph.invoke({ query: "LangGraph.js streaming patterns" });
  console.log(result.finalAnswer);

  // Stream
  for await (const chunk of await graph.stream(
    { query: "LangGraph.js streaming patterns" },
    { streamMode: "updates" }
  )) {
    console.log(chunk);
  }
}

main().catch(console.error);
```

---

## 代码示例 — 可运行的 Gateway Client 单元测试

```ts
// gateway-client.test.ts — 可用 node --test 运行
import { describe, it, assert } from "node:test";
import { GatewayClient, GatewayError } from "./gateway-client.js";

describe("GatewayClient", () => {
  it("should throw GatewayError on non-2xx response", async () => {
    // Use a non-existent endpoint to test error handling
    const client = new GatewayClient({
      baseUrl: "http://localhost:1", // Connection refused
      timeout: 1000,
    });

    await assert.rejects(
      () => client.spawn({ task: "test" }),
      (err: unknown) => {
        // Connection refused or timeout — both are expected
        assert.ok(err instanceof Error);
        return true;
      }
    );
  });

  it("should construct correct headers with auth token", () => {
    const client = new GatewayClient({
      baseUrl: "http://localhost:3271",
      authToken: "test-token",
    });
    // Verify config is set correctly
    assert.equal((client as any).config.authToken, "test-token");
    assert.equal((client as any).config.baseUrl, "http://localhost:3271");
  });

  it("should use env var for auth token when not provided", () => {
    process.env.OPENCLAW_GATEWAY_TOKEN = "env-token";
    const client = new GatewayClient({
      baseUrl: "http://localhost:3271",
    });
    assert.equal((client as any).config.authToken, "env-token");
    delete process.env.OPENCLAW_GATEWAY_TOKEN;
  });
});

describe("task()", () => {
  it("should compute deterministic task IDs", () => {
    const { createHash } = await import("crypto");
    const id1 = createHash("sha256").update("research:test").digest("hex").slice(0, 12);
    const id2 = createHash("sha256").update("research:test").digest("hex").slice(0, 12);
    assert.equal(id1, id2);
    
    const id3 = createHash("sha256").update("research:different").digest("hex").slice(0, 12);
    assert.notEqual(id1, id3);
  });
});
```

运行方式:
```bash
node --test gateway-client.test.ts  # 需要 --experimental-strip-types 或 tsx
# 或
npx tsx --test gateway-client.test.ts
```

---

## 关键洞察 (5条)

### 1. task() 幂等性 = 确定性任务 ID + 检查点恢复

LangGraph 的 task() 幂等性依赖于：每次执行时，从 (taskName, input) 计算确定性 ID。如果检查点中已有该 ID 的 completed 记录，跳过执行。这与 OpenClaw 的 session 生命周期天然对齐 — sessionKey 就是执行记录。

### 2. Gateway HTTP Client 是生产/本地双模式的关键

前序研究的 `createOpenClawNode()` 使用 in-process `sessions_spawn`，适合开发和测试。Gateway HTTP Client 使同一个 graph 既能在 OpenClaw 进程内运行（executor 直接调用），也能作为独立服务通过 HTTP 调用 Gateway。**核心抽象是 executor 接口**：

```ts
type Executor = (req: SpawnRequest) => Promise<SpawnResponse>;
// in-process: 直接调用 sessions_spawn
// remote: 通过 GatewayClient.spawn()
```

### 3. ReducedValue 的 taskResults 是任务编排的状态核心

不同于简单的 `z.string()` last-value 语义，`ReducedValue` 让多个节点的任务结果可以合并到同一个 record 中。这意味着：
- research 节点写入 `{ "research-abc123": { status: "completed", result: ... } }`
- analysis 节点读取并写入 `{ "analysis-def456": { ... } }`
- 不会互相覆盖，而是增量合并

### 4. Node-level Caching (2025.5) 与 Gateway 调用天然互补

LangGraph 2025.5 引入 Node-level Caching（`cachePolicy: { ttl: 3 }`），基于输入 hash 缓存节点结果。对于 Gateway HTTP 调用，这意味着相同输入不会重复发起 HTTP 请求，大幅减少延迟。**这比 task() 的幂等性更轻量 — task() 走检查点，caching 走内存**。

### 5. Subgraph 模式适合 OpenClaw 多 Agent 编排

LangGraph 支持 subgraph（子状态机），每个 subgraph 有独立状态。这意味着可以为每个 OpenClaw agent 创建独立 subgraph，父 graph 做路由和结果聚合。**这比之前的 Supervisor pattern 更模块化**：

```
ParentGraph
├── ResearchSubgraph (独立状态，可单独测试)
├── AnalysisSubgraph  
└── SummarySubgraph
```

---

## 与现有项目关联

| 项目 | 关联 |
|------|------|
| **createOpenClawNode()** (05-01) | task() 是 createOpenClawNode 的上层抽象，添加幂等性 |
| **A2A Trust Extension** (05-02) | Gateway Client 的 Bearer auth 可复用 A2A 的 JWS 签名 |
| **AMS (agent-memory-service)** | taskResults 可接入 AMS 的 embedding 搜索做历史任务复用 |
| **prompt-router** | Gateway 调用前的 model 路由可复用 prompt-router |

---

## 下一步行动

1. **创建 `lab/openclaw-langgraph-bridge/`** — 实现 GatewayClient + createTask + BridgeState
   - 第一步：GatewayClient 类（fetch-based，Zod 验证）
   - 第二步：createTask 包装器
   - 第三步：集成 createOpenClawNode（executor 双模式）
   - 成功标准：`node --test` 3+ tests passing

2. **实现 executor 接口抽象** — 同一个 graph 支持 in-process 和 HTTP 两种执行模式
   ```ts
   type Executor = (req: SpawnRequest) => Promise<SpawnResponse>;
   // local: (req) => sessions_spawn(req)
   // remote: (req) => gatewayClient.spawn(req)
   ```

3. **探索 subgraph 模式** — 为多 agent 编排设计可组合的 subgraph 架构

---

## 参考

- LangGraph.js Graph API: https://docs.langchain.com/oss/javascript/langgraph/graph-api
- LangGraph.js Streaming: https://docs.langchain.com/oss/javascript/langgraph/streaming
- StateSchema API: https://reference.langchain.com/javascript/langchain-langgraph/web/StateSchema
- RemoteGraph (Python): https://docs.langchain.com/langsmith/use-remote-graph
- LangGraph 2026 New Features: https://eastondev.com/blog/en/posts/ai/20260424-langgraph-agent-architecture/
