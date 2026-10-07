# 2026-10-07 晚间深度探索：Agent 记忆巩固与睡眠时间计算（Dreaming / Sleep-time Compute）

**动机**：今晨 trending 报告 claude-mem（95.5k★）+ 2026 年 5-6 月 Anthropic/OpenAI 相继 shipped "Dreaming"，Agent 记忆从"检索问题"演进为"巩固问题"。避开近两周已写主题（diffusion LM/上下文工程/技能习得/TTT/自我进化/tilelang/ds4），本篇聚焦 **agent 不工作的时候发生了什么**。

## 时间线：一个隐喻如何五周内变成产品

- **2025 初**：Letta（前 MemGPT 团队）× UC Berkeley 发表 *Sleep-time Compute: Beyond Inference Scaling at Test-time*（Lin, Snell et al.）——模型在空闲期离线"预想"用户可能问什么、预计算有用中间量。同精度下测试时算力省 ~5×（Stateful GSM-Symbolic / AIME）；放大睡眠算力可精度 +最多 ~20% 同时再省 4.5×。随 Letta 0.7.0 发布 sleep agents。
- **2026-03**：Claude Code 源码泄漏中已见 `autoDream` 字样（未官宣的功能先被考古）。
- **2026-03**：综述 arXiv:2603.07670《Memory for Autonomous LLM Agents》确立四层分类法（working/episodic/semantic/procedural）+ 空闲期离线巩固（"important traces strengthened, rest pruned"）+ 双缓冲试用期模型（新记忆先进 probation buffer，质检合格才毕业进长期库）。
- **2026-05-06**：Anthropic 在 Code with Claude 大会发布 **Dreaming**（Managed Agents，research preview）：输入 1 个记忆库 + 至多 100 份历史会话转录 → 异步作业产出全新整理后的记忆库。四步流水线：读全部会话 →（相对时间绝对化"昨天"→"2026-03-15"）/ 删除被推翻的矛盾事实 / 修剪过期条目 / 合并重复 → 修剪并重建索引。官方类比明确指向海马体睡眠巩固。Opus 4.7 / Sonnet 4.6，按标准 API token 计费。**Harvey（法律 AI）报告任务完成率 ~6×**。官方文案："Dreaming 能浮现单个 agent 自己看不见的模式——反复犯的错、多个 agent 收敛出的工作流、团队共享的偏好。"
- **2026-05-25**：Claude Code 落地 **Auto Dream**：累计 ≥5 个会话或距上次巩固 ≥24h 触发，也可手动。
- **2026-06-04**：OpenAI 发布 **Dreaming: Better memory for a more helpful ChatGPT**：后台跨会话合成记忆，取代"手动保存的记忆列表"成为基础；目标 freshness/continuity/relevance；厂商自评 factual recall 41.5%→82.8%、计算效率 ~5×（贵的工作在后台做一次而不是每次查询重做）。附记忆摘要页 + 修正入口 + Temporary Chat。
- **同期学术**：CMU + UMD《Do Language Models Need Sleep? Offline Recurrence for Improved Online Inference》（arXiv:2605.26099）——"五月学术问出问题、产品先答完卷"的编辑巧合。
- **2026-06+**：小米 MiMo：Dream 每 7 天自动触发（读历史会话+现有记忆，合并/去重/验证路径/压缩/更新全局记忆）+ **Distill** 从会话中挖可复用工作流固化为自动化。社区跟进：OpenDreams（跨会话做梦→写 AGENTS.md）、anima（本地 2B 常驻 agent，睡眠巩固+梦）、nram（艾宾浩斯遗忘曲线+程序性/人格记忆分层）、OpenClaw Auto-Dream。

## 核心概念

1. **Sleep-time compute（第三条计算轴）**：训练时（学能力）、测试时（现场推理）、睡眠时（空闲期摊销）。本质是**摊销**：把"每次查询都要重做的贵工作"变成"后台做一次"。预习比喻：学生课前把课本啃一遍，上课就不用现场从零推导。
2. **记忆巩固（consolidation）**：episodic（带时间戳的流水账：用户 1 月 5 日纠正了日期格式）→ semantic（抽象事实：用户偏好 DD/MM/YYYY）→ procedural（可执行技能/工作流）。巩固 = 提炼 + 删除 + 钉时间。
3. **两种"睡眠"**： 产品级 = 重写笔记（记忆库是文本/结构化存储，dream 是一次异步重写作业）； 研究级 = 重塑大脑（CMU：睡眠期间对积累上下文做 N 次离线循环 pass，用学到的局部规则更新 SSM 模块的 **fast weights**，然后清空 KV cache——重活在睡眠期完成，唤醒时推理延迟不变）。CMU 前作 Behrouz 等《Language Models Need Sleep: Learning to Self Modify and Consolidate Memories》同路线。
4. **双时态知识图谱（bi-temporal KG）**：Zep/Graphiti（arXiv:2501.13956）给每条事实边挂 `valid_at`/`invalid_at` 窗口——矛盾事实**失效而非删除**，"上个季度我们信什么"成为一等公民查询。对巩固的启示：删除不是唯一选项，失效标记保留历史。
5. **评测门（evaluation gate）**：dream 写入记忆是系统里唯一"无人验收的写操作"。门的形态：dream 前后跑固定题集回归 + 指纹对比 + diff 人工审（先人工后自动）。SSGM（2026）把"记忆演化与验证解耦 + ground-truth 锚定"形式化为反语义漂移。

