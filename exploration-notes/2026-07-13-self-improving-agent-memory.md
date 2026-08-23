# Self-Improving Agent Memory: From Passive Storage to Active Curation

**Date:** 2026-07-13
**Status:** Complete
**Sources:** 12+ papers, systems, and industry reports

---

## Overview

Agent memory is undergoing a paradigm shift: from externally-managed storage pipelines to self-improving systems where the agent itself decides what to remember, what to forget, and how to organize knowledge. This note surveys the key papers, systems, and industry developments driving this shift in 2025-2026.

---

## Core Concepts (5)

### 1. Write-Manage-Read Loop (Du, 2026 — arXiv:2603.07670)
The foundational formalization of agent memory as a three-phase cycle:
- **Write:** What gets stored, with what priority, after what filtering
- **Manage:** Summarization, deduplication, contradiction resolution, forgetting
- **Read:** Retrieval strategies (semantic, keyword, entity, temporal)

Key insight: `𝒰` (the update function) is NOT simple append. A well-designed system summarizes, deduplicates, scores priority, resolves contradictions, and deletes when appropriate. The agent's decisions determine what gets written, and what is written shapes future decisions — this recursive dependence makes memory both powerful and brittle.

### 2. Memory as Tool Calls — AgeMem (Yu et al., 2026 — arXiv:2601.01885, ACL 2026)
AgeMem exposes 6 memory operations as tools the LLM can call:
- Long-term: `add`, `update`, `delete`
- Short-term: `retrieve`, `summary`, `filter`

