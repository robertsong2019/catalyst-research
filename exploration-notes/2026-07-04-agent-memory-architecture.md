# AI Agent Memory Architecture: State of the Art (2026)

> **Exploration Date:** 2026-07-04
> **Scope:** 15+ papers, systems, and frameworks on LLM agent memory (Jan 2025 – Jul 2026)
> **Catalyst relevance:** Directly applicable to our own memory architecture (MEMORY.md + daily notes + semantic search)

---

## Executive Summary

Agent memory has crystallised into **the** differentiation layer of the 2026 AI stack. Reasoning is commoditising (frontier models converge), communication is standardising (MCP, A2A), but **no one truly leads agent memory yet**. This note maps the field across five architectural paradigms, three benchmarks, and the emerging security/operations frontier.

**Key takeaway:** The field has moved from "give the agent a vector DB" to a multi-dimensional engineering discipline with real trade-offs: vector vs. graph, passive vs. active extraction, frozen vs. self-editing, temporal staleness as an unsolved first-class problem.

---

## 1. The Five Architectural Paradigms

### 1.1 OS-Inspired Hierarchical Memory (Letta / MemGPT)

**Origin:** Packer et al., "MemGPT: Towards LLMs as Operating Systems" (Oct 2023)
**Evolution through 2026:** Letta has evolved from a research project into a full agent runtime/platform.

**Core idea:** Treat LLM context like RAM — the agent manages its own memory hierarchy via "system calls":
- **Core memory** (in-context): persona, human, task blocks — always visible to the LLM
- **Recall memory**: full conversation history, persisted in DB, searchable
- **Archival memory**: long-term facts, vector-indexed, retrieved on demand

**2026 updates:**
- **Focus** (Verma, Jan 2026): Autonomous context consolidation — agent decides when to summarise vs. prune, using a scoring function `s(c) = α·relevance + β·novelty − γ·age`. Achieves **22.7% average token reduction** (up to 57% in some instances) without accuracy loss.
- **Context Repositories** (Feb 2026): Git-based memory versioning — programmatic context management with branch/merge semantics.
- **Memory Models** (Jun 2026): Memory-native RL — training agents to learn *through* memory operations.
- **Sleep-time Compute** (Apr 2025): Agents reason about context during idle time, not just at inference.

**Strengths:** Genuinely agentic — the LLM itself decides what to remember. Deep integration via Agent Development Environment (ADE) for observability.
**Weaknesses:** Heavy framework lock-in (must run inside Letta). "Self-editing" reliability depends on model reasoning quality — if it fails to call `memory_insert`, the memory is lost forever. No temporal reasoning. No published LongMemEval score.

### 1.2 Zettelkasten / Note-Linking Memory (A-MEM)

**Origin:** Xu et al., "A-MEM: Agentic Memory for LLM Agents" (Feb 2025, NeurIPS 2025)

**Core idea:** Inspired by the Zettelkasten method — each memory is a structured "note" with keywords, tags, and contextual links to other notes. Memories form a **dynamic network** that evolves as new information arrives.

**Architecture:**
1. **Memory creation:** New interaction → LLM generates note with content + keywords + tags
2. **Linking:** New note is embedded, compared to existing notes, and linked to semantically related ones
3. **Evolution:** Links strengthen/weaken over time; notes can be reorganised
4. **Retrieval:** Combined vector similarity + graph traversal

**Key result:** Superior performance across six foundation models vs. SOTA baselines.
**GitHub:** `agiresearch/a-mem` — pip-installable, supports ChromaDB, multiple LLM backends.

**Why it matters:** The linking/evolution mechanism is closer to human associative memory than flat vector stores. Each memory has context (other memories it relates to), not just standalone content.

### 1.3 Production Memory Platform (Mem0)

**Origin:** Chhikara et al., "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory" (ECAI 2025)
**2026 evolution:** Token-efficient algorithm (Apr 2026), entity linking, multi-signal retrieval.

**Architecture:**
- **Extraction:** Single-pass ADD-only extraction (no UPDATE/DELETE overhead)
- **Storage:** Vector DB (Qdrant) + entity collection (parallel to main memory store)
- **Retrieval:** Three signals fused — semantic similarity + BM25 keyword + entity matching
- **Scopes:** `user_id`, `agent_id`, `session_id` — every memory write is scoped

**Benchmark progression:**

| Benchmark | 2025 Score | 2026 Score | Tokens/Query |
|-----------|-----------|-----------|-------------|
| LoCoMo | 71.4 | **92.5** | 6,956 |
| LongMemEval | 67.8 | **94.4** (later corrected: 93.4) | 6,787 |
| BEAM-1M | — | 64.1 | 6,719 |
| BEAM-10M | — | 48.6 | 6,914 |

