# Bi-Temporal Agent Memory: query_as_of(timestamp) 设计与实现

> **Research #057** | 2026-08-10 | Catalyst Deep Exploration
> **关联项目**: agent-memory-graph (Python), Issue #033
> **方法论**: autoresearch.md — 明确指标、快速循环、积累性

---

## 研究动机

agent-memory-graph 已有 `valid_from`/`valid_until` 的 valid-time 轴，支持 `edge_valid_at()` 和 `temporal_snapshot()`。但这是 **uni-temporal**——只知道"某事在真实世界什么时间成立"，无法回答 **"agent 在时间 T 时知道什么？"**（transaction-time 维度）。

这两个问题截然不同：
- **Valid time**: Alice 的合同是 2025-01 到 2025-06 → `valid_from/valid_until`
- **Transaction time**: 系统在 2025-03-15 才录入这条信息 → `recorded_at/expired_at`

**场景**: 3 月 10 日 agent 根据"不知道 Alice 有合同"做了决策；3 月 15 日补录了合同信息。回溯分析需要知道 **"3 月 10 日时 agent 知道什么"**，而非"3 月 10 日事实是什么"。

---

## 核心概念

### 1. 双时间轴 (Bi-Temporal Model)

每个事实（edge）携带 **两组时间戳**：

