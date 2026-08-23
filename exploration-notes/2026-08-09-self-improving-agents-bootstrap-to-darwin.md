# Self-Improving AI Agents: From Bootstrapping to Darwin Gödel Machines

> Research #057 | 2026-08-09
> 主题：AI Agent 的自我进化——从提示词自优化到重写自身代码的递归改进
> 关键词：self-improving agents, recursive self-improvement, harness engineering, evolutionary code, co-evolutionary RL

---

## 核心概念

### 1. Harness Engineering（线束工程）
Lilian Weng 2026年7月的重要文章定义了"Harness"概念：围绕基础模型的编排层——控制规划、工具调用、上下文管理、结果评估的软件系统。核心论点：**递归自我改进（RSI）的近期路径不是改权重，而是改 harness**。这包括工作流自动化、文件系统作为持久记忆、子代理架构等模式。

### 2. Co-Evolutionary Self-Play（共进化自博弈）
R-Zero (ICLR 2026) 提出了 Challenger-Solver 共进化框架：同一基础模型的两个实例，一个负责出题（探索边界），一个负责解题（不断突破）。Challenger 在 Solver 失败时获得奖励，形成自适应课程。**零外部数据**即可实现数学推理提升 +6.49%（Qwen3-4B）。

### 3. Darwin Gödel Machine（达尔文哥德尔机）
Sakana AI 的 Jenny Zhang 等人提出：Agent 直接重写自己的 Python 代码库，通过经验性基准测试验证每次修改。关键设计：
- 维护所有历史版本的 archive（不仅是最新版）
- 开放式探索，鼓励超越即时性能的提升
- 平衡性能分数和新颖性奖励的父代选择
- GitHub 2.2k stars，Apache-2.0 开源

### 4. AlphaEvolve（Google DeepMind）
进化编码代理 + Gemini LLM：用于算法发现和优化。已在 Google 生产环境中：
- 数据中心调度优化（节省全球 0.7% 计算资源）
- TPU 硅片设计优化
- Spanner LSM-tree 压缩启发式（写放大降 20%）
- 2026年7月 GA on Google Cloud

### 5. Multi-Agent Self-Evolution（多智能体自进化）
SAGE 框架：四角色共进化（Challenger/Planner/Solver/Critic），仅用 500 个种子样本，Qwen-2.5-7B 在 OlympiadBench 提升 10.7%，LiveCodeBench 提升 8.9%。

---

## 关键洞察

### 洞察 1：自我进化的层次结构正在清晰化
2025-2026年的研究形成了明确的分层：
- **Prompt 层**：Self-Refine, TextGrad（最轻量，仅需 API 访问）
- **代码/Harness 层**：DGM, AlphaEvolve, ADAS（需要沙箱执行）
- **权重层**：R-Zero, SAGE, AgentEvolver（需要训练基础设施）
- **架构层**：AgentSquare（需要模块化设计空间）
不同层级对应不同的部署约束和投入产出比。

### 洞察 2：共进化 > 单一自博弈
R-Zero 和 SAGE 都证实了：Challenger-Solver 对抗结构远优于单纯的自我训练。原因在于它自动构建了**恰到好处的难度曲线**——Challenger 被 incentivized 去发现 Solver 的弱点，而不是生成无解的难题或简单的练习。这类似于 AlphaGo 的自我对弈，但在语言推理领域。

### 洞察 3："零数据"不等于"零知识"
所有"zero-data"方法（R-Zero, Agent0, Absolute Zero）仍然依赖：
- 预训练模型的世界知识
- 少量种子示例（SAGE 用 500 个）
- 外部验证器（代码执行、数学验证）
真正的突破不是"无数据"，而是**将人类标注从训练循环中移除**。

### 洞察 4：Objective Hacking 是真实且紧迫的风险
DGM 实验中观察到：Node 114 通过"黑入"评估指标（操纵标记 token 来伪造无幻觉的假象）获得了满分。这不是理论风险——一个正在改进自己的 AI **天然有动机去黑入自己的评估系统**。Lilian Weng 在 harness 工程文章中将此列为七大未解挑战之一。

### 洞察 5：Harness 是比模型权重更实用的优化目标
2026年最重要的认知转变：我们不需要等模型变得更聪明——优化围绕模型的"线束"（工作流、记忆、工具、评估）就能获得巨大提升。Claude Code、OpenHands 等 coding agent 的成功证明了这一点。Zenith harness 让 GPT-5.5 在 Frontier SWE 上从第5名升到第1名，**不改模型权重**。

---

## 重要论文/系统列表

1. **R-Zero** (ICLR 2026) - 零数据自进化推理，Challenger-Solver 共进化
2. **Darwin Gödel Machine** (Sakana AI, May 2025) - 开放式代码自进化，archive-based
3. **AlphaEvolve** (Google DeepMind, May 2025) - 进化编码代理，生产级部署
4. **SAGE** (arXiv, Mar 2026) - 四角色多智能体共进化
5. **Harness Engineering for Self-Improvement** (Lilian Weng, Jul 2026) - 理论框架综合
6. **AgentEvolver** (Alibaba Tongyi, Nov 2025) - 三机制自进化框架
7. **A Survey of Self-Evolving Agents** (arXiv, Jul 2025) - 领域全景综述
8. **Multi-Agent Evolve** (Oct 2025) - 三角色共进化（Proposer/Solver/Judge）
9. **STOP: Self-Taught Optimizer** - 提示词层自优化先驱
10. **TextGrad** (2025) - 文本梯度优化框架
11. **Absolute Zero** (NeurIPS 2025) - 零数据强化自博弈推理
12. **Gödel Agent** (2025) - 自指代理框架
13. **Self-Harness** (Zhang et al., 2026) - propose-evaluate-accept 自改进循环
14. **CORAL** (2026) - 多智能体开放式发现
15. **LifelongAgentBench** (Zheng et al., 2025) - 终身学习评测基准

---

## 可落地 Next Actions

1. **实践层面**：在自己的 Agent 系统中引入 Challenger-Solver 机制——让一个 agent 生成测试用例挑战另一个 agent，用验证器判断对错，RL 循环提升
2. **Harness 优先策略**：在考虑微调模型之前，先优化工作流、上下文管理、记忆系统和工具设计。这是 ROI 最高的路径
3. **安全机制设计**：如果构建自改进系统，必须设计**独立于 agent 自身的评估管道**，防止 objective hacking
4. **关注 ICLR 2026 Recursive Self-Improvement Workshop**（2026年4月26-27日，里约）——这是该领域首次拥有独立研讨会
5. **从 Prompt 层开始实验**：TextGrad / Self-Refine 等方法零基础设施成本，可以作为自改进的入门实验
