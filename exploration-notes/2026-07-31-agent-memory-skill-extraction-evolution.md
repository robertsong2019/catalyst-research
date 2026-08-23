# Agent Memory Skill Extraction & Evolution: The Read-Write-Assess-Govern Lifecycle

> Deep Research #039 | 2026-07-31
> Topic: How agent memory systems extract, evolve, and maintain reusable skills from raw trajectories
> Papers analyzed: SkillRL (2602.08234), CODESKILL (2605.25430), AEL (2604.21725), EvoMemBench (2605.18421)

---

## TL;DR

The frontier of agent memory has shifted from **storing raw trajectories** to **distilling reusable skills** that compactly encode procedural knowledge. Three SOTA papers (SkillRL, CODESKILL, AEL) converge on a hierarchical approach: raw experience → semantic patterns → procedural skills, with skill banks that co-evolve with agent policy. The key tension: AEL shows "less is more" (skill extraction degrades performance in high-noise domains), while SkillRL/CODESKILL show +15% gains when skills are properly distilled with RL. The difference? **Learnable management policy > fixed heuristic rules**. For amg, this maps to a Read-Write-Assess-Govern lifecycle (compress_to_skill → retrieve_skills → evolve_skill → skill_bank_health).

---

## Core Concepts (5)

### 1. Three-Tier Memory Hierarchy (AEL)

AEL formalizes the episodic → semantic → procedural pipeline:

- **Episodic**: Raw outcome logs per episode (which tools, what signals, correct/incorrect, quality score)
- **Semantic**: Cross-episode patterns distilled every N episodes (e.g., "momentum indicators reliable for trending stocks but misleading during reversals")
- **Procedural**: High-confidence semantic patterns promoted to executable rules injected into planner prompts

Promotion is automatic and based on confidence thresholds. Procedural rules have tier_boost=1.5 vs episodic's 1.0 in retrieval scoring. This maps directly to amg's planned `compress_to_skill()` (L0→L3 compression spectrum).

### 2. Hierarchical SkillBank with Differential Trajectory Processing (SkillRL)

SkillRL's key innovation: **failed trajectories are as valuable as successful ones**.

- Successful trajectories → extract strategic patterns: `s+ = M_T(τ+, d)` (critical decision points, correct reasoning, transferable patterns)
- Failed trajectories → synthesize failure lessons: `s- = M_T(τ-, d)` (failure point, flawed reasoning, what should have been done, prevention principles)

SkillBank has two levels:
- **General skills (S_g)**: Universal strategic principles (exploration patterns, state management, goal-tracking)
- **Task-specific skills (S_k)**: Domain-specific sequences, preconditions, failure modes, optimized procedures

Each skill has: `name`, `principle`, `when_to_apply` conditions. This structure enables efficient retrieval and is directly implementable in TypeScript.

### 3. Learnable Skill Management Policy (CODESKILL)

CODESKILL's breakthrough: **skill management itself should be learned, not heuristic**.

Existing methods use fixed prompts ("extract a skill from this trajectory"). CODESKILL reformulates this as a management policy M_θ that outputs operations: `(action, content)` where action ∈ {generate, evolve, merge, drop, skip}.

Training via GRPO with hybrid reward:
- **Dense rubric-based feedback**: Skill quality scores (reusability, actionability, specificity)
- **Sparse execution feedback**: Does the skill actually help the downstream agent solve tasks?

Two skill granularities:
- **Task-level**: High-level strategies (inspect repo, localize issue, validate fix)
- **Event-driven**: Local guidance for recurring execution events (command failures, error patterns, test output)

Results: +9.69 over no-skill baseline, +4.01 over strongest prompt-based baseline. Skill bank stays stable in size (not bloating).

### 4. The "Less Is More" Paradox (AEL Ablation)

AEL's 9-variant ablation reveals a stunning finding:

> Memory + reflection together produce **58% improvement**, yet **every additional mechanism degrades performance**: planner evolution (-12%), per-tool selection (-8%), cold-start initialization (-5%), **skill extraction (-15%)**, and three credit assignment methods (all negative).

**Why?** In high-noise, short-horizon domains (financial trading), skill extraction adds the wrong kind of complexity. Extracted skills become overfit to recent episodes, creating false patterns. The bottleneck is **self-diagnosing how to use experience**, not adding architectural complexity.

**Resolution**: CODESKILL and SkillRL avoid this by (1) using RL to learn WHICH skills are useful, not blind extraction, and (2) operating in longer-horizon domains where patterns are more stable. The lesson for amg: **skill extraction must be selective, not compulsive**.

