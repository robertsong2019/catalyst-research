# A2A Protocol — Agent-to-Agent 通信与信任机制

> 研究日期: 2026-05-22
> 关联项目: lab/a2a-trust-prototype
> 来源: Google A2A Spec, Red Hat, Palo Alto, AgentGraph, Zuplo, arxiv:2504.16902

---

## 核心概念 (5)

### 1. Agent Card (发现与自描述)
- 发布在 `/.well-known/agent-card.json`
- JSON 元数据：身份、端点 URL、能力列表、认证要求、skills
- 类似 OpenAPI 的 `securitySchemes` 声明认证方式
- v0.3 新增 Agent Card 签名（防篡改）

### 2. Task Lifecycle (任务状态机)
```
submitted → working → input-required → completed
                   ↘ auth-required
                   ↘ failed
                   ↘ canceled
```
- `contextId` 可关联多个任务（会话概念）
- 长任务支持 SSE 流式更新 (`tasks.sendSubscribe`)
- 产出物叫 **Artifact**（结构化输出）

### 3. JSON-RPC 2.0 over HTTPS (传输层)
- `tasks/send` — 同步/一次性任务
- `tasks/sendSubscribe` — 长任务 + SSE 流
- `tasks/get` — 查询任务状态
- `tasks/cancel` — 取消任务
- 标准 HTTP，网关友好（限流、认证、日志全部复用）

### 4. 认证模型 (5种)
| 类型 | 适用场景 |
|------|---------|
| `apiKey` | 简单服务间调用 |
| `http` (Bearer) | JWT token |
| `oauth2` | 企业级授权 |
| `openIdConnect` | 身份联邦 |
| `mtls` | 零信任、服务网格 |

关键点：**认证在 HTTP 传输层**，不在 payload 里。Agent Card 声明要求，客户端按声明提供凭据。

### 5. 去中心化身份 (DID + JWKS)
- Mike Prince 已将 DID 认证 hooks 合入 A2A JS SDK
- 流程：客户端签名 challenge → 生成 JWT → 服务端通过 JWKS (`/.well-known/jwks.json`) 验证
- AgentGraph 项目：图遍历返回**签名证明**而非信任分数
- 三层信任栈：AgentGraph（预交互）→ MoltBridge（交互历史）→ Verascore（持续监控）

---

## 关键洞察 (4)

### 🔍 洞察 1: A2A ≠ MCP，它们互补
- **MCP**: Agent ↔ Tools（纵向，一个 agent 连自己的工具）
- **A2A**: Agent ↔ Agent（横向，多个 agent 协作）
- 架构图：Orchestrator Agent 通过 A2A 分配子任务，每个子 Agent 用 MCP 连自己的工具
- **对我们意味着**: a2a-trust-prototype 应该设计为 MCP 工具和 A2A 中间件之间的桥梁

### 🔍 洞察 2: 信任的关键不是分数，是签名证明
- AgentGraph 的教训：图遍历返回的不是 `trust_score: 66`，而是 **JWS (EdDSA/ES256) 签名的声明**
- 消费者通过 JWKS 验证签名，不需要信任中间人
- **设计原则**: a2a-trust 的 Trust Score 必须伴随可验证的签名证据，否则只是建议

### 🔍 洞察 3: 认证在传输层，授权在后端
- Palo Alto 的安全分析：即使网关验证了凭据，后端也必须独立验证角色和 scope
- 攻击向量：持有 calendar+hotel scope 的 agent 通过 prompt injection 让 orchestrator 发起 flight-booking
- **零信任原则**: 每个 agent 独立验证权限，不依赖上游

### 🔍 洞察 4: Agent Card 是攻击面
- Agent Card 是公开的、可变的 JSON —— 可能被篡改
- v0.3 的 Agent Card 签名是缓解措施
- 缓存 Agent Card 带来过期风险，不缓存带来性能问题
- **建议**: 实现 Agent Card 签名验证 + TTL 缓存策略

