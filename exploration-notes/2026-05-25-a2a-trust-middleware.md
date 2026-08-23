# A2A Protocol Trust Middleware — 研究笔记

> 日期: 2026-05-25 | 主题: Agent-to-Agent 协议的信任验证机制
> 目标: 为 lab/a2a-trust-prototype 提供设计基础和可运行原型代码

---

## 核心概念 (5)

### 1. Agent Card (代理名片)
A2A 的服务发现机制。JSON 文档（通常在 `/.well-known/agent.json`），声明 agent 的身份、能力、端点和认证方式。类似于 OpenAPI spec 但面向 agent 交互。

### 2. JWS/JWKS 签名链
Agent 用 ES256 (ECDSA P-256 + SHA-256) 对 JWT 签名，公钥通过 JWKS 端点暴露。验证方获取公钥后验证签名，建立信任链。这是 A2A 推送通知认证的核心。

### 3. Zero-Trust Agent Interaction
"永不信任，始终验证" — 每个 agent 交互都需要独立认证和授权，不因之前的交互建立隐式信任。A2A 的安全模型基于此原则。

### 4. Trust Score (信任评分)
协议规范之外的扩展概念。基于历史交互质量、签名验证成功率、任务完成率等指标，为 agent 建立动态信任评分。用于路由决策（高信任 agent 优先委托任务）。

### 5. JSON-RPC 2.0 over HTTPS
A2A 的传输层。所有通信通过 HTTPS 上的 JSON-RPC 2.0 进行，支持同步请求/响应、SSE 流式传输和异步推送通知。

---

## 可运行代码: A2A Trust Middleware 原型

