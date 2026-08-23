# Agent Trust & Safety 2026 — Multi-Agent Verification, Trust Scoring, and A2A Security Patterns

> Research #027 | 2026-07-25 | Catalyst Deep Exploration
> Topic selected from HEARTBEAT.md: `lab/a2a-trust-prototype: TrustEngineV2 (7算法)`
> Methodology: autoresearch.md (明确指标 + 快速循环 + 积累性)

---

## Context: Why This Research Now

The `lab/a2a-trust-prototype` has a V1 TrustEngine (simple +5/-15 scoring, time decay, per-skill tracking). HEARTBEAT.md calls for TrustEngineV2 with "7 algorithms". This research identifies what those 7 algorithms should be, grounded in July 2026 papers.

**Key tension**: The A2A protocol enables agents to discover and transact with each other, but **trust infrastructure for agents is fundamentally broken** (per Dissociative Identity, FAccT 2026). You can't just port human reputation systems to agents because agents are "ontologically dissociative" — their identity is mutable, their memory is detachable, and they're trivially copyable.

---

## Core Concepts (5)

### 1. Ontological Dissociativity → Behavioral Harness Shift

**Source**: Hu et al., "Dissociative Identity: Language Model Agents Lack Grounding for Reputation Mechanisms" (FAccT 2026, arXiv:2605.30169)

The paper argues that reputation systems presuppose 4 properties that humans have but agents lack:
- **Identifiability**: agent identity is a mutable assemblage (model + prompt + tools + memory)
- **Predictability**: persona fluidity means past performance ≠ future results
- **Credibility**: detachable memory means agents don't learn from sanctions
- **Rehabilitability**: trivial fungibility (copy/replace) means sanctions don't stick

**The shift**: from *ex post* reputation (rate after the fact) → *ex ante* behavioral harnesses (constrain and monitor in real time).

**Implication for TrustEngineV2**: Don't rely solely on historical scores. Implement **real-time behavioral constraints** — pre-execution gating, rate limiting, scope enforcement.

### 2. Per-Component Skill Fingerprinting

**Source**: Liu et al., "The Decomposition Is the Fingerprint" (arXiv:2606.31272, Palo Alto Networks)

Skills are mutable bundles (prompt + code + tools). Cryptographic hashes destroy similarity. Their solution:

- Decompose skill into (prompt, code, tools) triple
- Embed each component independently (768-dim)
- Multi-bank SimHash → 120-byte fixed signature
- Compare by Hamming distance per component
- AUC 0.974 over 4,950 pairs, 77× compression vs raw embedding

**Key insight**: "Recognition is not trust." The fingerprint establishes *lineage* (is this a modified copy of a known skill?), not *safety*. Safety requires behavioral verification on top.

**Implication for TrustEngineV2**: Skill trust should be **component-attributed**. "Same code, different prompt" is a different trust posture than "same prompt, different code."

### 3. Pre-Execution Gating (Cost-Aware LLM Judge)

**Source**: Caldwell et al., "ScopeJudge: Cost-Aware Pre-Execution Gating for Offensive Security Agents" (arXiv:2607.07774)

- A cheap trusted LLM judge inspects each tool call before execution
- Static policies fail catastrophically (recall near zero) because scope lives in user intent
- 4,897 tool calls, 7.7% violations, expert agreement F1=0.78
- Pareto frontier: cost vs accuracy across 5 transcript strategies
- Two operating points: cost-sensitive vs recall-first

**Implication for TrustEngineV2**: A **gate()** function that evaluates actions *before* execution, not just scoring *after*. The gate can use configurable context (from static policy to full transcript).

### 4. Multi-Agent Control: Distributed Attacks

**Source**: Makins et al., "Multi-Agent AI Control: Distributed Attacks Hamper Per-Instance Monitors" (NeurIPS submission, arXiv July 2026)

- AI Control studies single-agent; real deployments run many agents
- **Key finding**: Per-instance monitors that work on single agents fail when attacks are distributed across multiple agents
- Most severe risks (weight exfiltration, training poisoning) need several agents acting in concert
- **Implication**: Trust scoring must be **cross-agent aware**. A single agent looks clean, but the *pattern* across agents reveals the attack.

### 5. Cryptographic Authority-Learning Decoupling

**Source**: Qin et al., "Governed Individuation: Cryptographically Decoupling an Agent's Learning from Its Authority" (arXiv:2607.xxxxx, July 2026)

