# A2A Trust Protocol: Agent-to-Agent 认证与信任机制

> 研究日期: 2026-06-01
> 主题: Google A2A 协议中的 Agent 身份验证、签名机制、信任评分
> 目标: 为 lab/a2a-trust-prototype 提供技术基础

---

## 核心概念

### 1. Agent Card 签名 (JWS + JCS)

A2A 协议 v1.2 引入了 **Signed Agent Cards**。Agent Card（`/.well-known/agent.json`）可以用 JSON Web Signature (RFC 7515) 签名，确保来源可信和完整性。

关键流程：
1. **Canonicalization**: 使用 JSON Canonicalization Scheme (JCS, RFC 8785) 将 Agent Card 规范化
2. **Signing**: 用 ES256 (ECDSA + SHA-256) 签名规范化后的 JSON
3. **Verification**: 客户端验证签名，确认 Agent Card 未被篡改

签名后 Agent Card 格式：`{ "agentCard": {...}, "signature": { "header": {...}, "signature": "..." } }`

### 2. Zero Trust Agent Enclave (零信任代理飞地)

来自 Zentera Labs 的研究：Agent 的信任不应仅靠身份验证，还需要：
- **Enclave 隔离**: Agent 被限制在项目级网络边界内
- **Runtime Trust Score**: 运行时行为评分，动态调整权限
- **ABAC 策略**: 基于属性的访问控制（用户身份 + 设备状态 + Agent 信任分）

### 3. 行为信任评分 (Behavioral Trust Scoring)

来自 Pico/AgentLair 的实践：
- **Identity ≠ Trust**: 知道 Agent 是谁 ≠ 知道它是否可信
- 三个评分维度：Scope Compliance（权限合规）、Timing Consistency（时间一致性）、Transparency（透明度）
- Cold start = 30/100（不假设恶意，但也不信任）
- 反博弈机制：entropy penalty（维度过于均匀则惩罚）+ 每日观测上限

### 4. A2A + MCP 协议栈

2026 年的 Agent 协议栈已形成三层：
- **A2A**: Agent ↔ Agent 通信层（跨组织、跨框架）
- **MCP**: Agent ↔ Tool 数据层（97M downloads, 事实标准）
- **Context Layer**: 共享知识图谱/语义层（治理业务知识）

### 5. Sigstore A2A (透明度日志)

Sigstore 为 A2A Agent Card 提供：
- 代码来源绑定：签名关联 git revision + CI/CD workflow
- Rekor 透明度日志：公开审计，不可篡改
- Identity constraints：指定信任的仓库、workflow、actor

---

## 代码示例: Node.js ES256 Agent Card 签名 + 验证中间件

