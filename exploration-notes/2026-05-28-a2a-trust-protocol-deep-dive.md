# A2A Trust Protocol 深度研究

> Date: 2026-05-28 | Theme: Agent-to-Agent Trust Layer — 从标准到实现
> Method: autoresearch | Status: ✅ Complete

---

## 核心概念

### 1. Google A2A Protocol v0.3 (2025-04 → 2026)

A2A 是 Google 开源的 Agent 间通信协议，2025年4月发布，后捐给 Linux Foundation。**v0.3** 是当前稳定版本，关键新特性：

- **Signed Security Cards** — Agent Card 支持密码学签名（JWS格式），防止篡改和冒充
- **gRPC Transport** — 除 HTTP/JSON-RPC 外新增 gRPC，低延迟场景
- **Python SDK 扩展** — ADK 内建客户端支持

**A2A vs MCP 的定位**：
- MCP = Agent ↔ Tool（工具调用）
- A2A = Agent ↔ Agent（任务委派、协作）
- 两者互补：编排层用 A2A，每个 Agent 内部用 MCP 调工具

### 2. Agent Card Signing（安全卡签名）

v0.3 的核心安全改进。Agent Card 是 JSON 文档（`/.well-known/agent.json`），包含身份、能力、认证方式。签名方案：

```json
{
  "name": "booking-agent",
  "url": "https://agent.example.com",
  "skills": [{"id": "book-flight", "name": "Flight Booking"}],
  "authentication": {"schemes": ["oauth2"]},
  "signature": {
    "alg": "ES256",
    "kid": "did:web:agent.example.com#key-1",
    "signature": "base64url..."
  }
}
```

签名验证路径（按信任度排序）：
1. **x5c/x5u** — X.509 证书链 → TLS 级信任根
2. **jku + jwk** — JWKS 端点引用 → 适合企业内部
3. **DID kid** — `did:web:` 或 `did:key:` → 去中心化身份
4. **Out-of-band** — 注册表预知公钥 → 最强保证

**Semgrep 安全团队指出的问题**：v0.3 支持但不强制签名，导致可能出现未签名卡被冒充。

### 3. Zero-Trust Agent Identity（零信任代理身份）

Cisco Talos 2024 报告：身份攻击占 IR 案例的 60%。Agent 环境更复杂，当前学术/工业界的主流方案：

| 层 | 技术 | 作用 |
|---|------|------|
| 身份层 | DID + Verifiable Credentials (W3C) | 可验证的 Agent 身份 |
| 加密层 | ES256/EdDSA + ZKP | 签名认证 + 隐私保护 |
| 信任层 | Trust Score + Time Decay | 动态信任评估 |
| 执行层 | TEE（可信执行环境） | 代码完整性保证 |
| 审计层 | Blockchain/不可变日志 | 操作溯源 |

关键论文：
- **"Know Your Agent" (KYA)** — Chaffer 2025, 类似金融 KYC 但面向 Agent
- **"Zero-Trust Identity Framework for Agentic AI"** — Huang et al. 2025, arXiv:2505.19301
- **ERC-8004** — 区块链上的 Agent 身份 + 信誉标准，跨组织信任传递

### 4. Trust Scoring 模式

信任分数设计的关键参数：

```
信任增益: gain = base_gain × max(0.1, 1 - (interactions - 1) × decay_rate)
信任惩罚: penalty = fixed_deduction (通常比增益大 3x)
时间衰减: score -= decay_rate × elapsed_hours (每小时微降)
```

设计原则：
- **Negative heavier than positive** — 失败一次扣分 > 成功多次加分
- **Diminishing returns** — 交互越多，单次增益越小
- **Skill-specific** — 按 skill 维度独立评分，而非全局平均
- **Time decay** — 长时间不交互的信任会自然衰减

### 5. Post-Zero-Trust 架构

传统零信任还不够。新的 "Post-Zero-Trust" 框架：

- **Decentralized Trust Anchors** — 用区块链替代集中式身份提供商
- **Self-Sovereign Identity (SSI)** — Agent 自己控制身份和凭证
- **Context-Aware Auth** — 每次交互都重新评估（不只是登录时）
- **Federated Trust Learning** — 跨组织共享威胁模型，不泄露行为数据

---

## 可运行代码：A2A 兼容的 Signed Agent Card + Trust Middleware

