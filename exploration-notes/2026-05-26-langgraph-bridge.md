# LangGraph Bridge 研究笔记 — OpenClaw × LangGraph.js 集成架构

> 日期: 2026-05-26 | 主题: lab/openclaw-langgraph-bridge 设计前置研究
> 方法论: autoresearch — 明确指标、快速循环、积累性

---

## 核心概念

### 1. StateGraph + Annotation（状态图 + 注解）
LangGraph.js 的核心抽象。用 `Annotation.Root()` 定义状态 schema，`StateGraph` 构建有向图，节点函数接收状态并返回 `Partial<State>`。

```typescript
import { StateGraph, Annotation, START, END } from "@langchain/langgraph";

const WorkflowState = Annotation.Root({
  input: Annotation<string>,
  output: Annotation<string>,
  steps: Annotation<string[]>({
    reducer: (old, update) => old.concat(update),
    default: () => [],
  }),
});
```

**与 OpenClaw 的关联**: OpenClaw 的 session 概念可以映射为 LangGraph 的 `thread_id`，每次对话是一个持久化的 graph execution。

### 2. Command + interrupt（命令模式 + 中断恢复）
`Command` 是 LangGraph v1.0+ 引入的控制流原语，支持动态路由（`goto`）和状态更新（`update`）。`interrupt()` 实现 human-in-the-loop，graph 暂停并保存 checkpoint，外部通过 `Command({ resume })` 恢复。

```typescript
import { Command } from "@langchain/langgraph";

// 动态路由到不同节点
return new Command({
  update: { status: "needs_review" },
  goto: "reviewNode",
});

// 从外部恢复中断的 graph
await graph.invoke(new Command({ resume: { approved: true } }), config);
```

**与 OpenClaw 的关联**: OpenClaw 的 `sessions_spawn` + `sessions_send` 模式天然匹配 interrupt/resume 语义。一个 LangGraph 节点可以包装为 OpenClaw 子代理。

### 3. Functional API（entrypoint + task）
比 StateGraph 更轻量的替代方案。`entrypoint` 定义工作流入口，`task` 标记可重试/可追踪的步骤。适合包装现有函数，无需重构为图结构。

```typescript
import { entrypoint, task } from "@langchain/langgraph";
import { MemorySaver } from "@langchain/langgraph-checkpoint";

const processData = task("processData", async (input: string) => {
  return input.toUpperCase();
});

const workflow = entrypoint(
  { checkpointer: new MemorySaver(), name: "myWorkflow" },
  async (input: string) => {
    const result = await processData(input);
    return result;
  }
);
```

**与 OpenClaw 的关联**: `task` 映射到 OpenClaw 的 `sessions_spawn`，`entrypoint` 映射到主 session。这可能是 bridge 的首选集成模式——比 StateGraph 改动更小。

### 4. Checkpointer（持久化层）
MemorySaver（开发）、PostgresSaver（生产）、自定义 Saver。存储 graph 执行的每个 checkpoint，支持时间旅行调试和恢复。

**关键决策**: Bridge 可以使用 OpenClaw 的 `agent-context-store` 作为自定义 Checkpointer，复用已有的 graph traversal 和 state management。

### 5. Subgraph（子图嵌套）
LangGraph 支持将一个 StateGraph 作为另一个的节点嵌入，通过 `Command.PARENT` 与父图通信。

**与 OpenClaw 的关联**: 每个 OpenClaw 代理可以是一个 subgraph，主 session 是顶层 graph。

---

## 可运行代码示例

### 示例 1: OpenClaw-LangGraph Bridge 最小原型

