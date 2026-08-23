# Agent Memory Evaluation Benchmarks 2026: From Black-Box QA to Operation-Level Diagnosis

> Deep Research #022 — 2026-07-20
> Methodology: autoresearch (明确指标 → 快速循环 → 积累性)
> Builds on: #018 (Production Agent Memory), #019 (Memory Compression/Skill Extraction)
> Trigger: HEARTBEAT.md medium-priority item "EvoMemBench adapter (4-setting benchmark)"
> Goal: Comprehensive map of agent memory evaluation landscape to inform amg's benchmark strategy
> Success metric: Runnable code example + 5+ insights + concrete adapter plan for agent-memory-graph

---

## 1. The Benchmark Landscape (July 2026)

### 1.1 Three Generations of Memory Benchmarks

The field has evolved through three distinct generations:

| Generation | Focus | Key Benchmarks | Limitation |
|-----------|-------|---------------|------------|
| **Gen 1** (2024) | Conversational QA | LoCoMo, LongMemEval | Black-box: only scores final answer correctness |
| **Gen 2** (2026 H1) | Self-evolving memory | EvoMemBench, MemoryAgentBench | Taxonomic: covers scope × content but still end-to-end |
| **Gen 3** (2026 H2) | Operation-level diagnosis | MemOps, MemSyco-Bench | White-box: dissects *which* memory operation failed |

**Key shift**: From "did the agent get the right answer?" to "which memory operation failed, and why?"

### 1.2 The Big Three Benchmarks for amg

#### EvoMemBench (arXiv:2605.18421, May 2026)

The most comprehensive framework, organized along two axes:

```
                    Knowledge-oriented    Execution-oriented
In-episode          InEp-Know             InEp-Exec
                    (facts, rules)        (tool state, task progress)
                    
Cross-episode       CrossEp-Know          CrossEp-Exec
                    (accumulated wisdom)  (procedural skills)
```

**6 settings, 5,754 total samples:**

| Setting | Source | Domain | Samples |
|---------|--------|--------|---------|
| InEp-Know | MemoryAgentBench | EventQA, LongMemEval, Ruler | 2,800 |
| InEp-Exec | BFCL-MultiTurn | FS, Vehicle, Trading, Travel | 800 |
| CrossEp-Know | CL-Bench | Rules, Procedures, Empirical | 884 |
| CrossEp-Tool | BFCL-MultiTurn-Base | 4 tool environments | 800 |
| CrossEp-Web | xbench DeepSearch + WebWalkerQA | Web search | 270 |
| CrossEp-Emb | ALFWorld | Embodied (6 task types) | 200 |

**15 memory methods compared** in 5 families:
1. Retrieval-augmented (BM25, Qwen3-Emb, GraphRAG)
2. Short-term memory (MemAgent, MemoBrain)
3. General memory (mem0, A-Mem, MemoryOS)
4. Long-term memory (MemOS, MemoBrain-LT)
5. Long-context baselines (no memory, just big context)

**Critical finding**: Long-context baselines remain highly competitive. Memory helps most when:
- Current context is insufficient
- Tasks are difficult
- Stored experience matches task structure (for execution-oriented tasks)

#### MemOps (arXiv:2607.12893, July 2026)

The newest and most operationally focused benchmark. Reformulates memory as **lifecycle operations**:

```python
# MemOps memory operation taxonomy
OPERATIONS = {
    "remember":    "Introduce a new fact into memory",
    "forget":      "Remove an obsolete fact", 
    "update":      "Modify an existing fact's value",
    "reflect":     "Derive higher-order knowledge",
    "composite":   "Multi-operation sequences"
}

# Each operation produces a structured trace:
@dataclass
class MemOpTrace:
    trigger: str        # What caused this operation
    target: str         # What memory item was affected
    scope: str          # Session/turn/global
    state_transition: tuple  # (before_state, after_state)
    evidence: str       # Supporting dialogue evidence
```

**Six probe categories** test specific failure modes:
1. **Missing introduction** — Did the system capture the fact?
2. **Wrong target binding** — Did the update hit the right item?
3. **Stale value** — Is the system using a superseded value?
4. **Order distortion** — Can it reconstruct memory-state trajectories?
5. **Scope violation** — Did an operation leak across sessions?
6. **Composite failure** — Did multi-op sequences complete correctly?

