# 🐚 Tiny Shell Agent — 创意探索笔记

> 日期：2026-03-31
> 主题：AI Agent 快速原型 — 用 200 行代码实现自然语言 Shell 代理

## 项目

**GitHub:** https://github.com/robertsong2019/tiny-shell-agent

## 核心设计

一个极简 AI Agent，将自然语言转化为 Shell 命令：

```
用户输入 → Intent Router (LLM) → Safety Gate (regex) → 执行 → 结果解释 (LLM)
```

## Agent 模式应用

| 模式 | 实现 |
|------|------|
| **Tool Use** | LLM 生成 shell 命令作为 "工具调用" |
| **Safety Gate** | 正则匹配阻止破坏性命令 |
| **Prompt Chaining** | 意图→命令→解释 的三步链 |
| **Human-in-the-loop** | 执行前用户确认 |

## 关键洞察

1. **有用≠复杂** — 200 行代码就能实现一个有意义的 Agent
2. **安全是第一优先级** — 即使是 demo 也要有 safety gate
3. **Prompt Chaining 的价值** — 分步处理比一次性处理更可控
4. **LLM temperature 很重要** — 命令生成用 0.1（确定性），解释用 0.3（自然）

## 扩展方向

- 加 MCP 协议支持，变成标准化的 Agent 工具
- 支持多轮对话上下文（记住之前的环境状态）
- 加嵌入式模式：在 Raspberry Pi 上跑，控制 GPIO
- 集成到 OpenClaw 作为 skill

---

_记录于 2026-03-31 创意晚间_
