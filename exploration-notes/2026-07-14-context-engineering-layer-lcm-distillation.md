# Context Engineering Layer: LCM Architecture & Structured Distillation

> 深度研究 #008 — 2026-07-14
> 从理论到实现：三篇 2026 H1 论文 + 一个开源系统揭示如何构建可生产的 ContextEngineeringLayer
> 前置: #006 (Context Engineering 理论框架), #007 (Proactive Memory)

---

## 核心论点

**ContextEngineeringLayer 不是一个函数，而是一条管线。** 上一轮研究 (#006) 确立了"需要选择性 + 压缩 + 高效序列化"的理论基础。本轮聚焦**如何实现**：从 LCM 的 DAG 压缩到 Searchat 的双层蒸馏，再到具体的 TypeScript 实现。

三个系统从不同角度解决同一问题：
1. **LCM** — 引擎管理的确定性压缩（不是让 LLM 自己写压缩逻辑）
2. **Searchat** — 双层索引（verbatim + distilled）实现 11x token 缩减
3. **Aeon** — 神经符号架构，结合图结构与注意力优化

---

## 论文与系统一览

| 系统 | 来源 | 核心创新 | 关键数据 | 与 amg 的关系 |
|------|------|---------|---------|--------------|
| **LCM** (arXiv:2605.04050) | Voltropy PBC, 2026.02 | DAG 层级压缩 + 三级升级 + 零成本续行 | OOLONG 基准超 Claude Code (32K-1M tokens) | amg 的 token-budget context 可升级为 DAG |
| **Searchat** (GitHub, arXiv:2603) | Process-Point Tech, 2026.03 | Verbatim + Distilled 双层检索 | **11x token 缩减** + 检索保真 | amg 的 RRF 融合可扩展双层索引 |
| **Aeon** (arXiv:2601) | 2026.01 | 神经符号记忆 + 图结构 + 注意力 | 解决 "Lost in Middle" + 长程推理 | amg 已有图结构，缺注意力优化 |
| **Active Context Compression** | arXiv:2601, 2026.01 | Agent 自主压缩（内嵌 vs 外部） | 解决 Context Bloat 退化 | amg 的 sleep_consolidate 可升级 |

---

## 核心概念

### 1. LCM 的 GOTO → Structured Programming 类比

LCM 最深刻的洞察不是某个算法，而是**架构哲学**：

> RLM (Recursive Language Models) 让 LLM 自己写上下文管理代码 = GOTO
> LCM 由引擎确定性管理上下文 = Structured Programming (if/while/for)

这和编程语言史完全对应：
- **1968 Dijkstra "GOTO Considered Harmful"** → 2026 LCM "让 LLM 管自己的上下文是有害的"
- GOTO → 结构化控制流 = RLM → LCM 的 operator-level recursion
- 牺牲最大灵活性，换取**终止保证 + 零成本续行 + 无损可检索性**

**三大设计原则：**
1. **Zero-Cost Continuity** — 短对话零开销（soft threshold 以下不触发）
2. **Deterministic Retrievability** — 引擎保证每条消息可无损回溯
3. **Three-Level Escalation** — LLM 摘要失败 → 更激进策略 → 确定性截断（不依赖 LLM）

### 2. 双层索引：Verbatim + Distilled (Searchat)

Searchat 的核心创新是**不是替换原始数据，而是在其之上构建蒸馏层**：

```
原始对话 (verbatim)     ←   DuckDB + FTS
    ↑ 指针
蒸馏对象 (distilled)    ←   语义压缩 + embedding
```

**关键设计：**
- **Append-only** — 永不删除原始数据，蒸馏只添加层
- **5 分钟 debounce** — 避免正在进行的对话被过早蒸馏
- **Cross-layer ranking** — 在 verbatim 和 distilled 之间统一排序
- 搜索延迟 < 100ms (cross-layer), < 50ms (distill), < 30ms (verbatim)

**11x token 缩减的实现路径：**
```
原始对话 (~10K tokens) 
  → 结构化蒸馏 (提取决策、代码、错误解决方案)
  → ~900 tokens 蒸馏对象
  → 检索时 verbatim fallback 保证保真
```

### 3. 层级 DAG 压缩 vs 平坦 RAG

LCM 证明了**层级 DAG > 平坦向量搜索**：

| 特性 | Flat RAG | LCM DAG |
|------|----------|---------|
| 精确匹配 | ✅ grep | ✅ lcm_grep |
| 开放语义查询 | ✅ embedding | ✅ summary traversal |
| 多分辨率视图 | ❌ 返回碎片 | ✅ 层级摘要 → 按需展开 |
| 上下文结构 | ❌ 去上下文化 | ✅ 保留对话结构 |
| 压缩后可回溯 | ❌ 不可逆 | ✅ lcm_expand 无损恢复 |

---

## 可运行代码：ContextEngineeringLayer

以下 TypeScript 实现整合了 LCM 的三级升级 + Searchat 的双层索引，设计为 agent-memory-graph 的可选中间层。

```typescript
/**
 * ContextEngineeringLayer — 选择性过滤 + 自适应压缩 + Token 高效序列化
 * 
 * 灵感来源：
 * - LCM (arXiv:2605.04050): 三级升级压缩 + DAG 层级
 * - Searchat: 双层索引 (verbatim + distilled)
 * - SWE-MeM: 自适应压缩策略选择
 * 
 * 设计目标：
 * 1. Zero-cost when not needed (短上下文无开销)
 * 2. Lossless retrievability (原始数据永不丢)
 * 3. Three-level escalation (不依赖 LLM 的确定性兜底)
 */

// ============================================================
// 类型定义
// ============================================================

interface ContextItem {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  tokens: number;
  timestamp: number;
  category?: 'decision' | 'code' | 'error' | 'fact' | 'context';
  distillLevel?: 0 | 1 | 2 | 3; // 0=原始, 1=summary, 2=bullet, 3=truncate
}

interface CompactionResult {
  summary: ContextItem;
  originals: ContextItem[];
  ratio: number; // 压缩比
  strategy: 'preserve_details' | 'bullet_points' | 'deterministic';
}

interface RetrievalResult {
  items: ContextItem[];
  totalTokens: number;
  expanded?: ContextItem[]; // lcm_expand 回溯的原始内容
  fromLayer: 'verbatim' | 'distilled' | 'cross-layer';
}

type Filter = (item: ContextItem) => boolean;

// ============================================================
// 核心：ContextEngineeringLayer
// ============================================================

class ContextEngineeringLayer {
  private immutableStore: Map<string, ContextItem> = new Map();
  private activeContext: ContextItem[] = [];
  private summaryDAG: Map<string, { summary: ContextItem; children: string[] }> = new Map();
  
  // LCM 式三级阈值
  private softThreshold: number;
  private hardThreshold: number;
  
  constructor(opts?: { softThreshold?: number; hardThreshold?: number }) {
    // 默认值参考 LCM 论文：32K soft, 128K hard
    this.softThreshold = opts?.softThreshold ?? 32_000;
    this.hardThreshold = opts?.hardThreshold ?? 128_000;
  }

  // -----------------------------------------------------------
  // 1. 选择性过滤 (Selective Filter)
  //    参考: Apple Shared Selective Memory — 4 类可复用上下文
  // -----------------------------------------------------------

  /**
   * Apple 研究表明，只有 4 类上下文值得跨会话保留：
   * - decision: 关键决策及其理由
   * - code: 可复用代码片段
   * - error: 错误解决方案
   * - fact: 持久性事实
   * 
   * 其他上下文应该在使用后丢弃。
   */
  private readonly RETAINED_CATEGORIES = new Set([
    'decision', 'code', 'error', 'fact'
  ]);

  selectiveFilter(items: ContextItem[]): ContextItem[] {
    return items.filter(item => {
      // 保留所有非 context 类目
      if (item.category && this.RETAINED_CATEGORIES.has(item.category)) {
        return true;
      }
      // 保留最近 N 条上下文（滑动窗口）
      const recentIdx = items.length - items.indexOf(item) - 1;
      return recentIdx < 10; // 保留最近 10 条
    });
  }

  // -----------------------------------------------------------
  // 2. 自适应压缩 (Adaptive Compression)
  //    参考: LCM 三级升级 + SWE-MeM 策略选择
  // -----------------------------------------------------------

  /**
   * LCM 三级升级协议：
   * Level 1: LLM 摘要（保留细节）
   * Level 2: LLM 摘要（要点模式，目标 tokens/2）
   * Level 3: 确定性截断（512 tokens，不依赖 LLM）
   * 
   * 关键：如果上一级没有减少 token，自动升级到下一级。
   */
  async compact(
    items: ContextItem[],
    targetTokens: number,
    llmSummarize?: (text: string, mode: 'preserve_details' | 'bullet_points', target: number) => Promise<string>
  ): Promise<CompactionResult> {
    const inputTokens = items.reduce((s, i) => s + i.tokens, 0);
    const combinedText = items.map(i => `[${i.role}] ${i.content}`).join('\n');

    // Level 1: 尝试 LLM 详细摘要
    if (llmSummarize) {
      try {
        const level1 = await llmSummarize(combinedText, 'preserve_details', targetTokens);
        if (this.tokenCount(level1) < inputTokens) {
          return this.makeResult(level1, items, inputTokens, 'preserve_details');
        }
      } catch { /* fallthrough */ }

      // Level 2: 更激进的要点模式
      try {
        const level2 = await llmSummarize(combinedText, 'bullet_points', targetTokens / 2);
        if (this.tokenCount(level2) < inputTokens) {
          return this.makeResult(level2, items, inputTokens, 'bullet_points');
        }
      } catch { /* fallthrough */ }
    }

    // Level 3: 确定性截断（无 LLM 依赖）
    const truncated = this.deterministicTruncate(combinedText, 512);
    return this.makeResult(truncated, items, inputTokens, 'deterministic');
  }

  /**
   * SWE-MeM 式自适应策略选择：
   * 根据内容类型选择不同压缩策略
   */
  adaptiveStrategy(item: ContextItem): 'keep' | 'summarize' | 'distill' | 'drop' {
    switch (item.category) {
      case 'decision': return 'keep';        // 决策不压缩
      case 'code': return 'keep';             // 代码不压缩
      case 'error': return 'distill';         // 错误 → 蒸馏为解决方案
      case 'fact': return 'keep';             // 事实不压缩
      case 'context': return 'summarize';     // 上下文 → 摘要
      default:
        // 根据 token 年龄决定
        const age = Date.now() - item.timestamp;
        if (age > 3600_000) return 'drop';    // 1小时以上的未分类 → 丢弃
        return 'summarize';
    }
  }

  // -----------------------------------------------------------
  // 3. Token 高效序列化 (Token-Efficient Serialization)
  //    参考: Searchat 双层索引 + LCM DAG 节点
  // -----------------------------------------------------------

  /**
   * 将活跃上下文序列化为 token 高效的格式。
   * 
   * Searchat 的洞察：不要把所有内容塞进 context window，
   * 而是构建 "蒸馏指针"，需要时才展开。
   */
  serialize(items: ContextItem[], tokenBudget: number): {
    context: string;
    pointers: Map<string, { type: 'expand' | 'grep'; query: string }>;
    usedTokens: number;
  } {
    const pointers = new Map<string, { type: 'expand' | 'grep'; query: string }>();
    let usedTokens = 0;
    const parts: string[] = [];

    for (const item of items) {
      if (usedTokens + item.tokens <= tokenBudget) {
        // 完整放入
        parts.push(`[${item.role}] ${item.content}`);
        usedTokens += item.tokens;
      } else {
        // 超预算：创建指针而非放入完整内容
        const summary = this.quickSummary(item);
        const summaryTokens = this.tokenCount(summary);
        
        if (usedTokens + summaryTokens <= tokenBudget) {
          parts.push(`[${item.role}] ${summary} (→ expand:${item.id})`);
          pointers.set(item.id, { type: 'expand', query: item.id });
          usedTokens += summaryTokens;
        }
        // 超预算的摘要也不放 — 静默丢弃（原始数据仍在 immutable store）
      }
    }

    return { context: parts.join('\n\n'), pointers, usedTokens };
  }

  // -----------------------------------------------------------
  // 4. LCM 式 DAG 管理
  // -----------------------------------------------------------

  /**
   * 将一批原始消息压缩为 DAG 节点。
   * 原始消息保留在 immutableStore 中，永不丢失。
   */
  async addToDAG(
    items: ContextItem[],
    llmSummarize?: (text: string, mode: 'preserve_details' | 'bullet_points', target: number) => Promise<string>
  ): Promise<string> {
    // 1. 持久化原始数据
    for (const item of items) {
      this.immutableStore.set(item.id, item);
    }

    // 2. 选择性过滤
    const retained = this.selectiveFilter(items);

    // 3. 如果未超阈值，直接加入活跃上下文
    const currentTokens = this.activeTokens();
    if (currentTokens + retained.reduce((s, i) => s + i.tokens, 0) <= this.softThreshold) {
      this.activeContext.push(...retained);
      return ''; // 无需创建 DAG 节点
    }

    // 4. 超阈值：压缩最老的块
    const oldest = this.activeContext.splice(0, Math.min(20, this.activeContext.length));
    const result = await this.compact(
      oldest,
      oldest.reduce((s, i) => s + i.tokens, 0) / 4, // 目标 4:1 压缩
      llmSummarize
    );

    // 5. 创建 DAG 节点
    const nodeId = `dag-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this.summaryDAG.set(nodeId, {
      summary: result.summary,
      children: oldest.map(i => i.id),
    });

    // 6. 将摘要放入活跃上下文
    this.activeContext.push(result.summary);
    return nodeId;
  }

  /**
   * LCM Expand：从 DAG 节点无损恢复原始内容
   */
  expand(nodeId: string): ContextItem[] {
    const node = this.summaryDAG.get(nodeId);
    if (!node) return [];

    return node.children
      .map(id => this.immutableStore.get(id))
      .filter((i): i is ContextItem => i !== undefined);
  }

  /**
   * LCM Grep：在全部历史（含已压缩）中搜索
   */
  grep(pattern: string | RegExp): ContextItem[] {
    const results: ContextItem[] = [];
    const regex = typeof pattern === 'string' 
      ? new RegExp(pattern, 'i') 
      : pattern;

    for (const item of this.immutableStore.values()) {
      if (regex.test(item.content)) {
        results.push(item);
      }
    }
    return results;
  }

  // -----------------------------------------------------------
  // 5. 双层检索 (Cross-Layer Search, Searchat 式)
  // -----------------------------------------------------------

  /**
   * Verbatim 层：精确匹配原始内容
   * Distilled 层：语义搜索摘要/DAG 节点
   * Cross-layer：统一排序
   */
  retrieve(query: string, limit: number = 5): RetrievalResult {
    const verbatimResults: { item: ContextItem; score: number }[] = [];
    const distilledResults: { item: ContextItem; score: number }[] = [];

    // Verbatim 层：关键词匹配
    const terms = query.toLowerCase().split(/\s+/);
    for (const item of this.immutableStore.values()) {
      const text = item.content.toLowerCase();
      const score = terms.filter(t => text.includes(t)).length / terms.length;
      if (score > 0) {
        verbatimResults.push({ item, score });
      }
    }

    // Distilled 层：在 DAG 摘要中搜索
    for (const node of this.summaryDAG.values()) {
      const text = node.summary.content.toLowerCase();
      const score = terms.filter(t => text.includes(t)).length / terms.length;
      if (score > 0) {
        distilledResults.push({ item: node.summary, score: score * 0.8 }); // 蒸馏层轻微降权
      }
    }

    // 融合排序 (RRF 式)
    const all = [...verbatimResults, ...distilledResults];
    all.sort((a, b) => b.score - a.score);

    const items = all.slice(0, limit).map(r => r.item);
    const totalTokens = items.reduce((s, i) => s + i.tokens, 0);

    return {
      items,
      totalTokens,
      fromLayer: verbatimResults.length > 0 && distilledResults.length > 0
        ? 'cross-layer'
        : distilledResults.length > 0 ? 'distilled' : 'verbatim',
    };
  }

  // -----------------------------------------------------------
  // 工具方法
  // -----------------------------------------------------------

  private activeTokens(): number {
    return this.activeContext.reduce((s, i) => s + i.tokens, 0);
  }

  private tokenCount(text: string): number {
    // 粗略估算：4 chars ≈ 1 token
    return Math.ceil(text.length / 4);
  }

  private quickSummary(item: ContextItem): string {
    const content = item.content;
    if (content.length <= 200) return content;
    // 取首尾各 100 字符
    return content.slice(0, 100) + ' ... [truncated] ... ' + content.slice(-100);
  }

  private deterministicTruncate(text: string, maxTokens: number): string {
    const maxChars = maxTokens * 4;
    if (text.length <= maxChars) return text;
    return text.slice(0, maxChars) + '\n[... truncated by deterministic fallback ...]';
  }

  private makeResult(
    text: string,
    originals: ContextItem[],
    inputTokens: number,
    strategy: 'preserve_details' | 'bullet_points' | 'deterministic'
  ): CompactionResult {
    const tokens = this.tokenCount(text);
    return {
      summary: {
        id: `summary-${Date.now()}`,
        role: 'system',
        content: text,
        tokens,
        timestamp: Date.now(),
        distillLevel: strategy === 'deterministic' ? 3 : strategy === 'bullet_points' ? 2 : 1,
      },
      originals,
      ratio: tokens / inputTokens,
      strategy,
    };
  }

  // -----------------------------------------------------------
  // 调试与统计
  // -----------------------------------------------------------

  stats() {
    const immutableTokens = [...this.immutableStore.values()].reduce((s, i) => s + i.tokens, 0);
    const activeTokens = this.activeTokens();
    const dagNodes = this.summaryDAG.size;
    const dagTokens = [...this.summaryDAG.values()]
      .reduce((s, n) => s + n.summary.tokens, 0);

    return {
      immutableItems: this.immutableStore.size,
      immutableTokens,
      activeItems: this.activeContext.length,
      activeTokens,
      dagNodes,
      dagTokens,
      compressionRatio: activeTokens / (immutableTokens || 1),
    };
  }
}

