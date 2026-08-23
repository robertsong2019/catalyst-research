# 搜索即推理：LLM 推理新范式的崛起

**日期：** 2026-08-06
**主题：** LLM Tree Search + Process Reward Models + Inference-Time Scaling
**研究领域：** AI Reasoning, LLM Inference, RL for Language Models

---

## 核心概念

### 1. 推理搜索 (Reasoning Search / LLM Tree Search)
将 LLM 的推理过程从线性链 (CoT) 扩展为树状搜索空间。核心组件：
- **搜索机制**：MCTS、Beam Search、Best-of-N、Tree of Thoughts
- **奖励函数**：外部验证器 (Lean/compiler) 或内部评估 (LLM-as-judge、PRM)
- **转移函数**：每步操作可以是自然语言推理、代码执行、工具调用

关键论文：Wei et al. (2025) 统一框架，Yao et al. Tree of Thoughts，AlphaProof (Nature 2025)

### 2. Process Reward Models (PRM)
对推理链的**每一步**打分，而非只评价最终答案。

演进路线：
- **第一代**：人工标注步骤标签 (Lightman et al. 2023, OpenAI's "Let's Verify Step by Step")
- **第二代**：自动生成标签 (Math-Shepherd: MCTS rollout 统计)
- **第三代**：生成式 PRM (GenPRM: 用 CoT + 代码验证来评分，7B 模型超越 72B 判别式 PRM)
- **最新**：多模态 PRM (VisualPRM, URSA)、领域专用 (AgentPRM, DataPRM)

### 3. RLVR (Reinforcement Learning with Verifiable Rewards)
DeepSeek R1 的核心突破：用可验证的二元奖励 (代码编译通过/数学答案匹配) 替代学习型奖励模型。

关键发现：
- GRPO 去掉了 critic model，极大简化训练
- R1-Zero 无需 SFT，纯靠 RLVR 就涌现出推理、自验证、反思能力
- 但：RLVR 只适用于有客观正确答案的领域 (数学、代码)

### 4. Reward Hacking 与 PURE
PRM 在 RL 训练中的核心问题：**summation-form credit assignment 导致 reward hacking**

PURE (NeurIPS 2025) 的解决方案：
- 用 **min-form** 替代 summation-form：V(s) = min(R_future) 而非 Σ(γ^t * R_t)
- 限制价值函数范围，防止"一步高分掩盖整体低质"
- 最强结果：PURE-PRM+VR 在 AMC23 上达到 83.9% (对比 RLVR baseline)

### 5. Adaptive Reasoning / 自适应推理深度
2026 年的核心实践趋势：不是每步都需要深度推理。

关键方法：
- **Reasoning Effort 参数**：OpenAI o3 的 low/medium/high，Anthropic 的 budget_tokens
- **多模型级联**：简单步骤用小模型，复杂步骤升级到推理模型 (CogRouter, ARES)
- **AgentTTS**：自动搜索最优计算分配
- 效果：ARES/CogRouter 减少 50-62% token，保持 SOTA 性能

---

## 关键洞察

### 洞察 1：AlphaProof 验证了"搜索 + 验证器 = 超人表现"的范式

AlphaProof 的核心架构：
1. Gemini LLM 将自然语言问题**自动形式化**为 Lean 代码
2. AlphaZero-style MCTS 在 Lean tactic 空间中搜索证明
3. Lean 编译器提供**完美验证**——错误分支立即被剪枝
4. 成功证明用于 expert iteration，强化策略网络

2025 年 11 月发表于 Nature。2025 年 IMO 达到金牌水平。更惊人的是：AlphaProof Nexus 框架在单次运行中解决了 9 个 Erdős 开放问题。

**启示：** 当你有完美验证器时，搜索可以放大 LLM 的"直觉"到超人水平。关键瓶颈不是 LLM 的能力，而是验证信号的质量。

### 洞察 2：PRM 是连接训练时和推理时的桥梁

PRM 有两个用途：
- **训练时**：提供 step-level 监督信号 (但容易 reward hack)
- **推理时**：引导搜索 (beam search, tree search)，做 Best-of-N 选择

PURE 的发现打通了一个关键问题：训练时的 credit assignment 公式必须与推理时的使用方式一致。Summation-form 在推理时很少使用 (推理时通常取平均或投票)，min-form 更接近推理时的选择逻辑。

**启示：** 训练目标和推理使用方式的对齐，比奖励信号本身更重要。

### 洞察 3：推理计算的成本呈指数级膨胀

- DeepSeek-R1 每个查询生成的 token 是普通模型的 10-100x
- MCTS 一次推理可能需要 100-1000 次 LLM 调用
- OpenAI 2024 年推理花费 $23 亿，是 GPT-4 训练成本的 15 倍
- 预测：2026 年推理计算需求将超过训练需求的 118 倍

但好消息是：
- Best-of-N 的 scaling law：Pass@k = 1-(1-p)^k，收益递减但可预测
- Adaptive reasoning 可以减少 50-62% 的 token
- 5-20% 的步骤需要深度推理，其余可以用快速模型

### 洞察 4：Overthinking 是真实存在的风险

推理模型在简单问题上表现**更差**：
- OpenAI 文档显示 o3/o4-mini 在简单事实查询上不如 GPT-4o
- 原因：过度推理导致模型"想多了"，从正确路径偏移到错误路径
- 小模型 (<10B) 几乎无法从 CoT 中获益
- Agent 场景中的 overthinking 表现为：分析瘫痪、不等待环境反馈就生成连续步骤链

**启示：** 推理不是越多越好。关键是在正确的步骤上做正确深度的推理。

### 洞察 5：推理搜索正在从"学术研究"转向"工程实践"

2026 年的成熟度信号：
- 主流 API 暴露 reasoning_effort 参数 (OpenAI, Anthropic, Google)
- 开源 PRM 生态丰富 (Awesome-Process-Reward-Models 列出 50+ 模型)
- ICML 2026 有专门的 Adaptive Reasoning tutorial
- 生产 agent 架构采用多模型级联 (5-20% 步骤路由到推理模型)
- Beam Search 在 agent 场景中重新获得重要性 (从 NLP 解码策略到 agent 决策可靠性)

---

## 可落地 Next Actions

1. **在 agent 系统中实现 reasoning effort 分级路由**
   - 对每个步骤评估复杂度，路由到不同 reasoning level
   - 参考 CogRouter / ARES 架构
   - 预期效果：减少 40-60% 的推理 token 消耗

2. **评估 PRM 在现有 agent 中的应用**
   - 使用开源 PRM (如 Math-Shepherd-7B, GenPRM-7B) 对 agent 推理链做 step-level 评分
   - 用 PRM 做 Best-of-N 选择而非训练 (避免 reward hacking)
   - 关注 AgentPRM (2025) 专门为 agent 场景设计

3. **在生产 agent 中加入 overthinking 检测**
   - 监控推理 token 数 vs 任务完成率的关系
   - 设置 token budget 上限，触发降级到快速模型
   - 关注三种 overthinking 模式：分析瘫痪、未等待反馈的连续步骤、过早退出

4. **跟踪 AlphaProof 范式的泛化**
   - 核心是"LLM 直觉 + 形式验证器 + MCTS"
   - 在代码生成领域：编译器/测试套件就是天然验证器
   - 在数据分析领域：SQL 执行结果就是验证器
   - 关键问题：你的领域是否有"足够好"的验证器？

5. **关注 PURE 的 min-form credit assignment**
   - 如果在做 RL 训练，评估 summation vs min-form 的效果差异
   - 特别关注 step-level reward 的场景
   - PURE-PRM+VR 的混合方案（过程奖励为主 + 少量可验证奖励）可能是最优组合

---

## 参考文献

1. Hubert et al. (2025). "Olympiad-Level Formal Mathematical Reasoning with RL." Nature 651, 607-613.
2. Wei et al. (2025). "Unifying Tree Search Algorithm and Reward Design for LLM Reasoning: A Survey." arXiv:2510.09988.
3. Cheng et al. (2025). "Stop Summation: Min-Form Credit Assignment (PURE)." NeurIPS 2025.
4. Zhao et al. (2025). "GenPRM: Generative Process Reward Models." 
5. Guo et al. (2025). "DeepSeek-R1: Incentivizing Reasoning Capability via RLVR."
6. Snell et al. (2024). "Scaling LLM Test-Time Compute Optimally."
7. Khalifa et al. (2025). "ThinkPRM: Generative PRM with CoT."
8. Zou et al. (2025). "ReasonFlux-PRM-7B."
9. AgentPRM (2025). "Process Reward Models for LLM Agents."
10. DataPRM (2026). "Process-Level Reward Modeling for Agentic Data Analysis." arXiv:2604.24198.
11. Pronesti et al. (2026). "Verifiable Process Reward Models for Structured Reasoning." ACL 2026 Findings.
12. ICML 2026 Tutorial: "Adaptive Reasoning in LLMs."
13. BAIR (2026). "Adaptive Parallel Reasoning."
14. Zylos Research (2026). "Adaptive Reasoning Depth in AI Agent Systems."
