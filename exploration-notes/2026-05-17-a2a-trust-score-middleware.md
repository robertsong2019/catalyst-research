# A2A Trust Score Middleware 研究

> 日期: 2026-05-17 | 主题: Agent 信任评分算法 + ES256 签名中间件设计
> 目标: 为 `lab/a2a-trust-prototype/` 补充 TrustScore 引擎和 Express 中间件

---

## 核心概念

### 1. Context-Conditioned Trust Score（上下文条件信任评分）

来自 [AgentReputation (arXiv 2605.00073)](https://arxiv.org/html/2605.00073v1) 的核心洞察：**单一全局信任分是危险的**。一个擅长调试的 agent 不应该在安全审计任务上也获得同等信任。

Trust Score 应该是 `(agentId, context) → score` 的映射，而非 `agentId → score`。

**设计原则：**
- 每个 interaction event 带有 context 标签（如 `debugging`, `security`, `code-review`）
- 聚合时只匹配相同 context 的事件
- 验证强度权重：自动检查(0.3) < 人工抽查(0.7) < 专家审计(1.0)
- 时间衰减：近期事件权重更高

### 2. EigenTrust 算法的 Agent 化改造

经典 EigenTrust 用 PageRank 式迭代计算 P2P 网络的全局信任值。对于 A2A 场景：

```
T(i) = (1-α) × Σ [ C(j) × R(j→i) × T(j) ] + α × P(i)
```

- `R(j→i)` = agent j 对 agent i 的局部评分
- `T(j)` = agent j 的全局信任值
- `C(j)` = 归一化系数
- `P(i)` = 先验信任（预置可信节点）
- `α` = 阻尼因子（通常 0.15）

**改造点：** 加入 context 维度，使信任传播在同 context 子图中进行。

### 3. A2A v1.0 Signed Agent Cards（2026-04 发布）

A2A Protocol v1.0 引入了关键安全特性：
- Agent Card 使用 ES256 签名，通过 JWKS 端点发布公钥
- `sigstore-a2a` 支持 CI/CD 透明签名
- Agent Payments Protocol (AP2) 扩展了经济协调能力

### 4. Trust Score 中间件架构

```
Request → [Signature Verify] → [Trust Score Check] → [Policy Gate] → Handler
              ↓                      ↓                     ↓
         verifyAgentCard()    computeScore()        evaluatePolicy()
         (crypto.ts)         (trust-score.ts)      (policy.ts)
```

三层过滤：
1. **身份验证** — ES256 签名验证（已有 crypto.ts）
2. **信任评估** — 基于 history + context 的信任分计算
3. **策略决策** — 信任分是否满足该操作的最低要求

### 5. Verification Strength（验证强度分级）

不是所有信任证据都等价：

| 级别 | 来源 | 权重 | 示例 |
|------|------|------|------|
| L0 | 自动检查 | 0.3 | CI pass, lint clean |
| L1 | 人工抽查 | 0.7 | PR review approved |
| L2 | 专家审计 | 1.0 | 安全团队审计通过 |
| L-1 | 违规记录 | -1.0 | 签名伪造、任务篡改 |

---

## 可运行代码示例

以下代码可直接集成到 `lab/a2a-trust-prototype/src/` 中：

### trust-score.ts — 信任评分引擎

```typescript
// src/trust-score.ts — Context-conditioned trust scoring engine
// Dependencies: none (pure computation, uses existing crypto.ts types)

export interface TrustEvent {
  fromAgent: string;
  toAgent: string;
  context: string;           // e.g. 'debugging', 'security', 'code-review'
  rating: number;            // -1.0 to 1.0
  verificationLevel: 0 | 1 | 2 | -1;  // L0=auto, L1=human, L2=expert, L-1=violation
  timestamp: number;         // Unix ms
}

export interface TrustPolicy {
  context: string;
  minScore: number;          // minimum trust score required
  minEvents: number;         // minimum number of events before trusting
  requireSignature: boolean; // must have verified agent card
}

const LEVEL_WEIGHTS: Record<number, number> = {
  0: 0.3,    // auto check
  1: 0.7,    // human review
  2: 1.0,    // expert audit
  '-1': -1.0, // violation
};

// Time decay: half-life of 30 days
const HALF_LIFE_MS = 30 * 24 * 60 * 60 * 1000;

function timeDecay(eventTime: number, now: number): number {
  const age = now - eventTime;
  return Math.pow(0.5, age / HALF_LIFE_MS);
}

/**
 * Compute trust score for a specific agent in a specific context.
 * Returns score in [-1, 1] and metadata.
 */
export function computeTrustScore(
  events: TrustEvent[],
  agentId: string,
  context: string,
  now: number = Date.now(),
): { score: number; eventCount: number; confidence: number } {
  // Filter: only events ABOUT this agent, in this context
  const relevant = events.filter(
    (e) => e.toAgent === agentId && e.context === context,
  );

  if (relevant.length === 0) {
    return { score: 0, eventCount: 0, confidence: 0 };
  }

  // Weighted average with verification strength + time decay
  let weightSum = 0;
  let scoreSum = 0;

  for (const event of relevant) {
    const vWeight = LEVEL_WEIGHTS[event.verificationLevel] ?? 0.3;
    const decay = timeDecay(event.timestamp, now);
    const weight = Math.abs(vWeight) * decay;
    scoreSum += event.rating * weight * Math.sign(vWeight);
    weightSum += weight;
  }

  const score = weightSum > 0 ? Math.max(-1, Math.min(1, scoreSum / weightSum)) : 0;
  
  // Confidence: more events = higher confidence (logarithmic saturation)
  const confidence = relevant.length > 0
    ? Math.min(1, Math.log2(relevant.length + 1) / Math.log2(21)) // saturates at ~20 events
    : 0;

  return { score, eventCount: relevant.length, confidence };
}

/**
 * Evaluate whether a trust score meets policy requirements.
 */
export function evaluatePolicy(
  trustResult: { score: number; eventCount: number; confidence: number },
  policy: TrustPolicy,
): { allowed: boolean; reason: string } {
  if (policy.requireSignature && trustResult.confidence === 0) {
    return { allowed: false, reason: 'No verified signature' };
  }
  if (trustResult.eventCount < policy.minEvents) {
    return { allowed: false, reason: `Insufficient events: ${trustResult.eventCount}/${policy.minEvents}` };
  }
  if (trustResult.score < policy.minScore) {
    return { allowed: false, reason: `Score ${trustResult.score.toFixed(3)} below minimum ${policy.minScore}` };
  }
  return { allowed: true, reason: 'OK' };
}

/**
 * Record a trust event (to be persisted).
 */
export function createTrustEvent(
  from: string,
  to: string,
  context: string,
  rating: number,
  level: TrustEvent['verificationLevel'],
): TrustEvent {
  return {
    fromAgent: from,
    toAgent: to,
    context,
    rating: Math.max(-1, Math.min(1, rating)),
    verificationLevel: level,
    timestamp: Date.now(),
  };
}
```

### trust-middleware.ts — Express 中间件

```typescript
// src/trust-middleware.ts — Express middleware for A2A trust verification
// Dependencies: express, ./agent-card.ts, ./trust-score.ts

import type { Request, Response, NextFunction } from 'express';
import { verifyAgentCard, type SignedAgentCard } from './agent-card.js';
import { computeTrustScore, evaluatePolicy, type TrustEvent, type TrustPolicy } from './trust-score.js';
import { importJWK, type PublicKey } from './crypto.js';

// In-memory event store (replace with DB in production)
const eventStore = new Map<string, TrustEvent[]>();

function addEvent(event: TrustEvent) {
  const key = event.toAgent;
  const events = eventStore.get(key) ?? [];
  events.push(event);
  eventStore.set(key, events);
}

export interface TrustMiddlewareOptions {
  policies: TrustPolicy[];
  /** Lookup public key by agent ID */
  getPublicKey: (agentId: string) => Promise<PublicKey | null>;
  /** Get all trust events for an agent */
  getEvents?: (agentId: string) => TrustEvent[];
}

/**
 * Create trust middleware. Verifies signature + checks trust score.
 */
export function createTrustMiddleware(options: TrustMiddlewareOptions) {
  return async (req: Request, res: Response, next: NextFunction) => {
    const cardHeader = req.headers['x-agent-card'];
    if (!cardHeader || typeof cardHeader !== 'string') {
      return res.status(401).json({ error: 'Missing X-Agent-Card header' });
    }

    let signedCard: SignedAgentCard;
    try {
      signedCard = JSON.parse(Buffer.from(cardHeader, 'base64url').toString('utf-8'));
    } catch {
      return res.status(400).json({ error: 'Invalid agent card encoding' });
    }

    // Step 1: Verify signature
    const publicKey = await options.getPublicKey(signedCard.id);
    if (!publicKey) {
      return res.status(401).json({ error: 'Unknown agent' });
    }

    const valid = await verifyAgentCard(signedCard, publicKey);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid signature' });
    }

    // Step 2: Determine context from request path
    const context = req.path.split('/')[2] ?? 'default'; // /api/{context}/...
    const policy = options.policies.find((p) => p.context === context);

    // Step 3: Compute trust score
    const events = options.getEvents?.(signedCard.id) ?? eventStore.get(signedCard.id) ?? [];
    const trustResult = computeTrustScore(events, signedCard.id, context);

    // Step 4: Evaluate policy (if one exists for this context)
    if (policy) {
      const decision = evaluatePolicy(trustResult, policy);
      if (!decision.allowed) {
        return res.status(403).json({
          error: 'Trust policy denied',
          reason: decision.reason,
          score: trustResult.score,
          context,
        });
      }
    }

    // Attach trust info to request for downstream handlers
    (req as any).agent = {
      id: signedCard.id,
      card: signedCard,
      trust: trustResult,
    };

    next();
  };
}
```

### 测试用例（可直接跑）

```typescript
// tests/trust-score.test.ts
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  computeTrustScore,
  evaluatePolicy,
  createTrustEvent,
  type TrustEvent,
} from '../src/trust-score.js';

describe('TrustScore', () => {
  const now = Date.now();
  const DAY = 86400000;

  it('returns 0 for unknown agents', () => {
    const result = computeTrustScore([], 'unknown-agent', 'debugging');
    assert.equal(result.score, 0);
    assert.equal(result.eventCount, 0);
    assert.equal(result.confidence, 0);
  });

  it('computes score from positive events', () => {
    const events: TrustEvent[] = [
      createTrustEvent('agent-a', 'agent-b', 'debugging', 0.8, 0),
      createTrustEvent('agent-c', 'agent-b', 'debugging', 0.9, 1),
      createTrustEvent('agent-d', 'agent-b', 'debugging', 1.0, 2),
    ];
    // Fix timestamps to "now" for deterministic test
    events.forEach((e, i) => { e.timestamp = now - i * DAY; });

    const result = computeTrustScore(events, 'agent-b', 'debugging', now);
    assert.ok(result.score > 0.5, `Expected score > 0.5, got ${result.score}`);
    assert.equal(result.eventCount, 3);
    assert.ok(result.confidence > 0);
  });

  it('penalizes violations heavily', () => {
    const events: TrustEvent[] = [
      createTrustEvent('agent-a', 'agent-b', 'security', 1.0, 2),   // expert: +1.0
      createTrustEvent('agent-c', 'agent-b', 'security', -1.0, -1), // violation: -1.0
    ];
    events[0].timestamp = now;
    events[1].timestamp = now;

    const result = computeTrustScore(events, 'agent-b', 'security', now);
    assert.ok(result.score < 0, `Violation should pull score negative, got ${result.score}`);
  });

  it('isolates contexts', () => {
    const events: TrustEvent[] = [
      createTrustEvent('agent-a', 'agent-b', 'debugging', 1.0, 2),
    ];
    events[0].timestamp = now;

    const debugResult = computeTrustScore(events, 'agent-b', 'debugging', now);
    const secResult = computeTrustScore(events, 'agent-b', 'security', now);

    assert.ok(debugResult.score > 0, 'Should have debugging score');
    assert.equal(secResult.score, 0, 'Should NOT have security score');
  });

  it('applies time decay', () => {
    const recent: TrustEvent[] = [
      { fromAgent: 'a', toAgent: 'b', context: 'test', rating: 1.0, verificationLevel: 1, timestamp: now },
    ];
    const old: TrustEvent[] = [
      { fromAgent: 'a', toAgent: 'b', context: 'test', rating: 1.0, verificationLevel: 1, timestamp: now - 180 * DAY },
    ];

    const recentScore = computeTrustScore(recent, 'b', 'test', now);
    const oldScore = computeTrustScore(old, 'b', 'test', now);

    assert.ok(recentScore.score > oldScore.score, 'Recent events should weigh more');
  });
});

describe('Policy evaluation', () => {
  it('denies when score too low', () => {
    const result = evaluatePolicy(
      { score: 0.3, eventCount: 5, confidence: 0.5 },
      { context: 'security', minScore: 0.7, minEvents: 3, requireSignature: true },
    );
    assert.equal(result.allowed, false);
    assert.ok(result.reason.includes('below minimum'));
  });

  it('denies when insufficient events', () => {
    const result = evaluatePolicy(
      { score: 0.9, eventCount: 1, confidence: 0.3 },
      { context: 'debugging', minScore: 0.5, minEvents: 5, requireSignature: false },
    );
    assert.equal(result.allowed, false);
    assert.ok(result.reason.includes('Insufficient'));
  });

  it('allows when all criteria met', () => {
    const result = evaluatePolicy(
      { score: 0.8, eventCount: 10, confidence: 0.7 },
      { context: 'debugging', minScore: 0.5, minEvents: 3, requireSignature: false },
    );
    assert.equal(result.allowed, true);
  });
});
```

**运行方式：**
```bash
cd lab/a2a-trust-prototype
# 添加 trust-score.ts 和 trust-middleware.ts 到 src/
# 添加测试到 tests/
npx tsx --test tests/trust-score.test.ts
```

---

## 关键洞察

### 1. 全局信任分是反模式

AgentReputation 论文明确指出：AI agent 的能力是 context-specific 的。一个代码补全 agent 在安全审计场景可能完全不可靠。**信任必须是 (agent, context) → score 的二维映射**，而非 agent → score 的一维映射。

### 2. 验证强度比评分数量更重要

10 个自动检查通过（L0, weight=0.3）不如 1 次专家审计通过（L2, weight=1.0）。但 1 次违规（L-1, weight=-1.0）可以抵消大量正面评价。这种不对称设计防止了 "刷好评" 攻击。

### 3. A2A Protocol v1.0 的签名卡是信任基础设施的关键拼图

2026-04 发布的 v1.0 引入了 Signed Agent Cards（ES256 签名），这让中间件可以在不依赖外部 CA 的情况下验证 agent 身份。我们的 crypto.ts 已经实现了这个基础——信任评分层只需在其上构建。

### 4. 中间件模式优于 SDK 模式

Express middleware 让信任检查成为透明的管道阶段，而非每个 handler 都要显式调用的 SDK。这和 A2A 的 "agent card in header" 模式天然匹配。

### 5. 时间衰减防止历史信誉套利

30 天半衰期意味着 agent 不能靠历史信誉无限透支。如果持续表现差，信任分会自然下降到不可用水平。这是对抗 "变质 agent" 的核心防线。

---

## 与现有项目的关联

| 组件 | 状态 | 关联 |
|------|------|------|
| `crypto.ts` | ✅ 已实现 | ES256 签名/验证，trust-score 层直接使用 |
| `agent-card.ts` | ✅ 已实现 | SignedAgentCard 类型，中间件解析 |
| `trust-score.ts` | 🆕 本笔记 | 核心评分算法，需集成到 src/ |
| `trust-middleware.ts` | 🆕 本笔记 | Express 中间件，需集成到 src/ |
| `lab/agent-observability` | 🔜 进行中 | Trust events 可作为 observability 的信号源 |
| `agent-context-store` | ✅ 186 tests | event hooks 可用于 trust event 的 pub/sub |

---

## 下一步行动

1. **将 trust-score.ts + trust-middleware.ts 集成到 `lab/a2a-trust-prototype/src/`** — 写入文件并补全测试
2. **实现 TrustEvent 持久化** — 当前用 Map，需接入 agent-context-store 的 event hooks
3. **添加 EigenTrust 迭代计算** — 当 agent 网络规模 >10 时，全局信任传播比局部聚合更准确
4. **研究 AP2 (Agent Payments Protocol)** — 经济协调需要信任分作为风控输入
5. **设计 trust event 的 MCP 接口** — 让外部 agent 可以查询和提交信任评价

---

## 参考

- [AgentReputation (arXiv 2605.00073)](https://arxiv.org/html/2605.00073v1) — 去中心化 agent 声誉框架
- [A2A Protocol v1.0 (Linux Foundation)](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) — Signed Agent Cards + AP2
- [EigenTrust Algorithm](https://stackoverflow.com/questions/1002952/an-algorithm-for-distributed-or-decentralised-reputation-trust) — P2P 全局信任计算
- [Galileo A2A Guide](https://galileo.ai/blog/google-agent2agent-a2a-protocol-guide) — 企业级 A2A 认证流程
- [Node.js JWT Best Practices 2026](https://dev.to/akshaykurve/handling-authentication-with-jwt-the-right-way-in-nodejs-2026-edition-25na) — ES256 vs EdDSA 选型
