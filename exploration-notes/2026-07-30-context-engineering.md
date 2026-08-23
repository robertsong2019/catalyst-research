# Context Engineering：从提示工程到上下文工程的范式迁移

**日期：** 2026-07-30
**主题：** Context Engineering — 系统性管理 LLM 上下文的工程实践
**研究者：** Catalyst

---

## 研究范围

系统性调研了 2025-2026 年间关于 Context Engineering 的核心文献，覆盖：
- Anthropic 工程团队（Effective Context Engineering for AI Agents）
- Google DeepMind / Philipp Schmid（The New Skill in AI is Not Prompting）
- LangChain（The Rise of Context Engineering）
- Redis 工程团队（Best Practices for an Emerging Discipline）
- Drew Breunig（How Contexts Fail and How to Fix Them）
- Chroma Research（Context Rot: Increasing Input Tokens vs Performance）
- 学术综述：A Survey of Context Engineering for LLMs (arXiv:2507.13334)
- Awesome Context Engineering GitHub 仓库（Meirtz，含数百篇论文索引）
- Tobi Lütke（Shopify CEO）和 Andrej Karpathy 的原始定义

---

## 核心概念（5个）

### 1. Context ≠ Prompt（上下文不等于提示词）

Context Engineering 将"上下文"重新定义为：在推理时传给 LLM 的**全部 token 集合**，包括：
- 系统指令（System Prompt）
- 用户输入
- 对话历史（短期记忆）
- 长期记忆（用户偏好、过去交互摘要）
- 检索到的外部信息（RAG）
- 可用工具定义（Function Calling / MCP）
- 输出格式约束

Prompt Engineering 是 Context Engineering 的子集。前者关注"怎么写提示词"，后者关注"如何系统性地组装正确的信息"。

### 2. Context Rot（上下文腐烂）

Chroma Research 的实证研究（覆盖 18 个 LLM）发现：随着输入 token 数量增加，模型的准确检索能力**持续下降**，即使在简单任务上也是如此。

关键发现：
- NIAH（大海捞针）基准过于乐观，因为它只测试词法匹配
- 语义匹配任务（NoLiMa）的性能下降更严重
- 不同模型的衰减曲线不同，但**所有模型都存在衰减**
- Gemini 2.5 技术报告确认：context 超过 100k token 后，agent 开始重复历史行为而非生成新策略

这意味着：上下文窗口不是"越大越好"，而是"越大越需要精心策划"。

### 3. 四种上下文失败模式（Drew Breunig 分类法）

- **Context Poisoning（中毒）**：幻觉进入上下文后被反复引用。一旦"目标"被污染，agent 会追求不存在的目标。
- **Context Distraction（分心）**：上下文过长，模型过度关注上下文而忽略训练知识。Llama 3.1 405b 在 32k token 后开始下降。
- **Context Confusion（混淆）**：不相关内容（如多余的工具定义）影响输出质量。Berkeley 研究表明：给模型越多工具，准确率越低。
- **Context Clash（冲突）**：上下文内部自相矛盾。新信息与旧信息冲突时，模型行为不可预测。

### 4. Just-In-Time Context（即时上下文）

Anthropic 提出的关键策略：不要预加载所有信息，而是让 agent 在运行时按需检索。

核心思路：
- 维护轻量级引用（文件路径、URL、查询语句）而非全部数据
- Agent 通过工具（grep, find, head/tail）按需加载数据
- 文件名、目录结构、时间戳等元数据本身就携带语义信号
- 模仿人类认知：我们不记忆整个知识库，而是建立索引系统

Claude Code 就是这个策略的实践：CLAUDE.md 预加载核心指令，其余通过 glob/grep 按需获取。

### 5. The Right Altitude（正确的高度）

Anthropic 提出的系统提示词设计原则：在"过于具体（脆弱的 if-else）"和"过于模糊（缺乏指导）"之间找到最佳平衡点。

