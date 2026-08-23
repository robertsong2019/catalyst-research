# Agent Toolmaking: When AI Builds Its Own Tools

> Deep Research #024 — 2026-07-22
> Topic: LLM Agent Tool Creation, Self-Evolving Tool Libraries, Context-to-Weights Skill Learning
> Method: arxiv survey + production deployment analysis
> Trigger: 从 "agent 使用工具" 到 "agent 制造工具" 的范式转移

---

## 0. 为什么关注 Agent Toolmaking？

当前 AI Agent 领域有个明显矛盾：
- Agent 每次执行任务都要**从头推理**，即使昨天做过一模一样的事
- 这就像一个厨师每次做番茄炒蛋都要重新发明菜谱、重新打造厨具
- **Toolmaking** 解决的核心问题：让 Agent 把重复的推理过程**编译**成可复用的工具

类比人类文明：我们不是每次都重新发明轮子。我们制造工具、积累工具、改进工具。AI Agent 正在走同样的路。

---

## 1. 核心论文与系统（按时间线）

### 1.1 奠基期（2023）：证明 LLM 可以造工具

#### LATM — Large Language Models as Tool Makers
- **作者:** Cai, Wang, Ma, Chen, Zhou (Google DeepMind) — arXiv:2305.17126
- **核心思想:** 两阶段闭环框架：
  - **Tool Making Phase:** 强模型（GPT-4）充当"工具制造者"，为同类任务编写可复用的 Python 函数
  - **Tool Using Phase:** 弱模型（GPT-3.5）充当"工具使用者"，直接调用制造好的工具
- **关键结果:** GPT-4 制造工具 + GPT-3.5 使用工具 = GPT-4 直接做的效果，但成本大幅降低
- **核心洞察:** 工具缓存 > 响应缓存。传统 cache 存的是自然语言回答，LATM 存的是**功能**，适用范围指数级扩大
- **意义:** 第一次系统性地证明了 "LLM 可以成为工具制造者"，而不仅仅是工具使用者

#### CREATOR — Disentangling Abstract and Concrete Reasoning
- **作者:** Qian, Han, Fung, Qin, Liu, Ji — arXiv:2305.14318 (EMNLP 2023 Findings)
- **核心思想:** 将工具创建分为两层：
  - **抽象层:** 创建工具的文档和接口规范（"我需要一个能做 X 的工具"）
  - **具体层:** 实现工具的代码（"这个工具怎么做 X"）
- **关键创新:** 这种分离让 LLM 先想清楚"需要什么"再写"怎么实现"，显著减少错误
- **评估:** 在 MATH 和 TabMWP 上超越 CoT 和 Program-of-Thought
- **额外贡献:** Creation Challenge 数据集（2K 多样化问题），专门测试工具创建能力

#### Voyager — Open-Ended Embodied Agent
- **作者:** Wang et al. (NVIDIA) — arXiv:2305.16291
- **核心思想:** Minecraft 中的 LLM 终身学习Agent，三大组件：
  1. **自动课程:** 最大化探索多样性
  2. **可增长技能库:** 可执行代码形式存储，可检索复用
  3. **迭代提示:** 包含环境反馈、执行错误、自我验证
- **关键结果:** 获得 3.3x 更多独特物品，解锁关键技术树里程碑快 15.3x
- **核心洞察:** 技能是**可组合的**——简单技能组合出复杂行为，就像乐高积木
- **局限:** Minecraft 环境相对可控，真实世界的不确定性要大得多

#### Eureka — Human-Level Reward Design via Coding LLMs
- **作者:** Ma et al. — arXiv:2310.12931 (ICLR 2024)
- **核心思想:** LLM 作为进化优化器，自动生成 RL 奖励函数代码
- **方法论:** 进化循环 — GPT-4 生成候选奖励函数 → RL 训练 → 评估 → 反馈 → 改进
- **关键结果:** 29 个环境中，83% 的任务超越人类专家设计的奖励，平均提升 52%
- **核心洞察:** LLM 不只是"一次性"工具制造者，可以作为**进化搜索**的引擎

### 1.2 发展期（2024-2025）：从实验室到多场景

#### CRAFT — Creating and Retrieving from Specialized Toolsets
- **作者:** Yuan, Chen, Wang, Fung, Peng, Ji — arXiv:2309.17413 (更新至 2024)
- **核心思想:** 为不同领域定制专用工具集，通过检索增强调用
- **关键创新:** 工具不再是一把"瑞士军刀"，而是**专业工具箱**——每个领域有自己的工具集
- **贡献:** 将 toolmaking 与 RAG 结合，让 Agent 按需从工具库中检索

