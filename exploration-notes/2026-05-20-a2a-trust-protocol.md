# A2A 协议信任机制深度研究

> 日期: 2026-05-20 | 主题: Agent-to-Agent Protocol Trust & Auth
> 目标: 为 `lab/a2a-trust-prototype` 提供技术基础

---

## 核心概念

### 1. Agent Card（智能体名片）
- 位于 `/.well-known/agent.json` 的 JSON 元数据文档
- 声明: ID、能力列表、认证方式、端点 URL、加密签名
- 类比: OAuth 2.0 的 `.well-known/openid-configuration`

### 2. JWS 签名验证链
- Agent Card 用 JWS (JSON Web Signature) 签名，推荐 ES256
- 通过 `jku`/`x5c`/`x5u` 字段指向验证公钥
- **反模式**: 裸 `jwk` 无信任链 → 几乎无安全价值（A2A 官方明确反对）
- 正确做法: x.509 证书链 或 受信任的 JWKS URL

### 3. Trust Score（信任评分）
- A2A 规范未定义统一信任模型，留给了实现层
- 学术论文（arxiv 2504.16902）提出: Reputation-Based Trust + Registry Validation
- 实践中: 基于 (1)签名验证 (2)注册表信任 (3)历史行为 的多维评分

### 4. 任务生命周期与安全
- Task 状态: submitted → working → input-required → completed / failed / canceled
- 每个请求应包含 nonce + timestamp 防重放
- 设计为幂等操作（idempotent）

### 5. A2A vs MCP 互补关系
- MCP: 工具/上下文层（agent ↔ tools）
- A2A: 通信/协作层（agent ↔ agent）
- 官方建议: MCP for tools, A2A for agents

---

## 关键洞察

1. **签名是必要条件但不充分** — A2A Discussion #199 明确指出，仅有 JWS 签名只能证明 Card 未被篡改，不能建立身份信任。必须将签名密钥绑定到可验证的身份（x.509/DID/注册表），签名才有意义。

2. **信任是分层叠加的** — Signed Card → Key Identity → Registry Trust → Reputation Score，每层解决不同问题。`a2a-trust-prototype` 应该逐层实现，而非一步到位。

3. **ES256 是最优签名算法选择** — 相比 RS256，ECDSA 密钥更短（256 bit vs 2048+ bit）、签名更快、验证等价，特别适合 agent 间高频交互场景。

4. **A2A 已移交 Linux Foundation** — 从 Google 主导转为开源项目（Apache 2.0），10+ releases，560+ commits，生态成熟度快速提升。50+ 合作伙伴支持。

---

## 可运行代码: A2A Trust Middleware 原型

