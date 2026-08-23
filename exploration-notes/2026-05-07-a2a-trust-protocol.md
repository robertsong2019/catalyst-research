# A2A Protocol Trust & Signed Agent Cards 深度研究

> 日期: 2026-05-07 | 服务项目: lab/a2a-trust-prototype/ | 版本: A2A v1.2 (current stable)

## 核心概念

### 1. Agent Card — Agent 的"数字身份证"
- JSON 文档，发布在 `/.well-known/agent-card.json`
- 五大字段组：identity(身份)、skills(技能)、capabilities(能力)、modes(模式)、security(安全)
- 支持 `signatures` 字段附加 JWS 签名，证明卡片由密钥持有者签发
- v1.0 引入 Signed Agent Cards，v1.2 为当前稳定版

### 2. JWS 签名流程 (ES256)
- 算法：ES256 (ECDSA over P-256 with SHA-256)，也支持 RS256、EdDSA/Ed25519
- 签名格式遵循 RFC 7515 (JWS)，使用 detached payload 模式
- 关键步骤：
  1. 从 Agent Card 中移除 `signatures` 字段
  2. 移除默认值的属性
  3. 使用 **RFC 8785 (JSON Canonicalization Scheme)** 规范化 JSON
  4. 对规范化后的 payload 生成 ES256 签名
  5. 将签名附加回 Agent Card 的 `signatures` 数组

### 3. 三层信任模型
```
Layer 1: Transport — HTTPS + TLS 1.3 (加密传输)
Layer 2: Identity  — JWS Signed Agent Card (身份验证)
Layer 3: Policy    — OAuth 2.0 / RBAC / Trust Score (授权控制)
```

### 4. 验证流程
1. 获取 Agent Card
2. 提取 `signatures` 数组中的签名
3. Base64url 解码 `protected` header → 获取 `kid` + `jku`
4. 从 `jku` (JWKS endpoint) 获取公钥
5. 规范化 payload (RFC 8785)
6. 用公钥验证签名
7. （可选）检查 identity constraints：签名者是否来自可信仓库/工作流

### 5. 安全威胁与缓解（来自学术研究 arXiv:2505.12490）
- Prompt Injection in Agent Cards：恶意描述字段可注入指令
- Task Replay：需 nonce + timestamp + MAC 三重防护
- 数据泄漏：baseline A2A 在注入攻击下 60-100% 泄漏率
- OAuth scope 粒度过粗：违反最小权限原则

## 可运行代码：ES256 Agent Card 签名 & 验证

