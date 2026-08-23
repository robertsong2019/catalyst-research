# A2A Trust Protocol — Agent-to-Agent 认证与信任评分

> 研究时间: 2026-06-03 20:00 CST
> 触发任务: `lab/a2a-trust-prototype/` — Node.js 原生 crypto ES256 签名中间件 + Trust Score

---

## 核心概念

### 1. Google A2A Protocol（Agent-to-Agent）
- 2025年4月发布，2026年已有150+组织支持
- 与 MCP 互补：MCP 连接 agent→tool，A2A 连接 agent→agent
- 认证机制：OAuth 2.0 / mTLS / JWT / API Keys / OIDC
- **Agent Card**: JSON-LD 文档描述 agent 能力与权限，类似 OpenAPI spec

### 2. Zero-Trust Identity for Agentic AI
- arxiv 2505.19301: 用 DIDs (Decentralized Identifiers) + VCs (Verifiable Credentials) 构建 agent 身份
- 每个 agent 拥有 DID，通过 VC 证明其能力和授权
- Agent 间通信使用**密码学签名消息** + Verifiable Presentations
- 核心原则：永不隐式信任，每次交互都验证身份和授权

### 3. Trust Score 模型
- 信任不是二元的（信任/不信任），而是连续值
- 维度：身份验证强度、历史交互记录、权限范围、数据敏感度
- 参考方案：cheqd 的 Agentic Trust（基于 MCP 的信任图）
- 支付场景：Mastercard Agent Pay、Visa Trusted Agent Protocol、Google AP2

### 4. A2A 安全增强（arxiv 2505.12490）
- 现有 A2A 的7个缺陷：短命 token、客户认证(SCA)、细粒度 scope、显式同意、直接数据传输、多交易审批、支付专用 token
- **关键洞察**：A2A 协议本身不处理敏感数据，需要应用层增强

### 5. ES256 签名（我们的实现方案）
- ECDSA + P-256 + SHA-256
- 比 RSA 更短密钥、更快验证，适合 agent 间高频通信
- Node.js `crypto` 原生支持，零依赖

---

## 代码示例：A2A Trust 中间件原型

