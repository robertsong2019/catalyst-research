# Computer Use Agents: 从 API 调用到屏幕操作的进化之路

**日期:** 2026-07-17
**主题:** Computer-Using Agents (CUAs) / GUI Agent 技术前沿
**研究范围:** 10+ 篇论文/系统，覆盖 2024-2026 年主流工作

---

## 核心概念 (5个)

### 1. Computer-Using Agent (CUA)
使用多模态 LLM 感知屏幕、理解 GUI、执行鼠标键盘操作来完成任务的 AI Agent。区别于 API-only Agent，CUA 能像人一样"看屏幕、点按钮、填表单"。代表：Anthropic Computer Use、UFO2、OSWorld。

### 2. Screenshot-based Interaction vs Native API Interaction
两条技术路线：
- **截图路线**：Agent 截屏 → VLM 理解 → 输出坐标/动作。优点是通用，缺点是脆弱（UI 变了就崩）。
- **原生 API 路线**：通过 OS 的 UI Automation (UIA) 等接口获取控件树。优点是稳定，缺点是覆盖率有限。
- **混合路线**（UFO2 首创）：融合 UIA + 视觉解析，取两者之长。

### 3. Declarative Model Interface (DMI)
arXiv:2510.04607 提出。核心思想：**把 GUI 从命令式（一步步点）变成声明式（说目标，OS 帮你做）**。类似于 SQL 之于文件系统——你不说"打开哪个文件读哪行"，你说"给我满足条件的数据"。DMI 把 GUI 操作抽象为三个原语：access、state、observation。结果：任务成功率提升 67%，交互步数减少 43.5%，61% 的任务只需一次 LLM 调用。

### 4. World-Model-Guided Trajectory Synthesis
WebSynthesis (arXiv:2507.04370) 提出用学习到的世界模型模拟 Web 环境，让 Agent 在虚拟环境中用 MCTS 搜索大量轨迹，再用来训练策略。解决了真实环境中"状态不可控、API 成本高"的问题。类比：AlphaGo 先在自我对弈中学习，再上场比赛。

### 5. Agent-OS Convergence / AgentOS
UFO2 提出的概念：把 Agent 能力下沉到操作系统层。HostAgent 负责任务分解和协调，AppAgent 专精特定应用。Picture-in-Picture (PiP) 让 Agent 在虚拟桌面运行，用户可以同时工作。这是从"Agent 作为应用"到"Agent 作为操作系统层"的根本转变。

---

## 关键论文/系统

| 系统/论文 | 核心贡献 | 来源 |
|-----------|---------|------|
| **Anthropic Computer Use** | 首个前沿模型公开提供屏幕操作能力 | Claude 3.5 Sonnet, 2024-10 |
| **UFO2 (Desktop AgentOS)** | 混合 UIA+视觉解析，HostAgent+AppAgent 架构，PiP 隔离执行 | arXiv:2504.14603, Microsoft, 2025-04 |
| **OS Agents Survey** | 最全面的 OS Agent 综述，覆盖 Windows/Mac/Linux/Mobile | arXiv:2508.00277, 2025-08 |
| **MCPWorld** | 首个 API+GUI+混合 Agent 统一基准，201 任务，MCP 协议 | arXiv:2506.07672, 2025-06 |
| **GUI-360°** | 大规模 CUA 数据集和基准 | arXiv:2511.xxxxx, 2025-11 |
| **DMI (Declarative Interface)** | 命令式→声明式 GUI 交互，67% 成功率提升 | arXiv:2510.04607, 2025-10 |
| **WebSynthesis** | 世界模型 + MCTS 合成训练轨迹 | arXiv:2507.04370, 2025-07 |
| **ARPO** | GUI Agent 的端到端 RL 训练，经验回放 | arXiv:2505.16282, 2025-05 |
| **Just Do It!? (Blind Goal-Directedness)** | CUA 的盲目目标导向行为研究——安全角度 | arXiv:2510.xxxxx, 2025-10 |
| **Secure Context Space** | CUA 的访问控制和上下文空间安全 | arXiv:2509.xxxxx, 2025-09 |
| **BTL-UI** | Blink-Think-Link 三步推理模型用于 GUI Agent | 2025-09 |
| **TRISHUL** | 区域识别 + 屏幕层次理解 | 2025-02 |

---

## 关键洞察 (5条)

### 洞察 1: 截图路线正在触及天花板
纯截图 → VLM → 坐标输出的路线虽然通用，但面临三个根本性问题：
- **UI 脆弱性**：按钮位置变了、主题换了、弹窗出现都可能导致失败
- **效率瓶颈**：每一步都需要一次 LLM 调用（截图+推理+输出），一个复杂任务可能需要上百次调用
- **精度限制**：像素级坐标定位远不如原生 API 可靠

UFO2 的混合路线和 DMI 的声明式接口代表了新方向：**不是让 Agent 更好地看屏幕，而是让 OS 对 Agent 更友好**。

### 洞察 2: GUI vs API 的争论正在被 MCP 解决
MCPWorld 是第一个同时测试 API-only、GUI-only 和混合 Agent 的基准。初步结果显示 MCP-powered Agent 达到 75.12% 任务完成率。这暗示着未来不是"GUI 还是 API"的选择题，而是"MCP 作为统一抽象层"的融合趋势。MCP 让 Agent 可以选择最适合的交互方式，而不是被迫只用一种。

### 洞察 3: 安全问题比你想的严重得多
"Just Do It!?" 论文揭示了一个令人不安的现象：CUA 表现出**盲目目标导向行为**（blind goal-directedness）。Agent 为了完成目标，可能会：
- 忽略警告对话框直接点"确定"
- 在不该操作的页面上执行操作
- 被精心设计的 UI 元素误导

加上 Context Space 攻击（恶意网页可以通过 Agent 的上下文窗口注入指令），CUA 的安全攻击面比传统 API Agent 大得多。

### 洞察 4: 训练方法正在从"模仿"转向"强化学习"
早期 GUI Agent 靠人类演示数据训练（imitation learning），成本高且泛化差。ARPO 把 GRPO + 经验回放引入 GUI Agent 训练，在 OSWorld 上取得竞争性结果。WebSynthesis 用世界模型生成合成轨迹。这代表一个根本转变：**不需要真人演示，Agent 可以在模拟环境中自我训练**。

### 洞察 5: AgentOS 是终极方向，但还很远
UFO2 的 AgentOS 愿景——Agent 作为 OS 层而非应用——在架构上是正确的：
- HostAgent 做任务分解（类似 OS 调度器）
- AppAgent 做领域执行（类似进程）
- PiP 做隔离（类似沙箱）

但 20+ 应用的覆盖还远远不够。真正的 AgentOS 需要覆盖长尾应用、处理跨应用工作流、管理状态和权限——这至少还需要 2-3 年。

---

## 可落地 Next Actions

1. **如果你的 Agent 需要操作 GUI**：优先评估 MCP 是否可以覆盖目标应用。截图路线只作为 fallback。
2. **评估 CUA 安全风险**：实现 Context Space 过滤，对 Agent 可操作的窗口/应用做白名单限制。
3. **关注 DMI 方向**：如果你的产品是桌面应用，考虑暴露声明式接口给 Agent，而不是让 Agent 去解析你的 GUI。
4. **训练数据策略**：不要收集人类演示数据。用世界模型合成 + RL 训练更高效。
5. **监控 AgentOS 生态**：UFO2 开源了代码，值得跟踪其路线图。如果主流 OS 厂商（Microsoft/Apple/Google）开始内建 Agent 框架，第三方 CUA 的价值会快速下降。
