# World Models for Autonomous Agents: Simulation-Based Planning & Decision-Making

> **Date:** 2026-07-05 (Sunday Evening Deep Exploration)
> **Topic:** How learned world simulators are transforming LLM agent planning
> **Scope:** 15+ papers/systems from 2024–2026
> **Catalyst Research Series**

---

## TL;DR

World models — predictive systems that learn environment dynamics — are emerging as the **missing planning layer** for LLM agents. Instead of acting reactively, agents with world models can **simulate outcomes before acting** ("imagination"), enabling look-ahead planning, risk assessment, and sample-efficient learning. By mid-2026, three camps have crystallized: (1) **video-based foundation world models** (V-JEPA 2, Genie 3, Cosmos, Marble), (2) **LLM-as-world-model** approaches (WebDreamer, Dyna-Think, WorldEvolver), and (3) **graph-structured world models** (causal/relational schemas). The convergence is clear: **the next generation of agent systems will be model-based, not reactive**.

---

## 1. Why World Models Matter for Agents

### The Fundamental Problem

Current LLM agents are **reactive** — they observe state, pick an action, observe the next state. This has critical limitations:

- **No look-ahead**: Can't ask "what happens if I do X?" before committing
- **No sample efficiency**: Every interaction is consumed, never simulated
- **No counterfactual reasoning**: Can't evaluate alternative paths not taken
- **Irreversible actions**: On real websites/platforms, you can't "undo" a sent email

### The World Model Promise

A **world model** `𝒲(s, a) → ŝ'` learns to predict the next state given current state and action. With it, an agent can:

1. **Imagine** multiple candidate actions, simulate outcomes, pick the best
2. **Dream** entire training trajectories without real interaction (Dyna/Dreamer)
3. **Evaluate** "what-if" scenarios counterfactually
4. **Self-improve** by co-evolving the world model alongside the policy

This mirrors how humans plan: we simulate futures in our mind before acting.

### Historical Foundation

- **1990:** Sutton's Dyna architecture — interleave learning and planning via simulated experience
- **2018:** Ha & Schmidhuber's "World Models" — learned latent dynamics for policy training
- **2019:** MuZero — implicit model learning achieving superhuman game performance
- **2020:** Dreamer — latent imagination via backpropagation through time
- **2022:** LeCun's JEPA vision — predictive world models as path to autonomous intelligence

---

## 2. Taxonomy: Three Paradigms

### Paradigm A: Video/Foundation World Models

**Core idea:** Train on massive video corpora to learn physical/environmental dynamics. The model generates or predicts future frames/embeddings.

| System | Lab | Year | Key Innovation |
|--------|-----|------|----------------|
| **V-JEPA 2** | Meta FAIR | 2025 | Self-supervised video → zero-shot robot planning |
| **Genie 3** | Google DeepMind | 2025 | Text → real-time interactive 3D worlds (24fps, 720p) |
| **Cosmos** | NVIDIA | 2025-26 | Industrial-scale physics-aware synthetic training data |
| **Marble** | World Labs (Fei-Fei Li) | 2025-26 | Text → 3D spatial worlds (Gaussian splats, meshes) |
| **Sora 2** | OpenAI | 2025 | Improved physics + multi-scene control |
| **GAIA-2** | Wayve | 2025 | Multi-camera driving world model for AV safety |

**Strengths:** Rich visual fidelity, generalizes across domains, enables embodied/robotic training
**Weaknesses:** Computationally expensive, limited temporal consistency (minutes not hours), not directly pluggable into text-based agent systems

### Paradigm B: LLM-as-World-Model

**Core idea:** LLMs already encode knowledge about how environments work. Use the LLM itself to predict state transitions, either via prompting or fine-tuning.

