# Agent Skill 的回归税：当技能让 Agent 变得更差

**日期:** 2026-07-27
**主题:** LLM Agent 技能获取与自进化的暗面
**触发论文:** arXiv:2607.22520 (The Regression Tax) + arXiv:2607.22529 (Skill Self-Play)

---

## 核心概念

### 1. Agent Skill（智能体技能）
一段可复用的过程性指导：包含简短描述、自然语言指令体、有时附带代码。加载到 Agent 上下文中以控制其执行任务的方式。类似人类工作中的 SOP（标准操作流程）。

### 2. Regression Tax（回归税）
技能库导致 Agent 在原本能完成的任务上失败的现象。论文对 5832 次运行的分析显示：324 次 regression 抵消了 553 次 gross gain 的 59%。最好的技能库不是增益最大的，而是回归最少的。

### 3. Skill Self-Play（技能自博弈）
Qwen 团队提出的共进化框架：proposer 生成任务 → solver 解决任务 → skill controller 收集反馈更新技能库。用 RL 循环驱动技能库自主进化，解决"任务多样性 vs 验证可靠性"困境。

### 4. 三阶段模型（Grounding-Method-Verification）
论文提出 Agent 任务的三个阶段：
- **Grounding（接地）**: 正确读取和理解输入
- **Method（方法）**: 执行过程/程序
- **Verification（验证）**: 检查输出是否正确

关键发现：现有技能过度关注 Method 阶段，但 Regression 和残留失败主要发生在 Grounding 和 Verification 阶段。

### 5. 技能技能描述渗透（Skill Description Osmosis）
技能描述仅通过存在于系统提示中就改变 Agent 行为，即使从未被调用。这是上下文污染的一种隐蔽形式。

---

## 关键洞察

### 洞察 1: 平均改进是最危险的指标
传统评估只看平均成功率提升。但这隐藏了技能的两面性：它同时创造 gain（增益）和 regression（回归）。两个技能库可以有相同的平均增益，但在"破坏了多少已有能力"上天差地别。

**数据：** 324 次 regression 抵消了 553 次 gross gain 的 59%。最好的技能库优势来自"回归更少"而非"增益更多"。

### 洞察 2: 技能描述本身就是一种污染
即使技能从未被调用，仅其描述出现在系统提示中就会改变 Agent 行为。这被称为"技能描述渗透"（Skill Description Osmosis）。这类似于人类的锚定效应——仅仅是看到某个 SOP 的存在，就会改变你处理无关任务的方式。

**机制：** LLM 的注意力机制会在整个上下文中分散，技能描述中的词汇和模式会影响模型对后续输入的解读。

### 洞察 3: 过程指导被过度投资，接地和验证被忽视
当前技能生态系统的系统性偏差：大量技能教导 Agent"怎么做"（Method），但很少有技能帮助 Agent"看清楚输入"（Grounding）或"检查输出"（Verification）。然而数据显示，Grounding 和 Verification 才是失败的主要来源。

### 洞察 4: 技能自博弈（Skill-SP）指向了自主进化的方向
Qwen 的 Skill-SP 框架展示了一种可能的未来：Agent 系统不再依赖人类编写技能，而是通过 proposer-solver-controller 三方博弈自主生成、验证、进化技能库。关键创新在于用"技能"作为验证可靠性和任务多样性的中间地带。

### 洞察 5: 评估基础设施比技能本身更重要
Regression Tax 论文发现，226 个任务-条件的原评分有误（grader 的引擎无法处理 Excel 结构化引用公式）。这意味着：如果我们连正确评估 Agent 输出都做不到，讨论技能改进就更加可疑。验证基础设施是技能系统的瓶颈。

---

## 论文清单

| # | 系统/论文 | 机构 | 年份 | 核心贡献 |
|---|---------|------|------|---------|
| 1 | **The Regression Tax** (2607.22520) | Tank & Nama | 2026.07 | 分解技能的 gain/regression，识别三种回归机制 |
| 2 | **Skill Self-Play** (2607.22529) | Qwen/阿里 | 2026.07 | 共进化框架，proposer-solver-controller 自主技能进化 |
| 3 | **Trace2Skill** (Ni et al.) | - | 2026 | 从执行轨迹中提取可迁移技能 |
| 4 | **EvoSkill** (Alzubi et al.) | - | 2026 | 多 Agent 系统的技能发现 |
| 5 | **SkillOpt/SkillOS** (Yang et al.) | - | 2026 | 技能库优化和维护 |
| 6 | **ASSAY** (Wang et al.) | - | 2026 | 随机掩码估计单个技能效果 |
| 7 | **GRASP** (Moll et al.) | - | 2026 | 回归预算准入机制 |
| 8 | **RSEA** (Nguyen et al.) | - | 2026 | 进化上下文层 + 留出集检查 |
| 9 | **SEAGym** (Zheng et al.) | - | 2026 | 评估自进化迁移失败 |
| 10 | **SkillGraph** (Li et al.) | - | 2026 | 技能依赖图减少冗余检索 |
| 11 | **CausalForge** (2607.22511) | Tan et al. | 2026.07 | 自改进 Agent + Lean 证明助手（因果推理领域） |
| 12 | **Voyager** (Wang et al.) | NVIDIA | 2023 | Minecraft 技能库，Agent 技能学习的开山之作 |

---

## 可落地 Next Actions

### 短期（1-2周）
1. **审计现有技能库**：用 gain/regression 分解法重新评估 OpenClaw 的 skill 生态系统。不只看平均改进，要看每个技能引入后是否有任务退化。
2. **实现 Osmosis 检测**：对每个技能做 A/B 测试——仅在系统提示中包含技能描述但不触发它，测量对无关任务的影响。

### 中期（1-2月）
3. **增加 Grounding 和 Verification 技能**：不再只写"怎么做"的 SOP，而是写"怎么确认你读对了输入"和"怎么验证你的输出"的技能。
4. **建立 Regression Budget**：参考 GRASP，每个新技能准入时设置回归预算，超过阈值就拒绝或需要人工审核。

### 长期（3-6月）
5. **探索 Skill-SP 式自进化**：在受限领域（如代码生成、数据分析）实现 proposer-solver-controller 循环，让 Agent 自主进化技能库。
6. **技能依赖图**：参考 SkillGraph，构建技能间依赖关系图，避免冗余和冲突。

---

## 思考碎片

- Regression Tax 的发现类似于软件工程中的"技术债"概念：每个技能就像一个 abstraction layer，降低了某些任务的认知负担，但增加了系统整体的复杂性。当复杂性超过某个阈值，新加的抽象层反而会让系统更难维护。
- "技能描述渗透"与心理学中的"锚定效应"高度类比。LLM 的注意力机制在这方面的行为越来越像人类认知偏差。
- 三阶段模型（Grounding-Method-Verification）可以直接映射到软件工程的"输入验证-业务逻辑-输出测试"三段式。技能目前过度投资在业务逻辑层。
- Skill-SP 的 proposer-solver-controller 三方博弈结构，与 GAN 的 generator-discriminator 有结构上的相似性，但引入了"技能库"作为第三个实体，使验证和探索可以同时进行。
