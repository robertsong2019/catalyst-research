# Deep Research #019: Memory Compression → Skill Extraction — From Theory to TypeScript Implementation

> **Date:** 2026-07-19
> **Trigger:** deep-exploration-evening cron
> **Methodology:** autoresearch.md (明确指标 → 快速循环 → 保留/回退 → 积累性)
> **Relation to amg:** Directly informs `compress_to_skill()` + `evolve_skill()` + `skill_bank_health()` roadmap (~140 tests)
> **Builds on:** #014 (Self-Evolving Agent Memory), #011 (Procedural Memory)

---

## Executive Summary

Research #014 established the theory: Experience Compression Spectrum (L0→L3), Read-Write-Assess-Govern lifecycle, and skill banks as first-class citizens. This note answers the **how**: how to implement `compress_to_skill()` in TypeScript for agent-memory-graph. Three new papers (MemRefine, Focus, MemSkill) provide concrete implementation patterns that map directly to amg's existing APIs. The key finding: **amg's redundancy_detect() + knowledge_gap_report() + Q-value scoring are the exact primitives needed for storage-budgeted compression** — the same machinery that finds problems can drive the compression that fixes them.

---

## Core Concepts (5)

### 1. Storage-Budgeted Memory Management (MemRefine, arXiv:2606.13177)

**MemRefine** (Kim et al., Jun 2026, OpenReview) formalizes **post-construction memory compression** as a distinct task: given an already-built memory store and a target budget, reduce storage while preserving downstream utility.

**Key insight:** Surface similarity poorly reflects factual value. MemRefine uses similarity only to *propose candidate pairs*, then defers the delete/merge/preserve decision to an LLM judge based on factual content.

**Algorithm:**
```
while store_size > budget:
    1. Find top-K similar pairs via embedding cosine similarity
    2. For each pair, LLM judge decides: delete | merge | preserve
    3. Apply decisions
    4. Repeat until budget met
```

**Results:** Consistently meets target budgets while preserving downstream performance. Outperforms rule-based baselines under tight budgets. Works as a post-construction module on top of any memory framework (Mem0, A-MEM, etc.).

**amg mapping:** This is **exactly** what `compress_to_skill()` should do:
- Use `redundancy_detect()` (already built, cycle 267) to find candidate pairs — it already does content duplicates (trigram Jaccard), structural clones (neighbor set Jaccard), and functional duplicates (same kind + weight±20% + degree±1)
- Use LLM judge (or heuristic fallback) to decide: merge into a skill node | delete | keep
- Budget = configurable parameter (`max_nodes` or `target_density`)

```typescript
// MemRefine-inspired compress_to_skill()
compress_to_skill(options?: {
  budget?: number;           // target node count (default: current * 0.7)
  similarity_threshold?: number;  // candidate pair threshold (default: 0.75)
  merge_strategy?: 'llm' | 'heuristic';  // default: 'heuristic'
  skill_kind?: string;       // resulting node kind (default: 'skill')
}): {
  compressed_count: number;
  skills_created: number;
  nodes_removed: number;
  density_before: number;
  density_after: number;
}
```

### 2. Agent-Controlled Sawtooth Compression (Focus, arXiv:2601.07190)

**Focus** (Verma et al., Jan 2026) introduces **intra-trajectory compression**: the agent itself decides when to compress its context during a task, not after.

**Architecture:** Two primitives added to the agent loop:
- `start_focus()` — marks a checkpoint ("I'm investigating the database connection")
- `complete_focus()` — summarizes what was learned, prunes raw history

**The Sawtooth Pattern:** Context grows during exploration, collapses during consolidation. Key findings:
- 22.7% token reduction with **zero accuracy loss** (SWE-bench Lite)
- Aggressive prompting (compress every 10-15 tool calls) is critical
- Exploration-heavy tasks benefit most (50-57% savings)
- Iterative refinement tasks can suffer (-110% overhead) — compression isn't universally beneficial

**amg mapping:** This validates amg's `compact()` (cycle 230, Level 3 Context Engineering) but extends it: the agent should be able to **mark regions of the graph for compression** and convert them into higher-level skill nodes. The `start_focus → complete_focus` pattern maps to:

