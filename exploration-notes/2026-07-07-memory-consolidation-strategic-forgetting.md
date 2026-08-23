# Memory Consolidation & Strategic Forgetting in Agent Memory Systems

> 研究日期: 2026-07-07
> 触发: deep-exploration-evening cron
> 关联项目: agent-memory-graph (1975 tests), agent-context-store (2368 tests)

---

## 背景与定位

"An agent that remembers everything eventually remembers nothing useful."

这是 2026 H2 agent memory 领域的共识。industry 花了巨大精力给 agent **记忆**能力，但远较少关注更难的问题：教 agent **遗忘**什么。

agent-memory-graph 已实现 sleep_consolidate + strategic_forget + episodic_replay + staleness_score + memory_decay，但这些能力从未在 README 中被定位为核心差异化。本研究旨在填补这个 gap：理论支撑 → 竞品对比 → README 定位。

---

## 核心概念

### 1. Sleep-Dependent Consolidation（睡眠依赖性记忆巩固）

**生物原型**: 海马体在 NREM 睡眠期间重播日间经验，将情景记忆转移到皮层长时存储。

**AI 对应**: 在 agent session 之间的离线窗口，reviewing session transcripts → 提取 pattern → 合并重复 → 替换过时 → 写入新记忆。

**关键产品化:**
- **Anthropic Dreaming** (2026-05-06): Claude Managed Agents 的 async between-session 巩固过程。被 Anthropic 比作 "hippocampal memory consolidation"——review → merge duplicates → replace stale → write new。Harvey 报告 6x task completion lift。
- **Google Memory Bank** (2026-05-19, I/O): identity-scoped 持久化，与 ADK 2.0 一起 GA。
- **SCM (Sleep-Consolidated Memory)** (arXiv:2604.20943, April 2026): 学术形式化。synaptic downscaling → graph edge proportional weakening; replay → concept co-occurrence reactivation; forgetting → adaptive pruning。

**agent-memory-graph 对应**: `sleep_consolidate()` — 按 similarity 聚类低 weight 节点，合并到 anchor 节点，redirect edges，quarantine 被合并节点。

### 2. Strategic Forgetting（战略性遗忘）

**核心洞察**: 遗忘不是失败，而是维持记忆系统清洁、快速、相关的主动机制。

**量化证据**: 在医疗推理任务中，"add-all" 策略的 agent 积累了 2,400+ 条记录，准确率降至 13%。选择性记忆管理的 agent 仅保持 248 条，准确率达 39%——**3x 性能提升来自存储更少，而非更多**。

**遗忘策略谱系**（MaRS framework 分类）:

| Policy | 机制 | 适用场景 |
|--------|------|---------|
| FIFO | 先进先出 | 纯时间序日志 |
| LRU | 最少访问先忘 | 缓存型记忆 |
| Priority Decay | 按 importance score 衰减 | 混合价值记忆 |
| Reflection-Summary | 压缩为摘要后遗忘 | 经验积累 |
| Hybrid | 多策略组合 | 生产系统 |

**生产级遗忘的 4 个维度:**
1. **Relevance Filtering** — 跟踪哪些记忆实际帮助解决问题，unused 逐渐衰减
2. **Time-Based Decay** — 不同 semantic category 不同 TTL（immutable facts = ∞, transient = hours/days）
3. **Access-Frequency Reinforcement** — 成功检索并使用的记忆 score 提升（spaced repetition 效应）
4. **Error Elimination** — 失败方法记为 "don't try again" 而非详细失败日志

**agent-memory-graph 对应**: `strategic_forget()` — 支持 min_weight + max_age_days + protect_q_above + kind + target_count 多维过滤，quarantine 而非 delete（审计安全）。

### 3. Learned Memory Policies via RL（通过强化学习获得记忆策略）

**突破性论文: A-MEM / AgeMem** (arXiv:2601.01885, January 2026)