---

## 可运行代码示例：ES256 Agent Card 签名验证 + Trust Score 中间件

```typescript
// a2a-trust-middleware.ts — 用于 lab/a2a-trust-prototype
import { createVerify, createSign, randomBytes } from 'node:crypto';

// --- Agent Card 签名 ---

interface AgentCard {
  id: string;
  name: string;
  endpoint: string;
  skills: string[];
  securitySchemes: Record<string, { type: string }>;
}

function signAgentCard(card: AgentCard, privateKey: string): string {
  const sign = createSign('ES256');
  sign.update(JSON.stringify(card));
  sign.end();
  return sign.sign(privateKey, 'base64url');
}

function verifyAgentCard(card: AgentCard, signature: string, publicKey: string): boolean {
  const verify = createVerify('ES256');
  verify.update(JSON.stringify(card));
  verify.end();
  return verify.verify(publicKey, signature, 'base64url');
}

// --- Trust Score with Signed Evidence ---

interface TrustAttestation {
  issuer: string;       // attestor agent ID
  subject: string;      // attested agent ID  
  type: 'CAPABILITY' | 'SECURITY' | 'RELIABILITY';
  score: number;        // 0-100
  evidenceHash: string; // SHA-256 of supporting evidence
  issuedAt: number;     // timestamp
  expiresAt: number;
  jws: string;          // compact JWS signature
}

class TrustStore {
  private attestations = new Map<string, TrustAttestation[]>();

  addAttestation(attestation: TrustAttestation): void {
    const existing = this.attestations.get(attestation.subject) || [];
    existing.push(attestation);
    this.attestations.set(attestation.subject, existing);
  }

  getTrustScore(agentId: string): { score: number; evidence: TrustAttestation[] } {
    const attestations = this.attestations.get(agentId) || [];
    const now = Date.now();
    const valid = attestations.filter(a => a.expiresAt > now);
    
    if (valid.length === 0) return { score: 0, evidence: [] };
    
    // Weighted average, more recent = higher weight
    const totalWeight = valid.reduce((sum, a) => sum + (1 / (now - a.issuedAt + 1)), 0);
    const score = valid.reduce((sum, a) => {
      const weight = 1 / (now - a.issuedAt + 1);
      return sum + a.score * weight;
    }, 0) / totalWeight;
    
    return { score: Math.round(score), evidence: valid };
  }

  verifyAttestation(attestation: TrustAttestation, publicKey: string): boolean {
    const payload = JSON.stringify({
      issuer: attestation.issuer,
      subject: attestation.subject,
      type: attestation.type,
      score: attestation.score,
      evidenceHash: attestation.evidenceHash,
      issuedAt: attestation.issuedAt,
    });
    const verify = createVerify('ES256');
    verify.update(payload);
    verify.end();
    return verify.verify(publicKey, attestation.jws, 'base64url');
  }
}

// --- A2A Request Trust Middleware ---

interface A2ARequest {
  agentCard: AgentCard;
  signature: string;
  taskType: string;
}

function createTrustMiddleware(trustStore: TrustStore, minScore: number = 50) {
  return function trustCheck(req: A2ARequest, issuerPublicKey: string): {
    allowed: boolean;
    reason: string;
    trustScore: number;
  } {
    // 1. Verify agent card signature
    if (!verifyAgentCard(req.agentCard, req.signature, issuerPublicKey)) {
      return { allowed: false, reason: 'Invalid agent card signature', trustScore: 0 };
    }
    
    // 2. Check trust score
    const { score, evidence } = trustStore.getTrustScore(req.agentCard.id);
    
    if (score < minScore) {
      return { 
        allowed: false, 
        reason: `Trust score ${score} below minimum ${minScore}`,
        trustScore: score 
      };
    }
    
    // 3. Verify all evidence signatures
    for (const att of evidence) {
      if (!trustStore.verifyAttestation(att, issuerPublicKey)) {
        return { allowed: false, reason: `Invalid attestation from ${att.issuer}`, trustScore: score };
      }
    }
    
    return { allowed: true, reason: 'OK', trustScore: score };
  };
}

// --- Demo ---

import { generateKeyPairSync } from 'node:crypto';

const { publicKey, privateKey } = generateKeyPairSync('ec', {
  namedCurve: 'P-256',
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

const card: AgentCard = {
  id: 'agent://research.catalyst.dev',
  name: 'Catalyst Research Agent',
  endpoint: 'https://api.catalyst.dev/a2a',
  skills: ['deep-research', 'code-generation'],
  securitySchemes: { bearer: { type: 'http', scheme: 'bearer' } },
};

const sig = signAgentCard(card, privateKey);
console.log('✅ Card signed:', sig.slice(0, 20) + '...');
console.log('✅ Verify:', verifyAgentCard(card, sig, publicKey));

const store = new TrustStore();
store.addAttestation({
  issuer: 'agent://verifier.trust.dev',
  subject: 'agent://research.catalyst.dev',
  type: 'SECURITY',
  score: 85,
  evidenceHash: randomBytes(32).toString('hex'),
  issuedAt: Date.now() - 1000,
  expiresAt: Date.now() + 86400000,
  jws: '', // In production, sign the payload
});

const middleware = createTrustMiddleware(store, 50);
const result = middleware({ agentCard: card, signature: sig, taskType: 'research' }, publicKey);
console.log('✅ Trust check:', result);
```