| 时间轴 | 字段 | 含义 | 来源 |
|--------|------|------|------|
| **Valid Time** (T) | `valid_at` / `invalid_at` | 事实在真实世界成立/失效的时间 | Snodgrass (1995), SQL:2011 |
| **Transaction Time** (T') | `recorded_at` / `expired_at` | 系统录入/撤回该事实的时间 | Zep (arXiv 2501.13956), Engram (arXiv 2606.09900) |

关键区分来自 Martin Fowler 的经典表述：
> "On Mar 25th, we thought Sally's salary on Feb 25th was $6500."

### 2. 非破坏性失效 (Non-Destructive Invalidation)

当新事实与旧事实矛盾时，**不删除旧事实**，而是：
- 旧事实: `invalid_at = now`, `expired_at = now`
- 新事实: `supersedes = old_fact_id`
- 保留完整审计链

这是 Engram 的核心设计决策，使 knowledge-update 类得分达到 87.5%。

### 3. As-Of 查询 (Point-in-Time Query)

两种 as-of 查询语义：

```
query_as_of(timestamp, mode="knowledge"):
  → "在时间 T 时，agent 认为什么是真的？"
  → 过滤: recorded_at <= T AND (expired_at IS NULL OR expired_at > T)
  → AND  (valid_at IS NULL OR valid_at <= T) AND (invalid_at IS NULL OR invalid_at > T)

query_as_of(timestamp, mode="truth"):
  → "在时间 T 时，什么客观上是 true 的？"
  → 过滤: valid_at <= T AND (invalid_at IS NULL OR invalid_at > T)
  → 不关心 agent 何时知道
```

### 4. 四象限分析 (Four Quadrants)

| | valid_at ≤ T | valid_at > T |
|---|---|---|
| **recorded_at ≤ T** | ① 已知且为真 | ② 已知但事实尚未生效（未来事实） |
| **recorded_at > T** | ③ 未感知但已发生 | ④ 双方都未发生 |

`query_as_of(T, "knowledge")` 只返回 ① 和 ②。

### 5. 超越链 (Supersedence Chain)

```
Fact A (recorded_at=Jan, valid_at=Jan, supersedes=None)
  ↓ contradicted
Fact B (recorded_at=Mar, valid_at=Mar, supersedes=A)
  → A.invalid_at = Mar, A.expired_at = Mar
  → 查询 "Feb 的 knowledge" → 返回 A
  → 查询 "Apr 的 knowledge" → 返回 B
```

---

## 代码示例：完整 Bi-Temporal 实现原型

以下代码可直接集成到 amg 的 `memory_graph.py`，基于现有 `edge_set_validity` 扩展：

```python
"""
Bi-Temporal Edge Manager for agent-memory-graph.

Extends the existing valid-time axis with a transaction-time axis,
enabling true "as-of" queries: "what did the agent know at time T?"

Design references:
  - Zep: arXiv 2501.13956 (bi-temporal KG for agent memory)
  - Engram: arXiv 2606.09900 (as-of filter in hybrid read path)
  - Martin Fowler: bitemporal-history pattern
  - SQL:2011 standard (system-time + valid-time)
"""

import time
import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BiTemporalFact:
    """A bi-temporal fact stored as an edge in the knowledge graph."""
    source: str
    target: str
    relation: str
    weight: float = 1.0

    # Valid time (T): when the fact is true in the world
    valid_at: float = field(default_factory=time.time)
    invalid_at: Optional[float] = None  # set when superseded

    # Transaction time (T'): when the agent learned/retracted this
    recorded_at: float = field(default_factory=time.time)
    expired_at: Optional[float] = None  # set when retracted/replaced

    # Provenance
    fact_id: Optional[str] = None
    supersedes: Optional[str] = None  # fact_id of the predecessor
    source_episode: Optional[str] = None  # origin message/session

    def is_valid_at(self, t: float) -> bool:
        """True if fact was valid in the world at time t."""
        return self.valid_at <= t and (self.invalid_at is None or self.invalid_at > t)

    def is_known_at(self, t: float) -> bool:
        """True if the agent had recorded this fact by time t."""
        return self.recorded_at <= t and (self.expired_at is None or self.expired_at > t)

    def is_active_at(self, t: float, mode: str = "knowledge") -> bool:
        """
        mode='knowledge': what the agent believed was true at t.
          Only checks transaction time (recorded_at/expired_at).
          The agent may have believed something FALSE — that's the point.
        mode='truth': what was objectively true at t.
          Only checks valid time (valid_at/invalid_at).
        mode='certain': what the agent knew AND was actually true.
          Checks both axes — the intersection.
        """
        if mode == "truth":
            return self.is_valid_at(t)
        if mode == "knowledge":
            return self.is_known_at(t)
        if mode == "certain":
            return self.is_known_at(t) and self.is_valid_at(t)
        raise ValueError(f"Unknown mode: {mode}")


class BiTemporalIndex:
    """
    In-memory bi-temporal index for fast as-of queries.

    Indexes facts by (source, relation, target) for O(1) lookup,
    with per-key sorted lists for efficient temporal filtering.

    Usage:
        idx = BiTemporalIndex()
        idx.add(BiTemporalFact("alice", "works_at", "acme"))
        idx.add(BiTemporalFact("alice", "works_at", "google",
                               supersedes="fact_001"))

        # What did the agent know at time T?
        results = idx.query_as_of(T, mode="knowledge")

        # What was true at time T (regardless of awareness)?
        results = idx.query_as_of(T, mode="truth")
    """

    def __init__(self):
        # key=(source, relation, target) -> list of BiTemporalFact sorted by recorded_at
        self._index: dict[tuple, list[BiTemporalFact]] = {}
        # Reverse lookup: fact_id -> BiTemporalFact
        self._by_id: dict[str, BiTemporalFact] = {}
        # Global timeline: all facts sorted by recorded_at (for snapshot queries)
        self._timeline: list[BiTemporalFact] = []

    def add(self, fact: BiTemporalFact) -> str:
        """Insert a fact. Auto-handles supersedence chain."""
        if fact.fact_id is None:
            fact.fact_id = f"f_{int(time.time() * 1000)}_{id(fact)}"

        key = (fact.source, fact.relation, fact.target)
        if key not in self._index:
            self._index[key] = []

        # If supersedes is set, invalidate the predecessor
        if fact.supersedes and fact.supersedes in self._by_id:
            old = self._by_id[fact.supersedes]
            old.invalid_at = fact.valid_at       # old fact became false at this valid time
            old.expired_at = fact.recorded_at    # agent retracted it when it recorded the new one

        self._index[key].append(fact)
        self._by_id[fact.fact_id] = fact
        self._timeline.append(fact)
        # Keep timeline sorted by recorded_at
        self._timeline.sort(key=lambda f: f.recorded_at)
        return fact.fact_id

    def query_as_of(self, timestamp: float, mode: str = "knowledge",
                    source: str = None, relation: str = None) -> list[BiTemporalFact]:
        """
        Point-in-time query: return facts active at `timestamp`.

        Args:
            timestamp: The query time (epoch seconds).
            mode: 'knowledge' = what agent believed was true
                  'truth'     = what was objectively true
            source, relation: Optional filters.

        Returns:
            List of BiTemporalFact objects active at the given time.

        Examples:
            # "What did the agent know on Aug 1st?"
            idx.query_as_of(1722500000, mode="knowledge")

            # "What was objectively true on Aug 1st?"
            idx.query_as_of(1722500000, mode="truth")

            # "What did the agent know about Alice on Aug 1st?"
            idx.query_as_of(1722500000, mode="knowledge", source="alice")
        """
        results = []
        for key, facts in self._index.items():
            # Apply optional source/relation filters
            if source and key[0] != source:
                continue
            if relation and key[1] != relation:
                continue
            for f in facts:
                if f.is_active_at(timestamp, mode):
                    results.append(f)
        return results

    def diff(self, t1: float, t2: float, mode: str = "knowledge") -> dict:
        """
        What changed between t1 and t2?

        Returns dict with 'added', 'removed', 'updated' fact lists.
        Useful for debugging agent decision drift.
        """
        at_t1 = {f.fact_id for f in self.query_as_of(t1, mode)}
        at_t2 = {f.fact_id for f in self.query_as_of(t2, mode)}

        added = [self._by_id[fid] for fid in at_t2 - at_t1]
        removed = [self._by_id[fid] for fid in at_t1 - at_t2]
        updated = []

        # Facts present at both times but with changed validity
        for fid in at_t1 & at_t2:
            f = self._by_id[fid]
            # Check if valid_at or invalid_at changed between snapshots
            f_at_t1 = f.is_valid_at(t1)
            f_at_t2 = f.is_valid_at(t2)
            if f_at_t1 != f_at_t2:
                updated.append(f)

        return {"added": added, "removed": removed, "updated": updated}

    def supersedence_chain(self, fact_id: str) -> list[str]:
        """Trace the full supersession chain: [oldest, ..., newest]."""
        chain = []
        current = self._by_id.get(fact_id)
        while current:
            chain.append(current.fact_id)
            current = self._by_id.get(current.supersedes) if current.supersedes else None
        return list(reversed(chain))


# ─── Runnable Demo ──────────────────────────────────────────────

if __name__ == "__main__":
    idx = BiTemporalIndex()

    T0 = 1700000000  # Jan 2023
    T1 = 1701000000  # ~Nov 2023
    T2 = 1702000000  # ~Dec 2023
    T3 = 1703000000  # ~Dec 2023

    # Episode 1: Agent learns Alice works at Acme (recorded T0, valid from T0)
    f1 = idx.add(BiTemporalFact(
        source="alice", relation="works_at", target="acme",
        valid_at=T0, recorded_at=T0, fact_id="f001"
    ))

    # Episode 2: Agent learns Alice moved to Google (recorded T2, valid from T1)
    # This supersedes f001
    f2 = idx.add(BiTemporalFact(
        source="alice", relation="works_at", target="google",
        valid_at=T1, recorded_at=T2, fact_id="f002", supersedes="f001"
    ))

    # ─── Queries ───

    print("=== Knowledge Query (what agent believed) ===")
    for t_label, t in [("T0", T0), ("T1+ε", T1 + 1), ("T2", T2), ("T3", T3)]:
        facts = idx.query_as_of(t, mode="knowledge")
        for f in facts:
            print(f"  {t_label}: {f.source} --{f.relation}--> {f.target}")

    print("\n=== Truth Query (what was objectively true) ===")
    for t_label, t in [("T0", T0), ("T1+ε", T1 + 1), ("T2", T2), ("T3", T3)]:
        facts = idx.query_as_of(t, mode="truth")
        for f in facts:
            print(f"  {t_label}: {f.source} --{f.relation}--> {f.target}")

    print("\n=== Diff between T0 and T3 ===")
    d = idx.diff(T0, T3)
    print(f"  Added: {[f.fact_id for f in d['added']]}")
    print(f"  Removed: {[f.fact_id for f in d['removed']]}")
    print(f"  Updated: {[f.fact_id for f in d['updated']]}")

    print("\n=== Supersedence chain for f002 ===")
    print(f"  {' → '.join(idx.supersedence_chain('f002'))}")

    # Expected output:
    # === Knowledge Query (what agent believed) ===
    #   T0: alice --works_at--> acme
    #   T1+ε: alice --works_at--> acme          # still only knows about Acme
    #   T2: alice --works_at--> google           # now knows about Google
    #   T3: alice --works_at--> google
    #
    # === Truth Query (what was objectively true) ===
    #   T0: alice --works_at--> acme
    #   T1+ε: alice --works_at--> google         # truth changed even though agent didn't know yet
    #   T2: alice --works_at--> google
    #   T3: alice --works_at--> google
    #
    # === Diff between T0 and T3 ===
    #   Added: ['f002']
    #   Removed: ['f001']
    #   Updated: []
    #
    # === Supersedence chain for f002 ===
    #   f001 → f002
```

运行方式：
```bash
python3 /tmp/bitemporal_demo.py
```

---

## 关键洞察

### 洞察 1: amg 当前是 "1.5-temporal"，升级到 bi-temporal 的成本极低

amg 已有 `valid_from`/`valid_until` + `edge_set_validity` + `edge_invalidate` + `temporal_snapshot`。这已经覆盖了 valid-time 轴。升级到 bi-temporal 只需要：
- 给 `_temporal` dict 加 `recorded_at` / `expired_at` 两个字段
- 新增 `query_as_of(timestamp, mode)` 方法
- 在 `edge_invalidate` 时设置 `expired_at`
- **预估工作量：~80 行代码 + ~30 行测试**

### 洞察 2: knowledge vs truth 的区分是 agent 决策可审计性的关键

Engram 论文 (arXiv 2606.09900) 的核心发现：bi-temporal 模型在 knowledge-update 类得分 87.5%、temporal-reasoning 类 81.1%，远超全量上下文 baseline（73.2%）。原因：**agent 决策需要基于"我当时知道什么"而非"事实是什么"**。

这对 amg 的 `recall()` 方法有直接影响——应该增加 `as_of` 参数，让 agent 能够回溯"为什么当时做了这个决策"。

### 洞察 3: 非破坏性失效 (non-destructive invalidation) 已在 amg 中实现

`edge_invalidate()` 已经做了正确的事——设置 `valid_until` 而非删除。但它缺少：
- `supersedes` 指针（谁替代了这个事实）
- `expired_at` 事务时间（何时撤回）
- `source_episode` 溯源（哪段对话产生了这个事实）

补全这三个字段让 amg 具备完整的 provenance chain。

### 洞察 4: Bi-temporal RDF 论文 (MDPI 2025) 提供了 SPARQL 扩展的理论基础

Tansel et al. (2025) 的 "Time Travel with the BiTemporal RDF Model" 提出了 BiTRDF 本体和时间感知查询的正式语义。虽然 amg 不用 RDF，但其 **time-slicing + rollback + bitemporal join** 的三种查询操作类型可以直接映射到 Python API 设计。

---

## amg 集成计划

### 新增 API（~5 个方法）

| 方法 | 签名 | 说明 |
|------|------|------|
| `edge_record` | `(source, target, relation, valid_at=None, source_episode=None)` | 录入事实，自动设置 `recorded_at` |
| `edge_supersede` | `(source, target, relation, new_fact, supersedes_fact_id)` | 非破坏性替代旧事实 |
| `query_as_of` | `(timestamp, mode="knowledge", source=None, relation=None)` | 核心 as-of 查询 |
| `knowledge_diff` | `(t1, t2)` | 两个时间点之间的知识变化 |
| `supersedence_chain` | `(fact_id)` | 完整替代链 |

### 实验记录

```
timestamp	commit	metric	value	status	description
2026-08-10T20:00	-	bi_temporal_apis	5	design	Research #057 design complete
```

### 成功标准

- [ ] `query_as_of(T, "knowledge")` 和 `query_as_of(T, "truth")` 返回不同结果
- [ ] 非破坏性失效：superseded 事实仍可查询
- [ ] 完整 supersedence chain 可追溯
- [ ] 现有 `temporal_snapshot` 保持向后兼容

---

## 参考资料

| # | 来源 | 关键贡献 |
|---|------|---------|
| 1 | Zep: arXiv 2501.13956 | Bi-temporal KG for agent memory, T/T' 双时间轴 |
| 2 | Engram: arXiv 2606.09900 | As-of filter in hybrid read path, 83.6% on LongMemEval |
| 3 | Martin Fowler: bitemporal-history | actual/record 术语，四象限分析 |
| 4 | SQL:2011 Standard | `FOR SYSTEM_TIME AS OF` 语法 |
| 5 | Tansel et al. 2025: Mathematics 13(13), 2109 | BiTRDF 本体，time-slicing/rollback/bitemporal join |
| 6 | Graphiti (getzep.com) | 开源 bi-temporal KG，20K+ stars，工业实践 |
| 7 | pg_bitemporal (PostgreSQL) | Asserted Versioning Framework 实现 |

---

_Generated by Catalyst Deep Exploration · 2026-08-10_
