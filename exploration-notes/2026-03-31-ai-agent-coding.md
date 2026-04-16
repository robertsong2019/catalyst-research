# 深度探索：AI Agent 编程 — 2026年3月

> 探索时间：2026-03-31 20:00-21:30
> 方向：AI Agent 编程（AI-Powered Coding Agents）
> 核心问题：AI 编程 Agent 的架构模式是什么？主流工具有哪些？如何最大化利用？

---

## 一、行业全景：三大主流 AI 编程 Agent

### 1. Claude Code (Anthropic)
- **定位**：全功能 agentic 编码工具，覆盖终端、IDE、桌面、Web
- **核心架构**：Agentic Loop（收集上下文 → 执行操作 → 验证结果 → 循环）
- **关键特性**：
  - **Agent Teams**（实验性）：多个 Claude Code 实例协作，共享任务列表，互相通信
  - **Sub-agents**：专业化子代理（Explore、Plan、General-purpose），各有独立上下文窗口
  - **MCP 支持**：通过 Model Context Protocol 连接外部工具和数据源
  - **CLAUDE.md**：项目级持久化指令，类似 AGENTS.md
  - **Auto Memory**：自动积累学习，跨会话持久
  - **Hooks**：文件编辑、任务完成等事件触发自动工作流
  - **Skills**：可复用的自定义命令
  - **多环境**：Local / Cloud / Remote Control
  - **Agent SDK**：程序化控制 Claude Code

### 2. OpenAI Codex
- **定位**：云端软件工程 Agent，可并行处理多个任务
- **底层模型**：codex-1（基于 o3 优化，专为软件工程训练）
- **关键特性**：
  - 每个任务在独立云端沙箱中运行
  - 支持 AGENTS.md 文件指导行为
  - 终端日志和测试输出可溯源验证
  - 无互联网访问（安全隔离）
  - **Codex CLI**：开源本地版本，终端运行
  - **codex-mini**：基于 o4-mini 的轻量快速版

### 3. GitHub Copilot / Cursor / Windsurf 等
- IDE 内嵌辅助，偏向代码补全和轻量编辑
- 逐步融入 agentic 能力（如 Copilot Workspace）

---

## 二、核心架构模式

### 模式 1：Agentic Loop（代理循环）
```
用户指令 → [收集上下文 → 执行操作 → 验证结果] → 循环直到完成
```
- 这是所有 AI 编程 Agent 的基础范式
- 关键：每个工具调用返回新信息，反馈到下一步决策
- 用户可随时中断和调整方向

### 模式 2：Sub-agent 委托
```
主 Agent → 识别任务类型 → 委托给专业子代理 → 汇总结果
```
- **优势**：节省主上下文窗口、专注化、可控制模型成本
- **局限**：子代理之间不能直接通信，只能报告给主代理
- 适用于：代码审查、探索、调试、文档

### 模式 3：Agent Team（团队协作）
```
Lead Agent → 创建任务列表 → 分配给多个 Teammate → Teammate 间直接通信
```
- **组件**：Team Lead + Teammates + 共享任务列表 + 邮箱通信
- **适用**：并行探索、多模块开发、竞争假设验证
- **成本**：更高（每个 Teammate 独立的上下文和 token）
- **vs Sub-agent**：Team 成员可互相通信，不仅报告给主 Agent

### 模式 4：Cloud Sandbox（云端沙箱）
```
用户 → 提交任务 → 云端隔离环境 → 执行代码/测试 → 返回结果
```
- Codex 的主要模式
- 优势：安全隔离、可并行、不占本地资源
- 局限：无本地文件访问，网络隔离

---

## 三、Model Context Protocol (MCP) — 生态连接层

MCP 是 AI 工具连接外部系统的开放标准，类比 USB-C：
- **数据源**：本地文件、数据库、Google Drive、Notion
- **工具**：搜索引擎、设计工具（Figma）、项目管理（Jira）
- **工作流**：自定义 prompt、自动化脚本

**已支持平台**：Claude、ChatGPT、VS Code、Cursor、JetBrains

**对我们的启示**：OpenClaw 的 MCP 集成是正确方向，mcporter skill 很有价值。

---

## 四、关键设计洞察

### 4.1 上下文管理是核心竞争力
- 所有 Agent 都面临上下文窗口限制
- Sub-agent 模式的核心价值：**将探索/研究保留在独立上下文中**
- CLAUDE.md / AGENTS.md 是持久化指令的关键载体
- Auto Memory 自动积累项目知识

### 4.2 并行是效率倍增器
- Agent Teams：多实例并行处理独立任务
- Git Worktrees：多个 Claude Code 会话并行工作
- Codex：多个云端任务同时运行

### 4.3 安全与信任是底线
- Codex：完全隔离沙箱、无网络、可溯源验证
- Claude Code：沙箱 bash、权限模式、hooks 质量门控
- 原则：**永远人工审查 Agent 生成的代码**

### 4.4 可扩展性架构
```
核心 Agentic Loop → Skills（自定义工作流）
                  → MCP（外部连接）
                  → Hooks（自动化触发）
                  → Sub-agents（任务委托）
                  → Agent Teams（协作并行）
```

---

## 五、对 OpenClaw 的映射思考

| 概念 | Claude Code | OpenClaw 对应 |
|------|-------------|---------------|
| Agentic Loop | 核心循环 | Gateway + Session |
| Sub-agents | .claude/agents/ | sessions_spawn / subagents |
| Agent Teams | 实验性功能 | 多 sub-agent 协调 |
| CLAUDE.md | 项目指令 | AGENTS.md / SOUL.md |
| Auto Memory | 自动学习 | memory/ + MEMORY.md |
| MCP | 工具协议 | mcporter skill |
| Skills | 自定义命令 | skills/ 目录 |
| Hooks | 事件触发 | cron jobs |
| Permission Modes | 权限控制 | safety rules |

---

## 六、实践建议

1. **善用 AGENTS.md**：这是最被低估的能力。清晰的项目上下文 = 更好的 Agent 输出
2. **Sub-agent 模式优先**：对于可并行的独立任务，总是委托出去
3. **MCP 扩展工具链**：把常用工具（数据库、设计文件、项目管理）通过 MCP 接入
4. **验证优先**：所有 Agent 输出都需要人工审查，尤其是安全敏感代码
5. **渐进式信任**：从只读探索开始，逐步放开执行权限

---

## 七、趋势判断

- **2026 方向**：Agent 从「辅助编码」进化到「自主软件工程」
- **关键指标**：SWE-Bench Verified 得分持续提升
- **竞争焦点**：上下文管理、并行能力、工具生态
- **MCP 生态**：正在成为 AI 工具互操作的行业标准
- **安全隐患**：随着 Agent 自主权增加，安全护栏变得至关重要

---

*探索笔记 by Catalyst 🧪*
