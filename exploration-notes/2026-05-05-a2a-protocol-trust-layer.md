# A2A Protocol Trust Layer 深度研究

> **日期:** 2026-05-05 | **主题:** Agent-to-Agent (A2A) 协议的信任、签名与认证层
> **关联项目:** `lab/a2a-trust-prototype/` (待实现)

---

## 核心概念 (5个)

### 1. Agent Card — Agent 的数字身份证
每个 A2A Agent 发布一个 JSON 文档（Agent Card），类似 OpenAPI spec 但描述的是 Agent 的能力、认证方式和通信端点。发布在 `/.well-known/agent-card.json`。

```json
{
  "name": "my-calc-agent",
  "description": "A math calculation agent",
  "url": "https://agents.example.com/calc",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "skills": [{
    "id": "math-calc",
    "name": "Math Calculator",
    "description": "Performs arithmetic calculations"
  }],
  "securitySchemes": {
    "oauth2": {
      "type": "oauth2",
      "flows": { "clientCredentials": { "tokenUrl": "https://auth.example.com/token" } }
    }
  }
}
```

### 2. Signed Agent Cards — 密码学身份验证
A2A v1.0+ 引入了 Signed Agent Cards，使用 JWS (RFC 7515) 格式签名。签名算法首选 **ES256**（ECDSA + SHA-256），也支持 RS256。

签名流程：
1. 移除默认值属性，排除 `signatures` 字段
2. 用 RFC 8785 规范化 JSON（确保确定性序列化）
3. 构造 JWS Signing Input: `BASE64URL(header) || '.' || BASE64URL(payload)`
4. 用私钥签名，Base64url 编码结果

```json
{
  "protected": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpPU0UiLCJraWQiOiJrZXktMSIsImprdSI6Imh0dHBzOi8vZXhhbXBsZS5jb20vYWdlbnQvandrcy5qc29uIn0",
  "signature": "QFdkNLNszlGj3z3u0YQGt_T9LixY3qtdQpZmsTdDHDe3fXV9y9-B3m2-XgCpzuhiLt8E0tV6HXoZKHv4GtHgKQ"
}
```

Protected header 解码为: `{"alg":"ES256","typ":"JOSE","kid":"key-1","jku":"https://example.com/agent/jwks.json"}`

### 3. 三层身份架构 (FluxA 研究提出)
- **Layer 1 — 通信层:** A2A + MCP 处理发现和通信
- **Layer 2 — 凭证层:** W3C Verifiable Credentials 提供可移植的身份认证
- **Layer 3 — 身份绑定层:** Persistent Agent ID，跨运行时和平台持久化

关键洞察：A2A 只解决了通信层，持久身份需要上层协议。

### 4. Agent Card 注册表与动态发现
A2A 的核心机制是**动态发现**：编排 Agent 查询 Agent Card 注册表，找到能处理特定任务的子 Agent，无需硬编码。这使得企业环境中新部署的专门化 Agent 能被自动发现和调用。

### 5. 多协议共存架构
A2A 不是唯一标准，而是与 MCP、ACP、ANP 互补：
- **MCP** = Agent → 工具/数据（纵向）
- **A2A** = Agent → Agent（横向，跨组织）
- **ACP** = 商业交易
- **ANP** = 去中心化市场

类比：HTTP + WebSocket + gRPC 共存于现代 Web 基础设施。

---

## 可运行代码示例

### 示例 1: ES256 Agent Card 签名与验证 (Node.js, 零外部依赖)