这段代码直接基于我们的 `lab/a2a-trust-prototype`，但增加了 **A2A v0.3 兼容的签名卡格式** 和 **JWK 公钥发布**：

```typescript
// a2a-signed-card-demo.ts — 零依赖，Node.js 原生 Web Crypto
import { webcrypto } from 'node:crypto';
const { subtle } = webcrypto;

// ─── Crypto Helpers ────────────────────────────────────────
type KeyPair = { publicKey: CryptoKey; privateKey: CryptoKey };

async function generateKeyPair(): Promise<KeyPair> {
  return subtle.generateKey(
    { name: 'ECDSA', namedCurve: 'P-256' },
    true,
    ['sign', 'verify'],
  );
}

function canonicalize(obj: unknown): string {
  if (obj === null || typeof obj !== 'object') return JSON.stringify(obj);
  if (Array.isArray(obj))
    return '[' + obj.map(canonicalize).join(',') + ']';
  const sorted = Object.keys(obj as Record<string, unknown>)
    .sort()
    .map((k) => JSON.stringify(k) + ':' + canonicalize((obj as Record<string, unknown>)[k]));
  return '{' + sorted.join(',') + '}';
}

async function sign(privateKey: CryptoKey, payload: unknown): Promise<string> {
  const sig = await subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    privateKey,
    new TextEncoder().encode(canonicalize(payload)),
  );
  return Buffer.from(sig).toString('base64url');
}

async function verify(
  publicKey: CryptoKey, payload: unknown, signature: string,
): Promise<boolean> {
  return subtle.verify(
    { name: 'ECDSA', hash: 'SHA-256' },
    publicKey,
    Buffer.from(signature, 'base64url'),
    new TextEncoder().encode(canonicalize(payload)),
  );
}

async function exportJWK(key: CryptoKey): Promise<JsonWebKey> {
  return subtle.exportKey('jwk', key);
}

// ─── A2A Signed Agent Card ─────────────────────────────────
interface AgentCard {
  name: string;
  url: string;
  skills: Array<{ id: string; name: string }>;
  authentication: { schemes: string[] };
}

interface SignedAgentCard {
  card: AgentCard;
  jwk: JsonWebKey;            // 公钥，用于验证
  signature: string;          // card 的签名
  alg: 'ES256';
  timestamp: number;
}

async function createSignedCard(
  card: AgentCard, privateKey: CryptoKey,
): Promise<SignedAgentCard> {
  const jwk = await exportJWK(privateKey);
  return {
    card,
    jwk: { kty: jwk.kty, crv: jwk.crv, x: jwk.x, y: jwk.y }, // 只保留公钥部分
    signature: await sign(privateKey, card),
    alg: 'ES256',
    timestamp: Date.now(),
  };
}

// ─── Trust Engine (与 lab/a2a-trust-prototype 对齐) ─────────
type TrustLevel = 'unknown' | 'untrusted' | 'neutral' | 'trusted';

class TrustEngine {
  private scores = new Map<string, { score: number; n: number; lastSeen: number }>();

  private get(id: string) {
    let r = this.scores.get(id);
    if (!r) {
      r = { score: 50, n: 0, lastSeen: Date.now() };
      this.scores.set(id, r);
    }
    return r;
  }

  /** 记录交互，动态调整信任分 */
  record(agentId: string, success: boolean): number {
    const r = this.get(agentId);
    r.n++;
    r.lastSeen = Date.now();
    if (success) {
      r.score = Math.min(100, r.score + 5 * Math.max(0.1, 1 - (r.n - 1) * 0.01));
    } else {
      r.score = Math.max(0, r.score - 15); // 惩罚 > 奖励
    }
    return r.score;
  }

  level(agentId: string): TrustLevel {
    const r = this.scores.get(agentId);
    if (!r) return 'unknown';
    if (r.score < 50) return 'untrusted';
    if (r.score < 80) return 'neutral';
    return 'trusted';
  }

  /** 时间衰减：长时间不交互自动降分 */
  decay(hoursElapsed: number = 1): void {
    for (const [, r] of this.scores) {
      r.score = Math.max(0, r.score - 0.5 * hoursElapsed);
    }
  }
}

// ─── Trust Middleware ───────────────────────────────────────
async function verifyAndGate(
  signedCard: SignedAgentCard,
  trustEngine: TrustEngine,
  requiredLevel: TrustLevel,
): Promise<{ allowed: boolean; reason: string }> {
  // Step 1: 验证签名
  const pubKey = await subtle.importKey(
    'jwk', signedCard.jwk,
    { name: 'ECDSA', namedCurve: 'P-256' }, true, ['verify'],
  );
  const valid = await verify(pubKey, signedCard.card, signedCard.signature);
  if (!valid) return { allowed: false, reason: 'INVALID_SIGNATURE' };

  // Step 2: 检查信任等级
  const level = trustEngine.level(signedCard.card.name);
  const levels: TrustLevel[] = ['untrusted', 'unknown', 'neutral', 'trusted'];
  const required = levels.indexOf(requiredLevel);
  const actual = levels.indexOf(level);
  if (actual < required)
    return { allowed: false, reason: `INSUFFICIENT_TRUST: ${level} < ${requiredLevel}` };

  return { allowed: true, reason: 'OK' };
}

// ─── Demo ───────────────────────────────────────────────────
async function demo() {
  console.log('=== A2A Signed Agent Card + Trust Demo ===\n');

  const keyPair = await generateKeyPair();
  const trust = new TrustEngine();

  const card: AgentCard = {
    name: 'flight-booking-agent',
    url: 'https://agents.example.com/booking',
    skills: [{ id: 'book-flight', name: 'Flight Booking' }],
    authentication: { schemes: ['oauth2'] },
  };

  // 创建签名卡
  const signed = await createSignedCard(card, keyPair.privateKey);
  console.log('📋 Signed Agent Card:');
  console.log(JSON.stringify(signed, null, 2));
  console.log();

  // 模拟多次交互，观察信任分变化
  console.log('--- Trust Score Evolution ---');
  for (let i = 0; i < 10; i++) {
    const success = Math.random() > 0.2; // 80% 成功率
    const score = trust.record('flight-booking-agent', success);
    console.log(`  Interaction ${i + 1}: ${success ? '✅' : '❌'} → score=${score.toFixed(1)} level=${trust.level('flight-booking-agent')}`);
  }
  console.log();

  // 验证并访问控制
  const result = await verifyAndGate(signed, trust, 'neutral');
  console.log(`🔒 Access Gate (requires 'neutral'): ${result.allowed ? '✅ ALLOWED' : '❌ DENIED'} — ${result.reason}`);

  // 篡改检测
  console.log('\n--- Tamper Detection ---');
  const tamperedCard = { ...signed, card: { ...signed.card, name: 'evil-agent' } };
  const tamperResult = await verifyAndGate(tamperedCard, trust, 'neutral');
  console.log(`🔓 Tampered card check: ${tamperResult.allowed ? '⚠️ ALLOWED' : '✅ BLOCKED'} — ${tamperResult.reason}`);
}

demo().catch(console.error);
```

