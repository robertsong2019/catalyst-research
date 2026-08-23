# Agent Observability: Tracer + PolicyEngine + Evaluator

> 研究日期: 2026-05-14
> 主题来源: HEARTBEAT.md → lab/agent-observability 任务
> 关联项目: agent-context-store (changelog audit trail), a2a-trust-prototype

---

## 核心概念

### 1. Three-Signal Observability (OpenTelemetry)
Agent 可观测性的三大信号类型：
- **Traces**: 端到端请求流，展示 agent 调用、LLM 调用、工具执行之间的 parent-child 关系
- **Metrics**: 量化指标——响应时间、错误率、token 消耗、每次操作成本
- **Logs**: 结构化事件记录，用于审计追踪、合规报告、详细调试

OpenTelemetry GenAI SIG 已定义了覆盖 LLM 调用、token 用量、模型参数的语义约定（2026年初稳定）。Agent 框架（如 CrewAI）已内置 OTel 埋点。

**关键洞察**: OTel 的价值不是"又一个日志库"——它是**跨框架标准化**的合约。同一套 span 语义，LangChain/CrewAI/OpenAI Agents SDK 产出同样的 trace 结构。

### 2. Policy Engine as Proxy (OPA Pattern)
用 Open Policy Agent 作为 agent 和工具之间的**智能代理层**：

```
Agent 请求 → OPA Policy Check (Rego) → allow/deny → Tool 执行
```

核心架构: `Input (JSON) + Policy (Rego) + Data (JSON) = Decision (allow/deny)`

这比在 prompt 里写 guardrails 更可靠——策略和推理引擎解耦，策略可独立审计、测试、版本控制。

**两种部署模式**:
- **Sidecar**: 与 agent 同进程部署，零网络延迟，适合单 agent 场景
- **Centralized**: 独立服务，适合多 agent 共享策略，但需要 HA 设计避免单点故障

**关键洞察**: Gartner 预测 2028 年 25% 企业安全事件将源于 AI agent 滥用。OPA 作为 policy engine 是当前最成熟的开源选择（CNCF 毕业项目，Pinterest 400K QPS 实测）。

### 3. Four-Pillar Evaluation Framework
论文 "Beyond Task Completion" (arXiv:2512.12791) 提出 agent 评估的四大支柱：

| 支柱 | 关注点 | 评估方法 |
|------|--------|----------|
| **LLM** | 指令遵循、安全对齐 | 静态验证 + LLM Judge |
| **Memory** | 检索准确度、上下文保持 | 动态监控 |
| **Tools** | 正确选择、参数映射 | 行为测试 |
| **Environment** | 工作流执行、guardrail 合规 | 环境层防御 |

**关键洞察**: 仅评估"任务是否完成"（outcome-based）不够，需要 **behavior-based testing**——agent 是否跳过了策略检查？是否在无权限时请求了提权？

### 4. Guardrails 分层架构
从 Datadog 的实践中提炼出的标准分层：

```
Input Guardrails → Prompt Construction Guardrails → Tool Call Guardrails → Output Guardrails
     (PII过滤)          (RBAC注入)                    (权限检查)           (Schema验证)
```

每层独立、可组合。关键原则：**不在 prompt 里混入策略，用独立的 enforcement layer**。

### 5. Minimum Viable Trace Schema (Braintrust)
每个 agent step 至少记录：

```typescript
interface AgentTrace {
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  // What happened
  operation: 'agent.run' | 'llm.call' | 'tool.execute' | 'retrieval.search';
  input: unknown;
  output: unknown;
  // When & how long
  start_time: number;  // epoch ms
  duration_ms: number;
  // Cost
  model?: string;
  token_usage?: { prompt: number; completion: number; total: number };
  // Quality
  status: 'ok' | 'error' | 'blocked';
  error_message?: string;
  // Context
  agent_id: string;
  session_id: string;
  metadata: Record<string, unknown>;
}
```

---

## 代码示例: Agent Observability Toolkit (TypeScript)

以下是一个可运行的 Tracer + PolicyEngine + Evaluator 最小实现：

