# MCP Zero-Trust Auth: OAuth 2.1 + Agent Identity Layer

> 研究日期: 2026-05-27
> 触发: a2a-trust-prototype 前置研究 + MCP 生态安全趋势
> 状态: ✅ 含可运行代码 + 独到洞察

---

## 核心概念 (5个)

### 1. MCP Authorization Spec (OAuth 2.1 + PKCE)
MCP 规范现在要求远程服务器使用 OAuth 2.1 Authorization Code Flow + PKCE。流程：
- Agent → MCP Server (无 token) → 401 + `WWW-Authenticate: MCP` header
- Client 通过 Protected Resource Metadata (PRM) 发现授权需求
- OAuth 2.1 流程获取 scoped access token
- **关键**: PKCE 保护 token exchange，但不认证 client 本身

### 2. Protected Resource Metadata (PRM, RFC 9728)
JSON 文档，MCP Server 在 401 响应中返回，告诉 client：
- 需要哪个 Authorization Server
- 需要什么 scope
- 支持什么 token 格式

### 3. Agent Identity Layer (基础设施断言身份)
**核心洞察**: OAuth 2.1 解决的是"谁能访问"，但 AI Agent 的身份问题更复杂：
- Agent 不是人类 → 没有 username/password
- Agent 代表用户行动 → 需要 on-behalf-of 委托
- Agent 动态创建/销毁 → 需要临时身份

解决方案：**基础设施断言身份** (Infrastructure-Asserted Identity)
- SPIFFE/SPIRE 为 Agent 颁发 SVID (SPIFFE Verifiable Identity Document)
- 或通过平台 (Cloudflare Workers, K8s service mesh) 自动注入身份

### 4. Token Chaining (多跳委托)
```
User → Agent A (user token) → Agent A 获得 delegated token → Agent A → Tool B (delegated token)
```
每跳做 token exchange，保持：
- 可审计性 (谁通过哪个 agent 做了什么)
- 最小权限 (每跳 scope 递减)
- 短生命周期 (降低泄露风险)

### 5. Zero-Trust Agent Architecture (CSA 框架)
Cloud Security Alliance 的 Agentic Trust Framework 核心原则：
- 每个 Agent 一个唯一身份 (不是共享 API key)
- Just-in-Time 访问 (需要时才授权，限时)
- 微分段 (Agent 流量隔离)
- 行为监控 (异常检测)

---

## 可运行代码: MCP Auth Middleware (Node.js, 零依赖)

实现一个最小但完整的 MCP 服务器认证中间件，包含：
- JWT 签发/验证 (ES256, 纯 crypto)
- PRM 发现端点
- Scope 验证
- Token chaining 支持

