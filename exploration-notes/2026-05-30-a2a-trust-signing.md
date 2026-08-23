# A2A 信任协议与 Agent Card 签名验证

> 研究日期: 2026-05-30
> 关联项目: `lab/a2a-trust-prototype`
> 状态: ✅ 研究完成，可直接进入原型开发

---

## 核心概念

### 1. Agent Card — Agent 的数字名片
每个 A2A 兼容 Agent 在 `/.well-known/agent-card.json` 发布一个 JSON 文档，声明身份、能力、安全方案和端点。类似 OpenAPI spec 但面向 Agent。

**关键字段**: `name`, `url`, `skills[]`, `securitySchemes`, `signatures[]`

### 2. Signed Agent Card (JWS) — 密码学身份验证
A2A v1.0 (2026-03) 引入 Agent Card 数字签名，使用 **JWS (RFC 7515)** 格式。签名结构：

```json
{
  "signatures": [{
    "protected": "BASE64URL({alg,typ,kid})",
    "signature": "BASE64URL(ECDSA_SIG)",
    "header": { "kid": "key-2026-01" }
  }]
}
```

- **算法**: ES256 (ECDSA P-256 + SHA-256) — 推荐首选
- **规范化**: RFC 8785 (JSON Canonicalization Scheme) — 确保签名确定性
- **排除字段**: `signatures` 字段本身不参与签名计算

### 3. Trust Score — 信任评分模型
协议层只解决 "这个 Agent 是谁"，不解决 "能不能信任它"。信任需要多层模型：
- **身份层**: Signed Agent Card → 密码学验证
- **授权层**: OAuth 2.0 / mTLS → 权限范围控制
- **行为层**: 审计日志 → 异常检测
- **组织层**: 合规审计 → 6% 的企业敢让 Agent 自主操作

### 4. 协议栈定位
```
┌─────────────────────┐
│  AP2 / TAP          │  ← 监督 & 支付身份
├─────────────────────┤
│  A2A                │  ← Agent 间协作 (本文焦点)
├─────────────────────┤
│  MCP                │  ← Agent 到工具
├─────────────────────┤
│  x402 / MPP         │  ← 支付层
└─────────────────────┘
```

### 5. 认证流程三步模式
1. Client 获取 Agent Card → 读取 `securitySchemes`
2. Client 按指定方案获取凭证 (OAuth2/JWT/API Key/mTLS)
3. 请求携带 `Authorization: Bearer <token>` 或 `API-Key: <value>`

---

## 可运行代码示例

### Agent Card 签名与验证 (Node.js 原生 crypto)