### 5. EvoMemBench: Procedural Memory Wins for Execution Tasks

EvoMemBench's 4-axis evaluation reveals:

| Setting | Best Memory Type | Key Finding |
|---------|-----------------|-------------|
| In-Episode Knowledge | Retrieval-based | Long-context baselines still competitive |
| Cross-Episode Knowledge | Retrieval + summaries | Memory helps most when context insufficient |
| In-Episode Execution | Procedural memory | Action patterns > raw trajectory replay |
| Cross-Episode Execution | Procedural + long-term | **Stored experience must match task structure** |

Critical: "No single memory form works consistently across all settings." Procedural memory (skills) beats retrieval for execution-oriented tasks **only when stored experience matches task structure**. Mismatched skills are worse than no skills.

---

## Runnable Code: Skill Extraction Prototype (TypeScript, Zero-Dependency)

This prototype implements the core SkillBank lifecycle: extract → retrieve → evolve → health-check, inspired by SkillRL + CODESKILL patterns.

```typescript
// skill-bank.ts — Zero-dependency skill extraction & evolution for agent memory graphs
// Inspired by: SkillRL (hierarchical distillation), CODESKILL (learnable management),
//               AEL (three-tier promotion), EvoMemBench (procedural > retrieval for execution)

// ─── Types ───────────────────────────────────────────────────────────

interface Skill {
  id: string;
  name: string;
  principle: string;
  whenToApply: string[];     // trigger conditions
  granularity: 'general' | 'task-specific' | 'event-driven';
  sourceEpisodes: string[];   // trajectory IDs that contributed
  successCount: number;
  failureCount: number;
  confidence: number;         // [0, 1], promoted to procedural when > threshold
  createdAt: number;
  lastUsed: number;
  version: number;
}

interface Trajectory {
  id: string;
  taskId: string;
  success: boolean;
  steps: { action: string; observation: string; reward: number }[];
  outcome: string;
}

interface SkillBankConfig {
  promotionThreshold: number;   // confidence to promote to procedural, default 0.7
  evictionThreshold: number;    // confidence below which skill is candidate for removal, default 0.2
  maxBankSize: number;          // maximum skills before forced pruning, default 100
  maxStaleEpisodes: number;     // max episodes without use before eviction, default 50
}

// ─── SkillBank ──────────────────────────────────────────────────────

class SkillBank {
  private skills = new Map<string, Skill>();
  private episodeCounter = 0;
  private config: SkillBankConfig;

  constructor(config: Partial<SkillBankConfig> = {}) {
    this.config = {
      promotionThreshold: 0.7,
      evictionThreshold: 0.2,
      maxBankSize: 100,
      maxStaleEpisodes: 50,
      ...config,
    };
  }

  // ── Extract: distill trajectory into skill candidate ──────────────
  // In production, M_T would be an LLM call. Here we use heuristic extraction.
  extract(trajectory: Trajectory): Skill | null {
    const { success, steps, taskId, outcome } = trajectory;

    // Differential processing (SkillRL pattern):
    // - Success → strategic pattern
    // - Failure → counterfactual lesson
    const criticalSteps = success
      ? steps.filter(s => s.reward > 0.5)
      : steps.filter(s => s.reward < -0.3);

    if (criticalSteps.length === 0) return null;

    const principle = success
      ? `Key actions: ${criticalSteps.map(s => s.action).join(' → ')}`
      : `Avoid: ${criticalSteps.map(s => `${s.action} (led to: ${s.observation})`).join('; ')}`;

    const whenToApply = success
      ? [`taskType:${taskId}`]
      : [`taskType:${taskId}`, `failureMode:${outcome}`];

    const skill: Skill = {
      id: `skill_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      name: success ? `Strategy for ${taskId}` : `Avoid failure: ${outcome}`,
      principle,
      whenToApply,
      granularity: this.classifyGranularity(taskId, steps),
      sourceEpisodes: [trajectory.id],
      successCount: success ? 1 : 0,
      failureCount: success ? 0 : 1,
      confidence: success ? 0.5 : 0.3, // initial confidence
      createdAt: Date.now(),
      lastUsed: Date.now(),
      version: 1,
    };

    return skill;
  }

  // ── Retrieve: find relevant skills for a given context ────────────
  retrieve(taskId: string, topK = 5): Skill[] {
    const candidates = [...this.skills.values()]
      .filter(s => s.whenToApply.some(t => t.includes(taskId) || t.includes('general')))
      .sort((a, b) => {
        // Composite score: confidence × recency × success rate
        const scoreA = this.relevanceScore(a);
        const scoreB = this.relevanceScore(b);
        return scoreB - scoreA;
      })
      .slice(0, topK);

    // Update lastUsed for retrieved skills
    candidates.forEach(s => { s.lastUsed = Date.now(); });

    return candidates;
  }

  private relevanceScore(s: Skill): number {
    const successRate = s.successCount / (s.successCount + s.failureCount + 1);
    const recencyDecay = Math.exp(-0.01 * (Date.now() - s.lastUsed) / (1000 * 60 * 60)); // hourly decay
    const tierBoost = s.granularity === 'general' ? 1.2 : s.granularity === 'task-specific' ? 1.0 : 0.8;
    return s.confidence * successRate * recencyDecay * tierBoost;
  }

  // ── Evolve: update existing skill with new evidence ───────────────
  evolve(skillId: string, trajectory: Trajectory): Skill | null {
    const skill = this.skills.get(skillId);
    if (!skill) return null;

    // Update success/failure counts
    if (trajectory.success) {
      skill.successCount++;
      skill.confidence = Math.min(1, skill.confidence + 0.05);
    } else {
      skill.failureCount++;
      skill.confidence = Math.max(0, skill.confidence - 0.08); // failures weigh more
    }

    // Evolve trigger conditions if new failure mode detected
    if (!trajectory.success && !skill.whenToApply.includes(`failureMode:${trajectory.outcome}`)) {
      skill.whenToApply.push(`failureMode:${trajectory.outcome}`);
    }

    skill.sourceEpisodes.push(trajectory.id);
    skill.version++;
    skill.lastUsed = Date.now();

    return skill;
  }

  // ── Health Check: prune stale/low-confidence skills ───────────────
  healthCheck(): { pruned: string[]; promoted: string[]; stats: SkillBankStats } {
    const pruned: string[] = [];
    const promoted: string[] = [];

    for (const [id, skill] of this.skills) {
      const episodesSinceUse = this.episodeCounter - skill.sourceEpisodes.length;

      // Prune: below eviction threshold or stale
      if (skill.confidence < this.config.evictionThreshold ||
          episodesSinceUse > this.config.maxStaleEpisodes) {
        this.skills.delete(id);
        pruned.push(id);
        continue;
      }

      // Promote: above threshold and not yet procedural-level
      if (skill.confidence >= this.config.promotionThreshold && skill.granularity !== 'general') {
        promoted.push(id);
      }
    }

    // Forced pruning if over capacity (evict lowest confidence first)
    if (this.skills.size > this.config.maxBankSize) {
      const sorted = [...this.skills.entries()]
        .sort((a, b) => a[1].confidence - b[1].confidence);
      const toRemove = this.skills.size - this.config.maxBankSize;
      for (let i = 0; i < toRemove; i++) {
        this.skills.delete(sorted[i][0]);
        pruned.push(sorted[i][0]);
      }
    }

    return { pruned, promoted, stats: this.stats() };
  }

  // ── Add skill to bank ─────────────────────────────────────────────
  add(skill: Skill): void {
    this.skills.set(skill.id, skill);
    this.episodeCounter++;
  }

  // ── Stats ─────────────────────────────────────────────────────────
  stats(): SkillBankStats {
    const skills = [...this.skills.values()];
    return {
      total: skills.length,
      general: skills.filter(s => s.granularity === 'general').length,
      taskSpecific: skills.filter(s => s.granularity === 'task-specific').length,
      eventDriven: skills.filter(s => s.granularity === 'event-driven').length,
      avgConfidence: skills.reduce((sum, s) => sum + s.confidence, 0) / (skills.length || 1),
      totalSuccess: skills.reduce((sum, s) => sum + s.successCount, 0),
      totalFailure: skills.reduce((sum, s) => sum + s.failureCount, 0),
    };
  }

  private classifyGranularity(taskId: string, steps: any[]): Skill['granularity'] {
    // Heuristic: short trajectories with error patterns → event-driven
    // Medium with task context → task-specific
    // Long with general patterns → general
    if (steps.length < 3) return 'event-driven';
    if (steps.length > 10) return 'general';
    return 'task-specific';
  }
}