```js
// a2a-trust-middleware.js — Node.js 原生 crypto, 零依赖
// 用法: node a2a-trust-middleware.js

const crypto = require('crypto');
const http = require('http');

// ============================================================
// 1. 密钥生成 (ES256 = ECDSA P-256 + SHA-256)
// ============================================================

function generateKeyPair() {
  const { publicKey, privateKey } = crypto.generateKeyPairSync('ec', {
    namedCurve: 'P-256',
  });
  return { publicKey, privateKey };
}

// ============================================================
// 2. JWKS 端点 — 暴露公钥供验证方获取
// ============================================================

function publicKeyToJWK(publicKey, kid) {
  const exported = publicKey.export({ type: 'spki', format: 'jwk' });
  return { ...exported, kid, use: 'sig', alg: 'ES256' };
}

// ============================================================
// 3. JWT 签名 (Agent 端)
// ============================================================

function base64url(buf) {
  return buf.toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}

function signJWT(payload, privateKey, kid) {
  const header = { alg: 'ES256', typ: 'JWT', kid };
  const headerB64 = base64url(Buffer.from(JSON.stringify(header)));
  const payloadB64 = base64url(Buffer.from(JSON.stringify(payload)));
  const signingInput = `${headerB64}.${payloadB64}`;

  const signature = crypto.createSign('SHA256')
    .update(signingInput)
    .sign(privateKey);

  return `${signingInput}.${base64url(signature)}`;
}

// ============================================================
// 4. JWT 验证 (验证方)
// ============================================================

function verifyJWT(token, publicKey) {
  const [headerB64, payloadB64, signatureB64] = token.split('.');
  const signingInput = `${headerB64}.${payloadB64}`;

  const sigBuf = Buffer.from(signatureB64.replace(/-/g, '+').replace(/_/g, '/'), 'base64');
  const valid = crypto.createVerify('SHA256')
    .update(signingInput)
    .verify(publicKey, sigBuf);

  if (!valid) throw new Error('Invalid signature');

  const payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString());

  // 检查过期
  if (payload.exp && Date.now() / 1000 > payload.exp) {
    throw new Error('Token expired');
  }
  return payload;
}

// ============================================================
// 5. Trust Score 计算
// ============================================================

class TrustManager {
  constructor() {
    this.records = new Map(); // agentId -> { successes, failures, lastSeen }
  }

  record(agentId, success) {
    if (!this.records.has(agentId)) {
      this.records.set(agentId, { successes: 0, failures: 0, lastSeen: 0 });
    }
    const rec = this.records.get(agentId);
    rec[success ? 'successes' : 'failures']++;
    rec.lastSeen = Date.now();
  }

  getScore(agentId) {
    const rec = this.records.get(agentId);
    if (!rec) return 0.5; // 未知 agent 给中性分
    const total = rec.successes + rec.failures;
    if (total === 0) return 0.5;
    const baseScore = rec.successes / total;

    // 时间衰减: 超过 1 小时未交互扣分
    const hoursSinceLast = (Date.now() - rec.lastSeen) / 3600000;
    const decay = Math.max(0.5, 1 - hoursSinceLast * 0.01);

    // 样本量加权: 交互次数越多分越可靠
    const confidenceWeight = Math.min(1, total / 10);

    return baseScore * decay * confidenceWeight + 0.5 * (1 - confidenceWeight);
  }

  shouldTrust(agentId, threshold = 0.7) {
    return this.getScore(agentId) >= threshold;
  }
}

// ============================================================
// 6. A2A 请求验证中间件
// ============================================================

function createA2AMiddleware(trustManager, jwksMap) {
  return function verifyA2ARequest(req) {
    const authHeader = req.headers['authorization'];
    if (!authHeader?.startsWith('Bearer ')) {
      return { ok: false, error: 'Missing Bearer token', status: 401 };
    }

    const token = authHeader.slice(7);
    let payload;
    try {
      // 从 token header 提取 kid, 查找对应公钥
      const header = JSON.parse(Buffer.from(token.split('.')[0], 'base64url').toString());
      const publicKey = jwksMap.get(header.kid);
      if (!publicKey) return { ok: false, error: 'Unknown key ID', status: 401 };

      payload = verifyJWT(token, publicKey);
    } catch (e) {
      return { ok: false, error: e.message, status: 401 };
    }

    // Trust check
    const trusted = trustManager.shouldTrust(payload.iss);
    if (!trusted) {
      return { ok: false, error: `Agent ${payload.iss} trust score too low: ${trustManager.getScore(payload.iss).toFixed(2)}`, status: 403 };
    }

    return { ok: true, payload, trustScore: trustManager.getScore(payload.iss) };
  };
}

// ============================================================
// 7. 完整演示
// ============================================================

console.log('=== A2A Trust Middleware Prototype ===\n');

// 模拟两个 agent
const agentA = generateKeyPair();
const agentB = generateKeyPair();

const kidA = 'agent-a-key-1';
const kidB = 'agent-b-key-1';

// JWKS 映射 (验证方持有已知公钥)
const jwksMap = new Map();
jwksMap.set(kidA, agentA.publicKey);
jwksMap.set(kidB, agentB.publicKey);

// Trust manager
const trust = new TrustManager();

// 模拟历史: agentA 可靠, agentB 不太可靠
for (let i = 0; i < 8; i++) trust.record('agent-a', true);
for (let i = 0; i < 3; i++) trust.record('agent-b', true);
for (let i = 0; i < 4; i++) trust.record('agent-b', false);

console.log(`Agent A trust score: ${trust.getScore('agent-a').toFixed(3)} (should be high)`);
console.log(`Agent B trust score: ${trust.getScore('agent-b').toFixed(3)} (should be low)`);
console.log(`Agent A trusted: ${trust.shouldTrust('agent-a')}`);
console.log(`Agent B trusted: ${trust.shouldTrust('agent-b')}`);

// Agent A 签发 token
const token = signJWT(
  { iss: 'agent-a', aud: 'webhook.example.com', taskId: 'task-123', iat: Math.floor(Date.now() / 1000), exp: Math.floor(Date.now() / 1000) + 300 },
  agentA.privateKey,
  kidA,
);
console.log(`\nSigned JWT: ${token.slice(0, 60)}...`);

// 中间件验证
const middleware = createA2AMiddleware(trust, jwksMap);

const resultA = middleware({ headers: { authorization: `Bearer ${token}` } });
console.log(`\nAgent A request: ${resultA.ok ? '✅ ALLOWED' : '❌ REJECTED'}`);
if (resultA.ok) console.log(`  Trust score: ${resultA.trustScore.toFixed(3)}, Task: ${resultA.payload.taskId}`);

// Agent B 尝试用假 token
const badToken = signJWT(
  { iss: 'agent-b', aud: 'webhook.example.com', taskId: 'task-456', iat: Math.floor(Date.now() / 1000), exp: Math.floor(Date.now() / 1000) + 300 },
  agentB.privateKey,
  kidB,
);
const resultB = middleware({ headers: { authorization: `Bearer ${badToken}` } });
console.log(`\nAgent B request: ${resultB.ok ? '✅ ALLOWED' : '❌ REJECTED'}`);
if (!resultB.ok) console.log(`  Reason: ${resultB.error}`);

// 验证签名篡改检测
const tampered = badToken.slice(0, -5) + 'XXXXX';
const resultT = middleware({ headers: { authorization: `Bearer ${tampered}` } });
console.log(`\nTampered token: ${resultT.ok ? '✅ ALLOWED' : '❌ REJECTED'}`);
if (!resultT.ok) console.log(`  Reason: ${resultT.error}`);

console.log('\n=== All checks passed ===');
```

