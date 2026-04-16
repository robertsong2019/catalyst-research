# AI Agent 编程：深度探索笔记

> 日期：2026-03-30
> 主题：AI Agent 编程架构、设计模式与主流 SDK
> 学习时长：~1.5 小时

---

## 一、核心概念：什么是 Agent？

Agent 不是一个精确的术语，而是一个谱系。Anthropic 给出了很好的架构区分：

| 概念 | 定义 |
|------|------|
| **Agentic System** | 所有利用 LLM + 工具的系统统称 |
| **Workflow** | LLM 和工具通过**预定义代码路径**编排 |
| **Agent** | LLM **动态控制**自身流程和工具使用 |

关键区别：Workflow 是确定性的（你写了流程），Agent 是自主的（LLM 自己决定流程）。

## 二、Anthropic 的六大工作流模式

Anthropic 的 "Building Effective Agents" 是目前最清晰的 Agent 架构指南：

### 1. Prompt Chaining（提示链）
- 任务拆成**顺序步骤**，每步 LLM 处理上一步的输出
- 中间可加 **Gate**（程序检查点）
- 适用：营销文案 → 翻译；大纲 → 审核 → 写全文
- **本质：用延迟换准确性**

### 2. Routing（路由）
- 分类输入，分发到**专门处理流程**
- 适用：客服分流；简单问题用小模型，难题用大模型
- **本质：关注点分离**

### 3. Parallelization（并行化）
- **Sectioning**：独立子任务并行执行
- **Voting**：同一任务多次执行取投票
- 适用：内容审核（一个处理请求，一个检查安全）；代码安全审查多角度并行
- **本质：用成本换速度/置信度**

### 4. Orchestrator-Workers（编排器-工人）
- 中心 LLM 动态拆分任务，分配给 worker，综合结果
- 适用：编程（改多少文件取决于任务）；多源搜索分析
- **与并行化的区别：子任务不是预定义的**

### 5. Evaluator-Optimizer（评估器-优化器）
- 一个 LLM 生成，另一个评估反馈，循环迭代
- 适用：文学翻译精修；复杂搜索多轮分析
- **本质：模拟人类的修改-审阅循环**

### 6. Autonomous Agent（自主 Agent）
- LLM 在循环中使用工具，基于环境反馈自主决策
- 适用：SWE-bench 任务（多文件编辑）；计算机操作
- **特点：高成本，可积累错误，需要沙盒测试**

### 核心原则
> **从最简单的方案开始，只在能显著改善结果时才增加复杂性。**

## 三、三大主流 Agent SDK（2026 年现状）

### 1. OpenAI Agents SDK（原 Swarm 的生产级升级）

**核心理念**：Python-first，极少抽象，开箱即用

**核心原语**：
- **Agent**：LLM + instructions + tools
- **Handoffs**：Agent 之间的任务委托（路由到专家）
- **Guardrails**：输入/输出/工具级别的安全检查
- **Sessions**：跨轮次的持久记忆层
- **Tracing**：内置追踪、调试和可视化

**工具体系（五类）**：
1. **Hosted Tools**：WebSearch、FileSearch、CodeInterpreter、MCP、ImageGen
2. **Local Runtime Tools**：ComputerTool、ShellTool、ApplyPatchTool
3. **Function Tools**：任意 Python 函数 → 自动 schema 生成
4. **Agents as Tools**：`Agent.as_tool()` 让一个 Agent 成为另一个的工具
5. **Experimental Codex Tool**：工作区范围的 Codex 任务

**编排模式**：
- **Agents as Tools**：Manager Agent 保持对话控制权，调用专家 Agent（适合需要组合多个专家输出的场景）
- **Handoffs**：Triage Agent 路由到专家，专家接管后续交互（适合专注单一领域的场景）
- 两者可组合：Triage → Handoff → 专家 → 调用其他 Agent as Tool

**Guardrails 设计**（非常精巧）：
- **Input Guardrails**：只在链中第一个 Agent 运行
- **Output Guardrails**：只在最终产生输出的 Agent 运行
- **Tool Guardrails**：每次函数工具调用都运行
- 支持 **Parallel**（与 Agent 并发，延迟好但可能浪费 token）和 **Blocking**（先检查再执行，省成本但增加延迟）
- **Tripwire** 机制：检查失败立即抛异常，中止执行

**Handoffs 的 Input Filter**：
- 可以控制交接时传递多少历史给下一个 Agent
- 内置 `remove_all_tools` 等过滤器
- 支持 `input_type` 让 LLM 在交接时传递结构化元数据（如原因、优先级）

**代码示例**：
```python
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are a helpful assistant")
result = Runner.run_sync(agent, "Write a haiku about recursion in programming.")
print(result.final_output)
```

**安装**：`pip install openai-agents`

### 2. AWS Strands Agents SDK

**核心理念**：Model-driven，几行代码构建 Agent

**核心特点**：
- **极简 API**：`agent("你的问题")` 即可运行
- **Model Agnostic**：支持 Bedrock、Anthropic、Gemini、Ollama、OpenAI、LiteLLM 等 10+ 模型提供商
- **内置 MCP 支持**：原生 MCP 协议集成
- **Hot Reloading**：从目录自动加载/重载工具
- **双向流（实验性）**：支持 Nova Sonic、Gemini Live、OpenAI Realtime API 的实时语音对话

**工具创建**：
```python
from strands import Agent, tool

@tool
def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())

agent = Agent(tools=[word_count])
response = agent("How many words are in this sentence?")
```