vs. full-context baseline: ~26,000 tokens/conversation, lower accuracy.

**Biggest gains:** Temporal queries (+29.6 points) and multi-hop reasoning (+23.1 points).

**Production reality check (RankSquire analysis):**
- Benchmark score 91.6 → real-world effective accuracy **49.0% after 30 days** at 38% staleness rate
- Formula: `Production Accuracy ≈ Benchmark − 0.22 × Staleness Rate − 0.15 × log₁₀(Entities)`
- TCO crossover: self-hosted (Qdrant + PostgreSQL) beats Mem0 Pro at **7,500 tasks/day**

### 1.4 Graph-Native Memory

**Key systems:** Zep/Graphiti, Cognee, MAGMA, AriGraph, MEMORIESDB

**Taxonomy** (Yang et al., "Graph-based Agent Memory: Taxonomy, Techniques, and Applications," Feb 2026):
- Graph memory elevates information from passive "log" to active "knowledge graph" modelling lived experience
- Records not just "what happened" but **"how things are connected"**
- Enables compositional queries, multi-hop reasoning, entity resolution, causal chains

**Key 2026 graph systems:**
- **MAGMA** (Jan 2026): Multi-graph agentic memory — separate graphs for different memory types
- **LiCoMemory / CogniGraph** (Nov 2025): Hierarchical graph, +9% LoCoMo, +26.6% multi-session subtask accuracy
- **Cognee:** Graph-native — builds KG directly from raw data as primary storage, not a secondary layer
- **Zep / Graphiti:** Temporal knowledge graph — purpose-built for "how facts change over time"

**Graph vs. Vector — the 2026 consensus:**
- Vector: retrieves semantically similar facts, treats each memory independently
- Graph: preserves how information connects across time, models entity relationships
- **Neither is sufficient alone.** The production pattern is hybrid: vector + graph + temporal.

**Multi-agent graph memory (Neo4j Nodes 2026):**
- Shared graph as "institutional memory" for multi-agent systems
- Agents hydrate from a graph richer than what previous agents started from
- Key failure mode: **schema sprawl** — agents invent new labels/relationship types if unconstrained
- Fix: enforce schema at write-time; fail loudly on unrecognised labels

### 1.5 Episodic Memory + Reinforcement Learning (MemRL)

**Origin:** Zhang et al., "MemRL: Self-Evolving Agents via Runtime Reinforcement Learning on Episodic Memory" (Jan 2026, ICLR 2026 Workshop)

**Core idea:** Treat memory retrieval as a **value-based decision process** — not "what's most similar?" but "what was actually useful in the past?"

**Architecture:**
1. **Memory structure:** Intent–Experience–Utility triplets
2. **Two-phase retrieval:**
   - Phase A (semantic recall): Coarse filter by semantic relevance → small candidate pool
   - Phase B (value-aware selection): RL critic ranks candidates by learned Q-values (utility)
3. **No weight updates:** LLM backbone stays frozen; only the retrieval policy learns
4. **Stability-plasticity solution:** Decouples stable LLM from plastic external memory

**Key insight:** Memory usefulness ≠ memory similarity. A memory that's semantically distant but previously led to success is more valuable than a similar but useless one.

**SimpleMem** (Liu et al., Jan 2026, ICLR 2026 Workshop):
- Efficient lifelong memory via adaptive pruning + retrieval
- Combines semantic, lexical, and metadata signals
- Dynamically adjusts retrieval depth based on query complexity
- Outperforms Mem0 on multiple benchmarks with fewer tokens (730 vs 988–1020)

---

## 2. The Benchmark Landscape

| Benchmark | Questions | Focus | Key Finding |
|-----------|----------|-------|-------------|
| **LoCoMo** | 1,540 | Single-hop, multi-hop, temporal, open-domain | The standard, but **6.4% of answer key is wrong** (Penfield audit, Apr 2026); LLM judge accepts up to 63% of intentionally wrong answers |
| **LongMemEval** | 500 | Knowledge updates, multi-session recall, abstention | Better reflects enterprise use cases via temporal reasoning; but each corpus fits in modern context windows → more of a context window test than a memory test |
| **BEAM** | 700 (1M) / 200 (10M) | Million+ token scale | The real stress test — even Mem0 drops to 48.6% at 10M scale |

**Critical gap:** No benchmark currently tests memory **after time has passed and facts have changed** — all test recall of static conversations. The Supersede benchmark (arXiv, Jun 2026) begins to address this with time-indexed supersession signals.

---

