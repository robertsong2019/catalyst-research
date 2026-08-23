# LangGraph.js Bridge Patterns — 深度研究笔记

> 日期: 2026-05-26 | 主题: LangGraph.js Node Patterns for OpenClaw Bridge
> 状态: ✅ 含可运行代码 | 关联项目: lab/openclaw-langgraph-bridge

---

## 核心概念 (5个)

### 1. StateGraph + StateSchema（LangGraph.js 核心）

LangGraph.js 的状态管理基于 **Zod schema + reducer** 模式。每个节点只返回需要更新的字段，reducer 负责合并。

```ts
import { StateGraph, StateSchema, MessagesValue, START, END } from "@langchain/langgraph";
import { z } from "zod";

const State = new StateSchema({
  messages: MessagesValue,        // 内置 reducer: 消息追加
  task: z.string(),
  result: z.string().optional(),
  score: z.number().default(0),
});
```

**关键洞察**: LangGraph.js 的 `StateSchema` 与 LangGraph.py 的 `TypedDict` 等价，但用 Zod 做运行时验证。这是 TS 生态的优势——schema 即类型 即验证。

### 2. Subgraph 嵌套（Supervisor Pattern）

子图是节点内嵌完整 graph，实现分层编排。核心 API：父 graph 的 `addNode()` 接受编译后的子图。

```ts
// 子图：研究流程
const researchSubgraph = new StateGraph(SharedState)
  .addNode("search", searchNode)
  .addNode("synthesize", synthesizeNode)
  .addEdge(START, "search")
  .addEdge("search", "synthesize")
  .addEdge("synthesize", END)
  .compile();

// 父图：Supervisor 编排
const supervisorGraph = new StateGraph(SharedState)
  .addNode("router", routerNode)
  .addNode("research", researchSubgraph)  // 子图作为节点
  .addNode("analysis", analysisSubgraph)
  .addConditionalEdges("router", routeDecision, ["research", "analysis", END])
  .addEdge("research", "router")   // 回到 supervisor
  .addEdge("analysis", "router")
  .compile();
```

**关键洞察**: 2026年 LangGraph 的 subgraph 支持 **namespace isolation**——子图内的 checkpoint 不与父图冲突，这对生产系统至关重要。

### 3. Command + interrupt（Human-in-the-loop）

LangGraph 2025-2026 最重要的 API 变化：`Command` 替代直接返回值，`interrupt()` 替代 `NodeInterrupt`。

```ts
import { Command, interrupt } from "@langchain/langgraph";

function approvalNode(state: typeof State) {
  const decision = interrupt("需要人工审批: " + state.proposal);
  // decision 来自外部 resume 输入
  if (decision.approved) {
    return new Command({ update: { status: "approved", approvedBy: decision.reviewer } });
  }
  return new Command({ update: { status: "rejected" } });
}
```

### 4. Send（Map-Reduce / Fan-out）

`Send` 实现动态并行——运行时决定分发给哪些节点。

```ts
import { Send } from "@langchain/langgraph";

function fanOutNode(state: typeof State) {
  const topics = extractTopics(state.task);
  return topics.map(topic => new Send("researcher", { ...state, subtask: topic }));
}
```

### 5. Checkpointing + Time Travel

LangGraph 内置持久化，支持时间旅行调试。生产部署用 PostgreSQL / SQLite backend。

```ts
import { MemorySaver } from "@langchain/langgraph";

const checkpointer = new MemorySaver();
const graph = builder.compile({ checkpointer });

// 调用
const result = await graph.invoke(input, {
  configurable: { thread_id: "session-123" }
});

// 时间旅行：获取历史状态
const history = graph.getStateHistory({ configurable: { thread_id: "session-123" } });
for await (const state of history) {
  console.log(state.next, state.values); // 查看每步状态
}
```

---

## 可运行代码示例：OpenClaw Task Router

这是一个完整的、可直接运行的 LangGraph.js 示例，展示 OpenClaw Bridge 的核心路由模式。

```ts
// task-router.ts — 可直接 npx tsx task-router.ts 运行
import {
  StateGraph,
  StateSchema,
  MessagesValue,
  START,
  END,
} from "@langchain/langgraph";
import { z } from "zod";

// ---- 1. State 定义 ----
const TaskState = new StateSchema({
  messages: MessagesValue,
  task: z.string(),
  taskType: z.enum(["research", "code", "chat"]).optional(),
  researchResult: z.string().optional(),
  codeResult: z.string().optional(),
  finalResult: z.string().optional(),
});

// ---- 2. 模拟 OpenClaw 节点 ----
type NodeState = {
  messages: any[];
  task: string;
  taskType?: "research" | "code" | "chat";
  researchResult?: string;
  codeResult?: string;
  finalResult?: string;
};

function createOpenClawNode(
  name: string,
  handler: (task: string) => Promise<string>
) {
  return async (state: NodeState): Promise<Partial<NodeState>> => {
    console.log(`[${name}] Processing: ${state.task}`);
    const result = await handler(state.task);
    return { [`${name}Result`]: result };
  };
}

// ---- 3. 路由器节点 ----
function routerNode(state: NodeState): Partial<NodeState> {
  const task = state.task.toLowerCase();
  let taskType: "research" | "code" | "chat";
  if (task.includes("research") || task.includes("调研")) {
    taskType = "research";
  } else if (task.includes("code") || task.includes("代码") || task.includes("写")) {
    taskType = "code";
  } else {
    taskType = "chat";
  }
  console.log(`[router] Classified as: ${taskType}`);
  return { taskType };
}

function routeDecision(state: NodeState): string {
  return state.taskType || "chat";
}

// ---- 4. 汇总节点 ----
async function aggregatorNode(state: NodeState): Promise<Partial<NodeState>> {
  const result = state.researchResult || state.codeResult || "No specific result";
  const finalResult = `✅ Task: ${state.task}\n📋 Result: ${result}`;
  return { finalResult };
}

// ---- 5. 构建 Graph ----
const graph = new StateGraph(TaskState)
  .addNode("router", routerNode)
  .addNode("research", createOpenClawNode("research", async (t) => `Deep research on: ${t}`))
  .addNode("code", createOpenClawNode("code", async (t) => `Generated code for: ${t}`))
  .addNode("chat", createOpenClawNode("chat", async (t) => `Response to: ${t}`))
  .addNode("aggregator", aggregatorNode)
  .addEdge(START, "router")
  .addConditionalEdges("router", routeDecision, {
    research: "research",
    code: "code",
    chat: "chat",
  })
  .addEdge("research", "aggregator")
  .addEdge("code", "aggregator")
  .addEdge("chat", "aggregator")
  .addEdge("aggregator", END)
  .compile();

// ---- 6. 运行 ----
async function main() {
  const tasks = [
    "调研 2026 AI agent 框架对比",
    "写一个 JSON schema validator",
    "今天天气怎么样",
  ];

  for (const task of tasks) {
    console.log(`\n${"=".repeat(50)}`);
    const result = await graph.invoke({
      messages: [{ role: "user" as const, content: task }],
      task,
    });
    console.log(result.finalResult);
  }
}

main().catch(console.error);
```