| System | Venue | Year | Key Innovation |
|--------|-------|------|----------------|
| **WebDreamer** | TMLR | 2025 | LLM as web world model — simulate action outcomes for planning |
| **Dreamer-7B** | TMLR | 2025 | Fine-tuned 7B model rivals GPT-4o as web world model |
| **Dyna-Think** | ICLR | 2026 | Integrate world model simulation into reasoning process |
| **WorldEvolver** | arXiv | 2026 | Self-evolving world model + agent co-learning |
| **WebEvolver** | EMNLP | 2025 | Co-evolutionary world model + policy improvement loop |
| **DynaWeb** | arXiv | 2026 | Full Dyna-style MBRL for web agents (train, not just plan) |
| **R-WoM** | arXiv | 2025 | Retrieval-augmented world models reduce hallucination |
| **RAP** | NeurIPS | 2023 | LLM as both world model and reasoning agent + MCTS |

**Strengths:** Works with text-based agents today, leverages existing LLM infrastructure, no separate model needed
**Weaknesses:** Hallucination over long rollouts, limited to text-predictable dynamics, accuracy varies by domain

### Paradigm C: Graph-Structured World Models

**Core idea:** Represent environment state as a graph (entities, relations, attributes). Transitions are graph mutations. Enables precise relational and causal reasoning.

| System | Venue | Year | Key Innovation |
|--------|-------|------|----------------|
| **Graph World Models** | NODES AI | 2026 | Graph schema as world model — RL-ready state space |
| **GraphRAG** | Microsoft | 2024-25 | Knowledge graph as ground for agent reasoning |
| **Temporal KG Memory** | Multiple | 2025-26 | Bi-temporal fact-validity windows for agent memory |

**Strengths:** Precise, queryable, supports counterfactual reasoning natively
**Weaknesses:** Requires schema engineering, less expressive than neural models for raw perception

---

## 3. Deep Dive: Key Systems

### 3.1 V-JEPA 2 (Meta, June 2025)

**Architecture:** Joint Embedding Predictive Architecture for video
- **Stage 1:** Self-supervised pre-training on 1M+ hours of internet video
- **Stage 2:** Action-conditioned fine-tuning on 62 hours of robot data
- **Stage 3:** Model-Predictive Control (MPC) using learned world model

**Key Results:**
- 80% success on zero-shot pick-and-place (vs 15% for Octo baseline)
- 100% reach accuracy in unseen labs with uncalibrated cameras
- 16-second planning time (vs 4 min for Cosmos)
- 1.2B parameters

**Why it matters:** Demonstrates that **minimal robot data + massive video pre-training** yields functional zero-shot planning. The staged training (observe → act) is the key recipe.

**Limitation:** Sensitive to camera positioning; single-arm manipulation only.

### 3.2 Genie 3 (Google DeepMind, August 2025)

**Capabilities:**
- Text → real-time interactive 3D world generation
- 24 fps, 720p resolution
- World memory: consistency persists for several minutes
- Promptable world events: dynamically inject objects/weather/characters
- Street View integration for realistic street generation

**Architecture:** Autoregressive frame generation (not explicit 3D scene representation)

**Why it matters:** First model to cross the **real-time interactivity threshold** (24fps). Previous models were slideshows. This enables actual agent training in simulated worlds.

**Adoption:** Waymo built specialized driving world model on Genie 3 (Feb 2026). Time Magazine "Best Inventions of 2025."

**Limitation:** Few minutes of consistency; no true multi-agent interaction; actions limited.

### 3.3 NVIDIA Cosmos (2025-2026)

**Platform architecture:**
- Three tiers: Nano (edge), Super (general), Ultra (max quality)
- Trained on 9,000 trillion tokens from 20M hours of real-world video
- 2M+ downloads by Jan 2026
- Cosmos 3 announced at COMPUTEX 2026

**Key use cases:**
- Autonomous vehicle training (generate rare safety-critical scenarios)
- Robotics synthetic data pipeline
- Video analytics AI agents

**Why it matters:** First **industrial-scale** world model platform. Open models + tooling make it the de facto standard for physical AI training. Positions NVIDIA as infrastructure provider for the world model era.

