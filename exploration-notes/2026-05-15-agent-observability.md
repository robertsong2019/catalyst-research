# Agent Observability: Tracer + PolicyEngine + Evaluator

> 研究日期: 2026-05-15 | 主题: LLM Agent 追踪、策略引擎与评估框架
> 关联项目: lab/agent-observability/ (HEARTBEAT 待办)

---

## 核心概念

### 1. Trace-Span 模型 (OpenTelemetry GenAI Semantic Conventions)
Agent 的每次执行生成一个 **Trace**（一次完整会话），包含多层 **Span**：
- `agent.run` — 根 Span，记录任务、模型、耗时
- `llm.call` — 每次 LLM 调用，记录 token、成本、延迟
- `tool.invoke` — 每次工具调用，记录输入/输出/状态

关键属性遵循 `gen_ai.*` 语义约定：`gen_ai.system`, `gen_ai.usage.input_tokens`, `gen_ai.response.finish_reason`。

### 2. 三层评估模型
```
Layer 1: Unit Eval    — 单个 tool/LLM 调用的断言测试
Layer 2: LLM-as-Judge — 用 LLM 给 agent 输出打分（正确性、安全性、风格）
Layer 3: Prod Sampling — 生产环境抽检 + 用户反馈
```

### 3. 策略引擎 (Policy Engine)
不是所有 trace 都要保留。策略引擎决定：
- **采样率** — 只保留有价值的 trace（错误、高延迟、低分）
- **数据脱敏** — PII 自动检测与掩码
- **成本阈值** — 单次运行超过 $X 触发告警
- **行为约束** — agent 连续调用同一工具 N 次触发熔断

### 4. Tail-Based Sampling
传统 APM 用 head-based sampling（请求进来就决定是否采样）。Agent observability 需要 **tail-based**：等整个 trace 完成后再决定是否保留，因为只有看到完整执行链才能判断是否有价值。

### 5. Cost Attribution
多租户/多 Agent 环境下，成本必须按 `user_id × agent_id × task_type` 归因，而非简单的 API key 级别汇总。

---

## 工具生态对比 (2026)

| 工具 | 类型 | 开源 | 适合场景 |
|------|------|------|---------|
| **Langfuse** | 全栈 tracing + eval | MIT | 自托管、数据自主、自定义 eval |
| **OpenLLMetry** | OTel 自动埋点 | Apache 2.0 | 已有 OTel 基础设施、多语言 |
| **Arize Phoenix** | 本地调试 | ELv2 | notebook 开发、快速调试 |
| **AgentOps** | SDK-first | 部分 | time-travel 调试、CrewAI |
| **LangSmith** | 托管 | 否 | LangChain 深度用户 |
| **Braintrust** | eval-first | 否 | eval + tracing 融合 |

**关键洞察**: OTel 已成为事实标准接口。最佳实践是 instrument against OTel，backend 可以随时切换（Langfuse ↔ Jaeger ↔ Datadog）。

---

## 可运行代码: 最小 Agent Observability 框架