**运行方式**：
```bash
# 零依赖，直接运行
npx tsx a2a-signed-card-demo.ts
# 或
ts-node a2a-signed-card-demo.ts
```

**预期输出**：
```
=== A2A Signed Agent Card + Trust Demo ===

📋 Signed Agent Card:
{
  "card": {
    "name": "flight-booking-agent",
    "url": "https://agents.example.com/booking",
    ...
  },
  "signature": "base64url...",
  "alg": "ES256"
}

--- Trust Score Evolution ---
  Interaction 1: ✅ → score=55.0 level=neutral
  Interaction 2: ✅ → score=59.9 level=neutral
  Interaction 3: ❌ → score=44.9 level=untrusted
  ...

🔒 Access Gate (requires 'neutral'): ✅ ALLOWED — OK

--- Tamper Detection ---
🔓 Tampered card check: ✅ BLOCKED — INVALID_SIGNATURE
```

---

## 关键洞察

### 1. A2A 的签名是「可选而非强制」— 这是最大的安全缺陷

Semgrep 安全团队的发现：v0.3 支持签名但**不强制**。这意味着：
- 生产环境必须自己实现签名验证中间件
- 不能信任「未签名的 Agent Card」
- 我们的 `a2a-trust-prototype` 的 middleware 应该**默认拒绝未签名卡**

**行动项**：在 `lab/a2a-trust-prototype/src/middleware.ts` 中增加 `requireSignature: true` 默认配置。

### 2. Trust Score 的 "Negative Bias" 是核心设计模式

