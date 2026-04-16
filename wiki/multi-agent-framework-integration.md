# Multi-Agent Framework Integration
> 多 Agent 框架全景：LangGraph、CrewAI、Google ADK、A2A 的选择与集成

## 一句话定义
2026 年多 Agent 编排的三种范式（Graph/Crew/Chat），Supervisor 模式成为默认，A2A 协议解决跨框架互操作。

## 编排三范式

| 范式 | 代表 | 核心抽象 | 适用场景 |
|------|------|---------|---------|
| **Graph** | LangGraph | 状态图 + checkpointer | 复杂工作流、需中断/恢复 |
| **Crew** | CrewAI | 角色化团队 | 快速原型、小团队协作 |
| **Chat** | AutoGen | 对话驱动 | 需要反复讨论的任务 |

## Supervisor 模式（2026 年默认选择）

```
┌─────────────────┐
│   Supervisor     │  ← 70B 模型，强推理
│   (规划/决策)     │
└──┬──┬──┬──┬─────┘
   │  │  │  │
   ▼  ▼  ▼  ▼
  W1 W2 W3 W4     ← 7B 模型，专业化执行
```

**算力分配策略：70B supervisor + 7B workers > 四个 32B agents**

核心思想：推理与执行分离，把"聪明"的钱花在决策上。

## 零依赖 Supervisor（10 行核心代码）

```python
class Supervisor:
    def __init__(self, workers: dict):
        self.workers = workers  # {"research": worker_fn, "code": worker_fn}

    def run(self, task: str) -> str:
        # 1. 规划：决定哪个 worker 做什么
        plan = self._plan(task)  # [{"worker": "research", "input": "..."}, ...]
        
        # 2. 执行：路由到对应 worker
        results = []
        for step in plan:
            result = self.workers[step["worker"]](step["input"])
            results.append(result)
        
        # 3. 综合：汇总所有结果
        return self._synthesize(task, results)
```

## 框架对比

| 维度 | LangGraph | CrewAI | Google ADK |
|------|-----------|--------|------------|
| **核心抽象** | 状态图 | 角色+任务 | Agent+工具 |
| **状态管理** | ✅ checkpointer | ❌ 无持久化 | ✅ 内置 |
| **生产就绪** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **学习曲线** | 中 | 低 | 中 |
| **A2A 支持** | ✅ | ✅ | ✅ 原生 |
| **最佳场景** | 复杂工作流 | 快速原型 | Google 生态 |

## 关键洞察

1. **Supervisor 10 行搞定编排** — 不需要复杂框架
2. **状态管理是差异化关键** — LangGraph 的 checkpointer 是核心竞争力
3. **框架混合使用成常态** — 用 A2A 协议桥接不同框架
4. **实际并发上限 ~8 个 agent** — 超了协调开销 > 收益
5. **算力分层优于均分** — 70B+7B×4 > 32B×4

## 与 OpenClaw 的关联
- OpenClaw sessions_spawn ≈ Supervisor 模式
- 可用 LangGraph/CrewAI 桥接 OpenClaw
- A2A 协议实现跨框架 Agent 发现和任务委派

## 关联
- [[a2a-protocol]] — 跨框架通信标准
- [[mcp-protocol]] — 工具访问标准
- [[agent-engineering]] — 多 Agent 是 Agentic Engineering 的核心
- [[agent-orchestration]] — 编排模式的详细分析

---
_最后更新：2026-04-16_