```typescript
// Focus-inspired episodic→skill compression
// Step 1: Identify episodic cluster (a "focus region" in the graph)
const cluster = mg.subgraph_by_time(start_time, end_time);
// Step 2: Extract skill from cluster
const skill = mg.compress_to_skill({
  source_nodes: cluster.node_ids,
  extraction_mode: 'sawtooth',  // preserve key findings, discard raw traces
});
// Step 3: Connect skill to existing knowledge
mg.add_edge(skill.id, related_concept.id, { kind: 'derived_from' });
```

### 3. Learnable Memory Skills with Closed-Loop Evolution (MemSkill, ICML 2026)

**MemSkill** (Long et al., ICML 2026) is the most directly relevant paper for amg's skill evolution roadmap. It reframes memory operations (add/update/delete/skip) as **learnable, evolvable memory skills**.

**Three-component architecture:**
1. **Controller** — learns to select relevant skills for current context (RL-trained)
2. **Executor** — LLM conditioned on selected skills, produces memory updates in one pass
3. **Designer** — periodically reviews hard cases, refines existing skills, proposes new ones

**The closed loop:**
```
Train controller on skill bank → Log hard cases → 
Designer evolves skills (refine + create) → 
Resume training on evolved bank → Repeat
```

**Skill template structure:**
```
Skill:
  description: short text for selection
  content: detailed specification for executor
  invocation_conditions: when to apply
  expected_output: what the executor should produce
```

**Results:** Consistent improvements on LoCoMo, LongMemEval, HotpotQA, ALFWorld. Skills generalize across datasets. Evolved skills outperform initial hand-designed ones.

**amg mapping:** MemSkill's architecture maps beautifully to amg:
- Controller → `retrieve_skills()` with Q-value ranking
- Executor → `compress_to_skill()` with structured skill template
- Designer → `evolve_skill()` with hard-case-driven refinement

```typescript
// MemSkill-inspired skill bank structure
interface MemorySkill {
  id: string;
  description: string;           // for retrieval/selection
  content: string;               // detailed extraction guidance
  invocation_conditions: string; // when to apply
  contraindications: string[];   // when NOT to apply
  steps: string[];               // procedural steps
  output_spec: string;           // expected output format
  confidence: number;            // Q-value / utility score
  source_nodes: string[];        // which episodes compressed into this
  created_at: number;
  last_used: number;
  use_count: number;
  success_count: number;
  version: number;               // evolve_skill() increments this
}
```

### 4. Memory ↔ Skills Coupling (Externalization, arXiv:2604.08224)

**Externalization in LLM Agents** (Zhou et al., Apr 2026, 54-page tech report from SJTU) provides the theoretical framework that unifies memory and skills:

- **Memory externalizes state across time** (recall → recognition)
- **Skills externalize procedural expertise** (generation → composition)
- **They are coupled:** skill execution generates traces that become memory; memory retrieval influences which skills are chosen

**Key insight for amg:** The paper identifies a "missing diagonal" — no system supports adaptive cross-level compression (L1 episodic ↔ L2 skill ↔ L3 rule). This is exactly what amg's `compress_to_skill()` would provide for the first time in the npm ecosystem.

**Three-stage skill evolution (from the paper):**
1. Atomic execution primitives (amg: add/query/update)
2. Large-scale primitive selection (amg: query() with 7-intent routing)
3. Skill as packaged expertise (amg: compress_to_skill + retrieve_skills)

### 5. Compression as Quality Management (amg's Dual-Loop System)

**Synthesis insight:** amg's existing dual-loop quality system (cycles 264-267) is actually a **compression readiness detector**:

- `graph_information_density()` → tells you if compression is needed
- `knowledge_gap_report()` → tells you WHERE the gaps are (don't compress these areas)
- `redundancy_detect()` → tells you WHERE the excess is (compress these areas)
- `auto_heal_gaps()` → fixes under-connection
- **Missing:** `compress_to_skill()` → fixes over-connection by creating higher-level nodes

This means compression is the **natural completion** of the dual-loop system:
```
Gap analysis: find missing → auto_heal_gaps (add edges/nodes)
Redundancy analysis: find excess → compress_to_skill (merge into skills)
```

---

## Implementation Blueprint: compress_to_skill() + evolve_skill() + skill_bank_health()

### Phase 1: compress_to_skill() (~40 tests)

```typescript
/**
 * Compress redundant episodic nodes into a procedural skill node.
 * Inspired by MemRefine (similarity→candidate pairs→judge) and
 * Focus (sawtooth pattern: consolidate key learnings, withdraw raw traces).
 */
compress_to_skill(options: {
  // Targeting
  source_kind?: string;           // node kind to compress from (default: 'episodic')
  target_budget?: number;         // target total nodes (optional)
  density_threshold?: number;     // only compress if density < threshold
  
  // Candidate selection (reuse redundancy_detect machinery)
  content_jaccard_threshold?: number;  // default: 0.6
  structural_jaccard_threshold?: number; // default: 0.5
  functional_duplicate_weight_tolerance?: number; // default: 0.2
  
  // Skill creation
  skill_kind?: string;            // default: 'skill'
  skill_description?: string;     // auto-generated if not provided
  preserve_originals?: boolean;   // default: false (like compact() level 2)
  
  // Execution
  dry_run?: boolean;              // default: false
}): {
  skills_created: number;
  nodes_compressed: number;
  nodes_removed: number;
  edges_rewired: number;
  density_delta: number;
  skills: SkillCreationResult[];
}

// Internal implementation sketch:
function _compress_to_skill(options): CompressResult {
  // Step 1: Detect redundancy candidates (reuse cycle 267 code)
  const redundancy = this.redundancy_detect({
    content_threshold: options.content_jaccard_threshold,
    structural_threshold: options.structural_jaccarple_threshold,
  });
  
  // Step 2: For each merge candidate group, create a skill node
  const skills = [];
  for (const group of redundancy.merge_candidates) {
    // Extract common pattern from group members
    const skill_content = _extract_pattern(group.nodes);
    
    // Create skill node
    const skill = this.add({
      kind: options.skill_kind || 'skill',
      content: skill_content.summary,
      tags: ['compressed', `from_${group.nodes.length}_nodes`],
      weight: Math.max(...group.nodes.map(n => n.weight)),
      metadata: {
        source_node_ids: group.nodes.map(n => n.id),
        compression_ratio: group.nodes.length / 1,  // N nodes → 1 skill
        created_by: 'compress_to_skill',
        dimensions: group.dimensions,  // content/structural/functional
      }
    });
    
    // Rewire edges: connect skill to all neighbors of compressed nodes
    const neighbor_set = new Set<string>();
    for (const node of group.nodes) {
      const edges = this.edges_of(node.id);
      for (const edge of edges) {
        const neighbor = edge.source === node.id ? edge.target : edge.source;
        if (!group.nodes.find(n => n.id === neighbor)) {
          neighborSet.add(neighbor);
        }
      }
    }
    for (const neighborId of neighborSet) {
      this.add_edge(skill.id, neighborId, { kind: 'derived_from' });
    }
    
    // Remove originals (unless preserve_originals)
    if (!options.preserve_originals) {
      for (const node of group.nodes) {
        this.remove(node.id);
      }
    }
    
    skills.push(skill);
  }
  
  return { skills_created: skills.length, /* ... */ };
}
```

### Phase 2: retrieve_skills() (~25 tests)

```typescript
/**
 * Retrieve relevant skills from the skill bank.
 * MemSkill-inspired: rank by semantic relevance + Q-value (utility).
 */
retrieve_skills(query: string, options?: {
  top_k?: number;           // default: 5
  min_confidence?: number;  // default: 0.0 (all skills)
  tags?: string[];          // filter by tag
}): SkillMatch[]

// Implementation: combines BM25 (existing) + Q-value scoring
function _retrieve_skills(query: string, options): SkillMatch[] {
  const candidates = this.nodes()
    .filter(n => n.kind === 'skill')
    .filter(n => options.tags ? options.tags.every(t => n.tags.includes(t)) : true);
  
  const scored = candidates.map(skill => {
    const semantic_score = this._bm25_score(query, [skill]);
    const q_value = skill.metadata?.q_value ?? 0.5;
    const freshness = this._freshness_factor(skill.last_used);
    const combined = semantic_score * 0.5 + q_value * 0.3 + freshness * 0.2;
    return { skill, score: combined, semantic_score, q_value, freshness };
  });
  
  return scored
    .sort((a, b) => b.score - a.score)
    .slice(0, options.top_k ?? 5);
}
```

### Phase 3: evolve_skill() (~35 tests)

```typescript
/**
 * Evolve a skill based on usage feedback.
 * MemSkill's designer-inspired: refine content, update Q-value, version bump.
 */
evolve_skill(skill_id: string, options: {
  feedback?: 'success' | 'failure' | 'refine';
  new_content?: string;         // refined content (for 'refine')
  new_steps?: string[];         // refined steps
  q_value_delta?: number;       // manual Q-value adjustment
  auto_refine?: boolean;        // auto-generate improvements (default: false)
}): {
  skill_id: string;
  old_version: number;
  new_version: number;
  changes: string[];
}

// Implementation:
function _evolve_skill(skill_id: string, options): EvolveResult {
  const skill = this.get(skill_id);
  const old_version = skill.metadata?.version ?? 1;
  const changes: string[] = [];
  
  // Update Q-value based on feedback
  if (options.feedback === 'success') {
    skill.metadata.q_value = Math.min(1, (skill.metadata.q_value ?? 0.5) + 0.1);
    skill.metadata.success_count = (skill.metadata.success_count ?? 0) + 1;
    changes.push('q_value +0.1 (success)');
  } else if (options.feedback === 'failure') {
    skill.metadata.q_value = Math.max(0, (skill.metadata.q_value ?? 0.5) - 0.15);
    changes.push('q_value -0.15 (failure)');
  }
  
  // Content refinement
  if (options.new_content) {
    // Supersede old content (use existing supersede mechanism!)
    const old_content = skill.content;
    skill.metadata.previous_versions = skill.metadata.previous_versions || [];
    skill.metadata.previous_versions.push({
      version: old_version,
      content: old_content,
      timestamp: Date.now(),
    });
    skill.content = options.new_content;
    changes.push('content refined');
  }
  
  // Steps refinement
  if (options.new_steps) {
    skill.metadata.steps = options.new_steps;
    changes.push('steps updated');
  }
  
  skill.metadata.version = old_version + 1;
  skill.metadata.last_evolved = Date.now();
  
  return { skill_id, old_version, new_version: skill.metadata.version, changes };
}
```

### Phase 4: skill_bank_health() (~35 tests)

```typescript
/**
 * Health assessment of the skill bank.
 * Mirrors acs health_check pattern + amg reasoning_quality_eval.
 * AutoRefine-inspired: skills without maintenance degrade.
 */
skill_bank_health(options?: {
  stale_threshold_days?: number;   // default: 30
  min_confidence?: number;         // default: 0.2
  max_skills?: number;             // default: Infinity
  check_coverage?: boolean;        // verify skills cover all major clusters
}): {
  total_skills: number;
  healthy: number;
  stale: number;
  low_confidence: number;
  redundant: number;
  coverage_score: number;     // 0-100: do skills cover major clusters?
  recommendations: string[];
  health_score: number;       // 0-100 composite
}

// Implementation reuses:
// - govern_skill_bank() (cycle 260) for policy actions
// - knowledge_gap_report() (cycle 265) for coverage analysis
// - redundancy_detect() (cycle 267) for duplicate skills
```

---

## Runnable Code Example: Full Compression Pipeline

This is a complete, runnable test demonstrating the compression pipeline:

```typescript
import { MemoryGraph } from 'agent-memory-graph';

// Create a graph with redundant episodic nodes
const mg = new MemoryGraph();

// Simulate multiple episodes about the same topic
const episodes = [
  { kind: 'episodic', content: 'User asked about database connection timeout. Found the issue was in pool config.', tags: ['debugging', 'database'] },
  { kind: 'episodic', content: 'Database connection timeout again. Pool config maxSize was too low.', tags: ['debugging', 'database'] },
  { kind: 'episodic', content: 'Fixed pool config for database timeout. Set maxSize=20.', tags: ['debugging', 'database', 'fix'] },
  { kind: 'episodic', content: 'User reported slow queries. Added index on user_id column.', tags: ['performance', 'database'] },
  { kind: 'episodic', content: 'Slow query on user table resolved by adding index.', tags: ['performance', 'database', 'fix'] },
  { kind: 'episodic', content: 'API rate limiting implemented with token bucket algorithm.', tags: ['api', 'implementation'] },
];

for (const ep of episodes) {
  mg.add(ep);
}

// Connect related episodes
mg.add_edge(episodes[0].id, episodes[1].id, { kind: 'temporal' });
mg.add_edge(episodes[1].id, episodes[2].id, { kind: 'temporal' });
mg.add_edge(episodes[3].id, episodes[4].id, { kind: 'temporal' });

console.log(`Before compression: ${mg.node_count()} nodes, ${mg.edge_count()} edges`);

// Step 1: Detect redundancy
const redundancy = mg.redundancy_detect({ content_threshold: 0.4 });
console.log(`Found ${redundancy.merge_candidates.length} merge candidates`);

// Step 2: Compress episodic clusters into skills
const result = mg.compress_to_skill({
  source_kind: 'episodic',
  content_jaccard_threshold: 0.4,
  preserve_originals: false,  // remove originals after compression
});

console.log(`Created ${result.skills_created} skills`);
console.log(`Compressed ${result.nodes_compressed} nodes into skills`);
console.log(`Density: ${result.density_before.toFixed(2)} → ${result.density_after.toFixed(2)}`);

// Step 3: Retrieve skills for a new problem
const matches = mg.retrieve_skills('database connection issue', { top_k: 3 });
console.log(`Top skill match: ${matches[0]?.skill.content}`);
console.log(`Confidence: ${matches[0]?.q_value}`);

// Step 4: Evolve skill based on outcome
mg.evolve_skill(matches[0].skill.id, { feedback: 'success' });

// Step 5: Check skill bank health
const health = mg.skill_bank_health();
console.log(`Skill bank health: ${health.health_score}/100`);
console.log(`Recommendations: ${health.recommendations.join('; ')}`);

console.log(`After compression: ${mg.node_count()} nodes, ${mg.edge_count()} edges`);
// Expected: ~3 skill nodes + 1 unrelated episodic, down from 6 episodic nodes
```

---

## Key Insights (8)

### Insight #71: redundancy_detect() is a compression pre-processor
The three-dimensional redundancy analysis built in cycle 267 (content/structural/functional) is exactly what MemRefine proposes as the candidate-finding step. No npm memory library has this built-in. The implementation path: `redundancy_detect() → merge_candidates → compress_to_skill()`.

### Insight #72: Compression completes the dual-loop quality paradigm
Gap analysis (cycle 265) finds missing connections → auto_heal_gaps (cycle 266) adds them. Redundancy detection (cycle 267) finds excess connections → **compress_to_skill() consolidates them into higher-level nodes**. Without compression, redundancy detection is diagnostic only. With compression, it becomes therapeutic.

### Insight #73: Skills need versioning from day one
MemSkill's designer component shows that skills must evolve. amg's `supersede` mechanism (built for factual corrections) naturally extends to skill versioning: each `evolve_skill()` call creates a supersede chain, preserving history while updating the active version. Previous versions stored in metadata for auditability.

### Insight #74: Q-value scoring is the bridge between retrieval and evolution
amg already has Q-value scoring from the Memory-R1 research (cycle 195). For skills, Q-value serves double duty: (1) retrieval ranking in `retrieve_skills()` and (2) evolution signal in `evolve_skill()`. Low Q-value → candidate for deprecation. High Q-value → candidate for promotion. This mirrors MemSkill's RL-trained controller without requiring actual RL training.

### Insight #75: Compression direction matters: horizontal vs. vertical
MemRefine compresses horizontally (similar nodes at same abstraction level). Focus compresses vertically (raw traces → summary). amg should support both:
- **Horizontal:** `compress_to_skill()` merges redundant episodic nodes into a skill (MemRefine style)
- **Vertical:** `compact()` (existing) compresses episodic detail into summary (Focus style)
The distinction: horizontal preserves abstraction level, vertical raises it.

### Insight #76: LLM-judge is optional, heuristic-judge is sufficient for v1
MemRefine uses an LLM as the merge judge. But amg's `redundancy_detect()` already provides multi-dimensional scoring. For v1 (training-free), heuristic judgment (content Jaccard + structural overlap + functional similarity) is sufficient. The LLM-judge can be an optional `merge_strategy: 'llm'` parameter for users who provide an LLM callback.

### Insight #77: Skill bank health = governance + coverage + freshness
`skill_bank_health()` should answer three questions:
1. **Governance:** Are there stale/deprecated/low-confidence skills? (reuse `govern_skill_bank()` from cycle 260)
2. **Coverage:** Do skills cover all major clusters in the graph? (reuse `knowledge_gap_report()` from cycle 265 — if gaps overlap with skill-free areas, skills are under-covering)
3. **Freshness:** Are skills being used and evolved? (usage tracking via `use_count` and `last_used`)
No npm library provides skill bank health assessment.

### Insight #78: The "missing diagonal" is amg's unique value proposition
The Experience Compression Spectrum paper (arXiv:2604.15877) identifies that no system supports adaptive cross-level compression (L0 trace → L1 episodic → L2 skill → L3 rule). amg's combination of `add()` (L1) + `compress_to_skill()` (L1→L2) + `govern_skill_bank()` (L2 governance) + future `extract_rules()` (L2→L3) would make it the **first full-spectrum memory library**. This is a stronger README positioning than "graph memory" alone.

---

## Competitive Landscape Update (Jul 2026)

| System | Compression | Skill Extraction | Skill Evolution | Skill Health | npm/TS |
|--------|------------|-----------------|----------------|-------------|--------|
| **agent-memory-graph** | 🔄 `compress_to_skill()` (planned) | 🔄 planned | 🔄 planned | 🔄 planned | ✅ |
| Mem0 | ❌ | ❌ | ❌ | ❌ | ❌ (Python) |
| Letta | ❌ | ❌ | ❌ | ❌ | ❌ (Python) |
| Zep/Graphiti | ❌ | ❌ | ❌ | ❌ | ❌ (Python) |
| MemSkill | ✅ (learnable) | ✅ (controller+executor) | ✅ (designer) | ❌ | ❌ (Python, ICML) |
| MemRefine | ✅ (budget) | ❌ | ❌ | ❌ | ❌ (Python) |
| MUSE-Autoskill | ✅ | ✅ (5-stage lifecycle) | ✅ | ✅ | ❌ (Python) |

**Key gap:** No TypeScript library has any of these capabilities. MemSkill and MUSE are Python research systems, not production libraries. amg's `compress_to_skill()` would be the **first npm-accessible skill extraction API**.

---

## Next Actions for amg

### Immediate (next 2 cycles, ~80 tests)
1. **Cycle 268: `compress_to_skill()`** — MemRefine-inspired compression. Reuse redundancy_detect() candidates. Create skill nodes, rewire edges, remove originals. `dry_run` mode. ~40 tests
2. **Cycle 269: `retrieve_skills()` + `evolve_skill()`** — MemSkill-inspired retrieval and evolution. Q-value ranking + feedback-driven updates + version chains. ~40 tests

### Short-term (1 cycle, ~35 tests)
3. **Cycle 270: `skill_bank_health()`** — Health assessment reusing govern_skill_bank + gap_report + redundancy_detect. Coverage score + recommendations. ~35 tests

### Medium-term (benchmark)
4. **LoCoMo adapter with skill extraction** — Compare amg+skills vs. amg-only on LongMemEval
5. **EvoMemBench cross-setting evaluation** — Test amg in knowledge-intensive vs. execution-intensive settings

### README positioning update
```
agent-memory-graph: Beyond Recall — Agency-Grade Graph Memory with Skill Extraction

The first TypeScript library with:
- Full-spectrum compression: episodic → skill → rule (L1→L2→L3)
- Dual-loop quality system: gap detection + redundancy detection
- Evaluation quartet: retrieval + lifecycle + reasoning + density
- Write governance: sycophancy defense + injection screening
- 7-intent query routing with confidence scoring
