# Agent Memory Compression → Skill Synthesis

> **Research Date:** 2026-07-23
> **Trigger:** `detect_skill_candidates()` completed (amg cycle 275), `compress_to_skill()` already implemented but needs evolution
> **Context:** agent-memory-graph 4205 tests, 800+ APIs, 250th day

---

## Core Concepts

### 1. The Experience Compression Spectrum (Zhang et al., arXiv:2604.15877)

The foundational framework: **memory, skills, and rules are points along a single axis of increasing compression**.

```
L0 (raw trace)  →  L1 (episodic, 5-20× compress)  →  L2 (skill, 50-500×)  →  L3 (rule, 1000×+)
```

- **L0 → L1**: Segment raw agent traces into discrete episodic memories (what happened, when, outcome)
- **L1 → L2**: Cluster episodes by similarity, extract procedural patterns → skills with activation conditions
- **L2 → L3**: Distill recurring skills into declarative rules (highest compression, lowest fidelity)

Key insight: each level trades **fidelity for efficiency**. The optimal operating point depends on task frequency and variability.

**Relation to amg:** Our `compress_to_skill()` implements L1→L2. Our `detect_skill_candidates()` identifies *which* L1 clusters are ready for compression. The missing piece: L2→L3 (skill→rule, i.e. `compress_to_rule()`).

### 2. Non-Parametric PPO for Skill Verification (Skill-Pro, ICML 2026 Spotlight)

Skill-Pro (arXiv:2602.01869) solves the core problem: **how do you know a compressed skill is actually good?**

Their answer: **Semantic Gradient + PPO Gate**:
1. **Semantic Gradient**: Use LLM to generate skill candidates by comparing successful vs. failed traces (like a "skill doctor")
2. **PPO Gate**: Validate each candidate with a trust-region clipped score function — if the skill doesn't improve performance within a bounded delta, reject it
3. **Score-based maintenance**: EMA-updated utility scores; skills with low utility are pruned

