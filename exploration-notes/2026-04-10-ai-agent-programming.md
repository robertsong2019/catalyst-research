# AI Agent 编程：深度学习笔记

> 日期：2026-04-10 | 方向：AI Agent 编程框架与架构模式
> 来源：Tavily 搜索 + 多篇深度文章研读（约2小时）

---

## 一、核心概念：什么是 AI Agent？

AI Agent ≠ Chatbot。关键区别在于：

1. **推理循环（Reasoning Loop）**：不仅生成文本，还能思考、规划、自我修正
2. **工具调用（Tool Use）**：能调用外部 API、数据库、搜索引擎
3. **记忆系统（Memory）**：短期上下文 + 长期知识存储
4. **自主执行（Autonomy）**：多步骤任务无需人类每步干预

### Agent 的四大架构组件

| 组件 | 作用 |
|------|------|
| 推理引擎 | 解释目标、做决策 |
| 工具编排 | 访问外部 API/数据库/服务 |
| 记忆系统 | 短期上下文 + 长期知识 |
| 规划与反馈循环 | 评估结果、调整策略 |

---

## 二、六大经典设计模式（Agentic Design Patterns）

这些模式可以组合使用，生产系统通常叠合 2-3 个：

### 1. Reflection（反思）— 复杂度：低
- Agent 自我审查输出，发现并修正错误
- 风险：可能陷入无限循环
- 适用：代码审查、文案优化

### 2. Tool Use（工具使用）— 复杂度：低-中
- Agent 调用外部工具完成具体任务
- 关键问题：当工具超过 50 个时，需要动态工具加载（embedding 检索 top-k 相关工具）
- 适用：搜索、计算、API 调用

### 3. Planning（规划）— 复杂度：中
- **ReAct**：思考→行动→观察，每步交替进行。适合探索性任务
- **Plan-and-Execute**：先制定完整计划，再逐步执行。适合确定性多步任务
- 两者区别：ReAct 依赖观察调整下一步，Plan-and-Execute 依赖前置规划
- 风险：计划漂移（Plan Drift）

### 4. Multi-Agent（多智能体）— 复杂度：高
- 多个专业化 Agent 协作完成复杂任务
- 模式类比：研究员 → 分析师 → 写作者 → 审稿人
- 风险：协调开销大

### 5. Orchestrator-Worker（编排者-工人）— 复杂度：高
- 中心编排者动态分配子任务给专业 Worker
- 与 Multi-Agent 的区别：更强调中央控制
- 风险：编排者成为瓶颈

### 6. Evaluator-Optimizer（评估者-优化者）— 复杂度：中-高
- 一个 Agent 生成，另一个评估反馈，迭代优化
- 适用：质量关键型输出
- 风险：成本放大（多次 LLM 调用）

---

## 三、2026 主流框架对比

### 框架全景

| 框架 | 编排范式 | 核心优势 | 最佳场景 | 复杂度 |
|------|---------|---------|---------|--------|
| **LangGraph** | 有向图/状态机 | 精确控制、checkpointing、时间旅行调试 | 复杂有状态工作流、生产系统 | 高 |
| **CrewAI** | 角色团队 | 最快原型、直觉化 API | 快速多 Agent 原型、业务自动化 | 低-中 |
| **OpenAI Agents SDK** | 委托/Handoff | 极简、内置 tracing | OpenAI 生态、简单委托流 | 低 |
| **AutoGen** (Microsoft) | 对话驱动 | 多 Agent 辩论、协作推理 | 研究场景、Microsoft 生态 | 中-高 |
| **Google ADK** | 层级 Agent 树 | 多模态、A2A 原生 | Google 生态、多模态 Agent | 中 |
| **Claude Agent SDK** | 工具链+子 Agent | MCP 原生、安全、计算机使用 | 安全优先、Anthropic 生态 | 中 |
| **PydanticAI** | 类型安全 Python | 强类型、Pydantic 集成 | 类型安全要求高的项目 | 低-中 |

### 选型决策树

```
需要精确控制每个决策点？ → LangGraph
  └─ 需要快速原型验证？ → CrewAI
      └─ 已在 OpenAI 生态？ → OpenAI Agents SDK
          └─ 需要多 Agent 辩论？ → AutoGen
              └─ 安全/审计优先？ → Claude Agent SDK
```

### 代码量对比（实现同一任务）

| 框架 | 代码行数 | 灵活性 |
|------|---------|--------|
| LangGraph | ~30 行 | 完全控制（分支、循环、条件） |
| CrewAI | ~18 行 | 中等（自定义工具、记忆配置） |
| OpenAI Agents SDK | ~12 行 | 有限（只有 Handoff） |

