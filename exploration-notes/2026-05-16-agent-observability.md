# Agent Observability: Tracer + PolicyEngine + Evaluator

> 研究日期: 2026-05-16
> 目标: 为 `lab/agent-observability` 项目奠定架构基础
> 方法: autoresearch — 明确指标、快速循环、积累性

---

## 核心概念 (5)

### 1. 结构化追踪 (Structured Tracing)
Agent 执行不是简单的 request-response，而是多步骤推理链。每个步骤（LLM调用、工具执行、记忆检索）都是一个 **span**，通过 parent-child 关系构成 trace。

关键 span 类型：
- `agent.execute` — 根 span，整个 agent 运行
- `agent.llm_step` — 单次 LLM 调用
- `agent.tool_call` — 工具调用
- `agent.retrieval` — RAG/记忆检索

### 2. OpenTelemetry 语义约定 (Semantic Conventions)
OTel 1.37+ 定义了 GenAI 语义约定：
- `gen_ai.system` — 提供商 (openai, anthropic, etc.)
- `gen_ai.request.model` — 模型名
- `gen_ai.usage.input_tokens` / `output_tokens` — token 计数
- `gen_ai.prompt.*` / `gen_ai.completion.*` — 输入输出内容

**关键洞察**: 使用标准语义约定意味着可以接入任何 OTel 后端（Jaeger、SigNoz、Datadog），不被锁定。

### 3. 在线评估 (Online Evaluation)
不是事后跑测试集，而是在生产流量上**采样评估**：
- 1-10% 的流量自动跑 LLM-as-Judge
- 评估维度: 准确性、安全性、相关性、工具使用正确性
- 失败 case 自动转为 eval 测试用例

### 4. 策略引擎 (PolicyEngine)
基于 trace 数据的实时策略检查：
- Token 预算限制（per-user, per-session）
- 工具调用白名单/黑名单
- 敏感信息检测 (PII leakage)
- 幻觉率阈值告警

### 5. 最小可行 Trace Schema
Braintrust 提出的 MVP schema：
```
Step {
  id: string
  type: 'llm' | 'tool' | 'retrieval' | 'reasoning'
  input: any
  output: any
  latency_ms: number
  tokens?: { input: number, output: number }
  error?: string
  metadata: Record<string, any>
}
```

---

## 代码示例: 最小 Agent Tracer (可运行)

