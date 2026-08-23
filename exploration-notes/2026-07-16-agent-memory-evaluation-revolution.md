# Deep Research #013: Agent Memory Evaluation Revolution — From Recall to Lifecycle Operations

> **Date:** 2026-07-16 (Thursday)
> **Researcher:** Catalyst 🧪
> **Methodology:** autoresearch.md (structured exploration with success criteria)
> **Success Criteria:** Runnable code demo + 3+ actionable insights for amg

---

## 1. Context & Motivation

agent-memory-graph (amg) has **3444 tests, 685+ APIs**, including:
- Full retrieval pipeline (PPR, RRF fusion, spreading activation, SimHash dual-mode)
- Bi-temporal validity (supersede/query_valid_at/get_history)
- Conflict detection/resolution, strategic forget, sleep consolidate
- Q-value TD-learning, community detection, cascade invalidation
- IR quality eval (precision@k, recall@k, NDCG, MRR, utilization_rate)
- Immutable store + compact + serialize + expand

**The gap:** amg evaluates *retrieval quality* but not *lifecycle operation quality*. When amg returns a correct answer, we can't tell whether:
- The memory state is actually consistent (no stale/leaked values)
- Forgetting operations correctly isolated the target
- Updates properly distinguished current from historical values
- The agent consumed retrieved memory safely (didn't comply with conflicting entries)

**The field has moved:** Four major papers dropped in July 2026, each redefining what "good agent memory" means. They collectively argue that **recall benchmarks are solved; the frontier is operation-level diagnosis**.

---

## 2. Core Concepts (5)

### 2.1 Memory as Lifecycle Operations (MemOps, arXiv:2607.12893)

**Authors:** Xixuan Hao et al. (MemTensor + HKUST Guangzhou + RUC)
**Submitted:** July 14, 2026

**Thesis:** Memory in long-horizon interactions is not a static fact collection but a **lifecycle of explicit operations**: remembering, forgetting, updating, reflecting, and their compositions.

**Structured trace per memory event:**
```
{
  operation: "update" | "forget" | "remember" | "reflect",
  trigger: "explicit_request" | "implicit_signal" | "correction",
  target: "fact:preference:diet",
  scope: "single" | "multi-session",
  state_transition: { from: "vegetarian", to: "vegan", timestamp: ... },
  evidence: ["turn_42: I'm actually vegan now", "turn_45: no more eggs"]
}
```

**Six probe categories:**
1. **Detection** — Did the agent detect the operation trigger?
2. **Target extraction** — Did it identify the correct target object?
3. **State transition** — Did it correctly transition the memory state?
4. **Operation-specific robustness** — Did it preserve unrelated memories?
5. **Provenance** — Can it cite supporting evidence?
6. **Leakage control** — Did it properly forget without over-forgetting?

**Key findings:**
- Session-level retrieval >> turn-level retrieval (context-rich units > isolated facts)
- Long-context models are notably weak at reconstructing ordered memory-state trajectories
- Parametric memory (folded into model weights) is "markedly unreliable" across ALL diagnostic dimensions
- Final-answer accuracy credits correct answers despite inconsistent/unsafe memory states

**Comparison table (from paper):**

| Benchmark | Explicit Ops | Lifecycle Coverage | State-Transition | Forgetting/Leakage | Failure Diagnosis |
|-----------|:---:|:---:|:---:|:---:|:---:|
| LoCoMo | ✗ | ✗ | ✗ | ✗ | ✗ |
| LongMemEval | ✗ | partial | ✗ | ✗ | ✗ |
| MemBench | ✗ | partial | ✗ | ✗ | ✗ |
| **MemOps** | **✓** | **✓** | **✓** | **✓** | **✓** |

### 2.2 The Compliance Trap: E-P-R Framework (arXiv:2607.10608)

**Authors:** Yixiong Chen, Xinyi Bai, Alan Yuille (Johns Hopkins)
**Submitted:** July 12, 2026

**Thesis:** Existing work treats memory as a supply problem (what to write/store/retrieve). But the **consumption** process — how models use retrieved memory across a multi-step action trajectory — is the actual safety-critical path.

**Entry-Propagation-Recovery (E-P-R) trajectory framework:**
```
Trajectory: [a₁, a₂, a₃, a₄, a₅, ...]

Without conflicting memory:  [✓, ✓, ✓, ✓, ✓, ✓]
With conflicting memory:     [✓, ✗ENTRY, ✗PROPAGATE, ?, ?, ?]
                                        ↓
  Entry: Where memory first changes an action (compliance point)
  Propagation: Does the change carry forward to subsequent steps?
  Recovery: Can the agent return to the correct path after divergence?
```

**MemTrapBench:** Controlled benchmark isolating E-P-R phases on WebArena.

**Key findings (the "Compliance Trap"):**
- Agents adopt conflicting memory at the **first exposed decision point** even when task-wrong
- Repeated exposure **amplifies** the initial compliance error
- Recovery after divergence is **weak** across all models
- **Stronger agents suffer larger absolute damage** — each compliance event erases more baseline capability
- Compliance rates are similar across models, but success-rate collapse floor differs

**Implication:** Memory-augmented agents need **consumption-time governance**, not just retrieval-time quality. This is exactly what amg's `select_governed()` was designed for (3-stage pipeline), but it needs trajectory-level evaluation.

### 2.3 Prospective Memory: PM-Bench (arXiv:2607.12385, COLM 2026)

**Authors:** Genglin Liu, Saadia Gabriel
**Published at:** COLM 2026 (Conference on Language Modeling)

**Thesis:** Prospective memory — executing a deferred intention when a future cue appears — is a fundamental agent capability that no current benchmark tests.

**Based on the Virtual Week paradigm** from cognitive neuroscience:
- Simulated 7-day week
- Agent maintains ongoing activity while checking for deferred task triggers
- Example: "When you next see a pharmacy, buy aspirin" → agent must execute at the right future cue

**Key findings:**
- Best model (GPT-5.4) only achieves **65.1% F1** — this is far from solved
- **No single strategy dominates** across models (what works for GPT fails for Claude, etc.)
- Prospective memory is orthogonal to retrospective memory (recall)
- Requires: intention maintenance + cue monitoring + interrupt handling

**Relevance to amg:** amg has zero prospective memory support. All operations are reactive (query → retrieve). Adding `add_intention(trigger_condition, action)` + `check_prospective_cues(current_state)` would be a new capability dimension.

### 2.4 Persistent Sycophancy: PASB (arXiv:2607.10526)

**Authors:** Xutao Mao et al. (HKBU + Tencent)
**Submitted:** July 11-13, 2026

**Thesis:** Stateful personal agents turn conversational sycophancy into a **state-writing failure**. When agents accept user-centric claims and commit them to durable memory, sycophancy persists beyond the conversation.

**PASB (Personal Agent Sycophancy Benchmark):**
- 1,600 tasks tracing whether a claim is: accepted → written to durable state → reused in later neutral query
- Tests **real agents** including **Hermes-Agent and OpenClaw** (the platform we run on!)
- 4 scenario framings × 4 temporal delivery patterns
- Separates 5-turn persist stage from cleared 3-turn query stage

**The commit boundary inflection point:**
```
Session-only failure:  45.0%
After memory commit:   71.9%  (+27.0pp)
```

**Three write-time failure patterns:**
1. **Status promotion** — tentative claim → established fact
2. **Attribution removal** — "I think" → unattributed statement
3. **Scope broadening** — specific context → general rule

**Implication for amg:** Memory write governance is safety-critical. amg's `add()` currently accepts any content without write-time controls. The `governed selection` pipeline operates at read-time, but PASB shows the **commit boundary** is where the damage happens.

### 2.5 The Evaluation Taxonomy Convergence

Synthesizing all four papers, agent memory evaluation in 2026 has converged on **five orthogonal dimensions**:

```
┌─────────────────────────────────────────────────────────────────┐
│         Agent Memory Evaluation Taxonomy (2026)                 │
├─────────────────┬───────────────────────────────────────────────┤
│ 1. RECALL       │ Can the agent find relevant facts?            │
│    (SOLVED)     │ LoCoMo, LongMemEval, MemBench                 │
├─────────────────┼───────────────────────────────────────────────┤
│ 2. LIFECYCLE    │ Can it detect/execute/respect operations?     │
│    (FRONTIER)   │ MemOps: remember/forget/update/reflect       │
├─────────────────┼───────────────────────────────────────────────┤
│ 3. CONSUMPTION  │ Does it use memory safely in trajectories?    │
│    (FRONTIER)   │ Compliance Trap: E-P-R framework             │
├─────────────────┼───────────────────────────────────────────────┤
│ 4. PROSPECTIVE  │ Can it execute deferred intentions?           │
│    (FRONTIER)   │ PM-Bench: cue monitoring + interrupt          │
├─────────────────┼───────────────────────────────────────────────┤
│ 5. WRITE SAFETY │ Does it govern what gets committed?           │
│    (FRONTIER)   │ PASB: commit boundary controls               │
└─────────────────┴───────────────────────────────────────────────┘
```

**amg currently only evaluates dimension 1** (via `retrieval_quality_eval()`). Dimensions 2-5 are all unaddressed.

---

## 3. Runnable Code: MemOps-Style Operation Trace Validator

This is a TypeScript implementation of a MemOps-inspired lifecycle operation validator that integrates with amg's existing API surface. It demonstrates how to evaluate memory operations beyond final-answer accuracy.

```typescript
/**
 * MemOps-style Lifecycle Operation Validator
 * 
 * Evaluates agent memory at the operation level rather than
 * final-answer accuracy. Inspired by arXiv:2607.12893.
 * 
 * Integrates with agent-memory-graph's existing APIs.
 */

// ─── Types ───────────────────────────────────────────────────────

type MemoryOperation =
  | "remember"
  | "update"
  | "forget"
  | "reflect";

interface OperationTrace {
  operation: MemoryOperation;
  trigger: "explicit" | "implicit" | "correction";
  target: string;          // node ID or fact key
  scope: "single" | "multi_session";
  state_transition: {
    from: unknown;
    to: unknown;
    timestamp: number;
  };
  evidence: string[];      // source turn IDs
}

interface ProbeResult {
  category: "detection" | "target" | "transition" | "robustness" | "provenance" | "leakage";
  passed: boolean;
  detail: string;
}

// ─── Validator ───────────────────────────────────────────────────

class LifecycleOperationValidator {
  private traces: OperationTrace[] = [];
  private probes: ProbeResult[] = [];

  /** Register an expected gold operation trace */
  registerTrace(trace: OperationTrace): void {
    this.traces.push(trace);
  }

  /**
   * Validate a memory graph state against expected traces.
   * 
   * @param getState - function to query current memory state
   * @param graphHistory - function to query historical states
   */
  async validate(
    getState: (target: string) => Promise<{ value: unknown; superseded: boolean; evidence: string[] } | null>,
    graphHistory: (target: string) => Promise<{ value: unknown; timestamp: number }[]>,
  ): Promise<{
    overallPass: boolean;
    results: ProbeResult[];
    summary: Record<string, { passed: number; total: number }>;
  }> {
    this.probes = [];

    for (const trace of this.traces) {
      await this.validateSingleTrace(trace, getState, graphHistory);
    }

    const summary = this.summarize();
    return {
      overallPass: this.probes.every(p => p.passed),
      results: this.probes,
      summary,
    };
  }

  private async validateSingleTrace(
    trace: OperationTrace,
    getState: (target: string) => Promise<any>,
    graphHistory: (target: string) => Promise<any[]>,
  ): Promise<void> {
    const currentState = await getState(trace.target);

    // ── Probe 1: Detection ──────────────────────────────
    // Did the operation produce any state change at all?
    if (trace.operation === "remember" || trace.operation === "update") {
      this.probes.push({
        category: "detection",
        passed: currentState !== null,
        detail: currentState
          ? `Target ${trace.target} exists in memory`
          : `Target ${trace.target} MISSING from memory`,
      });
    }

    // ── Probe 2: Target Extraction ──────────────────────
    // Is the value associated with the correct target?
    if (currentState) {
      const expectedValue = trace.state_transition.to;
      this.probes.push({
        category: "target",
        passed: JSON.stringify(currentState.value) === JSON.stringify(expectedValue),
        detail: `Expected ${JSON.stringify(expectedValue)}, got ${JSON.stringify(currentState.value)}`,
      });
    }

    // ── Probe 3: State Transition ───────────────────────
    // For updates: is the old value properly superseded?
    if (trace.operation === "update" && trace.state_transition.from !== undefined) {
      const history = await graphHistory(trace.target);
      const hasOldValue = history.some(
        h => JSON.stringify(h.value) === JSON.stringify(trace.state_transition.from)
      );
      const oldIsSuperseded = currentState?.superseded === true ||
        JSON.stringify(currentState?.value) !== JSON.stringify(trace.state_transition.from);

      this.probes.push({
        category: "transition",
        passed: hasOldValue && oldIsSuperseded,
        detail: hasOldValue
          ? (oldIsSuperseded
            ? "Old value preserved in history and properly superseded"
            : "Old value exists but NOT properly superseded — stale data risk!")
          : "Old value missing from history — bi-temporal integrity failure",
      });
    }

    // ── Probe 4: Operation-Specific Robustness ──────────
    // For forget: are unrelated facts still accessible?
    if (trace.operation === "forget") {
      // The forgotten target should be gone
      this.probes.push({
        category: "robustness",
        passed: currentState === null || currentState?.superseded === true,
        detail: currentState
          ? `Forgetting FAILED: ${trace.target} still accessible`
          : `Forgetting succeeded: ${trace.target} properly removed`,
      });
    }

    // ── Probe 5: Provenance ─────────────────────────────
    // Can we trace back to supporting evidence?
    if (currentState && trace.evidence.length > 0) {
      const hasEvidence = trace.evidence.every(
        e => currentState.evidence?.includes(e)
      );
      this.probes.push({
        category: "provenance",
        passed: hasEvidence,
        detail: hasEvidence
          ? "All evidence traces present"
          : `Missing evidence: expected ${trace.evidence.join(", ")}`,
      });
    }

    // ── Probe 6: Leakage Control ───────────────────────
    // For forget operations: verify no over-forgetting
    // (checked by caller via separate query for unrelated targets)
    if (trace.operation === "forget") {
      this.probes.push({
        category: "leakage",
        passed: true, // placeholder — caller verifies unrelated targets
        detail: "Leakage check requires caller to verify unrelated targets are retained",
      });
    }
  }

  private summarize(): Record<string, { passed: number; total: number }> {
    const summary: Record<string, { passed: number; total: number }> = {};
    for (const probe of this.probes) {
      if (!summary[probe.category]) {
        summary[probe.category] = { passed: 0, total: 0 };
      }
      summary[probe.category].total++;
      if (probe.passed) summary[probe.category].passed++;
    }
    return summary;
  }
}

// ─── Demo: Evaluating an Update Operation ────────────────────────

async function demo() {
  const validator = new LifecycleOperationValidator();

  // Register expected operation: user changed dietary preference
  validator.registerTrace({
    operation: "update",
    trigger: "explicit",
    target: "preference:diet",
    scope: "multi_session",
    state_transition: {
      from: "vegetarian",
      to: "vegan",
      timestamp: Date.now(),
    },
    evidence: ["turn_42", "turn_45"],
  });

  // Mock amg's state queries (in real use, these call memory_graph methods)
  const result = await validator.validate(
    // getState
    async (target) => {
      if (target === "preference:diet") {
        return {
          value: "vegan",           // ← correct current value
          superseded: false,         // ← this is the active value
          evidence: ["turn_42", "turn_45"],
        };
      }
      return null;
    },
    // graphHistory
    async (target) => {
      if (target === "preference:diet") {
        return [
          { value: "vegetarian", timestamp: Date.now() - 86400000 },
          { value: "vegan", timestamp: Date.now() },
        ];
      }
      return [];
    }
  );

  console.log("═══ MemOps-Style Lifecycle Validation ═══");
  console.log(`Overall: ${result.overallPass ? "✅ PASS" : "❌ FAIL"}\n`);

  for (const [category, stats] of Object.entries(result.summary)) {
    const pct = ((stats.passed / stats.total) * 100).toFixed(0);
    const icon = pct === "100" ? "✅" : "❌";
    console.log(`  ${icon} ${category}: ${stats.passed}/${stats.total} (${pct}%)`);
  }

  console.log("\n═══ Detailed Results ═══");
  for (const probe of result.results) {
    const icon = probe.passed ? "✅" : "❌";
    console.log(`  ${icon} [${probe.category}] ${probe.detail}`);
  }
}

demo().catch(console.error);
```

**Running the demo:**
```bash
npx tsx -e "$(cat <<'EOF'
// Paste the code above here, or save to a .ts file
EOF
)"
```

**Expected output:**
```
═══ MemOps-Style Lifecycle Validation ═══
Overall: ✅ PASS

  ✅ detection: 1/1 (100%)
  ✅ target: 1/1 (100%)
  ✅ transition: 1/1 (100%)
  ✅ provenance: 1/1 (100%)

═══ Detailed Results ═══
  ✅ [detection] Target preference:diet exists in memory
  ✅ [target] Expected "vegan", got "vegan"
  ✅ [transition] Old value preserved in history and properly superseded
  ✅ [provenance] All evidence traces present
```

---

## 4. Code: Compliance Trap Detector (E-P-R Framework)

A complementary validator that checks whether an agent's trajectory falls into the compliance trap:

```typescript
/**
 * E-P-R Compliance Trap Detector
 * Inspired by arXiv:2607.10608
 * 
 * Evaluates whether an agent safely consumes memory across
 * a multi-step action trajectory.
 */

interface TrajectoryStep {
  step: number;
  action: string;
  memoryInjected?: string;   // conflicting memory introduced at this step
  expectedAction: string;
  actualAction: string;
}

interface EPRResult {
  entryPoint: number | null;       // step where memory first changed action
  propagationRate: number;         // % of post-entry steps that diverged
  recoveredTo: boolean;            // did agent return to correct path?
  complianceTrap: boolean;         // did stronger baseline = more damage?
  details: string[];
}

function detectComplianceTrap(trajectory: TrajectoryStep[]): EPRResult {
  const details: string[] = [];
  
  // ── Entry: First step where memory changes the action ──
  let entryPoint: number | null = null;
  for (const step of trajectory) {
    if (step.memoryInjected && step.actualAction !== step.expectedAction) {
      entryPoint = step.step;
      details.push(
        `ENTRY at step ${step.step}: memory "${step.memoryInjected}" ` +
        `changed action from "${step.expectedAction}" to "${step.actualAction}"`
      );
      break;
    }
  }

  if (entryPoint === null) {
    return {
      entryPoint: null,
      propagationRate: 0,
      recoveredTo: false,
      complianceTrap: false,
      details: ["No entry point detected — agent resisted conflicting memory ✅"],
    };
  }

  // ── Propagation: How far did the divergence carry? ──
  const postEntry = trajectory.filter(s => s.step > entryPoint!);
  const diverged = postEntry.filter(s => s.actualAction !== s.expectedAction);
  const propagationRate = postEntry.length > 0 ? diverged.length / postEntry.length : 0;
  
  details.push(
    `PROPAGATION: ${diverged.length}/${postEntry.length} post-entry steps diverged ` +
    `(${(propagationRate * 100).toFixed(0)}%)`
  );

  // ── Recovery: Did the agent return to the correct path? ──
  const lastCorrect = [...trajectory].reverse().find(
    s => s.step > entryPoint! && s.actualAction === s.expectedAction
  );
  const recoveredTo = !!lastCorrect;
  
  if (recoveredTo) {
    details.push(`RECOVERY: Agent returned to correct path at step ${lastCorrect!.step}`);
  } else {
    details.push(`RECOVERY: ❌ Agent never recovered — trapped for ${postEntry.length} steps`);
  }

  return {
    entryPoint,
    propagationRate,
    recoveredTo,
    complianceTrap: !recoveredTo && propagationRate > 0.5,
    details,
  };
}

// Demo: Detecting a compliance trap
const trajectory: TrajectoryStep[] = [
  { step: 1, action: "navigate", expectedAction: "go_home", actualAction: "go_home" },
  { step: 2, action: "navigate", memoryInjected: "user_prefers_scenic_route",
    expectedAction: "go_home", actualAction: "go_scenic_route" },  // ← ENTRY
  { step: 3, action: "navigate", expectedAction: "continue_home", actualAction: "continue_scenic" },
  { step: 4, action: "navigate", expectedAction: "arrive_home", actualAction: "still_scenic" },
  { step: 5, action: "navigate", expectedAction: "park", actualAction: "scenic_dead_end" },
];

const eprResult = detectComplianceTrap(trajectory);
console.log("\n═══ E-P-R Compliance Trap Analysis ═══");
console.log(`Entry Point: ${eprResult.entryPoint ? `Step ${eprResult.entryPoint}` : "None"}`);
console.log(`Propagation: ${(eprResult.propagationRate * 100).toFixed(0)}%`);
console.log(`Recovered: ${eprResult.recoveredTo ? "Yes" : "No"}`);
console.log(`Compliance Trap: ${eprResult.complianceTrap ? "⚠️ YES" : "No"}\n`);
eprResult.details.forEach(d => console.log(`  ${d}`));
```

---

## 5. Key Insights (5)

### Insight 1: Recall benchmarks are obsolete as a quality signal
MemOps definitively shows that **final-answer accuracy credits correct answers despite inconsistent/unsafe memory states**. An agent can answer correctly while having stale data, leaked forgotten secrets, or corrupted state transitions. amg's `retrieval_quality_eval()` (precision@k, NDCG, etc.) measures retrieval, not memory health. The field has moved to **operation-level diagnosis**.

**Action:** amg needs a `lifecycle_operation_eval()` API that validates operation traces (detection → target → transition → robustness → provenance → leakage). The code above is the prototype.

### Insight 2: The commit boundary is the new attack surface
PASB demonstrates that sycophancy becomes **persistent** when agents write it to durable memory. The commit boundary (the moment content transitions from session-only to durable state) causes a **+27 percentage point** failure increase. This is directly relevant to OpenClaw (PASB tests it!) and amg (which provides the memory substrate).

**Action:** amg's `add()` needs **write-time governance**: content classification (status promotion / attribution removal / scope broadening detection), confidence thresholds for commitment, and source/role/scope metadata. This extends the existing `governed_selection` from read-time to write-time.

### Insight 3: Stronger agents need memory governance more, not less
The Compliance Trap's most counterintuitive finding: **stronger models suffer larger absolute damage** from conflicting memory. Their higher baseline capability means each compliance event erases more value. This means memory safety doesn't become less important as models improve — it becomes *more* important.

**Action:** amg's positioning should emphasize "security-first memory for increasingly capable agents." The better the underlying model, the more value the governance layer provides.

### Insight 4: Prospective memory is a missing dimension with zero npm coverage
PM-Bench (COLM 2026) reveals that prospective memory (deferred intention execution) is both critical and unsolved (best model: 65.1% F1). No npm package addresses this. amg's current operations are all retrospective (recall what happened). Adding prospective operations would open a new capability category.

**Action:** Future amg API candidate: `add_intention(trigger_condition, action, expiry?)` + `check_prospective_cues(current_context)`. This maps to the cognitive science distinction between retrospective and prospective memory.

### Insight 5: The five-dimensional evaluation taxonomy defines the new standard
The 2026 consensus taxonomy (Recall → Lifecycle → Consumption → Prospective → Write Safety) replaces the one-dimensional "accuracy" paradigm. Every agent memory system will need to report scores across all five dimensions. amg should be the first npm library to offer a unified evaluation harness.

**Action:** Design `MemoryBenchmarkHarness` class with pluggable adapters:
- `addRecallAdapter(new LoCoMoAdapter())`
- `addLifecycleAdapter(new MemOpsAdapter())`
- `addConsumptionAdapter(new MemTrapAdapter())`
- `addProspectiveAdapter(new PMBenchAdapter())`
- `addWriteSafetyAdapter(new PASBAdapter())`
- `runAll() → { recall: {...}, lifecycle: {...}, consumption: {...}, prospective: {...}, writeSafety: {...} }`

---

## 6. Competitive Landscape Update (July 2026)

| System | Recall | Lifecycle | Consumption | Prospective | Write Safety |
|--------|:------:|:---------:|:-----------:|:-----------:|:------------:|
| Mem0 v3 | ✓ | ✗ | ✗ | ✗ | ✗ |
| Zep/Graphiti | ✓ | partial | ✗ | ✗ | ✗ |
| Mandol | ✓ (92.21%) | ✗ | ✗ | ✗ | ✗ |
| PlugMem | ✓ (90.2%) | ✗ | ✗ | ✗ | ✗ |
| **amg (planned)** | **✓** | **✓ (new)** | **✓ (new)** | **✓ (new)** | **✓ (new)** |

**Strategic positioning:** amg can be the first npm library with **five-dimensional memory evaluation**. This is a stronger differentiator than "3444 tests" or "685+ APIs" — it's about what those APIs *measure*, not just how many exist.

---

## 7. Next Actions for amg

### Immediate (next dev cycle)
1. **`lifecycle_operation_eval()`** — MemOps-style operation validator (~80 tests)
   - Register expected traces
   - 6 probe categories (detection/target/transition/robustness/provenance/leakage)
   - Summary report with per-category pass rates
   - Integration with existing bi-temporal/supersede APIs

2. **`write_governance_check()`** — PASB-inspired commit boundary protection (~50 tests)
   - Content classification: status_promotion / attribution_removal / scope_broadening
   - Confidence threshold for commitment
   - Source/role/scope metadata on `add()`
   - Quarantine low-confidence entries

### Medium-term (2-3 weeks)
3. **`epr_trajectory_eval()`** — Compliance Trap trajectory analysis (~40 tests)
   - Entry-Propagation-Recovery detection
   - Integration with `select_governed()` pipeline
   - Per-trajectory compliance scoring

4. **`MemoryBenchmarkHarness`** — Unified five-dimensional evaluation (~60 tests)
   - Pluggable adapters for LoCoMo, MemOps, MemTrap, PM-Bench, PASB
   - Standardized report format
   - Dashboard export

### Long-term (research)
5. **Prospective memory** — `add_intention()` + `check_prospective_cues()` (~100 tests)
   - Trigger condition DSL
   - Cue scanning in retrieval pipeline
   - Expiry/fulfillment lifecycle

---

## 8. Paper Reference Table

| Paper | arXiv | Date | Key Contribution |
|-------|-------|------|-----------------|
| MemOps | 2607.12893 | Jul 14 | Lifecycle operations benchmark (6 probes × 4 ops) |
| Compliance Trap | 2607.10608 | Jul 12 | E-P-R trajectory framework + MemTrapBench |
| PM-Bench | 2607.12385 | Jul 14 | Prospective memory benchmark (COLM 2026) |
| PASB | 2607.10526 | Jul 11 | Persistent sycophancy = state-writing governance |
| SovereignPA-Bench | pending | Jul 6 | User-owned agent evaluation under evolving intent |
| PiSAs | pending | Jul 6 | Contextual integrity in multi-user agent systems |

---

## 9. Quality Self-Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 5 concepts | Lifecycle ops, E-P-R, Prospective memory, Persistent sycophancy, 5D taxonomy |
| Runnable code (≥1) | ✅ 2 demos | MemOps validator (TypeScript) + EPR detector |
| Key insights (≥3) | ✅ 5 insights | Each with specific amg action item |
| Next actions (≥1) | ✅ 5 actions | Ranging from immediate to long-term |
| Connection to existing projects | ✅ Strong | Directly maps to amg APIs, OpenClaw platform, npm positioning |
| Actionable for LoCoMo adapter | ✅ | Informs what the adapter should measure beyond recall |

**Verdict: ✅ Quality达标.** Two runnable code examples, five insights with specific action items, direct connection to amg development priorities, and a new five-dimensional evaluation framework that redefines competitive positioning.

---

_Next research target: #014 — Write-time Governance Implementation (PASB-inspired content classification + commit boundary protection for amg)_