```js
// a2a-trust-middleware.js
// 可运行: node a2a-trust-middleware.js
// 依赖: npm install jose (无外部服务依赖)

const crypto = require('crypto');
const { jose } = require('jose');

// ============================================
// 1. ES256 密钥对生成
// ============================================
async function generateAgentKeyPair() {
  const { publicKey, privateKey } = await jose.generateKeyPair('ES256', {
    extractable: true,
  });
  return { publicKey, privateKey };
}

// ============================================
// 2. JCS Canonicalization (RFC 8785 简化实现)
// ============================================
function canonicalize(obj) {
  // RFC 8785 要求: 按 Unicode code point 排序 key，递归处理
  if (obj === null || typeof obj !== 'object') {
    return JSON.stringify(obj);
  }
  if (Array.isArray(obj)) {
    return '[' + obj.map(canonicalize).join(',') + ']';
  }
  const keys = Object.keys(obj).sort();
  return '{' + keys.map(k => JSON.stringify(k) + ':' + canonicalize(obj[k])).join(',') + '}';
}

// ============================================
// 3. Agent Card 签名
// ============================================
async function signAgentCard(agentCard, privateKey) {
  const canonical = canonicalize(agentCard);
  const canonicalBytes = new TextEncoder().encode(canonical);

  const jws = await new jose.CompactSign(canonicalBytes)
    .setProtectedHeader({ alg: 'ES256' })
    .sign(privateKey);

  return {
    agentCard,
    signature: {
      alg: 'ES256',
      jws,
      timestamp: new Date().toISOString(),
    },
  };
}

// ============================================
// 4. Agent Card 验证
// ============================================
async function verifyAgentCard(signedCard, publicKey) {
  try {
    const { payload } = await jose.compactVerify(
      signedCard.signature.jws,
      publicKey
    );
    const canonical = canonicalize(signedCard.agentCard);
    const payloadStr = new TextDecoder().decode(payload);
    return canonical === payloadStr;
  } catch {
    return false;
  }
}

// ============================================
// 5. Trust Score 计算 (行为评分简化版)
// ============================================
class AgentTrustScorer {
  constructor(agentId) {
    this.agentId = agentId;
    this.observations = [];
    this.score = 30; // cold start
  }

  observe(event) {
    // event: { scope, expectedScope, responseTime, errorReported, actualError }
    this.observations.push({ ...event, ts: Date.now() });
    if (this.observations.length >= 3) this._recalc();
  }

  _recalc() {
    const recent = this.observations.slice(-20);
    // Scope compliance: 请求是否在声明范围内
    const scopeOk = recent.filter(e => e.scope <= e.expectedScope).length / recent.length;
    // Timing consistency: 响应时间的标准差
    const times = recent.map(e => e.responseTime);
    const avg = times.reduce((a, b) => a + b, 0) / times.length;
    const stdDev = Math.sqrt(times.map(t => (t - avg) ** 2).reduce((a, b) => a + b, 0) / times.length);
    const timingScore = Math.max(0, 1 - stdDev / avg);
    // Transparency: 错误是否如实报告
    const transparency = recent.filter(e => e.errorReported === e.actualError).length / recent.length;

    // Entropy penalty: 三个维度过于均匀 → 惩罚
    const scores = [scopeOk, timingScore, transparency];
    const mean = scores.reduce((a, b) => a + b, 0) / 3;
    const entropy = Math.sqrt(scores.map(s => (s - mean) ** 2).reduce((a, b) => a + b, 0) / 3);
    const penalty = entropy < 0.02 ? 0.85 : 1.0;

    this.score = Math.round(((scopeOk + timingScore + transparency) / 3) * 100 * penalty);
    this.score = Math.max(10, Math.min(100, this.score));
  }

  getTrustTier() {
    if (this.score >= 85) return 'distinguished';
    if (this.score >= 70) return 'principal';
    if (this.score >= 50) return 'senior';
    if (this.score >= 35) return 'junior';
    return 'intern';
  }
}

// ============================================
// 6. Express 中间件 (可直接集成)
// ============================================
function a2aTrustMiddleware(trustScorer, trustedPublicKeys) {
  return async (req, res, next) => {
    const signedCard = req.body?.agentCard;
    if (!signedCard) return res.status(400).json({ error: 'Missing agent card' });

    // 验证签名
    const agentId = signedCard.agentCard?.name;
    const pubKey = trustedPublicKeys[agentId];
    if (!pubKey) return res.status(401).json({ error: 'Unknown agent' });

    const valid = await verifyAgentCard(signedCard, pubKey);
    if (!valid) return res.status(401).json({ error: 'Invalid signature' });

    // 检查信任分
    const tier = trustScorer.getTrustTier();
    if (tier === 'intern') {
      return res.status(403).json({ error: 'Insufficient trust', tier, score: trustScorer.score });
    }

    req.agentTrust = { agentId, tier, score: trustScorer.score };
    next();
  };
}

// ============================================
// Demo: 运行验证
// ============================================
async function demo() {
  console.log('=== A2A Trust Protocol Demo ===\n');

  // 生成密钥对
  const { publicKey, privateKey } = await generateAgentKeyPair();

  // 创建 Agent Card
  const agentCard = {
    name: 'catalyst-research-agent',
    description: 'Deep research agent for tech exploration',
    url: 'https://agents.example.com/catalyst',
    version: '1.0.0',
    skills: [{ id: 'research', name: 'Deep Research' }],
    authentication: { schemes: ['Bearer'] },
  };

  // 签名
  const signed = await signAgentCard(agentCard, privateKey);
  console.log('Signed Agent Card:');
  console.log(JSON.stringify(signed, null, 2).slice(0, 300) + '...\n');

  // 验证
  const valid = await verifyAgentCard(signed, publicKey);
  console.log(`✅ Signature valid: ${valid}\n`);

  // 篡改检测
  const tampered = JSON.parse(JSON.stringify(signed));
  tampered.agentCard.name = 'malicious-agent';
  const tamperValid = await verifyAgentCard(tampered, publicKey);
  console.log(`🚫 Tampered card valid: ${tamperValid}\n`);

  // Trust Score
  const scorer = new AgentTrustScorer('catalyst-research-agent');
  console.log(`Initial trust: ${scorer.score} (${scorer.getTrustTier()})`);

  // 模拟行为观测
  for (let i = 0; i < 5; i++) {
    scorer.observe({
      scope: 1, expectedScope: 2,
      responseTime: 150 + Math.random() * 50,
      errorReported: false, actualError: false,
    });
  }
  console.log(`After observations: ${scorer.score} (${scorer.getTrustTier()})`);

  console.log('\n=== Demo Complete ===');
}

// Run demo if executed directly
if (require.main === module) {
  demo().catch(console.error);
}

module.exports = { generateAgentKeyPair, canonicalize, signAgentCard, verifyAgentCard, AgentTrustScorer, a2aTrustMiddleware };
```