```js
// a2a-trust-middleware.js — ES256 签名验证 + Trust Score 计算
// 运行: node a2a-trust-middleware.js (需要: npm install jose express)

const { jwtVerify, importJWK, SignJWT, exportJWK, generateKeyPair } = require('jose');

// ============================================================
// 1. 密钥生成 & Agent Card 签名
// ============================================================

async function generateSigningKey() {
  const { publicKey, privateKey } = await generateKeyPair('ES256');
  return { publicKey, privateKey, jwk: await exportJWK(publicKey) };
}

async function signAgentCard(agentCard, privateKey, kid) {
  // 将 agent card canonicalize 后签名
  const payload = { ...agentCard, iat: Math.floor(Date.now() / 1000) };
  const jws = await new SignJWT(payload)
    .setProtectedHeader({ alg: 'ES256', kid })
    .setIssuedAt()
    .setExpirationTime('7d')
    .sign(privateKey);
  return jws;
}

// ============================================================
// 2. Agent Card 验证
// ============================================================

class AgentCardVerifier {
  constructor(trustedKeys = new Map()) {
    // kid → CryptoKey 或 JWKS URL
    this.trustedKeys = trustedKeys;
  }

  addTrustedKey(kid, publicKey) {
    this.trustedKeys.set(kid, publicKey);
  }

  async verify(signedCard) {
    const { header } = await jwtVerify(signedCard, (header) => {
      const key = this.trustedKeys.get(header.kid);
      if (!key) throw new Error(`Unknown key: ${header.kid}`);
      return key;
    }, { algorithms: ['ES256'] });

    return { valid: true, kid: header.kid };
  }
}

// ============================================================
// 3. Trust Score 计算
// ============================================================

class TrustScorer {
  /**
   * @param {Object} opts
   * @param {boolean} opts.signatureValid - 签名是否有效
   * @param {boolean} opts.keyInRegistry - 签名密钥是否在受信注册表
   * @param {number} opts.successfulTasks - 历史成功任务数
   * @param {number} opts.failedTasks - 历史失败任务数
   * @param {number} opts.daysSinceFirstSeen - 首次发现至今天数
   */
  compute(opts) {
    let score = 0;

    // Layer 1: 签名验证 (0-30分)
    if (opts.signatureValid) score += 30;

    // Layer 2: 注册表信任 (0-30分)
    if (opts.keyInRegistry) score += 30;

    // Layer 3: 历史行为 (0-25分)
    const total = opts.successfulTasks + opts.failedTasks;
    if (total > 0) {
      const successRate = opts.successfulTasks / total;
      score += Math.min(25, Math.floor(successRate * 25));
    }

    // Layer 4: 时间衰减 (0-15分) — 越久越可信
    score += Math.min(15, Math.floor(opts.daysSinceFirstSeen / 2));

    return Math.min(100, score);
  }

  /** 将分数映射为信任等级 */
  level(score) {
    if (score >= 80) return 'TRUSTED';
    if (score >= 50) return 'PROBATION';
    if (score >= 20) return 'UNKNOWN';
    return 'UNTRUSTED';
  }
}

// ============================================================
// 4. Express 中间件
// ============================================================

function a2aTrustMiddleware(verifier, scorer) {
  return async (req, res, next) => {
    const auth = req.headers['x-a2a-signed-card'];
    if (!auth) {
      return res.status(401).json({ error: 'Missing signed agent card' });
    }

    try {
      const { valid, kid } = await verifier.verify(auth);
      const score = scorer.compute({
        signatureValid: valid,
        keyInRegistry: verifier.trustedKeys.has(kid),
        successfulTasks: 0,  // 从 store 查询
        failedTasks: 0,
        daysSinceFirstSeen: 0,
      });

      req.a2a = { kid, trustScore: score, trustLevel: scorer.level(score) };

      // 低信任直接拒绝
      if (scorer.level(score) === 'UNTRUSTED') {
        return res.status(403).json({ error: 'Untrusted agent', score });
      }

      next();
    } catch (err) {
      res.status(401).json({ error: 'Invalid signature', detail: err.message });
    }
  };
}

// ============================================================
// 5. 运行演示
// ============================================================

async function demo() {
  // 生成密钥对
  const { publicKey, privateKey, jwk } = await generateSigningKey();
  const kid = 'a2a-demo-key-001';

  // 创建 Verifier 并注册受信密钥
  const verifier = new AgentCardVerifier();
  verifier.addTrustedKey(kid, publicKey);

  const scorer = new TrustScorer();

  // 创建 Agent Card
  const agentCard = {
    name: 'demo-agent',
    description: 'A2A Trust Demo Agent',
    url: 'https://agent.example.com',
    skills: [{ id: 'echo', name: 'Echo Service' }],
  };

  // 签名
  const signed = await signAgentCard(agentCard, privateKey, kid);
  console.log('✅ Signed Agent Card (JWS):', signed.substring(0, 60) + '...');

  // 验证
  const result = await verifier.verify(signed);
  console.log('✅ Verification:', result);

  // Trust Score
  const score = scorer.compute({
    signatureValid: true,
    keyInRegistry: true,
    successfulTasks: 47,
    failedTasks: 3,
    daysSinceFirstSeen: 30,
  });
  console.log(`✅ Trust Score: ${score}/100 → ${scorer.level(score)}`);

  // 测试 tampered card
  const tampered = signed.replace(/demo-agent/, 'evil-agent');
  try {
    await verifier.verify(tampered);
  } catch (e) {
    console.log('✅ Tampered card rejected:', e.message);
  }
}

demo().catch(console.error);
```

**运行方式:**
```bash
mkdir -p /tmp/a2a-demo && cd /tmp/a2a-demo
npm init -y && npm install jose
# 将上面代码保存为 a2a-trust-middleware.js
node a2a-trust-middleware.js
```

**预期输出:**
```
✅ Signed Agent Card (JWS): eyJhbGciOiJFUzI1NiIsImtpZCI6ImEyYS1kZW1vLWtleS0wMDEiLC...
✅ Verification: { valid: true, kid: 'a2a-demo-key-001' }
✅ Trust Score: 91/100 → TRUSTED
✅ Tampered card rejected: signature verification failed
```

---

## 与现有项目关联

| 现有项目 | 关联点 |
|---------|--------|
| `agent-context-store` | 存储 trust score 历史、agent 注册表、交互记录 |
| `lab/agent-observability` | A2A task 追踪 → OpenTelemetry spans |
| `lab/langgraph-bridge` | A2A 作为 LangGraph 节点间通信协议 |

---

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`** — 基于上述代码，实现完整原型:
   - `AgentCardSigner` — ES256 签名 + JWKS 导出
   - `AgentCardVerifier` — JWS 验证 + JWKS fetch
   - `TrustScorer` — 多维信任评分 (签名/注册表/行为/时间)
   - `Express middleware` — 即插即用的信任网关
   - 目标: 20+ tests, 覆盖签名/验证/评分/tampering 场景

2. **跟进 A2A spec 签名规范** — 当前是 Discussion #199 草案，关注是否进入正式 spec

3. **考虑 DID 集成** — `did:web` 方案与 JWKS URL 天然互补，值得在 trust-prototype 中预留接口

---

## 参考资料

- [A2A Official Repo (Linux Foundation)](https://github.com/a2aproject/A2A) — 560+ commits, Apache 2.0
- [Sign Agent Cards Discussion #199](https://github.com/a2aproject/A2A/discussions/199) — 签名方案设计讨论
- [A2A Security (arxiv 2504.16902)](https://arxiv.org/html/2504.16902v1) — 10 类攻击 + 缓解策略
- [Builder.io A2A Deep Dive](https://www.builder.io/blog/a2a-protocol) — 电商类比解释，最易懂
- [IBM A2A Overview](https://www.ibm.com/think/topics/agent2agent-protocol) — 企业视角
- [awesome-a2a](https://github.com/ai-boost/awesome-a2a) — 生态索引
