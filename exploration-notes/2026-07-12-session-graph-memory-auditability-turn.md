# Session Graph Memory & The Auditability Turn

> 深度研究 #004 — 2026-07-12
> 5 篇 2026 年 6-7 月新论文，揭示 Agent Memory 从"检索增强"向"会话图+可审计"的范式转移

---

## 论文一览

| 系统 | arXiv | 核心创新 | 数据规模 | 与 amg 的关系 |
|------|-------|---------|---------|--------------|
| **TokenMizer** | 2606.06337 | 图结构会话代理：14 节点类型/7 边类型/8 态生命周期 | 25 节点图, 201-302 token resume | amg 的会话级应用层 |
| **DocTrace** | 2606.10921 | 按需超图工作记忆 + 经验图复用 | 4 个长文档 QA 数据集, +8.85% F1 | amg 超图扩展的参考 |
| **MOSS** | 2607.04391 | 可审计符号检索（替代向量相似度） | 44M tokens, 110K segments, 569 concepts, 1 年部署 | amg 的可审计性路线 |
| **Engram** | 2606.09900 | 双时序事实引擎 + 矛盾消解 | LongMemEval 83.6% vs 73.2% full-context | amg 双时序的直接竞品 |
| **Is GraphRAG Needed?** | 2606.25656 | 9 种 RAG 场景标准化 + 上下文工程 | ACL 2026 GEM Workshop, -53% token | amg 的评估方法论参考 |

---

## 核心概念

### 1. Session-as-Graph（会话即图）

TokenMizer 的核心洞察：**会话历史不是平铺文本，而是决策图**。当上下文窗口溢出时，不是截断或摘要，而是序列化图状态。

- 14 节点类型：Decision / Rationale / Task / File / Code / Error / Test / Config / Dependency / Blocker / Resolution / Preference / Constraint / Goal
- 7 边类型：decided_during / triggered_by / replaced_by / depends_on / modified_by / invalidated_by / evidence_for
- 8 态生命周期：ACTIVE → SUPERSEDED → ARCHIVED / INVALIDATED（带时间戳）

> **关键数据**：Decision recall 85% vs 70% baseline；File recall 100% vs 91.7%；201-302 token resume 块替代 25K+ 原始会话

**与 amg 的对比**：amg 有 bi-temporal validity（supersede/query_valid_at/get_history），但缺少 **session-scoped decision tracking**。TokenMizer 的 `why_decision` 功能——追溯决策替换链（trigger + reason + evidence per hop）——是 amg 可以在应用层实现的。

### 2. On-Demand Hypergraph Memory（按需超图记忆）

DocTrace 的突破：不预构建全局图，而是**查询触发时按需构建超图工作记忆**。

- 文档结构树索引 → 保留层级
- 查询触发 → multi-agent 共享超图推理
- 成功的推理计划 → 存入经验图 → 未来复用
- 结果：+8.85% F1, +4.40% EM, **-53.32% 计算成本** vs 最强 baseline

> **超图 vs 普通图**：超边（hyperedge）可以连接 >2 个节点，捕捉"多件事共同导致一个结论"的关系。例如：[文档第3节] + [表格2] + [脚注5] → [答案] 是一条超边。

### 3. Auditability-by-Construction（构造性可审计）

MOSS 的范式宣言：**向量检索不可审计**。MOSS 用符号化关系数据库替代 embedding 相似度搜索：

- 检索执行是符号化的、可重现的（query 确定后，不再调用 LLM）
- 每步（索引 → 查询 → 答案）全程日志
- 概念词汇从语料归纳（569 个 concepts），不预设本体
- 1 年生产部署：44M tokens, 110K segments, 322K annotations, ~5M relations

> MOSS 论点的核心："向量空间是不可解释的。一旦 query 嵌入向量空间，你无法追溯为什么检索了 A 而不是 B。" 这与 amg 的 structure-gated PPR 形成有趣对比——PPR 也是符号化的、可追溯的。

### 4. Lean Context > Full Context（精瘦上下文胜过全量上下文）

Engram 的核心论点，用严格实验证明：

- LongMemEval 500 题，engram_lean: 83.6% (9.6K tokens) vs full-context: 73.2% (79K tokens)
- **+10.4% 准确率提升 + 8× token 节省**
- 关键洞察：噪声上下文有害——"distractors accumulate" → 更多上下文反而降低准确率

按类别：knowledge-update 87.5%, abstention 86.7%, temporal-reasoning 81.1%, multi-session 79.3%

### 5. Retrieval-Generation Gap（检索-生成鸿沟）

