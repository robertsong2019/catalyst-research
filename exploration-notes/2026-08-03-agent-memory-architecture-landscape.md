# AI Agent 记忆架构 2026 全景：从上下文窗口到时间知识图谱

**研究日期：** 2026-08-03
**研究领域：** AI Agent / LLM / Memory Systems
**研究方法：** 系统性搜索 + 多源交叉验证（学术论文、技术博客、GitHub 项目、基准测试报告）

---

## 核心概念（5个）

### 1. 三层记忆分类法（Episodic / Semantic / Procedural）
2025-2026 年，整个 Agent 记忆生态收敛到一个惊人的共识：认知科学几十年前提出的三层记忆模型——**情景记忆**（发生了什么）、**语义记忆**（事实是什么）、**程序记忆**（该怎么做）——成为了几乎所有生产级系统的架构基础。这不是学术界的"借鉴"，而是工程界在踩了无数次坑后独立发现的。

### 2. 双时间知识图谱（Bi-temporal Knowledge Graph）
Zep/Graphiti 的核心创新。每条边不仅记录"事实是什么"，还记录两个时间戳：**valid_time**（事实在真实世界中何时为真）和 **ingestion_time**（Agent 何时观察到了这个事实）。当事实变化时，旧事实不删除而是被"失效"。这使得 Agent 可以回答"去年三月时用户的地址是什么"这类时间旅行式查询。

### 3. Sleep-time Compute（离线固化）
Letta 团队提出。核心洞察：**Agent 不应该在对话中同时处理信息和整理记忆**——这就像一边开会一边做笔记还要同时整理归档。Sleep-time agent 在对话间隙异步运行，执行去重、冲突检测、图密度化、摘要生成等昂贵操作。这使得在线推理只需要做轻量的检索，而非完整的记忆构建。

### 4. LIGHT 三系统融合（Episodic + Working + Scratchpad）
ICLR 2026 论文提出的框架。在 BEAM 基准上证明：即使是 1M token 上下文窗口的模型，也会随着对话变长而急剧退化。LIGHT 将记忆分为三个互补系统，在推理时联合检索，比任何单一方法提升 3.5%-12.7%。

### 5. 写入治理 > 检索优化
Apple 2026.07 研究发现：选择性写入记忆的 Agent 达到 96% 准确率，而写入全部历史的只有 71%。Mem0 的熵感知写入在 add() 阶段过滤低价值内容，比在 retrieve() 阶段排序节省 40% token。**控制写入就是控制整个记忆库的质量。**

---

## 关键洞察（5条）

### 洞察 1：更大的上下文窗口 ≠ 更好的记忆
BEAM 基准（ICLR 2026）给出了铁证：
- GPT-4 Turbo 128K 上下文：LoCoMo 总分 51.6（人类 87.9）
- 即使有 1M token 窗口的模型，在 10M token 对话上也崩溃到 10-20% 准确率
- 核心原因：**context rot**——上下文越长，注意力越分散，关键信息被淹没
- 结论：记忆不是"更大的窗口"问题，而是"什么该被放入窗口"问题

### 洞察 2：五大系统在做完全不同的赌注
| 系统 | 核心赌注 | 最适合的场景 |
|------|---------|------------|
| Mem0 | 提取-冲突检测-图存储管线 | 实时对话个性化 |
| Letta | Agent 自我管理记忆（OS 模式） | 需要 Agent 学习和进化的场景 |
| Zep/Graphiti | 双时间知识图谱 | 需要时间推理的企业场景 |
| Cognee | 文档→知识图谱 ETL 管线 | 多模态数据融合 |
| Supermemory | 极简托管 API | 快速原型和轻量部署 |

**它们不是可互换的存储层。** 选择哪一个，决定了你的应用架构长什么样。

### 洞察 3：基准测试的诚实与不诚实
- Mem0 自报 LoCoMo 92.5，但 Maximem 的复现实验降到了 73.8
- 厂商基准数字"不能在复现中存活"——**永远要问 harness 是谁跑的**
- BEAM 是目前最难以注水的基准：10M token 规模下，没有真正的记忆架构能伪装
- Exabase M-1 在 BEAM 10M 上达到 68.0%（2026.07 SOTA），但这是三天前的新闻，随时可能被超越

### 洞察 4：时间推理是最大的未解难题
- GPT-4 Turbo 在 LoCoMo 时间问题上的得分：51.4（人类 92.6）——**41.2 分的鸿沟**
- Mem0 的新算法在时间推理上提升最大（+29.6 分），但仍远未解决
- Zep 的双时间模型是目前最优雅的解决方案，但以写入复杂度为代价
- 矛盾解析（contradiction resolution）是所有模型都挣扎的能力——维持全局一致状态仍未解决

### 洞察 5：Agent 记忆正在从"API 调用"演变为"认知架构"
- Letta 从 server-side memory tools → git-backed context repositories → client-side filesystem
- 从"调 memory.add()"→"Agent 用 bash 操作记忆文件系统"
- Sleep-time compute 从"批量处理"→"认知固化"——Agent 在离线时重新组织、压缩、连接知识
- 未来方向：Memory Models（用 RL 训练记忆本身），而非只是训练检索

---

## 可落地 Next Actions

1. **立即评估你的 Agent 记忆需求**：按"需要什么记忆类型"（个性化 vs 机构知识 vs 时间推理）选择架构，而非按"哪个系统最火"
2. **实施写入治理**：在 add() 前加 read-before-write + governance gate。参考 Apple 的选择性记忆策略
3. **用 BEAM 类基准测试自己的场景**：不要只看厂商数字。构造你自己的长对话基准（100轮+），测时间推理和矛盾解析
4. **试水 Sleep-time 模式**：即使不用 Letta，也可以在对话结束后跑异步固化任务：去重、摘要、冲突检测
5. **关注双时间图**：如果你的 Agent 需要处理变化的事实（地址变更、角色更换、配置更新），Graphiti 的 bi-temporal 模型是目前最完整的方案
6. **监控 LongMemEval-V2**：新的 Agent 记忆评估基准正在出现，关注"经验丰富的同事"而非"记事本"范式

---

## 参考来源

- Mem0: arXiv:2504.19413 (ECAI 2025), State of Agent Memory 2026 Report
- Zep/Graphiti: arXiv:2501.13956, getzep.com/graphiti (20K+ GitHub stars)
- Letta: MemGPT (2023), Sleep-time Compute (2025), Context Repositories (2026)
- BEAM/LIGHT: ICLR 2026, arXiv:2510.27246, github.com/mohammadtavakoli78/BEAM
- Exabase M-1: BEAM SOTA (2026.07.28), 68.0% at 10M tokens
- Apple: Selective Memory for Agents (2026.07)
- PASB: arXiv:2607.10526 (病态服从持久化)
- LongMemEval-V2: arXiv:2605.12493 (Agent memory as experienced colleagues)