```typescript
// agent-observability.ts — 最小可运行实现
// 运行: npx tsx agent-observability.ts (需要 Node 18+)

import { randomUUID } from "crypto";

// ============ Types ============

interface Span {
  id: string;
  traceId: string;
  parentId: string | null;
  name: string;
  kind: "agent" | "llm" | "tool";
  attributes: Record<string, any>;
  status: "ok" | "error";
  startMs: number;
  endMs: number | null;
}

interface Trace {
  id: string;
  spans: Map<string, Span>;
  rootSpanId: string;
}

interface Policy {
  name: string;
  check: (trace: Trace, spans: Span[]) => PolicyResult;
}

interface PolicyResult {
  pass: boolean;
  reason: string;
  severity: "info" | "warn" | "error";
}

interface EvalResult {
  score: number;       // 0-1
  label: string;
  reasoning: string;
}

// ============ Tracer ============

class Tracer {
  private traces = new Map<string, Trace>();
  private activeSpans = new Map<string, Span>();

  startTrace(name: string, attributes: Record<string, any> = {}): string {
    const traceId = randomUUID();
    const spanId = randomUUID();
    const span: Span = {
      id: spanId,
      traceId,
      parentId: null,
      name,
      kind: "agent",
      attributes,
      status: "ok",
      startMs: Date.now(),
      endMs: null,
    };
    const trace: Trace = { id: traceId, spans: new Map([[spanId, span]]), rootSpanId: spanId };
    this.traces.set(traceId, trace);
    this.activeSpans.set(spanId, span);
    return traceId;
  }

  startSpan(traceId: string, parentId: string, name: string, kind: Span["kind"], attributes: Record<string, any> = {}): string {
    const spanId = randomUUID();
    const span: Span = {
      id: spanId, traceId, parentId, name, kind, attributes,
      status: "ok", startMs: Date.now(), endMs: null,
    };
    const trace = this.traces.get(traceId);
    if (trace) trace.spans.set(spanId, span);
    this.activeSpans.set(spanId, span);
    return spanId;
  }

  endSpan(spanId: string, attributes?: Record<string, any>) {
    const span = this.activeSpans.get(spanId);
    if (!span) return;
    span.endMs = Date.now();
    if (attributes) Object.assign(span.attributes, attributes);
    this.activeSpans.delete(spanId);
  }

  getTrace(traceId: string): Trace | undefined {
    return this.traces.get(traceId);
  }

  /** Pretty-print trace as tree */
  printTrace(traceId: string): string {
    const trace = this.traces.get(traceId);
    if (!trace) return "Trace not found";
    const root = trace.spans.get(trace.rootSpanId)!;
    const lines: string[] = [];
    const buildTree = (span: Span, indent: string) => {
      const duration = span.endMs ? `${span.endMs - span.startMs}ms` : "running";
      const attrs = Object.entries(span.attributes)
        .filter(([k]) => k !== "input" && k !== "output")
        .map(([k, v]) => `${k}=${v}`)
        .join(", ");
      lines.push(`${indent}${span.kind}:${span.name} [${duration}] ${attrs ? `(${attrs})` : ""}`);
      for (const s of trace.spans.values()) {
        if (s.parentId === span.id) buildTree(s, indent + "  ├─");
      }
    };
    buildTree(root, "");
    return lines.join("\n");
  }
}

// ============ Policy Engine ============

class PolicyEngine {
  private policies: Policy[] = [];

  addPolicy(policy: Policy) { this.policies.push(policy); }

  evaluate(trace: Trace): PolicyResult[] {
    const spans = [...trace.spans.values()];
    return this.policies.map(p => p.check(trace, spans));
  }

  /** 内置策略: 循环检测 */
  static loopDetector(maxRepeated = 3): Policy {
    return {
      name: "loop-detector",
      check: (_, spans) => {
        const toolNames = spans.filter(s => s.kind === "tool").map(s => s.name);
        const counts = new Map<string, number>();
        for (const n of toolNames) counts.set(n, (counts.get(n) || 0) + 1);
        for (const [name, count] of counts) {
          if (count >= maxRepeated) {
            return { pass: false, reason: `Tool "${name}" called ${count} times (max: ${maxRepeated})`, severity: "error" };
          }
        }
        return { pass: true, reason: "No loops detected", severity: "info" };
      },
    };
  }

  /** 内置策略: 成本阈值 */
  static costThreshold(maxCost: number): Policy {
    return {
      name: "cost-threshold",
      check: (_, spans) => {
        const totalCost = spans
          .filter(s => s.kind === "llm")
          .reduce((sum, s) => sum + (s.attributes.cost || 0), 0);
        if (totalCost > maxCost) {
          return { pass: false, reason: `Total cost $${totalCost.toFixed(4)} exceeds $${maxCost}`, severity: "warn" };
        }
        return { pass: true, reason: `Cost $${totalCost.toFixed(4)} within limit`, severity: "info" };
      },
    };
  }

  /** 内置策略: 延迟阈值 */
  static latencyThreshold(maxMs: number): Policy {
    return {
      name: "latency-threshold",
      check: (_, spans) => {
        const root = spans.find(s => s.parentId === null);
        if (root && root.endMs && (root.endMs - root.startMs) > maxMs) {
          return { pass: false, reason: `Trace took ${root.endMs - root.startMs}ms (max: ${maxMs}ms)`, severity: "warn" };
        }
        return { pass: true, reason: "Latency within limits", severity: "info" };
      },
    };
  }
}

// ============ Evaluator (模拟 LLM-as-Judge) ============

class Evaluator {
  /** 评估 trace 的任务完成质量 */
  evaluate(trace: Trace): EvalResult {
    const spans = [...trace.spans.values()];
    const root = spans.find(s => s.parentId === null);
    const toolSpans = spans.filter(s => s.kind === "tool");
    const llmSpans = spans.filter(s => s.kind === "llm");
    const errors = spans.filter(s => s.status === "error");

    // 简化评分: 基于启发式规则（生产中用 LLM-as-Judge）
    let score = 1.0;
    const factors: string[] = [];

    // 错误惩罚
    if (errors.length > 0) {
      score -= 0.3 * errors.length;
      factors.push(`${errors.length} error(s) detected`);
    }

    // 工具成功率
    const toolFailures = toolSpans.filter(s => s.status === "error").length;
    if (toolSpans.length > 0 && toolFailures > 0) {
      score -= 0.2;
      factors.push(`Tool success rate: ${((1 - toolFailures / toolSpans.length) * 100).toFixed(0)}%`);
    }

    // 是否有输出
    if (root?.attributes.output) {
      factors.push("Has final output");
    } else {
      score -= 0.3;
      factors.push("No final output");
    }

    // Token 效率
    const totalTokens = llmSpans.reduce((s, sp) =>
      s + (sp.attributes.input_tokens || 0) + (sp.attributes.output_tokens || 0), 0);
    factors.push(`Total tokens: ${totalTokens}`);

    const label = score >= 0.8 ? "good" : score >= 0.5 ? "fair" : "poor";

    return { score: Math.max(0, score), label, reasoning: factors.join("; ") };
  }
}

// ============ Demo ============

function main() {
  const tracer = new Tracer();
  const engine = new PolicyEngine();
  const evaluator = new Evaluator();

  // 注册策略
  engine.addPolicy(PolicyEngine.loopDetector(3));
  engine.addPolicy(PolicyEngine.costThreshold(0.05));
  engine.addPolicy(PolicyEngine.latencyThreshold(10000));

  // 模拟一个 agent 运行
  const traceId = tracer.startTrace("research-agent", {
    task: "Find latest papers on agent observability",
    model: "gpt-4o",
  });

  // LLM 调用 1: 规划
  const llm1 = tracer.startSpan(traceId, tracer.getTrace(traceId)!.rootSpanId, "plan", "llm", {
    model: "gpt-4o", input_tokens: 245, output_tokens: 89, cost: 0.008,
  });
  // 模拟延迟
  tracer.endSpan(llm1, { output: "Step 1: Search, Step 2: Analyze" });

  // 工具调用 1: 搜索
  const tool1 = tracer.startSpan(traceId, llm1, "web_search", "tool", {
    query: "agent observability 2026",
  });
  tracer.endSpan(tool1, { result_count: 8 });

  // LLM 调用 2: 综合
  const rootSpanId = tracer.getTrace(traceId)!.rootSpanId;
  const llm2 = tracer.startSpan(traceId, rootSpanId, "synthesize", "llm", {
    model: "gpt-4o", input_tokens: 1200, output_tokens: 450, cost: 0.025,
  });
  tracer.endSpan(llm2, { output: "Key findings: OTel is standard, 3-layer eval model..." });

  // 结束 trace
  tracer.endSpan(tracer.getTrace(traceId)!.rootSpanId, {
    output: "Research complete: OTel + Langfuse recommended stack",
  });

  // 输出
  console.log("=== Trace Tree ===");
  console.log(tracer.printTrace(traceId));

  console.log("\n=== Policy Evaluation ===");
  const results = engine.evaluate(tracer.getTrace(traceId)!);
  for (const r of results) {
    const icon = r.pass ? "✅" : "❌";
    console.log(`${icon} [${r.severity}] ${r.reason}`);
  }

  console.log("\n=== Quality Score ===");
  const eval_ = evaluator.evaluate(tracer.getTrace(traceId)!);
  console.log(`Score: ${eval_.score.toFixed(2)} (${eval_.label})`);
  console.log(`Reasoning: ${eval_.reasoning}`);
}

main();
```