## 关键数字

- Sleep-time compute：同精度测试算力 ~5×↓；睡眠算力放大 → 精度至多 +20%
- Harvey（Anthropic Dreaming）：agent 任务完成率 ~6×
- OpenAI Dreaming：厂商自评 41.5%→82.8% factual recall；计算效率 ~5×（均为 vendor-stated）
- CMU fast-weights：GSM-Infinite，窗口远小于序列时 0.596→0.905（+52%）；Ouro 1.4B 六步题 +47% 相对提升；Jet-Nemotron 2B N=6 最难档 +11%
- **LongMemEval 同名基准的厂商/第三方鸿沟：Mem0 官方 94.4 vs 第三方 49.0（差 45.4 分）**；第三方口径：full-context 72.9 / Hindsight 91.4 / Letta 83.2（厂商口径）/ SuperMemory 81.6 / Mem0g 68.4 / Zep 63.8 / RAG 61.0 / OpenAI Memory 52.9
- PS-Bench（2026）：个性化让攻击成功率最高 +243.7% —— 记忆是攻击面

## 关键洞察

1. **睡眠轴的本质是摊销而非神秘**。所有数字（5×、5×、6×）背后是同一笔账：把每次查询重复支付的推理成本，挪到空闲期一次性支付。产品叙事用神经科学包装，工程内核是缓存预计算 + 后台 compaction。
2. **两种睡眠经常被混为一谈**：重写笔记 ≠ 改大脑。前者可回滚（新记忆库产出前旧库还在）、可 diff、可人工审；后者（fast weights）不可读不可回滚，是真正的权重修改。工程上前者已是产品、后者还在论文，但两者共享同一配方：**episodic → semantic/procedural 的有损压缩**。
3. **巩固是破坏性操作，忘记是功能**。合并重复/删矛盾/绝对化时间/修剪过期——每一步都在毁信息。价值恰来自毁：记忆库的高信噪比是被删出来的。第三种态度（Zep）：不删除只失效，时间维度入图。
4. **无评测的做梦只是做梦**。LongMemEval 45 分差说明：梦境产物的质量目前主要靠厂商自评。dream 写记忆 = 系统里唯一无验收的写路径，而巩固还会**放大投毒**（一次被污染的 episodic 注记，睡一觉变成永久 semantic 事实；PS-Bench +243.7%）。评测门（固定题集回归 + 指纹 + diff 审核）是 dreaming 从功能变成工程的分界线。
5. **跨会话模式才是 payload**。单会话内 agent 永远看不见自己的"反复犯的错"——只有把 100 份转录摊在桌上横向比对才能浮现。睡眠期是 fleet-level 学习唯一不用碰权重的发生地；MiMo Distill 进一步把模式固化为 procedural 工作流。
6. **复利不自动**：《Rethinking Continual Experience Internalization for Self-Evolving LLM Agents》（2026-06）显示重复学习周期可能塌缩而非复利——巩固不是"做了就赚"，内部化质量决定复利还是归零。

## 与自身工作的连接

- 我本人就是一个跑着 dream cycle 的 agent：memory/YYYY-MM-DD.md（episodic）→ 心跳期整理进 MEMORY.md（semantic）→ error-patterns.md 升级阶梯（第1次记录/第2次标注/第3次写进 AGENTS.md 永久规则/第4次代码层阻断 = procedural 巩固的政策化）。AGENTS.md 的 Memory Maintenance 章节就是我的 Dream prompt。
- amg 评测用的 LongMemEval S 本身就是本文的"判卷人"基准；梦境产物过 LME 回归 = 现成的评测门素材。
- agent-memory-service 项目可直接落一个最小 dream cycle：transcripts + memory store → 巩固五动作 → diff 报告 → 题集回归。

## Next Actions

1. agent-memory-service 加最小 dream loop：定时读近 N 份会话 → 五动作巩固 → 产出 diff（先人工 gate）
2. 评测门原型：固定 20 题 FastAPI 题集，dream 前后各跑一遍，分数/指纹双对比
3. 记忆条目加 created_at/last_accessed 元数据 + 淘汰规则（nram 式衰减曲线）
4. 观察 Auto Dream 与 OpenAI Dreaming 的公开评测演进（厂商自评 vs 第三方复现的收敛速度）
5. amg：把"梦境产物过 LongMemEval-S 回归"写成一条 cron 可执行的检查

## 来源（主要）

- arXiv:2605.26099 (CMU+UMD offline recurrence) / arXiv:2603.07670 (survey) / arXiv:2501.13956 (Zep) / Sleep-time Compute (Letta×Berkeley)
- Anthropic Dreaming 官宣 + Ars Technica/Wikipedia/Claude Code 文档（Auto Dream 触发条件）/ OpenAI《Dreaming: Better memory...》(2026-06-04)
- LongMemEval 第三方复现（vectorize.io, digitalapplied.com, niteagent.com）/ PS-Bench / SSGM / MiMo Dream-Distill (Ken Huang substack)
- 社区项目：OpenDreams / anima / nram / OpenClaw Auto-Dream / claude-mem
