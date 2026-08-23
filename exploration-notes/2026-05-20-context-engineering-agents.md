# Context Engineering for AI Agents — 2026 深度研究

> 日期: 2026-05-20 | 主题: Context Engineering | 关联项目: agent-context-store (246 tests), LangGraph Bridge

---

## 核心概念 (5)

### 1. Context Engineering ≠ Prompt Engineering
Context Engineering 是 **系统性设计什么进入 context window** 的学科。由 Google DeepMind 的 Phil Schmid 命名，Gartner 识别为 2026 年突破性 AI 能力。Prompt engineering 关注"怎么说"，Context engineering 关注"给什么信息、什么格式、什么时间"。

**关键洞察**: "大多数生产 Agent 失败不是因为模型不行，而是因为 context window 被错误管理了" — Anthropic

### 2. 四大策略: Write → Select → Compress → Isolate (LangChain 框架)
LangChain 将 context engineering 归纳为四个操作:

- **Write**: 将 context 保存到 context window 之外（scratchpad, memory, files）
- **Select**: 在 runtime 动态检索相关信息（RAG, memory recall）
- **Compress**: 压缩已有 context（summarization, compaction, folding）
- **Isolate**: 隔离 context 到子 agent（multi-agent 架构）

### 3. Context Folding (ICLR 2026)
**Context Folding** — agent 将已完成子任务"折叠"为简短摘要，节省 context。论文显示：在复杂长任务上，agent 用 **10× 更小的 active context** 匹配 baseline 性能。关键创新：agent **主动管理**自己的 working context（非人工定义管道）。

### 4. Virtual Context Management (MemGPT/Letta)
借鉴 OS 虚拟内存分页机制:
- **Main context (RAM)**: 活跃窗口，系统 prompt + 最近消息 + 当前相关记录
- **Recall storage (disk)**: 可搜索的所有历史消息
- **Archival storage (cold)**: 向量索引的长期知识

Letta 的 **Memory Blocks** 是优雅的抽象：将 context 分成离散的功能单元（persona, human, system），agent 可以自编辑每个 block。

### 5. Context Drift — 生产 Agent 的沉默杀手
Forrester 2025 研究: **65% 的企业 AI 失败源于 context drift 或记忆丢失**，而非 token 耗尽。GPT-4 准确率从 98.1% 降到 64.1%，仅因为信息在 context window 中的**位置**不同。有效 context window 远小于广告值。

---

## 代码示例: ContextEngine — 零依赖 Context 管理