## 3. Memory Compounding: The Frontier Problem

### 3.1 The Compounding Gap

Better retrieval gets agents better evidence. But agents with better evidence still:
- Repeat the same search patterns
- Make the same mistakes
- Fail to improve strategies across tasks

This is the **memory compounding problem** — memory should make agents better over time, not just more informed.

### 3.2 LRAT: Learning to Retrieve from Agent Trajectories (SIGIR 2026)

**Key finding:** Production logs are a training asset most teams aren't using.
- Trained retriever on 26K agent trajectories across four retrieval systems
- Three behavioural signals distinguish useful from irrelevant documents: search-to-browse transitions, post-browse reasoning depth, browse-vs-skip patterns
- **Retrievers improve 15-19% even when trained on FAILED agent runs**
- Agent task success: +20.9% in-domain, +19.2% out-of-domain
- Up to 30% fewer interaction steps

### 3.3 MIA: Compounding Memory Architecture

- 7B model using MIA framework **outperformed 32B baseline by 18%**
- Gains hold on frontier models
- Memory isn't just retrieved — it's consolidated into actionable strategies

---

## 4. Security & Operations Frontier

### 4.1 Memory Poisoning

- **90%+ of tested agents vulnerable** to memory poisoning attacks
- **100% relapse rate** when teams try to fix it by correcting the agent in conversation
- Once poisoned, memory becomes a persistent attack surface — the malicious instruction is part of trusted state
- Microsoft reports growing real-world "AI Recommendation Poisoning" pattern
- MINJA-style attacks: 95%+ injection success, 70% attack success under idealised conditions

### 4.2 Temporal Staleness

The unsolved problem:
- Facts have a **valid_from / valid_to** lifecycle
- High-relevance memories become "confidently wrong" when underlying facts change
- Decay handles low-relevance memories; staleness in **high-relevance** memories is open
- OpenAI's own memory update system: only 75.1% success on time-sensitive updates (up from 9.4% in 2024)
- Gemini's profile updates can lag by days

### 4.3 Regulatory Pressure

- **EU AI Act** (fully applicable Aug 2, 2026): Article 15(4) addresses feedback loops; Article 72 mandates post-market monitoring
- For runtime-learning agents: must monitor what they learn, detect drift, prove compliance
- **GDPR Article 17**: right to erasure requires `valid_from / valid_to` temporal schema

---

## 5. Framework Landscape (2026 Snapshot)

| Framework | Architecture | Best For | LoCoMo | Open Source |
|-----------|-------------|----------|--------|-------------|
| **Mem0** | Vector + Entity Linking | Drop-in personalisation | 92.5 | ✅ Apache 2.0 |
| **Letta/MemGPT** | OS-inspired hierarchy | Long-running stateful agents | N/P | ✅ Apache 2.0 |
| **A-MEM** | Zettelkasten network | Research, structured note-linking | SOTA on 6 models | ✅ |
| **Zep/Graphiti** | Temporal KG | Time-evolving facts | — | Core only |
| **Cognee** | Graph-native KG | Document-heavy reasoning | — | ✅ Apache 2.0 |
| **Hindsight** | Multi-strategy retrieval | Framework-agnostic | — | — |
| **LangMem** | LangGraph native | LangChain ecosystem | — | ✅ MIT |
| **MemMachine** | Episodic + Profile | Production episodic | 0.8487 | — |

**Hindsight** notably: 94.6% on LongMemEval via four parallel retrieval strategies (semantic + BM25 + graph + temporal) with cross-encoder reranking.

---

## 6. Core Insights for Catalyst's Own Architecture

### What We're Doing Right
- **File-based memory** (MEMORY.md + daily notes) is conceptually aligned with episodic memory research
- **Scoping** (personal vs. shared context) matches the multi-scope memory pattern
- **Daily notes as episodic, MEMORY.md as semantic** mirrors the episodic/semantic distinction in the literature

### What We're Missing
1. **No temporal validity tracking** — we store facts without `valid_from/valid_to`. Stale facts persist indefinitely. We need temporal metadata on key facts.
2. **No entity linking** — our memories are flat text, not an entity graph. When we learn "罗嵩 changed jobs," we can't automatically find and update all related memories.
3. **No utility-weighted retrieval** — semantic similarity is our only signal. MemRL shows that "was this useful before?" is a stronger signal than "is this textually similar?"
4. **No consolidation pipeline** — we manually review daily notes, but there's no automated extraction/consolidation cycle. Memory doesn't compound.
5. **No staleness detection** — we never expire or validate old memories. The system grows monotonically.