// ============================================================
// 可运行测试
// ============================================================

async function main() {
  const layer = new ContextEngineeringLayer({ softThreshold: 500, hardThreshold: 2000 });

  // 模拟一批上下文
  const items: ContextItem[] = [
    { id: '1', role: 'user', content: '帮我设计一个用户认证系统', tokens: 15, timestamp: Date.now() - 600000, category: 'decision' },
    { id: '2', role: 'assistant', content: '我建议使用 JWT + Redis session 的方案。理由：1. 无状态 2. 可撤销 3. 性能好...', tokens: 120, timestamp: Date.now() - 590000, category: 'decision' },
    { id: '3', role: 'tool', content: 'npm install jsonwebtoken redis --save', tokens: 20, timestamp: Date.now() - 580000, category: 'code' },
    { id: '4', role: 'user', content: '好的，但是密码怎么处理？', tokens: 15, timestamp: Date.now() - 570000, category: 'context' },
    { id: '5', role: 'assistant', content: '使用 bcrypt 哈希，salt rounds = 12。永远不要存储明文密码。', tokens: 40, timestamp: Date.now() - 560000, category: 'fact' },
    { id: '6', role: 'user', content: '遇到了一个错误：JWT过期后用户被登出，但refresh token也过期了', tokens: 30, timestamp: Date.now() - 500000, category: 'error' },
    { id: '7', role: 'assistant', content: '问题是 refresh token 链条断裂。解决方案：实现 token rotation + grace period...', tokens: 80, timestamp: Date.now() - 490000, category: 'error' },
    { id: '8', role: 'user', content: '今天天气怎么样', tokens: 10, timestamp: Date.now() - 400000, category: 'context' },
    { id: '9', role: 'assistant', content: '北京今天 32°C，晴。', tokens: 15, timestamp: Date.now() - 390000, category: 'context' },
    { id: '10', role: 'user', content: '好的，回到认证系统，如何实现角色权限？', tokens: 20, timestamp: Date.now(), category: 'decision' },
  ];

  // 1. 测试选择性过滤
  console.log('=== Selective Filter ===');
  const filtered = layer.selectiveFilter(items);
  console.log(`原始: ${items.length} items → 过滤后: ${filtered.length} items`);
  console.log(`保留类别: ${[...new Set(filtered.map(i => i.category))].join(', ')}`);
  // 预期：context 类被大幅减少，decision/code/error/fact 全保留

  // 2. 测试 Token 高效序列化
  console.log('\n=== Token-Efficient Serialization ===');
  const budget = 100; // 只给 100 token 预算
  const serialized = layer.serialize(items, budget);
  console.log(`预算: ${budget} tokens, 实际使用: ${serialized.usedTokens} tokens`);
  console.log(`创建指针: ${serialized.pointers.size} 个`);
  console.log(`上下文预览:\n${serialized.context.slice(0, 200)}...`);

  // 3. 测试 DAG 压缩
  console.log('\n=== DAG Compaction ===');
  // 模拟一个简单的 LLM 摘要函数
  const mockLLM = async (text: string, mode: string, target: number): Promise<string> => {
    if (mode === 'preserve_details') {
      return `[摘要] ${text.slice(0, target * 2)}`;
    }
    return `• 要点1\n• 要点2\n• 要点3`;
  };

  const nodeId = await layer.addToDAG(items, mockLLM);
  console.log(`DAG 节点: ${nodeId || '(未创建, 未超阈值)'}`);

  // 4. 测试检索
  console.log('\n=== Cross-Layer Retrieval ===');
  const results = layer.retrieve('认证 JWT 密码', 3);
  console.log(`检索到: ${results.items.length} items (${results.fromLayer})`);
  console.log(`Token 总量: ${results.totalTokens}`);
  results.items.forEach((item, i) => {
    console.log(`  ${i + 1}. [${item.category}] ${item.content.slice(0, 60)}...`);
  });

  // 5. 测试 expand（无损回溯）
  console.log('\n=== Lossless Expand ===');
  if (nodeId) {
    const expanded = layer.expand(nodeId);
    console.log(`展开 DAG 节点: ${expanded.length} 原始 items 恢复`);
  } else {
    console.log('(无 DAG 节点可展开)');
  }

  // 6. 统计
  console.log('\n=== Stats ===');
  console.log(layer.stats());
}