```js
// a2a-trust-prototype/sign-agent-card.mjs
// 零依赖，仅用 Node.js 内置 crypto 模块

import { generateKeyPairSync, createSign, createVerify } from 'node:crypto';

// ============================================
// 1. 生成 ECDSA P-256 密钥对
// ============================================
function generateSigningKey() {
  const { publicKey, privateKey } = generateKeyPairSync('ec', {
    namedCurve: 'P-256',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
  return { publicKey, privateKey };
}

// ============================================
// 2. RFC 8785 简化规范化
// (生产环境应使用 rfc8785 npm 包)
// ============================================
function canonicalize(obj) {
  // 递归排序 key，处理基本类型
  if (obj === null || typeof obj !== 'object') {
    if (typeof obj === 'string') return JSON.stringify(obj);
    if (typeof obj === 'number' || typeof obj === 'boolean') return String(obj);
    return 'null';
  }
  if (Array.isArray(obj)) {
    return '[' + obj.map(canonicalize).join(',') + ']';
  }
  const keys = Object.keys(obj).sort();
  return '{' + keys.map(k => JSON.stringify(k) + ':' + canonicalize(obj[k])).join(',') + '}';
}

// ============================================
// 3. Base64URL 编码/解码
// ============================================
function base64url(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function base64urlDecode(str) {
  let s = str.replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  return Buffer.from(s, 'base64');
}

// ============================================
// 4. 签名 Agent Card
// ============================================
function signAgentCard(card, privateKey, kid) {
  // 构造 Protected Header
  const header = { alg: 'ES256', typ: 'agent-card+jwt', kid };
  const protectedB64 = base64url(Buffer.from(JSON.stringify(header), 'utf-8'));

  // 规范化 payload (排除 signatures 字段)
  const { signatures, ...payload } = card;
  const canonicalPayload = canonicalize(payload);
  const payloadB64 = base64url(Buffer.from(canonicalPayload, 'utf-8'));

  // 计算签名
  const signInput = `${protectedB64}.${payloadB64}`;
  const signer = createSign('SHA256');
  signer.update(signInput);
  signer.end();
  const sigDer = signer.sign(privateKey);

  // DER → Raw (r || s, each 32 bytes)
  const sigRaw = derToRaw(sigDer);

  return {
    ...card,
    signatures: [{
      protected: protectedB64,
      signature: base64url(sigRaw),
      header: { kid }
    }]
  };
}

// DER 签名 → Raw r||s (JWS 要求)
function derToRaw(der) {
  // 简化解析: 0x30 <len> 0x02 <rlen> <r> 0x02 <slen> <s>
  const buf = Buffer.from(der);
  let offset = 2; // skip 0x30 + total len
  offset++; // skip 0x02
  const rLen = buf[offset++];
  const r = buf.slice(offset, offset + rLen);
  offset += rLen;
  offset++; // skip 0x02
  const sLen = buf[offset++];
  const s = buf.slice(offset, offset + sLen);

  // 去除前导零，补齐到 32 字节
  const rPadded = padTo32(r[0] === 0 ? r.slice(1) : r);
  const sPadded = padTo32(s[0] === 0 ? s.slice(1) : s);
  return Buffer.concat([rPadded, sPadded]);
}

function padTo32(buf) {
  if (buf.length === 32) return buf;
  const padded = Buffer.alloc(32);
  buf.copy(padded, 32 - buf.length);
  return padded;
}

// ============================================
// 5. 验证 Agent Card 签名
// ============================================
function verifyAgentCard(signedCard, publicKey) {
  const sig = signedCard.signatures?.[0];
  if (!sig) throw new Error('No signature found');

  // 解码 Protected Header
  const header = JSON.parse(base64urlDecode(sig.protected).toString('utf-8'));
  if (header.alg !== 'ES256') throw new Error(`Unsupported alg: ${header.alg}`);

  // 重构签名输入
  const { signatures, ...payload } = signedCard;
  const canonicalPayload = canonicalize(payload);
  const payloadB64 = base64url(Buffer.from(canonicalPayload, 'utf-8'));
  const signInput = `${sig.protected}.${payloadB64}`;

  // Raw → DER
  const sigRaw = base64urlDecode(sig.signature);
  const derSig = rawToDer(sigRaw);

  // 验证
  const verifier = createVerify('SHA256');
  verifier.update(signInput);
  verifier.end();
  return verifier.verify(publicKey, derSig);
}

function rawToDer(raw) {
  const r = Buffer.from(raw.slice(0, 32));
  const s = Buffer.from(raw.slice(32, 64));
  
  const rEnc = r[0] & 0x80 ? Buffer.concat([Buffer.from([0]), r]) : r;
  const sEnc = s[0] & 0x80 ? Buffer.concat([Buffer.from([0]), s]) : s;

  const rHead = Buffer.from([0x02, rEnc.length]);
  const sHead = Buffer.from([0x02, sEnc.length]);
  const inner = Buffer.concat([rHead, rEnc, sHead, sEnc]);
  return Buffer.concat([Buffer.from([0x30, inner.length]), inner]);
}

// ============================================
// 6. 完整演示
// ============================================
const { publicKey, privateKey } = generateSigningKey();
const kid = 'a2a-key-2026-05';

const agentCard = {
  name: "Catalyst Agent",
  description: "Research and coding assistant",
  url: "https://catalyst.example.com/a2a",
  provider: { organization: "Catalyst Lab" },
  version: "1.0.0",
  capabilities: { streaming: true, pushNotifications: false },
  skills: [{
    id: "deep-research",
    name: "Deep Research",
    description: "Execute autonomous research cycles",
    tags: ["research", "analysis"]
  }],
  securitySchemes: {
    bearer: { type: "http", scheme: "bearer", bearerFormat: "JWT" }
  }
};

// 签名
const signed = signAgentCard(agentCard, privateKey, kid);
console.log('✅ Signed Agent Card:');
console.log(JSON.stringify(signed, null, 2));

// 验证
const isValid = verifyAgentCard(signed, publicKey);
console.log(`\n🔐 Signature valid: ${isValid}`);

// 篡改检测
const tampered = { ...signed, name: "Malicious Agent" };
try {
  const tamperResult = verifyAgentCard(tampered, publicKey);
  console.log(`\n⚠️ Tampered check: ${tamperResult} (should be false)`);
} catch (e) {
  console.log(`\n✅ Tampered card rejected: ${e.message}`);
}
```

**运行**: `node sign-agent-card.mjs`

---

### Trust Score 计算器

