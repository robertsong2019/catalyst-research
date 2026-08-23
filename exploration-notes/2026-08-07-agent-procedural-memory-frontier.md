# Agent 程序性记忆：从经验中生长的智能

**日期：** 2026-08-07
**主题：** AI Agent 程序性记忆（Procedural Memory）—— 从经验蒸馏到技能进化
**调研范围：** 15+ 篇论文/系统，覆盖 2023-2026 年主要工作

---

## 核心概念（5个）

### 1. 程序性记忆（Procedural Memory）vs 陈述性记忆（Declarative Memory）
- **陈述性记忆**：存储"是什么"——事实、事件、用户偏好（语义记忆 + 情景记忆）
- **程序性记忆**：存储"怎么做"——工作流、操作模式、技能、策略
- 认知科学基础：Squire 的 declarative/procedural 二分法，Tulving 的 episodic/semantic 区分
- Agent 语境下：CLAUDE.md / AGENTS.md / SKILL.md 都是人类手工编写的程序性记忆

### 2. 技能层次金字塔（Experience → Strategy → Skill）
来自 2025-2026 多篇论文的共识：
- **原始经验层（Experience Memory）**：成功/失败的完整轨迹，包含 reward、feedback
- **策略/洞察层（Insight/Strategy Memory）**：从多次经验中蒸馏出的通用模式
- **技能层（Skill Memory）**：可执行、可组合的能力单元——代码片段、工作流定义

### 3. 记忆效用值（Utility-based Retrieval）vs 语义相似度（Semantic Similarity）
- 传统 RAG/Memory：基于 embedding 相似度检索 → "看起来像"
- MemRL 范式：通过 RL 学习每条记忆的 Q-value（效用值）→ "真的有用"
- 两阶段检索：先语义过滤候选集，再效用值排序选最优

### 4. 技能进化闭环（Skill Evolution Loop）
- Build → Retrieve → Update 三阶段
- 进化机制：成功强化、失败修正、跨任务/跨角色/跨模型迁移
- 关键挑战：技能过专业化（over-specialization）—— AWM 发现技能在跨角色时效果下降

### 5. 非参数学习（Non-parametric Learning）
- 不修改 LLM 权重，通过外部记忆系统实现"学习"
- 将 LLM 的稳定推理能力与记忆的可塑性解耦
- 类比人脑：新皮层（stable reasoning）+ 海马体（plastic memory）

---

## 关键论文/系统（15篇）

| # | 系统/论文 | 年份 | 核心贡献 |
|---|---------|------|---------|
| 1 | **Voyager** (Wang et al.) | NeurIPS 2023 | 首个代码技能库，Minecraft 终身学习 |
| 2 | **Reflexion** (Shinn et al.) | NeurIPS 2023 | 语言反馈作为"强化学习"，episodic memory buffer |
| 3 | **ExpeL** (Zhao et al.) | AAAI 2024 | 经验池 + 洞察提取，ADD/UPVOTE/DOWNVOTE/EDIT 操作 |
| 4 | **Agent Workflow Memory (AWM)** (Wang et al.) | ICML 2025 | 工作流归纳，离线/在线双模式，web navigation |
| 5 | **Mem^p** (Fang et al.) | 2025 | 系统研究程序性记忆的 build/retrieve/update 策略 |
| 6 | **Mem0** (Chhikara et al.) | ECAI 2025 | 生产级长期记忆，episodic+semantic+procedural 三层 |
| 7 | **MemRL** (Zhang et al.) | Jan 2026 | 非参数 RL，Q-value 记忆效用，frozen LLM + evolving memory |
| 8 | **MemEvolve** | Dec 2025 | 元学习进化整个记忆管理策略 |
| 9 | **SkillRL** | 2026 | 递归技能增强 RL，SkillBank 层级技能库 |
| 10 | **AFTER Benchmark** | 2026 | 382 task 评估程序性技能跨任务/角色/模型迁移 |
| 11 | **SkillMentor** | 2026 | 通过盲点诊断自进化，学习识别反复失败的模式 |
| 12 | **Memento-Skills** | 2026 | 持续技能写作 + 行为对齐路由 |
| 13 | **EvoSkill** | 2026 | 从失败和验证反馈中精炼技能 |
| 14 | **Salesforce PMD** | 2026 | 程序性记忆蒸馏，三层结构（experience→insight→behavior） |
| 15 | **Agent Skills Workshop** (CAIS 2026) | 2026 | 第一届 Agent Skills 学术 workshop，标志领域成型 |

---

## 关键洞察（5条）

### 洞察 1：程序性记忆是 Agent 领域 2026 年的最高杠杆创新点
 episodic/semantic memory 的工具化已经相对成熟（Mem0、Letta、Zep），但 procedural memory 的工具化被 Mem0 2026 报告明确标注为"still early-stage"。这意味着：