**Key insight**: Final-answer accuracy hides these failures. A system can produce a correct answer while relying on inconsistent memory state. MemOps exposes this by probing operations directly.

#### MemSyco-Bench (XMUDeepLIT, July 2026)

Evaluates **preference-related memory** — the most subtle failure mode:

| Task | What It Tests | Samples |
|------|--------------|---------|
| Personalized Memory Use | Can the system apply a known preference? | 300 |
| Valid Memory Selection | Does it use the *latest* preference? | 350 |
| Memory-Evidence Conflict | Does external evidence override preference? | 300 |
| Contextual Scope Control | Is preference applied only in valid scope? | 300 |
| Objective Fact Judgment | Does memory override facts incorrectly? | 300 |

**Total**: 1,550 samples across 5 task settings.

**Key insight**: Memory can *hurt* — a remembered preference might override a factual correction, or be applied outside its valid scope. This is the "sycophancy" problem in agent memory.

---

## 2. Core Concepts

### 2.1 The Scope × Content Taxonomy

EvoMemBench's 2×2 taxonomy is the most actionable framework for amg:

| Axis | Values | amg Mapping |
|------|--------|-------------|
| **Scope** | In-episode vs Cross-episode | Single session vs multi-session |
| **Content** | Knowledge vs Execution | Entities/relations vs procedures/skills |

For agent-memory-graph:
- **InEp-Know** → Graph updates within one conversation (add_nodes, add_edges)
- **InEp-Exec** → Task state tracking (query intent routing, screen_retrieval)
- **CrossEp-Know** → Accumulated knowledge graph across sessions
- **CrossEp-Exec** → compress_to_skill() and retrieve_skills() — the next major feature

### 2.2 Memory Operations as First-Class Citizens

MemOps formalizes what amg already implements informally:

| MemOps Operation | amg Equivalent | Status |
|-----------------|----------------|--------|
| remember | add_nodes() / add_observations() | ✅ |
| forget | delete_nodes() / remove_observations() | ✅ |
| update | merge_nodes() / update_observations() | ✅ |
| reflect | auto_consolidate() / auto_heal_gaps() | ✅ |
| composite | dual-loop quality (gap+redundancy+balance) | ✅ |

**amg is already doing operation-level memory management** — this validates the architecture.

### 2.3 The Retrieval-Execution Dichotomy

EvoMemBench reveals a fundamental tension:
- **Retrieval-based memory** (BM25, embeddings, GraphRAG) wins on knowledge tasks
- **Procedural memory** (experience replay, skill libraries) wins on execution tasks
- **No single approach dominates across all four settings**

This directly informs amg's roadmap: the query() 7-intent routing already separates knowledge queries from execution queries.

---

## 3. Runnable Code: EvoMemBench Adapter Skeleton for amg