---

## 四、协议层：MCP 与 A2A

### MCP（Model Context Protocol）
- **创造者**：Anthropic，2024年11月开源
- **定位**：Agent ↔ 工具/数据的标准接口（垂直整合）
- **机制**：JSON-RPC 2.0 over stdio 或 SSE
- **生态**：97M+ 月下载量，10,000+ 已有 MCP Server
- **作用**：让 Agent 连接 API、数据库、文件系统、搜索引擎等

### A2A（Agent-to-Agent Protocol）
- **创造者**：Google，捐赠给 Linux Foundation
- **定位**：Agent ↔ Agent 的标准通信（水平整合）
- **机制**：Agent Card（能力发现）+ 任务生命周期（submitted→working→completed）
- **支持者**：100+ 企业
- **关键特性**：Agent 之间保持不透明（不共享内部状态/记忆）

### 两者关系：互补而非竞争

```
┌──────────────────────────────────────┐
│  A2A: Agent ↔ Agent 通信层          │
│  （跨组织、跨框架协作）               │
├──────────────────────────────────────┤
│  MCP: Agent ↔ 工具/数据 连接层       │
│  （单个 Agent 的能力扩展）            │
├──────────────────────────────────────┤
│  AI Model / Agent Runtime            │
│  （推理与规划能力）                    │
└──────────────────────────────────────┘
```

**实践经验**：先用 MCP 连接工具，再用 A2A 做多 Agent 协作。

---

## 五、关键架构决策

### 单 Agent vs 多 Agent

| | 单 Agent | 多 Agent |
|---|---------|---------|
| 复杂度 | 低 | 高 |
| 调试 | 简单 | 困难 |
| Token 成本 | 较低 | 较高（Agent 间通信开销） |
| 适用 | 清晰线性任务 | 复杂多领域任务 |

### ReAct vs Plan-and-Execute

- **ReAct**：探索性强，每步依赖观察，适合开放式任务
- **Plan-and-Execute**：效率高，减少 LLM 调用次数，适合确定性任务
- 实际项目常混合使用：Plan-and-Execute 为主体，关键步骤用 ReAct 微调

### 工具规模问题

- < 10 个工具：全量传入
- 10-50 个工具：分类管理
- 50+ 个工具：必须用 embedding 检索动态加载（工具描述 embedding → top-k 匹配）

---

## 六、2026 趋势总结

1. **框架稳定化**：LangGraph 达到 v1.0+ GA，CrewAI 超 44,600 GitHub stars
2. **协议标准化**：MCP + A2A 成为行业事实标准，均由 Linux Foundation 治理
3. **多模态 Agent**：视频、音频、图像同时处理
4. **小模型 Agent**：本地 SLM（Llama 3、Mistral）降低成本和延迟
5. **生产化**：关注 checkpointing、可观测性、安全护栏、成本控制
6. **ACP/UCP 协议**：Agent 商业交易层正在形成

---

## 七、实用建议（给开发者）

### 快速启动路径
1. **验证想法**：用 CrewAI（最快原型）
2. **投入生产**：迁移到 LangGraph（最强控制）
3. **单一模型**：OpenAI Agents SDK（最简集成）

### 必学基础（框架无关）
- ReAct 推理模式
- Function Calling / Tool Use
- MCP 工具集成
- A2A Agent 间通信

### 避坑指南
- 不要一上来就用多 Agent，先验证单 Agent 能否解决
- 工具超过 50 个必须做动态加载
- 每个 Agent 的 system prompt 要明确边界，避免职责模糊
- 成本监控从第一天就开始，Agent 循环很容易 token 爆炸

---

## 八、参考资源

- [AI Agent Frameworks Compared: 2026 Guide](https://letsdatascience.com/blog/ai-agent-frameworks-compared) — 最全面的框架对比
- [The Definitive Guide to Agentic Design Patterns in 2026](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/) — 六大设计模式详解
- [MCP vs A2A in 2026: How the AI Protocol War Ends](https://philippdubach.com/posts/mcp-vs-a2a-in-2026-how-the-ai-protocol-war-ends/) — 协议层深度解读
- [AI Agent Architecture: Build Systems That Work](https://redis.io/blog/ai-agent-architecture/) — 生产架构实践
- [LangGraph vs CrewAI vs OpenAI Agents SDK](https://techsy.io/blog/langgraph-vs-crewai-vs-openai-agents-sdk) — 代码级对比
- [Open-Source AI Agent Frameworks Comparison](https://langfuse.com/blog/2025-03-19-ai-agent-comparison) — Langfuse 综合评测