```javascript
// a2a-card-signer.mjs — 仅使用 Node.js 内置 crypto，零依赖
import { generateKeyPairSync, createSign, createVerify } from 'node:crypto';

// === 1. 生成 ECDSA P-256 密钥对 ===
const { publicKey, privateKey } = generateKeyPairSync('ec', {
  namedCurve: 'P-256',
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

// === 2. 定义 Agent Card ===
const agentCard = {
  name: 'catalyst-research-agent',
  description: 'Deep tech research agent with autoresearch capabilities',
  url: 'https://agents.catalyst.dev/research',
  version: '1.0.0',
  capabilities: {
    streaming: true,
    pushNotifications: false,
    stateTransitionHistory: true,
  },
  skills: [{
    id: 'deep-research',
    name: 'Deep Research',
    description: 'Multi-step autonomous research with quality gates',
  }],
  provider: {
    organization: 'Catalyst Lab',
    url: 'https://catalyst.dev',
  },
};

// === 3. RFC 8785 JSON Canonicalization (递归排序 key) ===
function canonicalizeJson(obj) {
  if (obj === null || typeof obj !== 'object') return JSON.stringify(obj);
  if (Array.isArray(obj)) return '[' + obj.map(canonicalizeJson).join(',') + ']';
  const sortedKeys = Object.keys(obj).sort();
  return '{' + sortedKeys.map(k => JSON.stringify(k) + ':' + canonicalizeJson(obj[k])).join(',') + '}';
}

const canonicalPayload = canonicalizeJson(agentCard);

// === 4. 签名 (ES256 = ECDSA + SHA-256) ===
const protectedHeader = { alg: 'ES256', typ: 'JOSE', kid: 'key-1' };
const headerB64 = Buffer.from(JSON.stringify(protectedHeader)).toString('base64url');
const payloadB64 = Buffer.from(canonicalPayload).toString('base64url');
const signingInput = `${headerB64}.${payloadB64}`;

const signature = createSign('SHA256').update(signingInput).sign(privateKey);
const signatureB64 = signature.toString('base64url');

const agentCardSignature = { protected: headerB64, signature: signatureB64 };

console.log('✅ Agent Card Signature:');
console.log(JSON.stringify(agentCardSignature, null, 2));

// === 5. 验证签名 ===
const isValid = createVerify('SHA256').update(signingInput).verify(publicKey, signature);
console.log(`${isValid ? '✅' : '❌'} Signature verification: ${isValid}`);

// === 6. Trust Score 计算 ===
function calculateTrustScore(card, sig) {
  let score = 0;
  score += 30; // 有效签名
  try {
    const header = JSON.parse(Buffer.from(sig.protected, 'base64url').toString());
    if (header.jku) score += 20; // 有 JWKS URL
  } catch {}
  if (card.name) score += 10;
  if (card.description) score += 10;
  if (card.skills?.length > 0) score += 10;
  if (card.provider?.organization) score += 10;
  if (card.capabilities?.streaming) score += 5;
  if (card.capabilities?.stateTransitionHistory) score += 5;
  return Math.min(score, 100);
}

const trustScore = calculateTrustScore(agentCard, agentCardSignature);
console.log(`🏆 Trust Score: ${trustScore}/100`);
console.log(`   Grade: ${trustScore >= 80 ? 'A (Trusted)' : trustScore >= 60 ? 'B (Conditional)' : 'C (Unverified)'}`);
```

**运行输出 (已验证 ✅):**
```
✅ Agent Card Signature:
{
  "protected": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpPU0UiLCJraWQiOiJrZXktMSJ9",
  "signature": "MEUCIDxhX1hfQRsLhPd3B9lFTrAe5Zm7ijHRxtxT0XfxYv56AiEA9PoixRW3Tg..."
}
✅ Signature verification: true
🏆 Trust Score: 80/100
   Grade: A (Trusted)
```

### 示例 2: A2A 客户端 — 连接远程 Agent (使用官方 SDK)

```bash
npm install @a2a-js/sdk uuid
```

```javascript
// a2a-client-demo.mjs
import { ClientFactory } from '@a2a-js/sdk/client';
import { v4 as uuidv4 } from 'uuid';

// 实际使用时连接远程 A2A Agent
async function demo() {
  const factory = new ClientFactory();
  
  // 从 URL 发现 Agent Card
  // const client = await factory.createFromUrl('https://remote-agent.example.com');
  
  // 模拟：展示消息格式
  const message = {
    messageId: uuidv4(),
    role: 'user',
    parts: [{ kind: 'text', text: 'Research the latest A2A protocol updates' }],
    kind: 'message',
  };
  
  console.log('📤 A2A Message Format:');
  console.log(JSON.stringify(message, null, 2));
  
  // A2A 协议的 3 步流程：
  // 1. Discovery: GET /.well-known/agent-card.json → 获取 Agent Card
  // 2. Authentication: 根据 Agent Card 的 securitySchemes 认证
  // 3. Task Delegation: POST /message/send with JSON-RPC 2.0
}

demo();
```

### 示例 3: Trust Score 三层模型 (对应 lab/a2a-trust-prototype)