#### GATE — Graph-based Adaptive Tool Evolution
- **作者:** Luo et al. (中科院自动化所) — arXiv:2502.13795
- **核心思想:** 用**图结构**管理工具之间的关系，支持跨任务的工具进化
- **关键创新:**
  - 工具之间的关系用图表示（依赖、组合、替代）
  - 新任务可以触发图的局部更新，而非从零重建
  - 支持工具的"进化"——旧工具可以被新工具替代或合并
- **意义:** 第一个将图算法引入 toolmaking 的框架，让工具库有了**结构**

### 1.3 生产化期（2026）：真实世界的 ROI

#### Tool-Making and Self-Evolving LLM Agents in Low-Latency Systems
- **作者:** Kujanpää, Liu, Alam, Sura, Yang, Klinkner, Malmasi (Amazon) — arXiv:2607.08010
- **发表:** 2026年7月8日（非常新！）
- **场景:** Amazon 履约中心告警诊断系统，44 节点 SOP，异构 metric 后端
- **方法论:**
  1. 收集执行轨迹和环境观察
  2. 生成候选工具（grounded in 真实后端 schema）
  3. 对标注样本验证和修复工具
  4. 部署后 Agent 直接调用，仅在需要时回退到代码生成
- **生产数据:**
  - p50 延迟降低 **42%**
  - 端到端错误率降低 **53%**
  - 进一步简化架构后额外降低 **62%** p50 延迟
- **核心洞察:**
  - 工具返回紧凑结构化结果，天然简化了 Agent 架构
  - 版本化工具提升了可审计性，暴露规范缺口和数据漂移
  - "自进化"不是学术概念——它在工业环境中产生了可量化的 ROI

#### From History to State: Constant-Context Skill Learning
- **作者:** Xie et al. — arXiv:2605.05413
- **发表:** 2026年5月
- **核心思想:** 将"重复的 agent 工作流"从 prompt 编码到 model weights
- **方法论:**
  1. 可复用流程学习到轻量级 task-family modules
  2. 推理时只依赖当前观察 + compact state block
  3. 确定性 tracker 从任务进度生成 state block
  4. 步级 SFT + 在线 RL 训练
- **关键结果:**
  - ALFWorld: 89.6% unseen success (Qwen3-8B)
  - WebShop: 76.8% success
  - SciWorld: 66.4% unseen success
  - **Prompt tokens 减少 2-7x**
- **核心洞察:** 从 "context-based skills"（prompt）到 "weight-based skills"（fine-tuned modules）是下一步

#### 其他值得关注的系统
- **Hubble** (Shi et al., 2026): 金融领域的 agentic factor mining，安全约束下的工具生成
- **Design Conductor 2.0** (Verkor, 2026): Agent 在 80 小时内构建硬件加速器，大量使用自动生成的领域工具

---

## 2. 核心概念（3-5个）

### 概念 1: Tool Compilation（工具编译）
将推理过程从"解释执行"（每次重新推理）变为"编译执行"（一次制作，多次调用）。
- 类比：Python → C 的性能提升不是因为算法变了，而是因为执行方式从解释变成了编译
- Agent Toolmaking 做的是同样的事：把推理过程编译成确定性代码

### 概念 2: Tool Economics（工具经济学）
- **Make cost:** 一次性工具制作成本（用强模型）
- **Use cost:** 每次调用的成本（用弱模型或直接函数调用）
- **Break-even point:** 当 use_count × cost_per_use_without_tool > make_cost + use_count × cost_per_use_with_tool
- Amazon 案例：1500 次历史告警就回收了工具制作成本

### 概念 3: Tool Graph Evolution（工具图进化）
- 工具不是孤立的——它们之间有依赖、组合、替代关系
- GATE 论文用图结构表示这些关系
- 新工具可以"进化"——旧工具被更好的工具替代
- 这和人类科学工具的进化一模一样：望远镜 → 望远镜+光谱仪 → 哈勃望远镜

### 概念 4: Context-to-Weights Pipeline（从上下文到权重）
- 当前：技能作为 prompt/代码存在 context 中（每次都要消耗 token）
- 未来：技能编译进 model weights（零 token 消耗）
- 这是终极的 "tool compilation"——把工具变成了模型的"肌肉记忆"

### 概念 5: Tool Safety & Governance（工具安全与治理）
- 谁来审计自动生成的工具？
- 工具可能包含错误逻辑或被注入恶意行为
- Amazon 的方案：版本化 + 审计日志 + 数据漂移检测
- 未解决问题：跨工具的交互安全性

---

## 3. 关键洞察

### 洞察 1: Toolmaking 是 Agent 的"编译器"
人类编程语言的演进是：机器码 → 汇编 → C → Python。每一步都是在构建更高层的抽象工具。Agent Toolmaking 正在做同样的事——把 LLM 的"推理"编译成可复用的"工具"，就像人类把算法从"心算"变成"计算器"。

**实践启示:** 设计 Agent 系统时，应该默认考虑"这个操作会不会重复？如果是，就把它编译成工具"。