```javascript
// agent-tracer.js — 零依赖的最小 Agent 追踪器
// Node.js >= 18 即可运行

class AgentTracer {
  constructor(agentName) {
    this.agentName = agentName;
    this.traces = [];
  }

  startTrace(input) {
    const trace = {
      id: crypto.randomUUID(),
      agent: this.agentName,
      input,
      steps: [],
      startedAt: Date.now(),
      status: 'running'
    };
    this.traces.push(trace);
    return trace.id;
  }

  addStep(traceId, type, input, output, metadata = {}) {
    const trace = this.traces.find(t => t.id === traceId);
    if (!trace) throw new Error(`Trace ${traceId} not found`);
    
    const step = {
      id: crypto.randomUUID(),
      type,        // 'llm' | 'tool' | 'retrieval' | 'reasoning'
      input,
      output,
      latency_ms: metadata.latency_ms || 0,
      tokens: metadata.tokens || null,
      error: metadata.error || null,
      timestamp: Date.now()
    };
    trace.steps.push(step);
    return step.id;
  }

  endTrace(traceId, output, error = null) {
    const trace = this.traces.find(t => t.id === traceId);
    if (!trace) throw new Error(`Trace ${traceId} not found`);
    
    trace.output = output;
    trace.error = error;
    trace.status = error ? 'failed' : 'completed';
    trace.duration_ms = Date.now() - trace.startedAt;
    return trace;
  }

  // 策略引擎 — 检查 trace 是否违反策略
  checkPolicies(traceId, policies) {
    const trace = this.traces.find(t => t.id === traceId);
    if (!trace) return [];
    
    const violations = [];
    for (const policy of policies) {
      const result = policy.check(trace);
      if (result.violated) violations.push(result);
    }
    return violations;
  }

  // 简单评估器
  evaluate(traceId, evaluator) {
    const trace = this.traces.find(t => t.id === traceId);
    if (!trace) return null;
    return evaluator(trace);
  }

  // 导出为 OTLP 兼容格式
  toOTLP(traceId) {
    const trace = this.traces.find(t => t.id === traceId);
    if (!trace) return null;
    
    return {
      resourceSpans: [{
        scopeSpans: [{
          spans: trace.steps.map(step => ({
            name: `${trace.agent}.${step.type}`,
            kind: 1, // INTERNAL
            startTimeUnixNano: `${step.timestamp}000000`,
            attributes: [
              { key: 'gen_ai.system', value: { stringValue: 'custom' } },
              { key: 'agent.step.type', value: { stringValue: step.type } },
              ...(step.tokens ? [
                { key: 'gen_ai.usage.input_tokens', value: { intValue: step.tokens.input } },
                { key: 'gen_ai.usage.output_tokens', value: { intValue: step.tokens.output } }
              ] : [])
            ]
          }))
        }]
      }]
    };
  }
}

// === 内置策略 ===
const policies = {
  maxTokens: (limit) => ({
    name: 'max_tokens',
    check: (trace) => {
      const total = trace.steps.reduce((sum, s) => 
        sum + (s.tokens?.input || 0) + (s.tokens?.output || 0), 0);
      return total > limit
        ? { violated: true, policy: 'max_tokens', detail: `${total} > ${limit}` }
        : { violated: false };
    }
  }),
  
  noPII: () => ({
    name: 'no_pii',
    check: (trace) => {
      // 简单检测: 邮箱、手机号
      const piiPattern = /[\w.-]+@[\w.-]+\.\w+|1[3-9]\d{9}/g;
      for (const step of trace.steps) {
        const input = JSON.stringify(step.input);
        const output = JSON.stringify(step.output);
        if (piiPattern.test(input) || piiPattern.test(output)) {
          return { violated: true, policy: 'no_pii', detail: 'PII detected in trace' };
        }
      }
      return { violated: false };
    }
  }),
  
  maxSteps: (limit) => ({
    name: 'max_steps',
    check: (trace) => trace.steps.length > limit
      ? { violated: true, policy: 'max_steps', detail: `${trace.steps.length} > ${limit}` }
      : { violated: false }
  })
};

// === 内置评估器 ===
const evaluators = {
  taskComplete: (trace) => ({
    name: 'task_completion',
    score: trace.status === 'completed' ? 1.0 : 0.0,
    detail: trace.error || 'Success'
  }),
  
  efficiency: (trace) => {
    const toolSteps = trace.steps.filter(s => s.type === 'tool').length;
    const llmSteps = trace.steps.filter(s => s.type === 'llm').length;
    return {
      name: 'efficiency',
      score: llmSteps > 0 ? Math.min(1.0, toolSteps / llmSteps) : 0,
      detail: `${toolSteps} tool calls / ${llmSteps} LLM calls`
    };
  },
  
  tokenEfficiency: (trace) => {
    const total = trace.steps.reduce((sum, s) =>
      sum + (s.tokens?.input || 0) + (s.tokens?.output || 0), 0);
    return {
      name: 'token_efficiency',
      score: total < 1000 ? 1.0 : total < 5000 ? 0.7 : total < 10000 ? 0.4 : 0.1,
      detail: `${total} tokens used`
    };
  }
};

// === 演示 ===
const tracer = new AgentTracer('research-agent');

// 模拟一次 agent 执行
const traceId = tracer.startTrace('研究 OpenTelemetry 最佳实践');

tracer.addStep(traceId, 'llm', 
  '搜索 OpenTelemetry agent tracing 的最佳实践',
  '找到了5个关键资源...',
  { latency_ms: 1200, tokens: { input: 45, output: 380 } }
);

tracer.addStep(traceId, 'tool',
  { name: 'web_search', query: 'OpenTelemetry agent tracing 2026' },
  { results: ['...'], count: 8 },
  { latency_ms: 800 }
);

tracer.addStep(traceId, 'llm',
  '总结搜索结果并提取关键洞察',
  '核心发现: 1) OTel 1.37+ GenAI语义约定...',
  { latency_ms: 2100, tokens: { input: 520, output: 450 } }
);

const trace = tracer.endTrace(traceId, '研究完成: 5个核心概念已整理');

// 策略检查
const activePolicies = [policies.maxTokens(5000), policies.noPII(), policies.maxSteps(10)];
const violations = tracer.checkPolicies(traceId, activePolicies);
console.log('📋 Policy violations:', violations.length ? violations : 'None ✅');

// 评估
const scores = [
  evaluators.taskComplete(trace),
  evaluators.efficiency(trace),
  evaluators.tokenEfficiency(trace)
];
console.log('📊 Evaluation scores:');
scores.forEach(s => console.log(`  ${s.name}: ${s.score} (${s.detail})`));

// OTLP 导出
const otlp = tracer.toOTLP(traceId);
console.log(`\n🔗 OTLP export: ${otlp.resourceSpans[0].scopeSpans[0].spans.length} spans`);
```