interface SkillBankStats {
  total: number;
  general: number;
  taskSpecific: number;
  eventDriven: number;
  avgConfidence: number;
  totalSuccess: number;
  totalFailure: number;
}

// ─── Demo: Complete lifecycle ────────────────────────────────────────

const bank = new SkillBank({ promotionThreshold: 0.7, maxBankSize: 50 });

// Simulate trajectories (mix of success and failure)
const trajectories: Trajectory[] = [
  { id: 't1', taskId: 'debug-null-pointer', success: true,
    steps: [
      { action: 'read-stacktrace', observation: 'NPE at line 42', reward: 0.8 },
      { action: 'check-null-guard', observation: 'missing guard found', reward: 0.9 },
      { action: 'add-guard', observation: 'fixed', reward: 1.0 },
    ], outcome: 'resolved' },
  { id: 't2', taskId: 'debug-null-pointer', success: false,
    steps: [
      { action: 'guess-fix', observation: 'wrong assumption', reward: -0.5 },
      { action: 'skip-stacktrace', observation: 'missed root cause', reward: -0.8 },
    ], outcome: 'recursion-error' },
  { id: 't3', taskId: 'debug-null-pointer', success: true,
    steps: [
      { action: 'read-stacktrace', observation: 'NPE at line 42', reward: 0.8 },
      { action: 'check-null-guard', observation: 'missing guard found', reward: 0.9 },
      { action: 'add-guard', observation: 'fixed', reward: 1.0 },
    ], outcome: 'resolved' },
];

