# Research #079 — Context Engineering：读取侧的学科化

**Date:** 2026-08-20 (deep-exploration-evening)
**Status:** ✅ 调研完成，14+ 来源，博客已发布
**Chain:** AMG 写入治理（#2026-05 write-time governance）/ 记忆巩固（08-16）→ 本文补齐**读取/装配侧**：写什么决定了记忆库质量，装什么决定了单次推理质量

---

## 0. 为什么选这个题

AMG 前期研究全部聚焦**写入侧**（governance gate、遗忘工程、熵过滤）。但 agent 的每次推理都有一个独立的预算问题：系统提示 + 工具定义 + 检索结果 + 对话历史 + 记忆注入，全部挤同一个有限窗口。2025-2026 年这个领域快速学科化（Anthropic 官方定调、Stanford ACE、ICML 2026 Context Folding），值得系统梳理并和 AMG 的写侧工作对齐。

## 1. 核心概念

### 1.1 Context Rot / 注意力预算 / MECW
- Chroma 2025/2026 报告测了 18 个前沿模型：输入变长，**受控任务**上准确率也非均匀下降——不是"找不到"，是"注意力被稀释"。
- 机制根源：transformer 全注意力是 n² 两两关系，长序列下被摊薄；训练分布里短序列远多于长序列；位置插值外推有精度代价。**rot 是架构性的，窗口变大只是延长跑道**。
- MECW（Maximum Effective Context Window）：广告窗口 ≠ 可用窗口。行业经验值：多数模型高质量区间 **< 256k**，标称 200k 的模型 ~130k 开始退化；生产 agent 实际可用容量约为标称的 60-70%。
- Liu et al. "Lost in the Middle"（TACL 2024）：同样的信息放在窗口中间，召回显著差于首尾。

### 1.2 Context Engineering 的定义与四大杠杆
- Anthropic 定调：prompt engineering 的自然演进——"在推理时策展并维护最优 token 集合"的一组策略。Karpathy：为 LLM 填充正确信息的艺术与科学。
- Philschmid 框架四杠杆：**Offloading**（外置到文件/系统）、**Reduction**（压缩历史）、**Retrieval**（just-in-time 动态取）、**Isolation**（子代理隔离）。
- 关键心智模型：**上下文是边际收益递减的有限资源**。目标不是"多给"，而是"找到达成下一步所需的最小高效 token 集"（smallest set of high-signal tokens）。
- Sourcegraph 实测：同一个任务，100k 全量 codebase 摘要 **不如** 5k 定向检索——多≠好。

### 1.3 长任务三板斧 + 可逆性排序
Anthropic 三技术（均有产品化）：
1. **Compaction**（压缩重开窗口）：Claude Code 保留架构决策/未解 bug/实现细节，丢弃冗余工具输出。最轻的手法是 **tool result clearing**——深历史里的原始工具结果可清（调过即弃），保留调用记录结构。
2. **Structured note-taking**（结构化笔记/外部记忆）：agent 定期把笔记写到窗口外，稍后拉回。Claude playing Pokémon 跨数千步维护训练计数/地图/战术，上下文重置后读自己的笔记继续。
3. **Sub-agent architectures**（子代理隔离）：主代理只拿摘要，深搜索上下文隔离在子代理内。
- Manus/Philschmid 的**可逆性排序**（最有价值的单一启发）：**raw > compaction（可逆）> summarization（有损）**。agent 写了 500 行代码，历史里只需留文件路径——要用时工具重读（可逆）；实在不够再上有损摘要。摘要时保留最近 3 轮原始 tool call 以维持"节奏感"。
- 混合检索：Claude Code 的 CLAUDE.md 前置注入 + glob/grep just-in-time 探索。渐进披露：文件名/目录/时间戳本身就是信号。

### 1.4 Context 是新的权重：ACE 的演进式 playbook
- Stanford/SambaNova/Berkeley ACE（2025.10）：上下文不当静态 prompt 而当**活的 playbook**——Generator 干活 → Reflector 提炼经验 → Curator 以**增量 delta** 合并（去重、剪枝、分类），永不整篇重写。
- 对抗两个病态：**brevity bias**（重写越写越短丢细节）和 **context collapse**（反复重写磨掉关键信息，66.7%→57.1%）。传统整篇重写必塌，delta 增量不塌。
- 数字：AppWorld +10.6%，金融推理 +8.6%；DeepSeek-V3.1+ACE 59.4% ≈ GPT-4.1 系统 60.3%；适配延迟降 82-92%、token 成本降 75-84%。
- playbook 条目带 usage 计数：`{content, helpful: 14, harmful: 1, last_updated}`。
- 定位：**免训练的自改进**——API 模型时代比 fine-tune 现实得多；与 GEPA（prompt 进化）、Dynamic Cheatsheet 同赛道但增量化。

### 1.5 学习型上下文管理：Context Folding / FoldGRPO（ICML 2026）
- 现有 compaction/多代理/摘要都是**手工流水线**；Context Folding 让 agent **学会**管理自己的工作上下文：程序化 branch 出子轨迹处理子任务，完成后 **fold**——中间步骤坍缩，只保留结果摘要。
- FoldGRPO 用过程奖励（奖励有效分解 + 有效摘要）端到端 RL 训练。长程研究/软件任务上匹敌或超过强基线，活动上下文小得多。
- 与 08-16 记忆巩固研究同构：睡眠期巩固是"离线压缩"，folding 是"在线压缩"，方向一致——**压缩是有损但必要的第一公民操作**。

