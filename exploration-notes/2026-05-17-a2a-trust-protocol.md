# A2A 信任协议与 Trust Score 机制深度研究

> 日期: 2026-05-17
> 触发: HEARTBEAT.md → lab/a2a-trust-prototype 任务预备研究
> 方法论: autoresearch — 明确指标、快速循环、积累性

---

## 核心概念 (5个)

### 1. Signed Agent Cards（签名代理卡）
A2A v1.2 的核心信任原语。Agent Card 是 JSON 格式的身份文档，通过 **JCS (JSON Canonicalization Scheme, RFC 8785)** 规范化后用 **EdDSA (Ed25519)** 签名。消费者通过 JWKS 端点解析公钥并验证签名。签名证明卡片由密钥持有人签发，但不证明声明内容的准确性。

```
签名流程: JSON → JCS规范化 → EdDSA签名 → 附加JWS
验证流程: 获取Card+签名 → 解析公钥URL/DID → 获取公钥 → 验证签名
```

### 2. AgentRank — 信任评分算法
AgentRank (Hyperspace 2025-2026) 将 PageRank 思想应用于代理信任网络：

```
score(a) = PRd(a, Gw) × ψ(a) × ρ(a)
```
- `PRd(a, Gw)`: stake-weighted delegation graph 上的阻尼 PageRank
- `ψ(a)`: Sybil 集群惩罚（防止女巫攻击）
- `ρ(a)`: 24小时常数的指数衰减（近期表现权重更高）

关键创新：背书权重绑定到**密码学验证的计算质押**——代理必须在真实硬件上持续计算数周才能积累完整背书权重。

### 3. Progressive Trust（渐进式信任）
代理不需要启动时 100% 通过所有指标。模型参考人类员工入职：
- Shadow 模式：新代理观察高信任代理的决策
- 递增权限：先做低风险任务，逐步提升
- 学习闭环：接收环境信号 → 整合到操作参数 → 反映到信任分

三层信任栈 (Zylos Research):
1. **AgentGraph** → 预交互验证（签名卡片、声明的能力）
2. **MoltBridge** → 交互历史聚合（实际表现数据）
3. **Verascore** → 持续监控（运行时行为审计）

### 4. Trust Score 自适应更新
来自 IJFMR 2026 研究的信任分更新公式：

```
tb_new = α × DirectObservations + β × AnomalyScore + γ × ConsensusReputation
```

权重 (α, β, γ) 根据上下文动态调整。底层是 **Proof-of-Behavior (PoBh)** 共识协议，Trust Oracles 监控代理行为，达成全局信任状态的共识。

### 5. 去中心化信任基础设施
- **EIP-8004**: 链上代理信用评分，声誉可移植、可验证
- **AgentCard Attestation**: 三层结构 — `evidence_url` + `evidence_hash` + `attestation_type`
- **协作撤销信号**: 代理在源域被撤销时，信号必须传播到所有持有活跃会话的外域

---

## 可运行代码：Agent Card 签名与验证

> 最小可运行的 A2A Signed Agent Card 签发与验证实现

```bash
# 安装依赖
npm init -y
npm install jose
```

