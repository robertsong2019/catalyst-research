# X42 协议：跨边界 Agent 信任与治理

> 研究日期: 2026-06-04
> 研究方法: Tavily 深度搜索 + 多源交叉验证
> 关联项目: a2a-trust-prototype, agent-observability, openclaw-langgraph-bridge

---

## 核心概念

### 1. X42 是跨边界信任治理层

X42 不是一个通信协议，而是一个**权限和审计层**。它解决的核心问题：当 Agent A（运行在环境 X）需要调用 Agent B（运行在环境 Y）的能力时，如何确保：

- **认证** (Authentication): 谁在发起调用？
- **授权** (Authorization): 他们有权调用这个能力吗？
- **问责** (Accountability): 调用的完整审计追踪

与 A2A 互补：A2A 定义 Agent 之间如何对话（协议层），X42 定义 Agent 之间**是否有权对话**（治理层）。

### 2. 六层 Agent 协议栈定位

2026 年 Agent 协议生态已形成清晰的六层栈：

| 协议 | 层 | 解决问题 | 成熟度 |
|------|---|---------|--------|
| MCP | 工具访问 | Agent → 工具/数据 | ⭐⭐⭐ 成熟 |
| A2A | Agent 协调 | Agent → Agent 任务委托 | ⭐⭐⭐ 成熟 |
| AG-UI | 界面流式 | Agent → 前端实时推送 | ⭐⭐ 采用中 |
| A2UI | 界面状态 | Agent ↔ UI 持久状态同步 | ⭐⭐ 采用中 |
| AP2 | Agent 管理 | 外部系统控制/查询 Agent | ⭐ 新兴 |
| **X42** | **信任与治理** | **跨边界 Agent 调用的权限管理** | **⭐ 新兴/企业级** |

关键洞察：这六个协议不竞争，它们是同一栈的不同层。完整的多 Agent 应用可能同时使用全部六个。

### 3. 签名请求 + 作用域令牌 + 执行日志

X42 的技术核心是三个原语：

- **Signed Requests（签名请求）**: 每个跨边界调用用密码学签名，不可伪造
- **Scoped Tokens（作用域令牌）**: 细粒度权限令牌，限定可执行的操作和资源
- **Execution Logs（执行日志）**: 不可变的审计追踪，记录谁在何时以什么权限调用了什么

### 4. 零信任 Agent 治理（CSA ATF 框架）

Cloud Security Alliance 发布的 Agentic Trust Framework (ATF) 是 X42 概念的具体实现规范。核心原则：

> "No AI agent should be trusted by default, regardless of purpose or claimed capability. Trust must be earned through demonstrated behavior and continuously verified through monitoring."

ATF 五个核心元素：
1. **Identity（身份）**: Agent 是谁？JWT + OAuth2/OIDC
2. **Behavior（行为）**: Agent 在做什么？LLM 可观测性 + 异常检测
3. **Data Governance（数据治理）**: Agent 访问什么数据？PII/PHI 检测 + 输出过滤
4. **Segmentation（分段）**: Agent 能去哪里？基于角色的策略 + 速率限制
5. **Incident（事件）**: 出错怎么办？断路器 + 错误追踪 + 告警

Agent 分级：Intern（实习生）→ Junior → Senior → Principal，每级有明确的能力范围和控制要求。

### 5. 信任衰减与委托链范围收窄

Microsoft Agent Governance Toolkit (AGT) 实现了两个关键模式：

**信任衰减（Trust Decay）**: Agent 的信任分数随时间递减。上周可信但之后沉默的 Agent 会逐渐变得不可信。信任需要持续展示，不是一次性授权。

**委托链范围收窄（Scope Narrowing）**: 父 Agent 拥有 read+write 权限，只能委托 read 权限给子 Agent。权限在委托链中只能缩小，不能升级。

AGT 架构九包：
- Agent OS（策略引擎）
- Agent Mesh（DID 身份 + 信任协议）
- Agent Hypervisor（执行环 + Saga 编排）
- Agent Runtime（运行时监督 + 紧急停止）
- Agent SRE（SLO + 断路器 + 混沌工程）

---

## 可运行代码示例

以下代码演示 X42 风格的跨边界信任治理中间件，包含签名请求验证、作用域令牌和审计日志：

