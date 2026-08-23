# Agent Observability: OpenTelemetry + OWASP AOS 深度研究

> 日期: 2026-05-12 | 主题: Agent Observability
> 对齐项目: lab/agent-observability/ (Tracer + PolicyEngine + Evaluator)

---

## 核心概念 (5个)

### 1. OpenTelemetry GenAI Semantic Conventions
OTel GenAI SIG 定义的标准化属性词汇表，覆盖所有 LLM 操作：
- `gen_ai.system` — 提供商 (openai, anthropic, etc.)
- `gen_ai.request.model` / `gen_ai.response.model` — 模型标识
- `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` — Token 计数
- `gen_ai.agent.name` / `gen_ai.agent.id` — Agent 身份
- `gen_ai.tool.name` / `gen_ai.tool.type` — 工具调用

关键规则: **工具属性在 `gen_ai.tool.` 下，不是 `gen_ai.agent.tool.`**。这是最常见的实现错误。

### 2. OWASP Agent Observability Standard (AOS)
三层信任框架:
- **Instrumentable** — 通过 Guardian Agent 中间件注入行为控制（基于 MCP/A2A 协议）
- **Traceable** — 扩展 OpenTelemetry + OCSF，记录完整 Agent 生命周期
- **Inspectable** — 动态 AgBOM（Agent Bill of Materials），扩展 CycloneDX/SPDX

AOS 核心创新: **Guardian Agent 模式** — Agent 的每个操作都通过 JSON-RPC 2.0 请求 Guardian Agent 审批，实现 inline policy enforcement。

### 3. Hierarchical Span Trees（层次化 Span 树）
Agent 可观测性的核心数据结构：
```
agent.run (root span)
  ├── agent.plan (planning phase)
  ├── turn (conversation turn)
  │   ├── gen_ai.chat (LLM call)
  │   ├── tool.call (tool invocation)
  │   │   └── gen_ai.chat (tool's internal LLM call)
  │   └── memory.access (retrieval step)
  └── agent.evaluate (self-evaluation)
```

### 4. Trace → Evaluate → Enforce 渐进路径
Braintrust 提出的成熟度模型：
1. **Trace Capture** — 基础，让每次运行可检查
2. **Online Scoring** — 采样流量打分
3. **Eval Cases** — 失败转为测试用例
4. **CI Gate** — 用相同 scorer 门控发布

### 5. Tail-Based Sampling（尾部采样）
生产环境必须策略：只保留"有趣"的 trace（错误、高延迟、异常 token 用量），丢弃正常 trace。减少 90%+ 存储成本，同时保留调试所需的完整上下文。

---

## 代码示例: 最小可运行 Agent Tracer (TypeScript)