### 1.6 KV-cache 经济学：上下文布局就是账单
- prefix caching（vLLM）/ RadixAttention（SGLang，radix 树共享任意公共前缀）：60%+ 前缀重叠的工作负载命中 75-95%，TTFT 从秒级到 <200ms；**0% vs 90% 命中率 = 同负载 $20k/月 vs $2k/月 GPU 账单**。
- KVFlow（arXiv:2507.07400）：LRU 驱逐不适合 agent 工作流，按执行顺序感知驱逐 + 预取，比 SGLang 层级 radix cache 快 1.83-2.19×。
- 设计推论：**上下文顺序影响成本**——稳定前缀（系统提示/工具定义）在前、易变内容在后；用 RAG 动态注入工具定义会打破缓存还造成"幻觉工具"（第 1 轮有第 2 轮消失）。Manus：多代理 "share memory by communicating, not communicate by sharing memory"；分叉上下文是昂贵依赖。

## 2. 关键洞察

1. **更大的窗口救不了你。** rot 是架构性 n² 稀释 + 训练分布偏短所致；百万窗口只是更长跑道。工程含义：预算思维（token 是有限资源）替代容量思维（塞得下就行）。
2. **可逆性是最强的压缩排序键。** raw > 可逆 compaction（留指针留结构）> 有损 summarization。首选"指针而非载荷"（文件路径代替文件内容），需要时重取。tool result clearing 是零风险第一步。
3. **上下文空间可以做自改进（ACE），且必须增量。** 整篇重写必塌（context collapse）；delta + usage 计数 + curator 去重是可持续的。这为 API-only 团队提供了 fine-tune 之外的进化通道。
4. **上下文布局是成本变量，不只是质量变量。** 缓存友好性（稳定前缀、少分叉、工具定义静态化）直接乘以 GPU 账单系数；"最小高效上下文"同时优化质量与单位经济。
5. **手工流水线 → 学习型管理是明确趋势。** compaction/note-taking/sub-agent 是今天的手工答案，FoldGRPO 表明 RL 可以学会"何时折叠、如何摘要"。与记忆写入侧的熵过滤、睡眠期巩固汇合成同一条主线：**信息生命周期管理**。

## 3. 与 AMG 的对齐

- 写侧（已有）：governance gate、read-before-write、熵过滤写入、遗忘工程。
- 读侧（本文）：装配预算（pre-rot 阈值监控）、注入顺序（稳定前缀缓存友好）、注入形态（指针 vs 载荷）。
- AMG 的 memory 注入目前按相关性排序注入——缺一个**总量预算器**和**布局策略**。ACE 的 playbook 模式 ≈ AGENTS.md/TOOLS.md 的错误升级协议（出现次数→规则升级）已经是 proto-playbook，缺 usage 计数与 curator 去重。

## 4. Next Actions

1. [ ] AMG 读路径加 **pre-rot 阈值监控**：装配前统计注入 token 总量，超阈值告警/触发裁剪（本周可做，纯日志级别改动）。
2. [ ] 装配顺序实验：系统提示/工具定义前置固定，记忆注入按"稳定→易变"排序，验证缓存命中率变化。
3. [ ] 长 agent loop 里试点 tool result clearing（调过即弃，保留调用记录）。
4. [ ] 把 TOOLS.md 错误升级协议升级为 ACE 式条目结构（+helpful/harmful 计数 + last_updated），观察规则腐化速度是否下降。
5. [ ] 精读 FoldGRPO 论文全文，评估其对 AMG 读路径的可借鉴性（过程奖励设计）。
6. [ ] 博客已发布：context-engineering-token-budget-2026-08.html。

## 5. 来源（14）

1. Chroma, *Context Rot* research report, 2025/2026 — research.trychroma.com/context-rot
2. Liu et al., *Lost in the Middle*, TACL 2024
3. Anthropic, *Effective context engineering for AI agents*, 2025-09
4. Karpathy, context engineering 定义推文, 2025-06
5. Zhang et al., *Agentic Context Engineering (ACE)*, Stanford/SambaNova/Berkeley, 2025-10
6. *Scaling Long-Horizon Agent via Context Folding* (FoldGRPO), ICML 2026 poster
7. Philschmid, *Context Engineering for AI Agents Part 2*, 2025（Manus/Peak Ji webinar 提炼）
8. Manus, *Context Engineering for AI Agents: Lessons from Building Manus*
9. SGLang/RadixAttention, LMSYS 2024 + arXiv:2312.07104
10. KVFlow, arXiv:2507.07400
11. Sourcegraph, *Context Engineering: A Practical Guide*, 2026
12. Atlan, MECW / context engineering guide, 2026
13. TrueFoundry, gateway-level compaction & prefix caching, 2026
14. Mei et al., *A Survey of Context Engineering for LLMs*, arXiv 2025
