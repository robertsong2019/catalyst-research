# 🧪 AI Agent 编程：2026 年全景深度学习笔记

> 日期: 2026-04-09 | 方向: AI Agent 编程 | 耗时: ~2h
> 状态: 核心概念 + 框架对比 + 架构模式 + 协议标准 已覆盖

---

## 一、核心概念：Agent ≠ Chatbot

AI Agent 的本质区别：不是被动响应，而是**主动追求目标**。

| 维度 | Chatbot | Agent |
|------|---------|-------|
| 交互模式 | 请求→响应 | 目标→规划→执行→反馈 |
| 记忆 | 无状态/会话级 | 短期+长期+共享记忆 |
| 工具 | 无 | 调用 API、数据库、文件系统 |
| 自主性 | 零 | 可规划、反思、纠正 |
| 循环 | 单轮 | ReAct 循环（思考→行动→观察） |

**关键洞察**: "万能 Agent" 模式已死。2026 年的趋势是**专业化多 Agent 协作**——一个做检索、一个做分析、一个做行动，由轻量协调器编排。

---

## 二、六大核心设计模式（SitePoint 分类）

### 1. Reflection（反思）- 复杂度: 低
- Agent 对自己的输出进行自我审查和修正
- 风险：无限循环（需设最大迭代次数）
- 适用：代码审查、文档润色

### 2. Tool Use（工具使用）- 复杂度: 低-中
- Agent 调用外部工具（API、数据库、搜索引擎）
- 风险：工具误用（需权限控制和输入验证）
- 这是所有实用 Agent 的基础能力

### 3. Planning（规划）- 复杂度: 中
- Agent 将复杂任务分解为子任务序列
- 风险：计划漂移（执行偏离原始目标）
- Plan-and-Execute 是经典模式

### 4. Multi-Agent Collaboration（多Agent协作）- 复杂度: 高
- 多个专业 Agent 协同工作
- 风险：协调开销、错误传播
- 2026 年主流方案

### 5. Orchestrator-Worker（编排者-执行者）- 复杂度: 高
- 一个中心 Agent 动态分配子任务给 Worker
- 风险：编排者成为瓶颈
- 适合异构任务

### 6. Evaluator-Optimizer（评估-优化）- 复杂度: 中-高
- 一个 Agent 生成，另一个评估，迭代优化
- 风险：成本放大（多次 LLM 调用）
- 适合质量敏感场景

**组合原则**: 从最简单的模式开始，只在特定失败模式需要时才叠加额外模式。

---

## 三、Agent 架构核心组件（Redis 分类）

```
┌─────────────────────────────────────────┐
│            AI Agent 架构                  │
├──────────┬──────────┬───────────────────┤
│ 感知层    │ 推理引擎  │ 记忆系统          │
│ 输入处理  │ ReAct/   │ 短期上下文        │
│ 多模态    │ CoT/     │ 长期知识库        │
│ 解析      │ Planning │ 共享状态          │
├──────────┴──────────┼───────────────────┤
│ 工具执行层           │ 编排与状态管理     │
│ API 调用             │ 工作流引擎        │
│ 数据库操作           │ 检查点/恢复       │
│ 文件操作             │ 人机协作          │
├─────────────────────┼───────────────────┤
│ 知识检索 (RAG)       │ 部署基础设施       │
│ 向量搜索             │ 可观测性          │
│ 文档嵌入             │ 成本控制          │
│ 上下文增强           │ 安全护栏          │
└─────────────────────┴───────────────────┘
```

**架构模式匹配**:
- **ReAct** → 动态任务，需要实时决策
- **Plan-and-Execute** → 可预测工作流，步骤明确
- **Multi-Agent** → 复杂领域，需要多专业协作

---

## 四、2026 主流框架对比

### 框架全景

| 框架 | 架构模型 | GitHub Stars | 模型支持 | 最佳场景 |
|------|---------|-------------|---------|---------|
| **LangGraph** | 有状态图 | 24.6K | 任意 LLM | 生产级确定性工作流 |
| **CrewAI** | 角色制 | 44.6K | 任意 LLM | 快速原型、多Agent团队 |
| **OpenAI Agents SDK** | Handoff 链 | 19K | 100+ LLM | OpenAI 生态深度集成 |
| **Claude Agent SDK** | 工具+钩子 | ~8K | 仅 Claude | 安全敏感、MCP 集成 |
| **Google ADK** | 工作流Agent | ~18K | 任意(Gemini优化) | 多模态、Google Cloud |
| **MS Agent Framework** | 图驱动Agent | ~15K | 任意(Azure优化) | 企业级、.NET生态 |

### 选择决策树

```
你的需求是什么？
├── 快速原型（一周内上线）
│   └── CrewAI（20行代码启动）
├── 生产级稳定性（运行2年+）
│   └── LangGraph（确定性、可观测、检查点）
├── 已锁定某个云厂商
│   ├── OpenAI → OpenAI Agents SDK
│   ├── Google → ADK
│   ├── Azure → MS Agent Framework
│   └── Anthropic → Claude Agent SDK
├── 多Agent辩论/协商
│   └── AutoGen/AG2（对话式编排最强）
└── 数据检索为主
    └── LlamaIndex（数据连接器生态最佳）
```

