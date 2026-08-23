# OTel GenAI 语义约定 2026-08 快照 — lab/agent-observability 与 amg telemetry 双向对齐

**Research #070** | 2026-08-17 20:04 (deep-exploration-evening, 同晚第二轮) | 来源: HEARTBEAT 中优先级 "lab/agent-observability: OTel GenAI alignment"

## 背景与动机

两个自有资产的约定漂移：
- **lab/agent-observability**（TS, 91 tests, zero-dep）：span 名全自定义（`agent.run`/`llm.call`/`tool.execute`/`retrieval.search`/`memory.read|write`），`llm.call` 把 prompt/completion 作为裸属性 `gen_ai.prompt`/`gen_ai.completion` 常驻 span —— 违反规范的 Opt-In 内容捕获设计
- **amg telemetry.py**（Python, C374 实现于 Research #034/#053 时代）：span 名 `gen_ai.memory.{op}`，属性 `gen_ai.memory.store`（非 `store.id`）、4 个分立计数器（`items_stored/retrieved/updated/deleted`）、`gen_ai.memory.search.query`（无门控）

2026 年规范剧变：**6 月 v1.42.0 起 GenAI 约定整体迁出主仓**，新家 `open-telemetry/semantic-conventions-genai`（2026-05-05 建）至今**无 tagged release**，schema URL 为 TODO。本笔记锚定 commit `c739977`（2026-07-30）产出对齐设计 + 可运行适配器。

## 核心概念 (5)

### 1. 仓库分裂与"锚定 commit"纪律
主仓 registry 里所有 `gen_ai.*` 行的 stability 列现在只写 "Moved to the OpenTelemetry GenAI semantic conventions repository"；官方文档页是 stub；多数 instrumentation README 仍链向死页。新仓无版本标签，CHANGELOG 只有 `## Unreleased`——**唯一可引用的参考点是 commit hash**。迁移机器（Telemetry Schemas）对 GenAI 不可用（schema URL 404），所以实践纪律 = 代码/README 里钉 commit + 映射层隔离改名风险（`OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 是生态级过渡开关）。

### 2. Memory 操作族成为一等公民
`gen_ai.operation.name` 现有 17 个良定义值，其中 **7 个是 memory 动词**：`create_memory_store`/`search_memory`/`create_memory`/`update_memory`/`upsert_memory`/`delete_memory`/`delete_memory_store`。`upsert_memory` 的规范定义原文——"create, update, or consolidate memory records without the caller choosing which"——**逐词描述 amg 的 `add()`/`consolidate()`/`FastAppendQueue` 语义**。amg 是这个新操作族的现成完整实现。

### 3. Memory span 规范形状（c739977 原文要点）
- **Span 名 = `{gen_ai.operation.name}`**（如 `search_memory`，动词在前，无 `gen_ai.` 前缀）
- **Kind SHOULD CLIENT，MAY INTERNAL**（in-process 内存系统）→ amg/lab 均为 in-process，INTERNAL 合规
- 属性：`gen_ai.operation.name`（Required）｜`gen_ai.memory.record.id`/`store.id`（Cond. Required）｜`gen_ai.memory.record.count`（Recommended，**单一计数器**，语义随操作切换：search=返回数，create=尝试创建数…）｜`gen_ai.memory.query.text` 与 `gen_ai.memory.records`（**Opt-In**，须由 `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` 门控，records 须遵循 JSON schema）
- `delete_memory` 无 `record.id` = 删除全 store（语义化缺省）

### 4. 内容捕获三模式与 v1.37 聚合革命
旧规范逐消息事件（每条 message 一个 event）在多轮对话里淹死查询层 → v1.37 改为三个聚合属性（`gen_ai.system_instructions`/`gen_ai.input.messages`/`gen_ai.output.messages`）放 span 或专用事件 `gen_ai.client.inference.operation.details`。内容默认**不存在**；生产推荐模式是"外部存储 + span 只存引用 URL"。lab 工具包的裸 `gen_ai.prompt`/`gen_ai.completion` 属性是最典型的早期反模式。

### 5. Span 名内嵌身份 + SpanKind 语义网
v1.41 起 `execute_tool {gen_ai.tool.name}`（工具名**必须**进 span 名）、`chat {model}`、`invoke_agent {name}`；v1.41 把 `invoke_agent` 拆成 CLIENT（远程托管 agent）/INTERNAL（本地框架执行），`invoke_workflow`（预定路径）与 `plan`（任务分解）独立成操作。Trace viewer 的瀑布图直接以 span 名分组统计——名内嵌身份让 Jaeger/Tempo 无需展开属性即可聚合。

## 代码示例 (已验证可运行)

`code/otel_genai_align.ts` + `code/otel_genai_demo.ts` — **导出边界适配器**（对 lab 仓 91 个现有测试零侵入）+ 真实工具包端到端演示。实测输出（`npx tsx otel_genai_demo.ts`）：

```
=== 2) GenAI-convention export (captureContent=off, spec default) ===
  [INTERNAL] invoke_agent research-agent  gen_ai.agent.name=research-agent gen_ai.operation.name=invoke_agent
  [CLIENT]   chat gpt-4o-mini             gen_ai.usage.input_tokens=120 gen_ai.usage.output_tokens=80
  [INTERNAL] execute_tool bash            gen_ai.tool.name=bash error.type=policy_denied   ← 策略拒绝
  [INTERNAL] upsert_memory                gen_ai.memory.store.id=user-prefs gen_ai.memory.record.count=3
  [INTERNAL] search_memory                gen_ai.memory.store.id=user-prefs gen_ai.memory.record.count=2
  [CLIENT]   retrieval                    gen_ai.retrieval.top_k=5
  lint: PASS ✅   details events emitted: 0 (内容门控 OFF)
