# Research #026: July 2026 Agent Memory Landscape — Competitive Analysis for npm/PyPI Strategy

> Date: 2026-07-24
> Trigger: #1 priority npm publish (4 projects ready). Need competitive positioning.
> Methodology: Direct GitHub README analysis + npm/PyAPI audit + feature matrix

---

## Executive Summary

The agent memory landscape has shifted dramatically since our last competitive scan (Research #018, 07-19). **Mem0 v3** jumped to LoCoMo 92.5 / LongMemEval 94.4 with an ADD-only architecture. **Supermemory** claims #1 on all three major benchmarks with 95% Recall@15. **Graphiti/Zep** now requires a separate graph database (Neo4j/FalkorDB). **Cognee** has matured into a full platform with OpenClaw plugin. The competitive window is narrowing but amg's unique value proposition (triple-loop quality, 30k+ lines, 652 APIs, 4269 tests, zero external dependencies) remains differentiated.

---

## Core Concepts (5)

### 1. The Platform-vs-Library Divide
Every major competitor has chosen **platform** as their business model:
- **Mem0**: Managed platform + self-hosted server + thin library wrapper
- **Zep**: Managed-only (Graphiti is the OSS engine, still needs Neo4j)
- **Supermemory**: Managed API + local binary (but still a service, not a library)
- **Cognee**: API server + Docker containers + MCP server
- **Letta**: Agent SDK + cloud + CLI app

**None of them is a pure library.** All require external services (LLM API, vector DB, graph DB, or their managed platform). This is the gap amg fills: a **zero-dependency, embeddable library** that runs anywhere Python runs.

### 2. ADD-Only Architecture Trend
Mem0 v3's biggest change: **removed UPDATE/DELETE entirely**. Memories accumulate; nothing is overwritten. This confirms our Insight #7 (Mem0 contradiction_resolution 35.7%). But Mem0 spins it as a feature ("agent-generated facts are first-class"). The implication: **conflict resolution is an unsolved problem in production**, and the industry is punting on it. amg's `supersede` + `conflict` + `forget` is a competitive advantage that others are too afraid to implement.

### 3. Plugin-First Distribution is Table Stakes
Every competitor has MCP servers and IDE plugins:
- Mem0: Claude Code skills (`npx skills add`), CLI
- Supermemory: OpenClaw plugin, Claude Code plugin, Cursor, Windsurf, MCP server
- Cognee: Claude Code plugin, OpenClaw plugin, MCP server, Docker
- Graphiti: MCP server

**amg-mcp (122 tests, 14 tools, dual transport) is already competitive.** But the plugin ecosystem is now the primary distribution channel, not npm/PyPI.

### 4. Benchmark Arms Race
The leaderboard is hotly contested:
| System | LoCoMo | LongMemEval | BEAM (1M) | Notes |
|--------|--------|-------------|-----------|-------|
| Supermemory | #1 claimed | #1 claimed | — | 95% Recall@15, 99.4% context reduction |
| Mem0 v3 | 92.5 | 94.4 | 64.1 | ADD-only, single-pass retrieval |
| Mandol | 92.21 | — | — | ISCAS+MSRA, PyPI published |
| Hindsight | — | 91.4 | — | Multi-strategy hybrid |
| PlugMem | — | 90.2 | — | ICML 2026, OpenClaw plugin |
| Synthius-Mem | 94.4 | — | — | arXiv only |

**amg is not on this leaderboard.** Without benchmark scores, positioning must shift from accuracy to **capability breadth + architecture advantages**.

### 5. TypeScript Ecosystem is Still Empty
Despite all the platforms having TypeScript SDKs, **none is a TypeScript-native library**:
- Mem0 npm package (`mem0ai`) is a thin client wrapping their Python/cloud API
- Zep TypeScript SDK (`@getzep/zep-cloud`) calls their managed API
- Supermemory npm package is a client for their API
- Letta Agent SDK (`@letta-ai/letta-agent-sdk`) controls their agent runtime
- Cognee TypeScript client (`@cognee/cognee-ts`) is a wrapper over their Python core

**There is still zero TypeScript-native agent memory library with graph algorithms.** This validates Insight #68 but the window may close.

---

## Competitive Feature Matrix

| Feature | amg | Mem0 v3 | Graphiti | Supermemory | Cognee | Letta |
|---------|-----|---------|----------|-------------|--------|-------|
| **Architecture** | Library | Platform | Framework | Platform | Platform | Agent SDK |
| **Language** | Python | Python+TS client | Python | TS+Python | Python+TS client | TS |
| **Graph DB Required** | ❌ (SQLite) | ❌ | ✅ (Neo4j/Falkor) | ❌ | ❌ | ❌ |
| **LLM Required** | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Zero-Config** | ✅ | ❌ | ❌ | Partial | ❌ | ❌ |
| **External Deps** | 0 | LLM+VectorDB | Neo4j+LLM | — | LLM+DB | — |
| **Conflict Resolution** | ✅ (supersede+conflict) | ❌ (ADD-only) | ✅ (temporal) | ✅ | ✅ | ❌ |
| **Forgetting** | ✅ (strategic+entropy) | ❌ | ✅ (temporal) | ✅ | ✅ | ❌ |
| **Graph Quality Mgmt** | ✅ (triple-loop) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Skill Extraction** | ✅ (compress→skill) | ❌ | ❌ | ❌ | ❌ | ✅ (skills) |
| **Evaluation Suite** | ✅ (5-metric quartet) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Governance** | ✅ (write_governance) | ❌ | ❌ | ❌ | ✅ (OTEL) | ❌ |
| **Temporal Queries** | ✅ (bi-temporal) | ✅ | ✅ (bi-temporal) | ✅ | ❌ | ❌ |
| **Topological Indices** | ✅ (16 families) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Triple-Loop Quality** | ✅ (gap+redundancy+skill) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **CRDT Support** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **PPR Search** | ✅ | ❌ | ✅ (graph traversal) | ❌ | ❌ | ❌ |
| **MCP Server** | ✅ (14 tools) | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Tests** | **4269** | Unknown | Unknown | Unknown | Unknown | Unknown |
| **Lines of Code** | **30,339** | ~5,000* | ~8,000* | Unknown | Unknown | Unknown |
| **Benchmark Scores** | ❌ | 92.5/94.4 | SOTA claimed | #1 claimed | Unknown | Unknown |

*Estimated from GitHub stats

---

## Key Insights (5)

### Insight 1: amg is the only "batteries-included" library in a field of thin clients

Every competitor ships as a **platform** (API + dashboard + managed service). Their npm/PyPI packages are thin clients that call their API. amg is the only project that bundles:
- Graph algorithms (PPR, 19 centrality metrics, 16 topological index families)
- Vector + BM25 + graph search (all in-process)
- Triple-loop quality management (gap→heal, redundancy→consolidate, skill→compress)
- Evaluation suite (5 metrics)
- Governance layer (write-time checks)
- All on SQLite, zero external dependencies

**Positioning: "The only agent memory library that doesn't need a server, a database, or an API key."**

### Insight 2: Mem0's ADD-only pivot validates amg's conflict resolution advantage

Mem0 v3 explicitly removed UPDATE/DELETE: "Single-pass ADD-only extraction — one LLM call, no UPDATE/DELETE. Memories accumulate; nothing is overwritten." This is a **regression** in capability, spun as simplicity. amg's `supersede` + `conflict_detect` + `strategic_forget` is strictly more expressive. README should contrast: "Others accumulate. amg consolidates."

### Insight 3: The plugin ecosystem IS the distribution channel

Supermemory has OpenClaw, Claude Code, Cursor, Windsurf, and Hermes plugins. Cognee has OpenClaw and Claude Code plugins. Mem0 has skills. **If amg doesn't ship an OpenClaw plugin alongside the PyPI package, it's invisible to the fastest-growing user segment.** The MCP server (amg-mcp) is necessary but not sufficient — MCP is for tool access, plugins are for lifecycle hooks.

### Insight 4: Benchmark scores are now table stakes for credibility

Supermemory, Mem0, Mandol, PlugMem all lead with benchmark numbers. amg has no public scores. Two options:
1. **Run LoCoMo/LongMemEval** and publish (requires LLM API, ~$50-100 in tokens)
2. **Reframe positioning** from accuracy to capability ("Not just recall. Agency-grade memory with governance, quality management, and skill extraction.")

Option 2 is pragmatic for v1. Option 1 should be on the roadmap.

### Insight 5: amg's Python-first architecture is a strategic asset, not a liability

The TypeScript gap is real, but porting 30K lines is impractical. Instead, **amg should dominate PyPI** where the competition is weak (Mem0 and Graphiti are Python but require servers; Cognee needs Docker). amg is the only **pip-install, import, done** option. The npm package can be a Python subprocess wrapper or WASM-compiled module for the TypeScript market.

---

## Code Example: Competitive Differentiation Snippet for README

```python
from memory_graph import MemoryGraph

# === amg: Zero-config, zero-dependency, zero-API-key ===
mg = MemoryGraph(":memory:")  # In-memory SQLite. Done.

# Store with governance (no competitor has this)
mg.add("Alice prefers dark mode", tags=["preference"], confidence=0.95)
mg.add("Alice switched to light mode", tags=["preference"], confidence=0.90)

# Conflict detected, old memory superseded (Mem0 can't do this)
# Mem0 v3: both memories accumulate, retrieval returns contradictory results
# amg: supersede chain preserves history, retrieval returns current truth

# Triple-loop quality management (no competitor has ANY loop)
health = mg.health_check()           # Check graph health
gaps = mg.knowledge_gap_report()      # Find missing connections
mg.auto_heal_gaps()                   # Fix them automatically
redundancy = mg.redundancy_detect()   # Find duplicate information
mg.auto_consolidate()                 # Merge redundancies
mg.auto_compress_skills()             # Promote patterns to skills

# Multi-strategy retrieval (competitors have 1-2 strategies)
results = mg.query(
    "What does Alice prefer?",
    strategy="ppr",           # Personalized PageRank
    intent="preference",      # 7-intent taxonomy routing
    explain=True              # Score decomposition
)

# Evaluation (no competitor has built-in metrics)
quality = mg.retrieval_quality_eval(test_queries)
density = mg.graph_information_density()

print(f"Graph health: {health['health_score']}/100")
print(f"Retrieval quality: {quality}")
print(f"Information density: {density}")
# All without a single external API call, database server, or LLM.
```

---

## Actionable Recommendations

### For README (Immediate, blocks npm publish)

1. **Lead with the zero-dependency differentiator**: "pip install agent-memory-graph. No Neo4j. No OpenAI key. No Docker. Just memory."

2. **Feature comparison table** (use the matrix above, simplified)

3. **Anti-positioning against each competitor**:
   - vs Mem0: "Others ADD-only. amg consolidates."
   - vs Graphiti: "No graph database required."
   - vs Supermemory: "A library, not a SaaS."
   - vs Cognee: "No Docker, no server, no pipeline."

4. **The "800-pound gorilla" stats**: 4269 tests, 30K lines, 652 APIs, 251 consecutive days

### For Distribution (Next 2 weeks)

1. **PyPI publish first** — Python ecosystem is home turf, thinner competition
2. **OpenClaw plugin** — Supermemory and Cognee both have one; amg doesn't
3. **MCP server publish** — amg-mcp is ready (122 tests, dual transport)
4. **npm wrapper** — Thin TypeScript wrapper calling Python subprocess (like Cognee's approach)

### For Benchmarking (Next month)

1. **LoCoMo adapter** — Implement and run. ~$50-100 in LLM API costs
2. **LongMemEval adapter** — Second priority
3. **Publish scores** even if not SOTA. "Honest scores with zero external dependencies" is a positioning

---

## Next Actions (Updated)

- [ ] **amg README**: Use competitive matrix from this research. Lead with zero-dependency + triple-loop quality as twin pillars.
- [ ] **amg PyPI publish**: Python ecosystem is the fastest path to users. Thinner competition than npm.
- [ ] **amg OpenClaw plugin**: Critical for distribution. Supermemory + Cognee both have one.
- [ ] **LoCoMo benchmark run**: Budget ~$50-100 in LLM API tokens for first official score.
- [ ] **agent-context-store README**: Position as "analytics companion to amg" with the detect→configure→recommend→validate→correlate pipeline.

---

## Sources

- [Mem0 GitHub](https://github.com/mem0ai/mem0) — v3 announcement, benchmark numbers, ADD-only architecture
- [Graphiti GitHub](https://github.com/getzep/graphiti) — temporal KG, Neo4j requirement, MCP server
- [Supermemory GitHub](https://github.com/supermemoryai/supermemory) — #1 benchmarks claim, OpenClaw plugin
- [Cognee GitHub](https://github.com/topoteretes/cognee) — full platform, Docker, OpenClaw plugin
- [Letta GitHub](https://github.com/letta-ai/letta) — Agent SDK pivot, TypeScript native
- [Mem0 Paper (arXiv:2504.19413)](https://arxiv.org/abs/2504.19413) — LoCoMo 26% improvement, 91% latency reduction
- agent-memory-graph: 4269 tests, 30,339 lines, 652 functions (live repo data)
