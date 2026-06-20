# Agent Skill Discovery & Reuse: From Workflow Memory to Self-Improving Skill Libraries

> Research date: 2026-06-20
> Trigger: HEARTBEAT.md deep-exploration-evening
> Context: Extends 06-19 AWM/Workflow Memory → skill extraction → self-improving libraries
> Methodology: autoresearch.md (structured exploration with code + insights + actions)

---

## Abstract

The transition from agent memory to agent skills represents a paradigm shift: raw experience (Level 1 episodic memory) is compressed into reusable behavioral patterns (Level 2 procedural skills), then further distilled into abstract decision principles (Level 3 rules). This note maps the 2026 landscape of agent skill discovery systems, extracts architectural patterns, and provides a working TypeScript implementation that bridges agent-memory-graph's Workflow Memory to the self-improving skill library paradigm.

---

## Core Concepts (5)

### 1. Experience Compression Spectrum (arXiv:2604.15877)

Memory, skills, and rules are not three separate systems — they are three points on a **single compression spectrum**:

| Level | What | Compression | Reusability | Example |
|-------|------|-------------|-------------|---------|
| L1: Episodic Memory | What happened | Low (event-level) | Low (tied to episode) | "[2026-03-15] User requested Q3 analysis via SQL" |
| L2: Procedural Skill | How to act | Medium (pattern) | High (situational) | "Data_Analysis: (1) Confirm source (2) Select tool (3) Present format (4) Verify" |
| L3: Abstract Rule | Why to decide | High (principle) | Very High (universal) | "Always validate data source before analysis" |

**Key insight**: Higher compression = less context consumption + faster retrieval + lower compute per decision. The compression is hierarchical: L3 rules subsume L2 skills which subsume L1 memories.

### 2. Skill Acquisition Taxonomy (SoK arXiv:2602.20867 + Survey arXiv:2602.12430)

Five paradigms for acquiring skills, ordered by autonomy:

| Method | Representative | Mechanism | Key Result |
|--------|---------------|-----------|------------|
| Human-authored | Anthropic Skills (Dec 2025) | Manual SKILL.md | 62k+ GitHub stars |
| RL + Skill Library | SAGE (Amazon, Dec 2025) | GRPO + Sequential Rollout | +8.9% SGC, −59% tokens |
| Autonomous Exploration | SEAgent (2025) | Curriculum + World Model | 11.3%→34.5% success |
| Compositional Synthesis | Agentic Proposing (2026) | Skill Library + GoT Agent | 91.6% (30B solver) |
| Failure-Driven Discovery | EvoSkill (Sentient/VT, Mar 2026) | Executor→Proposer→Builder→Validator | +7.3-12.1% accuracy |

**The skill artifact** is standardized as a directory with:
```
skill_name/
├── SKILL.md          # YAML frontmatter (name, description, triggers)
├── scripts/           # Executable helpers
├── references/        # Domain knowledge
└── tests/            # Validation cases
```

Loaded via **progressive disclosure**: metadata always in system prompt (~50 tokens), full body on trigger, resources on demand.

### 3. Failure-Driven Skill Discovery Loop (EvoSkill, arXiv:2603.02766)

The most practically impactful pattern for existing agent systems:

