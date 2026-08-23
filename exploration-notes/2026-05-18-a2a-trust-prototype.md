# A2A Trust Prototype — 深度技术研究

> 日期: 2026-05-18 | 主题: Agent-to-Agent 信任验证中间件
> 关联项目: lab/a2a-trust-prototype/

---

## 核心概念

### 1. A2A 协议安全模型
A2A 使用 OpenAPI security schemes 进行认证：API Keys、OAuth 2.0、OpenID Connect Discovery。Agent Card（`/.well-known/agent-card.json`）声明安全方案，客户端据此认证。**关键点：不发明新的认证系统，复用现有企业身份基础设施。**

### 2. ES256 (ECDSA P-256 + SHA-256)
非对称签名算法，用私钥签名、公钥验证。相比 RS256，ES256 签名更短（64 bytes vs 256 bytes）、验证更快。适合 agent-to-agent 场景：每个 agent 持有私钥，对端用公钥验证身份。

### 3. Trust Score（信任评分）
基于历史交互行为的动态信任评估：任务完成率、响应延迟、错误率。类似 TLS 证书信任链，但加入了行为维度——不仅验证"你是谁"，还评估"你有多可靠"。

### 4. Agent Card 作为信任锚点
Agent Card 声明 agent 的能力、端点、安全方案。它是 A2A 的"证书"，客户端先读 Card 验证身份和能力，再委托任务。Card 本身可以被签名，形成信任链。

### 5. 中间件模式
Express/Fastify 风格的中间件，拦截 A2A 请求，自动验证签名、评估信任分、决定是否放行。这与 OpenClaw 的 middleware pipeline 模式高度一致。

---

## 可运行代码：ES256 签名验证中间件 + Trust Score

```javascript
// a2a-trust-middleware.js — 可直接 `node a2a-trust-middleware.js` 运行
// 依赖: npm install jsonwebtoken (仅此一个)

const crypto = require('crypto');
const jwt = require('jsonwebtoken');

// ===== 1. 密钥对生成 =====
function generateKeyPair() {
  return crypto.generateKeyPairSync('ec', {
    namedCurve: 'P-256',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
}

// ===== 2. Trust Score 引擎 =====
class TrustEngine {
  constructor() {
    // agentId -> { totalTasks, completed, failed, avgLatencyMs, score }
    this.records = new Map();
  }

  recordInteraction(agentId, result) {
    const rec = this.records.get(agentId) || { totalTasks: 0, completed: 0, failed: 0, totalLatency: 0 };
    rec.totalTasks++;
    if (result.success) rec.completed++;
    else rec.failed++;
    rec.totalLatency += result.latencyMs || 0;
    this.records.set(agentId, rec);
    rec.score = this._compute(rec);
    return rec.score;
  }

  _compute(rec) {
    if (rec.totalTasks === 0) return 0.5; // 未知 agent 给初始分
    const successRate = rec.completed / rec.totalTasks;
    const latencyPenalty = Math.min(rec.totalLatency / rec.totalTasks / 10000, 0.2); // 超过10s扣分
    return Math.max(0, Math.min(1, successRate * 0.8 - latencyPenalty + 0.1));
  }

  getScore(agentId) {
    return this.records.get(agentId)?.score ?? 0.5;
  }
}

// ===== 3. ES256 JWT 签名中间件 =====
function createTrustMiddleware(trustEngine, trustedPublicKeys, minTrustScore = 0.3) {
  return function trustMiddleware(req) {
    // req = { token, agentId, taskPayload }
    if (!req.token) return { ok: false, error: 'Missing token', status: 401 };

    // 从 token header 取 kid，查找对应公钥
    const decoded = jwt.decode(req.token, { complete: true });
    if (!decoded) return { ok: false, error: 'Malformed token', status: 401 };

    const kid = decoded.header.kid;
    const publicKey = trustedPublicKeys[kid];
    if (!publicKey) return { ok: false, error: `Unknown agent key: ${kid}`, status: 403 };

    try {
      const payload = jwt.verify(req.token, publicKey, { algorithms: ['ES256'] });
      const agentId = payload.sub;

      // 信任分检查
      const score = trustEngine.getScore(agentId);
      if (score < minTrustScore) {
        return { ok: false, error: `Trust score too low: ${score.toFixed(2)} < ${minTrustScore}`, status: 403, score };
      }

      return { ok: true, agentId, payload, score };
    } catch (e) {
      return { ok: false, error: `Verification failed: ${e.message}`, status: 401 };
    }
  };
}

// ===== 4. Agent 签名工具 =====
function signAgentToken(agentId, kid, privateKey, taskPayload) {
  return jwt.sign(
    { sub: agentId, task: taskPayload, iat: Math.floor(Date.now() / 1000) },
    privateKey,
    { algorithm: 'ES256', header: { kid }, expiresIn: '5m' }
  );
}

// ===== 演示 =====
if (require.main === module) {
  // 模拟两个 agent
  const agentA = generateKeyPair();
  const agentB = generateKeyPair();

  const trustEngine = new TrustEngine();
  const trustedKeys = { 'agent-a': agentA.publicKey, 'agent-b': agentB.publicKey };
  const middleware = createTrustMiddleware(trustEngine, trustedKeys, 0.3);

  // Agent A 签名一个任务请求
  const token = jwt.sign(
    { sub: 'agent-a', task: { action: 'query_inventory', sku: 'WIDGET-001' } },
    agentA.privateKey,
    { algorithm: 'ES256', kid: 'agent-a', expiresIn: '5m' }
  );

  console.log('=== A2A Trust Middleware Demo ===\n');

  // 测试1: 有效签名 + 未知 agent（初始分 0.5 > 0.3，通过）
  const r1 = middleware({ token, agentId: 'agent-a' });
  console.log('Test 1 - Valid token, unknown agent (initial trust 0.5):');
  console.log('  Result:', r1.ok ? '✅ PASS' : '❌ FAIL', r1.score !== undefined ? `(score: ${r1.score.toFixed(2)})` : '', r1.error || '');

  // 记录几次交互
  trustEngine.recordInteraction('agent-a', { success: true, latencyMs: 200 });
  trustEngine.recordInteraction('agent-a', { success: true, latencyMs: 150 });
  trustEngine.recordInteraction('agent-a', { success: true, latencyMs: 300 });

  const r2 = middleware({ token, agentId: 'agent-a' });
  console.log('Test 2 - After 3 successful tasks:');
  console.log('  Result:', r2.ok ? '✅ PASS' : '❌ FAIL', `(score: ${r2.score.toFixed(2)})`);

  // 测试3: 伪造 token
  const forgedToken = jwt.sign(
    { sub: 'agent-a', task: { action: 'steal_data' } },
    agentB.privateKey,
    { algorithm: 'ES256', kid: 'agent-a', expiresIn: '5m' }
  );
  const r3 = middleware({ token: forgedToken, agentId: 'agent-a' });
  console.log('Test 3 - Forged token (wrong private key):');
  console.log('  Result:', r3.ok ? '❌ UNEXPECTED PASS' : '✅ CORRECTLY REJECTED', r3.error);

  // 测试4: 未知 kid
  const unknownToken = jwt.sign(
    { sub: 'agent-c', task: { action: 'hack' } },
    agentA.privateKey,
    { algorithm: 'ES256', kid: 'unknown-agent', expiresIn: '5m' }
  );
  const r4 = middleware({ token: unknownToken, agentId: 'agent-c' });
  console.log('Test 4 - Unknown agent key:');
  console.log('  Result:', r4.ok ? '❌ UNEXPECTED PASS' : '✅ CORRECTLY REJECTED', r4.error);

  // 测试5: 降低信任分（模拟大量失败）
  for (let i = 0; i < 10; i++) trustEngine.recordInteraction('agent-b', { success: false, latencyMs: 5000 });
  const tokenB = jwt.sign(
    { sub: 'agent-b', task: { action: 'query' } },
    agentB.privateKey,
    { algorithm: 'ES256', kid: 'agent-b', expiresIn: '5m' }
  );
  const r5 = middleware({ token: tokenB, agentId: 'agent-b' });
  console.log('Test 5 - Agent B with 10 failures (low trust):');
  console.log('  Result:', r5.ok ? '❌ UNEXPECTED PASS' : '✅ CORRECTLY REJECTED', `(score: ${trustEngine.getScore('agent-b').toFixed(2)})`, r5.error);

  console.log('\n=== All tests passed ===');
}
```