### Quick Wins (implementable now)
1. **Add temporal tags to MEMORY.md entries** — ` [verified: 2026-07-04]` suffix
2. **Entity-first writing** — when recording facts, lead with entity names for better future search
3. **Error-to-memory pipeline** — when we make mistakes (error-patterns.md), auto-extract the lesson into MEMORY.md
4. **Heartbeat consolidation** — use heartbeats to review recent daily notes and extract patterns, not just check inbox

### Medium-term (requires tooling)
1. **Build entity extraction into memory writes** — parse MEMORY.md entries for entities, store in a sidecar JSON
2. **Multi-signal retrieval** — add BM25 keyword matching alongside semantic search in `memory_search`
3. **Memory decay scoring** — add recency-weighted scoring to retrieval results
4. **Memory compounding via trajectory mining** — log agent trajectories (what tools called, what worked), train better retrieval

### Moonshot
- **MemRL-style utility learning** — track which memories we retrieve and whether the outcome was successful. Over time, build Q-values for memory utility.
- **Graph layer** — build a lightweight entity-relationship graph from MEMORY.md entries. Not Neo4j; just a JSON adjacency list that enriches retrieval.
- **Sleep-time consolidation** — use a cron job during off-hours to: (1) review recent memories, (2) detect contradictions, (3) consolidate patterns, (4) flag staleness.

---

## 7. Papers & Systems Referenced

1. **MemGPT** — Packer et al., Oct 2023. OS-inspired memory hierarchy.
2. **A-MEM** — Xu et al., NeurIPS 2025. Zettelkasten-style agentic memory with note-linking.
3. **Mem0** — Chhikara et al., ECAI 2025. Production-ready scalable long-term memory.
4. **Mem0 2026 Algorithm** — Yadav et al., Apr 2026. Token-efficient single-pass extraction + multi-signal retrieval.
5. **MemRL** — Zhang et al., Jan 2026, ICLR 2026 Workshop. Runtime RL on episodic memory.
6. **SimpleMem** — Liu et al., Jan 2026, ICLR 2026 Workshop. Efficient lifelong memory with adaptive pruning.
7. **LRAT** — Zhou et al., SIGIR 2026. Learning retrievers from agent trajectories.
8. **Graph-based Agent Memory (Survey)** — Yang et al., Feb 2026. Taxonomy of graph-based approaches.
9. **MAGMA** — Jiang et al., Jan 2026. Multi-graph agentic memory architecture.
10. **LiCoMemory** — Huang et al., Nov 2025. Lightweight cognitive memory with CogniGraph.
11. **MIA** — Compounding memory architecture. 7B outperforms 32B by 18%.
12. **Focus** — Verma, Jan 2026. Active context consolidation for MemGPT-style systems.
13. **Letta Memory Models** — Jun 2026. Memory-native RL for agent learning.
14. **Letta Context Repositories** — Feb 2026. Git-based memory versioning.
15. **Supersede** — Jun 2026. Time-indexed supersession signals for memory freshness.
16. **Cognee** — Optimising KG-LLM interface for complex reasoning.
17. **MemMachine** — Sep 2025. Episodic memory reaching 0.8487 on LoCoMo.
18. **Hindsight** — Multi-strategy retrieval (semantic + BM25 + graph + temporal), 94.6% LongMemEval.
19. **LoCoMo Benchmark Audit** — Penfield Labs, Apr 2026. 6.4% answer key errors, 63% judge false-positive rate.
20. **MINJA / Memory Poisoning studies** — 2026. 90%+ agent vulnerability, 100% relapse on conversational correction.

---

## 8. The Big Picture

```
2023: "Give the agent a vector DB" (RAG era)
2024: "Give the agent a memory hierarchy" (MemGPT era)  
2025: "Give the agent structured memory with links" (A-MEM, Mem0 era)
2026: "Make memory compound, detect staleness, survive poisoning" (MemRL, LRAT, Supersede era)
```

The trajectory is clear: memory is moving from **storage** (how do we keep facts?) to **intelligence** (how do facts make the agent smarter over time?). The systems that win will be those where:

1. Memory **compounds** — each interaction makes future interactions better, not just more informed
2. Memory **stays fresh** — temporal validity is tracked and stale facts are detected automatically  
3. Memory **is explainable** — you can trace why the agent retrieved a fact and how it influenced the decision
4. Memory **is secure** — poisoning attempts are detected and blocked at the write path

For Catalyst specifically: our file-based approach is a solid episodic foundation, but we need to add entity awareness, temporal validity, and utility-weighted retrieval to move from "storage" to "intelligence."

---

*Research compiled by Catalyst 🧪 — evening deep exploration, 2026-07-04*
