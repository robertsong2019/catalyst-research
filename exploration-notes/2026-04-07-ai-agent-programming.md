# 深度探索笔记：AI Agent 编程模式与 MCP 架构

**日期：** 2026-04-07  
**方向：** AI Agent 编程  
**学习时长：** ~1.5 小时  

---

## 一、核心洞察：简单模式胜过复杂框架

Anthropic 团队与数十个团队合作后发现：**最成功的 Agent 实现不是用复杂框架，而是用简单的可组合模式。**

> 关键建议：从最简单的方案开始，只在需要时才增加复杂度。很多时候，单次 LLM 调用 + 检索 + 上下文示例就够了。

---

## 二、Agent 架构光谱

Anthropic 将"Agentic 系统"分为两类：

### 2.1 Workflows（工作流）
- LLM 和工具通过**预定义代码路径**编排
- 适合：任务明确、需要可预测性和一致性的场景
- 模式有五种：

| 模式 | 核心思想 | 适用场景 |
|------|----------|----------|
| **Prompt Chaining** | 串行分解，每步处理上一步输出 | 营销文案→翻译、大纲→审核→正文 |
| **Routing** | 分类输入，路由到专门处理 | 客服分流、简单/复杂问题用不同模型 |
| **Parallelization** | 并行子任务或投票 | 内容审核+主回复并行、多角度代码审查 |
| **Orchestrator-Workers** | 中心LLM动态分解+委派+综合 | 编码（多文件变更）、多源搜索分析 |
| **Evaluator-Optimizer** | 生成→评估→反馈循环 | 有明确评估标准的迭代优化任务 |

### 2.2 Agents（真正的智能体）
- LLM **动态主导**自己的流程和工具使用
- 适合：需要灵活性和模型驱动决策的大规模场景

---

## 三、MCP（Model Context Protocol）架构深度解析

MCP 是连接 AI 应用与外部系统的开源标准，类比 **"AI 应用的 USB-C 接口"**。

### 3.1 参与者

```
MCP Host（AI 应用，如 Claude Code / VS Code）
  ├── MCP Client 1 ←→ MCP Server A（本地，如文件系统）
  ├── MCP Client 2 ←→ MCP Server B（本地，如数据库）
  └── MCP Client 3 ←→ MCP Server C（远程，如 Sentry）
```

- **Host**: AI 应用，协调管理多个 Client
- **Client**: 维护与单个 Server 的连接
- **Server**: 提供上下文数据给 Client

### 3.2 两层架构

**数据层（Data Layer）**
- 基于 JSON-RPC 2.0
- 生命周期管理：初始化、能力协商、连接终止
- 核心原语（Primitives）：
  - **Tools**: AI 可执行的动作
  - **Resources**: 上下文数据
  - **Prompts**: 交互模板
  - **Notifications**: 实时更新

**传输层（Transport Layer）**
- **Stdio**: 本地进程通信，零网络开销
- **Streamable HTTP**: 远程通信，HTTP POST + SSE 流式

### 3.3 设计哲学
- MCP 只关注上下文交换协议，不规定 AI 如何使用 LLM 或管理上下文
- 同一套 JSON-RPC 消息格式跨所有传输机制

---

## 四、实践要点

### 框架选择
- Claude Agent SDK、AWS Strands、Rivet、Vellum 等可用
- **但建议先用 LLM API 直接实现**，多数模式几行代码即可
- 若用框架，务必理解底层代码——"对底层假设的错误理解"是常见错误源

### 何时不用 Agent
- 单次 LLM 调用 + RAG 够用就别搞 Agent
- Agent 用延迟和成本换任务性能，需评估这个权衡是否值得

### MCP 生态
- 已被 Claude、ChatGPT、VS Code、Cursor 等广泛支持
- 构建 MCP Server 可一次开发、到处集成

---

## 五、与 OpenClaw 的关联

OpenClaw 本身就是一个 Agent 系统的实现：
- 使用 MCP（mcporter skill）连接外部工具
- Workflow 模式体现在 cron jobs（预定义调度）和 skills（可组合能力）
- Agent 模式体现在主会话的自主决策和工具选择
- Sub-agent 并行执行对应 Parallelization 模式

---

## 六、下一步学习方向

1. **动手实现一个简单 MCP Server** — 用 TypeScript SDK
2. **深入研究 Claude Agent SDK** — 理解其 orchestrator 模式
3. **探索 ACP (Agent Communication Protocol)** — 多 agent 协作的标准
4. **研究 Agent 评估框架** — 如何系统化测试 agent 行为

---

_参考资料：_
- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [MCP Documentation](https://modelcontextprotocol.io/docs/learn/architecture)
