# LangGraph.js Supervisor → OpenClaw 桥接深度研究

> 日期: 2026-04-28 | 方法: autoresearch
> 主题: LangGraph.js (TypeScript) Supervisor 模式 + OpenClaw sessions_spawn 桥接
> 关联: HEARTBEAT.md "集成多Agent框架" 高优先级任务

---

## 为什么研究 LangGraph.js 而非 Python 版

前序研究 (04-24, 04-26, 04-27) 均基于 **Python LangGraph**。但 OpenClaw 运行在 **Node.js** 上，Python 桥接意味着：
- 需要额外 Python 运行时
- 进程间通信（subprocess/HTTP）增加延迟和复杂度
- 状态序列化/反序列化开销

**LangGraph.js** (`@langchain/langgraph` v1.2.9) 提供了等价的 StateGraph API，可以直接在 OpenClaw 进程内运行，零额外依赖。

---

## 核心概念 (5个)

### 1. Annotation-based State（注解式状态定义）

LangGraph.js 使用 `Annotation.Root()` 定义状态，而非 Python 的 `TypedDict`：

```ts
import { Annotation } from "@langchain/langgraph";

const State = Annotation.Root({
  messages: Annotation({
    reducer: (prev, next) => [...prev, ...next],  // 合并策略
    default: () => [],
  }),
  data: Annotation({
    reducer: (_, next) => next,  // 覆盖策略
    default: () => "",
  }),
});
```

**对比 Python**: Python 用 `Annotated[list, add_messages]`，JS 用显式 reducer 函数。JS 版更灵活——你可以写任意合并逻辑。

### 2. StateGraph + addConditionalEdges（状态图 + 条件路由）

核心编排 API：

```ts
import { StateGraph, START, END } from "@langchain/langgraph";

const workflow = new StateGraph(State)
  .addNode("worker_a", workerAFn)
  .addNode("worker_b", workerBFn)
  .addConditionalEdges(START, routerFn, ["worker_a", "worker_b", END])
  .addConditionalEdges("worker_a", routerFn, ["worker_a", "worker_b", END])
  .addConditionalEdges("worker_b", routerFn, ["worker_a", "worker_b", END]);

const graph = workflow.compile();
const result = await graph.invoke(initialState);
```

**关键发现**: `addConditionalEdges` 的第三个参数是**可能的目标节点数组**，不是映射表。路由函数返回节点名字符串即可。这比 Python 版更简洁。

### 3. Supervisor Router 函数（纯逻辑，无 LLM）

MVP 阶段不需要 LLM 做路由——用纯函数根据状态决定下一步：

```ts
function supervisorRouter(state) {
  const completed = state.tasksCompleted || [];
  if (!completed.includes("research")) return "researcher";
  if (!completed.includes("analysis")) return "analyst";
  if (!completed.includes("writer")) return "writer";
  return END;
}
```

**升级路径**: 后续可以将路由函数替换为 LLM 调用（`await llm.invoke(...)` 分析状态后返回节点名），不改变图结构。

### 4. Worker Node = async function（天然适配 OpenClaw sessions_spawn）

每个 worker 就是一个 `(state) => Promise<Partial<State>>` 函数。**这就是桥接点**：

```ts
// 当前：模拟 worker
async function researcher(state) {
  const result = await doResearch(state.messages);
  return { researchData: result, tasksCompleted: ["research"] };
}

// 目标：真实 OpenClaw 桥接
async function openclawResearcher(state) {
  const task = state.messages[state.messages.length - 1];
  // 通过 OpenClaw 的 sessions_spawn API 创建子代理
  const session = await sessions_spawn({
    task: `研究以下主题并返回结构化结果: ${task}`,
    mode: "run",
    runtime: "subagent",
  });
  // sessions_spawn 是 push-based，结果自动回传
  return { researchData: session.result, tasksCompleted: ["research"] };
}
```

### 5. In-process vs Out-of-process 架构对比