---

## 关键洞察

### 洞察 1: A2A 的信任模型是"签名 + 行为"双因子

单纯的身份签名（ES256/JWS）解决的是"你是谁"的问题，但不解决"你是否可信"的问题。CSA 的 MAESTRO 威胁建模明确指出 Agent 冒充（T3.1）是核心威胁，因为 Agent 身份是动态变化的。最佳实践是：
- **静态层**: JWS 签名验证 Agent Card 完整性
- **动态层**: 行为信任评分持续评估 Agent 可信度

### 洞察 2: A2A v1.2 的 JCS 规范化解决了跨语言互操作问题

JCS (RFC 8785) 确保不同 JSON 实现（Python json.dumps、JSON.stringify、Go encoding/json）生成的签名一致。这是实际部署中最容易被忽略但最容易出 bug 的地方。对于 `lab/a2a-trust-prototype`，必须确保 Node.js 和 Python 的 JCS 实现输出一致。

### 洞察 3: Sigstore 透明度日志为 A2A 提供了供应链级信任

Sigstore A2A 不仅验证签名，还绑定 CI/CD 来源（git revision + workflow）。这意味着可以建立信任链：Agent Card 签名 → 代码来源验证 → 透明度日志审计。对于企业级部署，这比单纯 ES256 签名可靠得多。

### 洞察 4: Cold Start 问题需要特别处理

所有信任系统都面临冷启动：新 Agent 没有历史数据。Pico 的方案是 cold start = 30（而不是 0），这是一种工程实用主义——不假设恶意，但限制权限。对于 `agent-context-store` 的集成，可以考虑将 trust score 作为 context 的一部分持久化。

### 洞察 5: A2A + MCP 的互补架构是 2026 的事实标准

Google 和 Anthropic 从设计之初就确保 A2A 和 MCP 互补而非竞争。A2A 处理 agent 间通信，MCP 处理 agent-tool 通信。对于 `openclaw-langgraph-bridge`，这意味着 Supervisor 应该同时支持 A2A（agent 间委派）和 MCP（工具调用）两种协议。

---

## 与现有项目的关联

| 项目 | 关联点 |
|------|--------|
| `lab/a2a-trust-prototype` | 直接输出：ES256 签名中间件 + Trust Score |
| `agent-context-store` | Trust Score 可作为 context 持久化，snapshot 包含信任状态 |
| `openclaw-langgraph-bridge` | Supervisor 应支持 A2A 协议做 agent 间委派 |
| `lab/agent-observability` | 行为观测数据可与 Trust Scorer 共享 |

---

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`**: 基于上述代码，实现完整的 ES256 签名中间件 + Trust Score 模块
2. **JCS 跨语言验证**: 编写 Python 版本的 `canonicalize()`，确认与 Node.js 版输出一致
3. **集成 agent-context-store**: 将 trust score 变更记录为 context event，支持 snapshot/restore
4. **研究 Sigstore A2A**: 评估是否需要在 prototype 中集成透明度日志

---

## 参考资料

- [A2A Protocol Specification - Agent Card Signing (§8.4)](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)
- [CSA: Threat Modeling Google's A2A Protocol with MAESTRO](https://cloudsecurityalliance.org/blog/2025/04/30/threat-modeling-google-s-a2a-protocol-with-the-maestro-framework)
- [Sigstore A2A Agent Signing](https://github.com/sigstore/sigstore-a2a)
- [A2A Protocol 1.0 Milestone](https://discuss.google.dev/t/the-a2a-0-milestone-ensuring-and-testing-backward-compatibility/352258)
- [How We Score AI Agent Trust (Pico)](https://dev.to/piiiico/how-we-score-ai-agent-trust-and-why-behavioral-consistency-beats-identity-3591)
- [Zero Trust Architecture for Agentic AI](https://www.zentera.net/blog/zero-trust-architecture-for-agentic-ai)
- [A2A Surpasses 150 Organizations (PR Newswire)](https://www.prnewswire.com/news-releases/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year-302737641.html)
