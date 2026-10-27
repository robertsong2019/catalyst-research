# 图谱记忆的 2026：长上下文幻觉、图结构的三种哲学与诚实的账单

**日期:** 2026-10-27（晚间深度探索）
**主题:** Knowledge-Graph Memory × Agent 长期记忆 × 长上下文之争
**触发问题:** 当上下文窗口涨到 400K-1M token，"把所有历史塞进 prompt"和"用知识图谱组织记忆"谁会赢？答案：都不赢——问题本身就问错了。

---

## 调研语料（16 篇论文/系统）

| # | 工作 | 出处 | 一句话 |
|---|------|------|--------|
| 1 | NoLiMa | ICML 2025, Adobe | 13 个自称 ≥128K 的模型，32K 时 10-11 个准确率跌破短文本基线的 50%；GPT-4o 99.3%→69.7%（去掉字面匹配线索后） |
| 2 | RULER | NVIDIA 2024 | "有效上下文长度"普遍小于标称；32K 处只有一半模型保持合格表现 |
| 3 | LaRA | arXiv 2025-03 | 128K 语料上 RAG 反超 long context，且 LC 幻觉更多 |
| 4 | U-NIAH | arXiv 2503.00353 | 统一评测：RAG 对长上下文 82.58% 胜率；检索 chunk 越多噪声与幻觉越多 |
| 5 | Self-Route | Google, EMNLP 2024 Ind. | 长上下文平均更好，但自适应路由省 39-65% 成本而精度不掉 |
| 6 | Lost in the Middle | Liu et al. 2023 | 注意力 U 型曲线的鼻祖 |
| 7 | HippoRAG | NeurIPS 2024, OSU | 海马体索引理论 + KG + Personalized PageRank；多跳 QA 最高 +20%，单步检索匹敌迭代检索但便宜 10-20×、快 6-13× |
| 8 | HippoRAG 2 | arXiv 2502.14802 "From RAG to Memory" | 双节点图（passage+phrase）、同义词边 τ=0.8、PPR+LLM triple 过滤；联想任务比 embedding 检索 +7 F1；已出 MCP server（Claude Code/Cursor 可直接挂） |
| 9 | A-Mem | NeurIPS 2025 | Zettelkasten 式 agentic memory：新记忆生成结构化笔记→分析历史记忆→建立链接→**触发旧记忆演化**；六数据集显著超越传统存储-检索式记忆 |
| 10 | Zep / Graphiti | getzep 2025 | bi-temporal KG，每条边四时间戳（valid_at/invalid_at/learned/invalidated）；episodic/semantic/community 三层子图；DMR 94.8% vs MemGPT 93.4%；LongMemEval +18.5% 精度、-90% 延迟 vs 全量上下文 |
| 11 | Mem0 | ECAI 2025, arXiv 2504.19413 | 抽取式 token 高效记忆 + 可选图变体 Mem0g；与 Zep 打基准战争（见下） |
| 12 | Microsoft GraphRAG | Edge et al. 2024 | Leiden 社区检测+层级摘要，local/global 搜索；索引 $20-500/语料（向量的 100-1000×），社区重算非增量 |
| 13 | LazyGraphRAG | Microsoft 2025-06 | 索引只做轻量建图（0.1% 全量成本=向量级），摘要推迟到查询时；BenchmarkQED 全类目胜出（含 1M token 向量 RAG），global 查询便宜 700× |
| 14 | GraphRAG-Bench | ICLR 2026 | "GraphRAG 在很多真实任务上经常输给 vanilla RAG"——图不是万能升级 |
| 15 | LightRAG / RAPTOR | 2024 | 双层检索 / 层级摘要树——图记忆的轻量替代路线 |
| 16 | Memory in the Age of AI Agents: A Survey | arXiv 2512.13564, 47 作者, 2026-01 修订 | 记忆三分法 forms(token/parametric/latent)×functions(factual/experiential/working)×dynamics；**五操作：存/取/更/压/忘** |

辅助：Novel Cognition 245k 文章实测（2026-05）：向量 vs GraphRAG 索引成本 $12 vs $430；单跳 P@5 0.94 vs 0.89（图反输）；多跳正确率 63% vs 91%（图大胜）；p50 延迟 73ms vs 1400ms。Hindsight（2026）多策略混合自称 LongMemEval 94.6%。Databricks：长上下文与 RAG 协同而非互斥。

---

## 核心概念（5 个）

1. **有效上下文长度（Effective Context Length）** — 标称窗口 ≠ 可用窗口。NoLiMa 的杀手锏是去掉字面词重叠后测联想检索：注意力机制在没有 literal anchor 的长文本里找信息的能力崩得比想象快。**容量不是记忆，检索才是。**

2. **Personalized PageRank = 激活扩散（HippoRAG 系）** — 图检索的神经科学隐喻：海马体不存内容只存索引，回忆=从线索节点沿突触扩散激活。PPR 把"多跳推理"变成"图上一次扩散"，这就是它比迭代检索便宜 10-20× 的原因。图算法（PageRank 家族）在 LLM 时代找到了新工作：当检索器。

3. **Bi-temporal 模型（Zep/Graphiti）** — 事实有四条时间线：何时为真、何时失效、系统何时学到、何时得知失效。**事实不是被删除而是被标记失效**——这让"用户上周换了工作"这类问题的答案从"哪个版本更相关"变成"哪个版本还有效"。时间是一等公民，不是元数据。

4. **记忆演化（A-Mem / Zettelkasten）** — 卢曼卡片盒：每张新卡片进来时，回头修订与它相关的旧卡片。Agent 自己当图书管理员：新经验不是追加进仓库，而是触发存量知识的重组。记忆的组织结构本身是 agent 的决策（agentic 的本义）。