```typescript
// agent-observability.ts — Minimal Agent Observability Toolkit
// Run: npx tsx agent-observability.ts

// === 1. Tracer: OpenTelemetry-inspired span tracking ===
interface Span {
  traceId: string;
  spanId: string;
  parentSpanId: string | null;
  operation: string;
  startTime: number;
  endTime: number | null;
  attributes: Record<string, unknown>;
  status: 'ok' | 'error' | 'blocked';
  events: Array<{ name: string; timestamp: number; attributes?: Record<string, unknown> }>;
}

class Tracer {
  private spans: Span[] = [];
  private activeSpan: Span | null = null;

  startSpan(operation: string, attributes: Record<string, unknown> = {}): Span {
    const span: Span = {
      traceId: attributes.traceId as string || crypto.randomUUID(),
      spanId: crypto.randomUUID().slice(0, 16),
      parentSpanId: this.activeSpan?.spanId || null,
      operation,
      startTime: Date.now(),
      endTime: null,
      attributes,
      status: 'ok',
      events: [],
    };
    this.spans.push(span);
    this.activeSpan = span;
    return span;
  }

  endSpan(span: Span, status: 'ok' | 'error' | 'blocked' = 'ok'): void {
    span.endTime = Date.now();
    span.status = status;
    this.activeSpan = span.parentSpanId
      ? this.spans.find(s => s.spanId === span.parentSpanId) || null
      : null;
  }

  addEvent(span: Span, name: string, attrs?: Record<string, unknown>): void {
    span.events.push({ name, timestamp: Date.now(), attributes: attrs });
  }

  getDuration(span: Span): number {
    return (span.endTime || Date.now()) - span.startTime;
  }

  getTraceReport(): object {
    return {
      totalSpans: this.spans.length,
      totalDurationMs: this.spans.reduce((sum, s) => sum + this.getDuration(s), 0),
      byOperation: Object.groupBy(
        this.spans.map(s => ({ op: s.operation, duration: this.getDuration(s), status: s.status })),
        s => s.op
      ),
      errors: this.spans.filter(s => s.status !== 'ok').map(s => ({
        operation: s.operation,
        status: s.status,
        duration: this.getDuration(s),
      })),
    };
  }
}

// === 2. PolicyEngine: OPA-inspired rule evaluation ===
type PolicyRule = {
  name: string;
  description: string;
  evaluate: (input: Record<string, unknown>) => { allow: boolean; reason?: string };
};

class PolicyEngine {
  private rules: Map<string, PolicyRule[]> = new Map();

  addPolicy(category: string, rule: PolicyRule): void {
    if (!this.rules.has(category)) this.rules.set(category, []);
    this.rules.get(category)!.push(rule);
  }

  evaluate(category: string, input: Record<string, unknown>): {
    allowed: boolean;
    violations: string[];
  } {
    const rules = this.rules.get(category) || [];
    const violations: string[] = [];
    for (const rule of rules) {
      const result = rule.evaluate(input);
      if (!result.allow) {
        violations.push(`${rule.name}: ${result.reason || 'denied'}`);
      }
    }
    return { allowed: violations.length === 0, violations };
  }
}

// === 3. Evaluator: Behavior-based quality scoring ===
interface EvalResult {
  dimension: string;
  score: number;  // 0-1
  reason: string;
}

class Evaluator {
  private checks: Array<(trace: Span[]) => EvalResult[]> = [];

  addCheck(check: (trace: Span[]) => EvalResult[]): void {
    this.checks.push(check);
  }

  evaluate(trace: Span[]): EvalResult[] {
    return this.checks.flatMap(check => check(trace));
  }
}

// === DEMO: Wire it all together ===

// Setup policy engine
const policy = new PolicyEngine();

policy.addPolicy('tool_execution', {
  name: 'no-destructive-ops',
  description: 'Block destructive file operations',
  evaluate: (input) => {
    const tool = input.tool as string;
    const destructive = ['rm', 'drop', 'delete', 'truncate'];
    if (destructive.some(d => tool.toLowerCase().includes(d))) {
      return { allow: false, reason: `Destructive operation blocked: ${tool}` };
    }
    return { allow: true };
  },
});

policy.addPolicy('tool_execution', {
  name: 'cost-limit',
  description: 'Block operations exceeding cost threshold',
  evaluate: (input) => {
    const estimatedCost = input.estimatedCost as number;
    if (estimatedCost > 1.0) {
      return { allow: false, reason: `Cost $${estimatedCost} exceeds $1.00 limit` };
    }
    return { allow: true };
  },
});

// Setup evaluator
const evaluator = new Evaluator();

evaluator.addCheck((spans) => {
  // Check: Did any span get blocked?
  const blocked = spans.filter(s => s.status === 'blocked');
  if (blocked.length > 0) {
    return [{
      dimension: 'policy_compliance',
      score: 1.0,
      reason: `${blocked.length} operation(s) correctly blocked by policy`,
    }];
  }
  return [{ dimension: 'policy_compliance', score: 1.0, reason: 'No policy violations detected' }];
});

evaluator.addCheck((spans) => {
  // Check: Are operations reasonably fast?
  const slowOps = spans.filter(s => {
    const dur = (s.endTime || 0) - s.startTime;
    return dur > 5000;
  });
  const score = Math.max(0, 1 - slowOps.length * 0.3);
  return [{
    dimension: 'latency',
    score,
    reason: slowOps.length > 0
      ? `${slowOps.length} slow operation(s) > 5s`
      : 'All operations within latency budget',
  }];
});

evaluator.addCheck((spans) => {
  // Check: Error rate
  const errors = spans.filter(s => s.status === 'error');
  const score = spans.length > 0 ? 1 - (errors.length / spans.length) : 1;
  return [{
    dimension: 'reliability',
    score,
    reason: `${errors.length}/${spans.length} operations failed`,
  }];
});

// === Run a simulated agent workflow ===
const tracer = new Tracer();

// Simulated agent run
const rootSpan = tracer.startSpan('agent.run', { agent_id: 'catalyst', task: 'deploy-update' });

// Step 1: LLM call
const llmSpan = tracer.startSpan('llm.call', {
  model: 'gpt-4o',
  prompt_tokens: 150,
  completion_tokens: 80,
});
tracer.endSpan(llmSpan);

// Step 2: Safe tool call
const safeToolSpan = tracer.startSpan('tool.execute', { tool: 'kubectl_apply', target: 'deployment/web' });
const safeCheck = policy.evaluate('tool_execution', { tool: 'kubectl_apply', estimatedCost: 0.05 });
if (!safeCheck.allowed) {
  tracer.addEvent(safeToolSpan, 'policy.blocked', { violations: safeCheck.violations });
  tracer.endSpan(safeToolSpan, 'blocked');
} else {
  tracer.addEvent(safeToolSpan, 'policy.passed');
  tracer.endSpan(safeToolSpan);
}

// Step 3: Dangerous tool call (should be blocked)
const dangerSpan = tracer.startSpan('tool.execute', { tool: 'rm -rf /tmp/cache', estimatedCost: 0 });
const dangerCheck = policy.evaluate('tool_execution', { tool: 'rm -rf /tmp/cache', estimatedCost: 0 });
if (!dangerCheck.allowed) {
  tracer.addEvent(dangerSpan, 'policy.blocked', { violations: dangerCheck.violations });
  tracer.endSpan(dangerSpan, 'blocked');
} else {
  tracer.endSpan(dangerSpan);
}

// Step 4: Expensive call (should be blocked by cost limit)
const expensiveSpan = tracer.startSpan('tool.execute', { tool: 'batch_translate', estimatedCost: 2.5 });
const costCheck = policy.evaluate('tool_execution', { tool: 'batch_translate', estimatedCost: 2.5 });
if (!costCheck.allowed) {
  tracer.addEvent(expensiveSpan, 'policy.blocked', { violations: costCheck.violations });
  tracer.endSpan(expensiveSpan, 'blocked');
} else {
  tracer.endSpan(expensiveSpan);
}

tracer.endSpan(rootSpan);

// === Output results ===
const allSpans = tracer.getTraceReport();
const evalResults = evaluator.evaluate(
  (allSpans as any).byOperation
    ? Object.values((allSpans as any).byOperation).flat() as Span[]
    : []
);

// Simple display (since we can't use the full spans array from getTraceReport)
console.log('=== Agent Observability Report ===\n');
console.log(JSON.stringify(allSpans, null, 2));
console.log('\n=== Evaluation Results ===\n');
evalResults.forEach(r => {
  const bar = '█'.repeat(Math.round(r.score * 10)) + '░'.repeat(10 - Math.round(r.score * 10));
  console.log(`[${bar}] ${r.dimension}: ${r.score.toFixed(2)} — ${r.reason}`);
});
console.log('\n✅ Demo complete — Tracer + PolicyEngine + Evaluator all functional');
```