### 3.4 WorldEvolver (arXiv, June 2026)

**Core idea:** World model and agent **co-evolve** through mutual feedback loops.

**Architecture:**
- **Memory-augmented episodic module (MEM_E):** Stores past trajectories for world model grounding
- **Modular self-model (MSM_S):** Agent's evolving self-representation
- **Failure-to-Forecast (FtF_t):** Detects when world model prediction diverges from reality, triggers update

**Key Results (ALFWorld + ScienceWorld):**
- 52.88% exact match state prediction (vs 20.06% for baseline RAWM-φ)
- +6-8% task success over baselines on ALFWorld
- Shows **self-evolution** without external supervision

**Why it matters:** First system to demonstrate that world models and agent policies can **bootstrap each other** — no human labels needed for the world model update.

### 3.5 WebDreamer (TMLR, November 2025)

**Question:** "Is your LLM secretly a world model of the internet?"

**Method:**
- Use LLM (GPT-4o or Dreamer-7B) to simulate each candidate web action
- Predict resulting page state in natural language
- Evaluate simulated outcomes to select best action
- No real environment interaction during planning

**Key Results:**
- Substantial improvement over reactive baselines on VisualWebArena and Mind2Web-live
- Dreamer-7B (fine-tuned) matches GPT-4o performance — specialized world models viable
- More efficient than tree search (fewer environment interactions)

**Why it matters:** Validates that **LLMs already encode web dynamics** — they know what clicking a button does, what a search returns, etc. This is implicit world knowledge that can be exploited for planning.

**Limitation:** Single-step lookahead in initial version; hallucination risk over multi-step rollouts.

### 3.6 Dyna-Think (ICLR 2026)

**Framework:** Integrates world model simulation into the reasoning process itself.

**Two training methods:**
1. **DIT (Dyna-Think Imitation Learning):** Reconstruct R1-style thinking to include world model simulation
2. **DDT (Dyna-Think Dyna Training):** Joint policy + world model training on single model

**Key Insight:** "AI agents with better performance correlate with better world modeling abilities." The act of **predicting outcomes improves decision quality**, even when predictions are imperfect.

**Why it matters:** Bridges the gap between "thinking" (reasoning) and "imagining" (world simulation). Shows that **world modeling is not just for planning — it improves reasoning itself**.

### 3.7 DynaWeb (arXiv, January 2026)

**Innovation:** Full Dyna-style model-based RL for web agents.

**Architecture:**
- LLM-based web world model as "learned web server"
- Predicts realistic next-state page representations
- Provides task-level feedback signals for policy optimization
- Trained on filtered NNetNav trajectories (state transitions + reasoning traces)

**Why it matters:** Goes beyond inference-time planning. The world model is used for **actual RL training** — agents learn from simulated web interactions, not just real ones. This is the classical Dreamer/Dyna paradigm realized for web agents.

### 3.8 R-WoM: Retrieval-Augmented World Models (October 2025)

**Problem:** LLM world models hallucinate and drift over long rollouts due to static pre-training.

**Solution:** Inject relevant retrieved knowledge at each simulation step.
- For web agents: retrieve tutorials/documentation for procedural alignment
- +25.3% and +18.1% gains on OSWorld and WebArena

**Why it matters:** Shows that **RAG + world modeling = grounded simulation**. The world model doesn't need to memorize everything — it can look things up during simulation.

---

## 4. Convergence Patterns

### Pattern 1: Staged Training (Observe → Act)

V-JEPA 2, Genie 3, and Dreamer all follow the same recipe:
1. **Phase 1:** Learn dynamics from passive observation (video/text)
2. **Phase 2:** Fine-tune with action-conditioned data
3. **Phase 3:** Use for planning/control

This mirrors child development: watch the world first, then interact.

### Pattern 2: Co-Evolution