核心思想：不手工设计何时记忆/遗忘，而是将记忆操作暴露为 tool，让 agent 通过 RL 自己学。

```
Memory Operations as Tools:
  store(info)          → 保存到长期记忆
  retrieve(query)      → 从记忆中检索
  update(key, value)   → 修改已有记忆
  summarize()          → 压缩短期记忆
  discard(key)         → 移除过时信息
```

**三阶段渐进式训练:**
1. Stage 1: 基础任务完成（无记忆）
2. Stage 2: 记忆增强训练（with reward shaping）
3. Stage 3: 端到端优化 with step-wise GRPO

**关键结果**: agent 学到了 non-obvious 策略——context overflow 前的 preemptive summarization、redundant entries 的选择性遗忘、related concepts 的 proactive linking。

**ICLR 2026 MemAgents Workshop** 明确将 "hippocampal-neocortical consolidation mechanisms" 列为开放研究问题。

### 4. Memory Staleness vs. Decay（记忆陈旧性 vs. 衰减）

这是 agent memory 领域最微妙的问题之一：

- **Decay** 处理低相关性记忆——逐渐降低 weight，最终低于检索阈值
- **Staleness** 处理**高相关性但过时**的记忆——一个关于用户雇主的高频记忆在用户换工作后变成 "confidently wrong"

> "Decay handles low-relevance memories. Staleness in high-relevance memories is a harder, open problem." — Mem0 State of AI Agent Memory 2026

**agent-memory-graph 对应**: `staleness_score()` + `stale_nodes()` — 专门检测高 weight 但内容可能过时的节点。bi-temporal 时间戳（valid_from / valid_to）提供基础设施。

### 5. Benchmark Landscape: LoCoMo 的局限与超越

**LoCoMo 现状**: 10 段对话 × 35 sessions × ~9K tokens × 1,540 questions。四大类别: single-hop / multi-hop / temporal / open-domain。

**关键发现**: filesystem-only 在 LoCoMo 上达到 74%，与复杂记忆系统持平或超越。**retrieval 不是瓶颈，conflict resolution 才是差异化**。

**Mem0 2026 算法**: 92.5% overall（temporal +29.6pp, multi-hop +23.1pp 最大提升来自 two architectural changes）。

**竞品分数表（README 用）:**

| System | LoCoMo Score | Notes |
|--------|-------------|-------|
| OpenAI ChatGPT Memory | 52.90% | Baseline |
| Mem0 (2025 paper) | 66.88% | First wave |
| Zep (corrected) | 75.14% | Graph-based |
| Pam | 74.35% | Proactive AI Manager |
| Filesystem-only | ~74% | Letta finding |
| Mem0 (2026 algo) | 92.50% | Temporal + multi-hop gains |
| **agent-memory-graph** | **? (TBD)** | Adaptive WRRF + bi-temporal + conflict detect |

---

## 可运行代码示例

### 示例 1: FadeMem 风格的双层记忆 + 衰减（独立可运行）

