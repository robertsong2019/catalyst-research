# 12-Factor Agents
> 可靠 LLM 应用的 12 条设计原则 — 从经验到方法论

## 一句话定义
12-Factor Agents 是一套可靠 LLM 应用的设计原则，借鉴 12-Factor App 理念，为 AI Agent 的架构设计提供标准化指导。

## 核心原则

### 1. Agent 是状态机，不是对话
Agent 的核心是状态转换，不是简单的对话轮次。每个状态有明确的转移条件和动作。

### 2. 工具是 Agent 的手脚
工具定义了 Agent 能做什么。好的工具设计：输入明确、输出结构化、错误可恢复。

### 3. 上下文窗口是最宝贵的资源
- 精心管理上下文内容
- 动态调整上下文窗口
- 避免无关信息污染

### 4. 拥抱不确定性
LLM 本质上是概率模型。设计时要考虑：
- 输出可能不正确
- 需要验证和重试机制
- 关键操作需要人类确认

### 5. 提示词是代码
- 版本控制
- 测试覆盖
- 渐进式优化

### 6. 观测性是必需品
- 记录所有 LLM 交互
- 追踪 Agent 决策路径
- 可回溯、可审计

## 设计模式

### 状态机模式
```python
class AgentStateMachine:
    STATES = ["idle", "thinking", "acting", "waiting_input", "done"]
    
    def transition(self, current, event):
        transitions = {
            ("idle", "start"): "thinking",
            ("thinking", "tool_call"): "acting",
            ("acting", "result"): "thinking",
            ("thinking", "done"): "done",
            ("thinking", "need_input"): "waiting_input",
        }
        return transitions.get((current, event), current)
```

### Guardrail 模式
```python
def safe_execute(tool, args, permissions):
    if not permissions.allows(tool, args):
        raise PermissionError(f"Tool {tool} not allowed")
    result = tool(**args)
    if is_sensitive(result):
        result = redact(result)
    return result
```

## 关键洞察

1. **可靠性 > 能力** — 企业环境中，可靠系统比聪明系统更有价值
2. **状态管理是核心** — 好的状态设计 = 好的 Agent
3. **上下文是瓶颈** — 管好上下文就管好了 Agent
4. **可观测性不可妥协** — 无法观测就无法改进

## 关联
- [[agent-engineering]] — 12-Factor Agents 是 Agentic Engineering 的基础
- [[agent-security-safety]] — 安全原则的具体实践
- [[harness-engineering]] — Harness 是 12-Factor 思想的延伸
- [[ai-rapid-prototyping]] — 快速原型也需要遵循 12-Factor

---
_最后更新：2026-04-16_