```javascript
// a2a-trust-demo.mjs — Node.js ES256 Agent Card 签名与验证
// 运行: node a2a-trust-demo.mjs (需要 Node.js 18+，无外部依赖)

import { createSign, createVerify, randomBytes } from 'node:crypto';

// ============================================================
// 1. 生成 EC P-256 密钥对（生产环境应从 vault/KMS 加载）
// ============================================================
function generateKeyPair() {
  const { publicKey, privateKey } = crypto.generateKeyPairSync('ec', {
    namedCurve: 'P-256',
  });
  return { publicKey, privateKey };
}

// 注意: Node 18+ 直接支持 generateKeyPairSync，这里用动态导入兼容
const crypto = await import('node:crypto');

function makeP256Keys() {
  return crypto.generateKeyPairSync('ec', { namedCurve: 'P-256' });
}

// ============================================================
// 2. RFC 8785 JSON Canonicalization（简化实现）
//    生产环境建议使用 rfc8785 npm 包
// ============================================================
function canonicalizeJSON(obj) {
  // RFC 8785 核心: 按 UTF-16 code unit 排序 key，递归处理
  function serialize(value) {
    if (value === null) return 'null';
    if (value === true) return 'true';
    if (value === false) return 'false';
    if (typeof value === 'number') return JSON.stringify(value);
    if (typeof value === 'string') return JSON.stringify(value);
    if (Array.isArray(value)) {
      return '[' + value.map(serialize).join(',') + ']';
    }
    if (typeof value === 'object') {
      const keys = Object.keys(value).sort((a, b) => {
        // RFC 8785 排序: 按 UTF-16 code unit 比较
        const aLen = a.length, bLen = b.length;
        for (let i = 0; i < Math.min(aLen, bLen); i++) {
          if (a.charCodeAt(i) !== b.charCodeAt(i)) {
            return a.charCodeAt(i) - b.charCodeAt(i);
          }
        }
        return aLen - bLen;
      });
      return '{' + keys.map(k => JSON.stringify(k) + ':' + serialize(value[k])).join(',') + '}';
    }
    return 'null';
  }
  return serialize(obj);
}

// ============================================================
// 3. Base64url 编解码
// ============================================================
const b64url = {
  encode: (buf) => buf.toString('base64url'),
  decode: (str) => Buffer.from(str, 'base64url'),
};

// ============================================================
// 4. 签名 Agent Card
// ============================================================
function signAgentCard(agentCard, privateKey, kid, jku) {
  // Step 1: 构造 JWS Protected Header
  const header = { alg: 'ES256', typ: 'JOSE', kid };
  if (jku) header.jku = jku;

  const protectedB64 = b64url.encode(Buffer.from(JSON.stringify(header)));

  // Step 2: 规范化 payload（移除 signatures 字段后）
  const { signatures, ...payload } = agentCard;
  const canonicalPayload = canonicalizeJSON(payload);

  // Step 3: 签名（JWS Detached: header.payload 作为签名输入）
  const signInput = `${protectedB64}.${b64url.encode(Buffer.from(canonicalPayload))}`;
  const sig = crypto.createSign('SHA256')
    .update(signInput)
    .sign(privateKey);

  return {
    ...agentCard,
    signatures: [{
      protected: protectedB64,
      signature: b64url.encode(sig),
    }],
  };
}

// ============================================================
// 5. 验证 Agent Card 签名
// ============================================================
function verifyAgentCard(signedCard, publicKey) {
  const sigs = signedCard.signatures;
  if (!sigs || sigs.length === 0) return { valid: false, reason: 'no signatures' };

  for (const sig of sigs) {
    // 解码 header
    const header = JSON.parse(b64url.decode(sig.protected).toString());
    if (header.alg !== 'ES256') continue;

    // 规范化 payload（排除 signatures）
    const { signatures, ...payload } = signedCard;
    const canonicalPayload = canonicalizeJSON(payload);

    // 重构签名输入
    const signInput = `${sig.protected}.${b64url.encode(Buffer.from(canonicalPayload))}`;

    // 验证
    const valid = crypto.createVerify('SHA256')
      .update(signInput)
      .verify(publicKey, b64url.decode(sig.signature));

    if (valid) return { valid: true, kid: header.kid, jku: header.jku };
  }
  return { valid: false, reason: 'no valid signature' };
}

// ============================================================
// 6. Trust Score 计算（三层加权模型）
// ============================================================
function computeTrustScore(card, verificationResult, policyCheck = {}) {
  let score = 0;

  // Layer 1: Transport (25%) — HTTPS 是否启用
  const url = card.url || '';
  score += url.startsWith('https://') ? 25 : 0;

  // Layer 2: Identity (40%) — 签名验证
  score += verificationResult.valid ? 40 : 0;

  // Layer 3: Policy (35%)
  const { hasOAuth, hasRBAC, hasNonce } = policyCheck;
  if (hasOAuth) score += 15;
  if (hasRBAC) score += 10;
  if (hasNonce) score += 10;

  return { score, level: score >= 80 ? 'HIGH' : score >= 50 ? 'MEDIUM' : 'LOW' };
}

// ============================================================
// 🧪 DEMO: 完整签名-验证-信任评分流程
// ============================================================
const { publicKey, privateKey } = makeP256Keys();

const agentCard = {
  name: 'Catalyst Research Agent',
  description: 'Deep tech research agent with A2A trust',
  url: 'https://catalyst.example.com/a2a',
  version: '1.0.0',
  capabilities: { streaming: true, pushNotifications: false },
  defaultInputModes: ['text/plain'],
  defaultOutputModes: ['text/plain'],
  skills: [{
    id: 'deep-research',
    name: 'Deep Research',
    description: 'Execute multi-source deep research with structured output',
    tags: ['research', 'analysis'],
  }],
  securitySchemes: {
    oauth2: { type: 'oauth2', flows: { clientCredentials: { tokenUrl: 'https://auth.example.com/token' } } }
  },
};

console.log('=== A2A Agent Card Trust Demo ===\n');

// 签名
const signed = signAgentCard(agentCard, privateKey, 'key-2026-05', 'https://catalyst.example.com/jwks.json');
console.log('✅ Signed Agent Card:');
console.log(`   Protected Header: ${signed.signatures[0].protected}`);
console.log(`   Signature: ${signed.signatures[0].signature.slice(0, 32)}...`);
console.log();

// 验证
const result = verifyAgentCard(signed, publicKey);
console.log(`🔍 Verification: ${result.valid ? 'VALID ✅' : 'INVALID ❌'} (kid: ${result.kid})`);
console.log();

// 信任评分
const trust = computeTrustScore(signed, result, { hasOAuth: true, hasRBAC: false, hasNonce: true });
console.log(`🛡️ Trust Score: ${trust.score}/100 (${trust.level})`);
console.log();

// 篡改检测
console.log('--- Tamper Detection Test ---');
const tampered = JSON.parse(JSON.stringify(signed));
tampered.description = 'MALICIOUS AGENT - modified!';
const tamperResult = verifyAgentCard(tampered, publicKey);
console.log(`🔍 Tampered Card: ${tamperResult.valid ? 'VALID ✅' : 'INVALID ❌'} (expected: INVALID)`);
```

