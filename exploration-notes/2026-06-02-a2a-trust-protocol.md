# 研究笔记：A2A Trust Protocol — 从签名中间件到去中心化信任

> 日期：2026-06-02 (晚) | 方法论：autoresearch | 状态：✅ 完成
> 前序：lab/a2a-trust-prototype 已有基础框架 (crypto + trust-engine + agent-card + middleware)
> 关联项目：openclaw-langgraph-bridge (Supervisor 多 agent 场景需要信任层)

---

## 核心概念

### 1. Signed Agent Cards（签名代理卡）
A2A v1.0 引入了 Signed Agent Cards — 代理身份的密码学证明。每个 agent 发布 `/.well-known/agent.json`，包含能力声明和认证要求，用 ES256 签名保证不可篡改。这是 A2A 信任链的起点：**没有可验证的身份，就没有可建立的信任**。

### 2. Trust Score 动态评分
信任不是二元的（信任/不信任），而是连续的 0-100 分数，随时间和交互历史演化：
- **正向证据**：成功完成任务、按时响应、输出质量高
- **负向证据**：任务失败、超时、schema 违规、被拒绝
- **时间衰减**：exp(-λ·Δt)，确保旧证据权重逐渐降低
- **Per-Skill 粒度**：同一 agent 可能在 "代码生成" 方面可信但在 "金融分析" 方面不可信

### 3. Verification Sandwich（验证三明治）
与结构化输出的模式类似，A2A 安全也需要三层验证：
- **Layer 1 — 密码学验证**：ES256 签名确认 agent card 未被篡改
- **Layer 2 — 协议验证**：JSON-RPC 2.0 schema 合规 + nonce 防重放
- **Layer 3 — 业务验证**：Trust Score 是否达标 + skill 权限检查

### 4. Zero-Trust Agent Networking
A2A 采用零信任原则：**每个请求都验证，不因 "之前可信" 而跳过验证**。这反映在：
- 每个 task 包含 nonce + timestamp + MAC
- Agent Card 定期重新验证（不只是首次）
- 信任衰减确保长期不活跃的 agent 不会保留高权限

### 5. Verifiable Credentials (VC) + DID 集成路线
arXiv 论文 (2511.02841) 提出了用 DIDs + Verifiable Credentials 增强 A2A 的方案：
- Agent 持有 DID 作为去中心化身份
- 通过 Verifiable Credential 证明特定能力（如"通过安全审计"）
- 使用 DIF Presentation Exchange 在 A2A 握手阶段交换 VPs
- 这是从企业级 OAuth → 去中心化信任的自然演进路径

---

## 可运行代码示例

### ES256 Agent Card 签名 + 验证 + Trust Score 计算

