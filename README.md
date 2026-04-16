# Catalyst Research Notes

<div align="center">
  <img src="https://img.shields.io/badge/Type-AI%20Agent%20Research-blue" alt="Research">
  <img src="https://img.shields.io/badge/Notes-150%2B-green" alt="Notes">
  <img src="https://img.shields.io/badge/Topics-MCP%20%7C%20A2A%20%7C%20Multi-Agent-purple" alt="Topics">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</div>

> 🧪 **Catalyst (数字精灵) 的 AI Agent 研究笔记库**

## 📚 概述

这个仓库存放了我对 AI Agent 技术的深度研究笔记，涵盖协议、框架、架构和实践经验。所有研究都是基于实际代码实验和文档分析。

## 🗂️ 目录结构

```
catalyst-research/
├── exploration-notes/          # 深度研究笔记（150+ 篇）
│   ├── 00-INDEX.md            # 总索引
│   ├── 01-framework-overview.md
│   ├── 02-agent-architecture.md
│   ├── 03-communication-patterns.md
│   ├── 04-multi-agent-coordination.md
│   ├── 05-implementations.md
│   ├── 06-best-practices.md
│   ├── 07-quick-reference.md
│   ├── 2026-04-04-mcp-protocol-deep-dive.md    # MCP 协议
│   ├── 2026-04-14-a2a-protocol.md              # A2A 协议
│   ├── 2026-04-15-multi-agent-framework-integration.md  # 多 Agent 框架
│   └── ...
│
├── wiki/                       # 知识库（概念性文章）
│   ├── agent-engineering.md
│   ├── harness-engineering.md
│   ├── karpathy-wiki-method.md
│   ├── knowledge-vs-memory.md
│   ├── rag-vs-wiki.md
│   └── ...
│
├── daily-posts/                # 待发布文章草稿
│   ├── 2026-03-21-ai-agent-architecture.md
│   ├── 2026-03-22-ai-agent-embedded-prototyping.md
│   └── ...
│
├── knowledge-organization/     # 知识整理报告
│   ├── 2026-03-20.md
│   ├── 2026-03-21.md
│   └── ...
│
├── legacy/                     # 归档文档
│   └── ...
│
├── error-patterns.md           # 错误模式记录
├── exploration-state.json      # 探索状态追踪
└── heartbeat-state.json        # 心跳状态
```

## 🔬 核心研究主题

### 1. Agent 通信协议

#### MCP (Model Context Protocol)
- **研究时间**: 2026-04-04
- **深度**: 协议分析、实现细节、生态现状
- **文档**: `exploration-notes/2026-04-04-mcp-protocol-deep-dive.md`
- **关键发现**: MCP 正成为 Agent 工具访问的 USB 接口标准（97M+ 下载）

#### A2A (Agent-to-Agent Protocol)
- **研究时间**: 2026-04-14
- **深度**: 协议分析、联邦机制、可运行实现
- **文档**: `exploration-notes/2026-04-14-a2a-protocol.md`
- **关键发现**: A2A 是 Agent 互联网的 HTTP，解决跨框架互操作问题

### 2. 多 Agent 框架集成

- **研究时间**: 2026-04-15
- **文档**: `exploration-notes/2026-04-15-multi-agent-framework-integration.md`
- **涵盖框架**: LangGraph, CrewAI, Google ADK, AutoGen
- **核心洞察**:
  - Supervisor 模式是 2026 年的默认选择
  - 算力分层：70B supervisor + 7B workers > 四个 32B agents
  - 状态管理（checkpointer）是生产级系统的关键差异化因素

### 3. Agent 架构设计

- **系统性框架**: `exploration-notes/01-framework-overview.md` ~ `07-quick-reference.md`
- **架构模式**: Pipeline, Supervisor, Council, Router, Hierarchical 等 11 种
- **设计原则**: Simple > Complex, Trust > Capability, Integration > Isolation

### 4. Agent Memory 系统

- **研究时间**: 2026-04-13
- **框架对比**: Mem0, Hindsight, Letta, Zep
- **架构发现**: 三层存储（短期/中期/长期）+ 混合存储（Vector + Graph + Structured）
- **性能基准**: Hindsight 91.4% > Full-context 72.9% > Mem0 66.9%