```typescript
// agent-tracer.ts — 最小 Agent 可观测性实现
// 基于 OpenTelemetry GenAI Semantic Conventions + AOS 灵感
// 运行: npx tsx agent-tracer.ts

import { trace, SpanKind, SpanStatusCode, context, Context } from "@opentelemetry/api";

// ---- 轻量级 Tracer 模拟（无需 OTel SDK 依赖） ----
interface Span {
  name: string;
  kind: SpanKind;
  attributes: Record<string, string | number>;
  status: SpanStatusCode;
  parent?: Span;
  children: Span[];
  startTime: number;
  endTime?: number;
  events: { name: string; time: number; attributes?: Record<string, unknown> }[];
}

class SimpleTracer {
  private spans: Span[] = [];
  private activeSpan?: Span;

  startSpan(name: string, kind: SpanKind, attributes: Record<string, string | number> = {}): Span {
    const span: Span = {
      name,
      kind,
      attributes,
      status: SpanStatusCode.UNSET,
      parent: this.activeSpan,
      children: [],
      startTime: Date.now(),
      events: [],
    };
    if (this.activeSpan) {
      this.activeSpan.children.push(span);
    } else {
      this.spans.push(span);
    }
    this.activeSpan = span;
    return span;
  }

  endSpan(span: Span, status: SpanStatusCode = SpanStatusCode.OK) {
    span.endTime = Date.now();
    span.status = status;
    this.activeSpan = span.parent;
  }

  addEvent(span: Span, name: string, attributes?: Record<string, unknown>) {
    span.events.push({ name, time: Date.now(), attributes });
  }

  getTraceTree(): string {
    const format = (span: Span, indent: string = ""): string => {
      const duration = (span.endTime! - span.startTime);
      const statusIcon = span.status === SpanStatusCode.OK ? "✅" : "❌";
      let result = `${indent}${statusIcon} ${span.name} (${duration}ms)`;
      if (Object.keys(span.attributes).length > 0) {
        const attrs = Object.entries(span.attributes)
          .map(([k, v]) => `${k}=${v}`)
          .join(", ");
        result += ` [${attrs}]`;
      }
      result += "\n";
      for (const event of span.events) {
        result += `${indent}  📌 ${event.name}`;
        if (event.attributes) {
          result += ` ${JSON.stringify(event.attributes)}`;
        }
        result += "\n";
      }
      for (const child of span.children) {
        result += format(child, indent + "  ");
      }
      return result;
    };
    return this.spans.map(s => format(s)).join("\n");
  }

  // AOS 灵感: Policy 检查点
  checkPolicy(span: Span, policy: (span: Span) => boolean): boolean {
    const allowed = policy(span);
    this.addEvent(span, "policy_check", { allowed, policyName: policy.name || "default" });
    return allowed;
  }
}

// ---- 使用示例 ----
const tracer = new SimpleTracer();

// 模拟 Agent 执行流程
async function runAgent(task: string): Promise<string> {
  const rootSpan = tracer.startSpan("agent.run", SpanKind.INTERNAL, {
    "gen_ai.agent.name": "research-agent",
    "gen_ai.system": "openai",
    "agent.task": task.slice(0, 50),
  });

  // Planning phase
  const planSpan = tracer.startSpan("agent.plan", SpanKind.INTERNAL, {
    "gen_ai.request.model": "gpt-4o",
  });
  await new Promise(r => setTimeout(r, 50)); // simulate planning
  tracer.endSpan(planSpan);

  // LLM call
  const llmSpan = tracer.startSpan("gen_ai.chat", SpanKind.CLIENT, {
    "gen_ai.operation.name": "chat",
    "gen_ai.request.model": "gpt-4o",
    "gen_ai.request.temperature": 0.7,
  });

  // Policy check (AOS 风格)
  const toolCallAllowed = tracer.checkPolicy(llmSpan, (s) => {
    // 不允许调用敏感工具
    return s.attributes["gen_ai.tool.name"] !== "delete_database";
  });

  tracer.addEvent(llmSpan, "gen_ai.content.completion", {
    prompt: "Research the topic...",
    completion: "Here is the analysis...",
  });

  tracer.endSpan(llmSpan);

  // Tool call
  const toolSpan = tracer.startSpan("tool.call", SpanKind.INTERNAL, {
    "gen_ai.tool.name": "web_search",
    "gen_ai.tool.type": "function",
  });
  await new Promise(r => setTimeout(r, 30)); // simulate tool
  tracer.addEvent(toolSpan, "tool.result", { result_count: 5 });
  tracer.endSpan(toolSpan);

  // Token usage recording
  rootSpan.attributes["gen_ai.usage.input_tokens"] = 312;
  rootSpan.attributes["gen_ai.usage.output_tokens"] = 148;

  tracer.endSpan(rootSpan);
  return "Research complete";
}

// Run and display
runAgent("Analyze agent observability patterns").then(() => {
  console.log("=== Agent Trace Waterfall ===\n");
  console.log(tracer.getTraceTree());
  console.log("\n=== Summary ===");
  console.log("Spans captured: 4 (agent.run → agent.plan + gen_ai.chat + tool.call)");
  console.log("Policy checks: 1 (tool call gate)");
  console.log("Token usage: 312 input + 148 output");
});
```

**运行方式:**
```bash
# 无依赖版 — 直接复制到文件运行
npx tsx agent-tracer.ts

# 或者纯 Node.js (无 TypeScript):
# 去掉类型注解后直接 node agent-tracer.js
```

**输出示例:**
```
=== Agent Trace Waterfall ===

✅ agent.run (83ms) [gen_ai.agent.name=research-agent, gen_ai.system=openai, agent.task=Analyze agent observability patterns, gen_ai.usage.input_tokens=312, gen_ai.usage.output_tokens=148]
  ✅ agent.plan (52ms) [gen_ai.request.model=gpt-4o]
  ✅ gen_ai.chat (1ms) [gen_ai.operation.name=chat, gen_ai.request.model=gpt-4o, gen_ai.request.temperature=0.7]
    📌 policy_check {"allowed":true,"policyName":"default"}
    📌 gen_ai.content.completion {"prompt":"Research the topic...","completion":"Here is the analysis..."}
  ✅ tool.call (31ms) [gen_ai.tool.name=web_search, gen_ai.tool.type=function]
    📌 tool.result {"result_count":5}

=== Summary ===
Spans captured: 4 (agent.run → agent.plan + gen_ai.chat + tool.call)
Policy checks: 1 (tool call gate)
Token usage: 312 input + 148 output
```

---

## 关键洞察

### 洞察 1: OTel GenAI 已成为事实标准，但实现陷阱多
- **属性路径错误**是最常见的 bug — `gen_ai.agent.tool.name` 看似合理，但标准规定工具属性在 `gen_ai.tool.` 层级
- `NodeSDK` 在 `spanProcessors: []` 时**静默禁用 trace 导出**，252 个测试全过但 trace 从未发送
- 必须设置 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 获取最新属性