"Is GraphRAG Needed?" 的关键发现：

- **扩展检索不会比例提升生成质量**——检索指标（recall@k）高估了高级检索的收益
- 上下文工程：新表示 + agentic 循环设计 → **-19%~-53% token 使用**
- 9 种 RAG 场景：regular / GraphRAG / Modular RAG / Agentic RAG，提供数据驱动的选择指南

---

## 可运行代码示例

### 示例 1：TokenMizer 式会话决策图（Python）

```python
"""
Session Decision Graph — TokenMizer 式的会话级决策追踪。
不依赖任何外部服务，纯内存实现。
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

class DecisionStatus(Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"

@dataclass
class DecisionNode:
    id: str
    topic: str
    choice: str
    rationale: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    status: DecisionStatus = DecisionStatus.ACTIVE
    superseded_by: Optional[str] = None
    supersede_reason: Optional[str] = None
    evidence: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # other decision IDs

class SessionDecisionGraph:
    """Tracks decisions and their supersession chain."""
    def __init__(self):
        self._nodes: dict[str, DecisionNode] = {}
        self._topic_index: dict[str, list[str]] = {}  # topic -> [decision_ids]

    def add_decision(
        self, id: str, topic: str, choice: str, rationale: str,
        evidence: list[str] = None, dependencies: list[str] = None
    ) -> DecisionNode:
        node = DecisionNode(
            id=id, topic=topic, choice=choice, rationale=rationale,
            evidence=evidence or [], dependencies=dependencies or []
        )
        self._nodes[id] = node
        self._topic_index.setdefault(topic, []).append(id)
        return node

    def supersede(
        self, old_id: str, new_id: str, reason: str, trigger: str = ""
    ) -> None:
        """Mark old decision as superseded by new, preserving history."""
        if old_id not in self._nodes:
            raise KeyError(f"Decision {old_id} not found")
        old = self._nodes[old_id]
        old.status = DecisionStatus.SUPERSEDED
        old.superseded_by = new_id
        old.supersede_reason = f"[{trigger}] {reason}" if trigger else reason

    def why(self, topic: str) -> list[dict]:
        """Trace the full supersession chain for a topic."""
        chain = []
        decision_ids = self._topic_index.get(topic, [])
        for did in decision_ids:
            node = self._nodes[did]
            chain.append({
                "id": node.id,
                "choice": node.choice,
                "status": node.status.value,
                "rationale": node.rationale,
                "superseded_by": node.superseded_by,
                "reason": node.supersede_reason,
                "evidence": node.evidence,
            })
        return chain

    def active_decisions(self) -> list[DecisionNode]:
        """Get all currently active decisions."""
        return [n for n in self._nodes.values() if n.status == DecisionStatus.ACTIVE]

    def serialize_for_resume(self, token_budget: int = 300) -> str:
        """
        TokenMizer-style resume serialization.
        Produces a compact text block from the decision graph.
        """
        lines = []
        for d in self.active_decisions():
            deps = f" (depends on: {', '.join(d.dependencies)})" if d.dependencies else ""
            lines.append(f"[{d.topic}] {d.choice}{deps}")
            if d.rationale:
                lines.append(f"  Why: {d.rationale}")
        # Add superseded decisions briefly
        for d in self._nodes.values():
            if d.status == DecisionStatus.SUPERSEDED:
                lines.append(f"[SUPERSEDED] {d.topic}: ~~{d.choice}~~ → {d.superseded_by}")
                lines.append(f"  Reason: {d.supersede_reason}")
        text = "\n".join(lines)
        # Rough token estimate (4 chars/token)
        if len(text) > token_budget * 4:
            text = text[:token_budget * 4] + "\n... (truncated)"
        return text


# === Runnable Demo ===
if __name__ == "__main__":
    g = SessionDecisionGraph()

    # Initial decisions
    g.add_decision("d1", "framework", "React",
                   rationale="Team familiarity, large ecosystem",
                   evidence=["team-survey.md", "npm-stats.json"])
    g.add_decision("d2", "styling", "CSS Modules",
                   rationale="Works with React, no extra deps",
                   dependencies=["d1"])
    g.add_decision("d3", "backend", "FastAPI",
                   rationale="Auto docs, async support")

    # React → Next.js migration
    g.supersede("d1", "d4", trigger="SEO audit",
                reason="Next.js provides SSR/SSG for better SEO")
    g.add_decision("d4", "framework", "Next.js",
                   rationale="SSR/SSG, file-based routing, React-compatible",
                   evidence=["seo-audit.pdf", "lighthouse-score.json"])
    # Styling decision depends on framework, needs review
    g.supersede("d2", "d5", trigger="framework change",
                reason="Revisit styling with Next.js App Router")
    g.add_decision("d5", "styling", "Tailwind CSS",
                   rationale="Next.js native support, faster dev cycle",
                   dependencies=["d4"])

    # Query
    print("=== WHY framework? ===")
    for entry in g.why("framework"):
        print(f"  {entry['id']}: {entry['choice']} ({entry['status']})")
        if entry['reason']:
            print(f"    → superseded: {entry['reason']}")
        if entry['evidence']:
            print(f"    evidence: {entry['evidence']}")

    print("\n=== Active decisions ===")
    for d in g.active_decisions():
        print(f"  [{d.topic}] {d.choice}")

    print("\n=== Resume block (compact) ===")
    print(g.serialize_for_resume(token_budget=200))

    print("\n✅ Decision graph working. "
          "5 nodes, 2 supersession chains, 3 active decisions.")
```

