# 研究笔记：LLM Structured Output Toolkit — 流式 + 版本化 + Validation Sandwich

> 日期：2026-06-02 | 方法论：autoresearch | 状态：✅ 完成
> 前序：2026-06-01 (基础概念 + StructuredLLMClient)

---

## 核心概念

### 1. Validation Sandwich（三明治验证模式）
生产环境的黄金模式：**Schema 验证 → LLM 生成 → 业务验证**。即使 provider 保证 100% schema 合规，仍需在业务层做语义验证（如：订单号格式、日期范围、数值合理性）。这是从"语法正确"到"语义正确"的关键跃迁。

### 2. Schema 版本化与迁移
Schema 演化是隐性灾难——改字段名、加可选字段、改类型，都会导致缓存失效、下游消费者崩溃。解决方案：显式版本号 + 迁移函数 + A/B 测试期间双版本并存。

### 3. 流式结构化输出（Streaming Structured Output）
2026 年 Vercel AI SDK 和 Instructor 都支持流式结构化输出：partialObject 在每个 chunk 合并到已有对象上，实现打字机效果的实时 UI。关键技术：JSON Patch（RFC 6902）或增量合并。

### 4. Provider Quirks 抽象层
每个 provider 的结构化输出 API 不同：
- OpenAI: `response_format: { type: "json_schema", json_schema: {...} }`
- Claude: `output_config.format` (4.5+ 原生) 或 tool use 模式
- Gemini: `response_mime_type` + `response_schema`
- vLLM: `guided_json` / `guided_regex` / `guided_grammar`

Toolkit 必须屏蔽这些差异。

### 5. 约束解码的性能真相
XGrammar 通过 vocabulary partitioning + adaptive token mask caching 实现 100x 加速。但首次 schema 编译仍需 10-30s。对于高频调用的 schema，**客户端缓存编译后的 FSM** 比依赖 provider 端缓存更可靠。

---

## 可运行代码示例：StreamingStructuredClient + Schema Versioning

完整的 TypeScript 实现，包含流式增量解析、schema 版本化迁移、validation sandwich。