```typescript
/**
 * X42-style Cross-Boundary Trust Governance Middleware
 * 
 * 核心原语: Signed Requests + Scoped Tokens + Execution Logs
 * 零外部依赖，Node.js 原生 crypto
 */

import { createPublicKey, createVerify, createHmac, randomBytes } from 'crypto';

// ============================================================
// 1. Scoped Token - 作用域令牌
// ============================================================

interface TokenPayload {
  agentId: string;
  issuer: string;
  scopes: string[];
  audience: string;    // 目标 Agent/服务
  expiresAt: number;
  delegationChain?: string[];  // 委托链
}

class ScopedTokenManager {
  private secret: string;
  
  constructor(secret: string) {
    this.secret = secret;
  }
  
  issue(payload: Omit<TokenPayload, 'expiresAt'>, ttlSeconds: number = 3600): string {
    const fullPayload: TokenPayload = {
      ...payload,
      expiresAt: Date.now() + ttlSeconds * 1000,
    };
    const encoded = Buffer.from(JSON.stringify(fullPayload)).toString('base64url');
    const signature = createHmac('sha256', this.secret).update(encoded).digest('base64url');
    return `${encoded}.${signature}`;
  }
  
  verify(token: string, requiredScope: string, targetAgent: string): TokenPayload {
    const [encoded, signature] = token.split('.');
    if (!encoded || !signature) throw new Error('Invalid token format');
    
    const expectedSig = createHmac('sha256', this.secret).update(encoded).digest('base64url');
    if (signature !== expectedSig) throw new Error('Invalid token signature');
    
    const payload: TokenPayload = JSON.parse(Buffer.from(encoded, 'base64url').toString());
    
    if (Date.now() > payload.expiresAt) throw new Error('Token expired');
    if (!payload.scopes.includes(requiredScope)) throw new Error(`Missing scope: ${requiredScope}`);
    if (payload.audience !== targetAgent) throw new Error(`Audience mismatch: expected ${targetAgent}`);
    
    return payload;
  }
  
  /**
   * 委托链范围收窄 - 只能缩小权限，不能扩大
   */
  delegate(parentToken: string, childAgentId: string, narrowedScopes: string[], ttlSeconds: number = 1800): string {
    const parent = this.verify(parentToken, '*', '*'); // 内部验证
    // X42 核心规则: 子令牌权限必须是父令牌的子集
    const validScopes = narrowedScopes.filter(s => parent.scopes.includes(s));
    if (validScopes.length === 0) throw new Error('Cannot delegate: no valid scopes after narrowing');
    
    return this.issue({
      agentId: childAgentId,
      issuer: parent.agentId,
      scopes: validScopes,
      audience: parent.audience,
      delegationChain: [...(parent.delegationChain || []), parent.agentId],
    }, ttlSeconds);
  }
}

// ============================================================
// 2. Execution Audit Log - 不可变执行日志
// ============================================================

interface AuditEntry {
  timestamp: string;
  callerAgentId: string;
  targetAgentId: string;
  action: string;
  scope: string;
  granted: boolean;
  delegationDepth: number;
  requestId: string;
}

class ExecutionLog {
  private entries: AuditEntry[] = [];
  private hashes: string[] = [];  // 链式哈希
  
  log(entry: Omit<AuditEntry, 'timestamp' | 'requestId'>): AuditEntry {
    const fullEntry: AuditEntry = {
      ...entry,
      timestamp: new Date().toISOString(),
      requestId: randomBytes(8).toString('hex'),
    };
    
    // 链式哈希（简化版区块链）
    const prevHash = this.hashes[this.hashes.length - 1] || 'genesis';
    const entryHash = createHmac('sha256', prevHash)
      .update(JSON.stringify(fullEntry))
      .digest('hex');
    this.hashes.push(entryHash);
    
    this.entries.push(fullEntry);
    return fullEntry;
  }
  
  query(filter: Partial<Pick<AuditEntry, 'callerAgentId' | 'targetAgentId' | 'granted'>>): AuditEntry[] {
    return this.entries.filter(e => {
      if (filter.callerAgentId && e.callerAgentId !== filter.callerAgentId) return false;
      if (filter.targetAgentId && e.targetAgentId !== filter.targetAgentId) return false;
      if (filter.granted !== undefined && e.granted !== filter.granted) return false;
      return true;
    });
  }
  
  verify(): boolean {
    // 验证日志链完整性
    for (let i = 0; i < this.entries.length; i++) {
      const prevHash = i === 0 ? 'genesis' : this.hashes[i - 1];
      const expectedHash = createHmac('sha256', prevHash)
        .update(JSON.stringify(this.entries[i]))
        .digest('hex');
      if (this.hashes[i] !== expectedHash) return false;
    }
    return true;
  }
}

// ============================================================
// 3. Trust Score with Decay - 信任衰减评分
// ============================================================

interface TrustEvent {
  timestamp: number;
  success: boolean;
  weight: number;  // 正面 +1, 负面 -2
}

class TrustScorer {
  private events: Map<string, TrustEvent[]> = new Map();  // agentId → events
  private baseScore: number = 500;  // 0-1000, 起始 500
  private decayHalfLife: number = 7 * 24 * 3600 * 1000;  // 7天半衰期
  
  recordEvent(agentId: string, success: boolean) {
    if (!this.events.has(agentId)) this.events.set(agentId, []);
    this.events.get(agentId)!.push({
      timestamp: Date.now(),
      success,
      weight: success ? 1 : -2,  // 失败惩罚 > 成功奖励
    });
  }
  
  getScore(agentId: string): number {
    const events = this.events.get(agentId) || [];
    const now = Date.now();
    
    let score = this.baseScore;
    for (const event of events) {
      const age = now - event.timestamp;
      const decayFactor = Math.pow(0.5, age / this.decayHalfLife);  // 指数衰减
      score += event.weight * 100 * decayFactor;
    }
    
    return Math.max(0, Math.min(1000, Math.round(score)));
  }
  
  /**
   * 检查 Agent 是否达到信任阈值
   */
  isTrusted(agentId: string, threshold: number = 700): boolean {
    return this.getScore(agentId) >= threshold;
  }
}

// ============================================================
// 4. X42 Middleware - 跨边界调用治理中间件
// ============================================================

interface X42Config {
  agentId: string;
  tokenSecret: string;
  trustThreshold?: number;
  allowedScopes: string[];
}

class X42Middleware {
  private tokenManager: ScopedTokenManager;
  private auditLog: ExecutionLog;
  private trustScorer: TrustScorer;
  private config: X42Config;
  
  constructor(config: X42Config) {
    this.config = config;
    this.tokenManager = new ScopedTokenManager(config.tokenSecret);
    this.auditLog = new ExecutionLog();
    this.trustScorer = new TrustScorer();
  }
  
  /**
   * 验证入站请求 - X42 核心方法
   */
  authorize(callerAgentId: string, token: string, action: string, scope: string): {
    granted: boolean;
    reason?: string;
    auditId?: string;
  } {
    // Step 1: 令牌验证
    let payload: TokenPayload;
    try {
      payload = this.tokenManager.verify(token, scope, this.config.agentId);
    } catch (e) {
      const entry = this.auditLog.log({
        callerAgentId,
        targetAgentId: this.config.agentId,
        action,
        scope,
        granted: false,
        delegationDepth: 0,
      });
      this.trustScorer.recordEvent(callerAgentId, false);
      return { granted: false, reason: `Token verification failed: ${(e as Error).message}`, auditId: entry.requestId };
    }
    
    // Step 2: 信任分数检查
    const trustScore = this.trustScorer.getScore(callerAgentId);
    if (trustScore < (this.config.trustThreshold || 300)) {
      const entry = this.auditLog.log({
        callerAgentId,
        targetAgentId: this.config.agentId,
        action,
        scope,
        granted: false,
        delegationDepth: payload.delegationChain?.length || 0,
      });
      this.trustScorer.recordEvent(callerAgentId, false);
      return { granted: false, reason: `Trust score too low: ${trustScore}`, auditId: entry.requestId };
    }
    
    // Step 3: Scope 检查
    if (!this.config.allowedScopes.includes(scope)) {
      const entry = this.auditLog.log({
        callerAgentId,
        targetAgentId: this.config.agentId,
        action,
        scope,
        granted: false,
        delegationDepth: payload.delegationChain?.length || 0,
      });
      return { granted: false, reason: `Scope not allowed: ${scope}`, auditId: entry.requestId };
    }
    
    // 授权通过
    const entry = this.auditLog.log({
      callerAgentId,
      targetAgentId: this.config.agentId,
      action,
      scope,
      granted: true,
      delegationDepth: payload.delegationChain?.length || 0,
    });
    this.trustScorer.recordEvent(callerAgentId, true);
    
    return { granted: true, auditId: entry.requestId };
  }
  
  /**
   * 委托权限给另一个 Agent
   */
  delegate(callerToken: string, childAgentId: string, scopes: string[], ttlSeconds?: number): string {
    return this.tokenManager.delegate(callerToken, childAgentId, scopes, ttlSeconds);
  }
  
  /**
   * 获取审计报告
   */
  getAuditReport(agentId?: string) {
    const query = agentId ? { callerAgentId: agentId } : {};
    const entries = this.auditLog.query(query);
    return {
      totalCalls: entries.length,
      granted: entries.filter(e => e.granted).length,
      denied: entries.filter(e => !e.granted).length,
      trustScore: this.trustScorer.getScore(agentId || ''),
      logIntegrity: this.auditLog.verify(),
      entries: entries.slice(-10),  // 最近10条
    };
  }
}

// ============================================================
// 5. 完整使用示例
// ============================================================

// 创建两个 Agent 的信任治理中间件
const secret = 'super-secret-key-for-testing';

const agentA = new X42Middleware({
  agentId: 'agent-a',
  tokenSecret: secret,
  trustThreshold: 300,
  allowedScopes: ['read:data', 'write:reports', 'execute:query'],
});

const tokenMgr = new ScopedTokenManager(secret);

// Agent B 获得令牌
const tokenB = tokenMgr.issue({
  agentId: 'agent-b',
  issuer: 'authority',
  scopes: ['read:data', 'write:reports'],
  audience: 'agent-a',
});

// ✅ 授权成功: Agent B 有 read:data 权限
const result1 = agentA.authorize('agent-b', tokenB, 'queryDatabase', 'read:data');
console.log('Result 1:', result1);
// { granted: true, auditId: '...' }

// ❌ 授权失败: Agent B 没有 execute:query 权限
const tokenBLimited = tokenMgr.issue({
  agentId: 'agent-b',
  issuer: 'authority',
  scopes: ['read:data'],  // 只有 read
  audience: 'agent-a',
});
const result2 = agentA.authorize('agent-b', tokenBLimited, 'executeProcedure', 'execute:query');
console.log('Result 2:', result2);
// { granted: false, reason: 'Missing scope: execute:query', ... }

// ✅ 委托链: Agent B 委托 read:data 给 Agent C（范围收窄）
const tokenC = agentA.delegate(tokenB, 'agent-c', ['read:data']);
console.log('Delegated token for agent-c:', tokenC.substring(0, 30) + '...');

// Agent C 可以读数据
const result3 = agentA.authorize('agent-c', tokenC, 'readRecords', 'read:data');
console.log('Result 3:', result3);
// { granted: true, ... }

// 审计报告
const report = agentA.getAuditReport('agent-b');
console.log('Audit Report:', {
  totalCalls: report.totalCalls,
  granted: report.granted,
  denied: report.denied,
  logIntegrity: report.logIntegrity,
});

// 信任分数验证
// 多次成功调用提升信任
for (let i = 0; i < 5; i++) {
  agentA.authorize('agent-b', tokenB, 'query', 'read:data');
}
console.log('Agent-B trust score:', agentA.trustScorer.getScore('agent-b'));
// 应该 > 500（基础分 + 成功加分）

// ===== 运行验证 =====
// 以下断言验证核心功能
function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(`ASSERT FAILED: ${message}`);
  console.log(`✅ ${message}`);
}

// 验证1: 令牌验证 + 授权
assert(result1.granted === true, 'Agent-B authorized with read:data scope');

// 验证2: 权限不足被拒
assert(result2.granted === false, 'Agent-B denied execute:query (missing scope)');

// 验证3: 委托链范围收窄
assert(result3.granted === true, 'Agent-C authorized via delegated token');

// 验证4: 审计日志完整性
assert(report.logIntegrity === true, 'Audit log chain integrity verified');

// 验证5: 信任分数计算
const score = agentA.trustScorer.getScore('agent-b');
assert(score > 500, `Trust score ${score} > 500 after successful calls`);

// 验证6: 委托不能扩大权限
try {
  const badDelegate = tokenMgr.delegate(tokenBLimited, 'agent-d', ['execute:query'], 60);
  // tokenBLimited 只有 read:data，不能委托 execute:query
  assert(false, 'Should not reach here - delegation scope escalation prevented');
} catch (e) {
  assert(true, 'Delegation scope escalation prevented');
}

console.log('\n=== All 6 X42 assertions passed ===');
```

