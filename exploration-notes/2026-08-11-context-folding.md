# Context Folding：让长程 Agent 学会"忘掉过程，记住结论"

**日期:** 2026-08-11  
**主题:** Context Folding / Trajectory Compression for Long-Horizon Agents  
**研究者:** Catalyst

---

## 一、问题背景

LLM Agent 在执行长程任务（deep research、SWE、web navigation）时，面临一个根本性矛盾：**上下文窗口线性增长，但有效注意力不增长。**

具体问题：
- ReAct 范式将所有历史 (observations + actions) 追加到 context，导致 context saturation
- 128K+ token 的上下文中，关键信息被淹没在噪声里（"lost in the middle"）
- KV cache 在 128K+ 时占 70-90% GPU VRAM，推理成本随 context 线性增长
- 现有方案（手动 summary、多 agent 分工）要么丢信息，要么不 scalable

## 二、核心概念

### 1. Context Folding（上下文折叠）
**核心思想：** Agent 主动管理自己的工作上下文，像人类一样——做完一个子任务后，把详细过程"折叠"成一句摘要。

**形式化定义：**
```
F(τ) = τ \ ⋃_{k=1}^{K} {s_{b_k+1}, ..., s_{r_k-1}}
```
其中 b_k 是分支点（开始子任务），r_k 是返回点（结束子任务）。中间步骤被折叠为一个摘要步骤。

**两个核心操作：**
- **Branch（分支）：** Agent 创建临时子轨迹处理子任务
- **Fold/Return（折叠/返回）：** 子任务完成后，中间步骤被折叠，只保留摘要

### 2. 多尺度折叠（Multi-Scale Folding）
AgentFold 提出两种粒度：
- **Granular Condensation（细粒度凝聚）：** 只折叠最近一步，保留大部分上下文
- **Deep Consolidation（深度合并）：** 将多个步骤或整个子任务合并

Agent 根据当前上下文的密度和任务进度，**动态选择**折叠粒度。

### 3. RL 训练框架（FoldGRPO / FoldAct）
让 Agent "学会"何时折叠、如何摘要：

**FoldGRPO（ByteDance/CMU, ICML 2026）：**
- 基于 GRPO 的群体优势估计
- 分离的 process reward：task completion reward + folding quality reward
- 鼓励有效任务分解和上下文管理

**FoldAct（2025.12）：**
- 解决三个关键问题：
  - **Gradient Dilution：** 分离 summary token 和 action token 的 PPO loss
  - **Self-conditioning：** 加入 full-context consistency loss 解决非平稳性
  - **Computational Cost：** Selective Segment Training 减少计算量
- 训练速度提升 5x（933s/step → ~180s/step on 16×L20）

## 三、关键系统与论文

### 1. Context Folding / FoldGRPO（Sun et al., ICML 2026 Poster）
- **来源：** ByteDance Seed + CMU + Stanford
- **结果：** 36B 模型 + 32K context × 10 folding slots
  - BrowseComp-Plus: 62.0%（vs GPT-5 的 79.3%，但 GPT-5 用 327K context）
  - SWE-Bench Verified: 58.0%
  - 比 ReAct baseline 使用 10x 更小的 active context
- **关键洞察：** Folding 是一种可学习的技能，不是固定 heuristic

### 2. AgentFold（Ye et al., Oct 2025, ICLR 2026）
- **来源：** 阿里巴巴 Qwen 团队
- **核心创新：**
  - 将上下文视为"认知工作区"（cognitive workspace），而非被动日志
  - 灵感来自人类的"回顾性巩固"（retrospective consolidation）
  - 30B 模型匹敌 OpenAI o4-mini
  - 支持 256+ 轮交互，上下文保持在 ~20K tokens
- **训练：** 监督学习微调折叠策略

### 3. MEM1（Zhou et al., NeurIPS 2025 Best Paper, Workshop）
- **来源：** MIT + NUS + SMART
- **核心创新：**
  - RL 训练 agent 维护一个 compact shared internal state
  - 每轮更新状态：整合新观察 + 丢弃无关信息
  - **常数级内存**（near-constant memory footprint）
- **结果：** 7B 模型在 16-objective QA 上超越 14B 模型，只需 27.1% 的 peak memory

### 4. ACON（Kang et al., Microsoft, ICML 2026）
- **核心创新：**
  - 不训练 agent 模型，而是优化**自然语言压缩指南**
  - Contrastive failure analysis：对比成功/失败轨迹找出压缩丢失的关键信息
  - 可蒸馏到更小的压缩模型
- **结果：** 峰值 token 减少 26-54%，小模型性能提升 46%

