# Agent Observability & Evaluation — 2026 深度研究

> 日期: 2026-05-10 | 主题: AI Agent 可观测性与评估框架
> 触发: 研究积累已饱和，选择治理层（observability + evals）作为新方向

---

## 核心概念 (5个)

### 1. Agent Trace（结构化轨迹）
Agent 执行的完整记录：每一步的工具选择、参数、返回值、状态变迁、耗时、token用量。与传统APM的trace不同，Agent trace捕获的是**决策过程**而非仅仅是函数调用。

**最小payload:**
```json
{ "traceId": "t-abc", "stepId": 3, "tool": "search_memory", "argsHash": "sha256:...", "duration_ms": 120, "result": "found 3 matches", "model": "glm-5.1", "tokens": { "in": 450, "out": 80 } }
```

### 2. Trajectory Evaluation（轨迹评估）
不只评估最终输出，而是评估**整个执行路径**：工具选择是否正确？参数是否合理？是否走了弯路？是否调用了不该调用的工具？

### 3. Policy-as-Code（策略即代码）
将Agent行为策略（允许哪些工具、哪些操作需要审批、预算限制）写成机器可读配置，在LLM外部强制执行。

### 4. LLM-as-Judge with Guardrails
用LLM评估Agent输出，但需要：rubric评分标准、结构化JSON输出、人工抽检审计。Judge分数在稳定前应视为flaky test。

### 5. Tool Mock Determinism（工具Mock确定性）
测试时用mock替换真实工具调用，使评估可重复、低成本。关键：`seed=42` + mock tools + maxSteps限制。

---

## 关键洞察 (5条)

### 1. "没有stack trace的崩溃" — Agent调试的核心困境
传统软件crash有stack trace，Agent失败往往在180步之后静默出错。Observability的核心价值是填补"Agent做了什么"与"你期望它做什么"之间的gap。**这与autoresearch方法论的"明确指标"原则完全一致。**

### 2. 小模型 ≠ 差工具调用
13个本地LLM测试结果：3.4GB的Nemotron Nano 4B得分95%（与18GB的GLM-4.7-Flash并列第二），而专用工具调用模型xLAM-2 8B仅15%。**训练方法论 > 参数量**，对Edge Agent Runtime的选择有直接影响。

### 3. Evaluations不是可选的 — 是CI的一部分
生产Agent必须：test full trajectories（工具选择+结果），不只是最终答案。Trace → Eval → CI 的闭环是2026年的标准实践。

### 4. Policy-as-Code是最被低估的Guardrail
把策略放在LLM外部执行，不让Agent自我约束。YAML配置 → 运行时强制。**这与OpenClaw的tool policy机制高度对应。**

### 5. Mock确定性是评估基础设施的基石
`toolMocks + seed + maxSteps` 三要素让测试可重复。Braintrust的"从生产trace自动生成eval case"模式值得借鉴。

---

## 可运行代码: Agent Trace & Eval Harness

零依赖TypeScript实现，可直接集成到现有lab/项目。