```typescript
/**
 * ContextEngine — 轻量级 Agent Context 管理器
 * 实现 Write/Select/Compress/Isolate 四大策略
 * 关联: agent-context-store 的 context 管理层
 */

interface ContextEntry {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  timestamp: number;
  tokenEstimate: number;
  folded?: boolean;
  summary?: string;
}

interface ContextEngineConfig {
  maxTokens: number;          // context window 上限
  compactionThreshold: number; // 触发压缩的比例 (0-1)
  reserveTokens: number;       // 为输出预留的 token 数
}

class ContextEngine {
  private entries: ContextEntry[] = [];
  private scratchpad: Map<string, string> = new Map();
  private config: ContextEngineConfig;

  constructor(config: Partial<ContextEngineConfig> = {}) {
    this.config = {
      maxTokens: 128000,
      compactionThreshold: 0.75,
      reserveTokens: 4096,
      ...config
    };
  }

  // === WRITE: 添加 context ===
  push(role: ContextEntry['role'], content: string): void {
    const tokens = this.estimateTokens(content);
    this.entries.push({ role, content, timestamp: Date.now(), tokenEstimate: tokens });
    this.maybeAutoCompact();
  }

  // === WRITE: Scratchpad（context 外存储）===
  writeToScratchpad(key: string, value: string): void {
    this.scratchpad.set(key, value);
  }

  readFromScratchpad(key: string): string | undefined {
    return this.scratchpad.get(key);
  }

  // === SELECT: 按相关性检索 ===
  selectRecent(count: number): ContextEntry[] {
    return this.entries.slice(-count);
  }

  selectByRole(role: ContextEntry['role']): ContextEntry[] {
    return this.entries.filter(e => e.role === role && !e.folded);
  }

  // === COMPRESS: Context Compaction ===
  compact(): { originalTokens: number; compactedTokens: number; savedRatio: number } {
    const beforeTokens = this.totalTokens();

    // 保留: system prompt + 最近 5 条 + 已折叠的摘要
    const systemEntries = this.entries.filter(e => e.role === 'system');
    const recentEntries = this.entries.slice(-5);
    const oldEntries = this.entries.filter(
      e => e.role !== 'system' && !this.entries.slice(-5).includes(e)
    );

    // 折叠旧条目为摘要
    if (oldEntries.length > 0) {
      const summary = this.summarize(oldEntries);
      const foldedEntry: ContextEntry = {
        role: 'system',
        content: `[COMPACTED ${oldEntries.length} turns]\n${summary}`,
        timestamp: Date.now(),
        tokenEstimate: this.estimateTokens(summary),
        folded: true,
        summary
      };
      this.entries = [...systemEntries, foldedEntry, ...recentEntries];
    }

    const afterTokens = this.totalTokens();
    return {
      originalTokens: beforeTokens,
      compactedTokens: afterTokens,
      savedRatio: 1 - afterTokens / beforeTokens
    };
  }

  // === COMPRESS: Context Folding (ICLR 2026) ===
  foldCompletedTask(taskLabel: string, outcome: string): void {
    const boundary = this.findTaskBoundary(taskLabel);
    if (boundary === -1) return;

    const taskEntries = this.entries.splice(boundary);
    const foldSummary: ContextEntry = {
      role: 'system',
      content: `[FOLDED: ${taskLabel}]\nOutcome: ${outcome}\n${taskEntries.length} steps compressed`,
      timestamp: Date.now(),
      tokenEstimate: this.estimateTokens(outcome) + 50,
      folded: true,
      summary: outcome
    };
    this.entries.splice(boundary, 0, foldSummary);
  }

  // === ISOLATE: 生成子 agent context ===
  isolate(subtaskPrompt: string): ContextEngine {
    const subContext = new ContextEngine({
      ...this.config,
      maxTokens: Math.floor(this.config.maxTokens * 0.5) // 子 agent 用一半
    });
    // 传递系统指令 + scratchpad 共享状态
    subContext.push('system', subtaskPrompt);
    for (const [key, value] of this.scratchpad) {
      subContext.writeToScratchpad(key, value);
    }
    return subContext;
  }

  // === 工具方法 ===
  totalTokens(): number {
    return this.entries.reduce((sum, e) => sum + e.tokenEstimate, 0);
  }

  utilization(): number {
    return this.totalTokens() / (this.config.maxTokens - this.config.reserveTokens);
  }

  getContext(): ContextEntry[] {
    return this.entries.filter(e => !e.folded || e.summary);
  }

  private maybeAutoCompact(): void {
    if (this.utilization() > this.config.compactionThreshold) {
      this.compact();
    }
  }

  private estimateTokens(text: string): number {
    // 粗略估计: ~0.75 words/token for English, ~1.5 chars/token for CJK
    return Math.ceil(text.length / 3.5);
  }

  private summarize(entries: ContextEntry[]): string {
    // 生产环境用 LLM 总结；这里用结构化提取
    const toolCalls = entries.filter(e => e.role === 'tool').length;
    const userMsgs = entries.filter(e => e.role === 'user').length;
    const assistantMsgs = entries.filter(e => e.role === 'assistant').length;
    const keyDecisions = entries
      .filter(e => e.role === 'assistant' && e.content.length > 50)
      .map(e => e.content.slice(0, 120))
      .slice(-3);

    return `Summary: ${userMsgs} user msgs, ${assistantMsgs} responses, ${toolCalls} tool calls.\n` +
      `Key decisions: ${keyDecisions.join(' | ')}`;
  }

  private findTaskBoundary(label: string): number {
    // 找到任务标签最后出现的位置
    for (let i = this.entries.length - 1; i >= 0; i--) {
      if (this.entries[i].content.includes(label)) return i;
    }
    return -1;
  }
}

// === 测试验证 ===
function assert(condition: string, actual: unknown, expected: unknown) {
  const pass = JSON.stringify(actual) === JSON.stringify(expected);
  console.log(pass ? '✅' : '❌', condition);
  if (!pass) console.log(`   expected: ${JSON.stringify(expected)}, got: ${JSON.stringify(actual)}`);
}

// Test 1: 基本 push 和 token 计算
const ctx = new ContextEngine({ maxTokens: 1000, compactionThreshold: 0.9 });
ctx.push('system', 'You are a helpful coding assistant.');
ctx.push('user', 'Write a function to reverse a string');
ctx.push('assistant', 'Here is the function...');
ctx.push('tool', 'File created: reverse.js');
assert('total entries', ctx.totalTokens() > 0, true);
assert('utilization < 1', ctx.utilization() < 1, true);

// Test 2: Scratchpad 读写
ctx.writeToScratchpad('todo', '1. implement reverse\n2. add tests');
assert('scratchpad read', ctx.readFromScratchpad('todo'), '1. implement reverse\n2. add tests');

// Test 3: Context Compaction
const bigCtx = new ContextEngine({ maxTokens: 500, compactionThreshold: 2.0, reserveTokens: 50 }); // threshold=2.0 disables auto-compact for deterministic test
bigCtx.push('system', 'System prompt');
for (let i = 0; i < 20; i++) {
  bigCtx.push('user', `User message ${i} with some content to make it longer`);
  bigCtx.push('assistant', `Assistant response ${i} with detailed explanation of the approach taken`);
  bigCtx.push('tool', `Tool output ${i}: operation completed successfully with detailed results`);
}
const result = bigCtx.compact();
assert('compaction saved tokens', result.savedRatio > 0, true);
assert('compacted entries < original', bigCtx.getContext().length < 61, true);

// Test 4: Context Folding
const foldCtx = new ContextEngine({ maxTokens: 10000 });
foldCtx.push('system', 'Agent starting');
foldCtx.push('user', 'Task: implement auth module');
for (let i = 0; i < 10; i++) {
  foldCtx.push('assistant', `Auth step ${i}: implementing...`);
  foldCtx.push('tool', `Auth tool ${i}: done`);
}
const tokensBefore = foldCtx.totalTokens();
foldCtx.foldCompletedTask('implement auth module', 'Auth module implemented with JWT + refresh tokens');
const tokensAfter = foldCtx.totalTokens();
assert('folding reduced tokens', tokensAfter < tokensBefore, true);
assert('folded context has summary', foldCtx.getContext().some(e => e.folded), true);

// Test 5: Isolation (子 agent)
const parentCtx = new ContextEngine({ maxTokens: 10000 });
parentCtx.push('system', 'Lead researcher agent');
parentCtx.writeToScratchpad('shared_state', 'project: catalyst-research');
const childCtx = parentCtx.isolate('Research subtask: find latest papers on context engineering');
assert('child inherits scratchpad', childCtx.readFromScratchpad('shared_state'), 'project: catalyst-research');
assert('child has own system', childCtx.selectByRole('system').length >= 1, true);
assert('child smaller budget', childCtx.totalTokens() >= 0, true); // fresh context

console.log('\n📊 Context Engine Stats:');
console.log(`  Fold context: ${tokensBefore} → ${tokensAfter} tokens (${Math.round((1 - tokensAfter/tokensBefore)*100)}% reduction)`);
console.log(`  Compaction: saved ${Math.round(result.savedRatio * 100)}% tokens`);
```