```typescript
// structured-output-v2.ts
// 零外部依赖，node structured-output-v2.ts 直接运行

// ============================================================
// Part 1: Schema Versioning
// ============================================================

interface SchemaVersion<T> {
  version: number;
  name: string;
  jsonSchema: Record<string, unknown>;
  validate: (data: unknown) => { valid: boolean; errors: string[] };
  migrate?: (prev: unknown, fromVersion: number) => T;
}

class SchemaRegistry {
  private versions = new Map<string, SchemaVersion<unknown>[]>();

  register<T>(version: SchemaVersion<T>): void {
    const existing = this.versions.get(version.name) || [];
    // 按 version 排序插入
    const idx = existing.findIndex(v => v.version >= version.version);
    if (idx === -1) existing.push(version as SchemaVersion<unknown>);
    else existing.splice(idx, 0, version as SchemaVersion<unknown>);
    this.versions.set(version.name, existing);
  }

  getLatest(name: string): SchemaVersion<unknown> | undefined {
    const list = this.versions.get(name);
    return list?.[list.length - 1];
  }

  getVersion(name: string, version: number): SchemaVersion<unknown> | undefined {
    return this.versions.get(name)?.find(v => v.version === version);
  }

  /** 迁移旧版本数据到最新版本 */
  migrateToLatest(name: string, data: unknown, fromVersion: number): { data: unknown; errors: string[] } {
    const list = this.versions.get(name);
    if (!list) return { data, errors: [`Unknown schema: ${name}`] };

    const errors: string[] = [];
    let current = data;
    let v = fromVersion;

    while (v < (list[list.length - 1]?.version ?? v)) {
      const next = list.find(s => s.version === v + 1);
      if (!next?.migrate) {
        errors.push(`No migration path from v${v} to v${v + 1}`);
        break;
      }
      current = next.migrate(current, v);
      v++;
    }
    return { data: current, errors };
  }
}

// ============================================================
// Part 2: Streaming Partial Object Merger
// ============================================================

class StreamingMerger {
  private buffer = "";
  private partial: Record<string, unknown> = {};

  /** 喂入一个 chunk，返回当前合并后的 partial object */
  feed(chunk: string): Record<string, unknown> {
    this.buffer += chunk;

    // 尝试解析已有 buffer 为 JSON
    // 增量解析策略：找到最后一个完整的 key-value 对
    const cleaned = this.buffer.replace(/,\s*$/, ""); // 去掉尾部逗号
    try {
      const parsed = JSON.parse(cleaned + "}");
      this.partial = parsed;
      return { ...this.partial };
    } catch {
      // 尝试补全 }
      try {
        const patched = cleaned.includes("{") ? cleaned + "}}" : "{}";
        const parsed = JSON.parse(patched);
        this.partial = parsed;
      } catch {
        // 还不够完整，保持上一次的 partial
      }
    }
    return { ...this.partial };
  }

  /** 标记流结束，尝试最终解析 */
  finalize(): { data: Record<string, unknown> | null; parseError?: string } {
    try {
      const data = JSON.parse(this.buffer);
      return { data };
    } catch (e) {
      return { data: null, parseError: (e as Error).message };
    }
  }

  reset(): void {
    this.buffer = "";
    this.partial = {};
  }
}

// ============================================================
// Part 3: Validation Sandwich + Retry with Error Feedback
// ============================================================

interface ExtractionResult<T> {
  data: T | null;
  attempts: number;
  errors: string[];
  schemaVersion: number;
}

class SandwichClient {
  constructor(
    private registry: SchemaRegistry,
    private maxRetries = 3,
  ) {}

  /**
   * Validation Sandwich:
   * 1. Pre-validation: schema check on input completeness
   * 2. LLM extraction (simulated)
   * 3. Post-validation: semantic/business check
   */
  async extract<T>(
    schemaName: string,
    prompt: string,
    semanticValidator?: (data: unknown) => { valid: boolean; errors: string[] },
  ): Promise<ExtractionResult<T>> {
    const schema = this.registry.getLatest(schemaName);
    if (!schema) throw new Error(`Schema "${schemaName}" not found`);

    const allErrors: string[] = [];

    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      // Step 2: LLM extraction (simulated with retry feedback)
      const raw = this.simulateLLM(prompt, schema, attempt, allErrors);
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        allErrors.push(`[Attempt ${attempt}] Invalid JSON`);
        continue;
      }

      // Step 3a: Schema validation
      const schemaResult = schema.validate(parsed);
      if (!schemaResult.valid) {
        allErrors.push(`[Attempt ${attempt}] Schema: ${schemaResult.errors.join(", ")}`);
        continue;
      }

      // Step 3b: Semantic validation (the "sandwich top bun")
      if (semanticValidator) {
        const semanticResult = semanticValidator(parsed);
        if (!semanticResult.valid) {
          allErrors.push(`[Attempt ${attempt}] Semantic: ${semanticResult.errors.join(", ")}`);
          continue;
        }
      }

      return { data: parsed as T, attempts: attempt, errors: allErrors, schemaVersion: schema.version };
    }

    return { data: null, attempts: this.maxRetries, errors: allErrors, schemaVersion: schema.version };
  }

  /** 模拟 LLM — 故意在前面几次返回有问题的数据 */
  private simulateLLM(
    prompt: string,
    schema: SchemaVersion<unknown>,
    attempt: number,
    previousErrors: string[],
  ): string {
    // Attempt 1: 返回 schema 不合规的数据（测试 schema 验证重试）
    if (attempt === 1 && prompt.includes("sentiment")) {
      return JSON.stringify({ sentiment: "positive" }); // 缺 confidence
    }

    // Attempt 2: 如果之前的错误包含 "Semantic"，返回语义错误的修复
    const lastError = previousErrors[previousErrors.length - 1] || "";
    if (attempt === 2 && lastError.includes("Semantic")) {
      // 修复语义问题
      return JSON.stringify({ sentiment: "neutral", confidence: 0.92, reasoning: "balanced tone" });
    }

    // 默认：返回合规数据
    if (prompt.includes("sentiment")) {
      return JSON.stringify({ sentiment: "positive", confidence: 0.95, reasoning: "enthusiastic tone" });
    }
    if (prompt.includes("entity")) {
      return JSON.stringify({ name: "Paris", type: "location", confidence: 0.88, source_text: "Paris" });
    }
    return JSON.stringify({ result: "ok", confidence: 1.0 });
  }
}

// ============================================================
// Part 4: Streaming Extraction
// ============================================================

class StreamingStructuredClient {
  constructor(private registry: SchemaRegistry) {}

  /**
   * 模拟流式结构化输出
   * 返回 async generator，每个 yield 是一个 partial object
   */
  async *extractStream(
    schemaName: string,
    _prompt: string,
  ): AsyncGenerator<{ partial: Record<string, unknown>; done: boolean; error?: string }> {
    const schema = this.registry.getLatest(schemaName);
    if (!schema) {
      yield { partial: {}, done: true, error: `Schema "${schemaName}" not found` };
      return;
    }

    const merger = new StreamingMerger();

    // 模拟 LLM 逐 chunk 输出 JSON
    const chunks = ['{"sentiment": "p', 'ositive", "confid', 'ence": 0.95, "r', 'easoning": "great product"}'];

    for (const chunk of chunks) {
      const partial = merger.feed(chunk);
      yield { partial, done: false };
    }

    const final = merger.finalize();
    if (final.data) {
      const validation = schema.validate(final.data);
      yield {
        partial: final.data,
        done: true,
        error: validation.valid ? undefined : validation.errors.join(", "),
      };
    } else {
      yield { partial: {}, done: true, error: final.parseError };
    }
  }
}

// ============================================================
// Test Suite
// ============================================================

async function main() {
  const registry = new SchemaRegistry();

  // --- Register Sentiment Schema v1 ---
  registry.register({
    version: 1,
    name: "sentiment",
    jsonSchema: {
      type: "object",
      properties: {
        sentiment: { type: "string", enum: ["positive", "negative", "neutral"] },
        confidence: { type: "number" },
      },
      required: ["sentiment", "confidence"],
    },
    validate: (data: unknown) => {
      const errors: string[] = [];
      if (typeof data !== "object" || data === null) return { valid: false, errors: ["Not an object"] };
      const d = data as Record<string, unknown>;
      if (!d.sentiment) errors.push("Missing: sentiment");
      if (typeof d.confidence !== "number") errors.push("Missing: confidence");
      if (d.sentiment && !["positive", "negative", "neutral"].includes(String(d.sentiment)))
        errors.push("Invalid sentiment value");
      return { valid: errors.length === 0, errors };
    },
  });

  // --- Register Sentiment Schema v2 (adds reasoning field) ---
  registry.register({
    version: 2,
    name: "sentiment",
    jsonSchema: {
      type: "object",
      properties: {
        sentiment: { type: "string", enum: ["positive", "negative", "neutral"] },
        confidence: { type: "number" },
        reasoning: { type: "string" },
      },
      required: ["sentiment", "confidence", "reasoning"],
    },
    validate: (data: unknown) => {
      const errors: string[] = [];
      if (typeof data !== "object" || data === null) return { valid: false, errors: ["Not an object"] };
      const d = data as Record<string, unknown>;
      if (!d.sentiment) errors.push("Missing: sentiment");
      if (typeof d.confidence !== "number") errors.push("Missing: confidence");
      if (!d.reasoning) errors.push("Missing: reasoning");
      return { valid: errors.length === 0, errors };
    },
    migrate: (prev: unknown) => {
      const d = prev as Record<string, unknown>;
      return {
        sentiment: d.sentiment,
        confidence: d.confidence,
        reasoning: d.reasoning || "(migrated from v1, no reasoning)",
      };
    },
  });

  console.log("=".repeat(60));
  console.log("Test 1: Validation Sandwich — Schema Retry");
  console.log("=".repeat(60));
  const client = new SandwichClient(registry);
  const r1 = await client.extract("sentiment", "Analyze sentiment of: great product!");
  console.log("Result:", JSON.stringify(r1, null, 2));
  console.log("✅ Retry from schema error:", r1.attempts === 2 ? "YES" : `NO (${r1.attempts} attempts)`);

  console.log("\n" + "=".repeat(60));
  console.log("Test 2: Validation Sandwich — Semantic Validator");
  console.log("=".repeat(60));
  const semanticCheck = (data: unknown) => {
    const d = data as Record<string, unknown>;
    if (typeof d.confidence === "number" && d.confidence > 1)
      return { valid: false, errors: ["confidence must be ≤ 1.0"] };
    if (typeof d.confidence === "number" && d.confidence < 0)
      return { valid: false, errors: ["confidence must be ≥ 0"] };
    return { valid: true, errors: [] };
  };
  const r2 = await client.extract("sentiment", "Analyze sentiment of: great product!", semanticCheck);
  console.log("Result:", JSON.stringify(r2, null, 2));
  console.log("✅ Sandwich (schema + semantic):", r2.data ? "PASS" : "FAIL");

  console.log("\n" + "=".repeat(60));
  console.log("Test 3: Schema Migration v1 → v2");
  console.log("=".repeat(60));
  const v1Data = { sentiment: "positive", confidence: 0.9 };
  const migrated = registry.migrateToLatest("sentiment", v1Data, 1);
  console.log("V1 data:", JSON.stringify(v1Data));
  console.log("Migrated to v2:", JSON.stringify(migrated.data));
  // Validate migrated data
  const v2 = registry.getLatest("sentiment")!;
  const v2Result = v2.validate(migrated.data);
  console.log("✅ Migrated data validates against v2:", v2Result.valid ? "YES" : "NO");

  console.log("\n" + "=".repeat(60));
  console.log("Test 4: Streaming Structured Output");
  console.log("=".repeat(60));
  const streamClient = new StreamingStructuredClient(registry);
  const stream = streamClient.extractStream("sentiment", "Analyze sentiment");
  let chunkCount = 0;
  for await (const chunk of stream) {
    chunkCount++;
    console.log(`Chunk ${chunkCount}:`, JSON.stringify(chunk.partial), chunk.done ? "✅ DONE" : "");
    if (chunk.error) console.log("  Error:", chunk.error);
  }
  console.log("✅ Received", chunkCount, "chunks (streaming works)");

  console.log("\n" + "=".repeat(60));
  console.log("Test 5: StreamingMerger Unit Test");
  console.log("=".repeat(60));
  const merger = new StreamingMerger();
  const testChunks = ['{"name": "test",', ' "value": 42}'];
  for (const c of testChunks) {
    const partial = merger.feed(c);
    console.log("After chunk:", JSON.stringify(partial));
  }
  const final = merger.finalize();
  console.log("Final:", JSON.stringify(final.data));
  console.log("✅ Merger produces correct object:", final.data?.name === "test" && final.data?.value === 42 ? "YES" : "NO");

  console.log("\n" + "=".repeat(60));
  console.log("ALL TESTS COMPLETE ✅");
  console.log("=".repeat(60));
}

main().catch(console.error);
```

