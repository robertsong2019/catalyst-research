# A2A 协议与 Agent 间信任机制深度研究

> 日期: 2026-05-19 | 主题: Agent-to-Agent Protocol & Trust | 关联任务: lab/a2a-trust-prototype

---

## 核心概念 (5个)

### 1. Agent Card — 身份与能力声明
A2A 协议的核心发现机制。每个 Agent 在 `/.well-known/agent.json` 发布一个 JSON 文档，声明自己的身份、能力(skills)、认证方式和端点。类似于 API 的 OpenAPI spec，但是是给 Agent 用的"名片"。

```json
{
  "name": "ResearchAgent",
  "description": "深度搜索和分析研究 Agent",
  "url": "https://agent.example.com/a2a",
  "provider": { "organization": "Catalyst Labs" },
  "version": "1.0.0",
  "capabilities": { "streaming": true, "pushNotifications": true },
  "authentication": { "schemes": ["bearer", "mutualTLS"] },
  "skills": [
    {
      "id": "deep-search",
      "name": "Deep Search",
      "description": "对指定主题进行多源深度搜索",
      "inputModes": ["text", "data"],
      "outputModes": ["text", "data"]
    }
  ]
}
```

**关键洞察**: Agent Card 是 A2A 的"Claim-based trust"——自声明能力，无外部验证。这是最弱但最常见的信任模型。

### 2. Task Lifecycle — 任务状态机
A2A 的通信以任务为核心，状态流转：`submitted → working → (input-required) → completed | failed | canceled`

通信基于 JSON-RPC 2.0 over HTTPS，核心方法：
- `tasks/send` — 发起或继续任务
- `tasks/get` — 查询任务状态
- `tasks/cancel` — 取消任务
- `tasks/sendSubscribe` — SSE 流式更新

### 3. 六层信任模型 (from arxiv:2511.03434)
学术论文将 Agent 间信任分为 6 层，从弱到强：

| 层级 | 模型 | 机制 | A2A 现状 |
|------|------|------|----------|
| 1 | **Claim** | 自声明(Agent Card) | ✅ 核心机制 |
| 2 | **Brief** | 第三方背书(VC/TLS证书) | ⚠️ 仅传输层 |
| 3 | **Proof** | 密码学证明(ZKP/TEE/签名) | ❌ 未规定 |
| 4 | **Stake** | 经济质押(slashing) | ❌ 未规定 |
| 5 | **Reputation** | 历史信誉系统 | ❌ 未规定 |
| 6 | **Constraint** | 策略约束(least-privilege) | ✅ 企业级 |

**核心问题**: A2A 停留在 Claim + Constraint 层，缺乏 Proof 层——这是 `lab/a2a-trust-prototype` 要解决的。

### 4. A2A + MCP 互补架构
2026 年的生产级 Agent 系统同时使用两个协议：
- **MCP**: Agent ↔ 工具(纵向，一个 Agent 访问多个工具)
- **A2A**: Agent ↔ Agent(横向，Agent 间协作)

```
Orchestrator Agent
├── A2A → Research Agent → MCP(search, db)
├── A2A → Analysis Agent → MCP(code-exec)
└── A2A → Writing Agent  → MCP(docs, cms)
```

### 5. ES256 签名验证层
在 A2A 的 Claim-based trust 上叠加 Proof-based trust 的最低成本方案：ES256 (ECDSA + SHA-256 + P-256曲线) 签名。

优势：比 RSA 签名更短(64 bytes vs 256 bytes)、更快、密钥更小。适合 Agent 间高频通信。

---

## 可运行代码: Agent 间信任中间件原型

