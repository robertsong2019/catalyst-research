# LangGraph.js 最新特性：Annotation、Command 动态路由与 Node Caching

> 日期: 2026-05-07 | 关联项目: lab/openclaw-langgraph-bridge

## 核心概念

### 1. Annotation API（替代 channels 定义）
LangGraph.js 最新版本引入了 `Annotation` 模式，比旧的 `channels` 定义更简洁：
```typescript
// 旧方式 - channels
const graphState: StateGraphArgs<IState>["channels"] = {
  input: { value: (x, y) => y ?? x ?? "", default: () => "" },
};

// 新方式 - Annotation（推荐）
import { Annotation, StateGraph, START, END } from "@langchain/langgraph";

const AgentState = Annotation.Root({
  messages: Annotation<BaseMessage[]>({ reducer: messagesReducer }),
  task: Annotation<string>,
  result: Annotation<string | null>({ default: () => null }),
});
```

### 2. Command 动态路由（替代 conditional_edges）
`Command` 对象允许节点直接返回路由指令，无需单独定义 `addConditionalEdges`：
```typescript
import { Command, StateGraph, START, END, Annotation } from "@langchain/langgraph";

const State = Annotation.Root({
  query: Annotation<string>,
  category: Annotation<string>,
});

// 节点直接通过 Command 控制流向
const classifier = (state: typeof State.State) => {
  const category = state.query.includes("code") ? "code_agent" : "chat_agent";
  return new Command({
    update: { category },
    goto: category,
  });
};

const graph = new StateGraph(State)
  .addNode("classifier", classifier, { ends: ["code_agent", "chat_agent", END] })
  .addNode("code_agent", async (state) => ({ result: `Code: ${state.query}` }))
  .addNode("chat_agent", async (state) => ({ result: `Chat: ${state.query}` }))
  .addEdge(START, "classifier")
  .addEdge("code_agent", END)
  .addEdge("chat_agent", END)
  .compile();
```

### 3. Node Caching（缓存节点结果）
LangGraph 支持节点级别的缓存，避免重复计算：
```typescript
import { CachePolicy, StateGraph, START, END, Annotation } from "@langchain/langgraph";
import { InMemoryCache } from "@langchain/langgraph";

const State = Annotation.Root({
  query: Annotation<string>,
  embedding: Annotation<number[]>,
});

const embeddingNode = async (state: typeof State.State) => {
  // 昂贵的嵌入计算
  const embedding = await computeEmbedding(state.query);
  return { embedding };
};

const graph = new StateGraph(State)
  .addNode("embed", embeddingNode, {
    cache_policy: new CachePolicy({ ttl: 300 }), // 缓存5分钟
  })
  .addEdge(START, "embed")
  .addEdge("embed", END)
  .compile({ cache: new InMemoryCache() });
```

## 可运行代码示例：OpenClaw Node Factory（最新 API）