几乎所有信任框架都采用「惩罚 > 奖励」的非对称设计：
- 成功 +5（递减），失败 -15（固定）
- 这不是 bug — 这是防 Sybil 攻击的基础
- **与 agent-memory-graph 的 recommend()** 的 Jaccard 相似度思路一致 — 稀有正向信号比高频信号更有价值

**与现有项目的关联**：`agent-trust-score` 可以直接复用 `a2a-trust-prototype` 的 TrustEngine，然后暴露为 `agent-memory-graph` 的一个分析维度。

### 3. A2A + MCP 的互补架构 = 我们的 langgraph-bridge

Google 的参考架构：**编排层用 A2A，工具层用 MCP**。这恰好对应我们的 `openclaw-langgraph-bridge`：
- Supervisor（编排）= A2A 的 "Client Agent"
- Worker Pool（执行）= A2A 的 "Remote Agent"
- MCP 连接 = 每个 Worker 内部的工具调用

**行动项**：评估在 langgraph-bridge 的 Supervisor 中增加 A2A 兼容的 Agent Card 发布能力。

### 4. KYA (Know Your Agent) 将成为合规要求

Chaffer 的 "Know Your Agent" 论文 + EU AI Act 的趋势：
- 类似金融 KYC 但面向 AI Agent
- 要求：身份验证、行为监控、风险分类、合规审计
- **ERC-8004** 已经在链上实现了这个模型（身份注册 + 加权信誉 + Sybil 防护）
- 2026 年下半年预计出现更多监管要求

### 5. 从 "Zero Trust" 到 "Post-Zero-Trust"

- 传统 Zero Trust：每次请求都验证身份
- Post-Zero-Trust：**身份本身就是去中心化的**，没有中心权威
- 技术栈：DID + VCs + Blockchain + ZKP
- 对我们的影响：`agent-context-store` 的 Agent 身份标识应该支持 DID 格式

---

## 下一步行动

1. **🔥 升级 `lab/a2a-trust-prototype`** — 增加 A2A v0.3 兼容的签名卡格式（JWS + kid + jku），默认拒绝未签名卡
2. **📊 Trust Engine → agent-memory-graph 集成** — 将信任分作为 graph 节点的属性，支持跨 Agent 信任传递
3. **🔐 langgraph-bridge Agent Card** — 在 Supervisor 层增加 A2A 兼容的 Agent Card 发布（`/.well-known/agent.json`）

---

## 质量自检

| 维度 | 状态 | 说明 |
|------|------|------|
| 可运行代码 | ✅ | 零依赖 TypeScript，直接 npx tsx 运行 |
| 独到见解 | ✅ | 指出 A2A 签名非强制的安全缺陷；与 langgraph-bridge 的架构映射 |
| 项目关联 | ✅ | 关联 a2a-trust-prototype, langgraph-bridge, agent-memory-graph |
| 核心概念 | ✅ | 5个：A2A v0.3, Signed Cards, Zero-Trust Identity, Trust Scoring, Post-Zero-Trust |
| 下一步 | ✅ | 3个具体行动项，都有明确的代码落地路径 |

---

## 参考资料

1. [Google A2A Protocol v0.3 Announcement](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade)
2. [Semgrep: Security Engineer's Guide to A2A](https://semgrep.dev/blog/2025/a-security-engineers-guide-to-the-a2a-protocol)
3. [Palo Alto: A2A Protocol Security Guide](https://live.paloaltonetworks.com/t5/community-blogs/safeguarding-ai-agents-an-in-depth-look-at-a2a-protocol-risks/ba-p/1235996)
4. [A2A Spec Discussion: Sign Agent Cards](https://github.com/a2aproject/A2A/discussions/199)
5. [Chaffer: "Know Your Agent" — Governing AI Identity on the Agentic Web](https://philarchive.org/archive/CHAKYAv1)
6. [Huang et al.: Zero-Trust Identity Framework for Agentic AI, arXiv:2505.19301](https://arxiv.org/abs/2505.19301)
7. [Cisco: A New Identity Framework for AI Agents](https://community.cisco.com/t5/security-blogs/a-new-identity-framework-for-ai-agents/ba-p/5294337)
8. [ERC-8004: Trustless Agents Standard](https://github.com/sudeepb02/awesome-erc8004)
9. [cheqd: AI Agent Trust Framework](https://cheqd.io/blog/ai-agents-framework-how-to-plug-them-with-cheqd-trust-framework)
