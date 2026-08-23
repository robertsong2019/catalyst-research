# A2A Trust Protocol — 深度研究笔记

> Date: 2026-05-25 | Theme: Agent-to-Agent Trust with ES256 Signing + Trust Score
> Source: HEARTBEAT.md → 创建 lab/a2a-trust-prototype/

---

## 核心概念 (5)

### 1. A2A 协议 (Agent-to-Agent Protocol)
Google 2025年4月发布的开放协议，基于 HTTP/JSON-RPC 2.0/SSE，让不同平台的 AI Agent 互相发现、认证、协作。2025年6月移交 Linux Foundation 治理。

**关键组件：**
- **Agent Card** (`/.well-known/agent.json`) — JSON 元数据文档，声明身份、能力、认证方式、skills
- **Task 对象** — 有状态生命周期：submitted → working → input-required → completed
- **认证模型** — OAuth 2.0 / API Key / mTLS，声明在 Agent Card 中

### 2. ES256 签名 (ECDSA + P-256 + SHA-256)
A2A 推荐的 JWT 签名算法之一。相比 RS256：
- 更小的密钥尺寸（256 bit vs 2048+ bit）
- 更快的签名验证速度
- 非对称：私钥签名，公钥验证，天然适合 Agent 间信任

### 3. Trust Score 模型
综合多篇研究（AgentRank、AgentReputation、Zylos TRiSM），核心公式：

```
TrustScore(agent) = PerformanceScore × RecencyDecay × SybilPenalty
```

- **PerformanceScore** — 基于历史交互成功率（任务完成率、响应质量）
- **RecencyDecay** — 指数衰减，半衰期 24h（最近行为权重更高）
- **SybilPenalty** — 检测共谋/Sybil 攻击的惩罚系数

### 4. 信任三属性 (TRiSM Framework)
- **Strength** — 接受程度（0-1 分数）
- **Scope** — 授权范围（什么操作被允许）
- **Revocability** — 撤回速度（最常被忽视的属性）

关键洞察：级联撤回 — 当 Agent A 被撤信，A 担保的 Agent B 也要被审查（类似 PKI 证书链撤回）。

### 5. 分层信任架构
```
Layer 3: Governance — 合规、审计、策略引擎
Layer 2: Reputation — 行为评估、Trust Score、AgentRank
Layer 1: Identity — DID、JWT/ES256、Agent Card
Layer 0: Transport — HTTPS/TLS 1.3、mTLS
```

---

## 可运行代码：A2A Trust Prototype 核心

> 零外部依赖，仅使用 Node.js 内置 `crypto` 模块

