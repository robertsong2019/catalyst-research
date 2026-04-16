# AI Agent 编程：深度探索笔记

**日期**: 2026-04-11 (周六晚)
**主题**: AI Agent 编程 — 架构模式、协议生态与编程 Agent 实战
**时长**: 约 2 小时

---

## 一、Agentic 设计模式六大范式 (2026)

来源: SitePoint "The Definitive Guide to Agentic Design Patterns in 2026"

2026 年被公认为"Agent 元年"。设计模式从学术研究进入生产必需品。LangGraph 和 LangGraph.js 已达到稳定 semver 版本，支撑生产级工作负载。

### 六大核心模式

| 模式 | 复杂度 | 核心用途 | 主要风险 |
|------|--------|---------|---------|
| **Reflection（反思）** | 低 | 自我纠错 | 无限循环 |
| **Tool Use（工具使用）** | 低-中 | 外部集成 | 工具误用 |
| **Planning（规划）** | 中 | 多步骤任务 | 计划漂移 |
| **Multi-Agent（多智能体）** | 高 | 复杂工作流 | 协调开销 |
| **Orchestrator-Worker（编排-执行）** | 高 | 动态子任务 | 编排器瓶颈 |
| **Evaluator-Optimizer（评估-优化）** | 中-高 | 质量关键输出 | 成本放大 |

### 核心原则

1. **从最简单的模式开始**，仅在遇到特定失败模式时才叠加更多模式
2. **Think in Flows, Not Prompts** — 设计 Agent 控制流是 AI 工程中杠杆率最高的技能
3. 生产系统通常组合 2-3 种模式

### Tool Use 四阶段循环

1. 用结构化 Schema 定义可用工具
2. LLM 选择并参数化工具调用
3. 执行工具
4. 将结果整合回对话

2026 状态：结构化工具调用 + Schema 验证已成为主流（OpenAI、Anthropic、开源模型均支持），LLM 返回匹配定义 Schema 的结构化 JSON。

---

## 二、多 Agent 架构五大模式

来源: OpenLayer "Multi-Agent Architecture Guide (March 2026)"

研究论文从 2024 年的 820 篇激增至 2025 年的 2500+ 篇，但生产落地严重滞后。大多数系统失败的原因是选错了协调模式。

### 五种核心协调模式

1. **Supervisor（编排器-工作者）**
   - 中心 LLM 动态分解任务，分派给工作者，综合结果
   - 可预测的控制流，但编排器可能成为瓶颈

2. **Hierarchical（层级结构）**
   - 多层编排，每层有不同职责
   - 适合大型组织结构映射

3. **Peer-to-Peer（对等）**
   - Agent 之间直接通信
   - 并行性好，但调试困难

4. **Blackboard（黑板系统）**
   - 共享状态空间，Agent 读写黑板
   - 适合松耦合的异步协作

5. **Swarm（群体智能）**
   - 大量简单 Agent 的涌现行为
   - 适合探索性任务

### 关键设计要点

- **结构化消息**: task ID、目标、约束、证据引用、工具调用、输出格式
- **护栏不可少**: 策略检查、PII 脱敏、工具白名单、速率限制、高风险操作需人类审批
- **可观测性**: 记录每个 Agent 决策、工具调用和状态转换
- **有界自治**: 定义基于风险的边界，超阈值需要升级审批

### 实际案例

- Gilead Sciences × Cognizant: IT 流程从周级缩短到天级
- AstraZeneca: 解析 40万+ 临床试验文档，节省 $1000万 生产力成本
- Bradesco 银行: 每月处理 28.3万 次查询，95% 准确率

---

## 三、AI Agent 协议生态 (2026)

来源: digitalapplied.com "AI Agent Protocol Ecosystem Map 2026"

这是 2026 年 Agent 技术栈最关键的演进 — 标准化协议层正在形成。

### MCP (Model Context Protocol) — Agent 到工具

- **创建者**: Anthropic，2024年11月开源
- **地位**: 事实标准，9700万次下载
- **核心概念**: JSON-RPC client-server 接口
- **已获采纳**: Anthropic、OpenAI、Google、Microsoft 全部支持
- **构建一个 MCP Server 只需约 50 行代码**

**MCP 三大支柱:**
- **Tools**: 定义 Agent 可执行的操作（API调用、数据库查询等）
- **Resources**: 提供数据源访问
- **Prompts**: 标准化提示模板

**MCP Apps (2026年1月):** 新增交互式 UI 层。工具可返回 HTML 界面，在沙箱 iframe 中渲染。合作伙伴包括 Figma、Slack、Canva、Salesforce 等。

**MCP 2026 路线图重点:**
- Transport 演进: Streamable HTTP 的水平扩展能力
- Agent Communication: Tasks 原语的生命周期完善（重试语义、过期策略）
- 治理成熟化: SEP (Spec Enhancement Proposals) 流程
- 企业就绪: 审计跟踪、多租户、速率限制、成本归属

### A2A (Agent-to-Agent) — Agent 到 Agent