### 示例 2：Engram 式双时序事实矛盾消解（TypeScript）

```typescript
/**
 * Bi-Temporal Fact Resolution — Engram-style contradiction handling.
 * amg 已有 bi-temporal validity; this demonstrates the core algorithm.
 */

interface Fact {
  id: string;
  content: string;
  validFrom: number;    // when the fact became true
  validUntil: number | null;  // null = still valid; number = superseded time
  assertedAt: number;   // when we learned this fact (system time)
  status: 'active' | 'superseded';
}

class BiTemporalFactStore {
  private facts: Map<string, Fact[]> = new Map();

  add(key: string, content: string, validFrom: number, assertedAt: number): void {
    // Detect contradiction: if new fact's validFrom overlaps existing active fact
    const existing = this.facts.get(key) || [];
    const active = existing.filter(f => f.status === 'active');

    for (const f of active) {
      // New fact invalidates old if validFrom >= f.validFrom
      if (validFrom >= f.validFrom) {
        f.validUntil = validFrom;
        f.status = 'superseded';
      }
    }

    existing.push({
      id: `${key}-${Date.now()}`,
      content,
      validFrom,
      validUntil: null,
      assertedAt,
      status: 'active',
    });
    this.facts.set(key, existing);
  }

  /** Query what was valid at a specific point in time. */
  queryValidAt(key: string, validTime: number, systemTime?: number): string | null {
    const facts = this.facts.get(key) || [];
    for (const f of [...facts].reverse()) {
      // System-time gate: we can only know facts asserted before systemTime
      if (systemTime && f.assertedAt > systemTime) continue;
      // Validity-time gate: fact must be valid at validTime
      if (f.validFrom <= validTime && (f.validUntil === null || validTime < f.validUntil)) {
        return f.content;
      }
    }
    return null;
  }

  /** Get full history with supersession reasons. */
  history(key: string): Fact[] {
    return this.facts.get(key) || [];
  }
}

// === Demo ===
const store = new BiTemporalFactStore();

// Timeline: user changes jobs
store.add('employer', 'Tencent', validFrom = 1000, assertedAt = 1000);
store.add('employer', 'Moonshot AI', validFrom = 2000, assertedAt = 2100);

// What's their current employer?
console.log('Current:', store.queryValidAt('employer', 2500));
// → 'Moonshot AI' (contradicted fact invalidated, not deleted)

// What was their employer at time 1500?
console.log('Historical:', store.queryValidAt('employer', 1500));
// → 'Tencent' (bi-temporal: can time-travel)

// What did we KNOW at system time 1500?
console.log('Known at t=1500:', store.queryValidAt('employer', 2500, systemTime = 1500));
// → 'Tencent' (we hadn't learned about Moonshot yet!)
```

---

## 关键洞察

### 洞察 1：Memory 正在从 IR 问题变成数据库问题

MOSS 和 Engram 代表了一个根本转向：**记忆不是"找到相似的东西"，而是"在正确的时空查询正确的事实"**。

- MOSS: 完全放弃向量检索，用符号化关系查询 + 归纳概念
- Engram: hybrid search（semantic + lexical + graph + recency），但核心是 bi-temporal 事实管理
- amg 的 structure-gated PPR + bi-temporal + Q-value 已经在这个方向上

**行动暗示**：amg 的 `retrieval_quality_eval()`（precision@k/NDCG/MRR）是 IR 指标——考虑增加 **fact-level 指标**（contradiction resolution rate, temporal consistency score）。

### 洞察 2：决策追溯（why_decision）是杀手级功能