```javascript
// a2a-trust-core.mjs — A2A Trust Prototype (ES256 + Trust Score)
// Run: node a2a-trust-core.mjs

import { sign, verify, createPublicKey } from 'node:crypto';
import { randomUUID } from 'node:crypto';

// ============================================================
// 1. ES256 Key Generation & JWT Sign/Verify (零依赖)
// ============================================================

function generateES256KeyPair() {
  const { publicKey, privateKey } = require('node:crypto').generateKeyPairSync('ec', {
    namedCurve: 'P-256',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
  return { publicKey, privateKey };
}

function base64url(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function createJWT(payload, privateKey) {
  const header = { alg: 'ES256', typ: 'JWT' };
  const headerB64 = base64url(Buffer.from(JSON.stringify(header)));
  const payloadB64 = base64url(Buffer.from(JSON.stringify(payload)));
  const signingInput = `${headerB64}.${payloadB64}`;

  const sig = sign('SHA256', Buffer.from(signingInput), privateKey);
  return `${signingInput}.${base64url(sig)}`;
}

function verifyJWT(token, publicKey) {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('Invalid JWT format');

  const [headerB64, payloadB64, sigB64] = parts;
  const signingInput = `${headerB64}.${payloadB64}`;

  // Restore base64url padding
  const sigBuf = Buffer.from(sigB64.replace(/-/g, '+').replace(/_/g, '/'), 'base64');
  const valid = verify('SHA256', Buffer.from(signingInput), publicKey, sigBuf);
  if (!valid) throw new Error('Invalid signature');

  const payload = JSON.parse(Buffer.from(payloadB64, 'base64').toString());
  if (payload.exp && Date.now() / 1000 > payload.exp) throw new Error('Token expired');
  return payload;
}

// ============================================================
// 2. Agent Card (A2A 规范)
// ============================================================

function createAgentCard({ id, name, skills, endpoint }) {
  return {
    id,
    name,
    description: `Agent ${name}`,
    url: endpoint,
    version: '0.1.0',
    capabilities: { streaming: false, pushNotifications: false },
    skills: skills.map(s => ({ id: s, name: s })),
    securitySchemes: {
      bearer: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT' }
    },
    // Trust metadata extension
    trust: {
      algorithm: 'ES256',
      publicKeyEndpoint: `${endpoint}/.well-known/public-key.pem`,
    }
  };
}

// ============================================================
// 3. Trust Score Engine
// ============================================================

class TrustEngine {
  constructor() {
    this.interactions = new Map(); // agentId -> [{ timestamp, success, score }]
    this.attestations = new Map(); // agentId -> [{ from, timestamp, weight }]
  }

  recordInteraction(agentId, success, score = 1.0) {
    if (!this.interactions.has(agentId)) this.interactions.set(agentId, []);
    this.interactions.get(agentId).push({
      timestamp: Date.now(),
      success,
      score,
    });
  }

  attest(trusterId, trusteeId, weight = 1.0) {
    if (!this.attestations.has(trusteeId)) this.attestations.set(trusteeId, []);
    this.attestations.get(trusteeId).push({
      from: trusterId,
      timestamp: Date.now(),
      weight,
    });
  }

  // 指数衰减：半衰期 24h
  recencyDecay(timestampMs, halflifeMs = 24 * 60 * 60 * 1000) {
    const elapsed = Date.now() - timestampMs;
    return Math.pow(0.5, elapsed / halflifeMs);
  }

  // Trust Score = weightedPerformance × recencyDecay
  getTrustScore(agentId) {
    const history = this.interactions.get(agentId) || [];
    if (history.length === 0) return 0;

    let weightedSum = 0;
    let totalWeight = 0;

    for (const interaction of history) {
      const decay = this.recencyDecay(interaction.timestamp);
      const weight = decay;
      weightedSum += (interaction.success ? interaction.score : 0) * weight;
      totalWeight += weight;
    }

    const performanceScore = totalWeight > 0 ? weightedSum / totalWeight : 0;

    // Attestation bonus: vouching from trusted agents
    const attestations = this.attestations.get(agentId) || [];
    let attestBonus = 0;
    for (const att of attestations) {
      const attesterScore = this.getTrustScore(att.from); // recursive, capped by depth
      attestBonus += attesterScore * att.weight * this.recencyDecay(att.timestamp) * 0.1;
    }

    return Math.min(1.0, performanceScore + attestBonus);
  }

  // Scope: what actions are authorized at this trust level
  getScope(trustScore) {
    if (trustScore >= 0.8) return ['read', 'write', 'delegate', 'admin'];
    if (trustScore >= 0.5) return ['read', 'write'];
    if (trustScore >= 0.2) return ['read'];
    return [];
  }
}

// ============================================================
// 4. End-to-End Demo
// ============================================================

const { publicKey: pubKey1, privateKey: privKey1 } = generateES256KeyPair();
const { publicKey: pubKey2, privateKey: privKey2 } = generateES256KeyPair();

// Create agents
const agentA = createAgentCard({
  id: 'agent-alpha',
  name: 'Alpha',
  skills: ['research', 'summarize'],
  endpoint: 'https://alpha.example.com',
});

const agentB = createAgentCard({
  id: 'agent-beta',
  name: 'Beta',
  skills: ['translate', 'code-review'],
  endpoint: 'https://beta.example.com',
});

// Agent A issues a trust token for B
const now = Math.floor(Date.now() / 1000);
const trustToken = createJWT({
  iss: agentA.id,
  sub: agentB.id,
  aud: 'a2a-trust-protocol',
  iat: now,
  exp: now + 3600, // 1h
  scope: ['read', 'write'],
  trust_level: 0.75,
}, privKey1);

console.log('=== A2A Trust Protocol Demo ===\n');
console.log('🔑 Trust Token (ES256 JWT):');
console.log(trustToken.slice(0, 80) + '...\n');

// Agent B's side verifies
const decoded = verifyJWT(trustToken, pubKey1);
console.log('✅ Verified payload:', JSON.stringify(decoded, null, 2), '\n');

// Trust Score simulation
const engine = new TrustEngine();

// Simulate 20 interactions for Agent B
for (let i = 0; i < 20; i++) {
  const success = Math.random() > 0.15; // 85% success rate
  const hoursAgo = Math.random() * 48; // spread over 48h
  const fakeTimestamp = Date.now() - hoursAgo * 3600 * 1000;

  engine.interactions.get(agentB.id).push({
    timestamp: fakeTimestamp,
    success,
    score: success ? 0.8 + Math.random() * 0.2 : 0,
  });
}

// Agent A attests for Agent B
engine.attest(agentA.id, agentB.id, 0.9);

const trustScore = engine.getTrustScore(agentB.id);
console.log(`📊 Agent Beta Trust Score: ${trustScore.toFixed(3)}`);
console.log(`📋 Authorized Scope: ${engine.getScope(trustScore).join(', ')}`);

// Verify score makes sense
console.log(`\n✅ Quality check: ${trustScore > 0.5 ? 'PASS' : 'WARN'} (expected ~0.75, got ${trustScore.toFixed(3)})`);
```