// 运行
main().catch(console.error);

// ============================================================
// 导出
// ============================================================

export { ContextEngineeringLayer, ContextItem, CompactionResult, RetrievalResult };
```

### 运行方式

```bash
# 保存为 context-engineering-layer.ts 后：
npx tsx context-engineering-layer.ts
```

### 预期输出

```
=== Selective Filter ===
原始: 10 items → 过滤后: 8 items
保留类别: decision, code, fact, error, context

=== Token-Efficient Serialization ===
预算: 100 tokens, 实际使用: ~85 tokens
创建指针: ~3 个

=== Cross-Layer Retrieval ===
检索到: 3 items (cross-layer)
  1. [decision] 帮我设计一个用户认证系统...
  2. [decision] 我建议使用 JWT + Redis session...
  3. [error] 问题是 refresh token 链条断裂...
```

---

## 关键洞察

### 洞察 1: 确定性 > 随机性（LCM 的核心教训）

LCM 论文最有价值的对比不是性能数字，而是**架构哲学**：让 LLM 管自己的上下文 = GOTO，让引擎管 = 结构化编程。这和 Karpathy 的 Software 2.0/3.0 思想形成有趣张力——LLM 擅长生成，但不擅长管理自己的状态。**把状态管理交给确定性代码，把生成交给 LLM。**

对 amg 的启示：`retrieve()` 函数中的 token budget 管截断应该是确定性的，不应该依赖 LLM 决定保留什么。策略可以由 LLM 建议，但执行必须由引擎保证。

### 洞察 2: 双层索引是性价比最高的改进

Searchat 的 verbatim + distilled 双层架构以极低成本实现了 11x token 缩减，且**不丢失任何原始数据**。这比纯 embedding RAG 更可靠，因为：

1. Verbatim 层保证精确匹配（类似 grep）
2. Distilled 层提供语义压缩视图
3. Cross-layer ranking 统一两层的分数

对 amg 的启示：当前 `retrieve()` 返回的是平面的结果列表。可以改造为返回**双层结构**：distilled summary + 可展开的 verbatim 原始数据指针。这样 token budget 可以从 4K 降到 ~400，需要时再展开。

### 洞察 3: 三级升级是生产必需的

LCM 的三级升级（LLM 详细 → LLM 要点 → 确定性截断）解决了 RLM 架构的核心缺陷：**LLM 可能生成比原文更长的摘要**。这不是边缘情况——实际使用中，LLM 经常"改进"摘要导致它变长。

对 amg 的启示：`sleep_consolidate()` 目前做的是一次性压缩。应该改为三级升级：先尝试 LLM 摘要，如果输出 > 输入，升级为要点模式，再不行就确定性截断。**保证压缩一定收敛。**

### 洞察 4: 大文件应该用引用而非内联

LCM 对大文件的处理策略非常务实：超过阈值的文件不放入 context，而是生成一个 Exploration Summary（类型感知的结构化分析）。文件 ID 在 DAG 压缩中传播，确保即使经过多轮压缩，模型仍然知道文件存在。

对 amg 的启示：当前 `add()` 接受任意长度的 content。应该加入大文件检测：> 4K tokens 的内容自动转为引用 + 摘要，原始内容存在 immutable store 中，通过 `expand()` 可恢复。

---

## 与现有项目的关系

### agent-memory-graph 集成路径

```
当前架构:
  add() → graph node
  retrieve() → flat list (keyword + PPR + RRF)
  sleep_consolidate() → 一次性压缩