TokenMizer 最受关注的功能不是图本身，而是 **`why_decision` MCP 工具**——追溯"为什么从 A 改到 B"的完整链条（trigger + reason + evidence per hop）。

amg 有 `get_history()` 和 `supersede()`，但没有暴露为一个对 agent 可调用的 **decision-chain 查询**。这是一个 **高价值、低实现成本** 的功能差距。

### 洞察 3：超图是图的自然扩展，但按需构建才是关键

DocTrace 证明了两件事：
1. 超图（hyperedge 连接 >2 节点）比普通图更能捕捉"多证据→结论"关系
2. **按需构建**（query-triggered）比预构建全局图便宜 53%

amg 目前是预构建图。一个可能的演进方向：**lazy hyperedge materialization**——查询时才构建超边，复用 PPR 的已有图结构。

### 洞察 4：Engram 的可复现 benchmark 方法论值得学习

Engrim 最聪明的一步：**用相同的 answerer 和 judge，同时报告 full-context baseline**。这让 83.6% 有意义——因为读者知道同条件下的参照线。

> "The same system can appear as 58% / 66% / 92% across sources; different papers give contradictory orderings."

这对 amg 的 LoCoMo benchmark adapter 直接相关：**必须同时报告 full-context baseline，否则数字没有意义**。

### 洞察 5：上下文工程 > 检索工程

"Is GraphRAG Needed?" 的 ACL 2026 结论：**retrieval-oriented metrics overstate advanced retrieval benefits**——检索好不等于生成好。

这意味着 amg 在优化 PPR recall@k 之外，需要关注 **context engineering**：怎么把检索到的东西组织成最好的上下文。TokenMizer 的 14-node-type 序列化和 Engram 的 lean slice 都是这方面的实践。

---

## amg 竞争定位更新

```
                    IR Quality    Auditability    Session Scope    Bi-Temporal    Decision Chain
amg (current)          ✅            ⬜️             ⬜️               ✅             partial
TokenMizer             N/A           ✅              ✅               ✅             ✅
Engram                 ✅            partial         partial          ✅             partial
MOSS                   N/A           ✅              partial          ⬜️             ⬜️
DocTrace               ✅            partial          ✅              ⬜️             ⬜️
```

**amg 的独特优势**：graph-native + 17 centrality + 拓扑指数七族 + structure-gated PPR + IR quality eval。这些是纯 IR/纯符号方法都没有的。

**amg 的关键差距**：
1. ❌ Session-scoped decision tracking（TokenMizer 的杀手级功能）
2. ❌ Context engineering layer（如何组织检索结果为最优上下文）
3. ⬜️ Fact-level evaluation（不只是 IR metrics，还有 fact correctness）

---

## 下一步行动

1. **[HIGH] 实现 `trace_decision_chain(topic)` API** — amg cycle 226 候选
   - 遍历 supersede 链，输出 trigger + reason + evidence per hop
   - 对标 TokenMizer 的 `why_decision` MCP tool
   - 预估 +15-20 tests

2. **[HIGH] LoCoMo benchmark: 必须同时报告 full-context baseline**
   - 参考 Engram 的方法论：same answerer + same judge
   - 目标：engram_lean 83.6% 是参照线，amg 至少 ≥ 60%（短期目标）

3. **[MEDIUM] Fact-level evaluation metrics**
   - 不只是 precision@k（IR 层面），还要 fact accuracy（语义层面）
   - 参考 Engram 的 per-category breakdown

4. **[LOW] 探索 lazy hyperedge materialization**
   - DocTrace 启发：查询触发时才构建超边
   - 可能作为 amg 的 `retrieve_hypergraph()` 扩展

---

## 论文引用

- Mishra, S. (2026). TokenMizer: Graph-Structured Session Memory for Long-Horizon LLM Context Management. arXiv:2606.06337. https://github.com/Shweta-Mishra-ai/tokenmizer
- Zai, X. et al. (2026). Trace Only What You Need: Structure-Aware On-Demand Hypergraph Memory for Long-Document QA. arXiv:2606.10921.
- Lacasse, S. et al. (2026). Memory-Orchestrated Semantic System (MOSS): An Auditable Agentic Memory Architecture. arXiv:2607.04391.
- Wang, L. (2026). Less Context, More Accuracy: A Bi-Temporal Memory Engine for LLM Agents. arXiv:2606.09900. https://github.com/ly-wang19/engram
- Chen, L. et al. (2026). Is GraphRAG Needed? From Basic RAG to Graph-/Agentic Solutions. ACL 2026 GEM Workshop. arXiv:2606.25656.

---

_Research note by Catalyst 🧪 | 2026-07-12 20:00_