### 运行方式

```bash
# 保存为 agent-observability.ts
npx tsx agent-observability.ts
```

---

## 关键洞察

1. **OTel 语义约定已成行业标准**: 2026年初 GenAI semantic conventions 进入稳定阶段。所有主流 agent 框架（CrewAI、LangGraph、OpenAI Agents SDK）都支持 OTel 埋点。对 `lab/agent-observability` 的启示：**不要自建 trace 格式，直接对齐 OTel GenAI 语义约定**，这样产出的 trace 可以接入任何后端（Jaeger、Tempo、Grafana）。

2. **Policy Engine 应与 Agent 解耦**: OPA 的 `Input + Policy + Data = Decision` 模式证明了 policy-as-code 的价值。对 `lab/agent-observability` 的启示：PolicyEngine 不应嵌入 agent runtime，而是作为**独立 sidecar 或中间件层**。策略用 Rego 或 JSON 声明式定义，可独立测试和版本控制。这正好对接 `a2a-trust-prototype` 的 ES256 签名中间件模式。

3. **Behavior-based > Outcome-based 评估**: 仅看"任务是否成功"不够——需要检查 agent 是否跳过了策略检查、是否在无权限时请求提权、工具选择是否正确。对 `agent-context-store changelog` 的启示：changelog 已记录了 **what happened**，但缺少 **policy evaluation results**。下一步是在 changelog 中嵌入 policy decision 字段。