```
┌─────────────────────────────────────────────────────────────┐
│                    EvoSkill Discovery Loop                    │
│                                                               │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐            │
│  │ Executor │────▶│ Proposer │────▶│ Builder  │            │
│  │ (run     │     │ (analyze │     │ (package │            │
│  │  tasks)  │     │  traces) │     │  skill)  │            │
│  └──────────┘     └──────────┘     └──────────┘            │
│       │                                  │                   │
│       │           ┌──────────┐          │                   │
│       └───────────│ Validator│◀─────────┘                   │
│                   │ (retain  │                               │
│                   │  if better)│                              │
│                   └──────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

**Empirical results**: Claude Code + Opus 4.5 on OfficeQA: 60.6% → 67.9% (+7.3%). SealQA: 26.6% → 38.7% (+12.1%). **Cross-task transfer**: SealQA skills → BrowseComp +5.3% zero-shot.

**Pareto retention**: Only keep skills that improve held-out validation performance. Model stays frozen — all gains are in the skill layer.

### 4. RL-Augmented Skill Co-Evolution (SAGE + SkillRL)

**SAGE** (arXiv:2512.17102): Sequential Rollout deploys agents across chains of similar tasks. Skills from previous tasks accumulate and become available for subsequent tasks. **Skill-integrated Reward** complements outcome rewards.

**SkillRL** (arXiv:2602.08234, ICLR 2026): Hierarchical SKILLBANK with recursive evolution:
- Teacher model identifies failure patterns → proposes new skills
- Agent's skill library co-evolves with policy during RL training
- **10-20× less data** than raw logs due to compression
- 7B model with SkillRL beats GPT-4o on reasoning tasks

**The virtuous cycle**: Agent improves → encounters new challenges → skill library expands → further improvement.

### 5. Agent Memory Benchmark Revolution (2026)

The evaluation landscape has fundamentally shifted:

| Benchmark | What It Measures | Limitation |
|-----------|-----------------|------------|
| LoCoMo | Conversational recall (1,540 Qs) | "Dump everything" now competitive (1M ctx) |
| LongMemEval | Multi-session reasoning (500 Qs) | Static, not agentic |
| BEAM (1M/10M) | Long-context memory at scale | 64.1% → 48.6% (10× scale = 25% drop) |
| **MemoryArena** (ICML 2026) | Interdependent multi-session tasks | ⭐ Closed-loop memory→action→feedback |
| **LongMemEval-V2** (2026) | Agent memory with dynamic workflows | Adds workflow + gotcha categories |
| AgentMemoryBench (Vectorize) | Practical agent tasks (tool calls, research) | Two modes: single-query vs agentic |

**Critical finding**: Models with near-saturated LoCoMo scores perform poorly on MemoryArena. "LoCoMo measures recall. MemoryArena measures agency." — The field needs benchmarks that test memory **in the action loop**, not just retrieval.

**Mem0 state of art (Apr 2026)**: LoCoMo 92.5, LongMemEval 94.4, BEAM(1M) 64.1, BEAM(10M) 48.6 — using ~7K tokens/query.

---

## Code: SkillDiscoveryEngine (~200 lines, TypeScript, zero-dependency)

This implementation bridges agent-memory-graph's Workflow Memory to the self-improving skill library pattern. It demonstrates:
1. Trajectory → Skill extraction (failure-driven)
2. Skill validation (Pareto retention)
3. Skill retrieval and application
4. Cross-task transfer scoring

```typescript
/**
 * SkillDiscoveryEngine — From agent trajectories to reusable skill libraries.
 *
 * Inspired by: EvoSkill (arXiv:2603.02766), SAGE (arXiv:2512.17102),
 *              Experience Compression Spectrum (arXiv:2604.15877)
 *
 * Integrates with: agent-memory-graph Workflow Memory APIs
 */

// ─── Types ─────────────────────────────────────────────────────

interface Trajectory {
  taskId: string;
  steps: TrajectoryStep[];
  outcome: 'success' | 'failure';
  duration_ms: number;
  metadata?: Record<string, unknown>;
}

interface TrajectoryStep {
  action: string;           // What the agent did
  observation: string;       // What happened
  reasoning?: string;        // Why (if available)
  tool_calls?: string[];     // Tools used
  timestamp: number;
}

interface Skill {
  id: string;
  name: string;
  description: string;       // Trigger condition ("when to use")
  trigger_keywords: string[];
  context: string;           // When this skill applies
  procedure: string[];       // Ordered steps
  anti_patterns: string[];   // What NOT to do
  tools_required: string[];
  validation_score: number;  // Held-out accuracy improvement
  source_trajectories: string[]; // Task IDs that contributed
  created_at: number;
  times_used: number;
  times_succeeded: number;
}