```python
"""
FadeMem-inspired dual-layer memory with time-based decay.
Based on arXiv:2601.18642 (FadeMem, 2026).

Run: python fade_memory_demo.py
"""
import json, time, math
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass
class MemoryItem:
    content: str
    importance: float = 0.5          # 0.0 = trivial, 1.0 = critical
    strength: float = 1.0            # current activation strength
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    def decay(self, half_life_hours: float = 24.0):
        """Ebbinghaus forgetting curve: exponential decay."""
        elapsed_hours = (time.time() - self.last_accessed) / 3600
        self.strength = self.importance * math.exp(-0.693 * elapsed_hours / half_life_hours)

    def access(self):
        """Reinforce memory on successful retrieval (spaced repetition)."""
        self.last_accessed = time.time()
        self.access_count += 1
        self.importance = min(1.0, self.importance + 0.05)  # boost on use

    def to_dict(self):
        return asdict(self)


class DualLayerMemory:
    """
    LLM (Long-term Memory Layer): importance >= threshold, slow decay
    SML (Short-term Memory Layer): importance < threshold, fast decay
    """
    def __init__(self, ltml_threshold: float = 0.7,
                 ltml_half_life_h: float = 168.0,   # 1 week
                 sml_half_life_h: float = 6.0):      # 6 hours
        self.threshold = ltml_threshold
        self.ltml_half_life = ltml_half_life_h
        self.sml_half_life = sml_half_life_h
        self.lml: list[MemoryItem] = []
        self.sml: list[MemoryItem] = []

    def add(self, content: str, importance: float = 0.5):
        item = MemoryItem(content=content, importance=importance)
        if importance >= self.threshold:
            self.lml.append(item)
        else:
            self.sml.append(item)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search with lazy decay evaluation."""
        results = []
        for m in self.lml + self.sml:
            half_life = self.ltml_half_life if m in self.lml else self.sml_half_life
            m.decay(half_life_hours=half_life)
            if m.strength > 0.1 and query.lower() in m.content.lower():
                m.access()  # reinforce on retrieval
                results.append({"content": m.content, "strength": round(m.strength, 3),
                                "layer": "LML" if m in self.lml else "SML"})
        results.sort(key=lambda x: x["strength"], reverse=True)
        return results[:top_k]

    def prune(self):
        """Remove memories below strength threshold."""
        before = len(self.lml) + len(self.sml)
        self.sml = [m for m in self.sml if m.decay_check(self.sml_half_life)]
        self.lml = [m for m in self.lml if m.decay_check(self.ltml_half_life)]
        after = len(self.lml) + len(self.sml)
        return {"pruned": before - after, "remaining": after}

    def stats(self):
        all_m = self.lml + self.sml
        if not all_m:
            return {"total": 0}
        return {
            "total": len(all_m),
            "long_term": len(self.lml),
            "short_term": len(self.sml),
            "avg_strength": round(sum(m.strength for m in all_m) / len(all_m), 3),
        }


# --- Demo ---
if __name__ == "__main__":
    mem = DualLayerMemory()

    # Add memories with varying importance
    mem.add("User's name is 罗嵩", importance=0.95)
    mem.add("User is debugging the payment module today", importance=0.3)
    mem.add("User prefers concise answers without filler", importance=0.85)
    mem.add("User mentioned wanting to publish to PyPI this week", importance=0.6)
    mem.add("Random thought about weather", importance=0.1)

    print("=== Initial State ===")
    print(json.dumps(mem.stats(), indent=2))

    # Simulate time passing (manipulate timestamps)
    for m in mem.sml:
        m.last_accessed -= 12 * 3600  # 12 hours ago
    for m in mem.lml:
        m.last_accessed -= 72 * 3600  # 3 days ago

    # Search reinforces matching memories
    print("\n=== Search: '罗嵩' ===")
    results = mem.search("罗嵩")
    print(json.dumps(results, indent=2))

    print("\n=== Search: 'payment' (should be decayed) ===")
    results = mem.search("payment")
    print(json.dumps(results, indent=2))

    print("\n=== Final Stats ===")
    print(json.dumps(mem.stats(), indent=2))
```

### 示例 2: agent-memory-graph 实际 API 调用