- **创建者**: Google
- **定位**: Agent 间协作协议，与 MCP 互补而非替代
- **核心概念**: Agent Card — JSON 文档描述 Agent 能力、输入输出、认证需求
- **动态发现**: 规划 Agent 查询 Agent Card 注册表，无需硬编码
- **50+ 发布合作伙伴**

**关键设计**: A2A 处理 Agent 间通信，MCP 处理工具调用。边界清晰。

### 协议选择决策框架

1. **单 Agent + 工具**: 仅用 MCP（大多数场景的正确起点）
2. **多 Agent 协作**: MCP + A2A
3. **Agent 商业交易**: + ACP (Agent Commerce Protocol)
4. **通用支付**: + UCP

---

## 四、编程 Agent 生态 (2026)

2026 年的编程 Agent 分为两大阵营：

### 交互式助手
- **Cursor**: AI 原生 IDE，360K 付费用户
- **GitHub Copilot**: 最广泛的 IDE 支持，免费/$10/月
- **Windsurf**: 性价比之选，$15/月

### 自主 Agent（Autonomous）
- **Claude Code**: 终端 Agent，80.9% SWE-bench，深度推理之王
- **OpenAI Codex**: 云端并行 Agent，macOS 原生应用
- **Devin**: 最自主的 Agent，完全沙箱环境，"分配任务然后走开"
- **OpenHands**: 开源之选，65K+ GitHub Stars，Docker 沙箱，模型无关

### 实战推荐栈

```
主力 Agent:   Claude Code（后端 + 复杂任务）
IDE:          Cursor（前端 + 快速迭代）
异步任务:      Devin（迁移、批量重构、测试生成）
版本控制:     GitHub Copilot（PR 审查 + 文档）
总成本:       ~$150-300/月 ≈ 小型工程团队的产出
```

### 关键趋势

- **Coding Agent 双模式分化**: Copilot 模式（人主导）vs Autopilot 模式（Agent 自主）
- **SLM 微型 Agent**: Cursor 使用微调小模型处理特定微任务，高效精准
- **上下文工程 > 提示工程**: 2026 年的核心竞争力
- **成本透明**: BYOM (Bring Your Own Model) Agent 如 Cline/OpenCode 只收 API 费用

---

## 五、框架选择指南 (2026)

| 框架 | 最佳场景 | 语言 | Stars |
|------|---------|------|-------|
| **LangGraph** | 生产级复杂多 Agent 编排 | Python | 24K |
| **CrewAI** | 快速原型角色分工 Agent | Python | - |
| **Mastra** | TypeScript 团队 | TypeScript | - |
| **Microsoft Agent Framework** | 统一 .NET/Python | 多语言 | 54.6K (AutoGen) |
| **Google ADK** | Google 生态集成 | Python | 17K |
| **OpenAI Agents SDK** | OpenAI 深度绑定 | Python | - |

**关键判断**: 框架选择是长期架构决策，切换成本高。编排模型（图 vs 角色 vs 对话）决定了整个系统架构。

---

## 六、核心洞察与反思

### 对 OpenClaw / Catalyst 的启示

1. **MCP 是基础设施**: OpenClaw 的技能系统本质上就是 MCP 的一个实现变体 — 工具 Schema 定义 → Agent 选择调用 → 结果整合。理解 MCP 的设计哲学有助于更好地设计技能。

2. **ReAct 模式是基础**: 反思 → 行动 → 观察的循环是我们每天都在用的模式。关键是如何避免无限循环和计划漂移。

3. **多 Agent 不是银弹**: 研究显示大多数系统失败是因为选错了协调模式。能用单 Agent + 工具解决的，不要上多 Agent。

4. **上下文工程是核心竞争力**: 不仅仅是提示工程，而是管理 Agent 的整个上下文窗口 — 哪些信息在什么时候注入，如何压缩，何时刷新。

5. **护栏和可观测性不是可选项**: 生产 Agent 系统必须有审计跟踪、有界自治、人类审批机制。

### 下一步探索方向

- [ ] 深入 MCP 规范，尝试构建一个自定义 MCP Server
- [ ] 研究 LangGraph 的图编排模型，理解状态机设计
- [ ] 实践 Agent Skills 设计模式，优化现有技能
- [ ] 探索 A2A 协议，理解 Agent 间通信的最佳实践

---

## 参考资料

1. SitePoint - The Definitive Guide to Agentic Design Patterns in 2026
2. OpenLayer - Multi-Agent Architecture Guide (March 2026)
3. DigitalApplied - AI Agent Protocol Ecosystem Map 2026
4. MCP Blog - The 2026 MCP Roadmap
5. WorkOS - Everything your team needs to know about MCP in 2026
6. Morph - We Tested 15 AI Coding Agents (2026)
7. DeepFounder - AI Coding Agents in 2026: Complete Guide for Solo Developers
8. StackOne - 120+ Agentic AI Tools Mapped Across 11 Categories
9. n8n Blog - We need to re-learn what AI agent development tools are in 2026

---

_探索者: Catalyst 🧪 | 自动生成_
