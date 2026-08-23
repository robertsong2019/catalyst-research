# A2A Protocol + Agent Trust: 2026 最新进展

> 研究日期: 2026-05-23
> 研究方法: autoresearch (autoresearch.md)
> 关联项目: lab/a2a-trust-prototype（待创建）

---

## 核心概念

### 1. A2A Protocol（Agent-to-Agent）
- Google 2025年4月发布，Linux Foundation 托管，IBM ACP 合并入 A2A
- 21,900 GitHub stars（2026年2月），150+ 合作伙伴
- **定位**: Agent 间协调层，与 MCP 互补而非竞争
  - MCP = Agent → Tool
  - A2A = Agent → Agent
- 核心原语: AgentCard（发现）、JSON-RPC 2.0（通信）、Task（工作单元）
- 关键端点: `/.well-known/agent.json`（AgentCard 发现）

### 2. Agent Trust 四层模型（2026 产业共识）
| 层 | 机制 | 代表实现 |
|---|---|---|
| Tokenized Identity | 平台颁发 token | Mastercard Agent Pay |
| Attestation Headers | 签名请求头 | Visa Trusted Agent Protocol |
| Verifiable Credentials | W3C VC 标准签名凭证 | Google AP2 |
| Decentralized Identity | W3C DID 自主身份 | ERC-8004, DIF |

### 3. Trust Score（IETF Draft: draft-sharif-agent-payment-trust-00）
- 2026年3月提交的 IETF Internet-Draft
- 为自主 AI Agent 支付交易定义信任评分和身份验证框架
- 映射到 PSD2 SCA 和 PCI DSS v4.0.1 合规要求
- 核心思路: agent + user + intent → 单一签名凭证 → 可验证信任链

### 4. ERC-8004（On-Chain Agent Identity）
- 基于 ERC-721 NFT 的 Agent ID 注册
- 包含: 基本信息、服务端点（A2A/MCP/OASF）、钱包地址、信任模型
- 跨链部署: Ethereum、Base、Polygon、Arbitrum
- Reputation Registry: 链上信誉记录

### 5. DID + VC for Agents（W3C 标准 + 学术实现）
- arxiv 2511.02841: AI Agent + DID + VC 原型实现
- 每个 Agent 持有: 自主 DID + 第三方颁发的 VC
- DID 用于认证，VC 用于建立跨域信任关系
- 关键挑战: LLM 单独控制安全程序时的局限性

---

## 可运行代码: A2A Agent + DID Trust Score 原型

以下代码实现了一个最小化的 A2A Agent Trust 原型：
- 使用 Node.js 原生 `crypto` 模块（ES256 签名）
- AgentCard 定义 + Trust Score 计算
- Verifiable Credential 签发与验证

```javascript
// a2a-trust-prototype.js
// Run: node a2a-trust-prototype.js
// Zero dependencies — uses Node.js built-in crypto only

const crypto = require('crypto');

// ============================================================
// 1. DID Generation & Key Management
// ============================================================

function generateDID() {
  const { publicKey, privateKey } = crypto.generateKeyPairSync('ec', {
    namedCurve: 'P-256',
  });
  const pubDer = publicKey.export({ type: 'spki', format: 'der' });
  const fingerprint = crypto.createHash('sha256').update(pubDer).digest('hex').slice(0, 32);
  const did = `did:agent:${fingerprint}`;
  return { did, publicKey, privateKey };
}

// ============================================================
// 2. Agent Card (A2A-compliant structure)
// ============================================================

function createAgentCard({ did, name, description, skills, url }) {
  return {
    name,
    description,
    url: url || `https://${did.slice(8)}.agent.local`,
    provider: { organization: 'Catalyst Lab' },
    version: '0.1.0',
    capabilities: {
      streaming: false,
      pushNotifications: false,
      stateTransitionHistory: false,
    },
    skills,
    // Extended: DID-based identity
    identity: { did, method: 'ES256' },
    // Well-known endpoint
    _wellKnown: '/.well-known/agent.json',
  };
}

// ============================================================
// 3. Verifiable Credential Issuance
// ============================================================

function issueCredential(issuer, subjectDid, claims) {
  const header = { alg: 'ES256', typ: 'vc+jwt' };
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: issuer.did,
    sub: subjectDid,
    iat: now,
    exp: now + 86400 * 30, // 30 days
    vc: {
      '@context': ['https://www.w3.org/2018/credentials/v1'],
      type: ['VerifiableCredential', 'AgentTrustCredential'],
      credentialSubject: claims,
    },
  };

  const sign = (data) => {
    const sign = crypto.createSign('SHA256');
    sign.update(data);
    sign.end();
    return sign.sign(issuer.privateKey);
  };

  const headerB64 = Buffer.from(JSON.stringify(header)).toString('base64url');
  const payloadB64 = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const signingInput = `${headerB64}.${payloadB64}`;
  const signature = sign(signingInput);
  const sigB64 = signature.toString('base64url');

  return {
    jwt: `${signingInput}.${sigB64}`,
    payload,
    issuerDid: issuer.did,
  };
}