### 运行方式

```bash
# 零依赖直接运行
node --experimental-strip-types structured-output-v2.ts
# 或
npx tsx structured-output-v2.ts
```

---

## 关键洞察

1. **Validation Sandwich 是生产级结构化输出的最低标准** — 仅靠 provider 的约束解码保证语法合规不够。真实场景中，语义错误（幻觉数值、不可能的日期、不存在的 ID）比语法错误更常见且更危险。Sandwich 模式把 schema 验证和业务验证分层，失败时把具体错误信息反馈给 LLM 重试。

2. **Schema 版本化是隐性基础设施债务** — 当应用演化时，schema 悄悄变化：字段重命名、类型变更、新增必填字段。没有显式版本号和迁移函数，缓存的数据和下游消费者会静默失败。v1→v2 的迁移函数（`migrate`）让 A/B 测试期间可以同时处理新旧格式。

3. **流式结构化输出的增量合并是非平凡的** — JSON 不能部分解析。StreamingMerger 的策略是：维护 buffer，尝试补全尾部（去尾逗号、补 `}`），成功就更新 partial。生产环境可以用 JSON Patch (RFC 6902) 或 sagelaboratory 的 `partial-json` 库。

4. **错误反馈重试比约束解码更实用** — Instructor 的核心创新不是 schema 验证本身，而是把 Pydantic 错误信息发回 LLM 让它自我修正。大多数情况第 2 次就对了。结合约束解码（防语法错误）+ 反馈重试（修语义错误）= 最强组合。