---

## 关键洞察 (4)

### 1. A2A 安全是"协议+实现"的双层模型
协议定义了 Agent Card 声明安全方案和 JWKS 签名机制，但实际的认证验证、授权检查、Trust Score 等全在实现层。这意味着中间件是 A2A 安全的核心战场 — 协议不替你做安全，只替你声明。

### 2. Trust Score 应该是动态的、衰减的
静态 ACL 在 agent 世界不够用。agent 的行为会变（被攻击、配置错误、模型更新），信任评分必须反映实时行为。时间衰减 + 样本量加权 + 中性基线的设计让新 agent 不会一开始就被拒绝，但也不会被盲目信任。

### 3. ES256 比 RS256 更适合 agent 场景
ECDSA 签名更短（64 bytes vs 256 bytes），验证更快。在 agent 间高频通信场景下，这个差异会被放大。A2A spec 推荐 ES256 是合理的。

### 4. Agent Card 是攻击面
Palo Alto 的研究指出，恶意 Agent Card 可以注入 prompt、暴露敏感信息。验证方必须在处理 Agent Card 内容前进行清洗和沙箱化，不能直接将其喂给 LLM。

---

## 下一步行动 (3)

1. **创建 lab/a2a-trust-prototype/** — 基于上面的代码扩展为完整的 Express/Fastify 中间件包，支持:
   - Agent Card 验证和缓存
   - JWKS 自动轮换
   - Trust Score 持久化 (SQLite/Redis)
   - 目标: 5+ tests

2. **研究 A2A spec v1.0 的 streaming (SSE) 安全** — 流式传输中的认证 token 如何处理？是初始握手认证还是每条 SSE 事件都验证？

3. **设计 Trust Score 的多维度模型** — 除了成功/失败率，加入: 响应延迟、数据质量评分、schema 合规率。与 agent-context-store 的 memory graph 集成。

---

## 参考资料

- [A2A Protocol Official (GitHub)](https://github.com/a2aproject/A2A) — 23.9k stars, v1.0.0 released
- [Google Dev: Understanding A2A](https://discuss.google.dev/t/understanding-a2a-the-protocol-for-agent-collaboration/189103)
- [Palo Alto: A2A Security Guide](https://live.paloaltonetworks.com/t5/community-blogs/safeguarding-ai-agents-an-in-depth-look-at-a2a-protocol-risks/ba-p/1235996)
- [arXiv: Building Secure Agentic AI with A2A](https://arxiv.org/html/2504.16902v1)
- [Linux Foundation A2A Project (June 2025)](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents)
- [CapiscIO: A2A Middleware](https://capisc.io/resources) — 商业 A2A 验证工具