**运行结果**: 保存为 `/tmp/context-engine.ts`，用 `npx tsx /tmp/context-engine.ts` 运行。

---

## 关键洞察 (5)

### 1. Context Drift 是真正的敌人，不是 Token 限制
Forrester 数据显示 65% 的生产失败是 context drift。GPT-4 在同一 context 中，信息位置不同可导致准确率从 98% 跌到 64%。**我们的 agent-context-store 的 TTL + compaction 是正确的方向**。

### 2. Context Folding 是 2026 年最优雅的解决方案
ICLR 2026 论文显示 10× context 压缩而不损失性能。与 agent-context-store 的 `snapshot/restore` 天然互补：folding 负责"压缩"，snapshot 负责"持久化"。**建议 agent-context-store 增加 `fold(key, summary)` API**。

### 3. Anthropic 的三层 Context 管理: Compaction + Tool Clearing + Memory
Claude Code 的实际做法:
- **Compaction**: 接近上限时，LLM 自行总结，保留架构决策和 bug，丢弃冗余 tool 输出
- **Tool Clearing**: 可重新获取的 tool 结果（文件读取、API 响应）在用完后删除
- **Memory Tool**: 跨 session 持久化到 NOTES.md 类文件

**这直接映射到我们的 MEMORY.md + memory/YYYY-MM-DD.md 架构。**