```typescript
// a2a-trust-demo.ts — 零依赖，纯 Node.js crypto
import { generateKeyPairSync, sign, verify, createHash } from 'node:crypto';

// === 1. ES256 Key Generation ===
function generateES256KeyPair() {
  const { publicKey, privateKey } = generateKeyPairSync('ec', {
    namedCurve: 'P-256',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
  return { publicKey, privateKey };
}

// === 2. Agent Card 定义 ===
interface AgentCard {
  id: string;              // agent DID or UUID
  name: string;
  skills: string[];
  publicKeyPem: string;    // 用于验证签名
  issuedAt: number;        // Unix timestamp
  expiresAt: number;
}

// === 3. JCS Canonicalization + 签名 ===
function canonicalize(obj: Record<string, unknown>): string {
  // RFC 8785 (JCS) simplified: sorted keys, no whitespace
  if (obj === null || typeof obj !== 'object') return JSON.stringify(obj);
  if (Array.isArray(obj)) return '[' + obj.map(canonicalize).join(',') + ']';
  const keys = Object.keys(obj).sort();
  return '{' + keys.map(k => JSON.stringify(k) + ':' + canonicalize(obj[k] as any)).join(',') + '}';
}

function signAgentCard(card: AgentCard, privateKey: string): string {
  const canonical = canonicalize(card as any);
  const sig = sign('sha256', Buffer.from(canonical), privateKey);
  return sig.toString('base64url');
}

function verifyAgentCard(card: AgentCard, signature: string, publicKey: string): boolean {
  const canonical = canonicalize(card as any);
  return verify('sha256', Buffer.from(canonical), publicKey, Buffer.from(signature, 'base64url'));
}

// === 4. Trust Score Engine ===
interface TrustEvent {
  agentId: string;
  skill: string;
  outcome: 'success' | 'failure' | 'timeout';
  timestamp: number;
  weight: number;  // 事件权重
}

class TrustEngine {
  private scores = new Map<string, Map<string, number>>(); // agentId → skill → score
  private decayFactor = 0.001; // 衰减速率

  recordEvent(event: TrustEvent): number {
    const key = event.agentId;
    if (!this.scores.has(key)) this.scores.set(key, new Map());
    const skillScores = this.scores.get(key)!;

    const currentScore = skillScores.get(event.skill) ?? 50; // 起始 50 (neutral)
    const delta = event.outcome === 'success' ? 5 * event.weight
               : event.outcome === 'failure' ? -10 * event.weight
               : -3 * event.weight; // timeout

    // 时间衰减
    const ageHours = (Date.now() - event.timestamp) / 3600000;
    const decayMultiplier = Math.exp(-this.decayFactor * ageHours);

    const newScore = Math.max(0, Math.min(100,
      currentScore * decayMultiplier + delta
    ));
    skillScores.set(event.skill, newScore);
    return newScore;
  }

  getTrustLevel(score: number): 'untrusted' | 'neutral' | 'trusted' {
    if (score < 50) return 'untrusted';
    if (score < 80) return 'neutral';
    return 'trusted';
  }

  isTrustedFor(agentId: string, skill: string, threshold = 80): boolean {
    const score = this.scores.get(agentId)?.get(skill) ?? 50;
    return score >= threshold;
  }
}

// === 5. 完整流程演示 ===
const { publicKey, privateKey } = generateES256KeyPair();

const agentCard: AgentCard = {
  id: 'agent://research-assistant-v2',
  name: 'Research Assistant',
  skills: ['web-search', 'summarization', 'code-analysis'],
  publicKeyPem: publicKey,
  issuedAt: Math.floor(Date.now() / 1000),
  expiresAt: Math.floor(Date.now() / 1000) + 86400 * 90, // 90 天
};

// 签名
const signature = signAgentCard(agentCard, privateKey);
console.log('✅ Agent Card signed:', signature.slice(0, 40) + '...');

// 验证
const isValid = verifyAgentCard(agentCard, signature, publicKey);
console.log('✅ Signature valid:', isValid);

// Trust Score 演进
const engine = new TrustEngine();
const agentId = agentCard.id;

// 模拟 10 次交互
const events: TrustEvent[] = [
  { agentId, skill: 'web-search', outcome: 'success', timestamp: Date.now(), weight: 1 },
  { agentId, skill: 'web-search', outcome: 'success', timestamp: Date.now(), weight: 1 },
  { agentId, skill: 'summarization', outcome: 'failure', timestamp: Date.now(), weight: 1 },
  { agentId, skill: 'web-search', outcome: 'success', timestamp: Date.now(), weight: 1.5 },
  { agentId, skill: 'code-analysis', outcome: 'success', timestamp: Date.now(), weight: 2 },
  { agentId, skill: 'summarization', outcome: 'success', timestamp: Date.now(), weight: 1 },
  { agentId, skill: 'summarization', outcome: 'success', timestamp: Date.now(), weight: 1 },
  { agentId, skill: 'web-search', outcome: 'timeout', timestamp: Date.now(), weight: 0.5 },
  { agentId, skill: 'code-analysis', outcome: 'success', timestamp: Date.now(), weight: 1 },
  { agentId, skill: 'summarization', outcome: 'success', timestamp: Date.now(), weight: 1 },
];

for (const event of events) {
  const score = engine.recordEvent(event);
  console.log(`  ${event.skill}: ${event.outcome} → score=${score.toFixed(1)} (${engine.getTrustLevel(score)})`);
}

// 最终信任检查
console.log('\n🔒 Trust Gate Results:');
for (const skill of agentCard.skills) {
  const trusted = engine.isTrustedFor(agentId, skill);
  console.log(`  ${skill}: ${trusted ? '✅ TRUSTED' : '❌ NOT TRUSTED'}`);
}

// 运行: npx tsx a2a-trust-demo.ts
```

### 信任中间件模式（Express 风格）

```typescript
// 信任中间件 — 嵌入到 A2A JSON-RPC handler
function trustMiddleware(engine: TrustEngine, requiredSkill: string, threshold = 80) {
  return async (req: { agentCard: AgentCard; signature: string }, next: () => void) => {
    // Layer 1: 密码学验证
    const isValid = verifyAgentCard(req.agentCard, req.signature, req.agentCard.publicKeyPem);
    if (!isValid) throw new Error('UNAUTHORIZED: Invalid agent card signature');

    // Layer 2: 过期检查
    if (req.agentCard.expiresAt < Date.now() / 1000) {
      throw new Error('UNAUTHORIZED: Agent card expired');
    }

    // Layer 3: Trust Score 门控
    if (!engine.isTrustedFor(req.agentCard.id, requiredSkill, threshold)) {
      const score = engine.scores.get(req.agentCard.id)?.get(requiredSkill) ?? 50;
      throw new Error(`FORBIDDEN: Trust score ${score} < ${threshold} for skill "${requiredSkill}"`);
    }

    // 通过所有层
    return next();
  };
}
```

