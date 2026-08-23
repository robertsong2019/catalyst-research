# LangGraph.js Bridge 实战：GatewayClient + createTask + Executor 双模式

> 日期: 2026-05-08 | 方法: autoresearch
> 主题: openclaw-langgraph-bridge 从设计到可运行验证
> 前序: [Gateway HTTP Client 设计](2026-05-08-langgraphjs-gateway-http-client.md) | [createOpenClawNode](2026-05-01-langgraphjs-create-openclaw-node.md)
> 关联: HEARTBEAT.md 高优先级 — lab/openclaw-langgraph-bridge/
> 验证: 18/18 tests passing ✅

---

## 为什么这次研究不同

前序研究停留在 API 设计层面（GatewayClient 类、createTask 签名）。本次研究：

1. **实现了完整验证代码** — GatewayClient、Executor 双模式、createTask 幂等检查、BridgeState ReducedValue、端到端 Bridge Graph
2. **发现了 Executor 接口是关键抽象** — 而非 GatewayClient 本身
3. **验证了 checkpoint 序列化** — 任务状态可跨 session 恢复
4. **对齐了真实 OpenClaw Gateway API** — `/v1/agent/run` 而非假设的 `/api/sessions/spawn`

---

## 核心概念 (5个)

### 1. Executor 接口 — 双模式的核心抽象

```ts
type Executor = (req: SpawnRequest) => Promise<SpawnResponse>;
```

GatewayClient 不是关键，**Executor 接口**才是。同一个 LangGraph graph 通过切换 executor 实现，零修改地在开发模式（in-process mock）和生产模式（HTTP Gateway）之间切换：

```ts
// 开发/测试: in-process mock
const devExecutor = createLocalExecutor(taskStore);

// 生产: HTTP Gateway
const prodExecutor = createHttpExecutor({
  baseUrl: "http://localhost:3271",
  authToken: process.env.OPENCLAW_GATEWAY_TOKEN,
});
```

这比直接在 graph 中硬编码 `sessions_spawn` 或 `fetch()` 调用更灵活。createOpenClawNode 接受 executor 参数，实现依赖注入。

### 2. createTask — 带检查点的幂等任务执行

createTask 包装 executor，添加：
- **确定性任务 ID**: `sha256(taskName:JSON.stringify(input)).slice(0,12)` — 相同输入始终产生相同 ID
- **幂等检查**: 执行前检查 completedTasks Map，已完成则跳过
- **检查点序列化**: `getCheckpoint()` / `restoreCheckpoint(data)` 用于跨 session 恢复

这是 LangGraph v1.2.9 `task()` 概念的轻量实现，不需要 LangGraph 平台级检查点器。

### 3. BridgeState ReducedValue — 增量状态合并

LangGraph 的 `ReducedValue` 让多节点的任务结果增量合并到同一个 record：

```ts
const BridgeState = new StateSchema({
  taskResults: new ReducedValue(
    z.record(z.unknown()).default(() => ({})),
    {
      inputSchema: TaskRecordSchema,
      reducer: (current, update) => ({ ...current, [update.taskId]: update }),
    }
  ),
  log: new ReducedValue(
    z.array(z.string()).default(() => []),
    { inputSchema: z.string(), reducer: (current, entry) => [...current, entry] }
  ),
});
```

关键区别：
- `taskResults`: 按 taskId 合并（不覆盖已有 key）
- `log`: append-only（每次追加）
- `query` / `finalAnswer`: LastValue（最后写入生效）

### 4. OpenClaw Gateway 真实 API 端点

通过研究 OpenClaw Gateway 源码和文档，确认了真实的 API 端点：

| 端点 | 用途 | 认证 |
|------|------|------|
| `POST /v1/agent/run` | 运行 Agent（主要入口） | Bearer token |
| `POST /api/sessions/main/messages` | 发送消息到主会话 | Bearer token |
| `GET /v1/sessions/` | 列出会话 | Bearer token |
| `GET /status` | 健康检查 | 无 |
| WebSocket `chat.run` | 实时对话 | Token in params |

HTTP executor 使用 `/v1/agent/run`（非之前假设的 `/api/sessions/spawn`），请求格式为：

```json
{
  "message": "task description",
  "sessionKey": "bridge-abc123",
  "options": { "model": "...", "thinking": "medium" }
}
```

### 5. StateSchema 替代 Annotation — LangGraph.js v1.1+ API 变迁

