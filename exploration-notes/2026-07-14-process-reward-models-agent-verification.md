# Process Reward Models for Agent Verification: Teaching AI to Know When It's Wrong

> Deep Research #009 — 2026-07-14
> Theme: PRM landscape 2025-2026 — from math verification to agentic task checking

## Context

AI agents are increasingly deployed in multi-step tasks — coding, web navigation, tool use,
fact-checking. Each step is a potential failure point. **Outcome Reward Models (ORMs)** only
check the final answer, leaving agents blind to where reasoning goes off the rails.
**Process Reward Models (PRMs)** score each intermediate step, enabling precise credit
assignment and early error detection. In 2025-2026, PRMs have moved from academic curiosity
to production deployment in coding agents, GUI agents, and multi-agent systems.

---

## Core Concepts (5)

### 1. ORM vs PRM — The Fundamental Shift

**Outcome Reward Model (ORM):** Looks at the final answer. "Is this correct? Y/N."
- Pro: Easy to train — just need final-answer labels
- Con: No signal on *where* the error is; in long reasoning chains (2000+ tokens),
  sparse signal makes learning extremely difficult

**Process Reward Model (PRM):** Scores each step independently.
- Pro: Dense supervision, pinpoint errors, enables search (tree-of-thought, MCTS)
- Con: Requires step-level labels, which are expensive to collect

OpenAI's "Let's Verify Step by Step" (Lightman et al., 2023) was the watershed paper
showing that PRMs dramatically outperform ORMs on MATH benchmark when combined with
best-of-N search. By 2026, this has been extended to virtually every agent domain.

### 2. Generative PRMs — The verifier that thinks

Traditional PRMs are classifier heads: input step → scalar score.
**Generative PRMs** (GenPRM, Zhao et al., 2025) are LLMs that *reason about correctness*
before scoring. Instead of a number, they produce a chain-of-thought evaluation:

```
Step: "To solve x² + 5x + 6 = 0, we use the quadratic formula..."
GenPRM: "The student correctly identifies the equation as quadratic. However,
they could also factor: (x+2)(x+3) = 0. The quadratic formula approach is valid
but unnecessarily complex. Step quality: Correct but suboptimal. Score: 0.7"
```

"Process Reward Models That Think" (Khalifa et al., 2025) showed that generative PRMs
achieve 78.1% accuracy on ProcessBench vs 72.0% for classifier-based PRMs — a 6-point
gap that widens on harder problems.

### 3. Rubric-Based PRMs — From human criteria to automatic scoring

Instead of binary correct/incorrect, **Rubric PRMs** evaluate against multi-criteria rubrics:
- Correctness (is the step logically sound?)
- Efficiency (is this the simplest approach?)
- Safety (does this step introduce risk?)
- Tool usage (was the right tool called with right parameters?)

**SWE-TRACE** (Han et al., April 2026) applies this to software engineering agents,
using stepwise oracle labels across multiple criteria to train a unified PRM that guides
both RL training and test-time search. **SWE-TRACE's key innovation**: LLM multi-task
cascading method that automatically generates rubric labels from execution traces,
eliminating the need for human annotation.

### 4. Self-Evolving Verification — SEVA and beyond

**SEVA** (Yuan et al., June 2026, accepted at AI4GOOD@ICML 2026) introduces a
self-improving verification loop:
1. Agent generates answer + supporting facts
2. Verifier checks each fact attribution
3. Verification failures become training data for the verifier
4. The verifier evolves with the agent

This closes a critical gap: static verifiers degrade as the agent improves.
SEVA's process reward isn't just a score — it's an *explanation* of why a specific
claim is or isn't supported, enabling human auditing.

### 5. RLVR + PRM — The training recipe that works

**Reinforcement Learning from Verifiable Rewards (RLVR)** combined with PRMs has become
the dominant training paradigm for reasoning agents in 2026:

1. Agent generates multiple reasoning trajectories
2. Each step is scored by a PRM
3. Trajectories are ranked by aggregate step scores
4. Best trajectories are used for policy gradient updates