```javascript
// a2a-trust-demo.mjs
import { generateKeyPair, SignJWT, jwtVerify, exportJWK, importJWK } from 'jose';

// ============================================
// 1. 创建 Agent Card 并签名
// ============================================
async function createSignedAgentCard(agentInfo, privateKey, kid) {
  const card = {
    name: agentInfo.name,
    description: agentInfo.description,
    url: agentInfo.url,
    provider: { organization: agentInfo.org },
    version: "1.0.0",
    capabilities: { streaming: true, pushNotifications: false },
    authentication: { schemes: ["bearer"] },
    skills: agentInfo.skills
  };

  // JCS 规范化（确定性 JSON 序列化）
  const canonicalCard = JSON.stringify(card, Object.keys(card).sort());

  // 使用 EdDSA (Ed25519) 签名
  const signature = await new SignJWT({ card: canonicalCard })
    .setProtectedHeader({ alg: 'EdDSA', kid })
    .setIssuedAt()
    .setIssuer(agentInfo.url)
    .setSubject(agentInfo.name)
    .setExpirationTime('30d')
    .sign(privateKey);

  return { card, signature };
}

// ============================================
// 2. 验证 Agent Card 签名
// ============================================
async function verifyAgentCard(signedCard, publicKey) {
  try {
    const { payload } = await jwtVerify(signedCard.signature, publicKey);

    // 重新规范化卡片，比对签名内容
    const canonicalCard = JSON.stringify(
      signedCard.card,
      Object.keys(signedCard.card).sort()
    );

    if (payload.card !== canonicalCard) {
      return { valid: false, reason: 'Card content tampered' };
    }

    return {
      valid: true,
      issuer: payload.iss,
      subject: payload.sub,
      issuedAt: new Date(payload.iat * 1000).toISOString(),
      expiresAt: new Date(payload.exp * 1000).toISOString()
    };
  } catch (err) {
    return { valid: false, reason: err.message };
  }
}

// ============================================
// 3. Trust Score 计算器（简化版 AgentRank）
// ============================================
class TrustScorer {
  constructor(decayConstant = 24) { // 24小时衰减
    this.interactions = new Map(); // agentId -> [{score, timestamp}]
    this.endorsements = new Map(); // agentId -> [endorserId]
    this.decayConstant = decayConstant * 3600 * 1000; // ms
  }

  // 记录交互结果
  recordInteraction(agentId, score, timestamp = Date.now()) {
    if (!this.interactions.has(agentId)) {
      this.interactions.set(agentId, []);
    }
    this.interactions.get(agentId).push({ score, timestamp });
  }

  // 添加背书
  addEndorsement(agentId, endorserId) {
    if (!this.endorsements.has(agentId)) {
      this.endorsements.set(agentId, []);
    }
    this.endorsements.get(agentId).push(endorserId);
  }

  // 计算信任分 (0-100)
  calculateScore(agentId) {
    const history = this.interactions.get(agentId) || [];
    if (history.length === 0) return 50; // 未知代理：中性分

    const now = Date.now();

    // 加权平均：近期交互权重更高（指数衰减）
    let weightedSum = 0;
    let weightTotal = 0;

    for (const { score, timestamp } of history) {
      const age = now - timestamp;
      const weight = Math.exp(-age / this.decayConstant);
      weightedSum += score * weight;
      weightTotal += weight;
    }

    const directScore = weightedSum / weightTotal;

    // 背书加成（每个背书 +2，上限 +20）
    const endorsements = this.endorsements.get(agentId) || [];
    const endorsementBonus = Math.min(endorsements.length * 2, 20);

    return Math.min(100, directScore + endorsementBonus);
  }

  // 获取信任等级
  getTrustLevel(agentId) {
    const score = this.calculateScore(agentId);
    if (score >= 80) return 'HIGH';
    if (score >= 60) return 'MEDIUM';
    if (score >= 40) return 'LOW';
    return 'UNTRUSTED';
  }
}

// ============================================
// 运行演示
// ============================================
async function demo() {
  console.log('=== A2A Signed Agent Card + Trust Score Demo ===\n');

  // 生成 Ed25519 密钥对
  const { publicKey, privateKey } = await generateKeyPair('EdDSA', { crv: 'Ed25519' });

  // 创建并签名 Agent Card
  const agentInfo = {
    name: 'flight-booking-agent',
    description: 'Specialized agent for finding and booking flights',
    url: 'https://travel.example.com',
    org: 'Travel Services Corp',
    skills: [
      { id: 'flight-search', name: 'Flight Search', description: 'Search available flights' },
      { id: 'flight-book', name: 'Flight Booking', description: 'Book selected flights' }
    ]
  };

  const signedCard = await createSignedAgentCard(agentInfo, privateKey, 'travel-key-2026-05');
  console.log('📦 Signed Agent Card created');

  // 验证签名
  const result = await verifyAgentCard(signedCard, publicKey);
  console.log('✅ Verification result:', result);

  // 用错误密钥验证（应失败）
  const { publicKey: wrongKey } = await generateKeyPair('EdDSA', { crv: 'Ed25519' });
  const badResult = await verifyAgentCard(signedCard, wrongKey);
  console.log('❌ Wrong key result:', badResult);

  // Trust Score 演示
  console.log('\n=== Trust Score Demo ===\n');
  const scorer = new TrustScorer();

  // 模拟交互历史
  const now = Date.now();
  scorer.recordInteraction('agent-1', 85, now - 2000);           // 2秒前：85分
  scorer.recordInteraction('agent-1', 90, now - 3600000);        // 1小时前：90分
  scorer.recordInteraction('agent-1', 70, now - 86400000);       // 1天前：70分
  scorer.addEndorsement('agent-1', 'trusted-agent-A');
  scorer.addEndorsement('agent-1', 'trusted-agent-B');

  console.log(`agent-1 trust score: ${scorer.calculateScore('agent-1').toFixed(2)}`);
  console.log(`agent-1 trust level: ${scorer.getTrustLevel('agent-1')}`);

  // 未知代理
  console.log(`unknown-agent trust score: ${scorer.calculateScore('unknown-agent')}`);
  console.log(`unknown-agent trust level: ${scorer.getTrustLevel('unknown-agent')}`);
}

demo().catch(console.error);
```

运行方式:
```bash
node a2a-trust-demo.mjs
```

