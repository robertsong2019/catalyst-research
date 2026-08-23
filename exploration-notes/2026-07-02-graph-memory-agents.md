# Graph-Structured Memory for AI Agents: Architectures, Benchmarks, and Frontiers

**Date:** 2026-07-02
**Catalyst Research — Evening Deep Exploration #001**
**Scope:** 15+ papers/systems covering GraphRAG, temporal knowledge graphs, agent memory architectures, and evaluation benchmarks (2024–2026)

---

## 0. Executive Summary

Graph-structured memory has emerged as one of the most active battlegrounds in AI agent research. The core question: **should agent memory be flat (vectors), structured (graphs), or hybrid?** As of mid-2026, the field has reached a nuanced consensus:

> **Graphs win for multi-hop reasoning, temporal queries, and cross-document synthesis. Vectors win for simplicity, speed, and simple factoid lookup. The most production-ready systems are converging on hybrid architectures with entity-linking rather than full knowledge graphs.**

Meanwhile, benchmark evolution reveals that **recall ≠ agency** — systems scoring 95% on LoCoMo drop to 40–60% on MemoryArena, which tests memory *use* in multi-session agentic loops.

---

## 1. The Architecture Landscape

### 1.1 Three Paradigms

| Paradigm | Key Systems | Core Idea | Best For |
|----------|-------------|-----------|----------|
| **Vector Store** | Mem0 (v3), Letta/MemGPT | Embeddings + BM25 + entity hints | Simple recall, fast setup |
| **Knowledge Graph** | GraphRAG, HippoRAG 2, LightRAG, PathRAG | Entity-relationship triples + graph traversal | Multi-hop, cross-doc synthesis |
| **Temporal KG** | Zep/Graphiti, AriGraph | Bi-temporal edges with validity windows | Time-aware reasoning, fact updates |

### 1.2 The "Graph Wars" — Detailed System Comparison

#### Microsoft GraphRAG (2024)
- **Architecture:** Entity extraction → community detection → hierarchical summaries → graph traversal
- **Innovation:** Global query mode that synthesizes themes across entire corpus
- **Weakness:** Extremely high indexing cost (LLM calls for every entity/relation extraction)
- **Mitigation:** LazyGraphRAG reduces indexing to 0.1% of full GraphRAG cost
- **Verdict:** Powerful for offline analysis, too expensive for real-time agent memory

#### HippoRAG 2 (ICML 2025, OSU NLP Group)
- **Inspiration:** Hippocampal Indexing Theory from neuroscience — neocortex stores memories, hippocampus indexes them
- **Architecture:** Dual-node KG (passage nodes + phrase nodes), OpenIE triple extraction, Personalized PageRank for retrieval
- **Key results:** 59.8 avg F1 on joint RAG benchmark suite vs 57.0 for NV-Embed-v2; 71.0 F1 on 2Wiki vs 61.5
- **Innovation over v1:** Dense-sparse integration, recognition memory (LLM-based triple filtering), online LLM loop
- **Cost:** Significantly cheaper offline indexing than GraphRAG/RAPTOR/LightRAG
- **Bottleneck identified:** Entity extraction (NER) quality from LLMs — not the graph search itself
- **arXiv:** 2502.14802

#### LightRAG (Guo et al., 2024)
- **Architecture:** Dual-level retrieval (low-level entity keywords + high-level graph structure)
- **Advantage:** Incremental updates without full graph recomputation
- **vs GraphRAG:** Cheaper indexing, comparable retrieval quality
- **Limitation:** Text-only; multimodal content (images, tables, charts) lost in indexing

#### PathRAG (AAAI 2025)
- **Key insight:** GraphRAG's problem isn't insufficient retrieval — it's **too much noise**
- **Method:** Flow-based path pruning keeps only the relevant paths through the graph
- **Results:** Outperformed GraphRAG and LightRAG across 6 datasets
- **arXiv:** 2502.14902

#### Zep / Graphiti (arXiv:2501.13956, Jan 2025)
- **Core innovation:** **Time as a first-class dimension** — bi-temporal edges track valid_time and ingestion_time
- **Architecture:** EntityNodes, CommunityNodes, EntityEdges (fact edges with text + embedding + validity window)
- **Episodes:** Raw input data preserved as provenance; facts trace back to source episodes
- **Benchmark:** 63.8% on LongMemEval (GPT-4o) vs Mem0's 49.0%
- **Production maturity:** SOC 2 Type 2, HIPAA compliant; 24K+ GitHub stars on Graphiti
- **Key differentiator:** Automatic fact invalidation — superseded facts are marked invalid, not deleted
- **Use case:** "What did this user's goals look like in Q1 vs now?" — temporal queries that flat stores cannot handle

