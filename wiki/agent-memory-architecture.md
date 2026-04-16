# Agent Memory Architecture
> 从 RAG 到 Agent Memory 的范式转变 — 三层存储 + 混合架构

## 一句话定义
Agent Memory 是主动管理的认知系统（而非被动检索的 RAG），采用三层存储（短期/中期/长期）+ 混合存储（Vector+Graph+Structured），实现连续性、个性化和学习能力。

## 范式转变：RAG → Agent Memory

| 维度 | RAG | Agent Memory |
|------|-----|-------------|
| **模式** | 被动检索 | 主动管理 |
| **生命周期** | 无 | Generation → Evolution → Archival |
| **结构** | 扁平向量 | 分层 + 图谱 + 结构化 |
| **遗忘** | 无 | 艾宾浩斯遗忘曲线 |
| **目标** | 找到相关信息 | 维护 Agent 的认知连续性 |

## 三层存储模型

```
┌──────────────────────────────┐
│  L0 Core (永不过期)           │  ← 身份、核心偏好、关键决策
├──────────────────────────────┤
│  L1 Long (30天半衰期)         │  ← 长期记忆、合并后的洞察
├──────────────────────────────┤
│  L2 Short (1天半衰期)         │  ← 会话上下文、临时信息
└──────────────────────────────┘
```

衰减机制：艾宾浩斯遗忘曲线 + 访问增强（recall 即复习）

## 混合存储架构

```
Vector DB (语义搜索) ─┐
                       ├→ 混合查询 → 排序融合
Graph DB (关系推理) ───┤
                       │
Structured DB (事实) ──┘
```

- **Vector DB**: "哪些记忆和 X 语义相似？"
- **Graph DB**: "A 和 B 什么关系？"
- **Structured DB**: "上次的决策是什么？"

## 框架对比（2026-04）

| 框架 | ⭐ | LongMemEval | 特点 |
|------|-----|------------|------|
| **Mem0** | 48K+ | 49.0% | 最大生态，Vector+Graph |
| **Hindsight** | 4K+ | **91.4%** | 多策略混合检索，最高准确率 |
| **Letta** | 21K+ | - | OS 启发分层记忆，Agent 自主管理 |
| **Zep** | 24K+ | - | 时间知识图谱，时间推理领先 |

**关键数据**: Hindsight 91.4% > Full-context 72.9% > Mem0 66.9%
但 Mem0 在准确率/延迟/成本间最佳平衡。

## 六大核心设计模式

1. **Reflection（反思）** — Agent 自我评估输出质量
2. **Tool Use（工具使用）** — Agent 调用外部工具扩展能力
3. **Planning（规划）** — 分解复杂任务为步骤
4. **Multi-Agent（多Agent）** — 多个专业化 Agent 协作
5. **Orchestrator-Worker（编排-工作）** — Supervisor 模式
6. **Evaluator-Optimizer（评估-优化）** — 迭代改进循环

## 关键洞察

1. **Memory 是 Agent 的灵魂** — 无 Memory = 无状态，Memory 赋予连续性
2. **架构 > 算法** — 混合架构是生产级系统的唯一可行路径
3. **可靠性 > 能力** — 企业环境中，可靠系统比稍强模型更有价值
4. **Memory ≠ Vector DB** — 向量数据库只是记忆的一个组件

## 与 OpenClaw 的关联
- OpenClaw 记忆系统：MEMORY.md（长期）+ memory/YYYY-MM-DD.md（短期）
- Agent Memory Service (v0.6.0, 90/90 tests) 实现了三层存储
- 可考虑添加中期记忆层和知识图谱关系

## 关联
- [[agent-engineering]] — 知识库 vs 记忆的本质区别
- [[multi-agent-framework-integration]] — 多 Agent 中的记忆共享
- [[agent-engineering]] — Memory 是 Agent 的核心能力
- [[project-lessons]] — 各项目的经验教训
- [[prompt-engineering-evolution]] — 记忆能力是 Agentic Engineering 的进化点

---
_最后更新：2026-04-16_