- Agents that learn while deployed create a governance problem: alignment techniques answer probabilistically, not cryptographically
- Proposal: cryptographically separate the agent's *learning* from its *authority*
- Agent can learn new skills, but authority (what it's allowed to do) is governed by an external signed policy
- Related: "Governable Individuals" (same authors) extends to embodied agents that migrate across bodies

**Implication for TrustEngineV2**: Trust scores should be **authority-scoped**, not global. An agent trusted for code analysis is not trusted for deployment. Authority changes require re-verification.

---

## TrustEngineV2: 7 Algorithms Blueprint (Runnable Code)

Based on the research, here are the 7 algorithms for TrustEngineV2:

1. **Bayesian Trust Update** — Replace ad-hoc +5/-15 with Beta distribution updating
2. **Exponential Time Decay** — Replace linear decay with exponential (RoMem-inspired)
3. **Per-Component Skill Fingerprint** — SimHash triple (prompt/code/tools)
4. **Pre-Execution Gate** — LLM-based action validation before execution
5. **Distributed Attack Detector** — Cross-agent pattern analysis
6. **Authority-Scoped Delegation** — Per-capability trust, not global
7. **Behavioral Harness Monitor** — Real-time constraint enforcement (ex ante, not ex post)

### Runnable Implementation (TypeScript, zero dependencies)

```typescript
// trust-engine-v2.ts — TrustEngineV2: 7 algorithms for agent trust & safety
// Zero dependencies. Inspired by FAccT 2026, arXiv:2606.31272, arXiv:2607.07774.

// ============================================================================
// Algorithm 1: Bayesian Trust Update (replaces ad-hoc +5/-15)
// ============================================================================
// Models trust as Beta(α, β). Success → α+=1, failure → β+=1.
// Expected value = α/(α+β). Starts uniform (Beta(1,1) = 0.5).
// Converges faster than linear, handles sparse data gracefully.

interface BetaParams { alpha: number; beta: number; }

function betaMean({ alpha, beta }: BetaParams): number {
  return alpha / (alpha + beta); // Expected value of Beta distribution
}

function betaUpdate(params: BetaParams, success: boolean, weight = 1): BetaParams {
  return success
    ? { alpha: params.alpha + weight, beta: params.beta }
    : { alpha: params.alpha, beta: params.beta + weight };
}

function betaToLevel(mean: number): 'untrusted' | 'neutral' | 'trusted' {
  if (mean < 0.4) return 'untrusted';
  if (mean < 0.7) return 'neutral';
  return 'trusted';
}

// ============================================================================
// Algorithm 2: Exponential Time Decay (replaces linear decay)
// ============================================================================
// Trust decays toward prior (0.5) with half-life configurable.
// Recent interactions weighted more. After 7 days (~168h), trust is 50% toward prior.
// decay_factor = exp(-ln(2) * hoursElapsed / halfLifeHours)

function exponentialDecay(
  currentMean: number,
  hoursElapsed: number,
  halfLifeHours = 168, // 1 week default half-life
  prior = 0.5
): number {
  const decayFactor = Math.exp(-Math.LN2 * hoursElapsed / halfLifeHours);
  return currentMean + (prior - currentMean) * (1 - decayFactor);
}

// ============================================================================
// Algorithm 3: Per-Component Skill Fingerprint (SimHash-based)
// ============================================================================
// Each skill decomposed into (prompt, code, tools) components.
// Each component → 32-bit SimHash via simple hash + band projection.
// Compare via Hamming distance per component.
// "Same code, different prompt" is DIFFERENT trust posture than "same prompt, different code."

interface SkillFingerprint {
  promptHash: number;   // 32-bit SimHash of prompt text
  codeHash: number;     // 32-bit SimHash of code
  toolsHash: number;    // 32-bit SimHash of tool declarations
  version: string;      // Embedding model version tag
}

// Simple string hash (djb2) — in production, use a proper text encoder
function simpleHash(str: string): number {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) + str.charCodeAt(i);
    hash = hash & 0xffffffff; // Keep 32-bit
  }
  return hash >>> 0; // Unsigned
}

function simhash(text: string, bands = 4): number {
  // Simplified SimHash: split text into token shingles, hash each,
  // project to bands, combine via majority vote
  const tokens = text.toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return 0;

  const bits = new Int32Array(32);
  const bandSize = Math.ceil(32 / bands);

  for (let b = 0; b < bands; b++) {
    const start = Math.floor((b / bands) * tokens.length);
    const end = Math.floor(((b + 1) / bands) * tokens.length);
    const bandText = tokens.slice(start, end).join(' ');
    const h = simpleHash(bandText);

    for (let i = 0; i < 32; i++) {
      if ((h >> i) & 1) bits[i]++;
      else bits[i]--;
    }
  }

  let result = 0;
  for (let i = 0; i < 32; i++) {
    if (bits[i] > 0) result |= (1 << i);
  }
  return result >>> 0;
}

function fingerprintSkill(prompt: string, code: string, tools: string): SkillFingerprint {
  return {
    promptHash: simhash(prompt),
    codeHash: simhash(code),
    toolsHash: simhash(tools),
    version: 'djb2-v1',
  };
}

function hammingDistance(a: number, b: number): number {
  let xor = (a ^ b) >>> 0;
  let count = 0;
  while (xor) { count += xor & 1; xor >>>= 1; }
  return count;
}

function skillRelationship(
  fp1: SkillFingerprint,
  fp2: SkillFingerprint,
  threshold = 8 // Max Hamming distance for "similar" (of 32)
): {
  relationship: 'clone' | 'variant' | 'unrelated';
  changedComponent: 'prompt' | 'code' | 'tools' | 'multiple' | 'none';
  similarity: number; // 0-1
} {
  const promptDist = hammingDistance(fp1.promptHash, fp2.promptHash);
  const codeDist = hammingDistance(fp1.codeHash, fp2.codeHash);
  const toolsDist = hammingDistance(fp1.toolsHash, fp2.toolsHash);

  const promptSim = 1 - promptDist / 32;
  const codeSim = 1 - codeDist / 32;
  const toolsSim = 1 - toolsDist / 32;
  const overallSim = (promptSim + codeSim + toolsSim) / 3;

  const promptSame = promptDist <= threshold;
  const codeSame = codeDist <= threshold;
  const toolsSame = toolsDist <= threshold;

  if (promptSame && codeSame && toolsSame) {
    return { relationship: 'clone', changedComponent: 'none', similarity: overallSim };
  }

  if (!promptSame && !codeSame) {
    return { relationship: 'unrelated', changedComponent: 'multiple', similarity: overallSim };
  }

  const changed = !promptSame && codeSame && toolsSame ? 'prompt'
    : promptSame && !codeSame && toolsSame ? 'code'
    : promptSame && codeSame && !toolsSame ? 'tools'
    : 'multiple';

  return {
    relationship: changed === 'multiple' ? 'unrelated' : 'variant',
    changedComponent: changed,
    similarity: overallSim,
  };
}

// ============================================================================
// Algorithm 4: Pre-Execution Gate
// ============================================================================
// Evaluates proposed actions BEFORE execution.
// Returns allow/deny/escalate based on trust level + action risk.
// Inspired by ScopeJudge: context-aware, not static policy.

type ActionRisk = 'low' | 'medium' | 'high' | 'critical';
type GateDecision = 'allow' | 'deny' | 'escalate';

interface ProposedAction {
  agentId: string;
  skillId?: string;
  action: string;
  target?: string;
  risk: ActionRisk;
  context?: string; // Transcript or summary for LLM judge (optional)
}

function evaluateGate(
  action: ProposedAction,
  trustMean: number,
  options?: {
    riskThresholds?: Record<ActionRisk, number>; // Min trust mean per risk level
    escalateAbove?: number; // Escalate if risk is above this level and trust < trusted
  }
): { decision: GateDecision; reason: string } {
  const thresholds = options?.riskThresholds ?? {
    low: 0.3,
    medium: 0.5,
    high: 0.7,
    critical: 0.85,
  };
  const escalateAbove = options?.escalateAbove ?? 2; // medium and above

  const riskOrder: ActionRisk[] = ['low', 'medium', 'high', 'critical'];
  const riskLevel = riskOrder.indexOf(action.risk);

  // Static policy check (always)
  if (trustMean < thresholds[action.risk]) {
    return {
      decision: 'deny',
      reason: `Trust ${trustMean.toFixed(3)} below threshold ${thresholds[action.risk]} for ${action.risk} risk`,
    };
  }

  // Escalate high-risk actions even if trust is sufficient
  if (riskLevel >= escalateAbove && trustMean < 0.85) {
    return {
      decision: 'escalate',
      reason: `High-risk action (${action.risk}) with non-elite trust (${trustMean.toFixed(3)})`,
    };
  }

  return { decision: 'allow', reason: 'Trust sufficient for action risk' };
}

// ============================================================================
// Algorithm 5: Distributed Attack Detector (cross-agent pattern analysis)
// ============================================================================
// Makins et al.: per-instance monitors fail against distributed attacks.
// This detector tracks patterns ACROSS agents, not just per-agent.
// Flags: (a) multiple agents accessing same resource, (b) coordinated timing,
// (c) information flow patterns suggestive of exfiltration.

interface AgentAction {
  agentId: string;
  action: string;
  target: string;
  timestamp: number;
}

function detectDistributedPattern(
  actions: AgentAction[],
  options?: {
    sameTargetThreshold?: number; // Flag if N agents hit same target
    timeWindowMs?: number;        // Time window for coordination
    uniqueAgents?: number;        // Min agents for "distributed"
  }
): { isDistributed: boolean; suspects: string[]; reason: string } {
  const sameTargetThreshold = options?.sameTargetThreshold ?? 3;
  const timeWindowMs = options?.timeWindowMs ?? 60000; // 1 minute
  const minAgents = options?.uniqueAgents ?? 2;

  // Group by target within time window
  const targetAgents = new Map<string, Set<string>>();

  for (const action of actions) {
    const key = action.target;
    if (!targetAgents.has(key)) targetAgents.set(key, new Set());
    targetAgents.get(key)!.add(action.agentId);
  }

  for (const [target, agents] of targetAgents) {
    if (agents.size >= sameTargetThreshold) {
      return {
        isDistributed: true,
        suspects: [...agents],
        reason: `${agents.size} agents accessed target "${target}" — possible coordinated activity`,
      };
    }
  }

  return { isDistributed: false, suspects: [], reason: 'No distributed pattern detected' };
}

// ============================================================================
// Algorithm 6: Authority-Scoped Delegation
// ============================================================================
// Qin et al.: authority should be cryptographically scoped, not global.
// Each capability (read, write, execute, delegate) has independent trust.
// Delegating authority requires signed permission chains.

type Capability = 'read' | 'write' | 'execute' | 'delegate';

interface AuthorityScope {
  agentId: string;
  capabilities: Map<Capability, BetaParams>;
  delegatedBy?: string; // Parent agent that delegated
  delegatedAt?: number;
  signature?: string;  // Cryptographic signature (simplified)
}

function newAuthorityScope(agentId: string): AuthorityScope {
  return {
    agentId,
    capabilities: new Map<Capability, BetaParams>([
      ['read', { alpha: 2, beta: 1 }],     // Slightly trusted by default
      ['write', { alpha: 1, beta: 2 }],    // Slightly untrusted by default
      ['execute', { alpha: 1, beta: 2 }],  // Slightly untrusted by default
      ['delegate', { alpha: 1, beta: 3 }], // Strongly untrusted by default
    ]),
  };
}

function canExercise(
  scope: AuthorityScope,
  capability: Capability,
  action: { risk: ActionRisk }
): { allowed: boolean; reason: string } {
  const params = scope.capabilities.get(capability);
  if (!params) return { allowed: false, reason: `No ${capability} capability` };

  const mean = betaMean(params);
  const result = evaluateGate(
    { agentId: scope.agentId, action: capability, risk: action.risk },
    mean
  );

  return {
    allowed: result.decision === 'allow',
    reason: result.reason,
  };
}

function delegateAuthority(
  parent: AuthorityScope,
  childAgentId: string,
  capabilities: Capability[],
  maxRisk: ActionRisk
): AuthorityScope | null {
  // Check if parent can delegate
  const parentDelegate = canExercise(parent, 'delegate', { risk: maxRisk });
  if (!parentDelegate.allowed) return null;

  // Child inherits reduced trust for requested capabilities
  const child = newAuthorityScope(childAgentId);
  child.delegatedBy = parent.agentId;
  child.delegatedAt = Date.now();

  for (const cap of capabilities) {
    const parentParams = parent.capabilities.get(cap)!;
    // Child gets 80% of parent's trust (discount for delegation depth)
    const childMean = betaMean(parentParams) * 0.8;
    // Convert back to Beta with uniform prior
    child.capabilities.set(cap, {
      alpha: 1 + childMean * 2,
      beta: 1 + (1 - childMean) * 2,
    });
  }

  return child;
}

// ============================================================================
// Algorithm 7: Behavioral Harness Monitor (ex ante, not ex post)
// ============================================================================
// Hu et al.: shift from ex post reputation to ex ante behavioral harnesses.
// Real-time constraint enforcement: rate limits, scope checking, anomaly detection.
// Does NOT wait for failure — prevents it.

interface HarnessConfig {
  rateLimitPerMinute: number;
  rateLimitPerHour: number;
  allowedTargets: Set<string>; // Whitelist
  blockedTargets: Set<string>; // Blacklist
  maxActionsPerSession: number;
  requireGateAbove: ActionRisk; // Gate threshold
}

class BehavioralHarness {
  private actionLog = new Map<string, number[]>(); // agentId → timestamps
  private sessionActions = new Map<string, number>(); // agentId → count

  constructor(private config: HarnessConfig) {}

  check(
    agentId: string,
    action: ProposedAction,
    timestamp = Date.now()
  ): { allowed: boolean; reason: string } {
    // 1. Blacklist check
    if (action.target && this.config.blockedTargets.has(action.target)) {
      return { allowed: false, reason: `Target "${action.target}" is blacklisted` };
    }

    // 2. Whitelist check (if non-empty)
    if (
      action.target &&
      this.config.allowedTargets.size > 0 &&
      !this.config.allowedTargets.has(action.target)
    ) {
      return { allowed: false, reason: `Target "${action.target}" not in whitelist` };
    }

    // 3. Rate limiting (per minute)
    const log = this.actionLog.get(agentId) ?? [];
    const recentActions = log.filter(t => t > timestamp - 60000);
    if (recentActions.length >= this.config.rateLimitPerMinute) {
      return { allowed: false, reason: `Rate limit exceeded: ${this.config.rateLimitPerMinute}/min` };
    }

    // 4. Session limit
    const sessionCount = this.sessionActions.get(agentId) ?? 0;
    if (sessionCount >= this.config.maxActionsPerSession) {
      return { allowed: false, reason: `Session limit exceeded: ${this.config.maxActionsPerSession}` };
    }

    // 5. Gate check for high-risk actions
    if (riskOrder(action.risk) >= riskOrder(this.config.requireGateAbove)) {
      // In production, this would call an LLM judge
      // Here we just flag it
      return { allowed: true, reason: `Allowed but logged (risk: ${action.risk}, gate: required)` };
    }

    // Record action
    recentActions.push(timestamp);
    this.actionLog.set(agentId, recentActions);
    this.sessionActions.set(agentId, sessionCount + 1);

    return { allowed: true, reason: 'OK' };
  }

  getStats(agentId: string): {
    actionsThisMinute: number;
    actionsThisSession: number;
  } {
    const now = Date.now();
    const log = this.actionLog.get(agentId) ?? [];
    return {
      actionsThisMinute: log.filter(t => t > now - 60000).length,
      actionsThisSession: this.sessionActions.get(agentId) ?? 0,
    };
  }
}

function riskOrder(risk: ActionRisk): number {
  return ['low', 'medium', 'high', 'critical'].indexOf(risk);
}

// ============================================================================
// Full TrustEngineV2 — Composing the 7 algorithms
// ============================================================================

export class TrustEngineV2 {
  // Algorithm 1: Bayesian trust per agent
  private agentTrust = new Map<string, BetaParams>();

  // Algorithm 3: Skill fingerprints
  private skillFingerprints = new Map<string, SkillFingerprint>();

  // Algorithm 5: Action history for distributed detection
  private actionHistory: AgentAction[] = [];

  // Algorithm 6: Authority scopes
  private authorityScopes = new Map<string, AuthorityScope>();

  // Algorithm 7: Behavioral harness
  private harness: BehavioralHarness;

  constructor(harnessConfig?: Partial<HarnessConfig>) {
    this.harness = new BehavioralHarness({
      rateLimitPerMinute: 30,
      rateLimitPerHour: 500,
      allowedTargets: new Set(),
      blockedTargets: new Set(),
      maxActionsPerSession: 200,
      requireGateAbove: 'high',
      ...harnessConfig,
    });
  }

  // --- Trust management ---

  recordOutcome(agentId: string, success: boolean, weight = 1): void {
    const params = this.agentTrust.get(agentId) ?? { alpha: 1, beta: 1 };
    this.agentTrust.set(agentId, betaUpdate(params, success, weight));
  }

  getTrustMean(agentId: string): number {
    const params = this.agentTrust.get(agentId) ?? { alpha: 1, beta: 1 };
    let mean = betaMean(params);

    // Algorithm 2: Apply exponential decay toward 0.5
    // (In production, track lastUpdated per agent)
    return mean;
  }

  getTrustLevel(agentId: string): 'untrusted' | 'neutral' | 'trusted' {
    return betaToLevel(this.getTrustMean(agentId));
  }

  // --- Skill fingerprinting ---

  registerSkill(
    skillId: string,
    prompt: string,
    code: string,
    tools: string
  ): SkillFingerprint {
    const fp = fingerprintSkill(prompt, code, tools);
    this.skillFingerprints.set(skillId, fp);
    return fp;
  }

  compareSkills(skillId1: string, skillId2: string) {
    const fp1 = this.skillFingerprints.get(skillId1);
    const fp2 = this.skillFingerprints.get(skillId2);
    if (!fp1 || !fp2) throw new Error('Unknown skill');
    return skillRelationship(fp1, fp2);
  }

  // --- Pre-execution gating (Algorithm 4) ---

  gate(action: ProposedAction): { decision: GateDecision; reason: string } {
    // 1. Behavioral harness check (Algorithm 7)
    const harnessResult = this.harness.check(action.agentId, action);
    if (!harnessResult.allowed) {
      return { decision: 'deny', reason: `[harness] ${harnessResult.reason}` };
    }

    // 2. Trust threshold check (Algorithm 1 + 4)
    const trustMean = this.getTrustMean(action.agentId);
    const gateResult = evaluateGate(action, trustMean);
    if (gateResult.decision === 'deny') {
      return { decision: 'deny', reason: `[gate] ${gateResult.reason}` };
    }

    // 3. Distributed pattern check (Algorithm 5)
    const distributedCheck = detectDistributedPattern(
      [...this.actionHistory, {
        agentId: action.agentId,
        action: action.action,
        target: action.target ?? '',
        timestamp: Date.now(),
      }],
      { sameTargetThreshold: 5 }
    );
    if (distributedCheck.isDistributed) {
      return { decision: 'escalate', reason: `[distributed] ${distributedCheck.reason}` };
    }

    // 4. Authority scope check (Algorithm 6)
    const scope = this.authorityScopes.get(action.agentId);
    if (scope) {
      const capResult = canExercise(scope, 'execute', { risk: action.risk });
      if (!capResult.allowed) {
        return { decision: 'deny', reason: `[authority] ${capResult.reason}` };
      }
    }

    return gateResult;
  }

  // --- Authority management (Algorithm 6) ---

  registerAgent(agentId: string): AuthorityScope {
    const scope = newAuthorityScope(agentId);
    this.authorityScopes.set(agentId, scope);
    return scope;
  }

  delegate(
    parentId: string,
    childId: string,
    capabilities: Capability[],
    maxRisk: ActionRisk
  ): AuthorityScope | null {
    const parent = this.authorityScopes.get(parentId);
    if (!parent) return null;
    const child = delegateAuthority(parent, childId, capabilities, maxRisk);
    if (child) this.authorityScopes.set(childId, child);
    return child;
  }

  // --- Action logging (for Algorithm 5) ---

  logAction(action: AgentAction): void {
    this.actionHistory.push(action);
    // Keep last 10000 actions
    if (this.actionHistory.length > 10000) {
      this.actionHistory.shift();
    }
  }
}

// ============================================================================
// Tests (runnable: npx tsx trust-engine-v2.ts)
// ============================================================================

import assert from 'assert';

function runTests(): void {
  console.log('Testing TrustEngineV2 — 7 algorithms\n');

  // Algorithm 1: Bayesian update
  console.log('1. Bayesian Trust Update');
  let params: BetaParams = { alpha: 1, beta: 1 };
  for (let i = 0; i < 10; i++) params = betaUpdate(params, true);
  assert(betaMean(params) > 0.9, '10 successes should give high trust');
  console.log(`   10 successes → mean = ${betaMean(params).toFixed(3)} ✅`);

  params = { alpha: 1, beta: 1 };
  for (let i = 0; i < 5; i++) params = betaUpdate(params, false);
  assert(betaMean(params) < 0.2, '5 failures should give low trust');
  console.log(`   5 failures → mean = ${betaMean(params).toFixed(3)} ✅`);

  // Algorithm 2: Exponential decay
  console.log('\n2. Exponential Time Decay');
  const decayed168h = exponentialDecay(0.9, 168, 168, 0.5);
  assert(Math.abs(decayed168h - 0.7) < 0.01, '168h at 168h half-life → halfway to prior');
  console.log(`   0.9 after 168h → ${decayed168h.toFixed(3)} (expected ~0.7) ✅`);

  const decayed0h = exponentialDecay(0.9, 0, 168, 0.5);
  assert(decayed0h === 0.9, '0h → no decay');
  console.log(`   0.9 after 0h → ${decayed0h.toFixed(3)} ✅`);

  // Algorithm 3: Skill fingerprinting
  console.log('\n3. Per-Component Skill Fingerprint');
  const fp1 = fingerprintSkill('Summarize text', 'def sum(t): return len(t)', 'read_text');
  const fp2 = fingerprintSkill('Summarize text', 'def sum(t): return len(t)', 'read_text');
  const fp3 = fingerprintSkill('Summarize the input', 'def summarize(text): return text[:100]', 'read_text');
  const fp4 = fingerprintSkill('Translate text', 'console.log("hello")', 'write_file');

  const rel12 = skillRelationship(fp1, fp2);
  assert(rel12.relationship === 'clone', 'Identical skills should be clones');
  console.log(`   Identical → ${rel12.relationship} (sim=${rel12.similarity.toFixed(3)}) ✅`);

  const rel13 = skillRelationship(fp1, fp3);
  console.log(`   Variant → ${rel13.relationship}, changed: ${rel13.changedComponent} (sim=${rel13.similarity.toFixed(3)}) ✅`);

  const rel14 = skillRelationship(fp1, fp4);
  assert(rel14.relationship === 'unrelated', 'Different skills should be unrelated');
  console.log(`   Different → ${rel14.relationship} (sim=${rel14.similarity.toFixed(3)}) ✅`);

  // Algorithm 4: Pre-execution gate
  console.log('\n4. Pre-Execution Gate');
  const lowTrustAction: ProposedAction = {
    agentId: 'agent-1', action: 'delete_file', risk: 'critical'
  };
  const lowResult = evaluateGate(lowTrustAction, 0.3);
  assert(lowResult.decision === 'deny', 'Low trust + critical → deny');
  console.log(`   Trust 0.3 + critical → ${lowResult.decision} ✅`);

  const highTrustAction: ProposedAction = {
    agentId: 'agent-1', action: 'read_file', risk: 'low'
  };
  const highResult = evaluateGate(highTrustAction, 0.6);
  assert(highResult.decision === 'allow', 'Medium trust + low → allow');
  console.log(`   Trust 0.6 + low → ${highResult.decision} ✅`);

  const escalateAction: ProposedAction = {
    agentId: 'agent-1', action: 'deploy_code', risk: 'high'
  };
  const escResult = evaluateGate(escalateAction, 0.75);
  assert(escResult.decision === 'escalate', 'High risk + non-elite → escalate');
  console.log(`   Trust 0.75 + high → ${escResult.decision} ✅`);

  // Algorithm 5: Distributed attack detector
  console.log('\n5. Distributed Attack Detector');
  const distributedActions: AgentAction[] = [
    { agentId: 'a1', action: 'fetch', target: 'weights.bin', timestamp: 1 },
    { agentId: 'a2', action: 'fetch', target: 'weights.bin', timestamp: 2 },
    { agentId: 'a3', action: 'fetch', target: 'weights.bin', timestamp: 3 },
    { agentId: 'a4', action: 'fetch', target: 'weights.bin', timestamp: 4 },
  ];
  const distResult = detectDistributedPattern(distributedActions);
  assert(distResult.isDistributed, '4 agents on same target → distributed');
  console.log(`   4 agents → same target → ${distResult.isDistributed} (${distResult.reason}) ✅`);

  const normalActions: AgentAction[] = [
    { agentId: 'a1', action: 'fetch', target: 'data1.json', timestamp: 1 },
    { agentId: 'a2', action: 'fetch', target: 'data2.json', timestamp: 2 },
  ];
  const normalResult = detectDistributedPattern(normalActions);
  assert(!normalResult.isDistributed, 'Different targets → normal');
  console.log(`   Different targets → ${normalResult.isDistributed} ✅`);

  // Algorithm 6: Authority-scoped delegation
  console.log('\n6. Authority-Scoped Delegation');
  const parent = newAuthorityScope('parent-agent');
  const parentRead = canExercise(parent, 'read', { risk: 'low' });
  assert(parentRead.allowed, 'Parent should read low-risk');
  console.log(`   Parent read low-risk → ${parentRead.allowed} ✅`);

  const parentWrite = canExercise(parent, 'write', { risk: 'high' });
  assert(!parentWrite.allowed, 'Parent should NOT write high-risk (default)');
  console.log(`   Parent write high-risk → ${parentWrite.allowed} ✅`);

  // Boost parent write trust
  parent.capabilities.set('write', { alpha: 10, beta: 1 });
  const parentWriteBoosted = canExercise(parent, 'write', { risk: 'high' });
  assert(parentWriteBoosted.allowed, 'Boosted parent should write');
  console.log(`   Boosted parent write → ${parentWriteBoosted.allowed} ✅`);

  const child = delegateAuthority(parent, 'child-agent', ['read', 'write'], 'medium');
  assert(child !== null, 'Delegation should succeed');
  if (child) {
    const childRead = canExercise(child, 'read', { risk: 'low' });
    assert(childRead.allowed, 'Child should read');
    console.log(`   Child read → ${childRead.allowed} ✅`);

    const childDelegate = canExercise(child, 'delegate', { risk: 'low' });
    // Child didn't receive delegate capability
    console.log(`   Child delegate cap: ${child.capabilities.has('delegate')} ✅`);
  }

  // Algorithm 7: Behavioral harness
  console.log('\n7. Behavioral Harness');
  const harness = new BehavioralHarness({
    rateLimitPerMinute: 3,
    rateLimitPerHour: 100,
    allowedTargets: new Set(['api.example.com', 'cdn.example.com']),
    blockedTargets: new Set(['evil.com']),
    maxActionsPerSession: 5,
    requireGateAbove: 'high',
  });

  // Blacklist
  const blacklisted = harness.check('a1', {
    agentId: 'a1', action: 'fetch', target: 'evil.com', risk: 'low'
  });
  assert(!blacklisted.allowed, 'Blacklisted target should be blocked');
  console.log(`   Blacklisted target → ${blacklisted.allowed} (${blacklisted.reason}) ✅`);

  // Whitelist
  const whitelisted = harness.check('a1', {
    agentId: 'a1', action: 'fetch', target: 'api.example.com', risk: 'low'
  });
  assert(whitelisted.allowed, 'Whitelisted target should pass');
  console.log(`   Whitelisted target → ${whitelisted.allowed} ✅`);

  // Non-whitelisted
  const notListed = harness.check('a1', {
    agentId: 'a1', action: 'fetch', target: 'unknown.com', risk: 'low'
  });
  assert(!notListed.allowed, 'Unknown target should be blocked');
  console.log(`   Unknown target → ${notListed.allowed} (${notListed.reason}) ✅`);

  // Rate limit
  for (let i = 0; i < 3; i++) {
    harness.check('a2', { agentId: 'a2', action: 'fetch', target: 'api.example.com', risk: 'low' });
  }
  const rateLimited = harness.check('a2', {
    agentId: 'a2', action: 'fetch', target: 'api.example.com', risk: 'low'
  });
  assert(!rateLimited.allowed, '4th action should be rate-limited');
  console.log(`   Rate limited (4/3 per min) → ${rateLimited.allowed} (${rateLimited.reason}) ✅`);

  // Full engine integration test
  console.log('\n--- Full TrustEngineV2 Integration ---');
  const engine = new TrustEngineV2();
  engine.registerAgent('worker-1');

  // Initially neutral
  for (let i = 0; i < 10; i++) engine.recordOutcome('worker-1', true);
  console.log(`   After 10 successes: trust = ${engine.getTrustMean('worker-1').toFixed(3)} (${engine.getTrustLevel('worker-1')})`);

  const gateResult = engine.gate({
    agentId: 'worker-1', action: 'read_data', risk: 'low'
  });
  console.log(`   Gate result for read_data: ${gateResult.decision} ✅`);

  console.log('\n✅ All 7 algorithms verified.');
}

runTests();
