# Agentic RL：从思维链 RL 到环境交互 RL（2026 全景）

> 日期：2026-08-14（晚间） · 主题：Agent 强化学习 / LLM 后训练
> 调研对象：20+ 系统/论文（Kimi-Researcher、Kimi K2.5 PARL、Tongyi DeepResearch、Agent-R1、Search-R1 系列、ToolRL/ReTool/TORL、DeepResearcher、ZeroSearch、Absolute Zero、AgentGym-RL、RAGEN、AutoForge、HiPER、KARL、GLM-5.2 PPO 路线、GPT-OSS agentic RL 复盘、Cursor/Chroma 生产实践、Fireworks 多轮 RL 最佳实践、Cameron Wolfe 综述）

## 一、背景：RL 的两次跃迁

1. **第一跃迁（2023-2025）**：RLHF → RLVR（可验证奖励 RL）。DeepSeek-R1 证明纯 outcome reward + GRPO 可以让模型"学会思考"，数学/代码等有标准答案的领域爆发。
2. **第二跃迁（2025-2026，本次主题）**：从 single-turn（一次生成一条思维链）到 **multi-turn agentic RL**（模型在真实/模拟环境中多轮调用工具、观察反馈、修正行为，整条轨迹一起优化）。代表：Kimi-Researcher、Tongyi DeepResearch、DeepResearcher。

关键区别（Cameron Wolfe 的 MDP 形式化）：
- Single-turn：state = token 上下文，transition 确定性（追加 token），reward = 终端奖励。
- Agentic：state = **联合状态**（上下文 + 环境外部状态），transition **非确定**（工具/环境可以随机返回），action 可以是文本 token 也可以是工具调用序列。

## 二、核心概念（5 个）

### 1. 端到端 Agentic RL（End-to-End RL）
不用预设 workflow、不用人工示教，让单一模型在环境中自由探索，用整条轨迹的 outcome reward 优化。Kimi-Researcher：HLE Pass@1 从 8.6% → 26.9%，平均 23 步推理、探索 200+ URL/任务。核心论点：**agent 能力应该内化进权重，而不是焊死在 workflow 里**。

### 2. Action Mask / Loss Mask（信用分配的工程基础）
Agent-R1 框架：训练时区分"模型生成的 token"和"环境返回的 token"，只对前者计算策略梯度。消融实验：关掉 advantage mask，PPO 从 0.3719 → 0.3136；再关掉 loss mask → 0.3022。环境 token 不是模型的决策，不该背锅也不该领功。

### 3. 冻结式信用分配（PARL 范式）
Kimi K2.5 的 Parallel-Agent RL：编排器可训练，子 agent 冻结（其轨迹视为环境观察，不进损失函数）。动机：多智能体联合优化时，"答对了"分不清是编排好还是子 agent 运气好 → 信用分配模糊 + 训练不稳定。解法不是更聪明的算法，而是**降维：把多智能体问题变回单智能体问题**。

### 4. 环境即数据
Pretraining 时代抢语料，agentic RL 时代抢**环境**。瓶颈从"标注数据稀缺"变成"高质量可验证环境稀缺"：Docker 沙箱集群、真实网页（DeepResearcher 在真实 web 环境做 RL）、生产影子后端。AutoForge 直接自动合成训练环境。"Train where you deploy"（Cursor 用影子生产后端、Chroma 对真实数据库训练）成为第一原则——训练环境和部署环境不一致，学到的能力会打水漂。

### 5. 上下文管理成为训练目标
长轨迹 RL 中上下文爆炸是物理约束。Kimi-Researcher 的 context management 机制让单条 rollout 延伸到 50+ 轮（消融：有该机制的模型多用 30% 轮次、性能更高）；另有工作把"总结历史"本身作为可学习的动作（summarization-based RL），以及常数内存的多轮 RL。上下文工程从推理时技巧变成训练时被优化的策略。

## 三、关键洞察（6 条）

1. **能力正在从 harness 迁回权重**。2024 年你在 prompt 里写"请一步步思考"，2026 年 RL 把它烧进权重并涌现出 prompt 写不出来的行为（如"面对看似简单的问题也主动交叉验证"的谨慎性）。工作流编排层（LangGraph 节点拼装式 agent）的价值空间被两头挤压——这是 Kimi-Researcher 明确的立论，且证据在积累。