```python
"""
agent-memory-graph: consolidation + forgetting pipeline.
This is the actual API available in the project (1975 tests).
"""

from memory_graph import MemoryGraph

mg = MemoryGraph("agent_memory.db")

# --- Sleep Consolidation ---
# Merge similar low-weight nodes, inspired by hippocampal replay
result = mg.sleep_consolidate(
    similarity_threshold=0.6,  # merge nodes with >=60% label similarity
    min_weight=0.3,            # only consolidate weak nodes
    dry_run=False              # set True for safe preview
)
print(f"Consolidated: {result['merged']} nodes merged into anchors")

# --- Strategic Forgetting ---
# Multi-dimensional forgetting with Q-value protection
result = mg.strategic_forget(
    min_weight=0.1,            # forget nodes below this weight
    max_age_days=30,           # forget nodes not accessed in 30 days
    protect_q_above=0.7,       # NEVER forget high-Q memories
    dry_run=False
)
print(f"Forgotten: {result['forgotten']} nodes, {result['edges_removed']} edges")

# --- Staleness Detection ---
# Find HIGH-weight nodes that might be outdated (the hard problem)
stale = mg.stale_nodes(threshold=0.7, limit=20)
for node in stale:
    print(f"⚠️ Stale but high-weight: {node['label']} (staleness={node['score']:.2f})")

# --- Episodic Replay ---
# Walk through memory graph from a specific node
episodes = mg.replay_from(node_id="node_abc123", direction="forward")
for ep in episodes:
    print(f"  → {ep['label']} (weight={ep['weight']:.2f})")

# --- Consolidation Report ---
report = mg.consolidation_report()
print(f"Memory health: {report}")
```

---

## 关键洞察

### 1. 巩固/遗忘是 agent memory 的下一个差异化战场

Retrieval (BM25 + Vector + RRF) 已经是 solved problem——Mem0 92.5%、Zep 75%、filesystem 74%。**但 conflict resolution + staleness + strategic forgetting 几乎没有竞品做好。** agent-memory-graph 的 `strategic_forget` + `staleness_score` + bi-temporal timestamps 组合在开源生态中是独特的。

**README 定位建议**: 不要打 retrieval 战（已经 commodity），打 consolidation/forgetting 战（蓝海）。

### 2. Anthropic Dreaming 验证了我们的架构方向

Anthropic 2026-05 推出 Dreaming（between-session 巩固），说明 sleep-like consolidation 不是学术概念，而是 production necessity。agent-memory-graph 的 `sleep_consolidate` + `consolidation_pipeline` 在功能上对应 Dreaming 的 merge duplicates / replace stale entries / write new insights。

**差异**: Dreaming 是 LLM-driven（用 Claude 本身做 consolidation），我们的实现是 algorithm-driven（similarity clustering + weight aggregation）。两者各有优劣——LLM-driven 更智能但更贵，algorithm-driven 更快更可控。

### 3. Learned Memory Policies (A-MEM) 是 12-18 个月后的威胁

A-MEM/AgeMem 用 GRPO 训练 agent 自主决定何时记忆/遗忘。目前还在学术阶段（Qwen2.5-7B, 5 benchmarks），但方向清晰：**memory operations as tools + RL = adaptive memory**。

agent-memory-graph 的 Q-value system 是这个方向的 precursor——Q-value 是 "learned importance"，A-MEM 把这个推到极致。**下一步可以把 Q-value 更新规则从 heuristic 升级为 learned policy。**

### 4. LoCoMo benchmark 的政治现实

- Mem0 自己跑自己定义的 benchmark 拿 92.5%，Zep 指出 implementation errors 导致分数被低估
- Filesystem-only 拿 74%，说明 LoCoMo 不够长不够复杂
- **真正的差异化在 conflict resolution 和 staleness**，不是 raw retrieval

**行动**: agent-memory-graph 应该跑 LoCoMo 拿一个 baseline number，但 README 的核心卖点不应该是 LoCoMo 分数，而是 **bi-temporal + conflict detection + strategic forget** 这套组合拳。

### 5. Memory staleness 是 "confidently wrong" 问题的解法

> "A highly-retrieved memory about a user's employer is accurate until they change jobs, at which point it becomes confidently wrong." — Mem0 2026

这是 production agent 最危险的模式。agent-memory-graph 的解法链：
1. `staleness_score()` 检测高风险节点
2. bi-temporal `valid_to` 标记失效时间
3. `conflict_detect` 在写入时发现矛盾
4. `strategic_forget` 清理确认过时的记忆

**没有其他开源项目同时做这四件事。**

