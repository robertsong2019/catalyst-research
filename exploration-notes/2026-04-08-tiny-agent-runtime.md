# 2026-04-08 GitHub 创意晚间项目

## 项目: tiny-agent-runtime 🧠

**仓库:** https://github.com/robertsong2019/tiny-agent-runtime

### 核心理念
完整 AI Agent 运行时，单文件 290 行 Python，零外部依赖。
- 只用 Python stdlib 的 `urllib.request` 调用 OpenAI 兼容 API
- ReAct 模式工具调用循环
- 内置 shell / think / read_file 工具
- 滑动窗口对话记忆
- 可在任何 Python 3.8+ 环境运行，包括树莓派/Jetson Nano

### 为什么做这个？
主流 Agent 框架（LangGraph、AutoGen、CrewAI）都是几千行代码加重依赖。
但 Agent 核心循环极其简单：Prompt → LLM → Tool → Result → 循环或结束。
这个项目把循环蒸馏到最纯粹的形式。

### 关键设计决策
1. **stdlib-only HTTP** — 不依赖 requests/httpx，用 urllib.request
2. **装饰器工具注册** — `@tool` 装饰器声明式定义工具
3. **内存安全** — 滑动窗口避免 token 爆炸
4. **边缘友好** — 示例包含 GPIO 读取、系统监控

### 示例项目
- `custom_tools.py` — 自定义工具 + 多 Agent 流水线
- `edge_agent.py` — 边缘设备硬件监控 Agent

### 行业趋势观察 (2026.04)
- **Dify** 129.8k stars（低代码 Agent 平台领跑）
- **LangGraph** 34.5M 月下载量（企业采用率最高）
- **Gemini CLI** 进入 GitHub Top 100（Google 开源终端 Agent）
- **everything-claude-code** 140.8k stars（Agent harness 优化）
- **GNAP (Git-Native Agent Protocol)** — 新出现的 Agent 协议
- **Qwen3.6-Plus** — 阿里 4 月发布，1M 上下文，MCP 原生
- **Gemma 4** — Google 新发布，面向 Consumer/IoT 优化

### 下一步想法
- [ ] 添加 MCP 协议支持
- [ ] WASM 编译版本（Pyodide 在浏览器运行）
- [ ] 添加 A2A (Agent-to-Agent) 通信
- [ ] 做 benchmark 对比（vs LangChain 调用开销）