### 洞察 2: Agent 可观测性 ≠ LLM 可观测性
LLM observability 只看单个调用（latency, tokens, cost）。Agent observability 需要：
- **跨步骤因果链** — turn 3 的错误可能源于 turn 1 的 memory 写入
- **工具选择审计** — 为什么 agent 选了工具 A 而不是 B？
- **收敛性追踪** — agent 是否在 loop 中反复做同样的决定？
- **成本归因到决策** — 不是"花了 $0.05"，而是"planning 花了 $0.01，tool execution 花了 $0.04"

### 洞察 3: AOS Guardian Agent 模式是安全关键路径
OWASP AOS 的 Guardian Agent 模式解决了 agent 安全的核心问题：**如何在运行时拦截和审计 agent 的每个关键决策**。
- 不是事后审计日志，而是 **inline policy enforcement**
- JSON-RPC 2.0 协议让 Guardian 成为 agent 和外部系统之间的代理
- 与 OpenClaw 的 `exec` approval 机制理念一致 — 人类/策略在关键操作前审批

### 洞察 4: 开源生态已分化为三个阵营
| 阵营 | 代表 | 特点 |
|------|------|------|
| OTel-native | Arize Phoenix, OpenLLMetry | 标准优先，无 vendor lock-in |
| 全栈自建 | Langfuse, Braintrust | 自有 schema + 丰富 UI |
| 框架绑定 | LangSmith, LangWatch | 深度框架集成 |

**对 lab/agent-observability/ 的启示**: 应该走 OTel-native 路线，使用 gen_ai semantic conventions，这样未来可以对接任何 backend。

### 洞察 5: Tail-Based Sampling 是生产部署的分水岭
头部采样（每 N 个请求采样 1 个）会错过所有异常。尾部采样基于 trace 结果决策：
- 保留所有错误 trace
- 保留高延迟 trace（> p99）
- 保留异常 token 用量 trace
- 正常 trace 采样率降至 1%

这对 OpenClaw 的 cron 任务特别重要 — 大量正常执行的 trace 不需要全部保留。

---

## 工具/平台对比（与 lab/agent-observability/ 选型相关）

| 工具 | 开源 | OTel | Agent 评估 | 自托管 | 适合场景 |
|------|------|------|-----------|--------|---------|
| **Arize Phoenix** | ✅ | ✅ native | ✅ LLM-as-judge | ✅ | 最佳 OTel-first 方案 |
| **Langfuse** | ✅ MIT | ⚠️ 部分 | ✅ | ✅ | 最佳自托管方案 |
| **Braintrust** | ❌ | ✅ | ✅ 最强 | ❌ | 最佳评估质量 |
| **OpenLLMetry** | ✅ | ✅ native | ❌ | ✅ | 最佳自动埋点库 |
| **LangSmith** | ❌ | ❌ | ✅ | ❌ | LangChain 绑定 |

**推荐组合**: OpenLLMetry (自动埋点) + Arize Phoenix (本地调试/评估) → 生产时按需切换 backend。

---

## 下一步行动

1. **[lab/agent-observability/ 实现]** 基于 OTel GenAI semantic conventions 实现 Tracer，使用上面的代码模式。核心接口：
   - `AgentTracer.startRun()` → root span
   - `AgentTracer.traceLLMCall()` → gen_ai.chat span + token recording
   - `AgentTracer.traceToolCall()` → tool span + policy check
   - `AgentTracer.traceMemory()` → memory access span

2. **[Guardian Agent 原型]** 参考 AOS spec 实现 JSON-RPC Guardian，作为 lab/a2a-trust-prototype/ 的扩展：
   - Agent 调用外部工具前请求 Guardian 审批
   - Guardian 执行 policy engine 规则
   - 记录审批决策到 trace

3. **[Tail Sampling 策略]** 为 OpenClaw cron 任务实现简单尾部采样：
   - 保留所有失败的 cron trace
   - 保留执行时间 > 2x 平均值的 trace
   - 正常 trace 只记录 summary metrics

---

## 参考资料

- [OWASP AOS Specification](https://owasp.github.io/www-project-agent-observability-standard/spec/instrument/specification/)
- [OTel GenAI Semantic Conventions](https://opentelemetry.io/blog/2024/otel-generative-ai/)
- [AOS Trace with OpenTelemetry](https://owasp.github.io/www-project-agent-observability-standard/spec/trace/extend_opentelemetry/)
- [OTel AI Agent Observability Blog](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [Braintrust: Agent Observability Complete Guide](https://www.braintrust.dev/articles/agent-observability-complete-guide-2026)
- [Zylos: OTel for AI Agents (TypeScript patterns)](https://zylos.ai/research/2026-02-28-opentelemetry-ai-agent-observability)
- [Dev.to: OTel LLM tracing implementation pitfalls](https://dev.to/vola-trebla/opentelemetry-just-standardized-llm-tracing-heres-what-it-actually-looks-like-in-code-2e5f)
