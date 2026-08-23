# A2A Trust Prototype — Agent-to-Agent 信任中间件研究

> 日期: 2026-05-28 | 关联项目: `lab/a2a-trust-prototype/`

## 核心概念

### 1. Agent Card（代理卡片）
A2A 协议中每个 Agent 声明自己的身份、能力、认证方式的 JSON 文档。类似 OpenAPI spec 但面向 Agent。关键字段：
- `url` — Agent 端点
- `capabilities` — 支持的技能/方法
- `authentication.schemes` — 支持的认证方式（OAuth2, API Key, mTLS 等）

### 2. ES256 签名（ECDSA + P-256 + SHA-256）
使用椭圆曲线签名确保 Agent 间消息的完整性和来源验证。相比 RS256：
- 密钥更短（256 bit vs 2048+ bit）
- 签名更快（EC 运算 vs 大数模幂）
- Token 更紧凑

### 3. Trust Score（信任评分）
动态评估 Agent 可信度的量化指标。基于：
- 签名验证历史（成功/失败比）
- 任务完成率
- 响应时间稳定性
- 衰减机制（长期不交互→信任衰减）

### 4. Zero-Trust Agent Network
CSA 用 MAESTRO 框架对 A2A 做了威胁建模，核心观点：Agent 身份是动态的，凭证生命周期短，需要在每次交互时验证。

### 5. A2A 与 MCP 的互补关系
- **MCP**：Agent ↔ Tool/Context（纵向，单 Agent 获取工具）
- **A2A**：Agent ↔ Agent（横向，多 Agent 协作）
- 两者在信任层面都需要签名验证，但 A2A 的挑战在于跨组织信任传递

## 可运行代码：A2A Trust Middleware

