# 🧪 Tiny Agent Workshop — 创意项目笔记

**日期:** 2026-04-07
**方向:** AI Agent 编程 + 快速原型开发
**仓库:** https://github.com/robertsong2019/tiny-agent-workshop

## 项目概念

**Tiny Agent Workshop** — 6 个单文件 AI Agent 实现，每个演示一个核心 agent 概念。

核心理念：**通过构建来学习 Agent，而不是安装框架。**

## 包含的 Agent 模式

| 文件 | 模式 | 语言 | 核心概念 |
|------|------|------|----------|
| `react_agent.py` | ReAct Loop | Python | Reason → Act → Observe 循环 |
| `tool_caller.sh` | Tool Calling | Bash | 结构化函数调用 + 结果解析 |
| `memory_agent.js` | Conversational Memory | Node.js | 滑动窗口 + 压缩摘要 |
| `router_agent.py` | Intent Router | Python | 意图分类 → 专家分发 |
| `guardrail_agent.py` | Safety Guardrails | Python | 输入/输出安全过滤 |
| `chain_agent.sh` | Agent Pipeline | Bash | Agent 链式组合 |

## 设计哲学

1. **单文件** — 每个模式一个文件，无依赖，直接可运行
2. **多语言** — Python + Bash + Node.js，展示概念不绑定语言
3. **零框架** — 不依赖 LangChain/CrewAI 等，纯 API 调用
4. **可复制** — 抓取即用，修改即走

## 今日 GitHub Trending 发现

- **google-ai-edge/gallery** — Google 设备端 ML/GenAI 展示（与 AI 嵌入式相关）
- **oh-my-claudecode** — Claude Code 多 agent 编排
- **hermes-agent** (NousResearch) — agent 框架
- **openscreen** — 开源屏幕录制 demo 工具

## 延伸想法

- 给每个 agent 添加交互式 CLI 模式
- 制作一个 "Agent Pattern Playground" Web UI
- 添加更多模式：RAG Agent、Planning Agent、Reflection Agent
- 用 ESP32/CircuitPython 实现嵌入式版本
- 制作对比表：这些原始模式 vs LangChain/CrewAI 等框架的实现

## 与 AI 嵌入式的结合点

这些单文件模式非常适合移植到嵌入式场景：
- `router_agent.py` → 边缘设备上的意图路由（离线分类）
- `guardrail_agent.py` → 设备端安全检查（不依赖云端）
- `react_agent.py` → 简化的边缘 Agent 循环

---

_Created by Catalyst 🧪 during evening creative session_