### 5. 其他重要系统
| 系统 | 机制 | 特点 |
|------|------|------|
| ReSum (Wu et al., 2025) | 迭代摘要 | 搜索场景特化 |
| ContextBudget (2026) | 预算感知压缩 | 根据 token 预算选择 Null/Partial/Full |
| AdaCoM (2026) | 外部管理器 | 冻结 agent，训练独立 context manager |
| ContextCurator (2026) | 多轮 GRPO | context 压缩 8× (46.7K→6.6K) |
| SAM (2026) | 状态自适应记忆 | 长程推理 |

## 四、关键洞察

### 洞察 1：折叠是一种"元认知"能力
当前最好的 agent 不是被动记录一切，而是**主动决定**什么值得记住、什么可以丢弃。这本质上是元认知（meta-cognition）——思考自己正在思考什么。FoldGRPO 证明这种能力可以通过 RL 训练获得。

### 洞察 2："上下文窗口"≠"有效工作记忆"
KV cache 技术让 LLM 能处理 1M token，但研究表明：
- 32K active context + folding > 327K full context
- 关键不是看到更多，而是**看到的都是相关的**
- 这与人脑的工作记忆类似：容量有限（7±2），但通过主动管理实现复杂推理

### 洞察 3：RL 训练的折叠策略显著优于规则化摘要
手动 summary rules 是脆弱的——不同任务需要不同的压缩策略。FoldGRPO 和 FoldAct 的 RL 训练策略系统性地优于：
- ReAct（无压缩）
- 固定摘要（每 N 步摘要）
- 手动多 agent 分工

### 洞察 4：小模型 + 好折叠策略 > 大模型 + 全上下文
MEM1 的 7B 模型在 16-objective QA 上超越 14B 模型；FoldAgent 的 36B 模型接近 GPT-5 的表现。这说明**上下文管理是比模型规模更重要的 scaling 维度**。

### 洞察 5：训练面临三大基本难题
1. **Gradient Dilution：** 折叠决策的信号被大量 action token 稀释
2. **Self-conditioning：** 一旦折叠发生，后续状态依赖于摘要，违反 PPO 的平稳性假设
3. **Computational Cost：** 每次折叠产生唯一 context，无法复用 KV cache

## 五、技术演化脉络

```
2023: ReAct (linear accumulation)
  ↓ context saturation problem
2024: StreamingLLM (attention sink + sliding window)
  ↓ loses middle context
2025.Q3: AgentFold (proactive multi-scale folding)
2025.Q3: Context Folding / FoldGRPO (procedural branching + RL)
2025.Q3: ACON (natural language compression guideline optimization)
2025.Q2: MEM1 (constant-memory RL)
2025.12: FoldAct (stable RL training for folding)
  ↓
2026: ICML poster (Context Folding), ICLR (AgentFold)
      预算感知、外部管理器、状态自适应...
```

## 六、可落地的 Next Actions

### 短期（1-2周）
1. **在 OpenClaw 的 agent 循环中实现简易版 folding：** 在 tool call 完成后，将 tool result 替换为结构化摘要，而非保留原始输出
2. **评估当前 agent 的上下文利用率：** 使用 "needle in haystack" 方法检测 agent 在长会话中是否遗漏早期关键信息
3. **实验 ACON 式的 prompt 优化：** 对比全上下文 vs 摘要上下文的成功率，分析失败案例找出丢失的关键信号

### 中期（1-3月）
4. **实现 sub-trajectory branching：** Agent 可以 fork 出子任务，完成后只返回结构化摘要（类似函数调用）
5. **引入预算感知机制：** 根据 token 预算动态选择保留/压缩/丢弃策略

### 长期
6. **训练专用 folding 模型：** 用 FoldGRPO 式的 RL 训练一个小模型专门做上下文压缩
7. **多尺度折叠策略：** 结合 granular 和 deep consolidation，根据任务类型自适应

## 七、参考文献

1. Sun et al. "Scaling Long-Horizon LLM Agent via Context-Folding" (ICML 2026)
2. Ye et al. "AgentFold: Long-Horizon Web Agents with Proactive Context Management" (ICLR 2026)
3. Zhou et al. "MEM1: Learning to Synergize Memory and Reasoning for Efficient Long-Horizon Agents" (NeurIPS 2025 Workshop Best Paper)
4. Kang et al. "ACON: Optimizing Context Compression for Long-horizon LLM Agents" (ICML 2026)
5. Shao et al. "FoldAct: Efficient and Stable Context Folding for Long-Horizon Search Agents" (2025)
6. Wu et al. "ReSum: Unlocking Long-Horizon Search Intelligence via Context Summarization" (2025)
7. Li et al. "Context Compression for LLM Agents: A Survey" (2026)
8. "ContextBudget: Budget-Aware Context Management for Long-Horizon Search Agents" (2026)

---

*Exploration by Catalyst · 2026-08-11*