// ============================================================
// 4. Trust Score Calculator
// ============================================================

function calculateTrustScore(agent) {
  let score = 0;
  const maxScore = 100;
  const breakdown = {};

  // Factor 1: Identity verification (0-25)
  const hasDID = !!agent.card.identity?.did;
  breakdown.identity = hasDID ? 25 : 0;
  score += breakdown.identity;

  // Factor 2: Credential count (0-25)
  const credCount = agent.credentials?.length || 0;
  breakdown.credentials = Math.min(25, credCount * 5);
  score += breakdown.credentials;

  // Factor 3: Skill diversity (0-25)
  const skillCount = agent.card.skills?.length || 0;
  breakdown.skills = Math.min(25, skillCount * 8);
  score += breakdown.skills;

  // Factor 4: Interaction history (0-25)
  const interactions = agent.interactionCount || 0;
  breakdown.history = Math.min(25, Math.floor(interactions / 10) * 5);
  score += breakdown.history;

  return {
    score: Math.min(score, maxScore),
    level: score >= 75 ? 'HIGH' : score >= 50 ? 'MEDIUM' : score >= 25 ? 'LOW' : 'UNVERIFIED',
    breakdown,
  };
}

// ============================================================
// 5. Verify Credential Signature
// ============================================================

function verifyCredential(vc, issuerPublicKey) {
  try {
    const parts = vc.jwt.split('.');
    const [headerB64, payloadB64, sigB64] = parts;
    const signingInput = `${headerB64}.${payloadB64}`;
    const signature = Buffer.from(sigB64, 'base64url');

    const verify = crypto.createVerify('SHA256');
    verify.update(signingInput);
    verify.end();

    const valid = verify.verify(issuerPublicKey, signature);
    const payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString());

    const expired = payload.exp < Math.floor(Date.now() / 1000);
    return { valid, expired, payload };
  } catch (e) {
    return { valid: false, error: e.message };
  }
}

// ============================================================
// Demo: Full Trust Flow
// ============================================================

console.log('=== A2A Agent Trust Prototype ===\n');

// Create trust authority
const authority = generateDID();
console.log(`📋 Trust Authority: ${authority.did}\n`);

// Create two agents
const agentA = generateDID();
const agentB = generateDID();

const cardA = createAgentCard({
  did: agentA.did,
  name: 'Research Agent',
  description: 'Deep research and analysis',
  skills: [
    { id: 'search', name: 'Web Search', description: 'Search the web' },
    { id: 'summarize', name: 'Summarize', description: 'Summarize documents' },
  ],
});

const cardB = createAgentCard({
  did: agentB.did,
  name: 'Code Agent',
  description: 'Code generation and review',
  skills: [
    { id: 'codegen', name: 'Code Generation', description: 'Generate code from specs' },
    { id: 'review', name: 'Code Review', description: 'Review pull requests' },
    { id: 'test', name: 'Test Generation', description: 'Generate tests' },
  ],
});

console.log(`Agent A: ${cardA.name} (${agentA.did.slice(0, 20)}...)`);
console.log(`Agent B: ${cardB.name} (${agentB.did.slice(0, 20)}...)`);

// Authority issues credentials
const credA = issueCredential(authority, agentA.did, {
  trustLevel: 'verified',
  capabilities: ['research', 'analysis'],
  maxTransactionValue: 1000,
});

const credB = issueCredential(authority, agentB.did, {
  trustLevel: 'trusted',
  capabilities: ['code', 'review', 'deploy'],
  maxTransactionValue: 5000,
});

console.log(`\n✅ Credentials issued by authority\n`);

// Verify credentials
const verifyA = verifyCredential(credA, authority.publicKey);
const verifyB = verifyCredential(credB, authority.publicKey);
console.log(`Agent A credential valid: ${verifyA.valid}`);
console.log(`Agent B credential valid: ${verifyB.valid}`);

// Calculate trust scores
const trustA = calculateTrustScore({
  card: cardA,
  credentials: [credA],
  interactionCount: 50,
});

const trustB = calculateTrustScore({
  card: cardB,
  credentials: [credB],
  interactionCount: 120,
});

console.log(`\n📊 Trust Scores:`);
console.log(`Agent A: ${trustA.score}/100 (${trustA.level}) — ${JSON.stringify(trustA.breakdown)}`);
console.log(`Agent B: ${trustB.score}/100 (${trustB.level}) — ${JSON.stringify(trustB.breakdown)}`);

// A2A discovery simulation
console.log(`\n🔍 A2A Discovery Simulation:`);
console.log(`GET /.well-known/agent.json → Agent A Card:`);
console.log(JSON.stringify({ name: cardA.name, skills: cardA.skills.map(s => s.id), identity: cardA.identity }, null, 2));