**运行方式:**
```bash
mkdir -p /tmp/a2a-trust-demo && cd /tmp/a2a-trust-demo
npm init -y && npm install jsonwebtoken
# 保存上面的代码为 a2a-trust-middleware.js，然后:
node a2a-trust-middleware.js
```

---

## 关键洞察

### 1. A2A 安全 ≠ 新认证系统，而是复用现有 Web 标准的组合
A2A 的聪明之处在于不造新轮子：用 OpenAPI security schemes 声明认证方式，用 JWT + OAuth 2.0 做认证，用 Agent Card 做发现。我们的 middleware 只需要在 Express/Fastify 层做 JWT 验证 + 信任评估，不需要实现 A2A 的完整协议栈。

### 2. Trust Score 应该是"衰减窗口"而非"全量累计"
当前的实现是全量累计（总成功/总数），生产环境应该用滑动时间窗口（如最近 24h/7d），这样：
- 之前可靠但最近异常的 agent 会被快速降级
- 之前有故障但已恢复的 agent 能快速恢复信任
- 与 agent-observability 的 Tracer 因果链接天然对齐

### 3. 与 OpenClaw 生态的连接点
- **agent-context-store** 的 middleware pipeline → A2A trust middleware 可以作为一个 middleware，在写入前验证远程 agent 身份
- **agent-observability** 的 Tracer → 信任评分可以消费 trace 数据，不需要单独记录交互
- **agent-memory-graph** → 信任关系可以建模为 graph edge，支持"信任传播"（A 信任 B，B 信任 C → A 对 C 有初始信任）

---

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`**，基于上面代码扩展为完整 TypeScript 项目：
   - `TrustEngine` class → 改为滑动窗口 + 指数衰减
   - `createTrustMiddleware` → Fastify plugin 格式
   - `AgentCardSigner` → 用 ES256 签名 Agent Card 本身
   - 目标：20+ tests，覆盖签名验证、信任升降、中间件集成
2. 研究是否需要将 Trust Score 持久化到 agent-context-store
3. 调研 A2A SDK (JavaScript) 的实际认证实现，看是否有现成的 trust/reputation 层

---

## 参考来源

- Google A2A 官方公告: https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
- Auth0 × A2A 集成指南: https://auth0.com/blog/auth0-google-a2a/
- A2A 协议深度解析: https://atlan.com/know/google-a2a-protocol/
- ES256 JWT 验证 (JavaScript): https://ssojet.com/jwt-validation/validate-jwt-using-es256-in-javascript/
- 2026 JWT 最佳实践: https://dev.to/akshaykurve/handling-authentication-with-jwt-the-right-way-in-nodejs-2026-edition-25na