The policy is trained via 3-stage progressive RL (GRPO):
1. Long-term construction (learn what's worth remembering)
2. Short-term control under distractors (learn when to trust LTM over noisy context)
3. Integrated reasoning (coordinate storage + retrieval + task-solving)

**Headline result:** 4B model with AgeMem beats 7B model with Mem0/A-Mem baselines. Learned memory buys more than 3B extra parameters.

### 3. Trajectory-Informed Memory Generation (Fang et al., 2026 — arXiv:2603.10600, IBM)
Four-component framework for extracting actionable learnings from execution traces:
1. **Trajectory Intelligence Extractor** — semantic analysis of reasoning patterns
2. **Decision Attribution Analyzer** — identifies immediate/proximate/root causes
3. **Contextual Learning Generator** — produces 3 tip types: strategy, recovery, optimization
4. **Adaptive Memory Retrieval** — multi-dimensional similarity matching

**Key result:** +14.3pp on AppWorld scenario completion, +28.5pp (149% relative) on complex tasks. The insight: not all learning comes from failures — inefficient successes and successful recoveries are equally valuable.

### 4. Dreaming — Background Memory Consolidation
Two major implementations:
- **OpenAI Dreaming (V3, June 2026):** Background process synthesizes memories across conversations. Solves staleness (auto-updates "going to Singapore" → "went to Singapore"), preference following, and temporal reasoning. 5x compute reduction enabled Free tier rollout.
- **Anthropic Claude Code Dreaming (May 2026):** Reviews past sessions to find patterns and self-improve. Part of a 7-layer memory system inside Claude Code's harness: token pruning → context compression → session memory → project memory → dreaming consolidation → cross-project knowledge → meta-learning.

### 5. Continual Learning vs In-Context Learning (a16z, April 2026)
The fundamental tension:
- **ICL (In-Context Learning):** Transient, no weight updates, depends on context engineering
- **Continual Learning:** Updates model parameters post-deployment, compresses experience into weights

a16z argues: "ICL is transient. Real learning requires compression. Until we let models compress continuously, we may be stuck in Memento's perpetual present."

State Space Models (SSMs) offer a middle ground — external memory layers with better scaling than attention for long contexts, potentially extending agent coherence from ~20 steps to ~20,000.

---

## Key Insights (5)

### Insight 1: Memory is becoming a learned subsystem, not fixed plumbing
The trajectory mirrors NLP's evolution: rules → statistical → neural → end-to-end learned. Memory is following the same path. AgeMem's RL-trained policy and trajectory-informed learning systems signal that hand-coded write/retrieve heuristics are the past.

### Insight 2: Smaller models with better memory beat larger models without
AgeMem's 4B model beating 7B baselines is the clearest evidence yet that memory architecture can rival or exceed model scaling. MemoryArena showed swapping active memory for long-context-only dropped task completion from 80%+ to ~45%. The gap between "has memory" and "doesn't have memory" is larger than the gap between different LLM backbones.

### Insight 3: Forgetting is the hardest unsolved problem
Every system struggles with what NOT to remember. Survey identifies "learned forgetting" as a top open challenge. Claude Code's Auto Dream tackles memory decay — after 20+ sessions, notes become contradictory messes. The industry has solved writing and is decent at reading, but intelligent forgetting remains the frontier.

### Insight 4: Trajectory analysis > raw conversation logging
IBM's framework shows that understanding WHY an agent made a decision (not just WHAT it did) produces dramatically better learnings. Three categories — strategy tips, recovery tips, optimization tips — capture different value from different outcome types. This is qualitatively different from Mem0's "store facts from conversations" approach.

### Insight 5: The benchmark wars are heating up
Three benchmarks now define evaluation:
- **LoCoMo** (1,540 questions, 4 categories) — the standard
- **LongMemEval** (500 questions, 6 categories) — broader scenarios
- **BEAM** (1M/10M token scale) — production-relevant

Mem0 leads production systems with 92.5 LoCoMo / 94.4 LongMemEval at ~6,900 tokens/query. But Bloo-Mind AI's analysis warns: "Almost nothing you've read about agent memory scores is true" — many benchmarks game easily.

---

## Systems Landscape

| System | Type | Key Innovation |
|--------|------|----------------|
| **AgeMem** (Alibaba) | Research | RL-trained memory as tool calls |
| **Mem0** | Production | Multi-signal retrieval, 21 framework integrations |
| **Zep/Graphiti** | Production | Real-time temporal knowledge graphs |
| **Cognee** | Production | Hybrid graph + vector knowledge graph |
| **TeleMem** (TeleAI) | Research/Prod | API-compatible Mem0 drop-in |
| **Trajectory Memory** (IBM) | Research | Causal attribution from execution traces |
| **OpenAI Dreaming** | Production | Background synthesis across conversations |
| **Claude Code Dreaming** | Production | 7-layer harness with Auto Dream decay fix |
| **Perplexity Brain** | Production | Self-improving memory for search agents |
| **Cloudflare Agent Memory** | Production | Managed persistent memory service |

---

## Benchmarks Summary

| Benchmark | Scale | Categories | Key Test |
|-----------|-------|------------|----------|
| LoCoMo | 1,540 Q | single-hop, multi-hop, open-domain, temporal | Standard recall |
| LongMemEval | 500 Q | 6 categories incl. knowledge update | Temporal reasoning |
| MemoryAgentBench | — | Memory + action coupling | Agentic memory |
| MemoryArena | — | Multi-session interdependent | Real-world transfer |
| BEAM | 1M/10M tokens | 10 categories | Production scale |
| MemBench | — | Richer evaluation dimensions | Learned memory control |

---

## Actionable Next Steps

1. **Expose memory operations as tools in your agent today** — even without RL training, giving the model `remember_fact(key, value)` and `forget_fact(key)` as tool calls improves long-task performance
2. **Log memory traces** — when debugging agent failures, the retrieval log is usually where the smoking gun is
3. **Implement trajectory analysis** — don't just store conversation facts; analyze execution patterns for strategy/recovery/optimization tips
4. **Build forgetting into the write path** — write-time entropy filtering (is this worth storing?) is cheaper than read-time noise reduction
5. **Track the AgeMem → production pipeline** — the RL training code isn't released yet, but the "memory as action" paradigm is portable to prompt engineering now
6. **Evaluate against BEAM, not just LoCoMo** — production scale (1M+ tokens) reveals failure modes invisible at benchmark scale
7. **Watch the SSM + continual learning space** — the a16z thesis suggests the next breakthrough may come from models that update weights post-deployment

---

## References

1. Du, P. (2026). "Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers." arXiv:2603.07670
2. Yu, Y. et al. (2026). "Agentic Memory: Learning Unified Long-Term and Short-Term Memory for LLM Agents." ACL 2026. arXiv:2601.01885
3. Fang, G. et al. (2026). "Trajectory-Informed Memory Generation for Self-Improving Agent Systems." arXiv:2603.10600
4. OpenAI (2026). "Dreaming: Better memory for a more helpful ChatGPT."
5. Anthropic (2026). "New in Claude Managed Agents: dreaming, outcomes, and multiagent orchestration."
6. Mem0 (2026). "AI Agent Memory 2026: Progress Benchmark Report."
7. a16z (2026). "Why We Need Continual Learning."
8. TeleAI-UAGI. "Awesome-Agent-Memory" (curated repository).
9. Bloo-Mind AI (2026). "The Benchmark Theatre: Why Almost Nothing You've Read About Agent Memory Scores Is True."
10. Park, J. et al. (2023). "Generative Agents: Interactive Simulacra of Human Behavior."
11. Wang, G. et al. (2023). "Voyager: An Open-Ended Embodied Agent with LLMs."
12. Shinn, N. et al. (2023). "Reflexion: Language Agents with Verbal Reinforcement Learning."