---

## 关键洞察

### 洞察 1: OTel 是正确的抽象层，但不是完整的解决方案
OpenTelemetry 提供了标准的 span/trace 模型和 `gen_ai.*` 语义约定，解决了**数据采集**问题。但 Agent Observability 的核心难题是**评估**（输出的质量，而非系统的可用性）。这需要一个独立的 Eval 层。

### 洞察 2: Tail-Based Sampling 是 Agent 场景的刚需
传统 APM 用 head-based sampling（请求进来就决定采样率）。Agent 的特点是：只有看到完整执行链才能判断 trace 是否有价值（比如中间某步出错导致最终结果差）。必须**等 trace 完成后再决定是否保留**。

### 洞察 3: 评估的三阶段成熟度模型是工程路线图
- Phase 1（开发期）: 手动查看 trace，理解 agent 行为 → **Tracer 足够**
- Phase 2（上线期）: LLM-as-Judge 自动评分 + 用户反馈 → **Evaluator 必须有**
- Phase 3（规模化）: 基准数据集 + 自动化回归测试 → **PolicyEngine 闭环**

### 洞察 4: Agent Observability ≠ LLM Observability
LLM Observability 关注单次 API 调用（latency, tokens, cost）。Agent Observability 关注**多步推理链**：规划是否合理？工具调用是否高效？是否陷入循环？最终目标是否达成？这是本质不同的抽象层级。

### 洞察 5: 自托管方案（Langfuse MIT）最适合 lab/ 阶段
对于 lab/agent-observability 原型，Langfuse 自托管 + OTel 语义约定是最佳组合：
- 数据完全本地，无需外部服务
- MIT 协议，无 vendor lock-in
- TypeScript SDK 原生支持
- 后续可无缝切换到其他 OTel backend

---

## 下一步行动

1. **创建 `lab/agent-observability/`** — 基于上述代码实现完整的 Tracer + PolicyEngine + Evaluator
   - Tracer: 基于 OTel 语义约定的 span 模型（上面的代码即为骨架）
   - PolicyEngine: 内置 loop-detector, cost-threshold, latency-threshold, PII-detector
   - Evaluator: 先用启发式规则，后续接入 LLM-as-Judge
   - 目标: 20+ tests, 零外部依赖

2. **研究 Langfuse TypeScript SDK 集成方式** — 确认 lab/ 版本是否需要 Langfuse exporter，还是纯自研更合适

3. **与 agent-context-store 对接** — namespace 隔离已就绪，observability 应该按 namespace 归因 trace