```typescript
// openclaw-langgraph-bridge.ts
// 最小化 bridge：把 LangGraph 节点包装为 OpenClaw 可调用的函数

import {
  StateGraph,
  Annotation,
  START,
  END,
  MemorySaver,
} from "@langchain/langgraph";

// ---- 1. 定义 OpenClaw 感知的状态 ----
const OpenClawState = Annotation.Root({
  sessionId: Annotation<string>,
  messages: Annotation<string[]>({
    reducer: (old, update) => old.concat(update),
    default: () => [],
  }),
  currentTask: Annotation<string>,
  metadata: Annotation<Record<string, unknown>>,
});

// ---- 2. 创建 OpenClaw 节点工厂 ----
type OpenClawNodeFn = (
  state: typeof OpenClawState.State
) => Promise<Partial<typeof OpenClawState.State>>;

function createOpenClawNode(
  name: string,
  handler: (input: string, ctx: Record<string, unknown>) => Promise<string>
): OpenClawNodeFn {
  return async (state) => {
    console.log(`[OpenClawNode:${name}] Processing: ${state.currentTask}`);
    const result = await handler(state.currentTask, state.metadata);
    return {
      messages: [`[${name}] ${result}`],
    };
  };
}

// ---- 3. 构建图 ----
const researchNode = createOpenClawNode("research", async (input) => {
  // 模拟搜索 + 总结
  return `Researched: ${input} → found 3 relevant sources`;
});

const analysisNode = createOpenClawNode("analysis", async (input) => {
  return `Analyzed: ${input} → key insight identified`;
});

const summaryNode = createOpenClawNode("summary", async (input) => {
  return `Summary: ${input}`;
});

function buildGraph() {
  const checkpointer = new MemorySaver();

  const graph = new StateGraph(OpenClawState)
    .addNode("research", researchNode)
    .addNode("analysis", analysisNode)
    .addNode("summary", summaryNode)
    .addEdge(START, "research")
    .addEdge("research", "analysis")
    .addEdge("analysis", "summary")
    .addEdge("summary", END)
    .compile({ checkpointer });

  return graph;
}

// ---- 4. 执行 ----
async function main() {
  const graph = buildGraph();
  const config = { configurable: { thread_id: "openclaw-session-001" } };

  // 初次执行
  const result = await graph.invoke(
    {
      sessionId: "session-001",
      messages: [],
      currentTask: "LangGraph bridge architecture",
      metadata: { source: "openclaw" },
    },
    config
  );

  console.log("=== 最终状态 ===");
  console.log(JSON.stringify(result, null, 2));

  // 验证消息链
  console.log("\n=== 消息链 ===");
  result.messages.forEach((msg, i) => console.log(`${i + 1}. ${msg}`));
}

main().catch(console.error);
```

**运行方式:**
```bash
npm install @langchain/langgraph @langchain/langgraph-checkpoint
npx tsx openclaw-langgraph-bridge.ts
```

**预期输出:**
```
[OpenClawNode:research] Processing: LangGraph bridge architecture
[OpenClawNode:analysis] Processing: LangGraph bridge architecture
[OpenClawNode:summary] Processing: LangGraph bridge architecture
=== 最终状态 ===
{
  "sessionId": "session-001",
  "messages": [
    "[research] Researched: LangGraph bridge architecture → found 3 relevant sources",
    "[analysis] Analyzed: Researched: LangGraph bridge architecture → key insight identified",
    "[summary] Summary: Analyzed: Researched: LangGraph bridge architecture → key insight identified"
  ],
  "currentTask": "LangGraph bridge architecture",
  "metadata": { "source": "openclaw" }
}
```

### 示例 2: 带 interrupt 的 Human-in-the-Loop 模式

```typescript
// hitl-bridge.ts — OpenClaw 代理需要人类确认时的 interrupt 模式
import {
  StateGraph,
  Annotation,
  START,
  END,
  MemorySaver,
  Command,
} from "@langchain/langgraph";
import { interrupt } from "@langchain/langgraph";

const ReviewState = Annotation.Root({
  proposal: Annotation<string>,
  approved: Annotation<boolean>,
  feedback: Annotation<string>,
});

async function generateProposal(state: typeof ReviewState.State) {
  return { proposal: "Proposal: Build openclaw-langgraph-bridge with 5+ tests" };
}

async function waitForReview(state: typeof ReviewState.State) {
  // 暂停执行，等待外部输入
  const decision = interrupt({
    question: "Do you approve this proposal?",
    proposal: state.proposal,
  });
  return {
    approved: decision.approved,
    feedback: decision.feedback || "",
  };
}

async function executeProposal(state: typeof ReviewState.State) {
  return {
    proposal: state.approved
      ? `EXECUTED: ${state.proposal}`
      : `REJECTED: ${state.proposal} — ${state.feedback}`,
  };
}

const graph = new StateGraph(ReviewState)
  .addNode("generate", generateProposal)
  .addNode("review", waitForReview)
  .addNode("execute", executeProposal)
  .addEdge(START, "generate")
  .addEdge("generate", "review")
  .addEdge("review", "execute")
  .addEdge("execute", END)
  .compile({ checkpointer: new MemorySaver() });

async function demonstrateHITL() {
  const config = { configurable: { thread_id: "review-thread-1" } };

  // 第一次调用 — 会暂停在 interrupt
  const result1 = await graph.invoke({}, config);
  console.log("Interrupted:", result1.__interrupt__);

  // 恢复执行 — 提供人类决策
  const result2 = await graph.invoke(
    new Command({ resume: { approved: true, feedback: "Looks good!" } }),
    config
  );
  console.log("Final:", result2);
}

demonstrateHITL().catch(console.error);
```

