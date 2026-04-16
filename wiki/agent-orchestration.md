# Agent Orchestration
> 多 Agent 编排模式与最佳实践 — 11 种编排模式的选择指南

## 一句话定义
Agent 编排是将多个专业化 Agent 组合成协作系统的艺术，核心模式包括 Pipeline、Supervisor、Council、Router 等 11 种。

## 11 种编排模式

### 基础模式
| 模式 | 描述 | 适用场景 |
|------|------|---------|
| **Pipeline** | 串行执行，前一个输出是后一个输入 | 数据处理流水线 |
| **Fan-out/Fan-in** | 并行执行后聚合 | 多角度分析 |
| **Router** | 根据输入类型路由到不同 Agent | 多技能助手 |

### 协作模式
| 模式 | 描述 | 适用场景 |
|------|------|---------|
| **Supervisor** | 中心编排者分配任务 | 复杂多步骤任务 |
| **Council** | 多 Agent 投票决策 | 需要高可靠性的决策 |
| **Debate** | Agent 间辩论达成共识 | 需要多角度思考的问题 |

### 高级模式
| 模式 | 描述 | 适用场景 |
|------|------|---------|
| **Hierarchical** | 多层 Supervisor | 大规模任务 |
| **Blackboard** | 共享状态空间 | 知识密集型任务 |
| **Market** | 竞价分配任务 | 资源优化 |
| **Mesh** | 去中心化 P2P 协作 | 边缘计算 |
| **Evaluator-Optimizer** | 迭代改进循环 | 质量敏感任务 |

## 2026 默认选择：Supervisor

```
Supervisor (70B, 强推理)
  ├── Worker A (7B, 专业化)
  ├── Worker B (7B, 专业化)
  └── Worker C (7B, 专业化)
```

**为什么**: 简单、有效、可扩展。实际并发上限 ~8 个 Agent。

## 关联
- [[agent-engineering]] — 编排是 Agentic Engineering 的核心能力
- [[multi-agent-framework-integration]] — 各框架的编排实现
- [[a2a-protocol]] — 跨框架编排的通信标准
- [[openclaw-multi-agent-optimization]] — OpenClaw 的编排优化
- [[project-lessons]] — 编排实践中的经验教训

---
_最后更新：2026-04-16_