```js
// a2a-trust.js — Agent-to-Agent ES256 签名中间件 + Trust Score
// 零依赖，仅用 Node.js crypto

const crypto = require('crypto');

// ============================================
// 1. 密钥管理 — 生成/导入 ES256 密钥对
// ============================================

function generateKeyPair() {
  return crypto.generateKeyPairSync('ec', {
    namedCurve: 'P-256',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
}

// ============================================
// 2. Agent Card — 声明 Agent 身份
// ============================================

function createAgentCard({ id, name, capabilities = [], publicKey }) {
  return {
    id,                    // agent-xxx
    name,
    capabilities,          // ['search', 'translate', ...]
    publicKey,             // PEM format
    authentication: { schemes: ['ES256'] },
    createdAt: Date.now(),
  };
}

// ============================================
// 3. A2A Message 签名与验证
// ============================================

function signA2AMessage(senderPrivateKey, { from, to, payload, type = 'task' }) {
  const message = {
    from,
    to,
    type,
    payload,
    timestamp: Date.now(),
    nonce: crypto.randomBytes(16).toString('hex'),
  };

  // 构造待签名内容: header.payload (JWT-like)
  const header = Buffer.from(JSON.stringify({ alg: 'ES256', typ: 'A2A' }))
    .toString('base64url');
  const body = Buffer.from(JSON.stringify(message))
    .toString('base64url');
  const signingInput = `${header}.${body}`;

  const signer = crypto.createSign('SHA256');
  signer.update(signingInput);
  signer.end();

  const signature = signer.sign(senderPrivateKey);
  // 转为 base64url (IEEE P1363 格式, Node.js 默认 DER → 需要 dsaEncoding)
  // 注意: crypto.sign 默认输出 DER, 但用 createSign + sign() 也输出 DER
  // 这里用 crypto.sign() 配合 dsaEncoding 更简洁:

  return {
    header,
    body,
    message,
    signature: signature.toString('base64url'),
  };
}

// 更简洁的签名方式 (推荐):
function signMessage(privateKeyPem, from, to, payload) {
  const message = { from, to, payload, ts: Date.now(), nonce: crypto.randomUUID() };
  const data = Buffer.from(JSON.stringify(message));

  const signature = crypto.sign('SHA256', data, {
    key: privateKeyPem,
    dsaEncoding: 'ieee-p1363',  // JWT 标准格式
  });

  return { message, signature: signature.toString('base64url') };
}

function verifyMessage(publicKeyPem, message, signature) {
  const data = Buffer.from(JSON.stringify(message));
  const sig = Buffer.from(signature, 'base64url');

  return crypto.verify('SHA256', data, {
    key: publicKeyPem,
    dsaEncoding: 'ieee-p1363',
  }, sig);
}

// ============================================
// 4. Trust Score 引擎
// ============================================

class TrustEngine {
  constructor(decayFactor = 0.99, maxScore = 100, minScore = 0) {
    this.scores = new Map();       // agentId → score
    this.history = new Map();      // agentId → [{ ts, delta, reason }]
    this.decayFactor = decayFactor;
    this.maxScore = maxScore;
    this.minScore = minScore;
  }

  // 获取信任分
  getScore(agentId) {
    return this.scores.get(agentId) ?? 50; // 未知 agent 默认 50 (中立)
  }

  // 验证签名并更新信任分
  verifyAndTrack(agentId, publicKeyPem, message, signature) {
    const valid = verifyMessage(publicKeyPem, message, signature);

    if (valid) {
      this._adjust(agentId, +2, 'signature_valid');
    } else {
      this._adjust(agentId, -20, 'signature_invalid'); // 无效签名重罚
    }

    return valid;
  }

  // 记录任务结果
  recordTaskResult(agentId, success) {
    this._adjust(agentId, success ? +5 : -10, success ? 'task_success' : 'task_failed');
  }

  // 信任衰减 (定时调用)
  decay() {
    for (const [agentId, score] of this.scores) {
      const newScore = Math.max(this.minScore, score * this.decayFactor);
      this.scores.set(agentId, newScore);
    }
  }

  // 信任决策: 是否允许交互
  shouldTrust(agentId, threshold = 30) {
    return this.getScore(agentId) >= threshold;
  }

  _adjust(agentId, delta, reason) {
    const current = this.getScore(agentId);
    const updated = Math.min(this.maxScore, Math.max(this.minScore, current + delta));
    this.scores.set(agentId, updated);

    if (!this.history.has(agentId)) this.history.set(agentId, []);
    this.history.get(agentId).push({ ts: Date.now(), delta, reason });
  }
}

// ============================================
// 5. Express 中间件 (即插即用)
// ============================================

function a2aTrustMiddleware(trustEngine, getPublicKey) {
  return (req, res, next) => {
    const agentId = req.headers['x-agent-id'];
    const signature = req.headers['x-agent-signature'];
    const timestamp = req.headers['x-agent-timestamp'];

    if (!agentId || !signature) {
      return res.status(401).json({ error: 'Missing agent authentication headers' });
    }

    // 重放攻击防护: 拒绝 >5min 的消息
    if (timestamp && Math.abs(Date.now() - Number(timestamp)) > 5 * 60 * 1000) {
      return res.status(401).json({ error: 'Message expired' });
    }

    // 信任分检查
    if (!trustEngine.shouldTrust(agentId)) {
      return res.status(403).json({ error: 'Agent trust score too low', score: trustEngine.getScore(agentId) });
    }

    // 验证签名
    const message = { method: req.method, path: req.path, body: req.body, ts: timestamp };
    const publicKey = getPublicKey(agentId);

    if (!publicKey) {
      return res.status(401).json({ error: 'Unknown agent' });
    }

    const valid = trustEngine.verifyAndTrack(agentId, publicKey, message, signature);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid signature', score: trustEngine.getScore(agentId) });
    }

    req.agentId = agentId;
    req.trustScore = trustEngine.getScore(agentId);
    next();
  };
}

// ============================================
// 6. 完整演示
// ============================================

// 生成两对密钥 (模拟两个 Agent)
const agentA = generateKeyPair();
const agentB = generateKeyPair();

// 创建 Agent Card
const cardA = createAgentCard({
  id: 'agent-alpha',
  name: 'Alpha Search Agent',
  capabilities: ['search', 'summarize'],
  publicKey: agentA.publicKey,
});

const cardB = createAgentCard({
  id: 'agent-beta',
  name: 'Beta Translation Agent',
  capabilities: ['translate', 'detect-language'],
  publicKey: agentB.publicKey,
});

// 初始化信任引擎
const trust = new TrustEngine();

// 模拟 A→B 通信
console.log('=== A2A Trust Demo ===\n');

// Agent A 签名消息发给 B
const msg = { from: cardA.id, to: cardB.id, payload: { task: 'search', query: 'A2A protocol' } };
const { message, signature } = signMessage(agentA.privateKey, msg.from, msg.to, msg.payload);

console.log('1. Agent A signs message to B');
console.log('   Message:', JSON.stringify(message));
console.log('   Signature:', signature.slice(0, 32) + '...\n');

// Agent B 验证
const valid = verifyMessage(cardA.publicKey, message, signature);
console.log('2. Agent B verifies signature:', valid ? '✅ VALID' : '❌ INVALID');

// 通过 Trust Engine 验证
const trusted = trust.verifyAndTrack(cardA.id, cardA.publicKey, message, signature);
console.log('3. Trust engine result:', trusted ? '✅ TRUSTED' : '❌ UNTRUSTED');
console.log('   Trust score for', cardA.id, ':', trust.getScore(cardA.id));

// 模拟多次交互
for (let i = 0; i < 5; i++) {
  const { message: m, signature: s } = signMessage(agentA.privateKey, cardA.id, cardB.id, { task: `task-${i}` });
  trust.verifyAndTrack(cardA.id, cardA.publicKey, m, s);
  trust.recordTaskResult(cardA.id, true);
}
console.log('\n4. After 5 successful tasks, score:', trust.getScore(cardA.id));

// 模拟恶意签名 (用错误的密钥签名)
const { signature: badSig } = signMessage(agentB.privateKey, cardA.id, cardB.id, { task: 'forged' });
const forged = trust.verifyAndTrack(cardA.id, cardA.publicKey,
  { from: cardA.id, to: cardB.id, payload: { task: 'forged' }, ts: Date.now(), nonce: 'x' }, badSig);
console.log('5. Forged signature test:', forged ? '❌ SECURITY ISSUE' : '✅ REJECTED');
console.log('   Score after forgery attempt:', trust.getScore(cardA.id));

// 信任衰减演示
console.log('\n6. Trust decay after 100 cycles:');
for (let i = 0; i < 100; i++) trust.decay();
console.log('   Score:', trust.getScore(cardA.id).toFixed(2));

console.log('\n=== Demo Complete ===');
```