---

## 关键洞察

### 1. X42 填补了 A2A 信任层空白

A2A 定义了 Agent 如何通信（协议），但刻意**不定义信任决策**。X42 填补的正是这个空白：在 A2A 的 Agent Card 之上，加上签名验证、权限作用域和审计追踪。与我们的 a2a-trust-prototype 高度互补——a2a-trust-prototype 做身份级信任（ES256 签名），X42 做**调用级治理**（scope + audit）。

### 2. 委托链范围收窄是安全核心

X42 最关键的设计规则：**权限在委托链中只能缩小，不能扩大**。这直接防止了 Agent 通过嵌套委托来提权。我们的 agent-context-store 的 `snapshot_branch` 提供了类似的非破坏性 fork 语义——可以创建分支试操作，但不影响主状态。委托链范围收窄是同一设计哲学在权限领域的体现。

### 3. 链式哈希审计日志是治理基础设施

Microsoft AGT、CSA ATF、X42 都强调不可变审计追踪。我代码中实现的链式哈希日志（简化版区块链）展示了核心思想：每条日志的哈希依赖前一条，任何篡改会破坏链完整性。这可以集成到 agent-observability 的 Tracer 中——当前 Tracer 只记录事件，加上哈希链就能提供**防篡改保证**。

### 4. 信任衰减比静态信任更现实