```typescript
// agent-observability.ts — 最小可观测性+评估框架
// 零依赖，兼容 Deno / Node.js / Bun

// === 1. Trace 数据结构 ===

interface TraceStep {
  stepId: number;
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
  duration_ms: number;
  tokens?: { in: number; out: number };
  model?: string;
  timestamp: string;
}

interface AgentTrace {
  traceId: string;
  input: string;
  steps: TraceStep[];
  finalOutput: unknown;
  success: boolean;
  totalDuration_ms: number;
  totalTokens: { in: number; out: number };
  tags: string[];
}

// === 2. Tracer — 记录执行轨迹 ===

class AgentTracer {
  private steps: TraceStep[] = [];
  private startTime: number;
  private tokens = { in: 0, out: 0 };

  constructor(private traceId: string, private input: string) {
    this.startTime = Date.now();
  }

  async traceTool<T>(
    tool: string,
    args: Record<string, unknown>,
    fn: () => Promise<T>,
    meta?: { model?: string; tokens?: { in: number; out: number } }
  ): Promise<T> {
    const start = Date.now();
    try {
      const result = await fn();
      const duration = Date.now() - start;
      this.steps.push({
        stepId: this.steps.length + 1,
        tool,
        args,
        result: typeof result === 'string' ? result.slice(0, 200) : result,
        duration_ms: duration,
        tokens: meta?.tokens,
        model: meta?.model,
        timestamp: new Date().toISOString(),
      });
      if (meta?.tokens) {
        this.tokens.in += meta.tokens.in;
        this.tokens.out += meta.tokens.out;
      }
      return result;
    } catch (err) {
      const duration = Date.now() - start;
      this.steps.push({
        stepId: this.steps.length + 1,
        tool,
        args,
        result: { error: String(err) },
        duration_ms: duration,
        timestamp: new Date().toISOString(),
      });
      throw err;
    }
  }

  finalize(success: boolean, finalOutput: unknown, tags: string[] = []): AgentTrace {
    return {
      traceId: this.traceId,
      input: this.input,
      steps: [...this.steps],
      finalOutput,
      success,
      totalDuration_ms: Date.now() - this.startTime,
      totalTokens: { ...this.tokens },
      tags,
    };
  }
}

// === 3. Policy Engine — 外部策略执行 ===

interface Policy {
  allowTools: string[];
  requireApprovalFor: string[];
  maxSteps: number;
  maxCost_tokens: number;
}

class PolicyEngine {
  constructor(private policy: Policy) {}

  checkTool(tool: string): { allowed: boolean; needsApproval: boolean } {
    if (this.policy.requireApprovalFor.includes(tool)) {
      return { allowed: true, needsApproval: true };
    }
    return { allowed: this.policy.allowTools.includes(tool), needsApproval: false };
  }

  checkBudget(tokensUsed: number): boolean {
    return tokensUsed <= this.policy.maxCost_tokens;
  }

  checkStepLimit(currentStep: number): boolean {
    return currentStep <= this.policy.maxSteps;
  }
}

// === 4. Evaluator — 轨迹评估 ===

interface EvalResult {
  passed: boolean;
  score: number; // 0-1
  checks: { name: string; passed: boolean; detail: string }[];
}

class TraceEvaluator {
  /**
   * 评估轨迹：工具选择正确性 + 步骤数限制 + 禁用工具检查 + 预算检查
   */
  evaluate(
    trace: AgentTrace,
    opts: {
      maxToolCalls?: number;
      forbiddenTools?: string[];
      requiredTools?: string[];
      expectedSuccess?: boolean;
    } = {}
  ): EvalResult {
    const checks: EvalResult['checks'] = [];

    // Check 1: 成功状态
    if (opts.expectedSuccess !== undefined) {
      const ok = trace.success === opts.expectedSuccess;
      checks.push({ name: 'success_match', passed: ok, detail: `expected=${opts.expectedSuccess}, got=${trace.success}` });
    }

    // Check 2: 步骤数限制
    if (opts.maxToolCalls) {
      const ok = trace.steps.length <= opts.maxToolCalls;
      checks.push({ name: 'max_tool_calls', passed: ok, detail: `${trace.steps.length}/${opts.maxToolCalls}` });
    }

    // Check 3: 禁用工具
    if (opts.forbiddenTools?.length) {
      const used = trace.steps.map(s => s.tool);
      const violations = used.filter(t => opts.forbiddenTools!.includes(t));
      checks.push({ name: 'no_forbidden_tools', passed: violations.length === 0, detail: violations.length ? `violated: ${violations.join(',')}` : 'clean' });
    }

    // Check 4: 必须使用的工具
    if (opts.requiredTools?.length) {
      const used = new Set(trace.steps.map(s => s.tool));
      const missing = opts.requiredTools.filter(t => !used.has(t));
      checks.push({ name: 'required_tools_used', passed: missing.length === 0, detail: missing.length ? `missing: ${missing.join(',')}` : 'all used' });
    }

    // Check 5: 无错误步骤
    const errorSteps = trace.steps.filter(s => s.result && typeof s.result === 'object' && 'error' in (s.result as any));
    checks.push({ name: 'no_error_steps', passed: errorSteps.length === 0, detail: `${errorSteps.length} error steps` });

    const passed = checks.every(c => c.passed);
    const score = checks.filter(c => c.passed).length / Math.max(checks.length, 1);

    return { passed, score, checks };
  }

  /**
   * 从trace自动生成eval case（用于回归测试）
   */
  traceToEvalCase(trace: AgentTrace): { input: string; expectedTools: string[]; expectedSuccess: boolean; maxSteps: number } {
    return {
      input: trace.input,
      expectedTools: [...new Set(trace.steps.map(s => s.tool))],
      expectedSuccess: trace.success,
      maxSteps: trace.steps.length + 2, // 允许少量偏差
    };
  }
}

// === 5. Demo: 完整可运行示例 ===

async function demo() {
  // 定义策略
  const policy = new PolicyEngine({
    allowTools: ['search', 'read_file', 'calculate', 'write_note'],
    requireApprovalFor: ['send_email', 'delete_file'],
    maxSteps: 8,
    maxCost_tokens: 10000,
  });

  const tracer = new AgentTracer('demo-001', 'Find the best prompt strategy for code generation');

  // 模拟Agent执行循环（带trace和policy检查）
  const tools = ['search', 'read_file', 'calculate', 'write_note'] as const;
  let totalTokens = 0;

  for (let i = 0; i < 4; i++) {
    const tool = tools[i];
    const args = { query: `step ${i + 1}` };

    // Policy 检查
    const check = policy.checkTool(tool);
    if (!check.allowed) throw new Error(`Tool ${tool} not allowed`);
    if (check.needsApproval) console.log(`⚠️ Tool ${tool} needs approval (auto-approved in demo)`);

    // Budget 检查
    if (!policy.checkBudget(totalTokens)) throw new Error('Budget exceeded');

    // 带trace的工具调用
    await tracer.traceTool(tool, args, async () => {
      return `Result from ${tool}: found ${Math.floor(Math.random() * 10)} items`;
    }, { model: 'mock-llm', tokens: { in: 100 + i * 50, out: 20 + i * 10 } });

    totalTokens += 100 + i * 50 + 20 + i * 10;
  }

  const trace = tracer.finalize(true, 'Best strategy: chain-of-thought with few-shot', ['demo', 'evaluation']);

  // 评估
  const evaluator = new TraceEvaluator();
  const result = evaluator.evaluate(trace, {
    maxToolCalls: 5,
    requiredTools: ['search', 'read_file'],
    forbiddenTools: ['send_email', 'delete_file'],
    expectedSuccess: true,
  });

  console.log('=== Agent Trace ===');
  console.log(`Trace ID: ${trace.traceId}`);
  console.log(`Steps: ${trace.steps.length}`);
  console.log(`Duration: ${trace.totalDuration_ms}ms`);
  console.log(`Tokens: ${trace.totalTokens.in} in / ${trace.totalTokens.out} out`);
  console.log();
  console.log('=== Evaluation ===');
  console.log(`Passed: ${result.passed} (score: ${(result.score * 100).toFixed(0)}%)`);
  result.checks.forEach(c => {
    console.log(`  ${c.passed ? '✅' : '❌'} ${c.name}: ${c.detail}`);
  });

  // 从trace生成回归测试case
  const evalCase = evaluator.traceToEvalCase(trace);
  console.log();
  console.log('=== Generated Eval Case ===');
  console.log(JSON.stringify(evalCase, null, 2));

  // 断言验证
  console.assert(result.passed === true, 'Evaluation should pass');
  console.assert(result.score === 1, 'Score should be 1.0');
  console.assert(trace.steps.length === 4, 'Should have 4 steps');
  console.assert(evalCase.expectedTools.length === 4, 'Should expect 4 unique tools');
  console.log('\n✅ All assertions passed!');
}

// Run
demo().catch(console.error);
```