运行方式: `node a2a-trust.js`（零依赖，Node.js 18+）

## 关键洞察

### 1. A2A 信任 ≠ 传统 API 认证
传统 API 认证解决"你是谁"，A2A 还需要解决"你可信吗"。Trust Score 引入了行为维度的动态评估——不是一劳永逸的认证，而是持续观察。这与 CSA MAESTRO 框架的 Layer 3（Agent Frameworks）威胁模型一致。

### 2. ES256 的 Node.js 陷阱
Node.js `crypto` 模块的 ECDSA 默认使用 DER 格式输出，但 JWT 标准要求 IEEE P1363 格式。必须设置 `dsaEncoding: 'ieee-p1363'`，否则签名验证会失败。这是实际开发中最容易踩的坑。

### 3. 信任衰减是关键设计
没有衰减的信任系统会被历史行为绑架。Trust Score 应该：
- 正常交互小增（+2~+5）
- 异常行为重罚（-10~-20）
- 自然衰减（每周期 ×0.99）
- 未知 Agent 起始分 50（中立，非零）

### 4. A2A 协议状态（2026-05）
- Linux Foundation 管理，100+ 公司支持
- 认证方案: OAuth2 + OpenID Connect + API Key + mTLS（Agent Card 声明）
- Auth0 已接入 A2A 认证
- 生产部署案例仍然有限（Semantic Kernel travel planning demo）

### 5. 与现有项目关联
- **openclaw-langgraph-bridge Supervisor**: 多 Agent 调度器已有健康追踪，可叠加 Trust Score 做故障权重
- **agent-observability**: audit 日志可 feeding Trust Engine
- **AMS**: embedding 可用于 Agent 能力匹配 + 信任传播

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`**，基于以上代码搭建项目骨架
2. **实现 Agent Card 注册表**（内存 + JSON 持久化），支持 Agent 发现
3. **添加 Express 中间件**，集成到现有 HTTP 服务中
4. **写测试**：签名验证、信任衰减、重放攻击防护、伪造检测
5. **后续**: 探索与 A2A 官方 SDK 的互操作性（Agent Card 格式对齐）

## 参考资料

- [A2A Protocol - Google Developers Blog](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability) (Apr 2025)
- [Building Secure A2A Application - arXiv](https://arxiv.org/html/2504.16902v1)
- [CSA MAESTRO Threat Modeling for A2A](https://cloudsecurityalliance.org/blog/2025/04/30/threat-modeling-google-s-a2a-protocol-with-the-maestro-framework)
- [Auth0 + Google A2A Authentication](https://auth0.com/blog/auth0-google-a2a)
- [Node.js ES256 Signature Format Issue](https://stackoverflow.com/questions/76164824)