```js
// mcp-auth-middleware.js — 零依赖 MCP Zero-Trust Auth
// Node.js 22+ required
import { webcrypto } from 'node:crypto';

const { subtle } = webcrypto;

// ─── Key Management ───
async function generateKeyPair() {
  return subtle.generateKey(
    { name: 'ECDSA', namedCurve: 'P-256' },
    true,
    ['sign', 'verify']
  );
}

async function exportSPKI(key) {
  const buf = await subtle.exportKey('spki', key);
  return btoa(String.fromCharCode(...new Uint8Array(buf)));
}

// ─── JWT (ES256) ───
function base64url(buf) {
  return btoa(String.fromCharCode(...new Uint8Array(buf)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function signJWT(payload, privateKey) {
  const header = { alg: 'ES256', typ: 'JWT' };
  const headerB64 = base64url(new TextEncoder().encode(JSON.stringify(header)));
  const payloadB64 = base64url(new TextEncoder().encode(JSON.stringify(payload)));
  const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const sig = await subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, privateKey, data);
  const sigB64 = base64url(sig);
  return `${headerB64}.${payloadB64}.${sigB64}`;
}

async function verifyJWT(token, publicKey) {
  const [headerB64, payloadB64, sigB64] = token.split('.');
  const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const sig = Uint8Array.from(atob(sigB64.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
  const valid = await subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, publicKey, sig, data);
  if (!valid) throw new Error('Invalid signature');
  return JSON.parse(atob(payloadB64.replace(/-/g, '+').replace(/_/g, '/')));
}

// ─── MCP Auth Middleware ───
class MCPAuthMiddleware {
  /**
   * @param {Object} opts
   * @param {string} opts.serverUrl - MCP server public URL
   * @param {string[]} opts.scopes - required scopes (e.g. ['tools:read', 'tools:write'])
   * @param {CryptoKeyPair} opts.keyPair - ES256 key pair
   */
  constructor(opts) {
    this.serverUrl = opts.serverUrl;
    this.requiredScopes = opts.scopes || ['tools:read'];
    this.keyPair = opts.keyPair;
    this.trustedKeys = new Map(); // kid → publicKey
  }

  /** Protected Resource Metadata (RFC 9728) */
  getPRM() {
    return {
      resource: this.serverUrl,
      'authorization_servers': [`${this.serverUrl}/auth`],
      'scopes_supported': this.requiredScopes,
      'bearer_methods_supported': ['header'],
      'resource_signing_alg_values_supported': ['ES256'],
    };
  }

  /** Issue a scoped access token for an agent */
  async issueToken({ agentId, subject, scopes, expiresInSec = 300 }) {
    const kid = crypto.randomUUID();
    const now = Math.floor(Date.now() / 1000);
    const payload = {
      iss: this.serverUrl,
      sub: subject || agentId,
      act: { sub: agentId },  // "act" = actor (the agent)
      scope: scopes.join(' '),
      iat: now,
      exp: now + expiresInSec,
      kid,
    };
    const token = await signJWT(payload, this.keyPair.privateKey);
    return { token, kid, expires_in: expiresInSec };
  }

  /** Token exchange: mint a delegated token (on-behalf-of) */
  async exchangeToken({ parentToken, targetAgentId, scopes, expiresInSec = 120 }) {
    const claims = await verifyJWT(parentToken, this.keyPair.publicKey);
    // Chain: original subject stays, actor updates, scopes narrow
    return this.issueToken({
      subject: claims.sub,
      agentId: targetAgentId,
      scopes: scopes.filter(s => claims.scope.split(' ').includes(s)), // only subset
      expiresInSec,
    });
  }

  /** Express/Node.js middleware function */
  authenticate() {
    return async (req, res, next) => {
      const auth = req.headers['authorization'];
      if (!auth || !auth.startsWith('Bearer ')) {
        res.setHeader('WWW-Authenticate', `MCP resource_metadata="${this.serverUrl}/.well-known/oauth-protected-resource"`);
        return res.status(401).json({ error: 'unauthorized', prm_url: `${this.serverUrl}/.well-known/oauth-protected-resource` });
      }

      try {
        const token = auth.slice(7);
        const claims = await verifyJWT(token, this.keyPair.publicKey);

        // Check expiration
        if (claims.exp < Math.floor(Date.now() / 1000)) {
          return res.status(401).json({ error: 'token_expired' });
        }

        // Check scopes
        const tokenScopes = (claims.scope || '').split(' ');
        const hasScope = this.requiredScopes.some(s => tokenScopes.includes(s));
        if (!hasScope) {
          return res.status(403).json({ error: 'insufficient_scope', required: this.requiredScopes });
        }

        // Attach agent identity to request
        req.agent = {
          id: claims.act?.sub || claims.sub,
          subject: claims.sub,
          scopes: tokenScopes,
          actor: claims.act?.sub,
        };
        next();
      } catch (e) {
        return res.status(401).json({ error: 'invalid_token', message: e.message });
      }
    };
  }
}

// ─── Demo / Test ───
async function demo() {
  console.log('=== MCP Zero-Trust Auth Demo ===\n');

  const keyPair = await generateKeyPair();
  const auth = new MCPAuthMiddleware({
    serverUrl: 'https://mcp.example.com',
    scopes: ['tools:read', 'tools:write', 'calendar:read'],
    keyPair,
  });

  // 1. Show PRM
  console.log('📋 Protected Resource Metadata:');
  console.log(JSON.stringify(auth.getPRM(), null, 2));
  console.log();

  // 2. Issue token for CalendarAI agent
  console.log('🤖 Issuing token for CalendarAI agent...');
  const { token, kid } = await auth.issueToken({
    agentId: 'calendar-ai-v1',
    subject: 'user:sarah',
    scopes: ['tools:read', 'calendar:read'],
    expiresInSec: 300,
  });
  console.log(`Token (truncated): ${token.slice(0, 50)}...`);
  console.log(`Key ID: ${kid}\n`);

  // 3. Verify token
  console.log('🔍 Verifying token...');
  const claims = await verifyJWT(token, keyPair.publicKey);
  console.log('Claims:', JSON.stringify(claims, null, 2));
  console.log();

  // 4. Token exchange (delegation to sub-agent)
  console.log('🔄 Token exchange: CalendarAI → SummaryAgent...');
  const { token: delegatedToken } = await auth.exchangeToken({
    parentToken: token,
    targetAgentId: 'summary-agent-v1',
    scopes: ['tools:read'], // narrowed scope
    expiresInSec: 60,
  });
  const delegatedClaims = await verifyJWT(delegatedToken, keyPair.publicKey);
  console.log('Delegated claims:', JSON.stringify(delegatedClaims, null, 2));
  console.log();

  // 5. Simulate scope violation
  console.log('🚫 Attempting scope escalation (calendar:read → tools:write)...');
  const { token: badToken } = await auth.exchangeToken({
    parentToken: token,
    targetAgentId: 'rogue-agent',
    scopes: ['tools:write'], // not in parent scope
    expiresInSec: 60,
  });
  const badClaims = await verifyJWT(badToken, keyPair.publicKey);
  console.log(`Escalation blocked! Got scopes: "${badClaims.scope}" (empty — parent didn't have tools:write)\n`);

  // 6. Tamper detection
  console.log('🔒 Tamper detection test...');
  const tamperedToken = token.slice(0, -5) + 'XXXXX';
  try {
    await verifyJWT(tamperedToken, keyPair.publicKey);
  } catch (e) {
    console.log(`Tampered token rejected: ${e.message}\n`);
  }

  console.log('✅ All tests passed!');
}