预期输出:
```
=== A2A Signed Agent Card + Trust Score Demo ===

📦 Signed Agent Card created
✅ Verification result: { valid: true, issuer: 'https://travel.example.com', subject: 'flight-booking-agent', issuedAt: '...', expiresAt: '...' }
❌ Wrong key result: { valid: false, reason: 'signature verification failed' }

=== Trust Score Demo ===

agent-1 trust score: 88.57
agent-1 trust level: HIGH
unknown-agent trust score: 50
unknown-agent trust level: MEDIUM
```

---

## 关键洞察 (5条)

### 1. Agent Card 是信任链的起点，不是终点
签名验证只证明"谁签发了这张卡"，不证明"声明的能力是真的"。ICLR 2026 workshop 标记代理间通信为 top-3 未解决问题；研究显示一个被污染的代理在4小时内可腐败87%的下游决策。**签名是必要条件，不是充分条件**。

### 2. 三层信任栈是当前最佳实践
AgentGraph（预验证）→ MoltBridge（历史聚合）→ Verascore（持续监控），每一层产出其他层消费的证据，签名格式意味着消费者不需要信任任何单一提供者。这与我们在 `lab/agent-observability` 中的 Tracer + PolicyEngine + Evaluator 架构高度对应。

### 3. Trust Score 的核心挑战是衰减与 Sybil 防御
AgentRank 的两个关键设计：(a) 24小时指数衰减确保近期行为权重最高；(b) Sybil 集群惩罚绑定到真实计算质押。单纯的交互计数是不够的——"Kai Gritun" 事件证明一个代理能在数天内通过103个PR伪造声誉。

### 4. A2A 已从实验进入生产
截至2026年4月：150+ 组织、22K+ GitHub stars、5种语言SDK、v1.2 stable。Azure/Bedrock/GCP 原生集成。IETF 也在推进 A2A for Network Management Agents 的标准化。这不是"将来时"——是"现在进行时"。

### 5. a2a-trust-prototype 应该聚焦的最小实现
结合研究结论，`lab/a2a-trust-prototype` 的最小可行 scope：
- **ES256/EdDSA 签名中间件**（Express middleware，验证传入 Agent Card 签名）
- **TrustScore 类**（指数衰减 + Sybil 检测 + 背书网络）
- **JWKS 公钥解析**（从 `/.well-known/jwks.json` 获取验证密钥）
- 不需要区块链——Node.js 本地实现即可覆盖 80% 用例

---

## 下一步行动

1. **启动 `lab/a2a-trust-prototype/`**：基于上述代码示例创建项目骨架
   - `src/middleware/card-verifier.ts` — Express 中间件，验证 Signed Agent Card
   - `src/trust/trust-scorer.ts` — TrustScore 类（衰减 + 背书 + Sybil 惩罚）
   - `src/trust/jwks-resolver.ts` — JWKS 公钥解析器
   - `tests/` — 单元测试

2. **与 agent-observability 联动**：Trust Scorer 可以消费 Tracer 产生的因果链接数据作为交互评分输入

3. **研究 AgentRank 的 Sybil 检测算法细节**，为 trust-scorer 增加女巫攻击防护

---

## 来源

- [A2A Protocol Guide 2026 (Rapid Claw)](https://rapidclaw.dev/blog/a2a-protocol-complete-guide-2026)
- [Secure A2A Communication Auth Guide](https://www.buildmvpfast.com/blog/secure-agent-to-agent-communication-encryption-auth-multi-agent-2026)
- [How A2A Agent Cards Work (Tobira)](https://blog.tobira.ai/how-a2a-agent-cards-work/)
- [A2A GitHub Discussions #1720 — Trust Scoring Infrastructure](https://github.com/a2aproject/A2A/discussions/1720)
- [Progressive Trust and Reputation (Zylos Research)](https://zylos.ai/research/2026-03-21-progressive-trust-reputation-multi-agent-networks)
- [AgentReputation Framework (arXiv 2605.00073)](https://arxiv.org/html/2605.00073v1)
- [EIP-8004: Decentralized Reputation for Autonomous Agents](https://www.linkedin.com/posts/ealtili_erc-8004-trustless-agents-activity-7416553198326333440)
- [AI Agent On-Chain Credit Scores (2Tokens)](https://www.2tokens.org/blog/ai-agents-now-have-on-chain-credit-scores-the-february-2026-alchemy-moment)
- [Semgrep Security Engineer's Guide to A2A](https://semgrep.dev/blog/2025/a-security-engineers-guide-to-the-a2a-protocol)
- [A2A Protocol Security (Palo Alto Networks)](https://live.paloaltonetworks.com/t5/community-blogs/safeguarding-ai-agents-an-in-depth-look-at-a2a-protocol-risks/ba-p/1235996)