=== 3) captureContent=on → chat span 携带 gen_ai.client.inference.operation.details 事件 ===
=== 4) 拒绝的 tool span: status=STATUS_CODE_ERROR error.type=policy_denied ===
=== 5) Evaluator → gen_ai.evaluation.result 事件 (policy_compliance 0.5 / latency 1.0 / reliability 0.86) ===
```

设计决策（每条对应规范条款）：
- **映射在导出边界**：`mapSpan()` 单函数承载全部改名/改型，未来规范改名 = 一处编辑（Development 状态下的唯一可持续姿势）
- **内容门控双向验证**：off 时 lint 断言 6 类敏感属性零出现；on 时 details 事件以规范聚合结构（`role`/`parts`/`finish_reason`）出现
- **`error.type=policy_denied`**：策略引擎拒绝映射为规范错误状态（低基数自定义值），PolicyEngine 语义无损
- **自定义信息隔离**：`task`/`method` 等无对应规范概念的信息放自有命名空间 `ao.*`——规范明确禁止自造 `gen_ai.*` 键
- **`lintGenAiSpans()` 内置 5 类合规断言**（Required 属性/span 名格式/error.type/Opt-In 泄漏/整数类型），可作 CI 门禁

## 关键洞察 (4)

1. **amg 的 README 差异化弹药就在规范里**：TencentDB-Agent-Memory 竞争压力下，"implements the OTel GenAI memory operation conventions (17 个良定义动词中的 7 个 memory 动词全覆盖)" 是别人还没讲的故事——但**全部 Development 状态**，措辞必须钉 commit（"aligned with semantic-conventions-genai @c739977"）且配映射层，否则改一次名就变成公开谎言。`upsert_memory` 规范原文与 amg consolidate 语义逐词重合不是巧合：规范作者面对的是同一类系统。

2. **amg telemetry 的漂移比 TS 工具包更隐蔽但同构**：span 名 `gen_ai.memory.search`（点分名词）vs 规范 `search_memory`（动词）；`gen_ai.memory.store` vs `store.id`；4 个分立计数器 vs 单一 `record.count`。**共同根因**：两者都实现于 RFC 草案时代（Research #034/#053），草案词汇与最终 registry 分叉了。修复成本极低（纯改名映射），收益是 trace 后端（Jaeger/Tempo/Datadog 原生支持 v1.37+）直接按规范聚合 amg 的记忆操作。

3. **"Development ≠ 不用，而是换姿势用"**：OTLP 传输与 tracing 模型是 Stable 的，移动的只是词汇表。生态证据：Datadog 已原生支持 v1.37+，OpenAI Python SDK instrumentation 最成熟，v1.37→v1.41 每版都动 GenAI。正确姿势 = 现在就对齐（私有词汇表严格更差）+ 映射层 + 盯新仓首次 tagged release。这与 08-14 GitHub 周报里 semantica（PROV-O 可审计图）的启示互补：**可审计叙事的护城河在稳定层（OTLP/trace 模型），不在移动层（属性名）**。

4. **MCP 约定（v1.39）是 amg MCP server 的免费升级**：amg 16-tool MCP server 现在发射的是普通 JSON-RPC 踪迹；MCP 约定定义了 `mcp.session.id`/`mcp.method.name`/`mcp.protocol.version` + 客户端-服务器跨进程 trace 连续性（W3C Trace Context 传播）+ 4 个 MCP 专属指标。amg MCP server + telemetry.py 联动 = "记忆操作在 MCP 边界两端各有一个规范 span"——这是 2026 年 agent 基础设施买家的验收清单项。

## 与现有项目关联

- **lab/agent-observability**（91 tests）：`otel_genai_align.ts` 可直接落入 `src/otel-genai.ts`（~200 行），`lintGenAiSpans` 进 test runner；README 增加 "OTel GenAI-convention export" 卖点
- **amg telemetry.py**（C374/C446）：span 名/属性改名映射 ~40 行 + 测试；README 基准表脚注追加约定锚定声明
- **amg MCP server**（16 tools）：MCP 约定对齐是下一个独立 cycle（见洞察 4）
- **amg README（最高优先级 human-blocked 项）**：benchmark 对比表 + OTel 合规声明形成"评测口径 + 可观测性"双脚注体系

## 下一步行动 (3)

1. **[dev, ~1 cycle] lab/agent-observability 落地 `src/otel-genai.ts`**：移植适配器 + lint 进 tests（semconv 合规成为测试门禁），91→~110 tests，README 更新。适配器已在本轮验证零侵入。
2. **[dev, ~1 cycle] amg telemetry.py v2 对齐**：`gen_ai.memory.{op}` span 名 → 动词式；`store`→`store.id`；分立计数→`record.count`；`search.query`→`query.text` + Opt-In 门控（env `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`）；`hit`/`actor_id` 迁入 `amg.*` 自有命名空间。同步 pyproject 版本注记钉 commit c739977。
3. **[watch, 季度] 盯 `semantic-conventions-genai` 首次 tagged release + 2026 stabilization roadmap (issue #3330)**：出标签即重估 pin；README 的锚定声明随之更新。

## 质量自评

- [x] 可运行代码：真实工具包 E2E 演示通过（7 span 映射 + 双向内容门控 + 策略拒绝错误语义 + evaluation 事件 + lint PASS ×2 模式），零依赖 tsx 直跑
- [x] 独到见解：upsert_memory 与 amg 语义逐词重合 / RFC→registry 分叉根因 / 稳定层护城河论 / MCP 约定免费升级（4 条，均非检索结果直接可得）
- [x] 项目关联：直连 lab 工具包、amg telemetry、amg MCP server、README 双脚注体系四个资产
- 素材来源：greptime.com 2026-05 六层解析 / praesidia.ai 2026-08-03 稳定性审计（仓库迁移首发报道之一）/ hidekazu-konishi.com（钉 c739977 逐属性转写）/ semantic-conventions-genai 仓 gen-ai-spans.md Memory+Retrieval 节原文（今日直拉 main）