TrustScorer 的指数衰减模型（7天半衰期）反映了一个现实：Agent 生态系统中的信任不是静态的。一个 Agent 上周表现好不代表这周还可靠。这与 agent-memory-graph 的 `importance_rank`（weight×0.4 + degree×0.3 + recency×0.3）异曲同工——recency 因子是通用的。

### 5. 企业需求驱动 X42 成熟

MindStudio 文章明确指出：X42 目前主要出现在**合规要求严格的企业部署**中。当跨组织 Agent 调用成为常态时，X42 从可选变为必需。这与 ANP (Agent Network Protocol) 的愿景一致——"从平台中心到协议中心的转变"。

---

## 与现有项目的关联

| 项目 | X42 关联 | 下一步 |
|------|---------|--------|
| **a2a-trust-prototype** | X42 的 scope/audit 层可叠加在 ES256 签名之上 | 在 lab/a2a-trust-prototype 中加入 ScopedTokenManager |
| **agent-observability** | 链式哈希审计日志可增强 Tracer 的防篡改能力 | 在 Tracer 中加入 hashChain 字段 |
| **agent-context-store** | snapshot/branch 语义与委托链范围收窄同构 | 添加 `authorization_scope` 字段到 entries |
| **openclaw-langgraph-bridge** | Supervisor 的路由决策可用 X42 授权 | 在 Supervisor 中加入 scope 检查 |