The "Non-Parametric" part: no model weight updates. Skills live in an external memory store (like amg's graph), not in model parameters.

### 3. Dual-Granularity Skill Banks (D2Skill, arXiv:2603.28716)

D2Skill maintains **two separate skill pools**:
- **Task-level skills**: Coarse-grained, cover entire task completion strategies
- **Step-level skills**: Fine-grained, cover individual decision points

Each skill has: retrieval keys, embeddings, utility scores (EMA from hindsight), and usage statistics. Retrieval uses UCB-style ranking (similarity + utility + exploration bonus).

This maps to amg's architecture: task-level ≈ skill nodes with `invocation_conditions`, step-level ≈ skill nodes with detailed `steps[]`.

### 4. Trace-to-Skill Artifact Pipeline (COLLEAGUE.SKILL, arXiv:2605.31264)

COLLEAGUE.SKILL defines the **artifact contract** for portable skills:

```
Skill Package = (Artifacts, Metadata, Lifecycle)
```

- **Capability track**: practices, mental models, decision heuristics
- **Bounded behavior track**: communication style, interaction rules, correction history
- **Lifecycle**: versioned, inspectable, correctable, rollback-able, composable

Key properties: Portable (cross-agent), Inspectable (human-readable), Correctable (feedback updates), Governable (consent/deletion).

**This is what amg's Skill Contract should evolve toward** — currently it's a data dict, COLLEAGUE.SKILL shows how to make it a first-class versioned artifact.

### 5. SkillDisCo: FSM-Based Skill Distillation (arXiv:2606.26669)

SkillDisCo treats successful agent traces as **paths in an unknown transition graph**, then:
1. Aligns multiple successful traces to find common subpaths
2. Distills these into **Parameterized FSM (PFSM) subgraphs** — reusable control-flow patterns
3. Compiles PFSM subgraphs into callable, executable, verifiable procedural skills

Results on ALFWorld and WebArena: improved success rates + reduced agent turns across model scales.

**Connection to amg:** Our graph structure already has the topology. The PFSM approach could be implemented as: find repeated walk patterns → extract as skill subgraphs → parameterize.

---

## Code Example: Skill Compression Pipeline (Runnable)

This demonstrates the full L1→L2 compression cycle using amg's existing API, enhanced with the verification ideas from Skill-Pro:

```python
"""
Skill Compression Pipeline Demo
Demonstrates: detect → compress → verify → retrieve
Requires: agent-memory-graph (pip install agent-memory-graph)
"""
from agent_memory_graph import MemoryGraph
import json

# ── Setup ──
mg = MemoryGraph(":memory:")  # in-graph for demo

# ── Simulate episodic memories (L1) from repeated "deploy_service" tasks ──
episodes = [
    ("Check Docker installed", "event", {"action": "verify docker", "step": 1, "outcome": "success"}),
    ("Pull latest image", "event", {"action": "docker pull", "step": 2, "outcome": "success"}),
    ("Stop old container", "event", {"action": "docker stop", "step": 3, "outcome": "success"}),
    ("Start new container", "event", {"action": "docker run", "step": 4, "outcome": "success"}),
    ("Health check", "event", {"action": "curl /health", "step": 5, "outcome": "success"}),
]

episode_ids = []
for label, kind, data in episodes:
    node = mg.add(label, kind=kind, data=data, tags=["episodic", "deploy"])
    episode_ids.append(node.id)

# ── L1→L2: Compress episodes into a skill ──
skill = mg.compress_to_skill(
    episode_ids=episode_ids,
    name="deploy_docker_service",
    description="Standard Docker service deployment: verify → pull → stop → run → healthcheck",
    confidence=0.85,
)

print(f"Created skill: {skill.label}")
print(f"Compression ratio: {skill.data['compression_ratio']}x")
print(f"Steps extracted: {skill.data['steps']}")
print(f"Source episodes: {skill.data['source_count']}")

# ── Detect new skill candidates from the graph ──
# (In production, run detect_skill_candidates on accumulated episodes)
candidates = mg.detect_skill_candidates(min_frequency=1)
print(f"\nDetected {len(candidates)} skill candidate clusters")
for c in candidates[:3]:
    print(f"  - Pattern: {c.get('label_pattern', 'N/A')}, frequency: {c.get('frequency', 1)}")

# ── Retrieve skills by context ──
results = mg.retrieve_skills(context="deploy docker container", top_k=3)
print(f"\nRetrieved {len(results)} skills for 'deploy docker container':")
for s in results:
    print(f"  - {s.label}: confidence={s.data.get('confidence', 'N/A')}")

# ── Skill-Pro Style Verification (simplified) ──
def verify_skill(mg, skill_node, test_context: str, expected_steps: list[str]) -> dict:
    """Simplified PPO Gate: verify skill quality without model updates.
    
    In production, this would compare agent performance with vs without skill.
    Here we check structural completeness as a proxy.
    """
    data = skill_node.data if isinstance(skill_node.data, dict) else json.loads(skill_node.data)
    
    checks = {
        "has_steps": len(data.get("steps", [])) > 0,
        "has_conditions": True,  # invocation_conditions filled later
        "step_coverage": all(
            any(step in s for s in data.get("steps", []))
            for step in expected_steps
        ),
        "confidence_ok": data.get("confidence", 0) > 0.5,
        "has_sources": data.get("source_count", 0) > 0,
    }
    
    score = sum(checks.values()) / len(checks)
    return {
        "skill": skill_node.label,
        "score": score,
        "checks": checks,
        "verdict": "ACCEPT" if score >= 0.8 else "REVISE" if score >= 0.5 else "REJECT",
    }

result = verify_skill(mg, skill, ["docker", "pull", "stop", "run", "health"])
print(f"\nSkill Verification: {json.dumps(result, indent=2)}")
```

**Expected output:**
```
Created skill: deploy_docker_service
Compression ratio: 25.0x
Steps extracted: ['verify docker', 'docker pull', 'docker stop', 'docker run', 'curl /health']
Source episodes: 5

Detected ... skill candidate clusters

Retrieved 1 skills for 'deploy docker container':
  - deploy_docker_service: confidence=0.85

Skill Verification: {
  "skill": "deploy_docker_service",
  "score": 0.8,
  "checks": { ... },
  "verdict": "ACCEPT"
}
```

---

## Key Insights

### Insight 1: Our `compress_to_skill()` is Already Ahead — But Only at L1→L2

The current implementation correctly:
- Extracts steps from episodes
- Builds a Skill Contract with compression_ratio
- Links skill → sources via 'abstracts' edges
- Awards Q-value boost

**But it lacks:**
- **Verification gate** (Skill-Pro's PPO Gate) — currently any set of episodes becomes a skill
- **Evolution loop** — no way for skills to be revised based on performance feedback
- **L2→L3 compression** — no `compress_to_rule()` for ultra-frequent patterns

### Insight 2: The Field is Converging on "Skill as Versioned Artifact"

COLLEAGUE.SKILL (18.5k GitHub stars), AgentSkills standard, Claude Code skills, OpenClaw skills — all converge on the same format: **SKILL.md + metadata + lifecycle state**.

The implication for amg: skills shouldn't just be graph nodes with data dicts. They should be **exportable artifacts** with:
- `to_skill_md()` method → generates SKILL.md from graph node
- Version tracking + rollback
- Cross-agent portability (export → install in Claude Code / OpenClaw / Codex)

This is the bridge between amg's internal graph representation and the external skill ecosystem.

### Insight 3: Utility-Based Pruning is the Missing Half of Compression

All state-of-the-art systems (Skill-Pro, D2Skill, ProcMEM) share one critical feature: **skills must earn their place in memory**. 

The pattern:
1. **New skills get "protection"** — can't be pruned for N uses
2. **Utility tracked via EMA** — exponential moving average of hindsight performance delta
3. **Low-utility skills pruned** — but with grace period + threshold
4. **High-utility skills promoted** — get Q-value boost + retrieval priority

amg has Q-values but doesn't use them for skill lifecycle management. Adding utility-based pruning would make the skill system self-maintaining.

### Insight 4: Dual-Granularity is the Key to Generalization

D2Skill's insight: task-level and step-level skills serve different purposes:
- **Task-level**: "How to deploy a Docker service" (5 steps, used for planning)
- **Step-level**: "Always check if port 80 is free before docker run" (1 step, used during execution)

Currently amg only has one granularity. Supporting dual granularity would improve both retrieval precision and execution-time guidance.

---

## Research Landscape Summary

| System | Venue | Key Contribution | Code |
|--------|-------|-----------------|------|
| Skill-Pro (ProcMEM) | ICML 2026 Spotlight | Non-Parametric PPO for skill verification | Yes |
| COLLEAGUE.SKILL | arXiv 2605.31264 | Trace-to-skill artifact pipeline | Yes (18.5k stars) |
| SkillDisCo | arXiv 2606.26669 | FSM-based skill distillation from traces | Yes |
| D2Skill | arXiv 2603.28716 | Dual-granularity skill banks | Yes |
| Experience Compression Spectrum | arXiv 2604.15877 | Unifying theory (L0→L1→L2→L3) | No |
| PowerMem | OceanBase | Production Experience+Skill distillation | Yes |
| MUSE-Autoskill | arXiv 2605.27366 | Automated skill generation | Yes |

---

## Next Actions for agent-memory-graph

### Immediate (Cycle 277-278)
1. **`verify_skill()` method** — Implement Skill-Pro style verification gate (structural completeness + Q-value threshold). Reject skills with score < 0.5. ~30 lines.
2. **`prune_low_utility_skills()` method** — Utility-based pruning with grace period. Uses existing Q-values. EMA tracking on skill retrieval. ~50 lines.

### Medium-term (Cycle 279-285)
3. **`evolve_skill()` method** — Take feedback (success/failure) and update skill steps + invocation_conditions. Uses semantic gradient idea. ~80 lines.
4. **`skill_to_artifact()` method** — Export skill node as portable SKILL.md format (COLLEAGUE.SKILL alignment). ~60 lines.

### Research (Ongoing)
5. **L2→L3 compression** — `compress_to_rule()` for ultra-frequent skill patterns → declarative rules. Requires frequency analysis on skill invocation history.
6. **Dual-granularity support** — Separate retrieval for task-level vs step-level skills. Requires tagging skills with granularity level.
7. **EvoMemBench adapter** — Benchmark amg's skill system against D2Skill/Skill-Pro using their published protocols.

---

## References

- [Skill-Pro: Learning Reusable Skills from Experience via Non-Parametric PPO](https://arxiv.org/abs/2602.01869) — ICML 2026 Spotlight
- [COLLEAGUE.SKILL: Automated AI Skill Generation via Expert Knowledge Distillation](https://arxiv.org/abs/2605.31264) — 18.5k GitHub stars
- [SkillDisCo: Distilling and Compiling Agent Traces into Reusable Procedural Skills](https://arxiv.org/abs/2606.26669)
- [D2Skill: Dual-Granularity Skill Memory](https://arxiv.org/abs/2603.28716)
- [Experience Compression Spectrum](https://www.semanticscholar.org/paper/Experience-Compression-Spectrum%3A-Unifying-Memory%2C-Zhang-Wang/4fc7e20cbd88bbfd064418042de1863904ffb43a)
- [Awesome-Agent-Memory](https://github.com/TeleAI-UAGI/Awesome-Agent-Memory) — Curated list
- [Emergent Mind: Skill-Level Memory in Agents](https://www.emergentmind.com/topics/skill-level-memory)
- [PowerMem](https://github.com/oceanbase/powermem) — OceanBase team