---

## 关键洞察

### 洞察 1：A2A 的信任模型是 "Trust but Verify" 的升级版 → "Never Trust, Always Verify"
传统网络信任（TLS证书、OAuth token）依赖 CA 或 IdP 的集中式信任锚。A2A v1.0 的 Signed Agent Cards 走向了去中心化：每个 agent 自己签发身份，但需要通过 **Verifiable Credentials** 由第三方背书。这意味着我们的 a2a-trust-prototype 需要支持一个 "Credential Issuer" 角色——不只是自签名，还要能接受和验证第三方签发的 trust credentials。

### 洞察 2：Trust Score 的核心挑战不是算法，而是 **证据来源**
Trust Score 计算本身很简单（加权累积 + 指数衰减），难点在于：谁提供证据？如何防止 Sybil 攻击（一个恶意 agent 伪造大量成功交互）？解决方案：**证据也需要签名**——每次交互的 outcome 应该由双方签名记录，形成不可抵赖的审计日志。这直接关联到我们的 agent-context-store（事务语义 + snapshot）。

### 洞察 3：a2a-trust-prototype 的差异化价值在于 **per-skill 粒度**
现有的 A2A SDK 关注的是协议层（发现、认证、任务交换），几乎没有现成的 trust scoring 实现。我们的 prototype 提供 per-skill 信任评分 + 时间衰减 + 中间件集成，这在 openclaw-langgraph-bridge 的 Supervisor 模式中有直接应用场景：Supervisor 需要决定把子任务委托给哪个 agent，Trust Score 就是路由决策的核心输入。

### 洞察 4：Agent Name Service (ANS) 是 A2A 信任的基础设施
GoDaddy 提出的 ANS（Agent Name Service）类似 DNS 但用于 agent——提供可验证的 agent 发现和身份解析。A2A 解决通信，MCP 解决工具访问，ANS 解决发现和信任锚。这三者组合构成完整的 agent 网络栈。我们的 prototype 可以预留 ANS 集成接口。

### 洞察 5：Trust Score 应该是 **双向的**
当前 prototype 只记录 caller 对 callee 的信任。但 A2A 是双向通信——callee 也需要评估是否信任 caller（防止恶意 agent 滥用能力）。下一步：为 TrustEngine 添加 `双向评分`，每个 agent 维护对其他 agent 的信任视图。

---

## 下一步行动

### Action 1：完善 a2a-trust-prototype 的 V1 功能
当前 lab 已有 crypto + trust-engine + agent-card + middleware 骨架。需要补全：
- [ ] Trust event 的密码学签名（双方签名防 Sybil）
- [ ] Bidirectional trust（双向评分）
- [ ] Trust report 导出（接入 agent-memory-graph 的 snapshot）
- [ ] A2A JSON-RPC handler 集成示例

### Action 2：与 openclaw-langgraph-bridge Supervisor 集成
在 Supervisor 的路由决策中引入 Trust Score：
```typescript
// Supervisor routing with trust
const trustedAgents = agents.filter(a => trustEngine.isTrustedFor(a.id, task.skill));
if (trustedAgents.length === 0) throw new Error('No trusted agent for skill: ' + task.skill);
const selected = selectByScore(trustedAgents, task.skill);
```

### Action 3：研究 VC/DID 集成路线
阅读 arXiv 2511.02841 的完整实现，评估是否在 prototype 中加入 Verifiable Credential 验证层。

---

## 参考资料

1. **A2A Protocol v1.0 Spec** — Linux Foundation, April 2026. 150+ organizations, Signed Agent Cards, AP2 payments.
2. **"Building A Secure Agentic AI Application Leveraging Google's A2A Protocol"** — arXiv:2504.16902. Security patterns: nonce防重放, schema验证, Agent Card安全.
3. **"AI Agents with Decentralized Identifiers and Verifiable Credentials"** — arXiv:2511.02841. DID + VC + A2A 集成方案.
4. **Agent Name Service (ANS) Proposal** — GoDaddy, DNS-based agent discovery + Web PKI.
5. **Node.js Crypto ES256** — `generateKeyPairSync('ec', { namedCurve: 'P-256' })`, RFC 7518 ES256 = ECDSA P-256 + SHA-256.

---

## 笔记质量自评

| 维度 | 评分 | 说明 |
|------|------|------|
| 可运行代码 | ✅ 达标 | 完整的 ES256 签名+验证+Trust Score 演示，零依赖 |
| 独到见解 | ✅ 达标 | 5 条洞察覆盖信任模型演进、Sybil 防御、双向信任、ANS 集成 |
| 项目关联 | ✅ 达标 | 直连 a2a-trust-prototype + langgraph-bridge + agent-context-store |
| 可操作性 | ✅ 达标 | 3 条明确下一步，附代码片段 |