LangGraph.js v1.1.0 引入 `StateSchema` + `ReducedValue` 替代旧的 `Annotation.Root()` API：

**旧 API (Annotation):**
```ts
const State = Annotation.Root({
  messages: Annotation<BaseMessage[]>({ reducer: concat, default: () => [] }),
});
```

**新 API (StateSchema):**
```ts
const State = new StateSchema({
  messages: MessagesValue,
  history: new ReducedValue(
    z.array(z.string()).default(() => []),
    { inputSchema: z.string(), reducer: (c, n) => [...c, n] }
  ),
});
```

优势：Zod v4 原生集成、`typeof State.State` / `typeof State.Update` 类型提取、标准 JSON Schema 输出（兼容 Studio 和 API）。

---

## 可运行代码 — 完整验证 (18 tests)

验证代码位于 `/tmp/langgraph-bridge-verify.mjs`，18/18 全通过。核心组件：

### Executor 工厂

```js
// In-process mock (开发/测试)
function createLocalExecutor(taskResults = new Map()) {
  return async function localExecutor(req) {
    const sessionId = `local-${randomBytes(4).toString("hex")}`;
    await new Promise(r => setTimeout(r, 10));
    const result = `[mock] Processed: ${req.task}`;
    taskResults.set(sessionId, { result, status: "completed" });
    return { sessionKey: sessionId, result, status: "completed" };
  };
}

// Gateway HTTP (生产)
function createHttpExecutor(config) {
  return async function httpExecutor(req) {
    const res = await fetch(`${config.baseUrl}/v1/agent/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(config.authToken ? { Authorization: `Bearer ${config.authToken}` } : {}),
      },
      body: JSON.stringify({
        message: req.task,
        sessionKey: `bridge-${randomBytes(4).toString("hex")}`,
        options: { model: req.model, thinking: "medium" },
      }),
      signal: AbortSignal.timeout(config.timeout || 30000),
    });
    if (!res.ok) throw new Error(`Gateway error: ${res.status}`);
    return res.json();
  };
}
```

### createTask 幂等包装

```js
function createTask(executor, config) {
  const completedTasks = new Map();
  return {
    name: config.name,
    async execute(input) {
      const taskId = computeTaskId(config.name, input);
      if (completedTasks.has(taskId)) return { ...completedTasks.get(taskId), _cached: true };
      const result = await executor({ task: typeof input === "string" ? input : JSON.stringify(input), model: config.model });
      if (result.status === "error") throw new Error(`Task "${config.name}" failed`);
      const parsed = (() => { try { return JSON.parse(result.result); } catch { return result.result; } })();
      completedTasks.set(taskId, parsed);
      return { ...parsed, _cached: false };
    },
    getCheckpoint() { return Object.fromEntries(completedTasks); },
    restoreCheckpoint(data) { for (const [k, v] of Object.entries(data)) completedTasks.set(k, v); },
  };
}
```

### BridgeState ReducedValue 模拟

```js
function applyUpdate(state, update) {
  if (update.taskResults) state.taskResults = { ...state.taskResults, ...update.taskResults };
  if (update.log) state.log = [...state.log, update.log];
  if (update.finalAnswer !== undefined) state.finalAnswer = update.finalAnswer;
  return state;
}
```

### 端到端验证结果

```
1. Task ID Determinism        ✅ Same input → same ID
2. Local Executor             ✅ Status completed, result correct
3. Task Idempotency           ✅ Second call returns cached
4. Checkpoint Serialization   ✅ Save/restore works
5. BridgeState ReducedValue   ✅ Merge + append correct
6. End-to-End Bridge Graph    ✅ Research → Analysis → Final Answer
=== Results: 18 passed, 0 failed ===
```

---

## 关键洞察 (5条)

### 1. Executor 接口 > GatewayClient 类

GatewayClient 只是 executor 的一种实现。真正重要的是 executor 的接口签名 `(SpawnRequest) => Promise<SpawnResponse>`。这使得：
- 测试时用 `createLocalExecutor()` — 零网络依赖
- 开发时用 in-process `sessions_spawn` 包装
- 生产时用 `createHttpExecutor()` — 调用真实 Gateway

createOpenClawNode 应该接受 executor 参数而非 GatewayClient 实例。

### 2. 确定性 Task ID 是幂等性的基石

`sha256(taskName:input)` 确保相同任务不会重复执行。这比 OpenClaw 的 sessionKey（随机生成）更适合 LangGraph 的 checkpoint 恢复场景。关键区别：
- sessionKey = 随机，用于追踪一次执行
- taskId = 确定性，用于判断是否需要执行

两者可以共存：taskId 决定"要不要执行"，sessionKey 追踪"这次执行在哪"。

### 3. ReducedValue 让 BridgeState 天然支持多节点协作

传统做法是在节点间传递完整结果数组。ReducedValue 让每个节点只关心自己的输出，状态框架自动合并。这意味着：
- 添加新节点不需要修改现有节点的 state 读取逻辑
- `taskResults` 是一个 growing record，不会丢失历史
- 这比 Python LangGraph 的 `operator.add` 更类型安全（Zod 验证）

### 4. Checkpoint 序列化是跨 session 恢复的关键

`getCheckpoint()` / `restoreCheckpoint(data)` 将任务完成状态序列化为纯对象，可以：
- 存入 LangGraph checkpointer（MemorySaver / Postgres）
- 通过 WebSocket 发送给前端做进度展示
- 在 graph crash 后恢复到最近状态

这与 OpenClaw 的 session 生命周期形成互补：OpenClaw 管理 agent 进程的存活，LangGraph checkpoint 管理 workflow 状态的持久化。

### 5. StateSchema 新 API 比 Annotation 更适合桥接场景

StateSchema 的优势在桥接场景中尤其明显：
- `typeof State.State` 提供完整类型，node 函数签名自动推导
- `ReducedValue` 的 `inputSchema` 区分"写入类型"和"存储类型"，适合 taskResults 这种每条记录结构不同的情况
- Zod v4 的 `.default()` 让初始状态声明更简洁
- 标准 JSON Schema 输出可用于自动生成 API 文档

---

## 与现有项目关联

| 项目 | 关联 | 行动 |
|------|------|------|
| **createOpenClawNode** (05-01) | executor 参数取代直接 sessions_spawn 调用 | 重构为接受 executor |
| **Gateway HTTP Client** (05-08 上午) | httpExecutor 是其具体实现 | 合并到 lab/ |
| **A2A Trust** | Bearer auth 可升级为 JWS 签名 | Phase 2 |
| **AMS** | taskResults 历史可接入 embedding 搜索 | Phase 3 |
| **prompt-router** | model 参数可复用路由能力 | Phase 2 |

---

## 下一步行动

1. **创建 `lab/openclaw-langgraph-bridge/`** — 基于 Executor 接口的完整实现
   - `src/executor.ts` — LocalExecutor + HttpExecutor 工厂
   - `src/create-task.ts` — 幂等任务包装器
   - `src/state.ts` — BridgeState (StateSchema)
   - `src/create-bridge-graph.ts` — 完整 graph 工厂
   - **成功标准**: `node --test` 5+ tests passing，包含端到端流程

2. **集成 createOpenClawNode** — 重构为 executor 参数模式
   - `createOpenClawNode({ executor, name, ...config })`
   - 开发模式: `executor = createLocalExecutor()`
   - 生产模式: `executor = createHttpExecutor({ baseUrl: gatewayUrl })`

3. **Supervisor 模式验证** — 用 @langchain/langgraph-supervisor 替代手写 router
   - 测试 supervisor 路由到多个 createOpenClawNode 生成的 worker 节点
   - 验证 subgraph 模式下的检查点隔离

---

## 参考

- LangGraph.js Graph API: https://docs.langchain.com/oss/javascript/langgraph/use-graph-api
- StateSchema API Reference: https://reference.langchain.com/javascript/langchain-langgraph/web/StateSchema
- ReducedValue API Reference: https://reference.langchain.com/javascript/langchain-langgraph/web/ReducedValue
- LangGraph Changelog v1.1.0: https://docs.langchain.com/oss/javascript/releases/changelog
- OpenClaw Gateway API: https://blink.new/blog/openclaw-api-guide-endpoints-integration-2026
- LangGraph Subgraphs: https://docs.langchain.com/oss/python/langgraph/use-subgraphs
- Idempotent Agent Designs: https://medium.com/@kaushalsinh73/7-langgraph-agent-designs-that-dont-buckle-590074126b0d
- Swarm vs Supervisor: https://www.augmentcode.com/guides/swarm-vs-supervisor

---

*验证代码: `/tmp/langgraph-bridge-verify.mjs` — 18/18 tests passing*