```js
// a2a-trust-middleware.js
// ES256 签名验证 + Trust Score 计算的 A2A 中间件原型
// 运行: node a2a-trust-middleware.js

const crypto = require('crypto');

// ============================================================
// 1. 密钥生成工具
// ============================================================
function generateES256KeyPair() {
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ec', {
    namedCurve: 'P-256',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
  return { privateKey, publicKey };
}

// ============================================================
// 2. Agent Card 签名与验证
// ============================================================
function signAgentCard(agentCard, privateKey) {
  const canonical = JSON.stringify(agentCard, Object.keys(agentCard).sort());
  const sign = crypto.createSign('SHA256');
  sign.update(canonical);
  sign.end();
  const signature = sign.sign(privateKey, 'base64');
  return { ...agentCard, proof: { type: 'ES256', signature, created: Date.now() } };
}

function verifyAgentCard(signedCard, publicKey) {
  const { proof, ...card } = signedCard;
  if (!proof || proof.type !== 'ES256') {
    return { valid: false, reason: 'missing or unsupported proof type' };
  }
  // 检查签名是否过期 (默认 1 小时)
  if (Date.now() - proof.created > 3600000) {
    return { valid: false, reason: 'signature expired' };
  }
  const canonical = JSON.stringify(card, Object.keys(card).sort());
  const verify = crypto.createVerify('SHA256');
  verify.update(canonical);
  verify.end();
  const valid = verify.verify(publicKey, proof.signature, 'base64');
  return { valid, reason: valid ? 'ok' : 'signature mismatch' };
}

// ============================================================
// 3. Trust Score 计算
// ============================================================
class TrustScorer {
  constructor(config = {}) {
    this.weights = {
      signatureValid: config.weights?.signatureValid ?? 0.30,
      knownIssuer: config.weights?.knownIssuer ?? 0.25,
      reputationScore: config.weights?.reputationScore ?? 0.20,
      taskSuccessRate: config.weights?.taskSuccessRate ?? 0.15,
      stakeAmount: config.weights?.stakeAmount ?? 0.10,
    };
    this.knownIssuers = new Set(config.knownIssuers ?? []);
    this.reputationDB = new Map(config.reputation ?? []);
  }

  score(agentCard, verificationResult) {
    let score = 0;
    const details = {};

    // Proof-based: 签名是否有效
    details.signatureValid = verificationResult.valid;
    score += verificationResult.valid ? this.weights.signatureValid : 0;

    // Brief-based: 是否来自已知签发者
    const issuer = agentCard.provider?.organization ?? '';
    details.knownIssuer = this.knownIssuers.has(issuer);
    score += details.knownIssuer ? this.weights.knownIssuer : 0;

    // Reputation: 历史信誉
    const rep = this.reputationDB.get(issuer) ?? 0;
    details.reputationScore = rep;
    score += (Math.min(rep, 1.0)) * this.weights.reputationScore;

    // Task success rate (从 card metadata 读取)
    const successRate = agentCard.metadata?.taskSuccessRate ?? 0;
    details.taskSuccessRate = successRate;
    score += successRate * this.weights.taskSuccessRate;

    // Stake (从 card metadata 读取)
    const stake = agentCard.metadata?.stakeAmount ?? 0;
    details.stakeAmount = stake;
    score += Math.min(stake / 100, 1.0) * this.weights.stakeAmount;

    return { score: Math.round(score * 100) / 100, details };
  }
}

// ============================================================
// 4. 中间件工厂
// ============================================================
function createTrustMiddleware(scorer, threshold = 0.5) {
  return function trustMiddleware(req, res, next) {
    const agentCard = req.body?.agentCard;
    const signature = req.body?.signature;
    if (!agentCard) {
      return res.status(400).json({ error: 'missing agentCard' });
    }
    // 这里简化了，实际需要用 card 中的 public key 验证
    const verification = { valid: !!signature }; // 生产环境用 verifyAgentCard
    const { score, details } = scorer.score(agentCard, verification);
    if (score < threshold) {
      return res.status(403).json({ error: 'trust score below threshold', score, details });
    }
    req.trustScore = score;
    req.trustDetails = details;
    next?.();
  };
}

// ============================================================
// 5. 演示运行
// ============================================================
console.log('=== A2A Trust Middleware Prototype ===\n');

// 生成密钥对
const agentKeys = generateES256KeyPair();
console.log('1. Generated ES256 key pair (P-256 curve)');

// 创建 Agent Card
const rawCard = {
  name: 'CatalystResearch',
  description: '深度搜索和分析研究 Agent',
  url: 'https://catalyst.example.com/a2a',
  provider: { organization: 'Catalyst Labs' },
  version: '1.0.0',
  skills: [{ id: 'deep-search', name: 'Deep Search' }],
  metadata: { taskSuccessRate: 0.92, stakeAmount: 50 },
};

// 签名 Agent Card
const signedCard = signAgentCard(rawCard, agentKeys.privateKey);
console.log('2. Signed Agent Card with ES256');
console.log('   Proof:', { type: signedCard.proof.type, created: new Date(signedCard.proof.created).toISOString() });

// 验证签名
const result = verifyAgentCard(signedCard, agentKeys.publicKey);
console.log('3. Verification:', result);

// 用错误公钥验证（应该失败）
const fakeKeys = generateES256KeyPair();
const badResult = verifyAgentCard(signedCard, fakeKeys.publicKey);
console.log('4. Verification with wrong key:', badResult);

// Trust Score 计算
const scorer = new TrustScorer({
  knownIssuers: ['Catalyst Labs', 'Trusted Corp'],
  reputation: [['Catalyst Labs', 0.85]],
});

const trustResult = scorer.score(signedCard, result);
console.log('\n5. Trust Score:', trustResult.score, '/ 1.0');
console.log('   Details:', JSON.stringify(trustResult.details, null, 2));

// 中间件测试
const middleware = createTrustMiddleware(scorer, 0.5);
const mockReq = { body: { agentCard: signedCard, signature: signedCard.proof.signature } };
const mockRes = { status: (code) => ({ json: (d) => console.log(`\n6. Middleware result: HTTP ${code}`, d) }) };
middleware(mockReq, mockRes, () => {
  console.log('\n6. Middleware PASSED - trust score:', mockReq.trustScore);
  console.log('   Trust details:', mockReq.trustDetails);
});

console.log('\n=== Prototype Complete ===');
```