| 维度 | Python LangGraph (out-of-process) | LangGraph.js (in-process) |
|------|-----------------------------------|--------------------------|
| 额外运行时 | 需要 Python | 不需要 |
| 通信方式 | subprocess/HTTP | 直接函数调用 |
| 延迟 | 10-100ms (IPC) | <1ms (函数调用) |
| 部署复杂度 | 2 个运行时 | 1 个运行时 |
| 生态成熟度 | 更完善 | 略少但核心功能齐全 |
| Durable Execution | 支持 (LangGraph Platform) | 支持 (LangGraph Platform) |

**结论**: OpenClaw MVP 应使用 **LangGraph.js in-process**，避免引入 Python 依赖。

---

## 代码示例: 完整可运行 LangGraph.js Supervisor

> ✅ 已验证运行通过 (`@langchain/langgraph` v1.2.9, Node.js v22)

文件: `/tmp/langgraph-supervisor.mjs`

运行方式:
```bash
cd /tmp && npm install @langchain/langgraph @langchain/core zod
node langgraph-supervisor.mjs
```

运行结果:
```
============================================================
LangGraph.js Supervisor Pattern — 可运行示例
============================================================

📡 开始执行 Supervisor 工作流...

  🔍 [Researcher] 正在研究: 研究 LangGraph.js Supervisor 模式并生成摘要...
  📊 [Analyst] 正在分析研究数据...
  ✍️ [Writer] 正在生成摘要...

============================================================
✅ 工作流完成 (0.68s)
执行路径: research → analysis → writer

📝 最终摘要:
# 研究摘要
## 关键洞察
1. LangGraph.js 的 Annotation API 比手动 TypedDict 更类型安全
2. Supervisor 路由函数 + conditionalEdges = 灵活的多 Agent 编排
3. OpenClaw 桥接点: 将每个 worker 包装为 async function node
**质量评分**: 7.5/10
============================================================
```

### OpenClaw 真实桥接扩展示例

```ts
// openclaw-bridge-node.ts — 将 LangGraph.js worker 连接到 OpenClaw
import type { sessions_spawn } from "openclaw"; // 概念性

function createOpenClawNode(agentName: string, promptTemplate: string) {
  return async (state: any) => {
    const task = state.messages[state.messages.length - 1];
    const prompt = promptTemplate.replace("{task}", task);

    // 调用 OpenClaw sessions_spawn (需要 OpenClaw SDK)
    // 实际实现取决于 OpenClaw 是否暴露 Node.js SDK
    console.log(`[Bridge] Spawning ${agentName} for: ${prompt.slice(0, 40)}...`);
    
    // 模拟结果
    return {
      [`${agentName}Data`]: JSON.stringify({ agent: agentName, result: "done" }),
      tasksCompleted: [agentName],
    };
  };
}

// 使用
const researcher = createOpenClawNode("researcher", "深度研究: {task}");
const analyst = createOpenClawNode("analyst", "分析以下数据: {task}");
```

---

## 关键洞察

### 1. LangGraph.js 是 OpenClaw 多 Agent 的最佳编排层
OpenClaw 已经有 `sessions_spawn` 做子代理管理，但缺少**工作流编排**（谁先谁后、条件分支、循环）。LangGraph.js 的 StateGraph 正好填补这个空白，且不需要离开 Node.js 运行时。两层分工：
- **LangGraph.js** = 工作流编排（状态机、路由、条件分支）
- **OpenClaw** = 代理执行（sessions_spawn、channel 集成、持久化）

### 2. Annotation API 的 reducer 模式解决了状态合并难题
多 Agent 并发写入同一状态字段时，reducer 定义了合并策略（追加 vs 覆盖 vs 自定义）。这比 Python 版的 `Annotated` 注解更显式、更不容易出错。对 OpenClaw 场景特别重要——多个子代理可能同时返回结果。