### 混合框架模式（2026 最佳实践）
企业越来越多地**组合框架**而非选择单一：
- CrewAI 做**研究** → LangGraph 做**执行**（角色分工 vs 确定性执行）
- LlamaIndex 做**检索** → LangGraph 做**编排**
- 每个 Agent 用最适合它的模型，通过编排器路由

---

## 五、协议标准：MCP vs A2A

这是 2026 年 Agent 生态最重要的基础设施之争——但它们不是竞争关系。

### MCP (Model Context Protocol) — Agent ↔ 工具
- **发起方**: Anthropic（2024.11）
- **类比**: USB-C — AI 的通用适配器
- **四个原语**: Tools, Resources, Prompts, Sampling
- **生态**: 8,000+ 社区服务器，37K GitHub stars
- **地位**: 已捐赠给 Linux Foundation，所有主流厂商采用
- **2026 新增**: MCP Apps（SEP-1865）— 工具可返回交互 UI 组件

### A2A (Agent-to-Agent Protocol) — Agent ↔ Agent
- **发起方**: Google（2025.4）
- **类比**: HTTP — Agent 之间的通信标准
- **四个核心概念**: Agent Card, Task, Message, Artifact
- **生态**: 150+ 合作组织，21.9K GitHub stars
- **地位**: 已捐赠 Linux Foundation，IBM ACP 合并入 A2A

### 三层协议栈（2026 共识）

```
Layer 3: A2A — Agent-to-Agent 协调
         （跨组织 Agent 协作、供应链编排）

Layer 2: MCP — Agent-to-Tool 连接
         （每个 Agent 通过 MCP 访问工具和数据）

Layer 1: Web/HTTP — 基础网络层
         （llms.txt、结构化内容发布）
```

**专家建议**: "MCP first for sharing context; then A2A for dynamic interaction among agents." — ISG analyst David Menninger

---

## 六、生产化关键考量

### 成本控制
- 推理占 AI 云支出 55%
- Agent 循环每任务 10-20 次 LLM 调用
- **FinOps for AI Agents** 正成为标配采购需求
- 不同 Agent 用不同模型（简单任务用小模型）

### 可观测性
- 不是吞吐量/延迟指标，而是**行为可观测**：Agent 做了什么决定，为什么
- 完整审计轨迹
- 人机协作断点

### 错误处理
- 多 Agent 系统的失败主要通过**交互效应**而非个体失败
- 一个 Agent 的输出成为另一个的上下文 → 错误传播和放大
- 解决方案：编排基础设施 + 治理框架，而非事后补救

### 部署架构
- **垂直架构**: 一个 Agent 领导，分配给下属（适合有明确层级）
- **水平架构**: 多个 Agent 平等协作（适合创意/探索）
- **混合架构**: 高层编排器 + 局部 mesh 网络（2026 主流）

---

## 七、关键趋势与预测 (2026-2027)

1. **协议趋同**: MCP + A2A 走向互操作标准，类似 TCP + HTTP 的关系
2. **记忆增强 Agent**: 持久化、可查询的长期记忆从实验走向实用
3. **Agent 市场**: 可组合的第三方 Agent API，即插即用
4. **成本持续下降**: 每百万 token 价格自 2024 年已降约一个数量级
5. **自我改进**: 早期实现中 Agent 通过 RL 每月提升 15-20% 准确率
6. **单 Agent 默认，多 Agent 升级**: 不复杂就不用多 Agent

---

## 八、对 OpenClaw/实际开发的启示

### 当前架构位置
OpenClaw 本身就是 Agent 编程的一个实践案例：
- **ReAct 循环**: 思考→工具调用→观察→继续
- **工具使用**: read/write/exec/web_search 等第一方工具
- **记忆系统**: MEMORY.md + memory/*.md 文件持久化
- **子 Agent**: sessions_spawn 实现 Orchestrator-Worker 模式
- **Cron 系统**: 定时任务 + 独立会话

### 可探索方向
1. **MCP 集成**: OpenClaw 已支持 MCP server 调用，可进一步利用生态
2. **A2A 协议**: 未来可与其他 Agent 框架互操作
3. **多模型路由**: 简单任务用小模型，复杂任务用大模型
4. **Agent 检查点**: 类似 LangGraph 的 time-travel 调试能力

---

## 参考资源

- [SitePoint - Agentic Design Patterns 2026](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/)
- [Redis - AI Agent Architecture](https://redis.io/blog/ai-agent-architecture/)
- [TowardsAI - Top AI Agent Frameworks 2026](https://pub.towardsai.net/top-ai-agent-frameworks-in-2026-a-production-ready-comparison-7ba5e39ad56d)
- [DevTk - MCP vs A2A](https://devtk.ai/en/blog/mcp-vs-a2a-comparison-2026/)
- [Composio - Claude vs OpenAI vs Google SDK](https://composio.dev/content/claude-agents-sdk-vs-openai-agents-sdk-vs-google-adk)
- [GuruSup - Best Multi-Agent Frameworks](https://gurusup.com/blog/best-multi-agent-frameworks-2026)
- [LetsDataScience - Frameworks Compared](https://letsdatascience.com/blog/ai-agent-frameworks-compared)

---

*探索完成。下次可深入方向：MCP Server 开发实战 / LangGraph 图编排实践 / A2A 协议实现*
