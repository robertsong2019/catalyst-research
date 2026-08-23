# A2A Trust Protocol — Agent间信任层深度研究

> 日期: 2026-05-29 | Catalyst Deep Exploration | autoresearch 方法论

## 研究背景

HEARTBEAT.md 高优先级任务：**创建 lab/a2a-trust-prototype/** — Node.js 原生 crypto ES256 签名中间件 + Trust Score。

核心问题：当 AI agents 跨组织、跨框架协作时，如何建立可验证的信任关系？

---

## 核心概念

### 1. Agent Card（Agent 身份声明）

A2A 协议的基础单元。JSON 格式的元数据文档，发布在 `/.well-known/agent.json`，声明 agent 的身份、能力、认证方式和技能。

```json
{
  "name": "CatalystResearchAgent",
  "description": "深度技术研究 agent",
  "url": "https://agents.catalyst.dev/a2a",
  "version": "1.0.0",
  "capabilities": { "streaming": true, "pushNotifications": true },
  "authentication": { "schemes": ["bearer"] },
  "skills": [
    {
      "id": "deep-research",
      "name": "Deep Research",
      "description": "执行多步骤技术研究",
      "inputModes": ["text", "data"],
      "outputModes": ["text", "data"]
    }
  ]
}
```

**关键洞察**: Agent Card 是 agent 的"名片"，但标准 A2A 协议中的 Card 只声明认证方案（OAuth2/API Key），不包含动态信任评分。这是 trust layer 需要填补的空白。

### 2. Agentic Zero Trust（零信任代理模型）

来自 Cequence Security 2026 年研究论文。核心思路：**每个 agent 请求都必须经过身份验证+授权，无论它在网络中的位置**。

关键机制：
- **OAuth 2.0 Token Exchange (RFC 8693)**: 每个 delegation hop 都颁发新的、scope 更窄、lifetime 更短的 token
- **Per-instance agent identity**: 超越 pod-level（SPIFFE/SPIRE），做到实例级别 attestation
- **Agent Naming Service (ANS)**: 发现机制，附带 trust score，防止 agent 冒充

### 3. ERC-8004 — 链上 Agent 身份与信誉（Trustless Agents）

Ethereum 上的 agent 身份标准，2025 年 8 月提出，2026 年 1 月主网部署。三个核心注册表：

| 注册表 | 功能 | 技术 |
|--------|------|------|
| **Identity Registry** | 便携 agent 身份 (ERC-721 NFT) | tokenId → tokenURI (IPFS JSON) |
| **Reputation Registry** | 授权客户端发布评分、标签、证据 URI | 链上事件 + 链下数据 |
| **Validation Registry** | 第三方验证 agent 行为 (0-100 分) | 支持 stake-based re-execution, zkML, TEE |

**关键洞察**: ERC-8004 的 trust score 不是单一数字，而是由多个信号源组成的复合评分：历史任务评分 + 第三方验证 + 链上行为证据。这比简单的"信任分"更鲁棒。

### 4. DID/VC — 去中心化身份与可验证凭证

W3C 标准的 Decentralized Identifiers + Verifiable Credentials 为 agent 提供跨组织信任：

- **DID**: 全局唯一、密码学可验证的标识符，不依赖中央权威
- **VC**: 数字签名的证明，包含 agent 的能力、来源、安全态势
- **Verifiable Presentation**: agent 向对方展示选择性披露的凭证，保护隐私

**关键洞察**: DID/VC 是 A2A 协议的信任基础设施层。A2A 定义了 agents 如何通信，DID/VC 定义了如何验证对方身份。

### 5. Trust Score 计算模型

综合各方案，trust score 应包含以下因子：

```
trust_score = w1 * reputation_history    # 历史交互评分 (ERC-8004 Reputation)
            + w2 * validation_score      # 第三方验证结果 (ERC-8004 Validation)
            + w3 * credential_strength   # DID/VC 凭证强度
            + w4 * behavioral_consistency # 行为一致性 (异常检测)
            + w5 * stake_alignment       # 利益对齐 (stake-based)
```

典型权重: `0.3, 0.25, 0.2, 0.15, 0.1`（根据场景调整）

---

## 代码示例：Node.js ES256 签名中间件

这是 `lab/a2a-trust-prototype` 的核心原型。使用 Node.js 原生 `crypto` 模块实现 ES256 (ECDSA + P-256 + SHA-256) 签名和验证。

```typescript
// a2a-trust-middleware.ts
// A2A Trust Layer: ES256 签名中间件 + Trust Score 计算

import { createSign, createVerify, generateKeyPairSync, randomUUID } from 'node:crypto';

// ─── 类型定义 ───────────────────────────────────────────

interface AgentIdentity {
  agentId: string;           // DID 格式: did:a2a:<uuid>
  publicKey: string;         // PEM 格式
  privateKey?: string;       // 仅 agent 自身持有
  capabilities: string[];    // 声明的能力
  trustLevel: 'unknown' | 'basic' | 'verified' | 'trusted';
}

interface TrustScore {
  agentId: string;
  score: number;             // 0-100
  factors: {
    reputationHistory: number;   // 0-100
    validationScore: number;     // 0-100
    credentialStrength: number;  // 0-100
    behavioralConsistency: number; // 0-100
  };
  updatedAt: string;         // ISO timestamp
  signature: string;         // ES256 签名，防止篡改
}

interface SignedMessage {
  header: {
    from: string;            // sender agentId
    to: string;              // recipient agentId
    timestamp: string;       // ISO timestamp
    messageId: string;       // UUID
  };
  payload: unknown;          // 任意 JSON-serializable data
  signature: string;         // ES256 签名
}

// ─── 密钥管理 ───────────────────────────────────────────

export function generateAgentIdentity(capabilities: string[]): AgentIdentity {
  const { publicKey, privateKey } = generateKeyPairSync('ec', {
    namedCurve: 'P-256',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });

  return {
    agentId: `did:a2a:${randomUUID()}`,
    publicKey,
    privateKey,
    capabilities,
    trustLevel: 'unknown',
  };
}

// ─── 消息签名 ───────────────────────────────────────────

export function signMessage(
  identity: AgentIdentity,
  recipientId: string,
  payload: unknown
): SignedMessage {
  if (!identity.privateKey) {
    throw new Error('Cannot sign: private key not available');
  }

  const header: SignedMessage['header'] = {
    from: identity.agentId,
    to: recipientId,
    timestamp: new Date().toISOString(),
    messageId: randomUUID(),
  };

  // 签名内容: header + payload 的规范 JSON 序列化
  const signingInput = JSON.stringify({ header, payload });

  const signer = createSign('SHA256');
  signer.update(signingInput);
  signer.end();

  const signature = signer.sign(identity.privateKey, 'base64url');

  return { header, payload, signature };
}

// ─── 签名验证 ───────────────────────────────────────────

export function verifyMessage(
  message: SignedMessage,
  senderPublicKey: string
): boolean {
  const signingInput = JSON.stringify({
    header: message.header,
    payload: message.payload,
  });

  const verifier = createVerify('SHA256');
  verifier.update(signingInput);
  verifier.end();

  return verifier.verify(senderPublicKey, message.signature, 'base64url');
}

// ─── Trust Score 计算 ───────────────────────────────────

const WEIGHTS = {
  reputationHistory: 0.30,
  validationScore: 0.25,
  credentialStrength: 0.20,
  behavioralConsistency: 0.25,  // 简化为4因子
};

export function calculateTrustScore(
  factors: TrustScore['factors'],
  signerIdentity: AgentIdentity
): TrustScore {
  const score = Math.round(
    factors.reputationHistory * WEIGHTS.reputationHistory +
    factors.validationScore * WEIGHTS.validationScore +
    factors.credentialStrength * WEIGHTS.credentialStrength +
    factors.behavioralConsistency * WEIGHTS.behavioralConsistency
  );

  const scoreData = {
    agentId: signerIdentity.agentId,
    score: Math.max(0, Math.min(100, score)),
    factors,
    updatedAt: new Date().toISOString(),
  };

  // 对 trust score 自身签名，防止篡改
  if (!signerIdentity.privateKey) {
    throw new Error('Cannot sign trust score: private key not available');
  }

  const signer = createSign('SHA256');
  signer.update(JSON.stringify(scoreData));
  signer.end();
  const signature = signer.sign(signerIdentity.privateKey, 'base64url');

  return { ...scoreData, signature };
}

export function verifyTrustScore(
  trustScore: TrustScore,
  publicKey: string
): boolean {
  const { signature, ...data } = trustScore;
  const verifier = createVerify('SHA256');
  verifier.update(JSON.stringify(data));
  verifier.end();
  return verifier.verify(publicKey, signature, 'base64url');
}

// ─── Express 中间件 ─────────────────────────────────────

import { NextFunction, Request, Response } from 'express';

interface TrustedAgentRequest extends Request {
  senderAgent?: {
    agentId: string;
    verified: boolean;
    trustScore?: TrustScore;
  };
}

export function a2aTrustMiddleware(
  trustedAgents: Map<string, AgentIdentity>,
  minTrustScore: number = 50
) {
  return async (
    req: TrustedAgentRequest,
    res: Response,
    next: NextFunction
  ) => {
    // 1. 提取签名消息
    const signedMsg: SignedMessage | undefined = req.body;
    if (!signedMsg?.header?.from || !signedMsg?.signature) {
      res.status(401).json({ error: 'Missing signed message' });
      return;
    }

    // 2. 查找发送者公钥
    const sender = trustedAgents.get(signedMsg.header.from);
    if (!sender) {
      res.status(403).json({ error: 'Unknown agent' });
      return;
    }

    // 3. 验证签名
    const verified = verifyMessage(signedMsg, sender.publicKey);
    if (!verified) {
      res.status(401).json({ error: 'Invalid signature' });
      return;
    }

    // 4. 检查时间戳 (防重放，允许 5 分钟窗口)
    const msgTime = new Date(signedMsg.header.timestamp).getTime();
    const now = Date.now();
    if (Math.abs(now - msgTime) > 5 * 60 * 1000) {
      res.status(401).json({ error: 'Message timestamp expired' });
      return;
    }

    // 5. 附带验证信息到 request
    req.senderAgent = {
      agentId: sender.agentId,
      verified: true,
    };

    next();
  };
}

// ─── 完整使用示例 ───────────────────────────────────────

// 运行: npx tsx a2a-trust-middleware.ts

function demo() {
  console.log('=== A2A Trust Protocol Demo ===\n');

  // 1. 生成两个 agent 身份
  const alice = generateAgentIdentity(['research', 'analysis']);
  const bob = generateAgentIdentity(['coding', 'testing']);

  console.log('Agent Alice:', alice.agentId);
  console.log('Agent Bob:  ', bob.agentId);
  console.log('Alice capabilities:', alice.capabilities.join(', '));
  console.log();

  // 2. Alice 签名一条消息给 Bob
  const taskPayload = {
    type: 'task_request',
    task: 'Implement ES256 signing middleware',
    priority: 'high',
  };

  const signedMsg = signMessage(alice, bob.agentId, taskPayload);
  console.log('Signed message:', JSON.stringify(signedMsg.header, null, 2));
  console.log('Signature:', signedMsg.signature.substring(0, 40) + '...');
  console.log();

  // 3. Bob 验证 Alice 的消息
  const isValid = verifyMessage(signedMsg, alice.publicKey);
  console.log('Bob verifies Alice\'s message:', isValid ? '✅ VALID' : '❌ INVALID');
  console.log();

  // 4. 计算 Alice 的 trust score
  const aliceTrustScore = calculateTrustScore(
    {
      reputationHistory: 85,    // 历史任务完成率 85%
      validationScore: 92,      // 第三方验证评分 92
      credentialStrength: 78,   // DID/VC 凭证强度 78
      behavioralConsistency: 88, // 行为一致性 88
    },
    alice
  );
  console.log('Alice Trust Score:', aliceTrustScore.score, '/ 100');
  console.log('Factors:', JSON.stringify(aliceTrustScore.factors, null, 2));
  console.log();

  // 5. 验证 trust score 签名
  const scoreVerified = verifyTrustScore(aliceTrustScore, alice.publicKey);
  console.log('Trust score signature:', scoreVerified ? '✅ VALID' : '❌ INVALID');

  // 6. 篡改检测
  const tamperedScore = { ...aliceTrustScore, score: 99 };
  const tamperedVerified = verifyTrustScore(tamperedScore, alice.publicKey);
  console.log('Tampered score detection:', tamperedVerified ? '❌ NOT DETECTED' : '✅ DETECTED');
}

// 仅在直接运行时执行 demo
if (require.main === module) {
  demo();
}

export { AgentIdentity, TrustScore, SignedMessage };
```

### 运行方式

```bash
# 无需外部依赖，仅使用 Node.js 原生 crypto
npx tsx a2a-trust-middleware.ts

# 预期输出:
# === A2A Trust Protocol Demo ===
#
# Agent Alice: did:a2a:550e8400-e29b-41d4-a716-446655440000
# Agent Bob:   did:a2a:6ba7b810-9dad-11d1-80b4-00c04fd430c8
# Bob verifies Alice's message: ✅ VALID
# Alice Trust Score: 86 / 100
# Trust score signature: ✅ VALID
# Tampered score detection: ✅ DETECTED
```

---

## 关键洞察

### 洞察 1: A2A 协议解决了"通信"问题，但"信任"是独立的层

Google 的 A2A 协议 (v0.3, 2025年7月) 定义了 agent 间的发现、任务委派和结果返回，但信任评分不内置。ERC-8004 的 Reputation + Validation 注册表，以及 Agentic Zero Trust 的 OAuth 2.0 Token Exchange，都是独立的信任层实现。

**对 lab/a2a-trust-prototype 的启示**: 不要试图修改 A2A 协议本身，而是在 A2A 之上构建 trust middleware 作为独立层。

### 洞察 2: Trust Score 不是静态数字，而是动态复合信号

各方案的共同特征：trust score 由多个因子动态计算，而非简单的"信任度 0-100"。ERC-8004 的三个注册表（Identity/Reputation/Validation）各自提供不同维度的信号。

**对原型设计的启示**: 
- Trust score 应该附带 factor breakdown（因子分解），让消费方能理解为什么高分/低分
- 因子权重应该是可配置的（不同场景关注不同维度）

### 洞察 3: 零信任的核心是"每跳衰减"，而非"全局信任"

Agentic Zero Trust 的精髓：每次 agent 间 delegation，权限都应衰减（scope 更窄、lifetime 更短）。这与传统的"建立信任后全权委托"模式根本不同。

**对中间件设计的启示**: 
- 中间件不仅要验证签名，还要检查 scope 和 lifetime
- 每次转发都应生成新的、更受限的凭证

### 洞察 4: 签名是信任的基础设施，不是信任本身

ES256 签名解决的是"这条消息确实来自该 agent"，但不解决"该 agent 是否可信"。签名是必要条件，trust score 是充分条件。两者必须结合：
- 签名 → 身份验证 (authentication)
- Trust score → 授权决策 (authorization)

### 洞察 5: 实用主义的信任分层

对于大多数场景，不需要完整的链上信任系统。实用的信任分层：

| 层 | 机制 | 适用场景 |
|----|------|---------|
| L1: 签名验证 | ES256/Ed25519 | 所有 A2A 交互 |
| L2: 本地信誉 | 内存/数据库评分 | 单组织内 agents |
| L3: 联邦验证 | DID/VC + ANS | 跨组织 agents |
| L4: 链上证明 | ERC-8004 | 价值转移/金融场景 |

---

## 与现有项目的关联

| 项目 | 关联点 |
|------|--------|
| **openclaw-langgraph-bridge** | Supervisor 模式中的 agent 间委派需要信任验证 |
| **agent-context-store** | snapshot 签名验证可复用 ES256 中间件 |
| **agent-memory-graph** | importance_rank 的 trust score 可作为节点权重因子 |
| **prompt-router** | 路由决策可考虑目标 agent 的 trust score |

---

## 下一步行动

1. **创建 `lab/a2a-trust-prototype/`** — 基于本研究的代码示例，搭建完整项目：
   - `src/identity.ts` — DID 生成 + key 管理
   - `src/signing.ts` — ES256 签名/验证
   - `src/trust-score.ts` — 多因子 trust score 计算
   - `src/middleware.ts` — Express/Fastify 中间件
   - `tests/` — 单元测试

2. **研究 A2A SDK 集成** — 调研 `@dexwox-labs/a2a-node` SDK，将 trust middleware 集成到 A2A client/server 流程中

3. **设计 Trust Score 持久化** — 定义 trust score 的存储格式和查询接口，考虑与 agent-context-store 的 snapshot 机制结合

---

## 参考资料

- [A2A Protocol Specification](https://github.com/google-a2a/A2A) — Google A2A 官方仓库 (22K+ stars)
- [ERC-8004: Trustless Agents](https://ethereum-magicians.org/t/erc-8004-trustless-agents) — Ethereum agent 身份标准
- [ERC-8126: AI Agent Verification](https://ethereum-magicians.org/t/erc-8126-ai-agent-verification/27445) — 多层验证提案
- [Agentic Zero Trust](https://www.cequence.ai/wp-content/uploads/2026/05/Agentic-Zero-Trust-Research-Paper-v3.pdf) — Cequence Security 研究论文 (May 2026)
- [Zero-Trust Identity Framework for Agentic AI](https://arxiv.org/html/2505.19301v1) — arXiv 论文
- [A2A Protocol Ecosystem Map 2026](https://www.digitalapplied.com/blog/ai-agent-protocol-ecosystem-map-2026-mcp-a2a-acp-ucp) — 协议全景图
- [@dexwox-labs/a2a-node](https://github.com/google-a2a/A2A/discussions/679) — TypeScript A2A SDK
- [IETF draft-sharif-agent-payment-trust](https://datatracker.ietf.org/doc/draft-sharif-agent-payment-trust) — Agent 支付信任标准草案