- 谁先做好程序性记忆，谁就获得差异化优势
- 目前最好的实践是手工编写（CLAUDE.md / AGENTS.md / SKILL.md），自动化空间巨大
- 自动化的核心挑战不是存储，而是"提取什么"和"何时更新"

### 洞察 2：效用值检索（Utility-based Retrieval）是语义检索的下一代
 MemRL 的核心创新：不是"检索最相似的"，而是"检索过去证明最有用的"。在 ALFWorld 探索任务上，MemRL 比 Mem^p 提升 56%，比无记忆 baseline 提升 82%。这颠覆了 RAG 的基本假设——相似性≠有用性。

### 洞察 3：技能迁移存在"过专业化陷阱"
 AFTER benchmark 发现：程序性技能在跨任务时迁移良好（+2.8pp），跨模型时如果用多模型轨迹训练可达 73.1% 准确率，但跨角色时效果显著下降。这说明技能不是通用的——它们嵌入了对特定工作流上下文的依赖。

### 洞察 4：进化闭环比初始构建更重要
 EvoSkill、SkillMentor、Memento-Skills 都聚焦于"如何更新"而非"如何创建"。证据表明，单轮技能进化就能带来 +5.2pp 的额外提升。但失败模式的识别和修正仍然是开放问题——技能可能因为环境变化而过时，但系统很少意识到需要更新。

### 洞察 5：非参数学习正在形成完整的学术议程
 ICLR 2026 有两个专门 workshop（Lifelong Agents + AI with Recursive Self-Improvement），ICML 2025 有 AWM，NeurIPS 2023 有 Voyager/Reflexion。从 demo 到研究议程只用了 3 年。但关键分歧未解：外部记忆算不算"真正的学习"？SKILL0/SDAR 主张真正的学习应该是参数化的——技能应该 internalize 到模型权重中。

---

## 可落地的 Next Actions

1. **为 agent-memory-graph 添加 procedural memory 层**
   - 当前系统有 episodic + semantic memory，缺少 procedural 层
   - 最小实现：记录每次任务执行的成功轨迹 → 蒸馏为 SKILL 格式 → 语义+效用双重检索

2. **引入效用值追踪机制**
   - 为每条记忆添加 utility_score 字段
   - 任务成功后更新相关记忆的 utility（类似 MemRL 的 Q-value update）
   - 检索时：`WHERE semantic_similarity > threshold ORDER BY utility_score DESC`

3. **构建技能进化闭环**
   - 失败检测：当任务执行失败时，自动分析失败原因
   - 技能修正：用 EvoSkill 的 generate-verify-refine 模式更新技能
   - 过时检测：定期检查技能是否仍然有效（API 变更、环境变化）

4. **实验跨模型技能迁移**
   - 用多模型轨迹训练技能（AFTER 证明这显著提升迁移性）
   - 评估 OpenClaw 技能在不同模型间的迁移效果

5. **关注安全维度**
   - Agent Skills 安全已经开始被研究（BadSkill 后门攻击、SkillJect 闭环注入）
   - 程序性记忆的安全审计需要成为系统级要求

---

## 技术对比矩阵

| 系统 | 记忆形式 | 构建方式 | 检索方式 | 更新机制 | 迁移能力 |
|------|---------|---------|---------|---------|---------|
| Voyager | 代码片段 | 手动+验证 | 语义 top-k | 无更新 | 同环境迁移 |
| ExpeL | NL洞察+轨迹 | 自动蒸馏 | 语义相似度 | ADD/VOTE/EDIT | 跨任务迁移 |
| AWM | 工作流 | 自动归纳 | 语义匹配 | 在线/离线 | 同域迁移 |
| Mem^p | 细粒度指令 | 多策略 | 多策略 | add/modify/delete | 跨任务迁移 |
| MemRL | 情景+效用值 | 自动记录 | 两阶段(语义+效用) | RL Q-value更新 | 跨任务迁移 |
| SkillRL | 层级技能库 | RL蒸馏 | 自适应检索 | 协同进化 | 跨任务迁移 |
| AFTER | SKILL.md | 轨迹蒸馏 | 语义检索 | 进化精炼 | 跨任务/模型(非跨角色) |

---

## 总结

程序性记忆正在从"手工编写的配置文件"走向"自动进化的能力系统"。这个转变类似从"手工编写规则"到"机器学习"的跃迁——只不过这次发生在 Agent 层面，而不是模型层面。核心趋势清晰：从相似性到效用性、从静态到进化、从单模型到多模型、从手工到自动。MemRL 的非参数学习、AFTER 的迁移评估、SkillRL 的层级进化，构成了 2026 年程序性记忆研究的三角支柱。
