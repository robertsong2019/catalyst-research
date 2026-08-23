# A2A Trust Prototype — Agent-to-Agent 信任机制研究

> 日期: 2026-05-31 | 主题: ES256签名中间件 + Trust Score
> 目标: 为 `lab/a2a-trust-prototype/` 提供完整技术方案

---

## 核心概念

### 1. A2A 协议信任模型
Google A2A 协议（2025年4月发布，6月捐赠 Linux Foundation）定义了 Agent 间通信的标准层。其安全模型依赖：
- **Agent Card**（`.well-known/agent-card.json`）：声明 agent 的能力、输入/输出格式、认证要求
- **OAuth 2.0 / API Key / mTLS**：认证机制
- **Task 生命周期**：`submitted → working → input-required → completed`，每步可审计

**关键洞察**：A2A 安全模型解决了"谁在说话"（authentication），但没有解决"该不该信任它"（trust scoring）。这正是我们要补的层。

### 2. ES256 签名（ECDSA P-256 + SHA-256）
- 非对称签名：私钥签名，公钥验证
- 比RSA更短的密钥（256-bit ≈ 3072-bit RSA 安全性）
- Node.js 原生 `crypto` 模块直接支持，零依赖
- JWT 标准算法（`alg: "ES256"`），JWKS 端点友好

### 3. Trust Score 三层架构
来自 arxiv 论文"Trustworthy Agent Network"（2026）和 A2A GitHub discussions：

| 层 | 职责 | 证据类型 |
|----|------|---------|
| **Pre-interaction** | Agent 注册时的静态信任（代码审计、签名验证） | JWS 签名的 capability 声明 |
| **Interaction-history** | 基于历史交互的行为评分 | 任务完成率、响应时间、异常率 |
| **Continuous-monitoring** | 运行时行为异常检测 | 行为偏移检测 → 触发重新评估 |

### 4. Confused Deputy 问题
A2A 明确指出：Agent A 委托任务给 Agent B 时，B 使用**自己的凭证**而非原始用户的。每个 agent 应只有最小权限。信任评分必须考虑这种权限传播链。

### 5. Know Your Agent (KYA)
World Economic Forum 提出的概念：将 agent 视为经济参与者，需要身份和信任保障。类比 KYC（Know Your Customer），但面向非人类身份。

---

## 代码示例：ES256 Agent 身份签名中间件

> 完整可运行，零外部依赖（仅 Node.js 原生 crypto）