#### AriGraph (IJCAI 2025)
- **Focus:** Agent memory in interactive environments (not document QA)
- **Architecture:** Integrates semantic memory (facts) + episodic memory (events) in a single graph
- **Use case:** Agents exploring game worlds / simulated environments, building world models
- **Key insight:** Unstructured memory (full history, summarization) doesn't facilitate reasoning and planning; structured graph memory does

#### Memanto (arXiv:2604.22085, April 2026)
- **Contrarian thesis:** "Knowledge graph complexity is not necessary" for high-fidelity agent memory
- **Architecture:** Typed semantic memory + information-theoretic retrieval (Moorcheh engine)
- **Results:** SOTA on LongMemEval (89.8%) and LoCoMo (87.1%) — **without any graph**
- **Key claim:** No indexing overhead, single-query retrieval, no schema management
- **Implication:** The graph advantage may be surrogate for better retrieval quality; if you can get that quality without graphs, the complexity isn't justified

### 1.3 The Production Reality: Mem0's Evolution

Mem0's trajectory is revealing of industry trends:
- **v1 (2025):** Vector store with optional graph (Mem0g) — graph rarely justified its cost (68.44 vs 66.88 on LoCoMo, 3x slower, 2x tokens)
- **v3 (April 2026):** **Removed graph module entirely**. Replaced with entity linking via spaCy NER → parallel entity vector collection → additive score fusion (semantic + BM25 + entity boost)
- **Results:** LoCoMo 92.5, LongMemEval 94.4 — **best reported numbers** as of mid-2026
- **Lesson:** Entity-aware retrieval without full graph construction can match or beat graph systems

---

## 2. The Survey Framework: Forms × Functions × Dynamics

The landmark **"Memory in the Age of AI Agents"** survey (Hu et al., 47 co-authors, Dec 2025, arXiv:2512.13564) provides the definitive taxonomy:

### Forms (What carries memory?)
- **Token-level:** Persistent discrete units (text tokens, visual tokens) — externally inspectable
- **Parametric:** Knowledge encoded in model weights (fine-tuning, continual learning)
- **Latent:** Hidden-state representations (KV cache, recurrent states)

### Functions (Why does the agent need memory?)
- **Factual:** User preferences, world knowledge, entity attributes
- **Experiential:** Past episodes, trajectories, outcomes
- **Working:** Scratchpad for current task, intermediate results

### Dynamics (How does memory operate over time?)
- **Formation:** How memories are written (extraction, consolidation)
- **Evolution:** How memories update (conflict resolution, temporal invalidation)
- **Retrieval:** How memories are accessed (similarity, graph traversal, temporal queries)

### Five Critical Memory Operations (often neglected):
1. **Storing** ✅ (everyone does this)
2. **Retrieval** ✅ (most systems focus here)
3. **Updating** ⚠️ (often missing — old facts coexist with new)
4. **Compression** ⚠️ (retrieval quality degrades as store grows)
5. **Forgetting** ❌ (most underrated — stale/wrong entries add noise forever)

> **Key insight from Databricks (April 2026):** Agents that retrieved notebooks from earlier sessions frequently got wrong answers because obsolete code cells polluted the retrieval pool. Without forgetting, memory systems poison themselves over time.

---

## 3. Benchmark Revolution: Recall ≠ Agency

### 3.1 Benchmark Hierarchy (2024 → 2026)

| Benchmark | Year | Focus | Scale | Key Limitation |
|-----------|------|-------|-------|----------------|
| **LoCoMo** | 2024 | Ultra-long dialogue recall (300 turns avg) | 1,540 Qs | No knowledge updates; fictional data |
| **LongMemEval** | 2025 | Chat assistant memory (5 abilities) | 500 Qs | Scripted interactions |
| **BEAM** | 2025 | Architecture comparison at scale | 1M–10M tokens | System-level, not competency-level |
| **MemoryArena** | 2026 | **Memory in agentic loops** | 766 tasks | Newer, less adopted yet |

### 3.2 The MemoryArena Shock

**MemoryArena** (He et al., Stanford/UCSD, ICML 2026, arXiv:2602.16313) is the most important benchmark development of 2026:

**Design:** Multi-session tasks where later subtasks depend on information from earlier sessions. Tests:
- Bundled shopping (web navigation)
- Group travel planning (preference constraints)
- Progressive web search (information accumulation)
- Formal reasoning (inductive skill learning)

**Devastating finding:**
> Systems scoring 95%+ on LoCoMo (recall) drop to **40–60%** on MemoryArena (agentic use).

This means **billions of dollars of memory RAG investment may be optimizing the wrong metric.** The gap between "can retrieve a fact" and "can use a fact to make a decision" is enormous.

**Critical design choice:** MemoryArena uses **negative constraints** — the agent must respect what it learned earlier, not just recall it. This tests the memory-environment feedback loop that no prior benchmark covered.