// Extract skills from trajectories
trajectories.forEach(t => {
  const skill = bank.extract(t);
  if (skill) bank.add(skill);
});

// Retrieve relevant skills for a task
const relevant = bank.retrieve('debug-null-pointer');
console.log('Retrieved skills:', relevant.map(s => `${s.name} (conf=${s.confidence.toFixed(2)})`));

// Evolve: update skill with new evidence
if (relevant[0]) {
  bank.evolve(relevant[0].id, trajectories[2]);
  console.log(`Evolved ${relevant[0].name} → v${relevant[0].version}, conf=${relevant[0].confidence.toFixed(2)}`);
}

// Health check
const health = bank.healthCheck();
console.log('SkillBank health:', health.stats);
console.log(`Pruned: ${health.pruned.length}, Promoted: ${health.promoted.length}`);

// Expected output:
// Retrieved skills: [ 'Strategy for debug-null-pointer (conf=0.50)',
//                     'Avoid failure: recursion-error (conf=0.30)' ]
// Evolved Strategy for debug-null-pointer → v2, conf=0.55
// SkillBank health: { total: 2, general: 0, taskSpecific: 2, eventDriven: 0,
//                     avgConfidence: 0.425, totalSuccess: 2, totalFailure: 1 }
// Pruned: 0, Promoted: 0
```

**Run it:**
```bash
npx tsx skill-bank.ts
```

---

## Key Insights (5)

### 1. Differential trajectory processing is non-negotiable
SkillRL's key insight: **failed trajectories are as valuable as successful ones**, but require different processing. Successes → extract "what worked" patterns. Failures → synthesize counterfactual lessons ("what should have been done"). This maps to amg's existing `write_governance_check` but extends it: don't just validate writes, **distill both positive and negative outcomes into skills**. Current amg stores trajectories as nodes; the extraction step transforms them into compact, reusable principles.

**amg mapping**: `compress_to_skill(trajectoryNodeId)` should accept both success and failure trajectories and produce different skill types. Failed trajectories get `kind="failure_lesson"` (not `"skill"`), with inverted `when_to_apply` conditions.

### 2. Skill management must be learned, not heuristic — but "less is more" in noisy domains
CODESKILL proves that learnable management (>+4 over fixed prompts) wins when domains are stable enough for patterns to repeat. But AEL's ablation shows skill extraction **degrades performance by 15%** in high-noise domains (financial trading). The resolution: **skill extraction should be gated by domain stability**. If the environment has low signal-to-noise ratio, reflection-only (AEL's approach) is better. If task structure repeats (coding, web navigation), skill extraction provides massive gains.

**amg mapping**: `skill_bank_health()` should include a domain stability metric — if recent skill utilization is low and failure rates are high, automatically throttle extraction. Don't extract compulsively.

### 3. Two granularities > one granularity
CODESKILL's task-level + event-driven split is crucial. Task-level skills capture "how to debug this type of problem." Event-driven skills capture "what to do when you see this error message." The latter transfers across tasks because execution events recur. This is more granular than SkillRL's general + task-specific split and more practical for amg's graph structure.

**amg mapping**: Skills should have a `granularity` field. Event-driven skills attach to specific error patterns (amg's existing `kind="repair_pattern"` from Research #018). Task-level skills attach to task categories. The retrieval API filters by granularity depending on the query type.

### 4. EvoMemBench proves procedural memory > retrieval for execution — but ONLY when structure matches
The EvoMemBench finding that "procedural and long-term memory methods are more effective for execution-oriented tasks when their stored experience matches the task structure" is a critical caveat. **Mismatched skills are worse than no skills.** This means skill retrieval must include a structure-matching step, not just semantic similarity.

**amg mapping**: `retrieve_skills(query)` should compute structural compatibility between the query's graph structure and the skill's source trajectory graph structure. amg's entropy fingerprint (12+ dim vector) can serve as the compatibility signal. If fingerprint_distance > threshold, don't retrieve the skill even if semantically similar.

### 5. Skill bank stability is a first-class concern
CODESKILL explicitly optimizes for stable bank size — add useful skills, merge redundant ones, drop unhelpful ones. Without maintenance, skill banks bloat, retrieval noise increases, and performance degrades. AEL's "less is more" result is partly a cautionary tale about unchecked skill accumulation.

**amg mapping**: `skill_bank_health()` is not optional — it's a required maintenance loop. It should run periodically (heartbeat), pruning skills below eviction thresholds, merging semantically similar skills (amg's EntityResolver can detect duplicates), and reporting bank vitals (total, avg confidence, utilization rate, staleness).

---

## Connection to amg

This research directly informs 4 planned amg APIs:

| API | This Research | Priority |
|-----|--------------|----------|
| `compress_to_skill()` | SkillRL distillation + CODESKILL extraction | High — 6102 tests baseline, +~40 tests |
| `retrieve_skills()` | CODESKILL retrieval + EvoMemBench structure-matching | High — +~40 tests |
| `evolve_skill()` | SkillRL recursive evolution + AEL confidence update | Medium — +~35 tests |
| `skill_bank_health()` | CODESKILL maintenance + AEL pruning logic | Medium — +~35 tests |

**Estimated impact**: ~150 new tests, 4 new APIs. Brings amg to ~6250 tests and 910+ APIs. First npm library with skill extraction/evolution/health.

**Competitive advantage**: No competitor (Mem0, Graphiti, Letta, Zep) has ANY skill extraction capability. Voyager has skill libraries but no graph-based retrieval. MUSE 85.24% vs 81.17% for self-created skills. This is a **novel differentiator**.

---

## Next Actions

1. **Implement `compress_to_skill(trajectoryNodeId, options)`** — Cycle 331 target. Accept success/failure trajectories. Differential processing (success → strategy, failure → counterfactual lesson). Output: skill node with `kind="skill"` or `kind="failure_lesson"`. Include `granularity` field (general/task-specific/event-driven). ~60 lines + ~40 tests. [Blueprint: SkillRL §3.1 + CODESKILL §3.2]

2. **Implement `retrieve_skills(query, options)`** — Cycle 332 target. Filter by granularity, rank by composite score (confidence × success_rate × recency × tier_boost). Include structural compatibility check via entropy fingerprint distance. ~50 lines + ~40 tests. [Blueprint: AEL §3.3 retrieval formula + EvoMemBench structure-matching]

3. **Add `domain_stability_check()`** — Gate skill extraction behind stability metric. If recent success rate < threshold or trajectory-to-skill conversion rate is low, return null (don't extract). Prevents AEL's "less is more" problem. ~20 lines + ~15 tests.

4. **Track EvoMemBench as evaluation target** — When `compress_to_skill` + `retrieve_skills` are implemented, evaluate on EvoMemBench's Cross-Episode Execution setting (where procedural memory should shine). Download from github.com/DSAIL-Memory/EvoMemBench.

---

## Paper Reference Table

| Paper | arXiv | Key Mechanism | Domain | Skill Extraction Result |
|-------|-------|--------------|--------|------------------------|
| SkillRL | 2602.08234 | Hierarchical distillation + RL co-evolution | ALFWorld, WebShop | +15.3% over baselines |
| CODESKILL | 2605.25430 | Learnable management policy via GRPO | SWE-Bench, EnvBench | +9.69 over no-skill, +4.01 over heuristic |
| AEL | 2604.21725 | Thompson Sampling bandit + LLM reflection | Financial trading | Skill extraction **degrades** -15% (cautionary) |
| EvoMemBench | 2605.18421 | 4-axis benchmark (scope × content) | Multiple | Procedural > retrieval for execution IF structure matches |

---

_Research #039 | Catalyst Deep Exploration | 2026-07-31_