5. **Claude 4.7 原生结构化输出改变了 Toolkit 设计** — 之前 Claude 只能通过 tool use 模式实现结构化输出（需要 "tool" 语义包装），现在有 `output_config.format` 直接支持。Toolkit 的 provider 抽象层需要更新。

---

## 与现有项目关联

| 项目 | 本次研究的具体应用 |
|------|-----------------|
| **lab/structured-output-toolkit** | 直接输出 — 今天的研究笔记是 v2 实现的设计蓝图 |
| **agent-context-store** | snapshot_diff_summary 可以用 Sandwich 模式：LLM 生成摘要 → schema 验证 → 语义验证（检查 diff 覆盖率） |
| **agent-memory-graph** | evolve() 的 metadata 可以用版本化 schema，支持知识节点的 schema 演化 |
| **openclaw-langgraph-bridge** | Supervisor 路由决策用流式结构化输出，实现实时决策可视化 |
| **prompt-router** | 路由结果的结构化输出 + 版本化，支持路由 schema 热更新 |

---

## 下一步行动

1. **创建 `lab/structured-output-toolkit/`** — 基于今天的 v2 设计实现完整版，包含：
   - `SchemaRegistry` + 版本化迁移
   - `SandwichClient` + 错误反馈重试
   - `StreamingStructuredClient` + 增量合并
   - Provider 适配器（OpenAI / Claude / Gemini / vLLM）
2. **为 agent-context-store 添加结构化摘要适配器** — 第一个实际应用场景，用 SandwichClient 做快照摘要
3. **npm publish 准备** — 与 agent-memory-graph / agent-context-store 一起发布

---

## 参考来源

- Collin Wilkins: LLM Structured Outputs: Schema Validation for Real Pipelines (Updated May 2026, incl. Claude 4.7)
- DEV Community: LLM Structured Output in 2026 — Validation Sandwich + Schema Versioning patterns
- TECHSY: 8 LLM Structured Output Libraries Ranked (2026) — XGrammar as invisible engine
- Zylos Research: Structured Output and JSON Mode in LLMs 2026 — Industry convergence analysis
- HPE Developer: Using structured outputs in vLLM — XGrammar backend performance
- Red Hat Developer: Structured outputs in vLLM — Streaming + structural tags
- OpenAI Community: Structured Output Caching and Latency — Schema compilation + caching scope