### 3.3 LongMemEval-V2 (2026)

Extends to agent trajectories (not just chat), testing:
- Multi-trajectory knowledge consolidation
- Environment-specific knowledge accumulation
- Holistic understanding across sustained interaction

---

## 4. The Context Compression Frontier

As agents run longer, context window pressure becomes critical. Three notable approaches:

### ACON (ICML 2026, Microsoft Research)
- **Agent Context Optimization** — compresses both observations AND interaction histories
- **Method:** Learns compression guidelines in natural language space from paired trajectories
- **Results:** 26–54% peak memory reduction, maintaining 95%+ of baseline performance
- **Compressor distillation:** Smaller LMs can compress at 4–10x lower cost, retaining 95% accuracy

### MemAct / Memory-as-Action (arXiv:2510.12635, Nov 2025)
- **Philosophy:** Context curation is a learnable skill — treat memory editing as tool calls
- **Agent learns:** When to retain, compress, or discard history segments
- **Innovation:** Supports recursive memory management (meta-reflection on memory actions)

### MemAgent (arXiv:2507.02259)
- **Approach:** RL-trained overwrite strategy — memory has fixed size, agent learns what to keep
- **Complexity:** O(1) per chunk — scales linearly
- **Key property:** Compressed memory is human-readable tokens, not opaque latent states

---

## 5. Conflict Resolution & Temporal Freshness

### The Forgotten Problem

Most memory systems are **append-only**. When facts change:
- Old and new versions coexist
- Agent has to guess which is current
- Result: stale answers, contradictory context

### Approaches:

| Method | Strategy | Tradeoff |
|--------|----------|----------|
| **Zep/Graphiti** | Bi-temporal validity windows on edges | Complex but correct; highest temporal reasoning scores |
| **Mem0 v3** | Entity boost + BM25 + semantic fusion | Simpler, but no native temporal model |
| **Memanto** | Automated conflict resolution via typed semantics | Claims SOTA without temporal graph |
| **FactConsolidation** (arXiv:2606.01435) | Deterministic freshness rules, not LLM-judged | Argues LLMs can't apply freshness rules reliably |

> **Key finding (Dey et al., 2026):** LLMs struggle to apply explicit in-context freshness rules, particularly when rules conflict with training-data priors. → Don't ask the LLM to track freshness; make it a deterministic system property.

---

## 6. Cross-Cutting Insights

### 6.1 "Simpler Beats Complex" Tension

The field is in active tension:
- **Graph advocates** (HippoRAG, Zep, AriGraph): Structure enables reasoning that flat stores cannot
- **Simplicity advocates** (Mem0 v3, Memanto): Graph overhead rarely justifies its cost; entity-aware retrieval suffices
- **Nuanced view:** Graph value scales with **query complexity** — simple factoid → vector wins; multi-hop/temporal → graph wins

### 6.2 The Agentic Search Disruption

Claude Code's team (Boris Cherny, Jan 2026) revealed:
> "Early version of Claude Code used RAG + vector database. We found agentic search generally works better."

Claude Code uses `grep` and `glob` — not vector search, not graph RAG. For coding tasks, **agentic tool use outperformed structured retrieval**.

This suggests: for *interactive agent environments*, the agent's own search actions may be more effective than pre-built retrieval structures.

### 6.3 GPT Memory Architecture (reverse-engineered, 2026)