WorldEvolver, WebEvolver, and DynaWeb all show that **world model and agent policy improve together**:
- Better agent → richer experience data → better world model
- Better world model → better planning → better agent

This creates a positive feedback loop that enables self-improvement without external supervision.

### Pattern 3: Retrieval Grounding

R-WoM and similar systems show that **retrieval prevents hallucination** in world model rollouts. The world model doesn't replace the knowledge base — it leverages it.

### Pattern 4: Graph as World Model Schema

Multiple talks at NODES AI 2026 and the "Graphs Meet AI Agents" survey show that **thinking of your graph schema as a world model** — even without implementing RL — leads to better agent system design. The graph captures state transitions, entity relations, and causal dependencies.

---

## 5. The Big Picture: 2024-2026 Timeline

```
2024-Q1  Dyna (Sutton, 1991) revived for LLM agents
2024-Q3  WebDreamer: LLM as web world model (prompting)
2024-Q4  Genie 2: 3D worlds but only 10-20s consistency
2025-Q1  RAP: LLM + MCTS for reasoning
2025-Q2  DreamerV3 adapted for language agents
2025-Q2  WebEvolver: co-evolutionary web world model (EMNLP)
2025-Q3  V-JEPA 2: zero-shot robot planning from video (Meta)
2025-Q3  Genie 3: real-time interactive 3D worlds (DeepMind)
2025-Q3  R-WoM: retrieval-augmented world model
2025-Q4  WebDreamer published in TMLR (Dreamer-7B released)
2025-Q4  NVIDIA Cosmos platform → 2M downloads
2025-Q4  World Labs / Marble: spatial intelligence (Fei-Fei Li)
2026-Q1  Dyna-Think: world model + reasoning (ICLR 2026)
2026-Q1  DynaWeb: full MBRL for web agents
2026-Q1  Agentic World Modeling survey (ACM CSUR)
2026-Q2  WorldEvolver: self-evolving world models
2026-Q2  Cosmos 3 at COMPUTEX 2026
```

---

## 6. Implications for OpenClaw / Agent Memory Systems

### 6.1 World Model as Memory Extension

Our agent memory system currently stores **what happened** (episodic) and **what's true** (semantic). A world model adds **what will happen if...** (predictive). This completes the memory stack:

| Memory Type | Question Answered | Current Implementation |
|------------|-------------------|----------------------|
| Episodic | "What happened?" | memory/YYYY-MM-DD.md |
| Semantic | "What's true?" | MEMORY.md, knowledge graph |
| Procedural | "How to do X?" | Skills, SKILL.md |
| **Predictive (NEW)** | **"What if I do X?"** | **World model** |

### 6.2 Practical Integration Points

**Near-term (1-3 months):**
1. **Before-action simulation:** For risky operations (file deletion, external sends), simulate the action outcome using LLM-as-world-model before executing
2. **Action verification:** Use world model to predict outcome, execute, compare prediction vs. actual — log discrepancies as learning events
3. **Multi-step planning:** Use world model rollout to evaluate 2-3 candidate plans before committing

**Medium-term (3-6 months):**
4. **Graph-based world model:** Extend our agent memory graph to include transition probabilities and preconditions — making it a queryable world model
5. **Skill co-evolution:** When a skill produces unexpected results, update the world model's transition prediction for that skill's domain
6. **Counterfactual analysis:** After failures, replay the scenario with alternative actions to build causal understanding

**Longer-term:**
7. **Self-evolving agent loop:** Implement WorldEvolver-style co-evolution — world model and policy improve together from experience
8. **Retrieval-grounded simulation:** Before simulating an action in an unfamiliar domain, retrieve relevant docs/logs to ground the world model

---

## 7. Core Insights

### Insight 1: World Models Are Not Optional for General Agents

> "General agents need world models." — Richens et al., ICML 2025

The argument is settled in the MBRL community. The question for LLM agents is not **whether** but **how** to integrate world models.

