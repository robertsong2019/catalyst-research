# Test-Time Training & Adaptive Inference: The New Frontier of Self-Adapting LLMs

> **Exploration Date:** 2026-07-03
> **Topic:** Test-Time Training (TTT), Test-Time Reinforcement Learning (TTRL), and Adaptive Inference for LLM Agents
> **Papers/Systems Covered:** 14

---

## 1. TL;DR — Why This Matters Now

The "train once, deploy forever" paradigm is dying. A new wave of techniques lets LLMs **update their own parameters during inference**, using self-supervised learning, reinforcement learning, or clever architectural tricks. This isn't prompt engineering or RAG — it's **actual weight adaptation at test time**, bridging the gap between frozen models and truly adaptive agents.

Three threads are converging in 2025-2026:
1. **TTT Layers** — architectural replacements for attention with trainable hidden states
2. **TTRL / SEAL / TT-SI** — RL and self-improvement frameworks that run at inference
3. **Sleep-Time Compute** — pre-computing context during idle periods for amortized speedup

The implication for agent systems is profound: agents that **learn from every interaction** without retraining.

---

## 2. The Taxonomy — Three Levels of Test-Time Adaptation

```
┌─────────────────────────────────────────────────────────────┐
│         TEST-TIME ADAPTATION TAXONOMY (2026)                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Level 0: Test-Time Compute Scaling (TTS)                   │
│  ├── Best-of-N sampling, majority voting                    │
│  ├── Chain-of-Thought / Tree-of-Thought                     │
│  ├── No parameter changes, just more compute per query      │
│  │                                                          │
│  Level 1: Test-Time Training (TTT)                          │
│  ├── Self-supervised weight updates on test input           │
│  ├── LoRA adapters fine-tuned on-the-fly                    │
│  ├── TTT-Linear / TTT-MLP as sequence layers                │
│  │                                                          │
│  Level 2: Test-Time Reinforcement Learning (TTRL)           │
│  ├── RL with self-generated rewards (no ground truth)       │
│  ├── Majority-vote → pseudo-reward → policy gradient        │
│  ├── Self-play and continual evolution                      │
│  │                                                          │
│  Level 3: Sleep-Time Compute                                │
│  ├── Pre-process context during idle time                   │
│  ├── Amortize compute across multiple queries               │
│  ├── Stateful agents with persistent memory                 │
│  │                                                          │
│  Level X: Architectural TTT (In-Place TTT)                  │
│  ├── MLP blocks as fast weights                             │
│  ├── Drop-in enhancement, no retraining needed              │
│  └── ICLR 2026 Oral                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Paper-by-Paper Deep Dive

### 3.1 TTT Layers: Learning to Learn at Test Time
**Sun et al., ICML 2025** | [Paper](https://zhang677.github.io/publications/ttt2025.pdf) | [Code (PyTorch)](https://github.com/test-time-training/ttt-lm-pytorch) | [Code (JAX)](https://github.com/test-time-training/ttt-lm-jax)

**Core Idea:** Replace RNN hidden states with **ML models** that are updated via self-supervised gradient descent at test time. The hidden state IS a model (linear or MLP), and the update rule IS an SGD step.

**Two Variants:**
- **TTT-Linear:** Hidden state = linear model `Wx`. O(N) complexity. Faster than Transformer at 8k context.
- **TTT-MLP:** Hidden state = 2-layer MLP (4× width, GELU). More expressive but higher memory I/O cost.

**Key Results:**
- Both TTT-Linear and TTT-MLP keep reducing perplexity as context grows (like Transformer), while Mamba plateaus at 16k
- TTT-Linear matches Mamba wall-clock time
- Pretrained checkpoints available: `Test-Time-Training/ttt-linear-1.3b-pile-8k`

**Critical Insight:** The inner loop (training the hidden state on current context) is essentially **learning to compress context** — not memorizing answers, but learning efficient encodings. This is analogous to how attention uses KCV to compress relevant information, but with linear instead of quadratic cost.

---

### 3.2 In-Place Test-Time Training
**Feng, Luo, Hua, Zhang, Huang, Di He, Cai — ICLR 2026 Oral** | [Paper](https://arxiv.org/html/2604.06169v1) | [OpenReview](https://openreview.net/forum?id=dTWfCLSoyl)

**Problem:** TTT layers require architectural changes → can't drop into existing LLMs.

**Solution:** Repurpose existing MLP blocks as fast weights. Specifically:
- Freeze `W_gate` and `W_up` (slow weights)
- Make `W_down` the adaptable fast weight (updated in-place during inference)
- Replace generic reconstruction objective with **Next-Token-Prediction-aligned objective**

**Results:**
- Qwen3-4B enhanced with In-Place TTT achieves superior performance at 128k context
- Advantage widens with sequence length (64k → 128k → 256k extrapolation)
- Works as both a **drop-in enhancement** (no retraining) AND when pretrained from scratch

**Why It's an Oral:** This resolves the three key barriers to TTT adoption:
1. ❌ Architectural incompatibility → ✅ Drop-in MLP repurposing
2. ❌ Computational inefficiency → ✅ Chunk-wise update mechanism
3. ❌ Misaligned objectives → ✅ NTP-grounded objective with theory

---

### 3.3 SEAL: Self-Adapting Language Models
**Zweiger, Pari, Guo, Akyürek, Kim, Agrawal — 2025** | [Paper](https://arxiv.org/html/2506.10943v1)

**Core Idea:** Train LLMs to **generate their own fine-tuning data and hyperparameters** ("self-edits") via RL.

**Architecture:** Two nested loops:
- **Outer loop (RL):** Optimize self-edit generation — model learns WHAT data helps it improve
- **Inner loop (TTT):** Apply generated self-edits via LoRA gradient descent

**Stunning Results:**
| Method | Success Rate |
|--------|-------------|
| ICL (baseline) | 0% |
| TTT + Self-Edit (no RL) | 20% |
| **SEAL** | **72.5%** |
| Oracle TTT (human-crafted) | 100% |

**Key Insight:** The model learns to generate the RIGHT training data for itself. It's not just self-supervised learning — it's **meta-learning what to learn from**.

---

### 3.4 TTRL: Test-Time Reinforcement Learning
**Zuo, Zhang, Sheng et al. (Tsinghua + Shanghai AI Lab) — NeurIPS 2025** | [Paper](https://arxiv.org/pdf/2504.16084) | [Code](https://github.com/prime-rl/ttrl)

**The Breakthrough:** RL on **unlabeled** test data. No ground truth needed.

**Mechanism:**
1. Sample N outputs from the model for a test input
2. Use **majority voting** (most common answer) as pseudo-ground-truth
3. Compute binary reward: 1 if output matches majority, 0 otherwise
4. Update policy via GRPO/PPO/PRIME (algorithm-agnostic)

**Results:**
- **+211% pass@1** on AIME 2024 with Qwen-2.5-Math-7B (unlabeled test data only)
- Surpasses the `maj@n` upper limit of the initial model
- Approaches performance of models trained with ground-truth labels

**Why It Works:** Pre-trained models have strong priors. Even without labels, the majority answer from multiple samples is usually correct enough to provide useful reward signal. This is **bootstrapping intelligence from model consensus**.

**Limitation (identified by EVOL-RL follow-up):** TTRL causes diversity collapse — pass@n drops even as pass@1 rises. The model becomes over-confident. Solution: add novelty/entropy terms.

---

### 3.5 TT-SI: Self-Improving LLM Agents with Test-Time Training
**Acikgoz, Qian, Ji, Hakkani-Tür, Tur (UIUC) — ACL 2026 Findings** | [Paper](https://aclanthology.org/2026.findings-acl.462.pdf)

**Three-Stage Self-Improvement:**
1. **Self-Awareness:** Uncertainty estimator identifies samples the agent struggles with
2. **Self-Data Augmentation:** Generate synthetic examples from uncertain cases
3. **Self-Improvement:** Lightweight LoRA fine-tuning on generated data

**Results:**
- **+5.48% average absolute gain** in direct inference across 4 agent benchmarks
- Achieves this with **1 training instance per uncertain case**
- Outperforms standard SFT while using **68× less training data**

**Variant — TT-D (Test-Time Distillation):** Replace self-generated data with stronger model (GPT-5-mini) outputs → additional +0.94% to +2.65% gains.

**Key Insight:** Inspired by **Self-Regulated Learning** theory from psychology. Agents that know what they don't know can target their own weaknesses efficiently. The uncertainty signal is the crucial innovation — training on ALL samples barely helps, but training on UNCERTAIN samples is transformative.

---

### 3.6 TTT-Discover: Learning to Discover at Test Time
**Yuksekgonul et al. — Jan 2026** | [Topic Summary](https://www.emergentmind.com/topics/test-time-training-to-discover-ttt-discover)

**Concept:** TTT + RL for **discovery tasks** — finding record-breaking solutions in math, GPU optimization, algorithm design, biology.

**Method:** Entropic utility objective + adaptive β scaling + PUCT-inspired exploration strategy. Focuses search on high-reward regions.

**Significance:** Extends TTT from "adaptation" to "discovery" — the model doesn't just fit known data better, it finds novel solutions.

---

### 3.7 TLM: Test-Time Learning for LLMs
**Hu et al. — ICML 2025** | [Paper](https://proceedings.mlr.press/v267/hu25z.html)

**Insight:** More accurate LLM predictions can be achieved by **minimizing input perplexity** of unlabeled test data.

**Method:** Formulate TTL as input perplexity minimization → self-supervised enhancement without labels.

---

### 3.8 One-Minute Video Generation with TTT
**Dalal et al. — CVPR 2025** | [Paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Dalal_One-Minute_Video_Generation_with_Test-Time_Training_CVPR_2025_paper.pdf)

**Application:** TTT layers in Diffusion Transformers for **1-minute video generation** (up from 3-second baseline).

**Result:** TTT-MLP outperforms Mamba-2, Gated DeltaNet, and Sliding Window Attention by **+34 ELO points** in human evaluation. +38 ELO on scene consistency.

**Why It Matters:** TTT isn't just for language — it's a general sequence modeling paradigm. Video generation's extreme sequence length requirements are a perfect fit for TTT's linear complexity.

---

### 3.9 Scaling LLM Test-Time Compute Optimally
**Snell, Lee, Xu, Kumar — ICLR 2025 Oral** | [Paper](https://openreview.net/forum?id=4FWAwZtd2n)

**Finding:** Test-time compute effectiveness **critically depends on prompt difficulty**. One-size-fits-all scaling is suboptimal.

**"Compute-Optimal" Strategy:** Adaptively allocate compute per prompt → **4× more efficient** than best-of-N baseline. Can outperform 14× larger model in FLOPs-matched evaluation.

---

### 3.10 When More Thinking Hurts: Overthinking in Test-Time Compute
**2026** | [Paper](https://arxiv.org/html/2604.10739v1)

**Counterintuitive Finding:** More reasoning tokens ≠ better answers. Systematic study shows:
- Marginal returns diminish rapidly past a certain point
- **Overthinking** degrades performance (model talks itself out of correct answers)
- Need adaptive reasoning length based on problem characteristics

**Implication:** Test-time compute scaling needs **difficulty-aware budgets**, not just "more tokens."

---

### 3.11 Sleep-Time Compute: Beyond Inference Scaling
**Letta + UC Berkeley — 2025** | [Paper](https://www.letta.com/blog/sleep-time-compute) | [Code](https://github.com/letta-ai/sleep-time-compute)

**Paradigm Shift:** Move compute-intensive reasoning to **idle/sleep time** between user queries.

**How It Works:**
1. During "sleep," agent pre-processes context, forms connections, rewrites memory
2. During "wake" (user query), agent uses pre-processed state for fast response
3. Requires **stateful agents** (persistent memory)

**Results:**
- Up to **+18% accuracy** improvement by scaling sleep-time compute
- Up to **+13%** additional gains from parallel sleep-time processing
- Test-time tokens weighted 10× higher (latency-critical) → sleep-time is dramatically cheaper
- Diminishing returns after optimal sleep compute budget

**Key Requirement:** Stateless models can't benefit. Sleep-time compute fundamentally requires **stateful agents with persistent memory**. This validates architectures like OpenClaw's memory system.

---

### 3.12 TTT is Secretly Linear Attention
**NVIDIA Research — 2026** | [Project Page](https://research.nvidia.com/labs/sil/projects/tttla)

**Revelation:** A broad class of TTT architectures, even multi-layer MLPs with complex designs, can be expressed as **learned linear attention operators**.

**Practical Benefits:**
- Principled architectural simplifications
- Fully parallel formulations that preserve performance
- Systematic reduction of diverse TTT variants to standard linear attention

**Implication:** TTT and linear attention are two sides of the same coin. This unifies the theoretical landscape.

---

### 3.13 Adaptive Test-Time Compute for Planning Agents
**Huang et al. — June 2026** | [Paper](https://furong-huang.com/wp-content/uploads/2026/06/Test-Time_Thinking_Control_June_2026.pdf)

**Comprehensive Framework:** Test-time alignment for agents including:
- **GenARM:** Reward-guided generation with autoregressive reward models (ICLR 2025)
- **SafeThink:** Inference-time safety defense — monitor reasoning steps, steer on violations
- **FlowBank:** Query-adaptive agentic workflow optimization through precompute-and-reuse

---

### 3.14 EVOL-RL: Fixing TTRL's Diversity Problem
**2025** | [Paper](https://arxiv.org/html/2509.15194v1)

**Problem with TTRL:** While pass@1 increases, pass@n drops — model becomes overconfident and brittle.

**Solution:** Add **novelty terms** to prevent mode collapse. Majority drives selection, novelty promotes variation. Inspired by evolutionary dynamics.

---

## 4. Unified Landscape Map

```
                    PARAMETER-FREE                    PARAMETER-UPDATING
                    ┌──────────────────┐              ┌──────────────────────────┐
                    │  Test-Time       │              │  Test-Time Training      │
                    │  Compute Scaling │              │  (TTT)                   │
                    │                  │              │                          │
 COGNITIVE          │  • Best-of-N     │              │  Architecture-Level:     │
 (reasoning)        │  • CoT/ToT/GoT   │              │  • TTT-Linear/MLP layers │
                    │  • PRM search    │              │  • In-Place TTT (MLP→FW) │
                    │  • Self-reflection│             │                          │
                    │                  │              │  Instance-Level:         │
                    │  Overthinking    │              │  • SEAL (RL + self-edit) │
                    │  is a real risk  │              │  • TT-SI (uncertainty)   │
                    └──────────────────┘              │  • TLM (perplexity min)  │
                                                      └──────────────────────────┘
                    ┌──────────────────┐              ┌──────────────────────────┐
                    │  Sleep-Time      │              │  Test-Time RL            │
 BEHAVIORAL         │  Compute         │              │  (TTRL)                  │
 (agent systems)    │                  │              │                          │
                    │  • Pre-process   │              │  • Majority-vote reward  │
                    │    context offline│             │  • Self-play / EVOL-RL   │
                    │  • Amortize      │              │  • TTT-Discover          │
                    │    across queries│              │  • Absolute Zero         │
                    │  • Needs stateful│              │                          │
                    │    agents        │              │  Reward-free:            │
                    │                  │              │  • Confidence-based      │
                    │                  │              │  • Novelty-seeking       │
                    └──────────────────┘              └──────────────────────────┘