---

## 关键洞察

### 洞察 1: Functional API 是 Bridge 的最佳入口
对比 StateGraph 和 Functional API：
- **StateGraph**: 适合复杂的 DAG 工作流，但需要将 OpenClaw 逻辑重构为节点函数
- **Functional API**: `task` 可以直接包装 OpenClaw 的 `sessions_spawn` 调用，`entrypoint` 包装主 session。**改动最小，集成最快**

**建议**: 先用 Functional API 实现 MVP（`entrypoint` = 主循环，`task` = 每个代理调用），验证可行后再考虑是否需要 StateGraph 的高级特性（条件边、并行节点）。

### 洞察 2: agent-context-store 可作为自定义 Checkpointer
LangGraph 的 Checkpointer 接口是公开的，可以自定义实现。`agent-context-store` 已有 447+ tests，包括 graph traversal 和 state management。将其适配为 LangGraph Checkpointer 可以：
- 复用已有的持久化逻辑
- 让 LangGraph 的 checkpoint 与 OpenClaw 的 context store 共享数据
- 避免引入额外的存储依赖

### 洞察 3: LangGraph 1.0+ 的 Command 模式天然匹配 OpenClaw 的会话模型
`Command({ goto, update })` 允许节点动态决定下一步执行哪个节点，而不需要预定义所有边。这类似于 OpenClaw 中子代理决定是否继续、重试或切换到另一个代理。这种动态路由是 agent orchestration 的核心需求，LangGraph 已经原生支持。

### 洞察 4: Subgraph + Command.PARENT 实现代理嵌套
OpenClaw 的多层代理（main → subagent → subagent）可以映射为 LangGraph 的 subgraph 嵌套。子图通过 `Command.PARENT` 与父图通信，类似 OpenClaw 中子代理通过 `sessions_yield` 返回结果给父 session。

### 洞察 5: 持久化选择策略
- **开发**: `MemorySaver`（内存，随进程消失）
- **生产**: `PostgresSaver` 或自定义 Checkpointer（基于 agent-context-store）
- **Bridge 原型**: 先用 `MemorySaver`，快速验证；生产化时接入 agent-context-store

---

## 设计方案: lab/openclaw-langgraph-bridge/

```
lab/openclaw-langgraph-bridge/
├── src/
│   ├── index.ts              # 导出 createOpenClawNode, createTask, Executor
│   ├── createOpenClawNode.ts # StateGraph 节点工厂
│   ├── createTask.ts         # Functional API task 包装
│   ├── executor.ts           # 工作流执行器（invoke + stream）
│   └── types.ts              # OpenClawState 类型定义
├── tests/
│   ├── createOpenClawNode.test.ts  # 节点创建 + 状态传递
│   ├── createTask.test.ts          # task 包装 + 重试
│   ├── executor.test.ts            # 完整工作流执行
│   ├── hitl.test.ts               # human-in-the-loop 模式
│   └── subgraph.test.ts           # 子图嵌套
├── package.json
├── tsconfig.json
└── README.md
```

**目标测试**: 5+ tests（与 HEARTBEAT.md 一致）

---

## 下一步行动

1. **[本周]** 创建 `lab/openclaw-langgraph-bridge/` 项目结构，安装 `@langchain/langgraph` 依赖
2. **[本周]** 实现 `createOpenClawNode()` — 基于 Functional API 的 `task` 包装，3 个测试
3. **[本周]** 实现 `Executor` — `invoke` + `stream` 包装，2 个测试
4. **[下周]** 实现 HITL 模式 — `interrupt` + `Command(resume)` 集成
5. **[下周]** 评估是否需要 StateGraph 模式或 Functional API 足够

---

## 参考

- [LangGraph.js Graph API](https://docs.langchain.com/oss/javascript/langgraph/graph-api)
- [LangGraph Functional API (JS)](https://docs.langchain.com/oss/javascript/langgraph/functional-api)
- [Choosing between Graph and Functional APIs](https://docs.langchain.com/oss/javascript/langgraph/choosing-apis)
- [LangGraph.js v0.2 Announcement](https://www.langchain.com/blog/javascript-langgraph-v02-cloud-studio)
- [LangGraph State Management in Practice 2026](https://eastondev.com/blog/en/posts/ai/20260424-langgraph-agent-architecture)
- [LangGraph.js Guide 2026](https://langgraphjs.guide)