运行方式：
```bash
npx tsx a2a-trust-middleware.ts
# 或存为 .mjs 用 node --experimental-strip-types 运行
```

---

## 与现有项目关联

| 项目 | 关联点 |
|------|-------|
| **a2a-trust-prototype** | 直接输入 — 上面的代码可作为 lab 起始模板 |
| **agent-context-store** | Trust Score 可作为 store 的 metadata，用 `incr`/`decr` 追踪信任变化 |
| **AMS** | Agent Card 可作为 AMS 的身份层，attestation 作为 memory 的安全维度 |
| **OpenClaw MCP** | A2A 的 Agent Card 模式可启发 MCP server 的能力声明 |
| **langgraph-bridge** | LangGraph 多 agent 编排可走 A2A 协议做 agent 间通信 |

---

## 下一步行动

1. **启动 lab/a2a-trust-prototype/** — 基于上面的代码模板，实现完整 ES256 签名 + JWKS 端点 + Trust Store
2. **验证 A2A JS SDK** — `npm install @a2aproject/a2a` 测试 Mike Prince 的认证 hooks
3. **实现 Agent Card 签名验证** — 参照 v0.3 spec，确保 Agent Card 防篡改
4. **写实验记录** — 在 lab/ 下创建 `experiments.tsv`，按 autoresearch 方法论迭代

---

## 参考来源

- [Google A2A Announcement](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability) — April 2025
- [A2A Protocol Guide - Zuplo](https://zuplo.com/learning-center/agent-to-agent-a2a-protocol-guide) — 最佳技术概述
- [Red Hat: Enhance A2A Security](https://developers.redhat.com/articles/2025/08/19/how-enhance-agent2agent-security) — 认证授权详解
- [Palo Alto: A2A Security Guide](https://live.paloaltonetworks.com/t5/community-blogs/safeguarding-ai-agents-an-in-depth-look-at-a2a-protocol-risks/ba-p/1235996) — 攻击面分析
- [AgentGraph Trust Scoring - GitHub Discussion](https://github.com/a2aproject/A2A/discussions/1720) — 签名证明模式
- [arxiv:2504.16902](https://arxiv.org/html/2504.16902v1) — 学术安全分析
- [Mike Prince - DID Auth Hooks](https://www.linkedin.com/posts/mike-prince-7713_ive-been-heads-down-the-last-six-weeks-on-activity-7363011367127171072-gdjT) — JS SDK 认证集成