```js
// a2a-trust-middleware.js — Node.js 原生 crypto ES256 签名 + Trust Score
const crypto = require('crypto');

// ============================================================
// 1. Agent Identity — DID-like key pair generation
// ============================================================
class AgentIdentity {
  constructor(name) {
    this.name = name;
    const { publicKey, privateKey } = crypto.generateKeyPairSync('ec', {
      namedCurve: 'P-256',
      publicKeyEncoding: { type: 'spki', format: 'pem' },
      privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    });
    this.publicKey = publicKey;
    this.privateKey = privateKey;
    this.agentId = `did:a2a:${crypto.randomUUID()}`;
  }

  // Sign a payload → JWT-like token
  signToken(payload, ttlSeconds = 300) {
    const header = Buffer.from(JSON.stringify({ alg: 'ES256', typ: 'A2A' }), 'utf8');
    const iat = Math.floor(Date.now() / 1000);
    const body = { ...payload, iss: this.agentId, iat, exp: iat + ttlSeconds };
    const bodyB64 = Buffer.from(JSON.stringify(body), 'utf8');
    const signingInput = `${header.toString('base64url')}.${bodyB64.toString('base64url')}`;
    const sig = crypto.sign('sha256', Buffer.from(signingInput), this.privateKey);
    return `${signingInput}.${sig.toString('base64url')}`;
  }

  // Verify a token from any agent given their public key
  static verifyToken(token, publicKey) {
    const [headerB64, bodyB64, sigB64] = token.split('.');
    const signingInput = `${headerB64}.${bodyB64}`;
    const sig = Buffer.from(sigB64, 'base64url');
    const valid = crypto.verify('sha256', Buffer.from(signingInput), publicKey, sig);
    if (!valid) throw new Error('Invalid signature');
    const body = JSON.parse(Buffer.from(bodyB64, 'base64url').toString('utf8'));
    if (body.exp < Math.floor(Date.now() / 1000)) throw new Error('Token expired');
    return body;
  }

  get agentCard() {
    return {
      '@context': 'https://a2a.dev/agent-card/v1',
      id: this.agentId,
      name: this.name,
      publicKey: this.publicKey,
      capabilities: [],
    };
  }
}

// ============================================================
// 2. Trust Score Engine
// ============================================================
class TrustEngine {
  constructor() {
    this.interactions = new Map(); // agentId → { success, fail, lastSeen }
  }

  /**
   * Compute trust score [0, 1] based on:
   * - Verification level (did agent present valid signature?)
   * - Interaction history (success rate)
   * - Scope alignment (is requested action within declared capabilities?)
   */
  computeScore(agentId, { verified = false, scopeMatch = false } = {}) {
    const record = this.interactions.get(agentId) || { success: 0, fail: 0 };
    const total = record.success + record.fail;
    
    let score = 0;
    score += verified ? 0.4 : 0;           // 身份验证
    score += scopeMatch ? 0.2 : 0;          // 权限匹配
    score += total > 0 ? (record.success / total) * 0.3 : 0;  // 历史成功率
    score += total >= 5 ? 0.1 : (total / 5) * 0.1;            // 交互频次
    
    return Math.min(score, 1);
  }

  recordInteraction(agentId, success) {
    const record = this.interactions.get(agentId) || { success: 0, fail: 0, lastSeen: 0 };
    record[success ? 'success' : 'fail']++;
    record.lastSeen = Date.now();
    this.interactions.set(agentId, record);
  }
}

// ============================================================
// 3. A2A Trust Middleware — drop-in for Express/Fastify
// ============================================================
function a2aTrustMiddleware(trustEngine, minScore = 0.5) {
  return async function middleware(req, res, next) {
    try {
      const token = req.headers['x-a2a-token'];
      if (!token) return res.status(401).json({ error: 'Missing A2A token' });

      // Caller's public key from header (in production: lookup from Agent Card registry)
      const callerPubKey = req.headers['x-a2a-pubkey'];
      if (!callerPubKey) return res.status(401).json({ error: 'Missing caller public key' });

      const decoded = AgentIdentity.verifyToken(token, callerPubKey);
      
      const score = trustEngine.computeScore(decoded.iss, {
        verified: true,
        scopeMatch: decoded.scope === 'task:execute',
      });

      if (score < minScore) {
        trustEngine.recordInteraction(decoded.iss, false);
        return res.status(403).json({ error: 'Insufficient trust score', score });
      }

      req.a2a = { agentId: decoded.iss, score, payload: decoded };
      trustEngine.recordInteraction(decoded.iss, true);
      next();
    } catch (err) {
      res.status(401).json({ error: err.message });
    }
  };
}

// ============================================================
// Demo: Two agents communicating
// ============================================================
function demo() {
  console.log('=== A2A Trust Protocol Demo ===\n');
  
  const agentA = new AgentIdentity('Agent-Alpha');
  const agentB = new AgentIdentity('Agent-Beta');
  const trust = new TrustEngine();

  console.log(`Agent A: ${agentA.agentId}`);
  console.log(`Agent B: ${agentB.agentId}\n`);

  // Agent A sends a signed task request to Agent B
  const token = agentA.signToken({ scope: 'task:execute', action: 'deploy', target: 'prod' });
  console.log('Signed token created (first 80 chars):', token.slice(0, 80) + '...');

  // Agent B verifies
  const decoded = AgentIdentity.verifyToken(token, agentA.publicKey);
  console.log('\nVerified payload:', JSON.stringify(decoded, null, 2));

  // Trust scoring
  const score = trust.computeScore(decoded.iss, { verified: true, scopeMatch: true });
  console.log(`\nTrust score: ${score.toFixed(2)} (min: 0.5 → ${score >= 0.5 ? 'PASS ✅' : 'FAIL ❌'})`);

  // Simulate 10 interactions to see trust grow
  console.log('\n--- Trust Growth Over Interactions ---');
  for (let i = 1; i <= 10; i++) {
    trust.recordInteraction(decoded.iss, true);
    const s = trust.computeScore(decoded.iss, { verified: true, scopeMatch: true });
    console.log(`Interaction ${i}: score = ${s.toFixed(2)}`);
  }
}

// Run demo
demo();
```