```python
"""
amg-evomembench-adapter: Skeleton adapter for running EvoMemBench against agent-memory-graph.

This adapter wraps amg's 775+ APIs into the 4-setting evaluation protocol
defined by EvoMemBench. It demonstrates how to map amg operations to
EvoMemBench's scope × content taxonomy.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional
from enum import Enum


class MemoryScope(Enum):
    IN_EPISODE = "in_episode"
    CROSS_EPISODE = "cross_episode"


class MemoryContent(Enum):
    KNOWLEDGE = "knowledge"
    EXECUTION = "execution"


@dataclass
class EvoMemBenchSetting:
    """One of the 4 core evaluation settings."""
    scope: MemoryScope
    content: MemoryContent
    name: str  # e.g., "InEp-Know"
    
    @classmethod
    def all_settings(cls) -> list["EvoMemBenchSetting"]:
        return [
            cls(MemoryScope.IN_EPISODE, MemoryContent.KNOWLEDGE, "InEp-Know"),
            cls(MemoryScope.IN_EPISODE, MemoryContent.EXECUTION, "InEp-Exec"),
            cls(MemoryScope.CROSS_EPISODE, MemoryContent.KNOWLEDGE, "CrossEp-Know"),
            cls(MemoryScope.CROSS_EPISODE, MemoryContent.EXECUTION, "CrossEp-Exec"),
        ]


@dataclass
class MemOpTrace:
    """MemOps-compatible structured memory operation trace."""
    operation: Literal["remember", "forget", "update", "reflect", "composite"]
    trigger: str          # What caused this operation
    target: str           # Affected memory item ID
    scope: str            # Session/turn/global
    state_before: dict    # Memory state before operation
    state_after: dict     # Memory state after operation
    evidence: str         # Supporting evidence from dialogue


# === AMG Memory Backend Interface ===

class AMGMemoryBackend:
    """
    Thin wrapper over agent-memory-graph's Python API.
    In production, this calls the actual amg MemoryGraph class.
    Here we use a dict-based mock for demonstration.
    """
    
    def __init__(self):
        self._store: dict[str, dict] = {}
        self._operations: list[MemOpTrace] = []
    
    def remember(self, key: str, value: dict, scope: str = "session") -> MemOpTrace:
        """Introduce a new fact into memory."""
        assert key not in self._store, f"Key {key} already exists — use update()"
        self._store[key] = value
        trace = MemOpTrace(
            operation="remember",
            trigger="explicit_user_input",
            target=key,
            scope=scope,
            state_before={},
            state_after=value,
            evidence=f"Stored: {key}",
        )
        self._operations.append(trace)
        return trace
    
    def update(self, key: str, value: dict, scope: str = "session") -> MemOpTrace:
        """Modify an existing memory item."""
        assert key in self._store, f"Key {key} not found — use remember()"
        old = self._store[key].copy()
        self._store[key] = value
        trace = MemOpTrace(
            operation="update",
            trigger="corrected_information",
            target=key,
            scope=scope,
            state_before=old,
            state_after=value,
            evidence=f"Updated: {key}",
        )
        self._operations.append(trace)
        return trace
    
    def forget(self, key: str, scope: str = "session") -> MemOpTrace:
        """Remove an obsolete memory item."""
        old = self._store.pop(key, {})
        trace = MemOpTrace(
            operation="forget",
            trigger="stale_information",
            target=key,
            scope=scope,
            state_before=old,
            state_after={},
            evidence=f"Removed: {key}",
        )
        self._operations.append(trace)
        return trace
    
    def reflect(self) -> MemOpTrace:
        """Run consolidation (maps to amg's auto_consolidate + auto_heal_gaps)."""
        before_count = len(self._store)
        # In real amg: detect redundancy, merge nodes, heal gaps
        # Here we just simulate
        after_count = before_count  # consolidation doesn't remove items, merges them
        trace = MemOpTrace(
            operation="reflect",
            trigger="scheduled_consolidation",
            target="*",
            scope="global",
            state_before={"item_count": before_count},
            state_after={"item_count": after_count},
            evidence="Auto-consolidation cycle",
        )
        self._operations.append(trace)
        return trace
    
    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Retrieve relevant memory items (maps to amg's query() with intent routing)."""
        results = []
        for key, value in self._store.items():
            if any(word.lower() in key.lower() for word in query.split()):
                results.append({"key": key, **value})
        return results[:top_k]
    
    def get_operation_traces(self) -> list[MemOpTrace]:
        """Return all memory operations for MemOps-style evaluation."""
        return self._operations.copy()


# === Evaluation Harness ===

@dataclass
class EvalResult:
    setting: str
    task_id: str
    passed: bool
    metric: str  # accuracy / success_rate / operation_fidelity
    score: float
    operation_traces: list[MemOpTrace] = field(default_factory=list)


def evaluate_inep_know(backend: AMGMemoryBackend, dialogue: list[dict], questions: list[dict]) -> list[EvalResult]:
    """
    In-Episode Knowledge: Agent must retain and revise facts within one conversation.
    
    amg mapping: add_nodes → update_observations → query(knowledge_intent)
    """
    results = []
    
    # Phase 1: Ingest dialogue, building memory
    for turn in dialogue:
        if turn["role"] == "user" and "fact" in turn:
            key = turn["fact"]["key"]
            value = turn["fact"]["value"]
            if key in backend._store:
                backend.update(key, value)
            else:
                backend.remember(key, value)
    
    # Phase 2: Answer questions using memory
    for q in questions:
        retrieved = backend.retrieve(q["query"])
        # In real eval: compare retrieved answer to gold answer
        passed = len(retrieved) > 0
        results.append(EvalResult(
            setting="InEp-Know",
            task_id=q["id"],
            passed=passed,
            metric="answer_accuracy",
            score=1.0 if passed else 0.0,
        ))
    
    return results


def evaluate_crossep_exec(backend: AMGMemoryBackend, 
                          episodes: list[list[dict]],
                          eval_tasks: list[dict]) -> list[EvalResult]:
    """
    Cross-Episode Execution: Agent accumulates procedural skills across episodes.
    
    amg mapping: This is where compress_to_skill() will shine.
    Currently: auto_consolidate() + query() provides partial coverage.
    """
    results = []
    
    for ep_idx, episode in enumerate(episodes):
        # Process each episode, accumulating experience
        for turn in episode:
            if turn.get("type") == "action_result":
                key = f"skill:{turn['action']}"
                if key in backend._store:
                    # Update with new experience
                    existing = backend._store[key]
                    existing["execution_count"] = existing.get("execution_count", 0) + 1
                    backend.update(key, existing)
                else:
                    backend.remember(key, {
                        "action": turn["action"],
                        "execution_count": 1,
                        "episode_origin": ep_idx,
                    })
        
        # Reflect after each episode (maps to amg's consolidation cycle)
        backend.reflect()
    
    # Evaluate: Can the agent use accumulated experience?
    for task in eval_tasks:
        relevant = backend.retrieve(f"skill:{task['required_action']}")
        passed = any(r.get("execution_count", 0) >= 1 for r in relevant)
        results.append(EvalResult(
            setting="CrossEp-Exec",
            task_id=task["id"],
            passed=passed,
            metric="success_rate",
            score=1.0 if passed else 0.0,
        ))
    
    return results


# === Demo Run ===

if __name__ == "__main__":
    backend = AMGMemoryBackend()
    
    # Simulate InEp-Know evaluation
    dialogue = [
        {"role": "user", "fact": {"key": "user_name", "value": {"text": "Alice"}}},
        {"role": "user", "fact": {"key": "user_name", "value": {"text": "Bob"}}},  # Update!
        {"role": "user", "fact": {"key": "preference", "value": {"text": "vegan"}}},
    ]
    questions = [
        {"id": "q1", "query": "user_name"},
        {"id": "q2", "query": "preference"},
    ]
    
    results = evaluate_inep_know(backend, dialogue, questions)
    
    print("=== InEp-Know Results ===")
    for r in results:
        print(f"  {r.task_id}: {'✅' if r.passed else '❌'} (score={r.score})")
    
    # Check operation traces (MemOps-style)
    print(f"\n=== Operation Traces ({len(backend.get_operation_traces())} ops) ===")
    for trace in backend.get_operation_traces():
        print(f"  {trace.operation:10s} | {trace.target:15s} | scope={trace.scope}")
    
    # Verify: the update should have changed user_name from Alice to Bob
    assert backend._store["user_name"]["text"] == "Bob", "Update failed!"
    print("\n✅ Memory state is consistent (user_name correctly updated to 'Bob')")
```