```

---

## 5. Core Insights & Patterns

### 5.1 The Three Barriers (and How They're Being Broken)

| Barrier | Problem | Solution |
|---------|---------|----------|
| **Architectural** | TTT layers need new model architectures | In-Place TTT: repurpose existing MLP blocks |
| **Computational** | Gradient updates during inference are expensive | Chunk-wise updates + Triton-fused kernels |
| **Objective** | Generic reconstruction loss ≠ good LM objective | NTP-aligned objectives + RL-learned update strategies |

### 5.2 The Uncertainty Principle of Self-Improvement

TT-SI's most important finding: **targeting uncertain samples** is 68× more efficient than training on everything. This mirrors active learning theory but applied at test time.

```
Training on ALL samples:  +X% accuracy, 190 samples needed
Training on UNCERTAIN:    +X% accuracy, ~3 samples needed (68× less)
```

### 5.3 The Majority-Vote Reward Hypothesis

TTRL's deep insight: **model consensus is a sufficient reward signal** for RL. You don't need ground truth — you need diversity + aggregation.

But EVOL-RL shows this has a failure mode: **diversity collapse**. The model converges to a single mode, majority voting becomes uninformamous, and learning stalls.

**Resolution:** Novelty bonuses + entropy regularization maintain exploration.

### 5.4 Sleep-Time Compute Validates Stateful Agents

The sleep-time compute paradigm is impossible without **persistent memory**. This directly validates agent architectures like:
- OpenClaw's memory system (MEMORY.md + daily notes + semantic search)
- Letta's stateful agent platform
- Any agent with long-running persistent context

The insight: **idle time is a resource**. Agents should proactively consolidate, pre-process, and reflect during downtime.

### 5.5 TTT = Linear Attention (NVIDIA's Unification)

NVIDIA's finding that TTT is "secretly linear attention" has a powerful implication: **all these test-time adaptation methods are forms of learned attention with adaptive keys/values**. The difference is in WHAT gets adapted and HOW.

---

## 6. Implications for Agent System Design

### For Agent Architecture:
1. **Stateful agents are non-negotiable** — Sleep-time compute, TT-SI, and continual learning all require persistent state
2. **Uncertainty detection should be built-in** — Knowing what you don't know is the key to efficient self-improvement
3. **Diversity maintenance is critical** — Self-improvement loops can collapse without explicit novelty preservation

### For Agent Memory:
1. **Memory consolidation during idle time** (sleep-time compute) maps directly to OpenClaw's heartbeat/memory-maintenance pattern
2. **TTT-inspired working memory** — Instead of fixed-size context windows, imagine a "trainable" working memory that adapts to current context via gradient updates
3. **Confidence-weighted memory** — Store uncertainty scores alongside memories to guide future self-improvement

### For Agent Orchestration:
1. **Adaptive compute budgeting** — Different queries need different amounts of reasoning (compute-optimal scaling)
2. **Overthinking is real** — More reasoning steps can HURT; agents need meta-cognitive awareness to stop early
3. **Self-improvement pipelines** — Uncertainty → augmentation → fine-tuning is a general pattern applicable beyond LLMs

---

## 7. Actionable Next Steps

### 🔬 Research Directions (For Catalyst/Catalyst-Lab)

| # | Direction | Effort | Impact |
|---|-----------|--------|--------|
| 1 | **Prototype In-Place TTT for OpenClaw memory** — Apply the "MLP-as-fast-weights" idea to agent memory retrieval: during a conversation, continuously adapt a lightweight projection matrix on the fly | Medium | High |
| 2 | **Implement uncertainty-guided memory consolidation** — During heartbeat/idle time, identify low-confidence past decisions and re-examine them (TT-SI pattern for memory) | Low | High |
| 3 | **Sleep-time compute for agent context** — Pre-process long conversation history during idle heartbeats into compressed summaries, ready for fast retrieval when user returns | Low | Medium |
| 4 | **TTRL-inspired self-evaluation for agent skills** — When agent completes a task, sample multiple solutions, use majority voting to self-assess quality | Low | Medium |
| 5 | **Explore EVOL-RL diversity metrics for agent skill library** — Ensure self-generated skills don't converge to a narrow distribution | Medium | Medium |

### 🛠️ Implementation Ideas

**Quick win (1-2 hours):**
- Add uncertainty estimation to agent decision-making: when confidence < threshold, trigger reflection/self-improvement loop
- Implement "sleep-time consolidation" in heartbeat: during idle periods, compress recent memory files into denser representations

**Medium-term (1-2 weeks):**
- Build a TTT-inspired adaptive retrieval layer: instead of fixed BM25/vector scores, learn per-conversation weights for different retrieval signals
- Prototype majority-vote self-evaluation: for important decisions, sample 3-5 reasoning paths and use consensus

**Long-term exploration:**
- Integrate In-Place TTT concepts into agent memory architecture: treat memory retrieval as a trainable hidden state that adapts to current conversation context
- Explore TTRL patterns for agent self-evolution: can an agent improve its own skills through unlabeled task experience?

### 📚 Reading Priority

1. 🔴 **In-Place TTT** (ICLR 2026 Oral) — Most immediately applicable architectural insight
2. 🔴 **TT-SI** (ACL 2026) — Practical self-improvement framework for agents
3. 🟡 **TTRL** (NeurIPS 2025) — Paradigm-shifting RL without labels
4. 🟡 **Sleep-Time Compute** — Validates stateful agent architecture, practical for OpenClaw
5. 🟢 **SEAL** — Fascinating but requires RL training infrastructure
6. 🟢 **NVIDIA's TTT=Linear Attention** — Theoretical, but important for understanding

---

## 8. Connections to Previous Explorations

- **Agent Memory Architecture** (2026-06-30): TTT layers offer a new paradigm for working memory — trainable, adaptive, linear complexity
- **Self-Evolving Graph Memory** (2026-06-27): TTRL's self-improvement without labels could apply to graph memory quality optimization
- **Test-Time Scaling Adaptive Retrieval** (2026-06-23): Directly extended by the overthinking findings and compute-optimal strategies
- **System-2 Memory Policy** (2026-06-15): TT-SI's uncertainty-guided adaptation is a concrete implementation of System-2 deliberate reasoning at test time
- **KV-Cache as Working Memory** (2026-06-26): In-Place TTT's repurposing of MLP weights is conceptually parallel — both treat existing model components as adaptive memory

---

## 9. Open Questions

1. **Can TTT layers replace attention in agent systems?** The linear complexity is attractive for long-running agents with huge context, but the quality tradeoff at shorter contexts needs investigation.

2. **How to prevent catastrophic forgetting in continual TTT?** If an agent continuously updates parameters during inference, how do we prevent it from forgetting important earlier knowledge? (Chunk-wise updates help but don't fully solve this.)

3. **What's the right "sleep-time compute" budget for a personal agent?** Too little = missing opportunities; too much = wasted resources. Needs empirical study.

4. **Can TTRL work for non-reasoning tasks?** Majority voting works for math (verifiable answers), but what about open-ended tasks where "correctness" is subjective?

5. **How does In-Place TTT interact with existing fine-tuned models?** If a model is already RLHF'd/instruction-tuned, does in-place TTT during inference break alignment?

---

## 10. Key References

| # | Paper | Venue | Year |
|---|-------|-------|------|
| 1 | Learning to Learn at Test Time (TTT-Linear/MLP) — Sun et al. | ICML | 2025 |
| 2 | In-Place Test-Time Training — Feng et al. | ICLR (Oral) | 2026 |
| 3 | SEAL: Self-Adapting Language Models — Zweiger et al. | arXiv | 2025 |
| 4 | TTRL: Test-Time Reinforcement Learning — Zuo et al. | NeurIPS | 2025 |
| 5 | TT-SI: Self-Improving LLM Agents with TTT — Acikgoz et al. | ACL Findings | 2026 |
| 6 | TTT-Discover — Yuksekgonul et al. | arXiv | 2026 |
| 7 | TLM: Test-Time Learning for LLMs — Hu et al. | ICML | 2025 |
| 8 | One-Minute Video Generation with TTT — Dalal et al. | CVPR | 2025 |
| 9 | Scaling LLM Test-Time Compute — Snell et al. | ICLR (Oral) | 2025 |
| 10 | When More Thinking Hurts — arXiv | arXiv | 2026 |
| 11 | Sleep-Time Compute — Letta + UCB | arXiv | 2025 |
| 12 | TTT is Secretly Linear Attention — NVIDIA | Research | 2026 |
| 13 | EVOL-RL: Diversity in Label-Free RL | arXiv | 2025 |
| 14 | Adaptive Test-Time Compute for Planning Agents — Huang et al. | Various | 2025-26 |

---

_Generated by Catalyst晚间深度研究 · 2026-07-03_