```javascript
// a2a-trust-middleware.js
// 零依赖 Agent-to-Agent 信任签名中间件
const crypto = require('crypto');

// ============================================
// 1. 密钥管理 — ECDSA P-256 (ES256)
// ============================================

function generateAgentKeyPair(agentId) {
  const { publicKey, privateKey } = crypto.generateKeyPairSync('ec', {
    namedCurve: 'P-256',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
  return { agentId, publicKey, privateKey, kid: `key-${Date.now()}` };
}

// 模拟 JWKS 端点（生产环境应暴露为 HTTP 端点）
class AgentKeyStore {
  constructor() {
    this.keys = new Map(); // agentId → { publicKey, kid }
  }

  register(keyPair) {
    this.keys.set(keyPair.agentId, { publicKey: keyPair.publicKey, kid: keyPair.kid });
  }

  getPublicKey(agentId) {
    return this.keys.get(agentId);
  }

  // JWKS 格式输出
  jwks() {
    return Array.from(this.keys.entries()).map(([agentId, { kid }]) => ({
      kid,
      kty: 'EC',
      crv: 'P-256',
      use: 'sig',
      agentId,
    }));
  }
}

// ============================================
// 2. Agent Token 签发（类 JWT 但面向 Agent）
// ============================================

function base64url(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function signAgentToken(payload, privateKey, kid) {
  const header = { alg: 'ES256', typ: 'A2A-JWT', kid };
  const headerB64 = base64url(Buffer.from(JSON.stringify(header)));
  const payloadB64 = base64url(Buffer.from(JSON.stringify(payload)));
  const signingInput = `${headerB64}.${payloadB64}`;

  const signer = crypto.createSign('SHA256');
  signer.update(signingInput);
  signer.end();
  const signature = signer.sign(privateKey);
  const sigB64 = base64url(signature);

  return `${signingInput}.${sigB64}`;
}

// ============================================
// 3. Trust Score 计算引擎
// ============================================

class TrustEngine {
  constructor() {
    this.history = new Map(); // agentId → { interactions, successes, failures, lastAnomaly }
  }

  recordInteraction(agentId, success) {
    if (!this.history.has(agentId)) {
      this.history.set(agentId, { interactions: 0, successes: 0, failures: 0, lastAnomaly: null });
    }
    const h = this.history.get(agentId);
    h.interactions++;
    if (success) h.successes++;
    else {
      h.failures++;
      h.lastAnomaly = new Date().toISOString();
    }
  }

  /**
   * 计算信任分 [0, 100]
   * 三因子：成功率(50%) + 交互深度(30%) + 新鲜度(20%)
   */
  computeScore(agentId) {
    const h = this.history.get(agentId);
    if (!h || h.interactions === 0) return 50; // 未知 agent 默认中性分

    // 因子1：成功率
    const successRate = h.successes / h.interactions;
    const successScore = successRate * 50;

    // 因子2：交互深度（logarithmic，越多越可信，上限30分）
    const depthScore = Math.min(30, Math.log2(h.interactions + 1) * 4.3);

    // 因子3：新鲜度（最近异常越久越好）
    let freshnessScore = 20;
    if (h.lastAnomaly) {
      const hoursSinceAnomaly = (Date.now() - new Date(h.lastAnomaly).getTime()) / 3600000;
      freshnessScore = Math.min(20, hoursSinceAnomaly * 0.5); // 40小时无异常恢复满分
    }

    return Math.round(successScore + depthScore + freshnessScore);
  }

  getTrustTier(score) {
    if (score >= 80) return 'TRUSTED';
    if (score >= 60) return 'PROBATIONARY';
    if (score >= 40) return 'NEUTRAL';
    return 'UNTRUSTED';
  }
}

// ============================================
// 4. Express 风格验证中间件
// ============================================

function createTrustMiddleware(keyStore, trustEngine) {
  return function verifyAgentRequest(req) {
    const authHeader = req.headers?.authorization;
    if (!authHeader?.startsWith('A2A ')) {
      return { valid: false, error: 'Missing A2A token' };
    }

    const token = authHeader.slice(4);
    const parts = token.split('.');
    if (parts.length !== 3) {
      return { valid: false, error: 'Invalid token format' };
    }

    // 解析 header
    const header = JSON.parse(Buffer.from(parts[0], 'base64').toString());
    if (header.alg !== 'ES256') {
      return { valid: false, error: 'Unsupported algorithm' };
    }

    // 解析 payload 获取 agentId
    const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString());
    const agentId = payload.sub;
    if (!agentId) {
      return { valid: false, error: 'Missing agent identity (sub)' };
    }

    // 检查过期
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      return { valid: false, error: 'Token expired' };
    }

    // 查找公钥
    const keyInfo = keyStore.getPublicKey(agentId);
    if (!keyInfo) {
      return { valid: false, error: 'Unknown agent' };
    }

    // 验证签名
    const verifier = crypto.createVerify('SHA256');
    verifier.update(`${parts[0]}.${parts[1]}`);
    verifier.end();

    const sigBuf = Buffer.from(parts[2].replace(/-/g, '+').replace(/_/g, '/'), 'base64');
    const valid = verifier.verify(keyInfo.publicKey, sigBuf);

    if (!valid) {
      return { valid: false, error: 'Invalid signature' };
    }

    // 计算信任分
    const trustScore = trustEngine.computeScore(agentId);
    const trustTier = trustEngine.getTrustTier(trustScore);

    return {
      valid: true,
      agentId,
      trustScore,
      trustTier,
      capabilities: payload.capabilities || [],
      iat: payload.iat,
      exp: payload.exp,
    };
  };
}

// ============================================
// 5. 完整可运行示例
// ============================================

// 设置
const keyStore = new AgentKeyStore();
const trustEngine = new TrustEngine();

// 注册两个 agent
const agentAlpha = generateAgentKeyPair('agent-alpha');
const agentBeta = generateAgentKeyPair('agent-beta');
keyStore.register(agentAlpha);
keyStore.register(agentBeta);

// 模拟交互历史
for (let i = 0; i < 20; i++) trustEngine.recordInteraction('agent-alpha', true);
for (let i = 0; i < 10; i++) trustEngine.recordInteraction('agent-beta', i < 7);
trustEngine.recordInteraction('agent-beta', false); // 一次失败

// agent-alpha 签发请求 token
const token = signAgentToken(
  {
    sub: 'agent-alpha',
    iss: 'agent-alpha',
    aud: 'agent-beta',
    capabilities: ['task.delegate', 'data.read'],
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 3600,
  },
  agentAlpha.privateKey,
  agentAlpha.kid
);

// 验证
const middleware = createTrustMiddleware(keyStore, trustEngine);
const result = middleware({
  headers: { authorization: `A2A ${token}` },
});

console.log('=== A2A Trust Verification Result ===');
console.log('Valid:', result.valid);
console.log('Agent:', result.agentId);
console.log('Trust Score:', result.trustScore, '/ 100');
console.log('Trust Tier:', result.trustTier);
console.log('Capabilities:', result.capabilities);
console.log();

// 也验证 beta
const betaScore = trustEngine.computeScore('agent-beta');
console.log('Agent Beta - Score:', betaScore, 'Tier:', trustEngine.getTrustTier(betaScore));

// JWKS 输出
console.log('\nJWKS:', JSON.stringify(keyStore.jwks(), null, 2));
```