---

## 关键洞察 (5)

1. **Agent 可观测性 ≠ LLM 监控**: LLM 监控看单次调用；Agent 可观测性看整个推理链。关键差异在于多轮状态、工具调用、非确定性和复合错误。Datadog 的 APM 扩展不够——需要 agent-native 的方案。

2. **采样策略是核心 tradeoff**: 100% 追踪太贵，1% 采样会错过边界 case。生产最佳实践是分层采样：正常流量 1-5%，错误/慢请求 100%，新功能灰度期间 50%。

3. **OTel 语义约定是正确选择**: OTel 1.37+ GenAI 约定正在成为行业标准。用 OTLP 格式导出意味着可以接入任何后端。对于 `lab/agent-observability`，应该基于 OTel span 模型构建，而不是自定义格式。

4. **Eval 是第一公民**: 最佳工具（Braintrust、Langfuse、Opik）都将评估作为核心，不是附加功能。生产流程是: trace → 采样评估 → 失败 case 转测试用例 → CI 门控发布。`lab/agent-observability` 的 Evaluator 应该能同时跑在线和离线评估。

5. **从 50 行代码开始**: 最小可观测性只需要 tracer + 2-3 个策略 + 1-2 个评估器。不需要 OTel SDK 依赖，用纯 JS 对象模拟 span 模型就够了。上面的代码示例就是这个思路——零依赖、可运行、可扩展。

---

## 工具生态对比 (2026)

| 工具 | 特色 | 自托管 | 适合场景 |
|------|------|--------|----------|
| **Langfuse** | 开源、详细追踪、Prompt 管理 | ✅ | 全栈 observability |
| **Arize Phoenix** | OTel 原生、评估套件 | ✅ | 标准化追踪 |
| **Braintrust** | 结构化追踪+评估一体化 | ❌ | Eval-first 团队 |
| **Opik** | 全栈(追踪→评估→护栏) | ✅ Docker | 企业合规 |
| **LangSmith** | LangChain 最佳集成 | ❌ | LangGraph 项目 |

**对 lab/agent-observability 的建议**: 不依赖任何外部平台。构建纯 JS 的 Tracer + PolicyEngine + Evaluator，通过 OTLP exporter 可选接入外部后端。

---

## 下一步行动

1. **创建 `lab/agent-observability/`** — 基于上面的 AgentTracer 设计，用 TypeScript 实现完整版
   - `Tracer` — span 模型 + trace 生命周期管理
   - `PolicyEngine` — 可组合的策略检查器（token预算、PII、步数限制、工具白名单）
   - `Evaluator` — LLM-as-Judge + 规则评估 + 人类标注接口
   - `OTLPExporter` — 导出为标准 OTLP 格式

2. **测试目标**: 首次提交应有 ≥15 个测试覆盖核心路径

3. **与现有项目集成**: 考虑将 Tracer 接入 `agent-context-store` 和 `better-ralph-core` 的执行循环

---

## 来源

- [OpenTelemetry 官方: AI Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [Braintrust: Agent Observability Complete Guide 2026](https://www.braintrust.dev/articles/agent-observability-complete-guide-2026)
- [TokenMix: LLM Observability 2026 Tools & Best Practices](https://tokenmix.ai/blog/llm-observability-2026-tools-best-practices)
- [OTel Agent Tracing 实践](https://oneuptime.com/blog/post/2026-02-06-trace-ai-agent/executions-flows-opentelemetry/view)
- [LangSmith: Evaluate with OpenTelemetry](https://docs.langchain.com/langsmith/evaluate-with-opentelemetry)