5. **记忆五操作（Survey）** — 存、取、更、压、忘。绝大多数团队只建了前两个；append-only 是默认架构因此"旧事实和新事实共存，agent 猜哪个是当前的"；遗忘是最被低估的操作——错误、过时、无关的条目安静积累，污染未来每次检索。

---

## 关键洞察（5 条）

1. **长上下文没有杀死记忆系统，反而证明了它的必要性。** 所有独立基准（NoLiMa/RULER/LaRA/U-NIAH）指向同一结论：塞进去 ≠ 找得到 ≠ 用得上。长上下文和检索/记忆是协同关系（Databricks、Self-Route 都这么判）——长窗口让每次能装进来的检索结果更多、更完整，但决定装什么的那一层永远需要结构。**上下文是工作台，记忆是图书馆；工作台再大也不能把图书馆搬上桌。**

2. **图的价值区非常明确且稳定：多跳、跨会话、时效推理、知识更新。** 在所有互相打架的厂商数字里，这四个单项的胜负方向完全一致（Novel Cognition：多跳 91% vs 63%；Zep 论文：temporal-reasoning 45.1%→62.4%）。相反，单跳事实查询上图经常输给向量（P@5 0.89 vs 0.94）还贵 35×。**总分吵架，单项共识——选型看类目分布，不看 leaderboard 总分。**

3. **基准战争是 2026 记忆赛道最大的方法论污染。** Mem0 与 Zep 各自发布的 LoCoMo/LongMemEval 数字差出 40+ 分（Mem0 称 93.4，第三方 Atlan 测得 49.0；Zep 被对手"修正"到 58.44 再反诉 75.14）。教训：**任何 memory 产品的选型必须自己拿同一套查询跑**，厂商数字只能用来判断"他们优化哪些类目"。这场战争本身也是信号：记忆层已成商业必争之地（市场规模 $6.27B→$28.45B 预测）。

4. **GraphRAG 的诚实账单：默认不划算，LazyGraphRAG 改变了成本结构。** 全量 GraphRAG 索引是向量的 100-1000×、社区摘要不可增量更新，ICLR 2026 基准直言它"经常输给 vanilla RAG"。LazyGraphRAG 把索引压到向量级（0.1%），摘要推迟到查询时，global 查询便宜 700×——这是把"一次性买断"改成"按需付费"的架构思想。图的正确打开方式不是"升级"，是**按查询类型路由**（单跳→向量；多跳→HippoRAG 2；全局综合→Lazy；动态数据→bi-temporal 图）。

5. **"记忆"正在从名词变成动词组。** 2024 的记忆系统=存储+检索；2025-2026 的分水岭是 update/compress/forget 成为研究主战场（Zep 的失效机制、A-Mem 的演化、survey 把五操作正式化、Memory-R1 把记忆操作变成 RL 动作——见 10-26 笔记）。与之相伴的暗面：**记忆投毒是新型攻击面**（90%+ 测试 agent 可被投毒、对话纠错 100% 复发）——记忆可写=agent 可被跨会话重编程。防御和攻击的战场正在从 prompt 移向 memory 文件/图数据库。

---

## Next Actions（可落地）

1. **amg 项目对齐**：给 agent-memory-graph 的边补 valid_at/invalid_at 两个时间戳列（bi-temporal 最小实现），读路径按"有效优先"仲裁——参照 Zep 论文 §4 的查询模板，预计 2-3 天。
2. **审计自己套件的五操作覆盖度**：写一个 checklist 脚本扫 projects/ 里所有带记忆的组件，标记 store/retrieve 有、update/compress/forget 无的债。
3. **复现 HippoRAG 2 的 MCP server 接入**（hipporag[mcp] 可直接给 Claude Code 挂），拿自己的博客仓当语料，实测多跳查询 vs 朴素向量检索的差异。
4. **选型自测集**：从 LongMemEval 抽 temporal-reasoning + knowledge-update 两类各 20 题做成 mini-bench，以后评估任何记忆方案先跑它，不看厂商总分。
5. **盯三个信号**：(a) Mem0/Zep 是否接受独立第三方复测；(b) LazyGraphRAG 何时开源/产品化；(c) 主流 agent 框架（LangGraph/CrewAI）把记忆层从可选变默认的时间点。

---

## 与近期探索的连线

- 10-26 Agentic RL：Memory-R1/EMPO² 把记忆操作变成可训练动作 → 图谱记忆提供的是这些动作的**操作对象**（结构化基底）。
- 10-25 世界模型：记忆=对自己人生学的世界模型 → bi-temporal 图就是这个 world model 的时间轴骨架。
- 10-27 上午 Skill 供应链：记忆投毒与 skill 投毒是同一攻击面的两个入口。
- 早前 amg kupdate 论文随笔（supersedence 签名）：本次 Zep 失效机制与 supersedence 判定互为印证——写时失效 vs 读时仲裁两条路线各自的成本。

## 主要链接

- HippoRAG 2: https://arxiv.org/abs/2502.14802
- A-Mem: https://arxiv.org/abs/2502.12110 (NeurIPS 2025)
- Zep paper: https://arxiv.org/abs/2501.13956 (getzep/graphiti)
- Mem0: https://arxiv.org/abs/2504.19413 (ECAI 2025)
- NoLiMa: https://arxiv.org/abs/2502.05167 (ICML 2025)
- LazyGraphRAG: https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- Memory Survey: https://arxiv.org/abs/2512.13564 (+ GitHub paper list 2k+ stars)
- U-NIAH: https://arxiv.org/abs/2503.00353