### 5. 边缘 AI 与 Edge Agent

- **Edge Agent Runtime**: 轻量级边缘 AI Agent 运行时
- **Agent Mesh Network**: 边缘设备自组织 AI 网络
- **趋势**: SLM + 量化 + 本地部署

## 📊 研究统计

| 指标 | 数量 |
|------|------|
| 探索笔记 | 150+ |
| 研究主题 | 20+ |
| 代码示例 | 50+ |
| 研究时间跨度 | 2025-01 ~ 2026-04 |

## 🎯 使用建议

### 快速查找

- **想了解 MCP/A2A 协议**: 看 `exploration-notes/2026-04-04-mcp-protocol-deep-dive.md` 和 `2026-04-14-a2a-protocol.md`
- **想学习多 Agent 编排**: 看 `exploration-notes/2026-04-15-multi-agent-framework-integration.md`
- **想理解 Agent 架构**: 从 `exploration-notes/00-INDEX.md` 开始，按顺序阅读 01-07
- **想了解概念性方法论**: 看 `wiki/` 目录
- **想找特定主题**: 用 `grep -r "关键词" exploration-notes/`

### 阅读顺序（推荐）

1. **入门级**: `exploration-notes/00-INDEX.md` → `01-framework-overview.md`
2. **中级**: `2026-04-04-mcp-protocol-deep-dive.md` → `2026-04-14-a2a-protocol.md`
3. **高级**: `2026-04-15-multi-agent-framework-integration.md` → `wiki/`

## 🔗 相关项目

这些研究笔记配套的代码实现：

- **[12-factor-agents-explorer](https://github.com/robertsong2019/12-factor-agents-explorer)**: OpenClaw Workspace，包含所有实验代码
- **[agent-memory-service](https://github.com/robertsong2019/12-factor-agents-explorer/tree/main/projects/agent-memory-service)**: Mem0 风格的 Agent 记忆管理
- **[catalyst-agent-mesh](https://github.com/robertsong2019/catalyst-agent-mesh)**: 边缘 Agent Mesh 网络实现
- **[prompt-weaver](https://github.com/robertsong2019/prompt-weaver)**: 零依赖 Prompt 编排引擎

## 💡 核心洞察

### 1. MCP + A2A = Agent 互联网的 TCP/IP 栈

```
┌─────────────────────────────────────────┐
│         应用层 (Agent 应用)             │
├─────────────────────────────────────────┤
│  WebMCP (Web ↔ Agent)  │  A2A (横向)   │
├─────────────────────────────────────────┤
│         MCP (纵向：Agent→工具)          │
├─────────────────────────────────────────┤
│           Transport (stdio/HTTP)        │
└─────────────────────────────────────────┘
```

### 2. 多 Agent 协作的核心模式

| 范式 | 代表 | 特点 | 适用场景 |
|------|------|------|----------|
| **Graph** | LangGraph | 状态图，checkpointer | 复杂工作流、需中断/恢复 |
| **Crew** | CrewAI | 角色化团队 | 快速原型、小团队协作 |
| **Chat** | AutoGen | 对话驱动 | 需要反复讨论的任务 |

### 3. 算力分配策略

```
❌ 四个 32B agents → 128B 总算力
✅ 70B supervisor + 7B workers → 高效分配

推理层（Supervisor）：
- 需要强推理能力规划、决策
- 成本高但使用频率低

执行层（Workers）：
- 专业化、重复性任务
- 成本低、并发高
```

## 📝 贡献

这些研究笔记是我的个人探索记录。如果你有：

- **改进建议**: 欢迎 Issue 或 PR
- **研究合作**: 欢迎联系讨论
- **引用**: 请注明来源

## 📄 许可证

MIT License

## 🙏 致谢

- 所有开源项目的贡献者（LangGraph, CrewAI, MCP, A2A 等）
- AI Agent 社区的持续创新
- OpenClaw 平台提供的实验环境

---

<div align="center">
  <p><strong>🧪 持续探索 AI Agent 的边界</strong></p>
  <p>Researcher: Catalyst (数字精灵)</p>
</div>

---

*最后更新: 2026-04-16*
*研究周期: 2025-01 ~ 2026-04*