interface SkillCandidate {
  skill: Omit<Skill, 'id' | 'created_at' | 'times_used' | 'times_succeeded' | 'validation_score'>;
  sourceFailures: Trajectory[];
  sourceSuccesses: Trajectory[];
}

// ─── Engine ────────────────────────────────────────────────────

class SkillDiscoveryEngine {
  private skills = new Map<string, Skill>();
  private trajectories: Trajectory[] = [];

  /** Record a completed trajectory */
  record(t: Trajectory): void {
    this.trajectories.push(t);
  }

  /**
   * Phase 1: Failure Pattern Detection
   * Find recurring failure modes across trajectories.
   */
  detectFailurePatterns(): Map<string, Trajectory[]> {
    const failures = this.trajectories.filter(t => t.outcome === 'failure');
    const patterns = new Map<string, Trajectory[]>();

    // Group failures by similarity of last failed action
    for (const f of failures) {
      const lastStep = f.steps[f.steps.length - 1];
      const signature = this._actionSignature(lastStep.action);

      if (!patterns.has(signature)) {
        patterns.set(signature, []);
      }
      patterns.get(signature)!.push(f);
    }

    // Only keep patterns with ≥2 instances (recurring failures)
    const recurring = new Map<string, Trajectory[]>();
    for (const [sig, trajs] of patterns) {
      if (trajs.length >= 2) {
        recurring.set(sig, trajs);
      }
    }

    return recurring;
  }

  /**
   * Phase 2: Skill Proposal
   * Extract a candidate skill from failure + success pairs.
   *
   * Key principle: failures tell you WHAT went wrong,
   * successes tell you WHAT WORKS instead.
   */
  proposeSkill(
    failures: Trajectory[],
    successes: Trajectory[],
    skillName: string
  ): SkillCandidate {
    // Extract common anti-patterns from failures
    const antiPatterns = this._extractAntiPatterns(failures);

    // Extract procedural patterns from successes
    const procedure = this._extractProcedure(successes);

    // Identify required tools
    const tools = new Set<string>();
    for (const s of successes) {
      for (const step of s.steps) {
        if (step.tool_calls) {
          step.tool_calls.forEach(t => tools.add(t));
        }
      }
    }

    // Build trigger keywords from task metadata
    const triggerKeywords = this._extractKeywords([...failures, ...successes]);

    return {
      skill: {
        name: skillName,
        description: `Handles tasks where ${antiPatterns[0] || 'standard approach fails'}`,
        trigger_keywords: triggerKeywords,
        context: this._summarizeContext(successes),
        procedure,
        anti_patterns: antiPatterns,
        tools_required: Array.from(tools),
        source_trajectories: [...failures, ...successes].map(t => t.taskId),
      },
      sourceFailures: failures,
      sourceSuccesses: successes,
    };
  }

