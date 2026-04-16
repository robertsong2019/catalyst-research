# 深度探索：OpenAI Agents SDK 架构与模式

> 日期：2026-04-04 | 方向：AI Agent 编程 | 耗时：~1.5h

---

## 一、SDK 定位

OpenAI Agents SDK 是 Swarm 实验项目的生产级升级版。设计哲学：**足够有用但足够简单**。

核心价值：
- Python-first，用语言原生特性编排 agent，不学新抽象
- 极少量原语：Agent、Handoff、Tool、Guardrail、Session
- 内置 tracing（可视化调试）
- 支持 100+ LLM（通过 LiteLLM / any-llm），不绑定 OpenAI
- 支持实时语音 Agent（gpt-realtime-1.5）

安装：`pip install openai-agents`

---

## 二、核心原语

### 2.1 Agent
Agent = LLM + instructions + tools + handoffs + guardrails

```python
agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant",
    tools=[...],
    handoffs=[...],
)
```

### 2.2 Runner
Runner 是执行引擎，负责 agent loop：
1. 发送消息给 LLM
2. LLM 返回 tool calls → 执行 tools → 结果回 LLM
3. 重复直到 LLM 不再调用 tools（任务完成）

```python
result = Runner.run_sync(agent, "Hello")
result = await Runner.run(agent, "Hello")  # 异步
```

### 2.3 Tools（五类）

| 类型 | 说明 |
|------|------|
| Hosted tools | WebSearch, FileSearch, CodeInterpreter, ImageGen, HostedMCP — OpenAI 服务器端运行 |
| Local runtime tools | ComputerTool, ApplyPatchTool, ShellTool — 本地执行 |
| Function tools | 任意 Python 函数，自动生成 schema + Pydantic 校验 |
| Agents as tools | `Agent.as_tool()` — 一个 agent 当工具调用，不转移控制权 |
| Codex tool | 实验性：在 tool call 中运行 Codex 任务 |

**亮点：ToolSearchTool** — 延迟加载工具。大量工具时，模型按需搜索加载，节省 token。配合 `tool_namespace()` 分组。

### 2.4 Handoffs（交接）

Handoff = agent 之间转移控制权。对 LLM 来说，handoff 表现为一个 tool（如 `transfer_to_refund_agent`）。

两种编排模式：

**Agents as Tools（管理者模式）**：
- Manager agent 保持对话控制权
- 调用专家 agent 获取结果，自己组织最终回复
- 适合：需要统一输出、组合多个专家结果

**Handoffs（路由模式）**：
- Triage agent 路由到专家，专家接管后续交互
- 适合：专家需要直接面对用户、各自 prompt 独立

可混合使用：triage → handoff 到专家 → 专家调用其他 agent as tool。

Handoff 高级特性：
- `input_type`：让 LLM 在交接时传递结构化数据（如 reason、priority）
- `input_filter`：控制交接后新 agent 看到多少历史对话
- `on_handoff` 回调：交接时触发（可做日志、预加载）
- `is_enabled`：动态启用/禁用交接

### 2.5 Guardrails（护栏）

三层防护：

**Input guardrails**：检查用户输入
- 并行模式（默认）：与 agent 同时运行，延迟低但可能已消耗 token
- 阻塞模式：先跑完 guardrail 再启动 agent，省钱

**Output guardrails**：检查 agent 输出

**Tool guardrails**：每次 function tool 调用前后检查
- Input tool guardrail：可跳过、替换输出、触发 tripwire
- Output tool guardrail：可替换输出、触发 tripwire

工作流边界：
- Input guardrails 只在 chain 第一个 agent 运行
- Output guardrails 只在产生最终输出的 agent 运行
- Tool guardrails 每次调用都跑

Tripwire 触发后立即抛异常，中止执行。

### 2.6 Sessions

持久化记忆层，跨 turn 维护对话上下文。支持 Redis 后端。

---

## 三、架构模式总结

### 模式 1：单 Agent + Tools
最简单。一个 agent 配多个 tools 完成任务。

### 模式 2：Manager + Specialists（Agents as Tools）
```
Manager Agent
  ├── Specialist A (as tool)
  ├── Specialist B (as tool)
  └── Specialist C (as tool)
```
Manager 控制全局，调用专家获取子结果。

### 模式 3：Triage + Handoffs
```
Triage Agent ─handoff→ Billing Agent
                  ─handoff→ Refund Agent
                  ─handoff→ FAQ Agent
```
路由后专家接管对话。

### 模式 4：Pipeline（代码编排）
```python
# 研究agent → 大纲agent → 写作agent → 审阅agent → 改进agent
outline = await Runner.run(outline_agent, research_result)
draft = await Runner.run(writer_agent, outline)
...
```

### 模式 5：Parallel（代码编排）
```python
results = await asyncio.gather(
    Runner.run(agent_a, input),
    Runner.run(agent_b, input),
)
```

### 模式 6：Evaluator-Optimizer Loop
```python
while True:
    result = await Runner.run(worker, task)
    review = await Runner.run(evaluator, result)
    if review.passes:
        break
    task = review.feedback
```

---

## 四、与 OpenClaw 的对比思考

| 维度 | OpenAI Agents SDK | OpenClaw |
|------|-------------------|----------|
| 语言 | Python | Node.js/TypeScript |
| 模型支持 | 100+ via LiteLLM | 多模型 |
| Agent 间通信 | Handoffs + as_tool | sessions_spawn, sessions_send |
| 工具协议 | OpenAI tools + MCP | MCP + 原生 tools |
| 记忆 | Sessions (Redis) | MEMORY.md + memory/ 文件 |
| 调度 | 无内置 | Cron jobs |
| 护栏 | Guardrails (input/output/tool) | 系统提示 + policy |
| Tracing | 内置 | Session history |
| 语音 | gpt-realtime-1.5 | TTS |

OpenClaw 更像是一个**持久化个人助手平台**（文件记忆 + cron + 多渠道），而 Agents SDK 更像是一个**构建 agent 应用程序的框架**。两者定位不同但互补。

---

## 五、关键收获

1. **Agent 编程的核心抽象已经很收敛**：Agent + Tools + Handoffs + Guardrails 四个概念覆盖大部分场景
2. **Tool Search 是解决工具爆炸的好思路**：延迟加载 + namespace 分组，大量工具时节省 token
3. **Guardrails 的三层设计很实用**：input/output/tool 三层，并行/阻塞两种模式，灵活度很高
4. **代码编排 vs LLM 编排**：确定性任务用代码编排（pipeline/parallel/loop），开放式任务让 LLM 自主决策（handoffs）
5. **Sessions 作为一等公民**：对话状态持久化是生产级 agent 的刚需

---

## 六、后续探索方向

- [ ] 对比 LangGraph 的图编排模式（状态机 vs Agents SDK 的扁平模型）
- [ ] 研究 Google ADK（Agent Development Kit）
- [ ] 实践：用 Agents SDK 构建一个小型多 agent 应用
- [ ] 深入 MCP 协议在 agent 框架中的集成方式