---

## 关键洞察 (5条)

### 洞察 1: A2A 的信任是"声明式"的，需要 Proof 层补强
A2A 原生只做 Claim-based trust（Agent 自说自话）。要实现真正的 Agent 间信任，至少需要叠加 Proof 层（ES256 签名验证）。这意味着 `lab/a2a-trust-prototype` 的核心价值在于：**在 A2A 协议之上提供可验证的信任层**。

### 洞察 2: Trust Score 应该是多维度加权计算
单一信号（如签名验证）不足以评估信任。6 层信任模型告诉我们：签名(Proof) + 已知签发者(Brief) + 历史信誉(Reputation) + 任务成功率 + 质押金额(Stake) 的加权组合才是实用方案。

### 洞察 3: Agent Card 签名是 A2A 生态的"Web of Trust"入口
类似 PGP 的 Web of Trust，Agent 可以互相签注对方的 Agent Card，形成信任链。这比中心化 CA 更适合去中心化 Agent 网络。

### 洞察 4: A2A + MCP 的双层架构是 2026 年的标配模式
生产系统中，A2A 处理 Agent 间通信，MCP 处理 Agent-工具通信。两者不竞争而是互补。lab/a2a-trust-prototype 应该设计为与 MCP 无关的纯 A2A 层中间件。

### 洞察 5: Node.js ES256 性能足够应对 Agent 间高频通信
ECDSA P-256 签名在 Node.js 中单次约 0.5ms，验证约 0.3ms。即使每秒 1000 次 Agent 间请求，签名验证的 CPU 开销也 < 1 核。ES256 是 Agent 间信任层的最佳选择。

---

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`** — 基于本研究的代码原型，扩展为完整项目：
   - `src/keys.ts` — ES256 密钥生成/管理
   - `src/agent-card.ts` — Agent Card 签名/验证
   - `src/trust-scorer.ts` — 多维度 Trust Score 计算
   - `src/middleware.ts` — Express/Fastify 中间件
   - `tests/` — 目标 30+ tests

2. **研究 Agent Card 签注链(endorsement chain)** — 实现 Web of Trust 模式，让可信 Agent 签注新 Agent 的 Card

3. **探索与 OpenClaw 的集成点** — 当前 OpenClaw 已有 MCP 和 subagent 机制，A2A trust 中间件可以作为 Agent 间通信的安全层

---

## 参考资源

- [Google A2A Protocol 官方公告](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) (2025-04)
- [Inter-Agent Trust Models (arxiv:2511.03434)](https://arxiv.org/html/2511.03434) — 六层信任模型学术论文
- [A2A Protocol 深度解析 - Codilime](https://codilime.com/blog/a2a-protocol-explained/)
- [AI Agent Protocol Ecosystem Map 2026](https://www.digitalapplied.com/blog/ai-agent-protocol-ecosystem-map-2026-mcp-a2a-acp-ucp)
- [Security Analysis of Agentic AI Communication Protocols (arxiv:2511.03841)](https://arxiv.org/html/2511.03841v1)
- [Linux Foundation A2A Project](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents) (2025-06)