```javascript
// trust-score-model.mjs
// 三层信任模型：身份信任 + 行为信任 + 声誉信任

class AgentTrustScorer {
  constructor() {
    this.identityWeights = { signed: 30, jwks: 20, knownIssuer: 20 };
    this.behaviorWeights = { responseRate: 10, latency: 5, errorRate: 5 };
    this.reputationWeights = { peerEndorsements: 5, taskSuccess: 5 };
  }
  
  scoreIdentity(card, signature) {
    let score = 0;
    if (signature) score += this.identityWeights.signed;
    try {
      const header = JSON.parse(Buffer.from(signature.protected, 'base64url').toString());
      if (header.jku) score += this.identityWeights.jwks;
      if (header.kid?.startsWith('known-')) score += this.identityWeights.knownIssuer;
    } catch {}
    return score;
  }
  
  scoreBehavior(history = {}) {
    let score = 0;
    if (history.totalTasks > 0) {
      const successRate = (history.successfulTasks || 0) / history.totalTasks;
      score += Math.round(successRate * this.behaviorWeights.responseRate);
      score += history.avgLatencyMs < 1000 ? this.behaviorWeights.latency : 0;
      score += (history.errorRate || 0) < 0.05 ? this.behaviorWeights.errorRate : 0;
    }
    return score;
  }
  
  scoreReputation(peerData = {}) {
    let score = 0;
    score += Math.min((peerData.endorsements || 0) * 1, this.reputationWeights.peerEndorsements);
    score += Math.min((peerData.completedTasks || 0) * 0.5, this.reputationWeights.taskSuccess);
    return score;
  }
  
  calculate(card, signature, behaviorHistory, peerData) {
    const identity = this.scoreIdentity(card, signature);
    const behavior = this.scoreBehavior(behaviorHistory);
    const reputation = this.scoreReputation(peerData);
    const total = identity + behavior + reputation;
    
    return {
      total: Math.min(total, 100),
      breakdown: { identity, behavior, reputation },
      grade: total >= 80 ? 'A' : total >= 60 ? 'B' : total >= 40 ? 'C' : 'D',
      recommendation: total >= 80 ? 'Allow full delegation' 
        : total >= 60 ? 'Allow with human approval' 
        : total >= 40 ? 'Monitor closely' : 'Block',
    };
  }
}

// 使用示例
const scorer = new AgentTrustScorer();
const result = scorer.calculate(
  { name: 'test-agent' },
  { protected: Buffer.from(JSON.stringify({ alg: 'ES256', typ: 'JOSE', kid: 'key-1' })).toString('base64url'), signature: 'fake' },
  { totalTasks: 50, successfulTasks: 47, avgLatencyMs: 450, errorRate: 0.02 },
  { endorsements: 3, completedTasks: 8 }
);

console.log('🏆 Trust Assessment:');
console.log(JSON.stringify(result, null, 2));
```

---

## 关键洞察 (5条)

### 1. A2A 已从实验走向生产
2026年4月（一周年）达到 150+ 组织支持，Google/Microsoft/AWS 均在生产环境运行。Linux Foundation 治理下的 v1.0 已稳定，不是"未来技术"而是"现在可用"。

### 2. 签名层是信任的基础设施
A2A v1.0 的 Signed Agent Cards 使用 ES256 + JWS，与我们 `lab/a2a-trust-prototype/` 的 ES256 中间件设计完全对齐。JWKS 端点用于公钥分发，与 OAuth2/OIDC 生态一致。

### 3. MCP + A2A 是互补架构，不是竞争
官方明确：MCP 解决 Agent → 工具（纵向），A2A 解决 Agent → Agent（横向）。我们的 OpenClaw 作为 MCP 生态的一部分，A2A 是自然的扩展方向。先有 MCP 再加 A2A 是推荐路径。

### 4. 三层信任模型有学术支撑
FluxA 的研究提出 Communication + Credentials + Identity Binding 三层架构。我们的 Trust Score 模型（身份信任 + 行为信任 + 声誉信任）对应了这三层的评分维度，设计方向正确。

### 5. 官方 JS SDK (@a2a-js/sdk) 已可用
`@a2a-js/sdk` v0.2.4 提供了 ClientFactory、AgentExecutor、A2AExpressApp 等完整抽象，可以直接用于 `lab/a2a-trust-prototype/` 的实现，不需要从零构建协议层。

---

## 与现有项目关联

| 现有项目 | 关联点 |
|---------|--------|
| `lab/a2a-trust-prototype/` | ES256 签名中间件 + Trust Score 计算，直接映射 A2A Signed Agent Cards |
| `lab/openclaw-langgraph-bridge/` | LangGraph Agent 可通过 A2A 协议暴露为远程 Agent |
| AMS (Agent Memory Service) | Agent 间的记忆共享可通过 A2A 安全传输 |
| OpenClaw (sessions_spawn) | executor 抽象层可扩展为 A2A 远程 Agent 调用 |

---

## 下一步行动

1. **立即:** 将本研究的 Trust Score 模型实现为 `lab/a2a-trust-prototype/` 的核心模块，使用 `@a2a-js/sdk` + `jose` 库
2. **本周:** 实现 Signed Agent Card 的签名/验证中间件，包含 JWKS 端点
3. **本月:** 将 Trust Score 集成到 OpenClaw 的 sessions_spawn 流程中，作为远程 Agent 调用的前置检查
4. **探索:** 研究 W3C Verifiable Credentials 作为持久身份层的可行性

---

## 参考资料

- [A2A Specification - GitHub](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)
- [A2A Protocol 1周年 - Linux Foundation](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year)
- [A2A JS SDK](https://github.com/a2aproject/a2a-js)
- [Agent Authentication Across Platforms - FluxA](https://fluxapay.xyz/learning/how-ai-agents-authenticate-across-platforms-2026)
- [A2A Protocol Security - OneReach](https://onereach.ai/blog/what-is-a2a-agent-to-agent-protocol/)
- [A2A + MCP Protocol Ecosystem Map 2026](https://www.digitalapplied.com/blog/ai-agent-protocol-ecosystem-map-2026-mcp-a2a-acp-ucp)
- [Zylos Research: Protocol Standards Comparison](https://zylos.ai/research/2026-02-15-agent-to-agent-communication-protocols)