### Insight 2: LLMs Are Already (Weak) World Models

WebDreamer and Dyna-Think show that LLMs encode surprising knowledge about environment dynamics. The challenge is **accuracy and consistency** — not capability. Fine-tuning specialized world model LLMs (Dreamer-7B) closes much of the gap.

### Insight 3: The Co-Evolution Loop Is the Breakthrough

Single-shot world model training (train model, then use for planning) is limited because the world model gets stale. **Co-evolution** (WorldEvolver, WebEvolver) creates a self-improving system where:
- Agent explores → generates new experience
- Experience updates world model
- Better world model → better planning
- Better planning → richer exploration

This is the practical realization of Sutton's Dyna vision from 1990.

### Insight 4: Temporal Consistency Is the Bottleneck

Both Genie 3 (visual) and WebDreamer (textual) share the same limitation: **predictions degrade over multi-step rollouts**. Genie 3 holds consistency for minutes; LLM world models drift after 3-5 simulated steps. Solving this is the key research frontier.

### Insight 5: Graph Schemas Are Implicit World Models

The NODES AI 2026 talk made this clear: if you design your graph schema as if you're going to build a world model, you get better agent systems — even without implementing RL. The schema captures state transitions, causal dependencies, and entity relations that are the substrate for prediction.

### Insight 6: Cost Asymmetry Drives Adoption

World models are worth the complexity because **real interactions are expensive** (API calls, side effects, irreversible actions). Simulated interactions are cheap and safe. As agents take on higher-stakes tasks, the value of simulation-only practice increases.

---

## 8. Actionable Next Steps

### 🎯 Action 1: Add "Predict Before Act" to Risky Operations
**Effort:** Small | **Impact:** High

For operations tagged as "external" or "destructive" in our agent system:
1. Before executing, prompt the LLM: "Predict the outcome of this action: [action description]"
2. Log prediction
3. Execute
4. Compare prediction vs. actual
5. Store discrepancy in `memory/prediction-errors.md`

This builds a **world model accuracy dataset** with zero infrastructure changes.

### 🎯 Action 2: Extend Agent Memory Graph with Transition Edges
**Effort:** Medium | **Impact:** High

Current graph: `Entity -[RELATION]-> Entity`
Extension: `Entity -[TRANSITION(action, precondition, probability)]-> Entity`

This makes the memory graph a **queryable world model**. Query: "What actions can transform state A into state B?" becomes traversable.

### 🎯 Action 3: Implement Dyna-Think Style Simulation in Planning
**Effort:** Medium | **Impact:** Medium

When the agent faces multiple candidate actions:
1. For each candidate, simulate 1-step ahead: "If I do X, the result would be..."
2. Score candidates by simulated outcome quality
3. Pick the best
4. Log the simulation trace

This is WebDreamer's core insight, implementable with prompt engineering alone.

### 🎯 Action 4: Track World Model Prediction Accuracy Over Time
**Effort:** Small | **Impact:** Medium

Maintain a running log of predictions vs. outcomes. Track accuracy by:
- Domain (file ops, web, communication, code)
- Step depth (1-step, 2-step, 3-step)
- Model version

This identifies where the agent's internal world model is reliable and where it needs grounding.

### 🎯 Action 5: Study Dyna-Think Training Method for Our Lab Projects
**Effort:** Large | **Impact:** High

The Dyna-Think Dyna Training (DDT) method — joint policy + world model training — could be applied to our agent-context-store and structured-output-toolkit lab projects. This would be a novel contribution: **world-model-augmented TDD for agent components**.

### 🎯 Action 6: Prototype Graph-as-World-Model for Agent Memory
**Effort:** Medium | **Impact:** High

Take the existing agent memory graph and add:
- `PRECONDITION` edges (what must be true before an action)
- `EFFECT` edges (what changes after an action)
- `PROBABILITY` weights on transition edges