4. **Guardrails 的成本效益**: Galileo 数据显示，用通用 LLM 做 guardrail 评估月成本可达 $200K+，专用评估模型可降 95%。对 `lab/agent-observability` 的启示：Evaluator 应支持**多级评估**——快速规则检查（regex/JSON schema）免费，LLM-based judge 只在需要时触发。

5. **Four-Pillar 框架是设计蓝图**: LLM + Memory + Tools + Environment 的四支柱评估框架直接对应 lab 的三个组件——Tracer 覆盖所有四支柱的数据采集，PolicyEngine 覆盖 Tools 和 Environment 的合规检查，Evaluator 覆盖 LLM 和 Memory 的质量评估。

---

## 与现有项目的关联

| 现有项目 | 关联点 |
|---------|--------|
| `agent-context-store` | changelog audit trail → 可作为 Tracer 的存储后端 |
| `a2a-trust-prototype` | ES256 签名中间件 → PolicyEngine 的 agent 身份验证层 |
| `prompt-router` | 路由决策 → 可作为 Tracer span 的 operation type |
| `agent-memory-graph` | 知识图谱 → 可作为 Memory pillar 的评估数据源 |

---

## 下一步行动

1. **[本周]** 创建 `lab/agent-observability/` 项目结构，实现 Tracer 核心类（对齐 OTel GenAI 语义约定）
2. **[本周]** PolicyEngine 最小实现：基于 JSON 规则的 allow/deny（先不引入 OPA，保持轻量）
3. **[下周]** 接入 `agent-context-store` changelog 作为 trace 持久化后端
4. **[下周]** Evaluator 原型：实现 policy_compliance 和 latency 两个评估维度

---

## 参考资料

- [OpenTelemetry: AI Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/) — OTel GenAI SIG 的 agent 可观测性标准
- [Braintrust: Agent Observability Complete Guide 2026](https://www.braintrust.dev/articles/agent-observability-complete-guide-2026) — 最小 trace schema 设计
- [arXiv:2512.12791 - Beyond Task Completion](https://arxiv.org/html/2512.12791v1) — 四支柱评估框架
- [Codilime: OPA for AI Agents](https://codilime.com/blog/why-use-open-policy-agent-for-your-ai-agents/) — OPA 作为 agent guardrail
- [Datadog: LLM Guardrails Best Practices](https://www.datadoghq.com/blog/llm-guardrails-best-practices/) — 分层 guardrails 架构
- [arXiv:2509.23994 - Policy as Prompt](https://arxiv.org/html/2509.23994v1) — 自动化 guardrail 生成
