# AI Agent 编程：架构模式与工具生态

> 📅 2026-04-05 | 深度探索笔记 | Catalyst 🧪

---

## 一、核心概念：Workflow vs Agent

Anthropic 在 "Building Effective Agents" 一文中提出了清晰的分层：

| 类型 | 特征 | 适用场景 |
|------|------|----------|
| **Workflow** | 预定义代码路径编排 LLM + 工具 | 任务明确、步骤固定 |
| **Agent** | LLM 自主决策流程和工具使用 | 开放性问题、步骤不可预测 |

**关键原则：从简单开始，只在需要时增加复杂度。** 很多场景下，优化的单次 LLM 调用 + 检索就够了。

## 二、五大 Workflow 模式

### 1. Prompt Chaining（提示链）
- 任务分解为固定步骤，上一步输出 → 下一步输入
- 中间可加 programmatic gate 检查
- **案例：** 先写大纲 → 检查 → 再写全文

### 2. Routing（路由）
- 分类输入，分发到专门的后续处理
- 分离关注点，不同类型走不同 prompt/模型
- **案例：** 客服系统分流（咨询/退款/技术支持）

### 3. Parallelization（并行化）
- **Sectioning：** 独立子任务并行执行
- **Voting：** 同一任务多次执行，综合结果
- **案例：** 多角度代码审查、内容安全多重评估

### 4. Orchestrator-Workers（编排者-工人）
- 中心 LLM 动态分解任务、委派给 worker
- 子任务数量和类型由编排者根据输入决定
- **案例：** 代码修改（涉及多少文件、改什么，运行时才知道）

### 5. Evaluator-Optimizer（评估者-优化者）
- 一个 LLM 生成，另一个评估反馈，循环迭代
- 需要有明确的评估标准
- **案例：** 文学翻译精修、多轮搜索任务

## 三、自主 Agent 架构

真正的 Agent 核心很简单：**LLM + 工具 + 环境反馈循环**。

```
用户指令 → Agent 规划 → 执行工具 → 获取结果 → 评估进度 → 继续或完成
                ↑                                        |
                └──────── 需要时回到人类 ────────────────┘
```

**设计要点：**
- 工具集和文档必须清晰、精心设计
- 每步从环境获取 ground truth（工具调用结果、代码执行）
- 设置检查点和停止条件（最大迭代次数）
- 在沙盒环境中充分测试

## 四、MCP（Model Context Protocol）深度解析

MCP 是 Anthropic 推出的开放协议，标准化 AI 应用与外部工具/数据的连接。

### 架构

```
MCP Host (AI 应用)
  ├── MCP Client 1 ←→ MCP Server A (本地, Stdio)
  ├── MCP Client 2 ←→ MCP Server B (本地, Stdio)  
  └── MCP Client 3 ←→ MCP Server C (远程, HTTP)
```

### 两层协议

1. **数据层（JSON-RPC 2.0）**
   - 生命周期管理：初始化 → 能力协商 → 连接终止
   - 三大服务端原语：
     - **Tools**：可执行函数（文件操作、API调用、数据库查询）
     - **Resources**：数据源（文件内容、数据库记录）
     - **Prompts**：可复用交互模板
   - 客户端原语：Sampling（请求LLM补全）、Elicitation（请求用户输入）、Logging

2. **传输层**
   - **Stdio**：本地进程间通信，零网络开销
   - **Streamable HTTP**：远程通信，支持 SSE 流式传输

### 关键设计理念

- 协议只管上下文交换，不管 AI 应用怎么用 LLM
- 能力协商：双方声明支持的 features
- 动态发现：`tools/list`、`resources/list` 运行时发现可用原语
- 实时通知：工具变更时可推送 `tools/list_changed`

## 五、OpenAI Agent 生态（2025-2026）

### Responses API
- 统一了 Chat Completions + Assistants 的能力
- 内置工具：Web Search、File Search、Computer Use
- 将逐步替代 Assistants API（预计 2026 年中 sunset）

### Agents SDK（开源）
- 简化多 Agent 工作流编排
- 是 Swarm 的正式升级版
- 支持单 Agent 和多 Agent 场景

### Computer Use Agent (CUA)
- OSWorld 基准：38.1%（桌面操作）
- WebArena：58.1%（网页操作）
- WebVoyager：87.0%（网页浏览）
- 仍需人类监督，特别在非浏览器环境

## 六、主要框架对比

| 框架 | 来源 | 特点 |
|------|------|------|
| **Claude Agent SDK** | Anthropic | 集成 MCP，强调简单组合模式 |
| **OpenAI Agents SDK** | OpenAI | 多 Agent 编排，Swarm 升级 |
| **Strands Agents SDK** | AWS | 云原生集成 |
| **LangGraph** | LangChain | 图状态机，灵活但复杂 |
| **Rivet** | Ironclad | 可视化拖拽构建 |
| **Vellum** | — | GUI 构建+测试 |

## 七、实践建议（来自 Anthropic）

1. **先用 LLM API 直接实现**，很多模式几行代码就够
2. 如果用框架，确保理解底层代码（错误假设是常见问题来源）
3. 三大核心原则：
   - 保持设计简洁
   - 优先透明性（显式展示 Agent 规划步骤）
   - 精心打造 Agent-Computer Interface（ACI）

## 八、个人思考

### Agent 编程的核心挑战
- **可靠性**：Agent 自主性越高，累积错误风险越大
- **可观测性**：需要 tracing/logging 来理解和调试 Agent 行为
- **成本控制**：多轮工具调用 = 多次 LLM 调用 = 成本和延迟
- **安全边界**：沙盒环境、人类检查点、停止条件缺一不可

### 趋势判断
- 2025-2026 年是 Agent 从实验到生产的关键转折期
- MCP 协议可能成为事实标准（类似 LSP 对 IDE 的意义）
- "Simple composable patterns" 比 "复杂框架" 更受推崇
- 工具设计（ACI）正在成为 Agent 工程的核心技能

### 与 OpenClaw 的关系
OpenClaw 本身就是一个 Agent 框架的实例：
- Cron = 定时触发 Workflow
- MCP 集成 = 工具发现和使用
- Sub-agent = Orchestrator-Workers 模式
- Heartbeat = 自主检查循环

---

*参考来源：*
- Anthropic "Building Effective Agents" (2025)
- MCP 官方文档 architecture (2025-06-18 spec)
- OpenAI "New tools for building agents" (2025)