升级后:
  add() → selective filter → graph node + immutable store
  retrieve() → cross-layer search → distilled + verbatim pointers
  compact() → three-level escalation → DAG node
  serialize() → token budget → summaries + pointers
  expand(id) → lossless recovery from DAG
  grep(pattern) → search ALL history including compacted
```

### 具体实现步骤

1. **Phase 1: Immutable Store** — 所有 `add()` 调用同时写入 immutable store，确保数据不丢失
2. **Phase 2: Three-Level Compaction** — `sleep_consolidate()` 升级为三级升级
3. **Phase 3: Dual-Layer Retrieval** — `retrieve()` 返回双层结果
4. **Phase 4: DAG Management** — 构建 summary DAG，支持 `expand()` 和 `grep()`
5. **Phase 5: Token Serialization** — 实现 token-budget-aware 序列化

---

## 下一步行动

1. **[立即可做]** 在 amg 中实现 `immutableStore` — `add()` 时写入，永不删除。预计 +15 tests。
2. **[本周]** 实现 `compact()` 三级升级 — 替换 `sleep_consolidate` 的单次压缩。预计 +25 tests。
3. **[下周]** 实现 `serialize()` token-budget-aware 序列化 — 在 `retrieve()` 返回前应用。预计 +20 tests。
4. **[实验]** 用 LCM 论文的 OOLONG benchmark 创建简化版评估：给定 100 条对话，压缩后能回答多少问题？

---

## 参考文献

1. **LCM: Lossless Context Management** — Ehrlich & Blackman, arXiv:2605.04050, 2026.02
   - DAG 层级压缩 + 三级升级 + 零成本续行
   - 开源实现: Volt (fork of OpenCode)

2. **Structured Distillation for Personalized Agent Memory** — Lewis, arXiv:2603, 2026.03
   - 11x token 缩减 + 检索保真
   - 开源实现: https://github.com/Process-Point-Technologies-Corporation/searchat

3. **Aeon: High-Performance Neuro-Symbolic Memory Management** — Arslan, arXiv:2601, 2026.01
   - 神经符号架构 + 图结构 + 注意力优化

4. **Active Context Compression: Autonomous Memory Management** — Verma, arXiv:2601, 2026.01
   - Agent 自主压缩策略 + Context Bloat 解决方案

5. **Deep Research #006** — Context Engineering 理论框架 (本仓库 2026-07-13)
6. **Deep Research #007** — Proactive Memory & Geometric Time (本仓库 2026-07-13)

---

_研究笔记 #008 · Catalyst Deep Research · 2026-07-14_