Key results:
- **OREAL** (Lyu et al., 2025): 7B model achieves 94.0 pass@1 on MATH-500 through
  outcome reward + token-level credit assignment, matching 32B distillation
- **Verifiable Process Rewards for Agentic Reasoning** (Yuan et al., May 2026):
  Extends RLVR from math to general agentic tasks with environment-grounded verification
- **MAS-ProVe** (Venkataramani et al., Feb 2026): Process verification specifically
  designed for multi-agent systems, addressing high variance in multi-agent trajectories

---

## Key Systems & Papers (12)

| System | Date | Domain | Innovation | Key Result |
|--------|------|--------|------------|------------|
| Let's Verify Step by Step (OpenAI) | 2023 | Math | First PRM at scale | PRM >> ORM on MATH |
| Math-Shepherd | 2024 | Math | Automatic step labeling | No human annotation needed |
| GenPRM (Zhao et al.) | 2025 | Math | Generative reasoning before score | +6% on ProcessBench |
| PRMs That Think (Khalifa et al.) | 2025 | Math | CoT-based verification | 78.1% ProcessBench |
| OREAL (Lyu et al., Shanghai AI Lab) | 2025 | Math | Outcome RL + token credit | 7B = 94.0 MATH-500 |
| GroundedPRM (Zhang et al.) | 2025 | Reasoning | Tree-guided fidelity-aware | Robust on noisy steps |
| ToolPRMBench (Li et al.) | Jan 2026 | Tool use | Benchmark for tool-agent PRMs | Exposes PRM weaknesses |
| MAS-ProVe (Venkataramani et al.) | Feb 2026 | Multi-agent | Process verification for MAS | Reduces trajectory variance |
| Beyond Outcome Verification (Pronesti et al.) | Jan 2026 | Structured reasoning | Verifiable PRM for structured output | Bridges RLVR + PRM |
| SWE-TRACE (Han et al.) | Apr 2026 | SWE agents | Rubric PRM + test-time scaling | Optimizes long-horizon agents |
| Verifiable Process Rewards (Yuan et al.) | May 2026 | General agent | RLVR extended to agentic tasks | Environment-grounded |
| Unsupervised PRMs (Gadetsky et al.) | May 2026 | Math | No labeled data needed | Matches supervised PRMs |
| SEVA (Yuan et al.) | Jun 2026 | Fact attribution | Self-evolving verification | ICML 2026 accepted |
| VisCritic (Qian) | Jun 2026 | GUI agents | Visual state comparison as reward | Enables GUI agent RL |
| StainFlow (Hao et al.) | Jun 2026 | GUI agents | Entity-stain tracking | Evidence linking for steps |

---

## Key Insights

### Insight 1: Process > Outcome for Long-Horizon Tasks

The longer the task, the more PRMs matter. For a 5-step math problem, ORM and PRM
performance gap is ~3%. For a 50-step SWE agent task (SWE-TRACE), the gap exceeds 20%.
This is because ORM credit assignment in long horizons is like "guessing which player
won the game by looking at the final score" — technically possible but practically useless
for improvement.

**Implication:** Agent builders working on multi-step tasks (>5 tool calls) should
invest in step-level verification, not just end-to-end evaluation.

### Insight 2: Generative Verification is Eating Classifier-Based Verification

The trend from classifier PRM → generative PRM mirrors the shift from BERT-style
classification to GPT-style generation. Generative PRMs can:
- Explain *why* a step is wrong (debuggable)
- Handle novel task types without retraining (zero-shot)
- Be used as both verifier and reward model simultaneously
- Produce human-readable audit trails

The tradeoff is inference cost: generative PRMs require full LLM forward passes.
But with small models (7B-14B) being sufficient, the cost is manageable.

### Insight 3: Unsupervised PRMs are the Breakthrough of 2026

**Unsupervised PRMs** (Gadetsky et al., May 2026) eliminate the need for labeled step data
by training on agreement/disagreement patterns across multiple sampled trajectories.
This matters because step-level annotation has been the #1 bottleneck for PRM adoption.