2. **Outcome reward must dominate**（Fireworks 实战铁律）。中间奖励（如"成功调用了一次搜索"）权重过高 → 收敛到退化策略：无限刷"看起来局部正确"的动作而不完成任务。安全配方：outcome 为主 + 轻量格式奖励，只有在奖励明显稀疏时才加过程奖励，且必须监控涌现的 hack。这与 PRM 路线（给过程打分）在 agentic 场景的冲突值得注意。

3. **多轮 RL 可以让小模型在特定工作流上超过 frontier 模型**（Fireworks：从 0.5 reward 起步的学习曲线最终越过 frontier 基线）。AGI 叙事之外，这是普通团队最现实的入场理由：垂直任务的专用 agent 用 RL 蒸馏，成本可控。

4. **算法在退居二线，工程在成为护城河**。GLM-5.2 因 compaction 把超长轨迹切成变长子轨迹、组内比较失稳而弃 GRPO 转 PPO；GPT-OSS 的 agentic RL 复盘里 FlashAttention v3 修复、MoE 物化、attention sink 等系统优化直接决定训练能否收敛。异步分离式 rollout 基础设施是标配。训练代码 <30%，工程 >70%。

5. **ZeroSearch / Absolute Zero 指向"零数据"极限**：用 LLM 模拟搜索引擎（ZeroSearch）替代真实 API 省 90%+ 成本；Absolute Zero 用自博弈 + 验证器完全摆脱外部数据。环境本身在被"内化"——与概念 4 形成有趣的张力：先疯狂抢环境，再把环境学进模型。

6. **离线 RL 是被低估的旁路**（Sergey Levine）：用次优交互数据（易得）+ LLM 世界知识做离线 RL，可以学出超过数据生成者的策略。生产环境的日志就是金矿，不一定非要在线探索。

## 四、可落地 Next Actions

- [ ] 精读 Kimi-Researcher tech blog + Cameron Wolfe《Agentic RL: Frameworks and Best Practices》（本周内，建立完整心智模型）
- [ ] 跑通一个多轮 RL demo：SkyRL / verl / Agent-R1 三选一，7B 模型 + ToolRL 风格 hotpotQA 任务，重点观察 reward 曲线和退化行为
- [ ] **AMG 连接点**：把 agent-memory-graph 包装成 RL 环境——observation = 检索结果/记忆状态，action = 记忆操作（增删查/巩固/压缩），reward = 下游 QA 准确率。记忆策略从手写规则变成可学习策略，这可能是一个独立论文级方向（"learnable memory policy via RL"）
- [ ] 跟踪 GLM-5.2 的 PPO 路线（与自家模型栈一致，工程细节参考价值最高）
- [ ] 研究 ZeroSearch 的模拟环境思路：AMG 若做 RL 训练，可用模拟 agent 轨迹替代昂贵的真实多 agent 运行

## 五、参考文献（部分）

1. Kimi-Researcher: End-to-End RL Training for Emerging Agentic Capabilities (Moonshot, 2025-06)
2. Kimi K2.5: Visual Agentic Intelligence — PARL 范式 (arXiv 2602.02276)
3. Agent-R1: Training Powerful LLM Agents with End-to-End RL (arXiv 2511.14460)
4. AgentGym-RL: Training LLM Agents for Long-Horizon Decision Making (arXiv 2509.08755)
5. RAGEN: Understanding Self-Evolution in LLM Agents via Multi-Turn RL (arXiv 2504.20073)
6. AutoForge: Automated Environment Synthesis for Agentic RL (arXiv 2512.22857)
7. HiPER: 分层规划器/执行器 + Hierarchical Advantage Estimation (2026)
8. KARL: RL for LLM Agents on Multi-Turn Knowledge-Intensive Tasks (ACL 2026)
9. Search-R1 / R1-Searcher++ / R-Search：搜索能力 RL 三部曲
10. ZeroSearch: Incentivize Search Capability without Searching / Absolute Zero (自博弈)
11. ToolRL: Reward is All Tool Learning Needs / ReTool / TORL / OTC
12. DeepResearcher: RL in Real-world Environments (GRPO + 真实 web)
13. Tongyi DeepResearch: agentic mid-training + post-training 统一范式
14. Fireworks: Best Practices for Multi-Turn RL（实战配方）
15. Cameron Wolfe: Agentic RL — Frameworks and Best Practices（含 GLM-5.2 PPO 细节）
16. HF Blog: Unlocking Agentic RL Training for GPT-OSS（工程复盘）
17. philschmid: How Kimi, Cursor, and Chroma Train Agentic Models with RL
18. NeurIPS 2025: A Practitioner's Guide to Multi-turn Agentic RL（环境/策略/奖励三支柱分析）
