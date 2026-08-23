# Agent Skills: 模块化能力架构的崛起

**日期:** 2026-07-18
**主题:** Agent Skills — 从单体 LLM 到模块化技能组合的范式转变
**调研范围:** 10+ 篇论文/系统/行业报告

---

## 核心概念

### 1. 技能抽象层 (Skill Abstraction Layer)
在原子工具（Tool）和高层次目标（Goal）之间，引入了一个中间层：**Skill**。工具执行单一动作并返回结果；技能编排多个工具，包含策略、错误处理、重试逻辑和结构化输出。这不是简单的封装，而是从"能做什么"到"知道怎么做"的质变。

### 2. 渐进式披露 (Progressive Disclosure)
三级上下文管理协议：
- **Level 1 — 发现**（~100 tokens/skill）：仅加载 name + description 到系统提示
- **Level 2 — 激活**：触发时加载完整 SKILL.md 正文
- **Level 3 — 引用**：按需加载 references/ 目录下的领域知识

这意味着一个部署了 30+ 技能的 agent，正常会话中只消耗 ~3000 tokens 的发现层开销，相比单体 prompt 的 60,000 tokens 节省 3-8 倍。

### 3. SKILL.md 开放标准
Anthropic 于 2025年12月18日发布，48小时内 Microsoft 和 OpenAI 宣布支持。到 2026年3月，32 个厂商的工具（Gemini CLI、JetBrains Junie、AWS Kiro、Block Goose 等）全部兼容同一格式。社区技能数量从 2025年12月的几千个爆发到 2026年Q2 的 800,000+。

### 4. 技能组合模式
四种主要组合模式：
- **顺序管道**：Planner → Worker → Reviewer → Publisher
- **并行扇出**：多个子技能并行执行，输出合并
- **分形组合**：技能可以调用其他技能，形成递归结构
- **条件路由**：技能内部包含决策逻辑，根据输入分发到不同子技能

### 5. 技能供应链安全
26.1%-36.8% 的社区技能包含漏洞（三项独立研究），76 个被确认为恶意载荷。攻击模式包括数据外泄、反向 shell、权限越界和依赖混淆。

---

## 关键洞察

### 洞察 1: 技能不是工具的封装，而是"程序性知识"的载体
论文 [arxiv:2602.12430] 精辟指出：工具执行并返回结果，技能**重塑 agent 对任务的理解**。一个 PDF 处理技能不是暴露一个"填写表单"函数，而是教会 agent 如何看待 PDF 操作、该用什么库、什么边界情况需要处理。这对应人类专家与新手的根本差异——不是会不会用某个工具，而是有没有解决这类问题的"操作手册"。

### 洞察 2: 技能获取的四种范式揭示了完全不同的设计哲学
| 获取方式 | 代表系统 | 核心思想 |
|---------|---------|---------|
| 人工编写 | Anthropic Skills | 把领域专家知识编码为 Markdown |
| 强化学习 | SAGE | 技能链间复用，Sequential Rollout + Skill-integrated Reward |
| 自主发现 | SEAgent | 在未见软件中自主探索，World State Model + Curriculum Generator |
| 组合合成 | Agentic Proposing | 从库中选择并组合模块化推理技能 |

SAGE 在 AppWorld 上比基线 GRPO 提升 8.9%，同时减少 26% 的交互步数和 59% 的 token 消耗。SEAgent 在 OSWorld 上从 11.3% 提升到 34.5%。

### 洞察 3: 结构化技能组合是一等公民问题
SkillComposer [arxiv:2606.32025] 把技能选择形式化为**结构化预测问题**：给定任务和技能库，预测一个可执行的技能计划，联合指定激活子集、数量和执行顺序。使用受约束的自回归解码器在技能标识符上生成，一次解码 pass 就能同时确定三个维度。在 GPT-5.2-Codex 上提升 pass rate 23.1 个百分点。

### 洞察 4: 多 agent 系统可以"编译"为单 agent 技能库
Li (2026) 的发现非常挑衅：多 agent 系统通常可以被"编译"为单 agent + 技能库，大幅减少 token 使用和延迟。但存在**相变**——超过临界库大小时，技能选择准确率急剧下降。这暗示了单 agent 有效管理技能数量的根本极限。

### 洞察 5: 技能供应链是 npm 历史的重演
36.8% 的社区技能有安全问题。主要市场（SkillsMP 66K+、Skills.sh 89K+）正在实现自动扫描和人工审核。签名技能、能力清单、沙箱执行、注册表审核等手段正在发展。但速度远落后于技能数量的爆发速度。

### 洞察 6: 循环子任务图的灵活性不是免费的
arxiv:2604.22820 的 CCSG 研究表明：
- 在**需要恢复的领域**（如 ALFWorld），循环回溯确实有帮助
- 在**有先决条件链的领域**（如 TextCraft），循环灵活性主要增加开销
- 在**外部瓶颈领域**（如 Finance-Agent），工作流灵活性几乎无关紧要
**实践启示：** 匹配工作流结构与领域特征，不要盲目追求最大灵活性。

### 洞察 7: 跨平台可移植性是真的，但有细微差别
SKILL.md 格式确实可以在 Claude Code、Codex CLI、Gemini CLI 之间互通。但引用绝对路径或依赖运行时特定功能的技能不是真正可移植的。最佳实践：使用相对路径、运行时无关的工具调用、显式文档化运行时依赖。

---

## 可落地 Next Actions

1. **审视自己的 skill 库**：用渐进式披露的三级框架检查每个 skill 的 description、body、references 是否分层合理
2. **引入技能签名验证**：在生产部署中，至少对第三方技能实现 hash 校验 + 来源审查
3. **实验技能组合模式**：将常用的多步骤工作流从单体 prompt 重构为顺序管道技能
4. **监控技能库规模**：关注"相变"临界点——当 skill 数量超过某个阈值时，选择准确率可能急剧下降
5. **编写可移植技能**：遵循相对路径、运行时无关工具调用、显式依赖文档化的最佳实践
6. **关注 SkillComposer 方向**：结构化技能组合预测可能是下一代 agent 路由的核心技术

---

## 参考论文与系统

1. [arxiv:2602.12430] Agent Skills for LLMs: Architecture, Acquisition, Security, and the Path Forward (ACM CAIS 2026 Workshop)
2. [arxiv:2606.32025] Generative Skill Composition for LLM Agents (SkillComposer)
3. [arxiv:2604.22820] Complete Cyclic Subtask Graphs (CCSG) study
4. [arxiv:2602.14922] ReusStdFlow: Extraction-Storage-Construction for workflow reuse
5. SAGE: Skill Augmented GRPO for self-Evolution (Wang et al., 2025)
6. SEAgent: Autonomous Skill Discovery (Sun et al., 2025)
7. CUA-Skill: Structured Skill Bases (Chen et al., 2026)
8. Agentic Proposing: Compositional Skill Synthesis (Jiao et al., 2026)
9. Li (2026): Multi-Agent to Single-Agent Skill Compilation
10. Anthropic Agent Skills Open Standard (Dec 2025)
11. Voyager: Open-Ended Embodied Agent (Wang et al., NeurIPS 2023)
12. Snyk: Agent Skill Security Analysis (2026)
13. Zylos Research: Agent Skill Composition in Production (May 2026)