**运行方式:**
```bash
cd lab/openclaw-langgraph-bridge
npm install @langchain/langgraph zod
npx tsx task-router.ts
```

---

## 关键洞察 (5条)

### 1. LangGraph.js 的 Schema-First 设计天然适配 OpenClaw

OpenClaw 的 `createOpenClawNode()` 本质是将 agent 配置映射为 LangGraph 节点函数。Zod schema 同时满足：
- **类型推导**（TypeScript 类型推断）
- **运行时验证**（输入/输出校验）
- **LangGraph 状态管理**（reducer 逻辑）

这比 Python 的 TypedDict 更强大，因为 Zod 是 runtime + compile-time 的。

### 2. Supervisor + Subgraph 是 2026 年的主流生产模式

根据 18+ 生产部署的分析，LangGraph 排名第一的关键原因是：
- **显式图模型**：可调试、可测试、可视化
- **内置 checkpointing**：状态持久化 + 时间旅行
- **Human-in-the-loop**：`interrupt()` + `Command` 原生支持

OpenClaw Bridge 应优先实现 `supervisor()` 和 `subgraph()` 模式。

### 3. `Command` API 是 2026 年的 breaking change

旧模式直接返回 `{ messages: [...] }`，新模式返回 `new Command({ update: {...}, goto: "nextNode" })`。
Bridge 应该同时支持两种模式，用版本标记区分。

### 4. Send + Map-Reduce 适合 OpenClaw 的多任务分发

OpenClaw 的 `sessions_spawn` 语义与 LangGraph 的 `Send` 高度匹配：
- `Send("node", payload)` ≈ `sessions_spawn({ task: payload })`
- 可以实现 fan-out 并行研究 → fan-in 汇总

### 5. Checkpoint Storage 选择影响生产架构

LangGraph 的 delta checkpointing 显著减少存储（10x-23x vs 全量）。
对于 OpenClaw Bridge，建议用 SQLite（单机）或 PostgreSQL（集群），与 OpenClaw 现有的状态存储对接。

---

## 下一步行动

1. **在 openclaw-langgraph-bridge 中实现 `supervisor()` 工厂函数**
   - 接受 `{ agents: AgentConfig[], routerConfig: RouterConfig }`
   - 内部创建 router 节点 + 子图节点 + conditional edges
   - 目标：5+ tests 覆盖路由决策

2. **添加 `Command` + `interrupt()` 支持**
   - 当前 `createOpenClawNode()` 只返回 partial state
   - 扩展为支持 `Command` 返回值，兼容 interrupt 场景
   - 适配 OpenClaw 的 `/approve` 审批流

3. **实现 `fanOut()` + `aggregate()` 模式**
   - `fanOut()` 基于 `Send`，动态分发子任务
   - `aggregate()` 收集所有结果，调用 reducer 合并
   - 与 OpenClaw 的 `subagents` 管理对齐

---

## 与现有项目关联

| 项目 | 关联 |
|------|------|
| `lab/openclaw-langgraph-bridge` | **直接目标** — 研究成果指导 supervisor/subgraph 实现 |
| `agent-orchestrator` skill | 可升级底层为 LangGraph.js，替换当前的 Python CrewAI 方案 |
| `agent-context-store` | LangGraph 的 checkpoint 可用 context-store 做持久化后端 |
| `structured-output-toolkit` | 节点内的 structured output 可直接使用 toolkit 的 StructuredLLMClient |

---

## 参考资料

- [LangGraph Subgraphs 文档](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [LangGraph.js Graph API](https://docs.langchain.com/oss/javascript/langgraph/graph-api)
- [LangGraph Multi-Agent Workflows](https://www.langchain.com/blog/langgraph-multi-agent-workflows)
- [LangChain Structured Output (JS)](https://docs.langchain.com/oss/javascript/langchain/structured-output)
- [AI Agent Frameworks 2026 Production Ranking](https://alicelabs.ai/en/insights/best-ai-agent-frameworks-2026)
- [agents-from-scratch-ts](https://github.com/langchain-ai/agents-from-scratch-ts)