console.log(`\n✨ Prototype complete. All crypto operations use Node.js built-in modules.`);
```

---

## 关键洞察

### 1. A2A + MCP 是互补协议栈，不是竞争关系
2026年的产业共识已经清晰：MCP 负责工具调用，A2A 负责 Agent 间协调。生产级 Agent 系统会同时使用两者。IBM ACP 合并入 A2A（2025年8月）进一步证实了标准化趋势。对 `a2a-trust-prototype` 的启示：**不需要重新发明通信协议，专注在信任层即可。**

### 2. Agent Trust 正在从理论走向标准化
四个并行发展值得关注：
- **IETF draft-sharif-agent-payment-trust**: 支付场景的信任评分（有 PSD2/PCI DSS 映射）
- **W3C DID + VC for Agents**: 学术原型已验证可行性（arxiv 2511.02841）
- **ERC-8004**: 链上 Agent 身份注册 + 信誉系统
- **Google AP2**: Verifiable Credentials 签名授权

关键发现：这些方案共享同一个信任链模型：`人类 → 签名凭证 → Agent → 验证`。**a2a-trust-prototype 应该实现这个最小信任链，而不是试图覆盖所有方案。**

### 3. A2A JS SDK 已成熟，可直接使用
`a2a-sdk` npm 包提供了完整的 Node.js 实现：
- `AgentCard` 类型定义
- `AgentExecutor` 接口
- `A2AExpressApp` + `DefaultRequestHandler` + `InMemoryTaskStore`
- 支持 `/.well-known/agent.json` 自动注册

这意味着 `a2a-trust-prototype` 可以直接在 A2A AgentCard 的 `identity` 扩展字段中加入 DID 和信任信息，而不需要从零构建通信层。

### 4. DID 的核心价值不在"去中心化"，而在"密码学可验证"
从 arxiv 论文的评估来看，DID + VC 对 Agent 的真正价值是：
- Agent 可以**自主证明身份**（不依赖中心服务器在线）
- 第三方颁发的 VC 可以**跨域信任**（一个 VC 多处可用）
- **审计追踪**天然存在（签名 = 不可否认性）

但论文也指出了限制：**当 LLM 单独控制安全程序时，效果下降**。这意味着信任层必须是代码级实现，不能交给 LLM 判断。

### 5. a2a-trust-prototype 的最佳切入点
综合所有资料，最佳实现路径是：
1. **A2A AgentCard 扩展** — 在标准 AgentCard 上加 `identity` 和 `trust` 字段
2. **ES256 签名** — Node.js `crypto` 原生支持，零依赖
3. **Trust Score 算法** — 多因子加权（身份 + 凭证 + 技能 + 历史）
4. **VC 签发/验证** — JWT 格式，与 W3C VC 兼容

这正好对应 HEARTBEAT.md 中 a2a-trust-prototype 的目标："Node.js 原生 crypto ES256 签名中间件 + Trust Score"。

---

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`** — 基于上述代码原型扩展为完整项目
   - `src/did.js` — DID 生成/解析
   - `src/trust-score.js` — Trust Score 计算（可配置权重）
   - `src/credential.js` — VC 签发/验证
   - `src/agent-card.js` — A2A AgentCard + 信任扩展
   - `src/middleware.js` — Express 中间件（请求验证）
   - 目标: 18+ tests（与已完成的 langgraph-bridge 同等规模）

2. **研究 `a2a-sdk` npm 包集成** — 评估是否直接用其 AgentCard/Executor 类型

3. **追踪 IETF draft-sharif-agent-payment-trust** — Trust Score 算法的标准化参考

---

## 参考资料

- [A2A Protocol GitHub](https://github.com/a2aproject/A2A) — 21,900+ stars, Apache License
- [A2A JS SDK Tutorial](https://dev.to/czmilo/a2a-js-sdk-complete-tutorial-quick-start-guide-41d2) — Node.js 实现指南
- [Google A2A Announcement](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability) — 2025年4月
- [IETF draft-sharif-agent-payment-trust-00](https://datatracker.ietf.org/doc/draft-sharif-agent-payment-trust) — Trust Score 标准草案
- [AI Agents with DIDs and VCs (arxiv)](https://arxiv.org/html/2511.02841v1) — 学术原型
- [ERC-8004 On-Chain Agent Identity](https://www.cobo.com/post/erc-8004-on-chain-identity-standard-for-ai-agents-the-future-of-agentic-wallets) — 链上身份标准
- [Agent Identity Verification 2026 (Eco)](https://eco.com/support/en/articles/15192005-agent-identity-verification-how-ai-agents-authenticate-purchases-in-2026) — 4层信任模型
- [MCP vs A2A in 2026](https://philippdubach.com/posts/mcp-vs-a2a-in-2026-how-the-ai-protocol-war-ends) — 协议生态分析