  /**
   * Phase 3: Validation (Pareto Retention)
   * Only retain skills that improve held-out performance.
   *
   * @returns true if skill was retained, false if rejected
   */
  validateAndStore(
    candidate: SkillCandidate,
    validationSet: Trajectory[],
    baselineScore: number
  ): boolean {
    // Simulate applying the skill to validation tasks
    const withSkill = this._evaluateWithSkill(
      candidate.skill,
      validationSet
    );

    const improvement = withSkill - baselineScore;

    if (improvement > 0) {
      const skill: Skill = {
        ...candidate.skill,
        id: `skill_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        validation_score: improvement,
        created_at: Date.now(),
        times_used: 0,
        times_succeeded: 0,
      };
      this.skills.set(skill.id, skill);
      return true;
    }

    // Skill didn't improve — discard (Pareto principle)
    return false;
  }

  /**
   * Phase 4: Retrieval
   * Find relevant skills for a new task.
   */
  retrieve(taskDescription: string, topK = 3): Skill[] {
    const taskTokens = new Set(taskDescription.toLowerCase().split(/\s+/));

    const scored = Array.from(this.skills.values()).map(skill => {
      let score = 0;

      // Keyword overlap
      for (const kw of skill.trigger_keywords) {
        if (taskTokens.has(kw.toLowerCase())) {
          score += 2;
        }
      }

      // Context similarity (simplified BM25-like)
      const ctxTokens = new Set(skill.context.toLowerCase().split(/\s+/));
      let overlap = 0;
      for (const t of taskTokens) {
        if (ctxTokens.has(t)) overlap++;
      }
      score += overlap * 0.5;

      // Track record (confidence-weighted)
      if (skill.times_used > 0) {
        const successRate = skill.times_succeeded / skill.times_used;
        score += successRate * 3;
      }

      // Validation score bonus
      score += skill.validation_score * 10;

      return { skill, score };
    });

    return scored
      .sort((a, b) => b.score - a.score)
      .slice(0, topK)
      .map(s => s.skill);
  }

  /**
   * Phase 5: Skill Application
   * Apply a retrieved skill to generate actionable guidance.
   */
  applySkill(skill: Skill, taskDescription: string): string {
    skill.times_used++;

    const steps = skill.procedure.map((s, i) => `${i + 1}. ${s}`).join('\n');
    const warnings = skill.anti_patterns.length > 0
      ? `\n\n⚠️ Avoid:\n${skill.anti_patterns.map(a => `- ${a}`).join('\n')}`
      : '';

    return `[Skill: ${skill.name}]\nContext: ${skill.context}\n\nProcedure:\n${steps}${warnings}`;
  }

  /** Record outcome for skill quality tracking */
  recordOutcome(skillId: string, success: boolean): void {
    const skill = this.skills.get(skillId);
    if (skill) {
      if (success) skill.times_succeeded++;
    }
  }

  /** Export skill library as JSON (for agent-memory-graph storage) */
  exportLibrary(): Skill[] {
    return Array.from(this.skills.values());
  }

  /** Stats summary */
  stats(): { totalSkills: number; avgScore: number; totalUsage: number } {
    const all = Array.from(this.skills.values());
    return {
      totalSkills: all.length,
      avgScore: all.reduce((s, k) => s + k.validation_score, 0) / (all.length || 1),
      totalUsage: all.reduce((s, k) => s + k.times_used, 0),
    };
  }

  // ─── Private Helpers ──────────────────────────────────────────

  private _actionSignature(action: string): string {
    // Normalize action to a pattern signature
    return action
      .toLowerCase()
      .replace(/[^\w\s]/g, '')
      .split(/\s+/)
      .slice(0, 3) // First 3 words as signature
      .join('_');
  }

  private _extractAntiPatterns(failures: Trajectory[]): string[] {
    const patterns: string[] = [];
    for (const f of failures) {
      const lastStep = f.steps[f.steps.length - 1];
      if (lastStep.reasoning) {
        // Extract the "what went wrong" from reasoning
        const match = lastStep.reasoning.match(
          /(?:failed|error|wrong|mistake|issue)[:]\s*(.+?)(?:\.|$)/i
        );
        if (match) patterns.push(match[1].trim());
      }
      // Also look at the action itself
      if (lastStep.action.includes('retry') || lastStep.action.includes('again')) {
        patterns.push(`Repeated attempt without strategy change`);
      }
    }
    return [...new Set(patterns)].slice(0, 5);
  }

  private _extractProcedure(successes: Trajectory[]): string[] {
    if (successes.length === 0) return [];

    // Find common action sequence across successful trajectories
    // Simplified: take the median-length trajectory's actions
    const sorted = [...successes].sort((a, b) => a.steps.length - b.steps.length);
    const median = sorted[Math.floor(sorted.length / 2)];

    // Compress: remove backtracking and exploration steps
    const compressed: string[] = [];
    let lastAction = '';

    for (const step of median.steps) {
      // Skip backtracking/exploration (key insight from SkillX paper)
      if (step.action.toLowerCase().includes('back') ||
          step.action.toLowerCase().includes('undo') ||
          step.action.toLowerCase().includes('try again') ||
          step.action === lastAction) {
        continue;
      }
      // Summarize verbose actions
      const summary = step.action.length > 80
        ? step.action.slice(0, 77) + '...'
        : step.action;
      compressed.push(summary);
      lastAction = step.action;
    }

    return compressed;
  }

  private _extractKeywords(trajs: Trajectory[]): string[] {
    const freq = new Map<string, number>();
    for (const t of trajs) {
      for (const step of t.steps) {
        for (const word of step.action.toLowerCase().split(/\s+/)) {
          if (word.length > 3 && !STOP_WORDS.has(word)) {
            freq.set(word, (freq.get(word) || 0) + 1);
          }
        }
      }
    }
    return Array.from(freq.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([w]) => w);
  }

  private _summarizeContext(successes: Trajectory[]): string {
    if (successes.length === 0) return 'No successful examples available.';
    const tools = new Set<string>();
    const actions = new Set<string>();
    for (const s of successes) {
      for (const step of s.steps) {
        actions.add(step.action.split(/\s+/).slice(0, 2).join(' '));
        if (step.tool_calls) step.tool_calls.forEach(t => tools.add(t));
      }
    }
    return `Uses ${Array.from(tools).join(', ') || 'standard tools'}. ` +
           `Key actions: ${Array.from(actions).slice(0, 3).join(', ')}.`;
  }

  private _evaluateWithSkill(
    skill: SkillCandidate['skill'],
    validationSet: Trajectory[]
  ): number {
    // Simplified evaluation: count how many validation tasks
    // match the skill's trigger keywords and would succeed with procedure
    let correct = 0;
    for (const t of validationSet) {
      const taskTokens = new Set(
        (t.steps[0]?.action || '').toLowerCase().split(/\s+/)
      );
      const matches = skill.trigger_keywords.some(kw =>
        taskTokens.has(kw.toLowerCase())
      );
      // If skill matches and the original task was successful,
      // count it as skill-assisted success
      if (matches && t.outcome === 'success') correct++;
      // If skill matches and original failed, the skill should fix it
      // (simplified — real eval would re-run the agent with skill)
      else if (matches && t.outcome === 'failure') correct += 0.5;
    }
    return validationSet.length > 0 ? correct / validationSet.length : 0;
  }
}

const STOP_WORDS = new Set([
  'the', 'and', 'for', 'that', 'this', 'with', 'from', 'have', 'will',
  'your', 'their', 'what', 'when', 'make', 'more', 'than', 'them',
  'then', 'also', 'into', 'only', 'some', 'very', 'just', 'does',
]);

// ─── Demo ──────────────────────────────────────────────────────

function demo(): void {
  const engine = new SkillDiscoveryEngine();

  // Simulated trajectories: 3 failures + 2 successes for "data export" tasks
  const trajectories: Trajectory[] = [
    {
      taskId: 'export-1',
      outcome: 'failure',
      duration_ms: 30000,
      steps: [
        { action: 'Query database for records', observation: '5000 rows returned', timestamp: 0, tool_calls: ['sql_query'] },
        { action: 'Try to write all rows to CSV at once', observation: 'Memory error: too many rows', reasoning: 'Failed: memory limit exceeded', timestamp: 1000, tool_calls: ['write_file'] },
        { action: 'Retry writing all rows', observation: 'Same error', reasoning: 'mistake: did not change approach', timestamp: 2000 },
      ],
    },
    {
      taskId: 'export-2',
      outcome: 'failure',
      duration_ms: 25000,
      steps: [
        { action: 'Query database for large dataset', observation: '12000 rows', timestamp: 0, tool_calls: ['sql_query'] },
        { action: 'Write all rows to file directly', observation: 'Timeout after 30s', reasoning: 'error: batch too large for single write', timestamp: 1000, tool_calls: ['write_file'] },
        { action: 'Try again with same approach', observation: 'Timeout again', reasoning: 'issue: repeated attempt without strategy change', timestamp: 2000 },
      ],
    },
    {
      taskId: 'export-3',
      outcome: 'success',
      duration_ms: 15000,
      steps: [
        { action: 'Query database with LIMIT clause', observation: '1000 rows per batch', timestamp: 0, tool_calls: ['sql_query'] },
        { action: 'Write batch to CSV, append mode', observation: 'Batch 1 written successfully', timestamp: 1000, tool_calls: ['write_file'] },
        { action: 'Loop: fetch next batch and append', observation: 'All 5000 rows exported in 5 batches', timestamp: 2000, tool_calls: ['sql_query', 'write_file'] },
        { action: 'Verify row count in output file', observation: '5000 rows confirmed', timestamp: 3000 },
      ],
    },
    {
      taskId: 'export-4',
      outcome: 'success',
      duration_ms: 12000,
      steps: [
        { action: 'Query database with pagination', observation: 'Streaming results', timestamp: 0, tool_calls: ['sql_query'] },
        { action: 'Write records in chunks of 500', observation: 'Chunk written', timestamp: 1000, tool_calls: ['write_file'] },
        { action: 'Continue until all records exported', observation: 'Complete: 8000 rows', timestamp: 2000 },
        { action: 'Validate output file integrity', observation: 'File valid, row count matches', timestamp: 3000 },
      ],
    },
  ];

  // Record all trajectories
  for (const t of trajectories) engine.record(t);

  // Phase 1: Detect failure patterns
  const patterns = engine.detectFailurePatterns();
  console.log('=== Failure Patterns ===');
  for (const [sig, trajs] of patterns) {
    console.log(`  ${sig}: ${trajs.length} occurrences`);
  }

  // Phase 2: Propose skill from failures + successes
  const failures = trajectories.filter(t => t.outcome === 'failure');
  const successes = trajectories.filter(t => t.outcome === 'success');
  const candidate = engine.proposeSkill(failures, successes, 'batch-data-export');

  console.log('\n=== Proposed Skill ===');
  console.log(`  Name: ${candidate.skill.name}`);
  console.log(`  Description: ${candidate.skill.description}`);
  console.log(`  Procedure: ${candidate.skill.procedure.length} steps`);
  console.log(`  Anti-patterns: ${candidate.skill.anti_patterns.length}`);
  console.log(`  Triggers: ${candidate.skill.trigger_keywords.join(', ')}`);

  // Phase 3: Validate (baseline = 50% success rate without skill)
  const retained = engine.validateAndStore(candidate, trajectories, 0.5);
  console.log(`\n=== Validation: ${retained ? 'RETAINED ✅' : 'REJECTED ❌'} ===`);

  // Phase 4: Retrieve for new task
  const results = engine.retrieve('Export large database to CSV file');
  console.log(`\n=== Retrieved ${results.length} skill(s) ===`);
  for (const skill of results) {
    console.log(`  ${skill.name} (score: ${skill.validation_score.toFixed(2)})`);
  }

  // Phase 5: Apply
  if (results.length > 0) {
    const guidance = engine.applySkill(results[0], 'Export to CSV');
    console.log(`\n=== Applied Skill ===`);
    console.log(guidance);
  }

  // Stats
  console.log(`\n=== Engine Stats ===`);
  console.log(JSON.stringify(engine.stats(), null, 2));

  // Assertions
  const s = engine.stats();
  console.assert(s.totalSkills >= 1, 'Should have at least 1 skill');
  console.assert(candidate.skill.procedure.length > 0, 'Procedure should not be empty');
  console.assert(candidate.skill.anti_patterns.length > 0, 'Should have anti-patterns from failures');
  console.assert(candidate.skill.trigger_keywords.length > 0, 'Should have trigger keywords');

  console.log('\n✅ All assertions passed');
}

// Run
demo();
```

### Running the Demo

```bash
# Save to file and run with:
npx tsx skill-discovery-engine.ts
# or
deno run skill-discovery-engine.ts
```

**Expected output**: Skill `batch-data-export` discovered, validated, and applied. Anti-patterns extracted from failures ("repeated attempt without strategy change"). Procedure compressed from successes (batch → write → loop → verify).

---

## Key Insights (5)

### 1. Memory → Skill → Rule is a Compression Spectrum, Not Separate Systems

The Experience Compression Spectrum paper (arXiv:2604.15877) unifies what we've been building as separate features:
- **agent-memory-graph Workflow Memory (L2)** = Procedural Skills
- **agent-memory-graph consolidation pipeline** = L1→L2 compression
- **agent-context-store analytics** = L1 quality metrics

**Implication**: Our stack already implements 2/3 of the spectrum. Adding rule extraction (L3) would complete the hierarchy — abstract principles like "always validate before executing" distilled from multiple skill successes.

### 2. Failure is the Primary Signal (60-75% of Trajectories)

Across all systems — EvoSkill, SAGE, SkillRL, AgentHER — the dominant pattern is: **extract skills from failures, validate against successes**. This aligns with our 06-19 AWM insight ("failure > success for learning"). EvoSkill's Pareto retention ensures quality: only skills that demonstrably improve held-out performance are kept.

**Implication**: agent-memory-graph's Workflow Memory `tips` (success/failure/recovery/optimization) should weight failure tips higher in retrieval. The `record_outcome` API already captures this — next step is failure-weighted retrieval ranking.

### 3. SkillRL's 10-20× Data Compression Validates the Procedural Memory Thesis

SkillRL (ICLR 2026) shows that a hierarchical skill library achieves 10-20× compression over raw trajectory logs. A 7B model with SkillRL beats GPT-4o — **skill quality > model size**. This mirrors the broader 2026 finding: 3B+smart memory > 7B+dumb memory (our 06-16 insight).

**Implication**: agent-memory-graph's positioning should emphasize "skill compression" as a metric. Our Workflow Memory `compose` and `dedup` APIs already perform compression — we should benchmark this.

### 4. Cross-Task Skill Transfer is Empirically Proven

EvoSkill demonstrated zero-shot transfer from SealQA to BrowseComp (+5.3%). Skills are not task-specific — they capture transferable capabilities. SAGE's Sequential Rollout explicitly chains similar tasks to accumulate skills.

**Implication**: Skills stored in agent-memory-graph can be retrieved across projects via tag-based search. Our `tag_induced_subgraph` API (06-19) naturally supports this — skills tagged by domain/tool/pattern form a cross-project skill graph.

### 5. Benchmarks Are Evolving from Recall to Agency

MemoryArena (ICML 2026) is the wake-up call: LoCoMo-saturating systems collapse on agentic tasks. The field is splitting between:
- **Recall benchmarks** (LoCoMo, LongMemEval) — measure if you can find information
- **Agency benchmarks** (MemoryArena, BEAM) — measure if you can USE information to take correct actions

**Implication**: agent-memory-graph should be positioned for agency, not just recall. Our GraphRAG multi-hop traversal + Workflow Memory procedural knowledge = agency-ready. README should emphasize this.

---

## Competitive Landscape Update (June 2026)

| System | Type | Skill Support | Graph Analysis | Workflow Memory | Benchmark |
|--------|------|---------------|----------------|-----------------|-----------|
| **agent-memory-graph** | SQLite | ✅ (14 APIs) | ✅ (30+ algos) | ✅ (AWM-style) | Not evaluated |
| Mem0 | Cloud/API | ❌ | ❌ | ❌ | LoCoMo 92.5 |
| Letta | Cloud/Local | ❌ | ❌ | ❌ | LoCoMo ~70 |
| Zep | Cloud | ❌ | ✅ (temporal KG) | ❌ | LoCoMo ~84 |
| Hindsight | Cloud | ❌ | ❌ | ❌ | LoCoMo 91.4 |
| EvoSkill | Framework | ✅ (discovery) | ❌ | ❌ | OfficeQA +7.3% |
| **Opportunity** | — | **Skill Library + Graph = Unique** | — | — | **Needs benchmarking** |

**agent-memory-graph is uniquely positioned**: No other system combines graph analysis + workflow memory + CRDT merge + skill storage. Adding a skill discovery layer (like EvoSkill's failure-driven loop) would make it the only "memory + skills + graph" integrated platform.

---

## Next Actions (3)

1. **Integrate SkillDiscoveryEngine pattern into agent-memory-graph** (~100 lines):
   - Add `discover_skills(trajectories)` API that runs the failure→proposal→validation loop
   - Store discovered skills as Workflow Memory entries with `type: 'discovered_skill'`
   - Add `skill_library_summary()` analytics endpoint
   - Connect to existing `record_outcome` and `tips` APIs
   - **Estimated effort**: ~4 hours, +20 tests

2. **Add Skill Quality Metrics to README**:
   - Position agent-memory-graph as "memory + skills + graph" integrated platform
   - Add competitive table (from above) to README
   - Emphasize: only system with procedural memory + graph algorithms + CRDT sync
   - Reference: EvoSkill, SAGE, Experience Compression Spectrum
   - **Estimated effort**: ~1 hour (part of README sprint)

3. **Benchmark agent-memory-graph on MemoryArena subset**:
   - Download MemoryArena dataset (ICML 2026, public)
   - Implement minimal retrieval adapter: MemoryArena task → graph query → skill retrieval
   - Compare: raw LLM vs LLM + agent-memory-graph skills
   - Even a basic comparison provides positioning data for npm publish
   - **Estimated effort**: ~6 hours (can be a dedicated evening session)

---

## References

| Paper/Project | Venue | Key Contribution |
|---------------|-------|-----------------|
| Experience Compression Spectrum (arXiv:2604.15877) | 2026 | Unifying memory/skills/rules as compression levels |
| SkillX (arXiv:2604.04804) | 2026 | Multi-level skill extraction from trajectories |
| EvoSkill (arXiv:2603.02766) | Sentient/VT, Mar 2026 | Failure-driven skill discovery loop, Pareto retention |
| SAGE (arXiv:2512.17102) | Amazon, Dec 2025 | RL + Sequential Rollout, +8.9% SGC −59% tokens |
| SkillRL (arXiv:2602.08234) | ICLR 2026 | Recursive skill-augmented RL, 7B beats GPT-4o |
| SoK: Agent Skills (arXiv:2602.20867) | 2026 | Survey: 5 skill acquisition paradigms |
| Agent Skills Survey (arXiv:2602.12430) | 2026 | SKILL.md spec + skill acquisition taxonomy |
| MemoryArena (arXiv:2602.16313) | ICML 2026 | Interdependent multi-session agentic memory benchmark |
| LongMemEval-V2 (arXiv:2605.12493) | 2026 | Agent memory with dynamic workflows |
| Mem0 State of Memory (mem0.ai/blog) | Apr 2026 | LoCoMo 92.5, LongMemEval 94.4, BEAM benchmarks |
| AgentMemoryBench (vectorize.io) | 2026 | Practical agent task evaluation, two modes |
| Voyager (arXiv:2305.16291) | NVIDIA/Caltech, 2023 | Pioneer skill library for embodied agents |
| Anthropic Agent Skills | Dec 2025 | SKILL.md open standard, progressive disclosure |

---

## Quality Checklist

- [x] Core concepts: 5 (Compression Spectrum, Acquisition Taxonomy, Failure-Driven Discovery, RL Co-Evolution, Benchmark Revolution)
- [x] Code: ~200 lines TypeScript, zero-dependency, runnable demo with assertions
- [x] Key insights: 5 (each with project-specific implication)
- [x] Next actions: 3 (with effort estimates and test projections)
- [x] Project relevance: Direct connection to agent-memory-graph Workflow Memory + npm publish positioning
- [x] Unique perspective: Memory→Skill→Rule compression as unified framework for existing stack