## 关键洞察

### 洞察 1: A2A 已从实验走向生产标准
- 2025年4月 Google 发布 → 6月捐赠 Linux Foundation → 2026年4月 v1.0 正式版
- 150+ 组织支持，AWS/Google/Microsoft 三大云平台集成
- **对 OpenClaw 的意义**: a2a-trust-prototype 应基于 v1.2 spec，聚焦 Signed Agent Cards + Trust Score

### 洞察 2: 签名不是信任，只是身份证明
- Signed Agent Card 只证明"这张卡由某个密钥持有者签发"，**不证明其声明内容真实**
- 信任需要额外层：identity constraints（来自哪个仓库/CI？）、reputation score、policy enforcement
- **对 a2a-trust-prototype 的启发**: Trust Score 计算不应只看签名有效性，还需考虑来源可信度、历史行为

### 洞察 3: Node.js 生态已成熟
- 官方 JS SDK: `a2aproject/a2a-js` (npm: `a2a-sdk`)
- Strands Agents SDK 内置 A2A 支持 (`@strands-agents/sdk`)
- 签名可用 Node.js 内置 crypto 模块（EC P-256），无需外部依赖
- **行动**: lab/a2a-trust-prototype 可直接用 `node:crypto` 实现 ES256，无需 jose 库

### 洞察 4: 安全研究已发现严重漏洞
- arXiv:2505.12490 发现 baseline A2A 在 prompt injection 下 60-100% 数据泄漏率
- Agent Card description 字段是主要攻击面（可以嵌入隐藏指令）
- **缓解方案**: 签名验证 + 内容审计（检测 Card 中的可疑指令模式）

### 洞察 5: A2A + MCP 互补，不是替代
- A2A = agent ↔ agent（水平通信）
- MCP = agent ↔ tools（垂直连接）
- Google 参考架构：每个 A2A agent 同时是 MCP client
- **对 OpenClaw 架构的启发**: OpenClaw 的 `sessions_spawn` 天然是 agent 间通信，可映射到 A2A 概念

## 下一步行动

1. **[本周]** 基于 v1.2 spec 创建 `lab/a2a-trust-prototype/`，实现：
   - ES256 密钥生成 + Agent Card 签名（本笔记代码可直接使用）
   - RFC 8785 canonicalization（先简化实现，后续换 `rfc8785` npm 包）
   - Trust Score 三层计算模型
   - 签名验证 + 篡改检测测试

2. **[本周]** 安装 `a2a-sdk` (`npm install a2a-sdk`)，评估与现有 a2a-trust 原型的集成点

3. **[本月]** 研究 Sigstore A2A (github.com/sigstore/sigstore-a2a) 作为生产级 Agent Card 签名方案

## 参考资料

- A2A Specification v1.2: https://github.com/a2aproject/A2A/blob/main/docs/specification.md
- A2A JS SDK: https://github.com/a2aproject/a2a-js
- Agent Card 详解: https://blog.tobira.ai/how-a2a-agent-cards-work/
- 安全研究: arXiv:2505.12490 (8 security weaknesses in A2A v1)
- Red Hat 安全加固: https://developers.redhat.com/articles/2025/08/19/how-enhance-agent2agent-security
- Sigstore A2A 签名: https://github.com/sigstore/sigstore-a2a
- Linux Foundation 一周年公告: https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations
- PEAC Protocol A2A 适配器: https://www.peacprotocol.org/adapters