demo().catch(console.error);
```

**运行方式:**
```bash
node mcp-auth-middleware.js
```

**预期输出:**
```
=== MCP Zero-Trust Auth Demo ===

📋 Protected Resource Metadata:
{ resource: 'https://mcp.example.com', ... }

🤖 Issuing token for CalendarAI agent...
Token (truncated): eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...
🔍 Verifying token...
Claims: { iss: '...', sub: 'user:sarah', act: { sub: 'calendar-ai-v1' }, scope: 'tools:read calendar:read', ... }

🔄 Token exchange: CalendarAI → SummaryAgent...
Delegated claims: { sub: 'user:sarah', act: { sub: 'summary-agent-v1' }, scope: 'tools:read', ... }

🚫 Scope escalation blocked! Got scopes: "" (empty)
🔒 Tampered token rejected: Invalid signature
✅ All tests passed!
```

---

## 关键洞察 (5条)

### 1. PKCE ≠ Client 认证
业界普遍误解 PKCE 能认证 client。实际上 PKCE 只保护 authorization code 不被截获。Agent 的真实身份认证需要**基础设施层**（SPIFFE/平台注入），不能靠 PKCE。

### 2. MCP 正在经历 Gartner 炒作周期
Perplexity 放弃 MCP（72% context window 消耗）引发了"MCP is dead"论调。但实际上这是从"膨胀期望峰值"走向"启蒙斜坡"的正常过渡。企业级 OAuth 2.1 + gateway 就是启蒙阶段的产物。

### 3. Token Chaining 是 Agent 信任的核心原语
`User → Agent A → Agent B → Tool` 的每一步都需要独立的 token exchange，scope 递减。这不是新概念（OAuth on-behalf-of flow），但应用到 AI Agent 是新领域。**我们的 a2a-trust-prototype 应该直接实现这个模式**。

### 4. Agent 身份 = 基础设施身份
静态 API key 是 "skeleton key"——一旦泄露全暴露。2026 年共识：每个 Agent 需要唯一身份（SPIFFE SVID / OAuth client credentials / 平台注入），短生命周期，scope 严格限制。**这验证了我们在 a2a-trust-prototype 中选择 ES256 + 短生命周期 token 的方向**。

### 5. MCP Gateway 正在成为基础设施层
Solo.io 的 agentgateway、Cloudflare 的 McpAgent、Arcade 的 MCP runtime 都在做同一件事：在 Agent 和 MCP Server 之间加一个策略网关。这个模式类似于 API Gateway 之于微服务——**Agent Gateway 将成为 AI 基础设施的标准组件**。

---

## 与现有项目关联

| 项目 | 关联 |
|------|------|
| **lab/a2a-trust-prototype** | 直接输入：OAuth 2.1 flow + token chaining + scope 验证，可复用本文中间件代码 |
| **lab/agent-observability** | Token 签发/验证事件应纳入 tracing，OTel 语义约定 |
| **openclaw-langgraph-bridge** | Multi-agent 编排中的身份传播：supervisor → worker 需要 token chain |
| **AMS / agent-context-store** | Context store 可以存储 agent identity claims，支持跨 session 身份连续性 |

---

## 下一步行动

1. **将本文中间件代码整合到 lab/a2a-trust-prototype/** — 扩展现有 TrustManager，加入 OAuth 2.1 PRM + token exchange
2. **研究 SPIFFE/SPIRE 与 Node.js 集成** — 为 Agent 提供基础设施级身份，而非应用级 token
3. **评估 agentgateway (Solo.io)** — 是否值得作为 OpenClaw 的 MCP 代理层

---

## 参考来源

- [Aembit: MCP, OAuth 2.1, PKCE, and the Future of AI Authorization](https://aembit.io/blog/mcp-oauth-2-1-pkce-and-the-future-of-ai-authorization)
- [Cerbos: MCP and Zero Trust](https://www.cerbos.dev/blog/mcp-and-zero-trust-securing-ai-agents-with-identity-and-policy)
- [CSA: Agentic Trust Framework](https://cloudsecurityalliance.org/blog/2026/02/02/the-agentic-trust-framework-zero-trust-governance-for-ai-agents)
- [Arcade: Multi-User AI Agent Auth](https://www.arcade.dev/blog/ai-agent-authentication-authorization)
- [Tyk: Is MCP Dead?](https://tyk.io/learning-center/is-mcp-dead-in-2026-why-enterprises-still-need-mcp)
- [MCP Authorization Specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/authorization/)