```typescript
// createOpenClawNode.ts — 基于 LangGraph.js Annotation + Command
import {
  Annotation,
  Command,
  StateGraph,
  START,
  END,
  type CompiledStateGraph,
} from "@langchain/langgraph";
import { RunnableConfig } from "@langchain/core/runnables";

// ---- State 定义 ----
const OpenClawState = Annotation.Root({
  task: Annotation<string>,
  agentId: Annotation<string>,
  result: Annotation<string | null>({ default: () => null }),
  error: Annotation<string | null>({ default: () => null }),
  step: Annotation<number>({ default: () => 0, reducer: (a, b) => b }),
});

type State = typeof OpenClawState.State;

// ---- Executor 抽象（可替换为 sessions_spawn） ----
type Executor = (task: string, agentId: string) => Promise<string>;

const defaultExecutor: Executor = async (task, agentId) => {
  // 生产环境替换为: sessions_spawn({ runtime: "subagent", task, agentId })
  return `[${agentId}] 完成任务: ${task}`;
};

// ---- 工厂函数 ----
export function createOpenClawNode(
  agentId: string,
  executor: Executor = defaultExecutor
) {
  return async (state: State): Promise<Command> => {
    try {
      const result = await executor(state.task, agentId);
      return new Command({
        update: { result, step: state.step + 1 },
        goto: END,
      });
    } catch (err: any) {
      return new Command({
        update: { error: err.message, step: state.step + 1 },
        goto: "error_handler",
      });
    }
  };
}

// ---- 错误处理节点 ----
const errorHandler = (state: State): Command => {
  console.error(`Step ${state.step} error: ${state.error}`);
  // 重试一次或结束
  if (state.step < 2) {
    return new Command({ goto: "agent" });
  }
  return new Command({ goto: END });
};

// ---- 构建图 ----
export function buildOpenClawGraph(
  agentId: string,
  executor?: Executor
): CompiledStateGraph<State> {
  const agentNode = createOpenClawNode(agentId, executor);

  return new StateGraph(OpenClawState)
    .addNode("agent", agentNode, { ends: [END, "error_handler"] })
    .addNode("error_handler", errorHandler, { ends: [END, "agent"] })
    .addEdge(START, "agent")
    .compile();
}

// ---- 运行 ----
async function main() {
  const graph = buildOpenClawGraph("research-agent");

  const result = await graph.invoke({
    task: "搜索最新的 LangGraph 特性并总结",
    agentId: "research-agent",
    result: null,
    error: null,
    step: 0,
  });

  console.log("最终状态:", result);
  // 输出: { task: "...", agentId: "...", result: "[research-agent] 完成任务: ...", error: null, step: 1 }
}

// main().catch(console.error);

export { OpenClawState, createOpenClawNode, buildOpenClawGraph };
```

## 关键洞察

1. **Annotation > channels**: 新的 `Annotation.Root()` 模式比旧 `channels` 定义更类型安全、更简洁。`createOpenClawNode` 应基于 Annotation API。

2. **Command 消灭 conditional_edges**: 节点通过返回 `Command` 对象直接控制路由，比 `addConditionalEdges` 的路由函数更内聚。这意味着 OpenClaw agent 节点可以自行决定是否重试、切换 agent 或结束——路由逻辑封装在节点内部。

3. **Node Caching 为 OpenClaw 带来去重能力**: 当多个图路径可能触发相同的 agent 调用时，Node Caching 自动去重。这对 agent mesh 网络特别有价值——多个请求可能触发同一 research agent，缓存避免重复执行。

4. **工厂模式是官方推荐**: LangGraph 文档明确展示了 `makeGraphForUser()` 工厂模式（runtime rebuild），这验证了我们 `createOpenClawNode()` 工厂函数的设计方向。

5. **ends 声明是 Command 的安全网**: 使用 Command 时必须用 `{ ends: [...] }` 声明可能的跳转目标，编译器会验证所有路径。这比隐式的 conditional_edges 更安全。

## 与现有项目关联

- **lab/openclaw-langgraph-bridge/**: 本研究的代码示例可直接作为该项目的 v2 实现，用 Annotation + Command 替换之前的 channels + conditional_edges 方案
- **HEARTBEAT.md**: createOpenClawNode 已在待办中，本笔记提供了最新的 API 参考
- **A2A Trust Prototype**: Command 的动态路由可用于实现信任评分路由——高信任请求直接执行，低信任请求走审核节点

## 下一步行动

1. **在 lab/openclaw-langgraph-bridge/ 中实现 v2**: 使用 Annotation + Command 重写 createOpenClawNode，目标通过 3 个测试（invoke + stream + 动态复用）
2. **测试 Node Caching**: 在 agent mesh 场景下验证缓存效果，量化去重收益
3. **探索 subgraph composition**: 将 OpenClaw agent 作为 subgraph 嵌入更大的编排图中

## 参考资料

- [LangGraph.js Overview (官方)](https://docs.langchain.com/oss/javascript/langgraph/overview)
- [LangGraph Graph Rebuild Factory (官方)](https://docs.langchain.com/langsmith/graph-rebuild)
- [LangGraph Graph API + Node Caching (官方)](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Command in LangGraph.js (论坛讨论)](https://forum.langchain.com/t/is-command-on-js-ts-langgraph/1916)
- [LangGraph.js Concept Guide](https://dev.to/zand/langgraphjs-concept-guide-50g0)
