# AI Agent 编程框架深度对比

**日期**: 2026-03-31
**主题**: AI Agent 编程 — 三大主流框架架构对比
**学习时长**: ~1.5h

---

## 一、框架概览

### 1. OpenAI Agents SDK (Python)

**定位**: 轻量级、生产就绪的 Agent 编排框架，Swarm 的正式升级版。

**核心原语 (仅 3 个)**:
- **Agent** = LLM + instructions + tools
- **Handoffs / Agents as Tools** = Agent 间委托
- **Guardrails** = 输入/输出验证

**设计哲学**:
- Python-first：用语言本身的特性编排，不造新抽象
- 够用但不过度：原语少，但表达力强
- 内置 tracing（可视化/调试/评估/微调）

**工具体系 (5 类)**:
1. **Hosted tools** — WebSearch, FileSearch, CodeInterpreter, HostedMCP, ImageGen（OpenAI 服务器端运行）
2. **Tool Search** — 延迟加载工具，按需加载命名空间，减少 token 消耗
3. **Local runtime tools** — ComputerTool(GUI自动化), ShellTool, ApplyPatchTool
4. **Function tools** — 任意 Python 函数，自动生成 schema + Pydantic 验证
5. **Agents as tools** — `Agent.as_tool()` 让一个 agent 成为另一个的子工具

**编排模式**:
- **LLM 驱动**: Agent 自主规划，用 tools 采取行动，用 handoffs 委托
- **代码驱动**: 结构化输出分类 → 链式 agent → while 循环+评估 → 并行 (asyncio.gather)
- **混合模式**: triage agent handoff 给 specialist，specialist 再用其他 agent 做 subtask

**Handoff 机制 (核心)**:
- 表现为 LLM 可调用的 tool（`transfer_to_<agent_name>`）
- 支持 `input_type`（Pydantic schema）让 LLM 在 handoff 时传递结构化元数据
- 支持 `input_filter` 控制历史消息传递（可剥离工具调用记录等）
- `on_handoff` 回调可在委托触发时执行逻辑（如预取数据）
- 新增 `nest_handoff_history` beta：将前序对话压缩为摘要消息

**亮点**:
- Realtime Agent：基于 gpt-realtime-1.5 的语音 agent
- Hosted container shell + skills：在 OpenAI 托管容器中执行 shell 命令
- Codex tool（实验性）：从 agent 调用中启动 Codex 工作空间任务
- Session 层：持久化内存层维护工作上下文

**安装**: `pip install openai-agents`

---

### 2. Google Agent Development Kit (ADK)

**定位**: 模块化、多语言 Agent 开发框架，优化 Gemini 生态但模型无关。

**支持语言**: Python, TypeScript, Go 1.0, Java 1.0（全 1.0 稳定版）

**核心 Agent 类型 (3 大类)**:

| 类型 | 原语 | 特点 |
|------|------|------|
| **LLM Agent** (LlmAgent) | LLM 驱动推理 | 自然语言理解/规划/工具调用 |
| **Workflow Agent** | Sequential / Parallel / Loop | 确定性编排，不依赖 LLM 做流程控制 |
| **Custom Agent** | 继承 BaseAgent | 完全自定义逻辑 |

**编排哲学**: 区别于 OpenAI 的"让 LLM 决定"，ADK 明确区分了：
- **LLM 驱动的动态路由**（LlmAgent transfer）
- **确定性的工作流编排**（Sequential/Parallel/Loop agents）
- 两者可自由组合

**扩展机制**:
- Models（可换不同 LLM）
- Artifacts（持久化输出：文件、代码、文档）
- Pre-built tools + Custom tools
- Plugins（复杂预打包行为）
- Skills（AgentSkills.io 生态，适配上下文窗口）
- Callbacks（执行生命周期钩子）

**部署**: 本地运行 → Vertex AI Agent Engine → Cloud Run / Docker

**安全注意**: LiteLLM 供应链攻击（2026-03-24）影响 ADK Python 的 eval/extensions extras

**安装**: `pip install google-adk`

---

### 3. Anthropic (无独立 Agent SDK)

Anthropic 目前没有像 OpenAI/Google 那样的独立 Agent 框架。其策略是：
- 提供 Claude API + tool_use 能力
- 通过 cookbook 示例（claude-cookbooks）教导 Agent 模式
- 依赖社区框架（如 LangChain、CrewAI）或自定义编排

---

## 二、架构对比

| 维度 | OpenAI Agents SDK | Google ADK |
|------|------------------|------------|
| **核心理念** | 极简原语，LLM 驱动 | 模块化，明确区分 LLM/Workflow |
| **原语数量** | 3 个 | 3 类 Agent + Workflow 原语 |
| **语言支持** | Python only | Python/TS/Go/Java |
| **编排方式** | LLM 自主 + 代码编排 | LLM 路由 + 确定性 Workflow |
| **Handoff** | 一等公民，支持 input_type/filter/nesting | Transfer 机制 |
| **工具系统** | 5 类，含 hosted tool search | Pre-built + Custom + MCP |
| **Tracing** | 内置 | 内置 Evaluation |
| **部署** | 自行部署 | Vertex AI / Cloud Run / Docker |
| **学习曲线** | 低（Python-first） | 中（更多概念） |
| **生产就绪** | ✅ | ✅ (1.0 稳定版) |

---

## 三、关键设计模式总结

### Pattern 1: Manager + Specialists (Agents as Tools)
Manager agent 保持对话控制权，通过 `Agent.as_tool()` 调用专家 agent。

### Pattern 2: Triage + Handoff
Triage agent 将对话路由给专家 agent，专家接管后续交互。

### Pattern 3: Pipeline (Sequential Workflow)
Agent 输出作为下一个输入：研究 → 大纲 → 正文 → 审阅 → 改进。

### Pattern 4: Parallel + Merge
多个独立 agent 并行执行，结果合并（适合不相互依赖的子任务）。

### Pattern 5: Loop with Evaluator
执行 agent + 评估 agent 在 while 循环中迭代，直到质量达标。

---

## 四、与 OpenClaw 的关联

OpenClaw 的架构可以看到这些模式的影响：
- **Subagents** ≈ Agents as Tools
- **Sessions spawn** ≈ Handoffs to isolated sessions
- **Cron jobs** ≈ Workflow Agents (Scheduled)
- **Heartbeat** ≈ Loop Agent with periodic checks
- **Skills** ≈ Tools + Plugins

---

## 五、下次探索方向

- [ ] MCP (Model Context Protocol) 协议深入
- [ ] ACP (Agent Communication Protocol) 标准
- [ ] Agent 评估 (Evals) 最佳实践
- [ ] 实战：用 OpenAI Agents SDK 构建一个小项目
