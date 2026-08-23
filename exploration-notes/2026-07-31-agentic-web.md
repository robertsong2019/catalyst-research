# 探索笔记：Agentic Web — 当 AI Agent 成为互联网的一等公民

**日期：** 2026-07-31
**主题：** Agentic Web（智能体互联网）— 从人类驱动的 Web 到 Agent 自主协作的新范式
**研究者：** Catalyst

---

## 核心概念（5个）

### 1. Agentic Web（智能体互联网）
Web 发展的第三阶段。PC Web 连接信息，Mobile Web 连接服务，Agentic Web 连接**意图**。在这个范式中，AI Agent 取代人类成为互联网的主要"用户"——它们自主规划、协调、执行任务，人类只需表达意图。这不是 Add-on，是范式转换。

### 2. MCP（Model Context Protocol）— Agent 的"USB-C"接口
Anthropic 2024年11月发布的开放标准，解决的是 Agent ↔ Tool 的连接问题。类比 LSP（Language Server Protocol）对编辑器的意义——任何模型连任何工具，只需各实现一次 MCP。2025年12月捐赠给 Linux Foundation 的 Agentic AI Foundation（AAIF），成为厂商中立的核心基础设施。截至2025年底：5,800+ MCP Server，300+ MCP Client，月均 SDK 下载 9700万次。

### 3. A2A（Agent2Agent Protocol）— Agent 之间的"外交协议"
Google 2025年4月发布，解决的是 Agent ↔ Agent 的通信问题。MCP 让 Agent 用工具，A2A 让 Agent 互相协作。核心概念：Agent Card（能力声明，JSON格式）、Task lifecycle（任务生命周期管理）、Artifact（任务产出物）。基于 HTTP/SSE/JSON-RPC，支持长时间运行任务和模态协商。

### 4. Agent Attention Economy（Agent 注意力经济）
论文 arXiv:2507.21206 提出的核心经济模型。当 Agent 取代人类浏览网页，传统的"人类注意力经济"（广告→点击→转化）瓦解。新经济模型：Agent 的注意力成为稀缺资源——哪些服务能被 Agent 发现、理解、信任，就能获得流量。这是 SEO → AEO（Answer Engine Optimization）的底层逻辑。

### 5. Agent Identity & Delegation（Agent 身份与授权委托）
Microsoft Entra Agent ID 提出的概念：每个 Agent 需要有独立的身份标识，用于认证、授权、审计。核心问题：Agent 代表人类行动时，权限边界在哪里？如何防止"Agent 蔓延"（agent sprawl）导致的权限失控？

---

## 关键洞察（5条）

### 洞察 1：MCP + A2A 正在形成 Agentic Web 的"TCP/IP 时刻"
就像 1970年代 ARPANET 需要 TCP/IP 来互联不同网络，2025-2026 年的 AI Agent 生态需要标准化协议来互联不同厂商的 Agent。MCP 解决 Agent→Tool，A2A 解决 Agent→Agent。两者互补而非竞争。Google 明确说 A2A "complements MCP"。微软同时支持两者。Linux Foundation 成为治理方。这不是一个公司的游戏，是整个行业的共识。

### 洞察 2：Web 的"用户"正在从人类变成 Agent，但基础设施还没准备好
当前 Web 基础设施——从 HTML 到 CAPTCHA，从 Cookie 到 OAuth——全部假设用户是人类。当 Agent 开始"浏览"网页、填表单、做决策时，这套基础设施面临根本性挑战。Akamai 的白皮书指出：推理（inference）正在成为 Web 的新核心工作负载。CDN 需要从分发内容变为分发推理。这不是渐进改良，是架构重构。

### 洞察 3：Agent Attention Economy 将重新洗牌互联网商业模型
当 Agent 替人类做决策（买什么、看什么、去哪里），传统的 SEO/广告模型失效。企业不再需要优化"人类点击率"，而是需要优化"Agent 可发现性和可信度"。论文提出的框架：检索→推荐→规划→协作，每一步都有新的商业机会。谁能让 Agent 更容易理解和信任你的服务，谁就赢。

### 洞察 4：安全是 Agentic Web 最大的系统性风险
arXiv 论文系统分析了 Agentic Web 各层的安全威胁：Agent 被注入恶意指令、Agent 身份被盗用、多 Agent 协作中的信任传递失效、Agent 产生幻觉执行危险操作。现有防御手段（inference-time guardrails, controllable generation）远远不够。Microsoft 的方案是给 Agent 分配 Entra ID——像管理员工身份一样管理 Agent 身份。但这只是起步。

### 洞察 5：从"Agent-as-Tool"到"Agent-as-User"是质的飞跃
arXiv 论文区分了三个阶段：Agent-as-Interface（Agent 作为界面，帮人类操作 Web）、Agent-as-User（Agent 作为用户，完全代理人类）、Agent-with-Physics（Agent 与物理世界结合，如机器人）。当前处于第一阶段向第二阶段过渡。ChatGPT Agent（2025年7月）已经是第二阶段的早期形态——它能替你购物、预订、操作软件。这意味着 Web 服务需要同时服务人类用户和 Agent 用户。

---

## 可落地的 Next Actions

1. **为自己的服务实现 MCP Server** — 如果你有 API 或数据源，包装一层 MCP Server 让任何 Agent 都能接入。这是 Agentic Web 的"上线第一步"。
2. **设计 Agent Card** — 按 A2A 规范描述你的 Agent 能做什么，让别人能发现并调用。
3. **审计 Agent 权限** — 如果你已经在运行 Agent，用 Microsoft Entra Agent ID 或类似方案给每个 Agent 分配身份，设定权限边界。
4. **制作 llms.txt** — 为你的网站/服务提供机器可读的描述文件，让 Agent 能理解你的服务（类比 robots.txt，但面向 AI）。
5. **跟踪 AAIF 项目** — Linux Foundation 的 Agentic AI Foundation 是 MCP、goose、AGENTS.md 的家。关注其 Working Group 的输出。
6. **研究 Agent Attention Economy 的影响** — 如果你的业务依赖 SEO/广告，开始思考"Agent 发现"的策略。

---

## 参考来源

1. **arXiv:2507.21206** — "Weaving the Next Web with AI Agents"（2025年7月，UC Berkeley + SJTU + UCL 等）
2. **Google Developers Blog** — "Announcing the Agent2Agent Protocol (A2A)"（2025年4月9日）
3. **Microsoft Build 2025** — "The Age of AI Agents and Building the Open Agentic Web"
4. **Deepak Gupta** — "MCP: Enterprise Adoption, Market Trends & Implementation"（2025年12月）
5. **a2a-protocol.org** — A2A Protocol Specification v1.0
6. **modelcontextprotocol.io** — MCP Specification 2025-11-25
7. **Akamai** — "Architecting the Agentic Web"（2026 白皮书）
8. **IEEE Spectrum** — "The Agentic Web: AI Agents Will Redefine the Internet"
9. **Deloitte** — "Agentic AI Strategy"（Tech Trends 2026）
10. **Linux Foundation / AAIF** — MCP 捐赠公告（2025年12月9日）
11. **Anthropic** — Mike Krieger 关于 MCP 捐赠的声明
12. **arXiv:2503.23278** — "MCP: Landscape, Security Threats, and Future Directions"
