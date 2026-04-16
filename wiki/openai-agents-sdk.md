# OpenAI Agents SDK
> 足够有用但足够简单 — Python-first 的生产级 Agent 框架

## 一句话定义
OpenAI Agents SDK 是 Swarm 实验项目的生产级升级版，用极少量原语（Agent、Handoff、Tool、Guardrail）编排 Agent，支持 100+ LLM，不绑定 OpenAI。

## 核心原语

| 原语 | 作用 | 类比 |
|------|------|------|
| **Agent** | LLM + instructions + tools + handoffs | 一个有能力的员工 |
| **Handoff** | Agent 间任务转移 | 转接电话 |
| **Tool** | 外部能力调用 | 工具箱里的工具 |
| **Guardrail** | 输入/输出安全检查 | 安检门 |
| **Session** | 对话上下文管理 | 工作记忆 |

## Agent = LLM + 编排

```python
from agents import Agent, Runner

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant",
    tools=[web_search, file_read],
    handoffs=[research_agent, code_agent],
)

# Runner 是执行引擎，自动处理 tool call 循环
result = await Runner.run(agent, messages=[{"role": "user", "content": "..."}])
```

## Runner 执行循环

```
1. 发送消息给 LLM
2. LLM 返回 tool calls → 执行 tools → 结果回 LLM
3. 重复直到 LLM 不再调用 tools（任务完成）
4. 返回最终结果
```

## Handoff 模式（多 Agent 切换）

```python
research_agent = Agent(name="Research", handoff_description="Deep research tasks")
code_agent = Agent(name="Code", handoff_description="Code writing tasks")

triage_agent = Agent(
    name="Triage",
    instructions="Route to the right specialist",
    handoffs=[research_agent, code_agent],
)
```

**Handoff = function call** — LLM 自动决定何时转交任务给其他 Agent。

## 与其他框架对比

| 维度 | OpenAI Agents SDK | LangGraph | CrewAI |
|------|-------------------|-----------|--------|
| **学习曲线** | 极低 | 中 | 低 |
| **核心抽象** | 5 个原语 | 状态图 | 角色+任务 |
| **LLM 支持** | 100+ (via LiteLLM) | 任意 | 任意 |
| **内置安全** | ✅ Guardrail | ❌ | ❌ |
| **Tracing** | ✅ 内置 | ✅ LangSmith | ❌ |
| **语音 Agent** | ✅ gpt-realtime | ❌ | ❌ |

## 关键洞察

1. **Python-first** — 用语言原生特性编排，不学新抽象
2. **Handoff 是杀手级特性** — 自然的多 Agent 切换机制
3. **Guardrail 内置** — 安全不是附加，是核心原语
4. **不绑定 OpenAI** — 通过 LiteLLM 支持 100+ LLM
5. **Swarm 的生产版** — 从实验到产品的进化

## 关联
- [[multi-agent-framework-integration]] — 框架全景对比
- [[agent-security-safety]] — Guardrail 模式的安全实践
- [[agent-engineering]] — Agents SDK 体现的 Agentic Engineering 思想

---
_最后更新：2026-04-16_