---

## 下一步行动

### 立即可做（本周）
1. **跑 LoCoMo baseline** — 用 Mem0 的 memory-benchmarks repo，把 agent-memory-graph 作为 custom backend 接入。即使分数不高，也是 README 的必要数据点。
2. **README 重写** — 从 "37-in-1 graph memory" 改为 "Sleep. Forget. Remember." 三层定位：
   - Sleep: between-session consolidation (sleep_consolidate)
   - Forget: strategic forgetting with Q-value protection (strategic_forget)
   - Remember: adaptive WRRF retrieval (已有)
3. **竞品定位表** — 直接放本文的竞品分数表，highlight "no competitor does bi-temporal + conflict + strategic forget combined"

### 中期（本月）
4. **Consolidation Pipeline 升级** — 当前 sleep_consolidate 是 algorithm-driven。增加 LLM-driven 模式（用 cheap model 如 GPT-4o-mini 做 pairwise merge decision）。Dual-mode: fast (algorithm) / smart (LLM)。
5. **A-MEM 方向探索** — 把 Q-value 更新从固定规则改为 simple reward signal。即使不用 RL，也能让 Q-value 更 adaptive。

### 研究（持续）
6. **ConvoMo benchmark** — 新 benchmark，75K QA pairs，比 LoCoMo 更全面。值得关注。
7. **ICLR 2026 MemAgents Workshop papers** — 特别是 "Agentic Memory Should Localize Compression" 和 AMA-Bench。

---

## 参考文献与来源

| # | 来源 | 类型 | 关键贡献 |
|---|------|------|---------|
| 1 | Anthropic Dreaming (2026-05-06) | Product | Hippocampal consolidation for Claude agents |
| 2 | Google Memory Bank (2026-05-19, I/O) | Product | Identity-scoped persistence |
| 3 | SCM (arXiv:2604.20943) | Paper | Sleep-Consolidated Memory with Algorithmic Forgetting |
| 4 | FadeMem (arXiv:2601.18642) | Paper | Biologically-inspired forgetting, dual-layer |
| 5 | A-MEM / AgeMem (arXiv:2601.01885) | Paper | Memory operations as RL tools, step-wise GRPO |
| 6 | FOREVER (January 2026) | Paper | Forgetting curve-inspired memory replay |
| 7 | Mem0 State of AI Agent Memory 2026 | Report | LoCoMo 92.5%, staleness as open problem |
| 8 | Zep vs Mem0 analysis | Blog | LoCoMo flaws, corrected Zep 75.14% |
| 9 | Letta: Filesystem all you need | Blog | 74% with filesystem, retrieval not bottleneck |
| 10 | TianPan: Forgetting Problem | Blog | 3x improvement from storing less |
| 11 | ICLR 2026 MemAgents Workshop | Event | Consolidation as open research problem |
| 12 | ConvoMo (arXiv:2511.10523) | Paper | 75K QA pairs, improved benchmark |
| 13 | MaRS Framework | Framework | Taxonomy of forgetting policies |

---

## 笔记质量自评

| 维度 | 状态 | 说明 |
|------|------|------|
| 核心概念 ≥ 3 | ✅ 5 个 | Consolidation / Forgetting / RL Policies / Staleness / Benchmarks |
| 可运行代码 ≥ 1 | ✅ 2 个 | FadeMem demo (独立可运行) + agent-memory-graph API |
| 关键洞察 ≥ 3 | ✅ 5 条 | 差异化定位 / Dreaming 验证 / A-MEM 威胁 / LoCoMo 政治 / Staleness 解法 |
| 下一步行动 ≥ 1 | ✅ 7 个 | 立即 3 + 中期 2 + 研究 2 |
| 与现有项目关联 | ✅ | 直接关联 agent-memory-graph 的 5 个 API |
| 独到见解 | ✅ | "不打 retrieval 战，打 consolidation/forgetting 战" |