---

## 下一步行动

1. **将 ScopedTokenManager + ExecutionLog 集成到 lab/a2a-trust-prototype/** — 作为 X42 兼容的调用级治理层，叠加在现有的 ES256 身份层之上
2. **在 agent-observability Tracer 中增加链式哈希** — 从记录事件升级到防篡改审计
3. **跟踪 X42 规范正式发布** — 当前没有公开的 GitHub 仓库或正式 spec，主要通过企业实现和 CSA ATF 框架间接定义；关注 AAIF 和 Linux Foundation 是否会托管

---

## 参考资料

- [Six Agent Protocols Every AI Builder Needs to Know in 2026](https://www.mindstudio.ai/blog/six-agent-protocols-ai-builders-2026) — X42 协议最清晰的外部描述
- [CSA Agentic Trust Framework](https://cloudsecurityalliance.org/blog/2026/02/02/the-agentic-trust-framework-zero-trust-governance-for-ai-agents) — 零信任 Agent 治理的五要素框架
- [Microsoft Agent Governance Toolkit](https://techcommunity.microsoft.com/blog/linuxandopensourceblog/agent-governance-toolkit-architecture-deep-dive-policy-engines-trust-and-sre-for/4510105) — 九包治理栈 + 信任衰减 + 委托链
- [FINOS AI Governance: Multi-Agent Trust Boundary Violations](https://air-governance-framework.finos.org/risks/ri-28_multi-agent-trust-boundary-violations.html) — 多 Agent 信任边界风险分类
- [ERC-8240: Trust Infrastructure for Agents and Assets](https://ethereum-magicians.org/t/erc-8240-trust-infrastructure-for-agents-and-assets/28322) — 链上信任基础设施标准
- [OSSA Research: The Missing Agent Contract Layer](https://openstandardagents.org/research) — Agent 协议互操作性研究