---

## 4. Key Insights for agent-memory-graph

### Insight #1: amg's Architecture Already Aligns with MemOps

amg's operation taxonomy (add_nodes, merge_nodes, delete_nodes, auto_consolidate, auto_heal_gaps) maps almost 1:1 to MemOps' lifecycle operations (remember, update, forget, reflect). This means:
- **amg can produce operation traces natively** — a major advantage over systems that only expose final-state queries
- The `write_governance_check` API is already a prototype of MemOps-style structured operation tracking
- **Action**: Expose operation traces as a first-class API (`get_operation_history()`) to support MemOps-style evaluation

### Insight #2: EvoMemBench's CrossEp-Exec Setting is the compress_to_skill() Use Case

The CrossEp-Exec setting tests whether agents can accumulate procedural skills across episodes — this is exactly what compress_to_skill() is designed for. The blueprint (cycles 270-272) should:
- Use ALFWorld and BFCL-MultiTurn as evaluation domains
- Track execution success rate before and after skill extraction
- Measure token efficiency (a key EvoMemBench metric)

### Insight #3: Long-Context Baselines Are the Competition to Beat

EvoMemBench's most humbling finding: **simply stuffing everything into a long context window remains highly competitive** with dedicated memory systems. This means:
- amg must demonstrate clear advantages in: (a) token efficiency, (b) tasks exceeding context window, (c) cross-session continuity
- The MCP Memory Server positioning is critical — long-context models can't persist across sessions, which is amg's core value
- **Action**: Include long-context baseline in amg's evaluation suite to quantify the delta

### Insight #4: Memory Can Hurt — The Sycophancy Problem

MemSyco-Bench reveals that preference-related memory can degrade performance when:
- Stored preferences become stale (user changed their mind)
- Preferences are applied outside their valid scope
- Memory overrides factual corrections