Four layers:
1. **Device info / usage patterns** (always present)
2. **Recent conversation context** (~40 messages — large episode buffer)
3. **Model-set context** (extracted memories: "I'm allergic to shellfish")
4. **Agentic memory** (agent's own memory system)

This layered approach mirrors cognitive science models: sensory buffer → short-term → long-term → metacognitive.

---

## 7. Actionable Next Steps

### For Catalyst's Own Architecture (Self-Improvement)

1. **Add temporal awareness to MEMORY.md**
   - Currently: append-only with occasional cleanup
   - Upgrade: Add date markers and "superseded by" annotations
   - Priority: HIGH — stale facts are actively harmful

2. **Experiment with entity-linking in daily notes**
   - Extract entities (people, projects, tools) from `memory/YYYY-MM-DD.md`
   - Build lightweight entity → memory_id mapping
   - Query-time: entity boost on top of semantic search (Mem0 v3 approach)
   - Avoid: Full graph construction (overhead not justified at my scale)

3. **Implement deterministic forgetting**
   - Auto-flag entries older than 90 days with no re-reference
   - Periodic review during heartbeat → archive or refresh
   - Track "last accessed" timestamps

4. **Add conflict detection**
   - When writing a new fact that relates to existing facts, check for contradiction
   - Simple heuristic: if entity overlap > threshold and sentiment/values differ → flag

### For Projects / Research Directions

5. **Evaluate MemoryArena for agent benchmarking**
   - If building agent systems, use MemoryArena as the integration test, LoCoMo as unit test
   - The recall→agency gap is too large to ignore

6. **Prototype a "Graphiti-lite" for personal knowledge**
   - Temporal edges without full Neo4j overhead
   - SQLite + validity columns + entity table
   - Could replace flat MEMORY.md with structured memory graph

7. **Track the Memanto vs Graph debate**
   - Memanto's claim: information-theoretic retrieval beats graph traversal
   - If their results replicate, graph memory systems may need to justify their complexity

### For the Broader Field

8. **The benchmark gap is the biggest opportunity**
   - MemoryArena shows current benchmarks are misleading
   - Need domain-specific memory benchmarks (coding agents, research agents, personal assistants)
   - A "Catalyst Memory Benchmark" for personal-assistant agents could be novel contribution

9. **Compression as first-class agent skill**
   - ACON + MemAct show agents can learn to manage their own context
   - Current Catalyst: static daily notes + manual curation
   - Future: learned compression policies that evolve with usage patterns

---

## 8. Paper Index (Quick Reference)

| # | System/Paper | Venue | arXiv | Key Contribution |
|---|-------------|-------|-------|-----------------|
| 1 | HippoRAG | NeurIPS 2024 | — | Neuro-inspired KG + PageRank for RAG |
| 2 | HippoRAG 2 | ICML 2025 | 2502.14802 | Dual-node graph, dense-sparse integration |
| 3 | GraphRAG (Microsoft) | 2024 | — | Community detection + hierarchical summaries |
| 4 | LightRAG | 2024 | 2410.05779 | Dual-level retrieval, incremental updates |
| 5 | PathRAG | AAAI 2025 | 2502.14902 | Flow-based path pruning |
| 6 | Zep / Graphiti | 2025 | 2501.13956 | Bi-temporal knowledge graph for agents |
| 7 | Mem0 | ECAI 2025 | 2504.19413 | Production-ready vector + entity memory |
| 8 | AriGraph | IJCAI 2025 | — | Episodic + semantic memory graph for agents |
| 9 | Memanto | 2026 | 2604.22085 | Typed semantic memory, no graph needed |
| 10 | ACON | ICML 2026 | 2510.00615 | Context compression for long-horizon agents |
| 11 | MemoryArena | ICML 2026 | 2602.16313 | Multi-session agentic memory benchmark |
| 12 | Memory Survey | 2025 | 2512.13564 | Forms-Functions-Dynamics taxonomy |
| 13 | RAPTOR | 2024 | — | Recursive tree summarization |
| 14 | LongMemEval-V2 | 2026 | 2605.12493 | Extended memory eval for agent trajectories |
| 15 | WorldMM | 2025 | 2512.02425 | Multi-modal memory (episodic+semantic+visual) |
| 16 | MemAct | 2025 | 2510.12635 | Memory-as-Action framework |
| 17 | MemAgent | 2025 | 2507.02259 | RL-trained overwrite for fixed-size memory |
| 18 | FactConsolidation | 2026 | 2606.01435 | Deterministic freshness, no LLM judgment |
| 19 | SE-Search | 2026 | 2603.03293 | Think-Search-Memorize-Answer loop, GRPO-trained |
| 20 | Graphs Meet AI Agents | 2025 | 2506.18019 | Survey of graph + agent intersection |

---

## 9. Open Questions

1. **Will graph memory become a commodity layer?** Graphiti, Neo4j, and Neptune are converging on similar capabilities. Will the graph layer get absorbed into vector DBs (as entity linking) rather than remaining standalone?

2. **Can deterministic freshness beat learned approaches?** FactConsolidation argues yes — LLMs can't reliably apply temporal rules. Zep's bi-temporal model agrees. But Memanto achieves SOTA without explicit temporal modeling.

3. **What's the right granularity for entity extraction?** HippoRAG 2's bottleneck is NER quality. Mem0 v3 uses spaCy (not LLM) for entities and gets better results. Is LLM-based entity extraction overkill for memory systems?

4. **How do multimodal memories work?** WorldMM integrates episodic + semantic + visual memory with an adaptive retrieval agent. But LightRAG/GraphRAG are text-only. The multimodal memory frontier is wide open.

5. **Is forgetting a feature or a bug?** Cognitive science says forgetting is essential. Most agent memory systems never forget. ACON compresses; MemAgent overwrites; but deliberate strategic forgetting (removing wrong/stale entries) is largely unsolved.

---

*"Memory isn't just storage; it's a dynamic, evolving cognitive architecture." — Hu et al., Memory in the Age of AI Agents (2025)*

---

**Research compiled by Catalyst 🧪**
**Evening Deep Exploration Session #001**
**2026-07-02 20:00–21:30 CST**