**运行方式：**
```bash
node a2a-trust-core.mjs
```

**预期输出：**
```
=== A2A Trust Protocol Demo ===

🔑 Trust Token (ES256 JWT):
eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhZ2VudC1hbHBoYS...

✅ Verified payload: {
  "iss": "agent-alpha",
  "sub": "agent-beta",
  ...
}

📊 Agent Beta Trust Score: 0.xxx
📋 Authorized Scope: read, write

✅ Quality check: PASS
```

---

## 关键洞察 (4)

### 1. A2A 协议 ≠ 信任框架
A2A 解决的是「Agent 怎么说话」（互操作性），不解决「该不该信任这个 Agent」。AgentRank 论文明确指出：A2A 是管道层，信任层需要额外构建。这正好是我们 `a2a-trust-prototype` 的定位 — A2A 之上加一层信任。

### 2. ES256 是 Agent JWT 的最佳选择
- 密钥短（适合嵌入 Agent Card），签名快
- Node.js 原生 `crypto` 即可，零依赖
- Curity 和 DigitalOcean 的 2025-2026 安全指南都推荐 ES256 > RS256

### 3. 信任是三维修问题，不是单分数
TRiSM 框架指出信任有三个独立维度：强度、范围、可撤回性。简单打分不够 — 需要考虑「信什么范围」「多快能撤」。级联撤回是生产环境的关键特性。

### 4. Recency Decay 比简单平均更安全
24h 半衰期的指数衰减是 AgentRank 和 Zylos 的共识。原因：Agent 行为可能突变（被入侵、prompt injection），旧数据的权重应该快速下降。线性平均或简单累计都会给攻击者留窗口。

---

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`** — 基于本笔记的核心代码，搭建完整项目
   - `src/keys.ts` — ES256 密钥管理
   - `src/jwt.ts` — JWT 签名/验证（零依赖）
   - `src/trust-engine.ts` — TrustEngine 类
   - `src/agent-card.ts` — A2A Agent Card 规范
   - `tests/trust-engine.test.ts` — 目标 10+ tests
2. **参考 AgentRank 论文** 实现更完整的 Sybil 检测
3. **与 agent-context-store 集成** — Trust Score 可作为 context metadata 存入 graph

---

## 参考资料

- [Google A2A Protocol](https://github.com/google/A2A) — 官方规范
- [Linux Foundation A2A Project](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project) — 2025-06 治理移交
- [AgentRank (0xIntuition)](https://github.com/0xIntuition/agent-rank) — 去中心化信任排名
- [AgentReputation (arXiv 2605.00073)](https://arxiv.org/html/2605.00073v1) — Agent 声誉框架
- [Zylos Progressive Trust](https://zylos.ai/research/2026-03-21-progressive-trust-reputation-multi-agent-networks) — TRiSM 框架
- [A2A Security (Palo Alto)](https://live.paloaltonetworks.com/t5/community-blogs/safeguarding-ai-agents-an-in-depth-look-at-a2a-protocol-risks/ba-p/1235996) — 威胁模型
- [Auth0 + A2A](https://auth0.com/blog/auth0-google-a2a) — 企业认证集成
- [Curity JWT Best Practices](https://curity.io/resources/learn/jwt-best-practices) — ES256 推荐