两个极端：
- 太具体：硬编码复杂逻辑 → 脆弱、维护成本高
- 太模糊：高层抽象 → 模型无法理解期望行为

正确做法：足够具体以引导行为，足够灵活以提供启发式规则。Few-shot 示例是"值千言的图片"。

---

## 关键洞察（5条）

### 洞察 1：大多数 Agent 失败不是模型失败，而是上下文失败

 Philipp Schmid (Google DeepMind) 的判断：「Most agent failures are not model failures anymore, they are context failures.」

这意味着：与其等待更好的模型，不如改善你给模型的上下文。这是工程师可以控制的变量。

### 洞察 2：上下文是有限资源，有递减的边际收益

Transformer 的注意力机制是 O(n²) 的——每增加一个 token，都消耗其他所有 token 的注意力预算。Context Rot 研究证明：即使在简单任务上，更多 token 也不等于更好结果。

实践含义：上下文不是"能放就放"，而是"必须修剪"。每个 token 都有成本。

### 洞察 3：工具是上下文的一部分

Berkeley Function-Calling Leaderboard 显示：每多给一个工具，模型的准确率就下降。不相关的工具定义会"稀释"模型的注意力。

这意味着工具设计需要像 API 设计一样严谨：最小化工具数量、最大化工具描述质量、移除功能重叠的工具。

### 洞察 4：Hybrid 策略是实践最优解

纯预加载（传统 RAG）速度快但缺乏灵活性；纯即时检索（agentic search）灵活但慢。

最佳实践是混合策略：
- 预加载：核心指令、关键配置、项目上下文（如 CLAUDE.md）
- 即时检索：具体数据、大文件、实时信息

### 洞察 5：Context Engineering 正在从"技巧"变成"工程学科"

2025-2026 年的发展轨迹：
- Tobi Lütke 和 Karpathy 赋予了名字
- Anthropic 给出了系统框架
- 学术界开始正式综述（arXiv:2507.13334）
- 工具链开始成熟（LangSmith tracing, MCP, 12-Factor Agents）

这个领域正在经历从"vibes-based prompting"到"measurable context engineering"的范式迁移。

---

## 可落地的 Next Actions

1. **审计你的 Agent 上下文**：把每次 LLM 调用的完整输入记录下来，检查是否有上述四种失败模式
2. **实施上下文预算**：为每个上下文组件分配 token 预算（系统指令 X%, 历史 Y%, 工具 Z%），超出则触发压缩
3. **采用即时检索**：把大块预加载数据替换为引用（文件路径、URL），让 agent 按需加载
4. **修剪工具集**：如果一个 agent 有超过 10 个工具，审视是否能合并或分层加载
5. **建立评估闭环**：用 LangSmith 或类似工具追踪每次 LLM 调用的完整上下文，找到"什么信息在什么时候帮助了模型"
6. **阅读 Anthropic 原文**：https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

---

## 参考来源

1. Anthropic, "Effective Context Engineering for AI Agents", 2025-09-29
2. Philipp Schmid (Google DeepMind), "The New Skill in AI is Not Prompting, It's Context Engineering", 2025
3. LangChain, "The Rise of Context Engineering", 2025
4. Redis, "Context Engineering: Best Practices for an Emerging Discipline", 2025-09-26
5. Drew Breunig, "How Long Contexts Fail and How to Fix Them", 2025-06-22
6. Chroma Research, "Context Rot: How Increasing Input Tokens Impacts LLM Performance", 2025
7. Mei et al., "A Survey of Context Engineering for Large Language Models", arXiv:2507.13334, 2025-07-17
8. Tobi Lütke (Shopify), X/Twitter post on context engineering, 2025-06
9. Andrej Karpathy, X/Twitter post on context engineering, 2025-06
10. Berkeley Function-Calling Leaderboard, gorilla.cs.berkeley.edu
11. Gemini 2.5 Technical Report, Google DeepMind
12. humanlayer/12-factor-agents, GitHub