```js
// a2a-trust-prototype/trust-score.mjs

/**
 * Agent 信任评分模型
 * 结合身份验证、行为历史、权限范围计算综合信任分数
 */
export class TrustScorer {
  constructor(config = {}) {
    this.weights = {
      identityVerified: 0.30,  // Signed Agent Card 验证通过
      authStrength: 0.20,      // mTLS > OAuth2 > API Key
      scopeMinimal: 0.15,      // 最小权限原则
      historyClean: 0.20,      // 行为历史无异常
      orgReputation: 0.15      // 组织信誉/审计
    };
  }

  score(agent) {
    let total = 0;
    const breakdown = {};

    // 身份验证 (0-100)
    breakdown.identityVerified = agent.cardSigned && agent.signatureValid ? 100 : 0;
    
    // 认证强度 (0-100)
    const authLevels = { mtls: 100, oauth2: 80, openid: 75, bearer: 50, apiKey: 30 };
    breakdown.authStrength = authLevels[agent.authScheme] ?? 0;
    
    // 权限最小化 (0-100): skills 越少越专一越高
    const skillCount = agent.skills?.length ?? 0;
    breakdown.scopeMinimal = skillCount <= 3 ? 90 : skillCount <= 8 ? 60 : 30;
    
    // 历史记录 (0-100)
    breakdown.historyClean = agent.incidentCount === 0 ? 100 
      : agent.incidentCount <= 2 ? 60 : 20;
    
    // 组织信誉 (0-100)
    breakdown.orgReputation = agent.audited ? 90 : agent.orgKnown ? 60 : 20;

    for (const [key, weight] of Object.entries(this.weights)) {
      total += (breakdown[key] / 100) * weight;
    }

    return {
      score: Math.round(total * 100),  // 0-100
      level: total >= 0.8 ? 'HIGH' : total >= 0.5 ? 'MEDIUM' : 'LOW',
      breakdown,
      recommendation: total >= 0.8 ? '可自主执行任务' 
        : total >= 0.5 ? '需要人类审批关键操作'
        : '仅允许只读访问'
    };
  }
}

// 演示
const scorer = new TrustScorer();
const result = scorer.score({
  cardSigned: true,
  signatureValid: true,
  authScheme: 'oauth2',
  skills: ['research', 'code-review'],
  incidentCount: 0,
  audited: true,
  orgKnown: true
});
console.log('Trust Assessment:', JSON.stringify(result, null, 2));
```

---

## 关键洞察

### 1. 协议标准化 ≠ 信任建立
A2A 一年达到 150+ 组织支持，但只有 **6%** 的企业信任 Agent 自主操作。协议解决的是 "怎么说话"，信任解决的是 "敢不敢听"。Signed Agent Card 是从协议到信任的桥梁，但只是第一步。

### 2. Agent Card 签名的十一月空窗期
A2A 2025-04 发布，但签名机制直到 2026-03 (v1.0) 才落地。这段空窗期意味着早期部署的 Agent Card 无法验证来源完整性。这个教训对原型设计很重要：**从第一天就内置签名**。

### 3. Node.js 原生 crypto 完全够用
A2A Agent Card 签名只需要 ES256 (ECDSA P-256 + SHA-256)，Node.js 内置 `crypto` 模块原生支持，不需要 `jsonwebtoken` 或 `jose` 等第三方库。关键坑点在于 DER ↔ Raw 签名格式转换（JWS 要求 Raw 格式，Node.js crypto 输出 DER 格式）。

### 4. 规范化是最大的工程挑战
RFC 8785 JSON Canonicalization 看似简单（排序 key），但边界情况复杂：Unicode 处理、数字精度、嵌套结构。生产环境必须用专门的 `rfc8785` npm 包，自己实现的排序只适合原型验证。

### 5. 信任评分应该是多维的
单一维度（如"签名是否有效"）不足以判断信任。Trust Score 应该融合：身份验证(30%) + 认证强度(20%) + 权限范围(15%) + 行为历史(20%) + 组织信誉(15%)。这与 Visa 的 TAP 和 AP2 的思路一致。

---

## 下一步行动

1. **`lab/a2a-trust-prototype/` 原型开发** — 基于本文代码，实现完整的签名中间件
   - Agent Card 签名生成/验证模块
   - Trust Score 计算引擎
   - Express 中间件集成
   - 目标：可 `npm install` 集成到任意 Agent 服务

2. **引入 `rfc8785` 包处理规范化** — 生产级 JSON Canonicalization

3. **探索与 openclaw-langgraph-bridge 集成** — A2A 信任层作为 Supervisor 的路由决策因子

---

## 参考资源

- [A2A 规范 - Agent Card Signing](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) — 官方签名规范
- [A2A at One Year](https://vibeagentmaking.com/blog/a2a-at-one-year-the-standard-won-and-nobody-has-production-trust) — 信任差距分析
- [The Agent Stack 2026](https://sanbi.ai/blog/agent-stack-protocols-2026) — 协议栈全景
- [OAuth for Agent Integration](https://jevvellabs.com/assets/files/oauth-for-agent-integration) — JWT Claims 在 Agent 场景的应用
- [RFC 8785](https://tools.ietf.org/html/rfc8785) — JSON Canonicalization Scheme
- [RFC 7515](https://tools.ietf.org/html/rfc7515) — JSON Web Signature (JWS)