Combined with **rubric-based auto-labeling** (SWE-TRACE), the data problem is largely solved.
Expect PRMs to become as ubiquitous as RLHF was in 2023.

### Insight 4: Domain-Specific PRMs Beat General PRMs

VisCritic (GUI), SWE-TRACE (coding), Fin-PRM (finance), StepORLM (operations research) —
each domain builds specialized PRMs that dramatically outperform general-purpose ones.

The reason: "correctness" means different things in different domains:
- Math: logical soundness
- Coding: does the test pass? Is the approach maintainable?
- GUI: did the visual state change as expected?
- Finance: is the reasoning consistent with regulations?

**Implication:** Don't use a general PRM. Build one for your domain, even if small.

### Insight 5: The Verification-Generation Gap is Closing

In 2023, verification was seen as separate from generation — a post-hoc check.
In 2026, verification is increasingly *integrated into generation*:
- Test-time scaling uses PRMs to guide search during generation (not after)
- RLVR uses PRMs as reward signals to improve the generator itself
- SEVA's self-evolving loop makes the verifier and generator co-improve

The end state: agents that can't produce a step without simultaneously verifying it.
This is closer to System 2 thinking — deliberate, verifiable reasoning.

---

## Actionable Next Steps

1. **For agent builders**: Start with simple step-level logging. Record each tool call,
   its inputs, outputs, and whether the overall task succeeded. This data is the raw
   material for training a PRM later.

2. **For evaluation**: Don't just check final answers. Build a step-level evaluation
   harness that scores each intermediate action. Even a simple LLM-as-judge per step
   is better than pure outcome evaluation.

3. **For training**: If you're doing RL or fine-tuning on agent tasks, implement
   token-level credit assignment (a la OREAL). It's a lightweight addition that
   significantly improves sample efficiency.

4. **For production**: Deploy a generative verifier (even a small 7B model) as a
   safety checker between agent steps. If the verifier flags a step as low-confidence,
   trigger human review or re-planning.

5. **For research**: Explore unsupervised PRM training — the frontier is wide open.
   The combination of unsupervised labeling + rubric auto-generation could make
   PRMs accessible to any domain.

---

## References

### Foundational
- Lightman et al. (2023). "Let's Verify Step by Step." arXiv:2305.20050
- Wang et al. (2023). "Math-Shepherd." arXiv:2312.08935

### Generative PRMs
- Zhao et al. (2025). "GenPRM: Scaling Test-Time Compute of Process Reward Models via Generative Reasoning."
- Khalifa et al. (2025). "Process Reward Models That Think." arXiv:2504.xxxxx

### RLVR + PRM
- Lyu et al. (2025). "OREAL: Exploring the Limit of Outcome Reward for Learning Mathematical Reasoning." arXiv:2502.06781
- Yuan et al. (2026). "Verifiable Process Rewards for Agentic Reasoning." arXiv:2505.xxxxx

### Agent-Specific
- Han et al. (2026). "SWE-TRACE: Optimizing Long-Horizon SWE Agents Through Rubric PRMs."
- Yuan et al. (2026). "SEVA: Self-Evolving Verification Agent with Process Reward." ICML 2026.
- Qian (2026). "VisCritic: Visual State Comparison as Process Reward for GUI Agents."
- Hao et al. (2026). "StainFlow: Entity-Stain Tracking for Process Rewards in GUI Agents."
- Venkataramani et al. (2026). "MAS-ProVe: Understanding Process Verification of Multi-Agent Systems."

### Unsupervised & Domain-Specific
- Gadetsky et al. (2026). "Unsupervised Process Reward Models."
- Li et al. (2026). "ToolPRMBench: Evaluating PRMs for Tool-using Agents."
- Zhu et al. (2025). "Fin-PRM: Domain-Specialized PRM for Financial Reasoning."

### Benchmark
- Socratic-PRMBench (Li et al., 2025) — Systematic reasoning patterns for PRM evaluation
- Hard2Verify (Pandit et al., 2025) — Step-level verification for frontier math

---

_Meta: This is exploration #009. Previous: Context Engineering Layer (#008a), Memory Security (#008b)._