### 洞察 2: 强弱模型分工是经济最优解
LATM 证明了：GPT-4 制造工具 + GPT-3.5 使用工具 ≈ GPT-4 全程做的效果。这不是偶然——工具制造需要"创造力"（强模型），工具使用需要"执行力"（弱模型即可）。这和人类似：资深架构师设计系统，初级工程师写 CRUD。

**实践启示:** 不要让昂贵的模型做重复的事。让它做一次，编译成工具，然后让便宜的模型去用。

### 洞察 3: 工具库是 Agent 的"组织记忆"
Amazon 的案例最有说服力：版本化工具不仅减少了延迟和错误，还**暴露了规范缺口和数据漂移**。工具库不只是代码仓库——它是 Agent 对环境的"结构化理解"。

**实践启示:** 把工具库当作 Agent 的知识图谱来管理，版本化、可审计、可追溯。

### 洞察 4: 图结构是工具管理的下一步
GATE 论文的图结构不是装饰——它解决了"工具爆炸"问题。当工具数量从 10 个增长到 1000 个，扁平的列表不够用。你需要知道工具之间的依赖、组合、冲突关系。这和微服务架构的演进一模一样。

**实践启示:** 工具数量超过 50 个时，需要引入图结构管理工具关系。

### 洞察 5: 终极形态是 Weight-Based Skills
Constant-Context Skill Learning 论文揭示了一个趋势：prompt 中的技能描述终究要消耗 token。终极方案是把技能"烧"进模型权重——就像人类把反复练习的动作变成"肌肉记忆"。

**实践启示:** 对于高频使用的 Agent 工作流，考虑用 SFT+RL 训练轻量级模块，而不是无限增加 prompt 长度。

---

## 4. 可落地 Next Actions

### 短期（1-2周）
1. **为 amg-mcp 添加 tool-making 能力:** 当 `memory.consolidate` 检测到重复模式时，不仅去重，还生成一个可复用的"记忆工具"（函数）
2. **实现 tool-versioning:** 在现有 Agent 系统中加入工具版本管理，记录每个工具的创建时间、修改历史、使用频次
3. **工具使用统计:** 记录哪些工具被调用最多、哪些几乎不用——用于工具库的"垃圾回收"

### 中期（1-2月）
4. **构建工具依赖图:** 用图结构表示工具之间的关系（组合、替代、依赖），支持可视化
5. **强弱模型分工实验:** 在 OpenClaw 中实现 LATM 式架构——用 GLM-5 做工具制造者，用更轻的模型做工具使用者
6. **跨域工具迁移:** 测试一个领域制造的工具能否迁移到另一个领域（GATE 的核心问题）

### 长期（3-6月）
7. **Context-to-Weights pipeline:** 为高频 Agent 工作流训练轻量级 LoRA 模块
8. **工具安全审计框架:** 自动化检测生成工具中的逻辑错误和安全风险
9. **工具进化实验:** 让 Agent 在长期运行中自主淘汰低效工具、生成更好工具

---

## 5. 技术选型矩阵

| 需求 | 推荐方案 | 参考系统 |
|------|---------|---------|
| 简单工具缓存 | LATM 式 make-once-use-many | LATM |
| 跨域工具管理 | 图结构工具库 | GATE |
| 高频工作流优化 | SFT+RL 训练权重模块 | Constant-Context |
| 生产部署 | 版本化+审计+回退 | Amazon Tool-Making |
| 安全敏感场景 | 人工审核+沙箱执行 | Hubble |
| 终身学习 Agent | 技能库+自动课程 | Voyager |

---

## 6. 参考文献

1. Cai et al. "Large Language Models as Tool Makers" arXiv:2305.17126, 2023
2. Qian et al. "CREATOR: Tool Creation for Disentangling Abstract and Concrete Reasoning" arXiv:2305.14318, EMNLP 2023
3. Wang et al. "Voyager: An Open-Ended Embodied Agent with Large Language Models" arXiv:2305.16291, 2023
4. Yuan et al. "CRAFT: Customizing LLMs by Creating and Retrieving from Specialized Toolsets" arXiv:2309.17413, 2023
5. Ma et al. "Eureka: Human-Level Reward Design via Coding Large Language Models" arXiv:2310.12931, ICLR 2024
6. Luo et al. "GATE: Graph-based Adaptive Tool Evolution Across Diverse Tasks" arXiv:2502.13795, 2025
7. Kujanpää et al. "Tool-Making and Self-Evolving LLM Agents in Low-Latency Systems" arXiv:2607.08010, 2026
8. Xie et al. "From History to State: Constant-Context Skill Learning for LLM Agents" arXiv:2605.05413, 2026
9. Shi et al. "Hubble: An LLM-Driven Agentic Framework for Safe Alpha Factor Discovery" arXiv:2603.xxxxx, 2026

---

_Last updated: 2026-07-22_