### 运行方式
```bash
# Node.js
npx tsx agent-observability.ts

# Deno
deno run agent-observability.ts

# Bun
bun agent-observability.ts
```

---

## 与现有项目的关联

| 项目 | 关联 |
|------|------|
| **agent-context-store** | Tracer可存储trace到context-store，复用现有持久化 |
| **prompt-router** | eval loop可评估路由准确率，cross_validate已是雏形 |
| **better-ralph-core** | experiments.tsv 是轻量trace，可升级为结构化AgentTrace |
| **Edge Agent Runtime** | 小模型tool calling数据(95% @ 3.4GB)直接影响模型选择 |
| **autoresearch方法论** | "明确指标"→trace eval; "快速循环"→eval in CI; "保留/回退"→trace-based regression |
| **OpenClaw gateway** | Policy-as-Code对应tool policy; trace格式可标准化 |

---

## 下一步行动

1. **创建 `lab/agent-observability/`** — 将上述TypeScript代码扩展为独立模块
   - `tracer.ts` (AgentTracer + AgentTrace类型)
   - `policy.ts` (PolicyEngine + YAML加载)
   - `evaluator.ts` (TraceEvaluator + traceToEvalCase)
   - `reporter.ts` (Markdown/JSON报告生成)
   - 目标: 10+ tests

2. **集成到现有项目** — 在better-ralph和prompt-router中添加trace捕获，用evaluator评估每次实验循环

3. **研究 Braintrust/LangSmith 的 trace-to-eval 模式** — 生产trace自动转回归测试，减少手动编写test case

---

## 参考资料

- [Agent Observability: Complete Guide 2026 (Braintrust)](https://www.braintrust.dev/articles/agent-observability-complete-guide-2026)
- [AI Agents in 2026: Tools, Memory, Evals, Guardrails](https://andriifurmanets.com/blogs/ai-agents-2026-practical-architecture-tools-memory-evals-guardrails)
- [Local LLMs on Tool Calling: 13 Model Eval](https://www.jdhodges.com/blog/local-llms-on-tool-calling-2026-pt1-local-lm/)
- [Top 5 Agent Evaluation Tools (MLflow)](https://mlflow.org/top-5-agent-evaluation-frameworks/)
- [Best AI Model for Tool Calling 2026 (Fleece AI)](https://fleeceai.app/blog/best-ai-model-for-tool-calling-2026)