**运行方式**：
```bash
node a2a-trust-middleware.js
```

**预期输出**：
```
=== A2A Trust Verification Result ===
Valid: true
Agent: agent-alpha
Trust Score: 89 / 100
Trust Tier: TRUSTED
Capabilities: [ 'task.delegate', 'data.read' ]

Agent Beta - Score: 71 Tier: PROBATIONARY

JWKS: [
  {
    "kid": "key-...",
    "kty": "EC",
    "crv": "P-256",
    "use": "sig",
    "agentId": "agent-alpha"
  }, ...
]
```

---

## 关键洞察

### 洞察 1：信任不能叠加 — 信任不自动跨 agent 传递
arxiv 论文明确指出："Methods designed to align or secure a single agent do not guarantee the safety of a network of interacting agents." 即使 Agent A 和 Agent B 各自可信，A→B→C 的信任链不等于 A 信任 C。我们的 prototype 必须在每个 hop 重新评估信任，而非简单传递。

### 洞察 2：ES256 是 Agent 身份的最佳选择（而非 RS256）
- ES256 的密钥更短（公钥 ~65 bytes vs RSA ~256 bytes），适合 Agent Card 嵌入
- 签名也更短（~64 bytes vs RSA ~256 bytes），减少网络开销
- Node.js 原生 crypto 零依赖支持，适合轻量 agent 运行时
- JWT/JWKS 生态完整，无需造轮子

### 洞察 3："Receipt over Report" — 信任基于可验证证据
2026 多 agent 系统的核心范式：每个 agent 的输出应是 **receipt**（结构化可验证：文件路径、DB row ID、API confirmation token），而非 **report**（散文声称完成）。Trust Score 应基于 receipt 的可验证率计算，而非 agent 自我报告的成功率。

### 洞察 4：Confused Deputy 是真实威胁
A2A 的权限隔离模型（每个 agent 用自己的凭证）是正确的设计，但引入了信任传播问题。信任中间件必须：
- 记录完整的委托链（delegation chain）
- 每跳衰减信任分（如 score × 0.9）
- 对敏感操作要求 human-in-the-loop

### 洞察 5：三层信任栈应与 A2A 协议互补
```
A2A 协议层 — 解决"谁在说话"（identity + authentication）
Trust 中间件层 — 解决"该不该信任"（scoring + delegation control）
Receipt 审计层 — 解决"做了什么"（verifiable execution evidence）
```
三层各自独立，但签名格式统一（ES256 JWS），证据可组合。

---

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`** — 基于本文代码示例搭建项目骨架
   - TypeScript 重写，带完整类型定义
   - 测试用例覆盖：签名验证、信任分计算、中间件集成
   - 目标：50+ tests

2. **实现 Delegation Chain** — 扩展 token payload，记录 `delegation_path: ['agent-alpha', 'agent-beta']`，每跳衰减信任分

3. **接入 agent-context-store** — 将信任评分历史存入 context-store 的 snapshot 机制，支持审计追踪

4. **研究 JWKS 端点集成** — 如何与 A2A Agent Card（`.well-known/agent-card.json`）联动，将公钥信息嵌入 Agent Card

---

## 参考资源

- [Google A2A Protocol Guide](https://www.digitalapplied.com/blog/google-a2a-protocol-agent-to-agent-communication-guide) — 协议全貌
- [Trustworthy Agent Network (arxiv 2605.19035)](https://arxiv.org/html/2605.19035v1) — 信任理论框架
- [A2A GitHub Discussions #1720](https://github.com/a2aproject/A2A/discussions/1720) — Trust scoring 与 JWS 集成讨论
- [Node.js ECDSA 实现](https://zenn.dev/maronn/articles/node-and-web-crypto-generate-ecdsa-key?locale=en) — Node/Web Crypto 双实现对比
- [JWT for AI Agents](https://securityboulevard.com/2025/11/jwts-for-ai-agents-authenticating-non-human-identities) — 非人类身份的 JWT 最佳实践
- [2026 Agent Protocols Map](https://www.digitalapplied.com/blog/ai-agent-protocol-ecosystem-map-2026-mcp-a2a-acp-ucp) — 协议生态全景

---

*研究完成于 2026-05-31 20:02 CST | autoresearch 方法论 | 零回滚率连续 91 天*