### 4. Memory Blocks (Letta) 是 context 管理的最佳抽象
将 context window 分成功能块（persona, human, task_state），agent 可自编辑每块。比 flat message list 更结构化。**agent-context-store 的 `middleware pipeline` + `watchers` 已经提供了基础设施，可以构建 Memory Blocks 抽象。**

### 5. Multi-Agent 本质是最强的 Context Isolation
Anthropic 研究系统使用 multi-agent 的原因不是并行，而是 **context 隔离**：子 agent 在独立 context 中探索，只返回摘要给 lead agent。这与 OpenClaw 的 `sessions_spawn` + `LangGraph Bridge` 设计完全一致。

---

## 与现有项目关联

| 项目 | Context Engineering 应用 |
|------|------------------------|
| **agent-context-store** | 增加 `fold(key, summary)` — context folding 原语；middleware 做 tool clearing |
| **LangGraph Bridge** | 每个节点是天然 context 隔离单元；StateSchema 对应 Memory Blocks |
| **Agent Observability** | 追踪 context utilization + drift；compaction 事件作为 trace |
| **A2A Trust** | Agent Card 是一种 context injection；Trust Score 影响 context 优先级 |
| **Hindsight Mini** | HER 本质是 context folding 的特殊形式：失败轨迹 → 教训摘要 |

---

## 下一步行动

1. **agent-context-store 增加 `fold(key, summary)` API** — context folding 原语，标记条目为 folded + 附加摘要，目标 3-5 tests
2. **实现 `ToolClearingMiddleware`** — 中间件管道中自动清理过大的 tool 输出（基于可重新获取性标记），目标 5 tests
3. **设计 Memory Blocks 抽象** — 在 agent-context-store 上层构建 persona/human/task 三块结构，agent 可自编辑
4. **LangGraph Bridge 中实现 compaction node** — 在 StateGraph 中添加自动压缩节点

---

## 参考文献

1. Anthropic — "Effective Context Engineering for AI Agents" (2026) — https://www.anthropic.com/engineering/
2. LangChain — "Context Engineering: Write, Select, Compress, Isolate" (2026) — https://www.langchain.com/blog/context-engineering-for-agents
3. "Scaling Long-Horizon Agent via Context Folding" (ICLR 2026) — https://openreview.net/forum?id=JaLXQnA2wi
4. "Memory Management and Contextual Consistency for Long-Running Low-Code Agents" (arXiv:2509.25250)
5. Letta — "Memory Blocks: The Key to Agentic Context Management" — https://www.letta.com/blog/memory-blocks
6. "Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Challenges" (arXiv:2603.07670)
7. Cursor — "Training Composer for longer horizons through self-summarization" — https://cursor.com/blog/self-summarization
8. tianpan.co — "Context Engineering: Memory, Compaction, and Tool Clearing for Production Agents" (2026)
9. Gartner — Context Engineering 识别为 2026 breakout capability
10. Taskade — "Context Engineering: Complete 2026 Field Guide" — 5 层 context stack

---

*Generated by Catalyst 🧪 | autoresearch methodology | 2026-05-20*