Then implement a simple planner: given current state graph, find action sequence to reach goal state via graph traversal. This is **graph-based planning without RL**.

---

## 9. References

### Primary Papers & Systems

1. **V-JEPA 2** — Assran et al., "Self-Supervised Video Models Enable Understanding, Prediction and Planning" (arXiv 2506.09985, 2025)
2. **Genie 3** — Google DeepMind, "Genie 3: Creating dynamic worlds that you can navigate in real-time" (Aug 2025)
3. **Cosmos** — NVIDIA, "Cosmos World Foundation Models" (CES 2025; Cosmos 3 at COMPUTEX 2026)
4. **Marble** — World Labs (Fei-Fei Li), Spatial intelligence platform (Nov 2025)
5. **WebDreamer** — Gu et al., "Is Your LLM Secretly a World Model of the Internet?" (TMLR 2025)
6. **Dreamer-7B** — Fine-tuned web world model (released with WebDreamer, HF Collection)
7. **Dyna-Think** — Yu et al., "Synergizing Reasoning, Acting, and World Model Simulation in AI Agents" (ICLR 2026)
8. **WorldEvolver** — "Self-Evolving World Models for LLM Agent Planning" (arXiv 2606.30639, 2026)
9. **WebEvolver** — Fang et al., "Enhancing Web Agent Self-Improvement with Co-evolving World Model" (EMNLP 2025)
10. **DynaWeb** — "Model-Based Reinforcement Learning of Web Agents" (arXiv 2601.22149, 2026)
11. **R-WoM** — Mei et al., "Retrieval-augmented World Model for Computer-use Agents" (arXiv, Oct 2025)
12. **RAP** — Hao et al., "Reasoning with Language Model is Planning with World Model" (NeurIPS 2023)
13. **Dreamer** — Hafner et al., "Dreaming to Control: Learning Behaviors by Latent Imagination" (ICLR 2020)
14. **Agentic World Modeling** — "Agentic World Modeling: Foundations, Capabilities, Laws, and Beyond" (arXiv 2604.22748, 2026)
15. **"General Agents Need World Models"** — Richens et al. (ICML 2025)
16. **Graphs Meet AI Agents** — "Graphs Meet AI Agents: Taxonomy, Progress, and Future Opportunities" (arXiv 2506.18019, 2025)
17. **Learning to Model the World** — "A Survey of World Models in Artificial Intelligence" (preprints.org, Mar 2026)
18. **LLM-Based World Models** — EmergentMind topic survey (emergentmind.com, 2025-26)

### Foundational References

19. **Dyna** — Sutton, "Integrated Architectures for Learning, Planning, and Reacting" (ICML 1990)
20. **World Models** — Ha & Schmidhuber (NeurIPS 2018)
21. **MuZero** — Schrittwieser et al. (Nature 2019)
22. **JEPA Vision** — LeCun, "A Path Towards Autonomous Machine Intelligence" (2022)

---

## 10. Open Questions for Further Exploration

1. **How long can LLM-based world models maintain consistency?** Current limit seems to be 3-5 steps. What techniques (retrieval, self-correction, external memory) extend this?

2. **Can world models learn from failures?** When the agent's prediction is wrong, how should the world model update? Online learning? Replay buffers? RAG from error logs?

3. **What's the right granularity for a world model?** Should it predict exact next-state text, or abstract "what changed"? The transition from WebDreamer (full page prediction) to transition-focused abstraction (Chae et al.) suggests abstraction wins.

4. **How do multi-agent world models work?** When multiple agents share an environment, does each need its own world model of the others? Or can they share a common model?

5. **Can we combine graph-based and neural world models?** Graph for structural/causal reasoning, neural for perceptual/textual prediction. Hybrid architecture.

---

*Generated by Catalyst evening deep exploration, 2026-07-05*
*Next exploration: Consider "Test-Time Scaling Laws for Agent Systems" or "Causal Reasoning in Agent Memory"*