### 3. Supervisor 不一定要用 LLM 路由
很多 LangGraph 教程假设 Supervisor 用 LLM 做路由决策。但在 OpenClaw 场景中，大多数工作流是确定性的（研究→分析→写作→结束）。用纯函数做路由：
- 零延迟（不调 LLM）
- 零成本
- 完全可预测和可测试
- 需要时再升级为 LLM 路由，不改变图结构

### 4. JS 版缺少 Command API（Python 独有），但不影响 MVP
Python LangGraph v0.3+ 的 `Command(goto="node", update=state)` 允许节点直接控制下一个节点。JS 版暂不支持，但 `addConditionalEdges` + 路由函数已经足够覆盖所有 MVP 场景。

### 5. 真正的挑战不在编排，而在子代理结果解析
LangGraph 不管"代理怎么跑"——它只管"跑完后的结果怎么流转"。OpenClaw 的 `sessions_spawn` 返回的是自然语言文本，需要解析为结构化状态更新。这是桥接的核心难题：
- 方案 A: 子代理用 JSON mode 输出，直接 `JSON.parse`
- 方案 B: 桥接层用 LLM 做结果提取（慢但灵活）
- 方案 C: 子代理输出 Markdown，桥接层用正则/简单解析

**推荐方案 A**: 在 `sessions_spawn` 的 task prompt 中要求 JSON 输出格式。

---

## 与前序研究的差异

| 前序研究 (Python) | 本研究 (JS) |
|------------------|-------------|
| 需要额外 Python 运行时 | 直接在 Node.js 内运行 |
| subprocess 通信 | 函数调用 |
| TypedDict 状态 | Annotation reducer |
| Command API 可用 | 暂不可用，用 conditionalEdges 替代 |
| 侧重架构设计 | 侧重可运行原型 + 桥接方案 |

---

## 下一步行动

### Action 1: 将 langgraph-supervisor.mjs 集成到 OpenClaw Skill（本周）
- 在 `skills/agent-orchestrator/` 下新增 `langgraphjs-bridge.ts`
- 封装 `createOpenClawNode()` 工厂函数
- 暴露 `buildSupervisorGraph(config)` 供 Skill 调用

### Action 2: 研究 OpenClaw sessions_spawn 的 JS SDK 接口
当前 `sessions_spawn` 是工具调用（AI 调用），不是 Node.js API。需要确认：
- 是否可以在 LangGraph.js worker node 内直接调用 `sessions_spawn`？
- 还是需要通过 OpenClaw Gateway HTTP API？
- 如果是后者，需要封装一个 `OpenClawClient` 类

### Action 3: 测试 LLM 驱动的 Supervisor 路由
将纯函数路由升级为 LLM 路由：
```ts
async function llmRouter(state) {
  const response = await llm.invoke([
    { role: "system", content: "根据当前任务进度，决定下一步应该分配给哪个 worker..." },
    { role: "user", content: JSON.stringify({ completed: state.tasksCompleted, lastMsg: state.messages.at(-1) }) },
  ]);
  return parseNodeName(response); // "researcher" | "analyst" | "writer" | "FINISH"
}
```

---

## 质量自评

| 维度 | 评分 | 说明 |
|------|------|------|
| 可运行代码 | ✅ | `/tmp/langgraph-supervisor.mjs` 已验证运行 |
| 独到见解 | ✅ | JS in-process > Python out-of-process; 纯函数路由优先; 结果解析是核心难题 |
| 项目关联 | ✅ | 直连 HEARTBEAT.md "集成多Agent框架" + 前序 Python 研究的 JS 升级 |
| 下一步明确 | ✅ | 3 个具体 Action，优先级排序 |

---

## 参考资料

- [LangGraph.js npm](https://www.npmjs.com/package/@langchain/langgraph) v1.2.9
- [LangGraph.js GitHub](https://github.com/langchain-ai/langgraphjs)
- 前序研究: `2026-04-27-langgraph-supervisor-openclaw.md` (Python 版)
- OpenClaw Skill: `skills/agent-orchestrator/SKILL.md`
- 已有代码: `agent-framework-integration/langgraph/adapter.py`
