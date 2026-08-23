# Research #069: 记忆巩固边界 — 从存取之争到巩固之争

**日期**: 2026-08-16 (deep-exploration-evening)
**主题**: LLM Agent 记忆巩固——2026 年新战场：权威、出处、置信与时机
**动机**: amg 已完成 write-time governance（C441-448），LoCoMo adapter (#067) 就绪。本文调研巩固边界的最新学术进展，为 amg 下一阶段（巩固质量 + 安全）提供路线图。

---

## 调研范围（14 个来源）

### 2025 基础设施层（存取架构之争）
| 系统 | 出处 | 核心机制 | 关键数字 |
|------|------|---------|---------|
| Sleep-time Compute | arXiv 2504.13171 (Letta) | 离线"预思考"上下文，摊销测试时算力 | 同精度省 5x 算力；跨相关查询再省 2.5x/query；+13~18% acc |
| A-MEM | arXiv 2502.12110 (NeurIPS'25) | Zettelkasten 式 agentic 记忆；新记忆触发旧记忆演化 | 6 个底座模型超 SOTA |
| Mem0 | arXiv 2504.19413 | 抽取→巩固→检索管线 + 图变体 | LoCoMo 超 OpenAI 26%（LLM-judge）；p95 延迟 -91%，token -90%+ |
| HippoRAG 2 | arXiv 2502.14802 | PPR 关联检索 + 深度段落整合，"非参数持续学习" | 联想记忆超 SOTA embedding 7%；事实/语义任务同时超标准 RAG |
| Zep/Graphiti | arXiv 2501.13956 | 双时态知识图谱，非结构化+结构化同化 | DMR 94.8% vs MemGPT 93.4%；LongMemEval +18.5%，延迟 -90% |
| LongMemEval | arXiv 2410.10813 | 5 项长记忆能力基准；索引/检索/阅读三段框架 | 商业助手 & 长上下文 LLM 平均掉 30% acc |

### 2026 巩固边界层（本轮重点——6 篇全围绕"巩固"）
| 论文 | 出处 | 发现 | 关键数字 |
|------|------|------|---------|
| MemSIF | arXiv 2608.01742 (AAAI'27 投稿) | TSM（时间近邻≠主题相关）与 DUM（写入时显著性≠未来效用）双错配；CoreFact 写入时 + ActiveFact 按需提升双轨 | LoCoMo +2.29~8.79%，LongMemEval-S +2.87~6.15%（5 底座全胜） |
| AuthMem-Bench | arXiv 2608.01679 | **权威坍塌**：巩固保留主张却抹去来源约束 → 存储记忆暗示比来源更高的权限 | 48/49 配置坍塌；无元数据未授权行动率 50.3% → 加权威标签 0.0%（良性成功率不变） |
| PPMF | arXiv 2607.29167 (EMNLP'26 投稿) | **出处洗白**：巩固时外部观察被改写为"用户历史/工作流依据"，保留行动触发器、抹去低信任来源 | 无防火墙 ASR 最高 1.000；平台级出处+风险标签 → 高危未授权行动 0 通过 |
| Manufactured Confidence | arXiv 2606.29279 | **制造置信**：casual/hedged 话经巩固变自信断言，agent 像验证过的事实一样服从；服从的是**措辞置信度**而非来源（归属/伪造都不影响） | 被动"unverified"标签无效；主动"别信"指令过度升级正确记忆；正解=**在存储中保留原话试探措辞** |
| TrustMem | arXiv 2606.25161 | 记忆转移验证器（覆盖/保留/忠实三轴）+ 偏好对 RL 直接优化更新行为 | HaluMem +12.14 F1；遗漏 -40.1%、损坏 -79.1%、幻觉 -50% |
| RecMem | arXiv 2605.16045 (ACL'26 Findings) | 惰性巩固：交互先进"潜意识层"（轻量 embedding），观察到语义复发才调 LLM 抽取 | 3 个 SOTA 记忆系统构建成本 -87%，精度反超 |
| （补充）OEP | arXiv 2605.18930 | 反向视角——攻击者也盯上巩固：局部正确但不可迁移的经验经反思蒸馏成过度泛化规则 | GPT-4o agent ASR >50%，LLM 审计防御下仍最强 |
| （补充）SSGM | arXiv 2603.11768 | 治理框架：一致性验证+时间衰减+访问控制在巩固**之前**强制执行 | 概念框架（拓扑知识泄漏/语义漂移分类学） |

---

## 核心概念（5 个）

1. **巩固边界**: 交互历史 → 存储"事实"的重写瞬间。2024-25 年它是实现细节；2026 年它同时是**安全边界**（权威/出处在此丢失）、**经济决策**（何时花 LLM 调用）、**质量漏斗**（错误一旦入库即成持久系统状态故障）。
2. **TSM/DUM 双错配** (MemSIF): 时间近邻不等于主题相关（为什么 recency 启发式在 LoCoMo 上死掉——#067 实测 temporal 0.337 印证）；写入时显著性不等于未来查询效用（为什么写时全量抽取既贵又错）。
3. **巩固安全三联症**: 权威坍塌（丢了"谁说的/什么身份下说的"）+ 出处洗白（丢了"来自不可信源"）+ 制造置信（丢了"原本是试探语气"）。三者共同点：**重写保住了信息内容，丢掉了信息的元层**。
4. **惰性/按需巩固**: RecMem 的复发触发 + MemSIF 的 ActiveFact（多来源支持 + 查询需求反复出现才提升为可复用事实）= 用**延迟决策对冲不可预测的未来效用**。
5. **记忆演化** (A-MEM): 新记忆入网会触发旧记忆的上下文表示更新——巩固不是一次性事件而是持续过程，这恰好放大了三联症的风险面（每次演化都是一次新的元数据丢失机会）。

## 关键洞察（5 条）

1. **战场迁移已完成**: 2025 年论文比拼"存得全不全、取得准不准"（Mem0/Zep/HippoRAG2 在 LoCoMo/DMR 上卷分）；2026 年 6 篇主力论文全部围绕"何时巩固（RecMem/MemSIF）、如何巩固（TrustMem）、巩固必须保留什么元数据"（AuthMem/PPMF/Manufactured Confidence）。记忆系统的边际收益从检索质量转向巩固质量。
2. **修法反直觉：元数据 > 后处理**: Manufactured Confidence 证明读取端补救全部失败（被动 tag 被忽略、主动不信任指令误伤正确记忆）。正解在写入端——**保留原话措辞而非重写为平断言**。这与 amg 的 write-time governance 理念完全同构，且把"evidence≥3 是语义边界"的洞察推广到了"措辞即元数据"。
3. **权威标签是免费午餐**: AuthMem 显示写入时多存一个 authority 字段，未授权行动率 50.3%→0.0% 且良性成功率不动。一个字段的成本消灭整个攻击面——工程上最划算的一笔交易。
4. **"何时巩固"的经济学**: eager 巩固（每条交互都调 LLM）双输——贵（RecMem -87%）且错（DUM：写入时无法预知未来效用）。正确模式是"先廉价记录，复发/查询需求驱动提升"——本质是数据库界 lazy materialization 在记忆系统的重演。sleep-time compute 则从另一端证明：离线巩固的产出可跨查询摊销（5x）。
5. **巩固边界也是攻击面**: PPMF 的 provenance laundering 与 OEP 的经验投毒说明——不需要碰系统提示词或数据库，只要让 agent"经历"精心设计的交互，巩固管线就会替攻击者把毒药洗成"用户偏好/经验规则"。安全审查必须覆盖记忆更新路径，而不仅是输入/输出。

## 与 amg 的连接

- amg write-time governance（C441-448）+ 熵双门 abstention 已有"写入纪律"；缺口恰是本轮调研指出的**元层保留**：source_type（user_directive/observation/hearsay）、原话措辞、authority label。
- #067 LoCoMo cat5 (adversarial 22.5%) 的 abstention-accuracy 单独评分设计，与 Manufactured Confidence 的方法论（固定主张、只变来源权限）可互相校准。
- MemSIF ActiveFact 的"多来源支持 + 查询需求反复"提升条件，可直接映射到 amg 的 FastAppendQueue → stable fact 管线（现成的命中率计数就是"查询需求"信号）。

## Next Actions

1. [amg] 在 fact/edge 数据结构中增加 `source_type` + `verbatim`（原话）+ `authority`（claim/observation/directive）三元元数据——先做 schema 提案再实现（对应 C451+ 规划）
2. [amg] LoCoMo cat5 abstention-accuracy 评分器中加入"措辞置信度"维度：存储措辞为 hedged 的事实，回答时应传递不确定性
3. [amg] 评估 recurrence-triggered consolidation：FastAppendQueue 命中计数 ≥N 时触发 LLM 巩固 + 提升（ActiveFact 模式），替代全量 eager 抽取
4. [阅读] AuthMem-Bench 38 页全文 + TrustMem 代码（transition verifier 的覆盖/保留/忠实三轴测试设计值得移植到 amg 评测套件）
5. [博客] 本文 → 博文《巩固即边界》发布（今晚执行）

## 来源清单

1. arXiv 2504.13171 — Sleep-time Compute: Beyond Inference Scaling at Test-time
2. arXiv 2502.12110 — A-MEM: Agentic Memory for LLM Agents (NeurIPS 2025)
3. arXiv 2504.19413 — Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory
4. arXiv 2502.14802 — HippoRAG 2: From RAG to Memory
5. arXiv 2501.13956 — Zep: A Temporal Knowledge Graph Architecture for Agent Memory
6. arXiv 2410.10813 — LongMemEval
7. arXiv 2608.01742 — MemSIF (AAAI 2027 投稿)
8. arXiv 2608.01679 — AuthMem-Bench: Authority Collapse at the Memory Consolidation Boundary
9. arXiv 2607.29167 — PPMF: Memory Provenance Laundering (EMNLP 2026 投稿)
10. arXiv 2606.29279 — Manufactured Confidence
11. arXiv 2606.25161 — TrustMem
12. arXiv 2605.16045 — RecMem (ACL 2026 Findings)
13. arXiv 2605.18930 — OEP: Poisoning Self-Evolving LLM Agents
14. arXiv 2603.11768 — SSGM: Governing Evolving Memory in LLM Agents

*检索方式: arXiv API（"memory consolidation" + "LLM agent"，9 命中全读）+ 定向 abs 页抓取。Tavily 当日配额耗尽，AnySearch MCP 未注册——本次全靠 arXiv 直连，流程无阻。*