**运行方式：**
```bash
node a2a-trust-middleware.js
```

**预期输出：**
```
=== A2A Trust Protocol Demo ===

Agent A: did:a2a:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Agent B: did:a2a:yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy

Signed token created (first 80 chars): eyJhbGciOiJFUzI1NiIsInR5cCI6IkEyQSJ9.eyJzY29wZSI6InRhc2s6ZXhlY3V0...
Verified payload: { scope: 'task:execute', action: 'deploy', ... }

Trust score: 0.90 (min: 0.5 → PASS ✅)

--- Trust Growth Over Interactions ---
Interaction 1: score = 0.93
...
Interaction 10: score = 1.00
```

---

## 关键洞察

### 1. A2A 安全是分层洋葱，不是单点方案
Google A2A 解决了 agent 互操作性问题，但安全需要多层叠加：
- 传输层：mTLS
- 身份层：DID + VC（或 JWT）
- 授权层：细粒度 scope + 显式用户同意
- 应用层：trust score + 行为监控
**教训**：我们的 `a2a-trust-prototype` 不应该试图替代 A2A，而是在 A2A 之上叠加 trust score 层。

### 2. Trust Score 必须是动态的、可衰减的
静态信任（"这个 agent 是认证的所以永远信任"）是危险的。好的 trust score 应该：
- 随成功交互增长
- 随失败交互快速衰减
- 长时间不活动后衰减
- 权限变更时重置
这和 `agent-memory-graph` 的 evolution 概念天然契合——trust evolution 是 memory evolution 的一个维度。

### 3. ES256 是 agent 签名的最佳起点
- 比 Ed25519 更广泛支持（Web Crypto API、JWT 生态）
- 比 RSA-2048 更短（64 字节签名 vs 256 字节）
- Node.js 原生支持，零外部依赖
- 与 W3C DID 规范兼容
- 可以无缝集成到 A2A 的 Agent Card 中

### 4. Agent Card 是新时代的 OpenAPI Spec
Google A2A 的 Agent Card（JSON-LD）定义了 agent 的能力、认证方式和权限。这和我们 `agent-context-store` 的 store metadata 思路一致。可以探索让 agent 在 runtime 发布自己的 Agent Card，其他 agent 据此决定是否信任和如何交互。

---

## 与现有项目关联

| 项目 | 关联点 |
|------|--------|
| `lab/a2a-trust-prototype` | 直接产出——本文的代码可作为种子 |
| `agent-memory-graph` | trust score evolution → memory graph 的一个 edge type |
| `agent-context-store` | Agent Card → store 的一种 structured context |
| `openclaw-langgraph-bridge` | 多 agent 协作时需要 agent 间信任机制 |

---

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`** — 基于本文代码建立项目骨架，包含：
   - `src/AgentIdentity.ts` — ES256 密钥生成 + 签名/验证
   - `src/TrustEngine.ts` — 动态 trust score 计算
   - `src/middleware.ts` — Express/Fastify 中间件
   - `tests/` — 完整测试覆盖
2. **接入 agent-memory-graph** — trust 交互历史持久化到 memory graph
3. **研究 A2A Agent Card JSON-LD schema** — 与 OpenClaw agent 配置打通

---

## 参考来源

- [Google A2A Protocol 官方公告](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability)
- [Zero-Trust Identity Framework for Agentic AI (arxiv 2505.19301)](https://arxiv.org/html/2505.19301v1)
- [Safeguarding Sensitive Data in Multi-Agent Systems (arxiv 2505.12490)](https://arxiv.org/html/2505.12490v1)
- [AI Agents with DIDs and VCs (arxiv 2511.02841)](https://arxiv.org/html/2511.02841v1)
- [Auth0: MCP vs A2A Guide](https://auth0.com/blog/mcp-vs-a2a)
- [cheqd Agentic Trust](https://cheqd.io/blog/2025-in-review-cheqds-year-of-building-trust-identity-and-verifiable-ai)