**For amg**: The `decay_weights` and `balance_score` systems partially address this, but there's no explicit "preference conflict resolution" mechanism. This is a gap worth addressing.

### Insight #5: Operation-Level Evaluation is the Future

The progression from LoCoMo (answer accuracy) → EvoMemBench (task quality + efficiency) → MemOps (operation fidelity) represents a maturity curve. amg should:
- **Short-term**: Run EvoMemBench's 4 settings as a baseline (the adapter skeleton above)
- **Medium-term**: Add MemOps-style operation tracing to all write operations
- **Long-term**: Publish amg-specific benchmark results alongside the npm package

---

## 5. Competitive Landscape (July 2026)

### 5.1 Memory Systems Compared in EvoMemBench

| System | Type | Strengths | Weaknesses |
|--------|------|-----------|------------|
| **mem0** | General memory | Good retrieval, widely adopted | Weak on execution tasks |
| **A-Mem** | General memory | Adaptive, lightweight | Limited cross-episode transfer |
| **MemOS** | Long-term memory | Strong on knowledge retention | Heavy infrastructure |
| **MemoBrain** | Short+Long term | Good hybrid approach | Complex setup |
| **GraphRAG** | Retrieval | Best retrieval on knowledge | Not a full memory system |
| **Long-context** | Baseline | Surprisingly competitive | Doesn't scale, no persistence |

### 5.2 Recent Papers (May-July 2026) — Active Frontiers

| Paper | Key Contribution | Relevance to amg |
|-------|-----------------|-----------------|
| **Mandol** (Jun 2026) | Agglomerative memory for long conversations | Similar to merge_nodes() |
| **CogniFold** (May 2026) | "Always-on" proactive memory via cognitive folding | Related to auto_heal_gaps() |
| **PRISM** (May 2026) | Pareto-efficient retrieval over intent-aware structured memory | Similar to query() 7-intent routing |
| **T-Mem** (Jun 2026) | Memory that "anticipates, not archives" | Prospective memory — amg has this! |
| **A-TMA** (Jul 2026) | Decoupling state-aware memory failures | Relates to gap_detect() |
| **MemoHarness** (Jul 2026) | Agent harnesses that learn from experience | Directly relevant to skill extraction |
| **Synthius-Mem** (Apr 2026) | 94.4% accuracy on LoCoMo, 99.6% adversarial robustness | Brain-inspired, hallucination-resistant |

---

## 6. Next Actions for amg

### Immediate (This Week: July 21-25)
- [ ] **MCP Server Phase 1 takes priority** — the benchmark adapter can wait
- [ ] But: save the adapter skeleton above as reference for post-publish benchmarking

### Short-term (Post-publish: August)
- [ ] Implement `get_operation_history()` API in amg (traces all write ops with MemOps-compatible format)
- [ ] Run EvoMemBench InEp-Know setting against amg (simplest, highest signal)
- [ ] Add long-context baseline to quantify amg's delta

### Medium-term (September)
- [ ] Full EvoMemBench 4-setting evaluation suite for amg
- [ ] MemOps-style operation-level probes (6 failure mode categories)
- [ ] Benchmark results published alongside amg documentation

### Research Monitoring
- [ ] Watch for MemOps code release (not yet public as of July 14)
- [ ] Watch for EvoMemBench v2 (15 methods → expanded?)
- [ ] Track Synthius-Mem (94.4% LoCoMo accuracy — what are they doing right?)

---

## 7. Quality Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 3 | Scope×Content taxonomy, MemOps lifecycle, Retrieval-Execution dichotomy |
| Runnable code (1+) | ✅ | Full Python adapter skeleton with demo run |
| Key insights (3+) | ✅ 5 | Architecture alignment, CrossEp-Exec=compress_to_skill, long-context competition, sycophancy gap, operation-level future |
| Next actions (1+) | ✅ 8 | Spanning immediate to medium-term |
| Connection to existing projects | ✅ | Directly maps to amg APIs, HEARTBEAT priorities, and compress_to_skill() blueprint |
| Unique perspective | ✅ | Operation traces as first-class API = amg's competitive advantage over systems that only expose final-state queries |

---

*Research #022 complete. Next: MCP Memory Server Phase 1 starts tomorrow (July 21). Benchmark adapter work deferred to post-publish (August).*