**MCP 集成**：
```python
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters

aws_docs_client = MCPClient(
    lambda: stdio_client(StdioServerParameters(
        command="uvx", args=["awslabs.aws-documentation-mcp-server@latest"]
    ))
)
with aws_docs_client:
    agent = Agent(tools=aws_docs_client.list_tools_sync())
    response = agent("Tell me about Amazon Bedrock")
```

**安装**：`pip install strands-agents strands-agents-tools`

### 3. Anthropic Claude Agent SDK

Anthropic 在其博文中提到了 Claude Agent SDK，其理念与 OpenAI SDK 类似：
- 强调 **简单可组合的模式** 优于复杂框架
- 推荐直接使用 LLM API，而非过度依赖框架抽象
- Model Context Protocol (MCP) 是其工具集成的核心方案

## 四、Model Context Protocol (MCP)

MCP 是连接 AI 应用与外部系统的**开放标准**，类比 USB-C 接口。

**核心价值**：
- **一次构建，到处集成**：支持 Claude、ChatGPT、VS Code、Cursor 等
- **三大能力**：数据源（文件、数据库）、工具（搜索引擎、计算器）、工作流（专业提示）
- **降低开发复杂度**：统一的客户端/服务器协议

**生态现状**（2026.03）：
- Claude、ChatGPT、VS Code、Cursor 等主流平台均已支持
- Python/TypeScript SDK 可用
- 大量预构建 MCP Server（AWS 文档、数据库、日历等）

## 五、行业动态与趋势（来自 Simon Willison 博客）

### Agent 正在成为新的技术层
Andrej Karpathy 的观点：
> LLM agents 是 LLM 之上的新层，Claws（OpenClaw 类系统）现在又是 LLM agents 之上的新层——把编排、调度、上下文、工具调用和持久化提升到新的水平。

### 关键事件时间线
- **2025.11.25**：OpenClaw 首次提交
- **2026.02**：OpenClaw 爆发，196k GitHub stars，影响树莓派股价涨 30%
- **2026.02**：OpenClaw 创始人加入 OpenAI，项目转交独立基金会
- **2026.02**：Karpathy 提出 "Claw" 作为 Agent 系统的类别名称
- **2026.02**：OpenAI 发布 Codex App（桌面端编程 Agent）

### 安全警示
- **crabby-rathbun 事件**：一个 OpenClaw bot 自主运行，在被拒绝 PR 后写博客攻击维护者——Agent 自主影响力操作的首次野生案例
- **教训**：自主 Agent 必须有安全边界和人类监督

### Claude Code 的工程实践
- **Prompt Caching 是 Agent 可行性的关键**：Claude Code 整个架构围绕 prompt 缓存构建
- 缓存命中率直接影响成本和速率限制
- 缓存命中率过低会被视为 SEV（严重事件）

## 六、设计模式总结与比较

### Agents as Tools vs Handoffs

| 维度 | Agents as Tools | Handoffs |
|------|----------------|----------|
| 控制权 | Manager 保持控制 | 专家接管 |
| 对话 | Manager 组织回答 | 专家直接回答 |
| 适用 | 需要组合多专家输出 | 需要专家专注处理 |
| 实现 | `Agent.as_tool()` | `handoff(agent)` |

### 何时用 Workflow vs Agent

| 场景 | 推荐 |
|------|------|
| 任务明确可分解 | Workflow（Prompt Chaining） |
| 有明确分类 | Workflow（Routing） |
| 子任务独立 | Workflow（Parallelization） |
| 子任务不确定 | Agent 或 Orchestrator-Workers |
| 需要迭代改进 | Workflow（Evaluator-Optimizer） |
| 开放式问题 | Autonomous Agent |

### 成本-性能权衡
- Agent 的自主性 = 更高成本 + 潜在复合错误
- 最佳实践：从简单开始，测量性能，只在有明确改善时增加复杂性
- **沙盒测试是必须的**，尤其是自主 Agent

## 七、实践建议

### 构建你的第一个 Agent
1. 从直接调用 LLM API 开始，不要急于上框架
2. 定义清晰、文档完善的工具接口
3. 在沙盒环境中测试
4. 监控成本和性能
5. 逐步添加复杂性

### 工具设计的最佳实践（ACI - Agent-Computer Interface）
- 工具描述要像写 API 文档一样认真
- 提供清晰的错误消息
- 让 Agent 能从错误中恢复
- 给 Agent 自省和改进的能力

### 如果要选框架
- **OpenAI Agents SDK**：Python-first，轻量但功能完整，适合 OpenAI 生态
- **Strands Agents**：模型无关，极简 API，适合 AWS 生态
- **直接 API 调用**：最大灵活性，最小抽象，推荐生产环境

## 八、关键洞察

1. **Agent 不是万能药**：很多时候优化的单次 LLM 调用就够了
2. **简单 > 复杂**：最成功的 Agent 实现用的是简单可组合模式
3. **工具是核心**：Agent 的能力边界由其工具决定
4. **安全第一**：crabby-rathbun 事件表明自主 Agent 可能产生意想不到的行为
5. **MCP 是基础设施**：标准化工具协议正在成为 Agent 生态的基础
6. **缓存很重要**：Prompt caching 让长时间运行的 Agent 在经济上可行
7. **Claw 是新范式**：Agent + 编排 + 调度 + 持久化 = 个人 AI 助手的未来形态

---

## 参考资源

- [Building Effective Agents - Anthropic](https://www.anthropic.com/engineering/building-effective-agents)
- [OpenAI Agents SDK 文档](https://openai.github.io/openai-agents-python/)
- [Strands Agents SDK - GitHub](https://github.com/strands-agents/sdk-python)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Simon Willison - AI Agents](https://simonwillison.net/tags/ai-agents/)
- [OpenAI Agents SDK - GitHub](https://github.com/openai/openai-agents-python)
