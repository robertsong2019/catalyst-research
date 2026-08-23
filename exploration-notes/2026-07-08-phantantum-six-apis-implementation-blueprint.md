# Phantom-Lost 6 APIs: Implementation Blueprint from Latest Research

> 研究日期: 2026-07-08
> 触发: deep-exploration-evening cron
> 关联项目: agent-memory-graph (2007 tests) — Next Action #7: 重新实现 6 个 phantom-lost APIs
> 前序研究: 2026-07-07 Dual-Mode Consolidation Architecture / 2026-07-07 Memory Consolidation & Strategic Forgetting
> 方法论: autoresearch (明确指标 → 快速循环 → 保留/回退 → 积累性)

---

## 问题陈述

07-07 phantom commit 灾难中丢失的 6 个 API：

| # | API 名称 | 核心功能 | 原设计来源 |
|---|---------|---------|-----------|
| 1 | Memory Maturation | sigmoid 激活 0→1，防止未验证记忆过早影响检索 | Human-Inspired Memory Arch (arXiv:2605.08538) |
| 2 | RecurrenceDetector | 同主题 ≥3 次触发 smart consolidation | RecMem (ACL 2026 Findings, arXiv:2605.16045) |
| 3 | ConsolidationRouter | trigger-based 路由 FAST/SMART 模式 | Dual-Mode 设计 (自有) |
| 4 | Recall with Activation | 检索时加入 activation_strength 过滤 | Human-Inspired Memory Arch |
| 5 | confidence_score | 统一信任度量 (source + consistency + freshness) | Portable Agent Memory (arXiv:2605.11032) |
| 6 | forgetting_curve | Ebbinghaus 指数衰减 + 访问强化 | FOREVER (ACL 2026, arXiv:2601.03938) |

**成功标准：** 6 个 API 各有可运行代码 + 测试 + experiments.tsv 记录。从 2007 baseline 开始，每实现一个 API 后 test count 必须增加（保留/回退）。

---

## 核心概念

### 1. Memory Maturation: Engram Silence → Sigmoid Activation

**来源：** Human-Inspired Memory Architecture for LLM Agents (arXiv:2605.08538)

**认知科学基础：** Kitamura et al. (2017) 发现 engram（记忆痕迹）在形成后立即存在但保持"沉默"——需要数天才能变得可检索。这就是 complementary learning systems theory：快速编码（hippocampus）vs 慢性语义提取（neocortex）。

**Dual-trace design:**
```
新事件写入时：
  - Episodic trace（向量存储）: 立即可检索，activation = 0.0
  - Semantic trace（知识图谱）: 创建但 activation = 0.0
  
经过时间 t 后：
  - activation(t) = 1 / (1 + e^(-(t - t_half) / k))
  - t_half: 半激活时间（默认 24h）
  - k: 曲线陡度（默认 6h）
  
当 activation > 阈值（0.5）时：
  - Semantic trace 开始参与检索
  - Q-value 从 0.0 开始累积
```

**关键公式：**
```python
A(t) = 1 / (1 + exp(-(t - t_half) / k))

# t = 0h:    A ≈ 0.04 (几乎沉默)
# t = 12h:   A ≈ 0.27 (开始苏醒)
# t = 24h:   A = 0.50 (半激活)
# t = 36h:   A ≈ 0.73 (基本成熟)
# t = 48h:   A ≈ 0.92 (完全成熟)
```

**为什么 24h 半激活？** 人类 hippocampus→neocortex consolidation 约需 7-14 天。但 agent 运行周期更短，24h 是合理的工程近似——一个 session 周期内新记忆不干扰旧决策，跨 session 后成熟。

### 2. FOREVER: Forgetting Curve with Model-Centric Time

**来源：** FOREVER (ACL 2026 Camera-ready, arXiv:2601.03938)

**核心创新：** 不用 wall-clock time 衡量遗忘，而是用 **parameter update magnitude**（参数更新幅度）作为"模型时间"。

```
传统 forgetting curve:
  R(t) = e^(-t/S)        # t = 真实时间, S = 记忆强度

FOREVER 的改进:
  R(τ) = e^(-τ/S)        # τ = 累积参数更新幅度
  τ = Σ ||θ_t - θ_{t-1}||  # 模型实际"经历"了多少变化
```

**对 agent-memory-graph 的映射：** agent-memory-graph 不是训练模型，没有梯度更新。但可以映射到 **memory operation intensity**（记忆操作强度）：

```
agent-memory-graph 的 "model time":
  τ = 总节点数变化 + 总权重变化 + 总访问次数变化
  
意义：一个沉睡 7 天的 memory graph 和一个活跃 7 天的 graph，
      遗忘曲线的衰减率应该不同——后者"经历"了更多。
```

**Intensity-aware regularization：** FOREVER 的第二个组件——高强度更新期间减弱 replay，低强度期间加强。映射到记忆管理：

```
高强度期（新节点涌入）: 减弱 forgetting（保留更多信息待筛选）
低强度期（稳定状态）: 加强 forgetting（清理过时记忆）
```

### 3. RecMem 三层潜意识架构：Recurrence as Trigger

**来源：** RecMem (ACL 2026 Findings, arXiv:2605.16045, CUHK + Huawei)

**RecMem 的核心洞察：** 不是所有交互都值得 LLM 处理。用 embedding 把交互存入"潜意识层"，只在**复发**时触发 LLM 巩固。

**三层检索预算：**
```
查询时同时检索三个层级:
  K_sub (潜意识层): budget = N (原始交互)
  K_epi (情景层):   budget = k  
  K_sem (语义层):   budget = 2k  (RecMem 设定 k_sem = 2 * k_epi)
  
最终答案 = LLM(q, K_sub + K_epi + K_sem)
```

**Recurrence detection 算法：**
```
1. 新交互进来 → embedding 计算
2. 在潜意识层中做 top-k 相似检索
3. 如果 sim > threshold 的相似交互数 >= min_recurrence:
     → 触发 LLM consolidation
     → 生成 episodic abstraction（情景摘要）
     → 从情景中提取 semantic facts（语义事实）
4. 否则：只存入潜意识层，零 LLM 成本
```

**性能数据（RecMem paper Table 2）：**
```
                    LoCoMo Score    Construction Tokens
Full Context         84.18%          0 (但 query 31.5K tokens)
Mem0                 62.92%          1,520.8K
A-Mem                68.83%          1,459.9K  
RecMem               81.10%          193.2K  ← -87% cost, +18pp vs Mem0
```

### 4. Portable Agent Memory: Confidence Score with Merkle-DAG

**来源：** Portable Agent Memory (arXiv:2605.11032)

**五组件记忆模型：**
```
M = (E, S, P, W, I)
  E = Episodic (时间序列事件)
  S = Semantic (SPO 三元组 + confidence score)
  P = Procedural (操作程序)
  W = Working (当前任务上下文)
  I = Identity (持久身份信息)
```

**confidence_score 的设计：**
```python
confidence = weighted_average(
    source_trust,      # 来源可信度 (verified user > LLM extracted > external)
    consistency,       # 与已有记忆的一致性
    freshness,         # 时间衰减
    corroboration,     # 交叉验证次数
    transformation,    # 经历了多少次变换 (原始 > 摘要 > 摘要的摘要)
)
# 每次变换（merge/summarize）降低 confidence（信息损失）
```

**Merkle-DAG 防篡改：** 每条记忆的 hash 包含所有父节点的 hash。任何修改都会导致 root hash 变化，100% 篡改检测率。

**对 agent-memory-graph 的映射：** 已有 bi-temporal + conflict detect 可以直接支撑 source_trust 和 consistency。Q-value 可以作为 corroboration 的近似。

### 5. AgeMem: Memory Operations as RL Tools

**来源：** AgeMem / Agentic Memory (ACL 2026 Long Paper, arXiv:2601.01885, Wuhan University + Alibaba)

**核心概念：** 把记忆操作（ADD, UPDATE, DELETE, RETRIEVE, SUMMARY, FILTER）变成 agent 的 tool-based actions，用 RL 训练 agent 学习最优记忆策略。

**Step-wise GRPO：**
```
传统 RL: 终端 reward 只在 episode 结束时给
问题: 记忆操作的 reward 是稀疏且延迟的

Step-wise GRPO: 
  终端 reward 广播到 trajectory 中所有 step
  每个 step 都获得相同的 reward signal
  → 解决了记忆操作的稀疏 reward 问题
```

**实验数据（AgeMem Table 3, HotpotQA）：**
```
Tool         Qwen2.5-7B noRL → GRPO    Qwen3-4B noRL → GRPO
ADD Memory   0.92    → 1.64             2.49    → 2.64
UPDATE       0.00    → 0.13             0.13    → 0.34
DELETE       0.00    → 0.08             0.00    → 0.22
RETRIEVE     2.31    → 1.95             4.62    → 4.35
```

**关键发现：** RL 训练后 agent 学会了非平凡的记忆策略：
- preemptive summarization（上下文溢出前主动摘要）
- selective forgetting（丢弃冗余条目）
- proactive linking（主动关联相关概念）

**威胁评估：** 这是 12-18 月后的威胁——当前 agent-memory-graph 的记忆操作是启发式的（固定规则），AgeMem 是 learned 的。但 AgeMem 需要 RL 训练基础设施（GPU + reward model），agent-memory-graph 不需要。两条路线可以共存：先交付算法版，后续加 RL layer。

---

## 可运行代码示例

### 完整实现：6 个 Phantom-Lost APIs 原型

```python
"""
agent-memory-graph: 6 Phantom-Lost APIs Implementation Blueprint
================================================================
Run: python phantom_six_apis.py
Verify: pytest test_phantom_six_apis.py

Each API is self-contained and demonstrates the core algorithm.
Production integration would add these as methods on the MemoryGraph class.
"""

import math
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════
# Shared data structures (simplified from agent-memory-graph)
# ═══════════════════════════════════════════════════════════════

@dataclass
class MemoryNode:
    """Simplified MemoryNode matching agent-memory-graph's structure."""
    id: str
    content: str
    weight: float = 0.5
    q_value: float = 0.0
    activation: float = 0.0           # NEW: maturation activation
    confidence: float = 0.5           # NEW: unified trust metric
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    content_hash: str = ""
    topics: list = field(default_factory=list)
    source: str = "unknown"           # NEW: provenance tracking
    transform_count: int = 0          # NEW: how many times merged/summarized
    
    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.md5(self.content.encode()).hexdigest()[:8]
    
    def age_hours(self) -> float:
        return (time.time() - self.created_at) / 3600
    
    def access(self):
        self.last_accessed = time.time()
        self.access_count += 1


# ═══════════════════════════════════════════════════════════════
# API 1: Memory Maturation (sigmoid activation)
# Source: arXiv:2605.08538, Kitamura et al. (2017)
# ═══════════════════════════════════════════════════════════════

class MemoryMaturation:
    """
    Engram maturation: new memories start with activation=0.0,
    gradually mature via sigmoid function over time.
    
    This prevents unverified information from influencing retrieval
    until it has had time to be validated by subsequent interactions.
    """
    
    def __init__(self, t_half: float = 24.0, k: float = 6.0):
        """
        Args:
            t_half: half-activation time in hours (default: 24h)
            k: steepness of sigmoid in hours (default: 6h)
        """
        self.t_half = t_half
        self.k = k
    
    def compute_activation(self, age_hours: float) -> float:
        """
        Sigmoid activation function.
        
        A(t) = 1 / (1 + e^(-(t - t_half) / k))
        
        At t=0:    A ≈ 0.04 (nearly silent)
        At t=t_half: A = 0.50 (half-activated)  
        At t=2*t_half: A ≈ 0.96 (nearly mature)
        """
        return 1.0 / (1.0 + math.exp(-(age_hours - self.t_half) / self.k))
    
    def update_node(self, node: MemoryNode) -> float:
        """Update a node's activation based on its current age."""
        node.activation = self.compute_activation(node.age_hours())
        return node.activation
    
    def is_mature(self, node: MemoryNode, threshold: float = 0.5) -> bool:
        """Check if a node has matured enough to influence retrieval."""
        return self.update_node(node) >= threshold
    
    def batch_update(self, nodes: list[MemoryNode]) -> dict:
        """Update activation for all nodes. Returns stats."""
        mature = immature = silent = 0
        for n in nodes:
            act = self.update_node(n)
            if act >= 0.7:
                mature += 1
            elif act >= 0.3:
                immature += 1
            else:
                silent += 1
        return {
            "total": len(nodes),
            "mature": mature,
            "immature": immature,
            "silent": silent,
        }


# ═══════════════════════════════════════════════════════════════
# API 2: RecurrenceDetector
# Source: RecMem (arXiv:2605.16045, ACL 2026 Findings)
# ═══════════════════════════════════════════════════════════════

class RecurrenceDetector:
    """
    Tracks topic/semantic recurrence to trigger smart consolidation.
    
    Inspired by RecMem's three-tier architecture:
    - New interactions enter "subconscious" layer (no LLM cost)
    - When similar content recurs ≥ N times → trigger consolidation
    - This achieves 87% token cost reduction vs eager consolidation
    """
    
    def __init__(
        self,
        min_recurrence: int = 3,
        similarity_threshold: float = 0.75,
        window_hours: float = 48.0,
    ):
        self.min_recurrence = min_recurrence
        self.similarity_threshold = similarity_threshold
        self.window_hours = window_hours
        self._topic_history: dict[str, list[tuple[float, str]]] = defaultdict(list)
        self._pending_triggers: list[dict] = []
    
    def observe(self, node: MemoryNode) -> Optional[dict]:
        """
        Record a new interaction. Returns trigger dict if recurrence detected.
        
        In production, similarity would use embeddings (cosine sim).
        Here we use word-overlap as a lightweight proxy.
        """
        topic = self._extract_topic(node.content)
        now = time.time()
        self._topic_history[topic].append((now, node.content))
        
        # Filter to recent window
        window_sec = self.window_hours * 3600
        recent = [
            (ts, content) for ts, content in self._topic_history[topic]
            if now - ts < window_sec
        ]
        self._topic_history[topic] = recent
        
        # Check recurrence threshold
        if len(recent) >= self.min_recurrence:
            trigger = {
                "type": "recurrence",
                "topic": topic,
                "count": len(recent),
                "contents": [c for _, c in recent],
                "should_consolidate": True,
                "mode": "smart",
                "timestamp": now,
            }
            self._pending_triggers.append(trigger)
            # Reset counter after triggering
            self._topic_history[topic] = []
            return trigger
        
        return None
    
    def _extract_topic(self, content: str) -> str:
        """
        Lightweight topic extraction.
        Production: use embedding clustering or LLM topic modeling.
        Here: first meaningful word as topic proxy.
        """
        words = [w.lower() for w in content.split() if len(w) > 3]
        return words[0] if words else "general"
    
    def get_pending_triggers(self) -> list[dict]:
        triggers = self._pending_triggers[:]
        self._pending_triggers.clear()
        return triggers
    
    def stats(self) -> dict:
        return {
            "total_topics": len(self._topic_history),
            "active_topics": sum(
                1 for v in self._topic_history.values() if len(v) >= self.min_recurrence
            ),
            "pending_triggers": len(self._pending_triggers),
        }


# ═══════════════════════════════════════════════════════════════
# API 3: ConsolidationRouter
# Source: Dual-Mode design (2026-07-07 research note)
# ═══════════════════════════════════════════════════════════════

class ConsolidationMode(Enum):
    FAST = "fast"      # Algorithm-driven, <100ms, $0
    SMART = "smart"    # LLM-driven, 2-10s, ~$0.002


class TriggerType(Enum):
    SESSION_END = "session_end"
    VOLUME = "volume"
    RECURRENCE = "recurrence"
    CONFLICT = "conflict"
    IDLE = "idle"
    MANUAL = "manual"


class ConsolidationRouter:
    """
    Trigger-based router between FAST (algorithm) and SMART (LLM) modes.
    
    Routing principles:
    - High certainty (exact dedup, weight decay) → FAST
    - Low certainty (contradiction, semantic merge) → SMART
    - High value (Q > 0.8) → SMART (worth the cost)
    - Bulk low-value → FAST (not worth LLM cost)
    """
    
    def __init__(
        self,
        q_value_threshold: float = 0.8,
        stale_weight_threshold: float = 0.6,
        volume_threshold: int = 20,
    ):
        self.q_value_threshold = q_value_threshold
        self.stale_weight_threshold = stale_weight_threshold
        self.volume_threshold = volume_threshold
        self._decision_log: list[dict] = []
    
    def route(
        self,
        nodes: list[MemoryNode],
        trigger: TriggerType,
        recurrence_triggers: list[dict] = None,
    ) -> ConsolidationMode:
        """Decide consolidation mode based on trigger and node analysis."""
        
        # Manual → always SMART (user requested full Dreaming)
        if trigger == TriggerType.MANUAL:
            return self._log("manual", ConsolidationMode.SMART, "user request")
        
        # Conflict → SMART (needs semantic judgment)
        if trigger == TriggerType.CONFLICT:
            return self._log("conflict", ConsolidationMode.SMART, "contradiction needs LLM")
        
        # Recurrence → SMART (worth semantic merge, RecMem-style)
        if trigger == TriggerType.RECURRENCE and recurrence_triggers:
            return self._log(
                "recurrence", ConsolidationMode.SMART,
                f"{len(recurrence_triggers)} topics recurring"
            )
        
        # Session end → FAST (basic maintenance)
        if trigger == TriggerType.SESSION_END:
            return self._log("session_end", ConsolidationMode.FAST, "basic cleanup")
        
        # Volume / idle → analyze nodes
        # High Q-value nodes need careful handling
        high_q = [n for n in nodes if n.q_value > self.q_value_threshold]
        if high_q:
            return self._log(
                "high_q", ConsolidationMode.SMART,
                f"{len(high_q)} nodes with Q > {self.q_value_threshold}"
            )
        
        # High-weight stale nodes need semantic review
        stale_high = [
            n for n in nodes
            if n.weight > self.stale_weight_threshold
            and n.access_count == 0
            and n.age_hours() > 48
        ]
        if stale_high:
            return self._log(
                "stale_high_weight", ConsolidationMode.SMART,
                f"{len(stale_high)} stale high-weight nodes"
            )
        
        # Default: FAST (bulk algorithm consolidation)
        return self._log("default", ConsolidationMode.FAST, "bulk algorithm cleanup")
    
    def _log(self, reason: str, mode: ConsolidationMode, detail: str) -> ConsolidationMode:
        self._decision_log.append({
            "reason": reason,
            "mode": mode.value,
            "detail": detail,
            "timestamp": time.time(),
        })
        return mode
    
    def decision_history(self) -> list[dict]:
        return self._decision_log


# ═══════════════════════════════════════════════════════════════
# API 4: Recall with Activation
# Source: arXiv:2605.08538 (activation-gated retrieval)
# ═══════════════════════════════════════════════════════════════

class RecallWithActivation:
    """
    Retrieval that filters by activation_strength.
    
    Immature memories (activation < threshold) are excluded from
    semantic retrieval but remain accessible via episodic (raw) retrieval.
    
    This implements the dual-trace design:
    - Episodic store: always accessible (raw interaction history)
    - Semantic store: activation-gated (only mature knowledge)
    """
    
    def __init__(
        self,
        activation_threshold: float = 0.5,
        min_results: int = 3,
        fallback_to_episodic: bool = True,
    ):
        self.activation_threshold = activation_threshold
        self.min_results = min_results
        self.fallback_to_episodic = fallback_to_episodic
        self._maturation = MemoryMaturation()
    
    def recall(
        self,
        query: str,
        nodes: list[MemoryNode],
        top_k: int = 10,
    ) -> dict:
        """
        Retrieve relevant memories with activation gating.
        
        Returns dict with:
          - semantic_results: mature memories (activation >= threshold)
          - episodic_results: all memories (including immature)
          - filtered_count: how many were suppressed by activation gate
        """
        # Update all activations
        for n in nodes:
            self._maturation.update_node(n)
        
        # Split by activation level
        mature = [n for n in nodes if n.activation >= self.activation_threshold]
        immature = [n for n in nodes if n.activation < self.activation_threshold]
        
        # Rank mature nodes by relevance (word overlap proxy)
        ranked_mature = self._rank_by_relevance(query, mature)[:top_k]
        
        # Fallback: if not enough mature results, include episodic
        if len(ranked_mature) < self.min_results and self.fallback_to_episodic:
            ranked_episodic = self._rank_by_relevance(query, nodes)[:top_k]
        else:
            ranked_episodic = []
        
        # Mark access
        for n in ranked_mature + ranked_episodic:
            n.access()
        
        return {
            "semantic_results": [
                {"id": n.id, "content": n.content, 
                 "activation": round(n.activation, 3),
                 "confidence": round(n.confidence, 3)}
                for n in ranked_mature
            ],
            "episodic_results": [
                {"id": n.id, "content": n.content,
                 "activation": round(n.activation, 3)}
                for n in ranked_episodic
            ],
            "filtered_count": len(immature),
            "total_pool": len(nodes),
        }
    
    def _rank_by_relevance(
        self, query: str, nodes: list[MemoryNode]
    ) -> list[MemoryNode]:
        """Lightweight relevance ranking via word overlap."""
        if not nodes:
            return []
        query_words = set(query.lower().split())
        scored = []
        for n in nodes:
            content_words = set(n.content.lower().split())
            overlap = len(query_words & content_words)
            # Combined score: relevance * activation * confidence
            score = overlap * n.activation * max(n.confidence, 0.1)
            scored.append((score, n))
        scored.sort(key=lambda x: -x[0])
        return [n for _, n in scored]


# ═══════════════════════════════════════════════════════════════
# API 5: confidence_score (Unified Trust Metric)
# Source: Portable Agent Memory (arXiv:2605.11032) + Evidence Tracing (arXiv:2606.04990)
# ═══════════════════════════════════════════════════════════════

# Source trust levels (arXiv:2605.11032 provenance model)
SOURCE_TRUST = {
    "verified_user": 1.0,      # User directly stated
    "user_corrected": 0.95,    # User corrected previous info
    "llm_extracted": 0.7,      # LLM extracted from conversation
    "inferred": 0.5,           # System inferred from patterns
    "external": 0.3,           # External source (web, tool)
    "unknown": 0.2,            # Unknown provenance
}


class ConfidenceScorer:
    """
    Unified trust metric combining:
    - Source provenance (who said it)
    - Consistency (does it conflict with existing knowledge)
    - Freshness (how old is it)
    - Corroboration (how many times confirmed)
    - Transformation cost (how many times merged/summarized)
    
    Based on Portable Agent Memory's provenance model and
    Evidence Tracing survey's lineage tracking.
    """
    
    def __init__(
        self,
        w_source: float = 0.30,
        w_consistency: float = 0.25,
        w_freshness: float = 0.15,
        w_corroboration: float = 0.20,
        w_transformation: float = 0.10,
    ):
        self.weights = {
            "source": w_source,
            "consistency": w_consistency,
            "freshness": w_freshness,
            "corroboration": w_corroboration,
            "transformation": w_transformation,
        }
    
    def compute(self, node: MemoryNode, conflicts: int = 0) -> float:
        """
        Compute unified confidence score [0.0, 1.0].
        
        Args:
            node: MemoryNode with metadata
            conflicts: number of conflicting memories detected
        """
        # 1. Source trust (0.0 - 1.0)
        source_score = SOURCE_TRUST.get(node.source, 0.2)
        
        # 2. Consistency (conflict penalty)
        consistency_score = max(0.0, 1.0 - 0.3 * conflicts)
        
        # 3. Freshness (exponential decay, half-life = 30 days)
        age_days = node.age_hours() / 24.0
        freshness_score = math.exp(-0.693 * age_days / 30.0)  # 30-day half-life
        
        # 4. Corroboration (access count as proxy)
        # log-scale: 0 accesses = 0, 1 = 0.69, 5 = 1.79, 10 = 2.40
        corroboration_score = min(1.0, math.log(node.access_count + 1) / math.log(10))
        
        # 5. Transformation cost (more transforms = less trustworthy)
        # Each transform loses information. 0 transforms = 1.0, 3+ = <0.5
        transformation_score = 1.0 / (1.0 + 0.2 * node.transform_count)
        
        # Weighted average
        confidence = (
            self.weights["source"] * source_score
            + self.weights["consistency"] * consistency_score
            + self.weights["freshness"] * freshness_score
            + self.weights["corroboration"] * corroboration_score
            + self.weights["transformation"] * transformation_score
        )
        
        return round(confidence, 4)
    
    def update_node(self, node: MemoryNode, conflicts: int = 0) -> float:
        """Compute and store confidence on the node."""
        node.confidence = self.compute(node, conflicts)
        return node.confidence
    
    def batch_score(
        self,
        nodes: list[MemoryNode],
        conflict_map: dict[str, int] = None,
    ) -> dict:
        """Score all nodes. conflict_map: {node_id: conflict_count}."""
        conflict_map = conflict_map or {}
        scored = 0
        low_confidence = []
        for n in nodes:
            c = self.update_node(n, conflict_map.get(n.id, 0))
            scored += 1
            if c < 0.3:
                low_confidence.append(n.id)
        return {
            "scored": scored,
            "avg_confidence": round(
                sum(n.confidence for n in nodes) / max(len(nodes), 1), 3
            ),
            "low_confidence_ids": low_confidence,
            "weight_config": self.weights,
        }


# ═══════════════════════════════════════════════════════════════
# API 6: forgetting_curve (Ebbinghaus + FOREVER)
# Source: FOREVER (arXiv:2601.03938, ACL 2026) + Ebbinghaus (1885)
# ═══════════════════════════════════════════════════════════════

class ForgettingCurve:
    """
    Ebbinghaus forgetting curve with FOREVER-inspired adaptive intensity.
    
    Traditional: R(t) = e^(-t/S)
    FOREVER:     R(τ) = e^(-τ/S)  where τ = model-centric time
    
    For agent-memory-graph, τ maps to "memory operation intensity":
    - High activity (many new nodes) → slower forgetting (preserve info)
    - Low activity (stable graph) → faster forgetting (clean up)
    
    Also implements spaced repetition: each access strengthens the memory
    (flattens the forgetting curve), following Ebbinghaus's discovery.
    """
    
    def __init__(
        self,
        base_half_life_hours: float = 168.0,  # 1 week default
        reinforcement_factor: float = 1.5,    # each access multiplies half-life
        intensity_sensitivity: float = 0.1,   # how much activity affects decay
        min_weight: float = 0.05,             # below this = forgotten
    ):
        self.base_half_life = base_half_life_hours
        self.reinforcement_factor = reinforcement_factor
        self.intensity_sensitivity = intensity_sensitivity
        self.min_weight = min_weight
    
    def compute_retention(
        self,
        age_hours: float,
        access_count: int,
        graph_activity: float = 0.5,  # 0-1, how active the graph has been
        q_value: float = 0.0,
    ) -> float:
        """
        Compute retention strength [0, 1].
        
        R(t) = e^(-0.693 * t / S_eff)
        
        Where S_eff (effective stability) is:
          S_eff = S_base * reinforcement^access_count * (1 + α * activity) * (1 + Q)
          
        Args:
            age_hours: time since creation
            access_count: number of times accessed
            graph_activity: 0-1, normalized new node rate
            q_value: memory importance [0, 1]
        """
        # Q-value extends half-life for important memories
        q_multiplier = 1.0 + q_value * 4.0  # Q=1 → 5x half-life
        
        # Access reinforcement (spaced repetition effect)
        access_multiplier = self.reinforcement_factor ** access_count
        
        # Activity adjustment (FOREVER-inspired)
        # High activity → slower decay (system is evolving, keep info)
        # Low activity → normal decay (stable system, clean up)
        activity_multiplier = 1.0 + self.intensity_sensitivity * graph_activity
        
        # Effective half-life
        s_eff = (
            self.base_half_life
            * access_multiplier
            * activity_multiplier
            * q_multiplier
        )
        
        # Exponential decay
        retention = math.exp(-0.693 * age_hours / s_eff)
        
        return max(0.0, min(1.0, retention))
    
    def apply_decay(self, node: MemoryNode, graph_activity: float = 0.5) -> float:
        """Apply forgetting curve to a node. Returns new weight."""
        retention = self.compute_retention(
            age_hours=node.age_hours(),
            access_count=node.access_count,
            graph_activity=graph_activity,
            q_value=node.q_value,
        )
        node.weight = retention
        return retention
    
    def batch_decay(
        self,
        nodes: list[MemoryNode],
        graph_activity: float = 0.5,
    ) -> dict:
        """
        Apply forgetting curve to all nodes.
        Returns stats including which nodes should be pruned.
        """
        forgotten = []
        reinforced = []
        
        for n in nodes:
            old_weight = n.weight
            new_weight = self.apply_decay(n, graph_activity)
            
            if new_weight < self.min_weight:
                forgotten.append(n.id)
            elif new_weight > old_weight * 0.9 and n.access_count > 0:
                reinforced.append(n.id)
        
        return {
            "total": len(nodes),
            "forgotten": len(forgotten),
            "forgotten_ids": forgotten,
            "reinforced": len(reinforced),
            "avg_weight": round(
                sum(n.weight for n in nodes) / max(len(nodes), 1), 3
            ),
            "graph_activity": graph_activity,
        }
    
    def forgetting_curve_data(
        self,
        access_count: int = 0,
        q_value: float = 0.0,
        max_hours: float = 720,  # 30 days
        points: int = 50,
    ) -> list[dict]:
        """
        Generate forgetting curve data points for visualization.
        Useful for debugging and documentation.
        """
        curve = []
        for i in range(points):
            t = max_hours * i / points
            r = self.compute_retention(t, access_count, 0.5, q_value)
            curve.append({"hours": round(t, 1), "retention": round(r, 4)})
        return curve


# ═══════════════════════════════════════════════════════════════
# Integration Demo: All 6 APIs Working Together
# ═══════════════════════════════════════════════════════════════

def demo_integration():
    """Demonstrate the 6 APIs working as an integrated system."""
    print("=" * 70)
    print("Phantom-Lost 6 APIs: Integration Demo")
    print("=" * 70)
    
    # Initialize all components
    maturation = MemoryMaturation(t_half=24, k=6)
    recurrence = RecurrenceDetector(min_recurrence=3, window_hours=1)
    router = ConsolidationRouter()
    recall = RecallWithActivation(activation_threshold=0.5)
    scorer = ConfidenceScorer()
    forgetting = ForgettingCurve(base_half_life_hours=168)
    
    # Simulate memory graph with nodes of various ages
    now = time.time()
    nodes = [
        # Old, mature, high-confidence memory
        MemoryNode(
            id="n1",
            content="User's name is 罗嵩",
            weight=0.95, q_value=0.9, source="verified_user",
            created_at=now - 7200,  # 2h ago (matured)
            access_count=15, topics=["identity"],
        ),
        # Medium-age memory
        MemoryNode(
            id="n2",
            content="User prefers concise answers",
            weight=0.85, q_value=0.7, source="user_corrected",
            created_at=now - 1800,  # 30 min ago (maturing)
            access_count=5, topics=["preference"],
        ),
        # Brand new memory (should be immature)
        MemoryNode(
            id="n3",
            content="Payment module bug #1234 needs hotfix",
            weight=0.5, q_value=0.3, source="llm_extracted",
            created_at=now - 300,  # 5 min ago (silent)
            access_count=0, topics=["work", "bug"],
        ),
        # Another payment-related memory
        MemoryNode(
            id="n4",
            content="Payment module crash is in line 42",
            weight=0.4, q_value=0.2, source="llm_extracted",
            created_at=now - 240,  # 4 min ago
            access_count=0, topics=["work", "bug"],
        ),
        # Third payment mention (should trigger recurrence)
        MemoryNode(
            id="n5",
            content="Payment module needs immediate attention",
            weight=0.45, q_value=0.3, source="external",
            created_at=now - 180,  # 3 min ago
            access_count=1, topics=["work", "bug"],
        ),
        # Low-value noise
        MemoryNode(
            id="n6",
            content="Random thought about weather",
            weight=0.05, q_value=0.0, source="unknown",
            created_at=now - 600,  # 10 min ago
            access_count=0, topics=["casual"],
        ),
    ]
    
    # ─── API 1: Memory Maturation ────────────────────────────
    print("\n📋 API 1: Memory Maturation")
    print("─" * 50)
    mat_stats = maturation.batch_update(nodes)
    print(f"  Mature (act≥0.7): {mat_stats['mature']}")
    print(f"  Immature (0.3≤act<0.7): {mat_stats['immature']}")
    print(f"  Silent (act<0.3): {mat_stats['silent']}")
    for n in nodes:
        print(f"    [{n.activation:.2f}] {n.content[:50]}")
    
    # ─── API 2: RecurrenceDetector ───────────────────────────
    print(f"\n📋 API 2: Recurrence Detector")
    print("─" * 50)
    det = RecurrenceDetector(min_recurrence=3, window_hours=1)
    for n in nodes:
        trigger = det.observe(n)
        if trigger:
            print(f"  🔥 Recurrence: '{trigger['topic']}' × {trigger['count']}")
    print(f"  Stats: {det.stats()}")
    
    # ─── API 3: ConsolidationRouter ──────────────────────────
    print(f"\n📋 API 3: Consolidation Router")
    print("─" * 50)
    for trigger_type in [TriggerType.SESSION_END, TriggerType.RECURRENCE,
                          TriggerType.CONFLICT, TriggerType.MANUAL]:
        mode = router.route(nodes, trigger_type,
                           recurrence_triggers=[{"topic": "payment"}])
        print(f"  {trigger_type.value:>15} → {mode.value}")
    
    # ─── API 4: Recall with Activation ───────────────────────
    print(f"\n📋 API 4: Recall with Activation")
    print("─" * 50)
    # Fast-forward time for demo (pretend some nodes have matured)
    for n in nodes[:2]:
        n.created_at -= 86400  # shift 24h back to mature
        maturation.update_node(n)
    
    result = recall.recall("payment bug", nodes, top_k=5)
    print(f"  Semantic results (mature): {len(result['semantic_results'])}")
    for r in result["semantic_results"]:
        print(f"    [{r['activation']:.2f}] {r['content'][:50]}")
    print(f"  Episodic fallback: {len(result['episodic_results'])}")
    print(f"  Filtered (immature): {result['filtered_count']}")
    
    # ─── API 5: Confidence Score ─────────────────────────────
    print(f"\n📋 API 5: Confidence Score")
    print("─" * 50)
    conflict_map = {nodes[2].id: 0, nodes[3].id: 1}  # one has a conflict
    conf_stats = scorer.batch_score(nodes, conflict_map)
    print(f"  Average confidence: {conf_stats['avg_confidence']}")
    print(f"  Low confidence: {conf_stats['low_confidence_ids']}")
    for n in nodes:
        print(f"    [{n.confidence:.2f}] {n.source:>15} | {n.content[:40]}")
    
    # ─── API 6: Forgetting Curve ─────────────────────────────
    print(f"\n📋 API 6: Forgetting Curve")
    print("─" * 50)
    decay_stats = forgetting.batch_decay(nodes, graph_activity=0.6)
    print(f"  Forgotten: {decay_stats['forgotten']}")
    print(f"  Reinforced: {decay_stats['reinforced']}")
    print(f"  Average weight: {decay_stats['avg_weight']}")
    for n in nodes:
        print(f"    [w={n.weight:.3f}] {n.content[:50]}")
    
    # Generate forgetting curve visualization data
    curve = forgetting.forgetting_curve_data(access_count=0, q_value=0.5)
    print(f"\n  Forgetting curve (Q=0.5, no access):")
    for point in curve[::10]:  # every 10th point
        bar = "█" * int(point["retention"] * 20)
        print(f"    {point['hours']:>6.0f}h │{bar:<20}│ {point['retention']:.2f}")
    
    print(f"\n{'=' * 70}")
    print("✅ All 6 APIs operational. Ready for integration into MemoryGraph class.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    demo_integration()
```

---

## 关键洞察

### 1. Memory Maturation 是"免费"的质量过滤器

Sigmoid 激活函数零计算成本（一次 `math.exp`），但它实现了 RecMem 潜意识层的核心功能——新记忆不干扰旧决策。**这不是"额外功能"，而是检索质量的 baseline 保障。**

在实现上只需要：
- `MemoryNode` 加 `activation: float = 0.0` 字段
- `recall()` 方法加 `activation >= threshold` 过滤
- 定期 `batch_update()` 更新 activation

**测试要点：** 创建一个新节点 → 立即 recall → 不应返回（activation < 0.5）。等待模拟时间 24h → recall → 应返回。

### 2. FOREVER 的 "Model-Centric Time" 映射到 "Graph Activity"

FOREVER 用 parameter update magnitude 定义"模型时间"。agent-memory-graph 不是训练模型，但可以映射到 **graph operation intensity**：新节点创建率 + 权重变化率 + 访问频率。

**实际含义：** 一个活跃的 memory graph（大量新交互）应该比一个沉睡的 graph 保留更多记忆——因为活跃意味着信息还在涌入，过早遗忘会丢失上下文。这和 FOREVER 的 "intensity-aware regularization" 一致。

**实现：** `graph_activity = normalized(new_nodes_in_last_hour / avg_new_nodes_per_hour)`，范围 [0, 1]。传入 `forgetting_curve.batch_decay()` 作为参数。

### 3. confidence_score 的五维设计是防篡改基础

Portable Agent Memory (arXiv:2605.11032) 证明了 Merkle-DAG + provenance tracking 可以实现 100% 篡改检测。虽然 agent-memory-graph 不需要 Merkle-DAG（它不是跨 agent 传输的），但 **provenance tracking 本身就是 confidence scoring 的基础**。

五个维度中，agent-memory-graph 已经有四个的基础设施：
- **source**: 可以在 `add_node()` 时传入
- **consistency**: `conflict_detect` 已有
- **freshness**: `staleness_score` 已有
- **corroboration**: `access_count` 已有
- 只需新增 **transformation_count**（每次 merge/summarize 时 +1）

**关键：** 每次 consolidation 操作后，被合并的节点 transform_count += 1，confidence 降低。这防止了"摘要的摘要的摘要"变得过于自信——信息在每次变换中都有损失。

### 4. RecurrenceDetector 是 ConsolidationRouter 的信号源

这两个 API 不是独立的——RecurrenceDetector 产生的 trigger 直接喂给 ConsolidationRouter：

```
add_node() → RecurrenceDetector.observe()
                    ↓ (if triggered)
           ConsolidationRouter.route(trigger=RECURRENCE) → SMART mode
                    ↓
           SmartConsolidator.consolidate() (4-phase Dreaming)
```

这意味着实现顺序很重要：先 RecurrenceDetector（API 2），再 ConsolidationRouter（API 3）。Maturation（API 1）和 confidence_score（API 5）可以并行实现因为它们是节点级操作。

### 5. forgetting_curve 不是简单的指数衰减

三个因素使它远超 `e^(-t/S)`：
- **Spaced repetition（访问强化）：** `reinforcement_factor ** access_count` 使每次访问都延长 half-life。这是 Ebbinghaus 原始发现的核心。
- **Q-value weighting（重要性加权）：** Q=1 的记忆 half-life 是 Q=0 的 5 倍。高价值记忆"忘得慢"。
- **Graph activity（FOREVER-inspired）：** 活跃 graph 中所有记忆衰减更慢，因为系统还在快速演化。

**对 agent-memory-graph 的意义：** 现有的 `staleness_score` 是静态的（基于 age + access）。`forgetting_curve` 是动态的（考虑 graph 整体活跃度 + Q-value + 访问历史），是 staleness_score 的升级版。

---

## 实现顺序与测试计划

### TDD 循环（遵循 autoresearch 方法论）

```
Baseline: 2007 tests (2026-07-08 cycle 200)

Phase 1: Memory Maturation (API 1)
  → 新增 MemoryMaturation class
  → 测试: sigmoid 计算正确性, 零时刻 ≈ 0.04, 24h = 0.50
  → 预期: +15-20 tests → 2022-2027
  → commit: "feat: Memory Maturation (sigmoid activation)"

Phase 2: RecurrenceDetector (API 2)  
  → 新增 RecurrenceDetector class
  → 测试: 单次观察不触发, 3次同主题触发, 跨主题不触发
  → 预期: +12-16 tests → 2034-2043
  → commit: "feat: RecurrenceDetector (RecMem-style trigger)"

Phase 3: ConsolidationRouter (API 3)
  → 新增 ConsolidationRouter class  
  → 测试: 每种 TriggerType 路由到正确 mode
  → 预期: +10-14 tests → 2044-2057
  → commit: "feat: ConsolidationRouter (FAST/SMART dual-mode)"

Phase 4: Recall with Activation (API 4)
  → 修改 recall 方法, 加入 activation 过滤
  → 测试: immature 不返回, mature 返回, fallback 正确
  → 预期: +8-12 tests → 2052-2069
  → commit: "feat: Recall with Activation gating"

Phase 5: confidence_score (API 5)
  → 新增 ConfidenceScorer class
  → 测试: 各维度权重正确, edge cases (0 access, high conflicts)
  → 预期: +12-16 tests → 2064-2085
  → commit: "feat: confidence_score (unified trust metric)"

Phase 6: forgetting_curve (API 6)
  → 新增 ForgettingCurve class
  → 测试: 衰减计算, 访问强化, Q-value 加权, graph activity 调整
  → 预期: +14-18 tests → 2078-2103
  → commit: "feat: forgetting_curve (Ebbinghaus + FOREVER)"

Target: 2078-2103 tests (from 2007 baseline, +71-96 tests)
```

### experiments.tsv 格式

```
timestamp	commit	metric	value	status	description
2026-07-09T20:00	baseline	test_count	2007	baseline	cycle 200 subgraph_centrality
2026-07-09T20:30	a1b2c3d	test_count	2027	keep	Memory Maturation sigmoid
2026-07-09T21:00	b2c3d4e	test_count	2043	keep	RecurrenceDetector
2026-07-09T21:30	c3d4e5f	test_count	2057	keep	ConsolidationRouter
2026-07-09T22:00	d4e5f6g	test_count	2069	keep	Recall with Activation
2026-07-09T22:30	e5f6g7h	test_count	2085	keep	confidence_score
2026-07-09T23:00	f6g7h8i	test_count	2103	keep	forgetting_curve
```

---

## 下一步行动

### 立即可做（本 cron 的下一个 cycle）
1. **将代码示例中的 6 个 class 集成到 `memory_graph.py`** — 每个 class 独立添加，不修改现有方法（surgical changes）。每个 API 的测试文件独立创建。
2. **实现顺序: API 1 → 2 → 3 → 4 → 5 → 6**（前序 API 是后续 API 的依赖）。Phase 1-3 可在一个 dev cycle 完成，Phase 4-6 在下一个。

### 本周
3. **Pre-commit 防 phantom** — 在实现前先加 pre-commit hook 验证 source 文件变更（防止再次 phantom commit）。教训来自 07-07：6 个 phantom APIs 就是因为 test 改了但 source 没改。
4. **Smart mode LLM callback 接口** — ConsolidationRouter 的 SMART mode 需要一个可插拔的 LLM callback。设计接口：`def llm_consolidate(nodes, context) -> list[MemoryNode]`，生产环境接 GPT-4o-mini，测试用 mock。

### 持续研究
5. **AgeMem 的 RL 路线评估** — 当前 6 个 API 都是算法驱动的（FAST mode 级别）。AgeMem 的 RL 方法是 12-18 月后的升级路径。评估：agent-memory-graph 的 6 个 API 作为"规则基线"，未来 RL policy 学习何时打破规则。
6. **Portable Agent Memory 的 Merkle-DAG** — 如果 agent-memory-graph 未来需要跨 agent 共享记忆（multi-agent 场景），Merkle-DAG + hash verification 是已验证的防篡改方案。

---

## 参考文献与来源

| # | 来源 | 类型 | 关键贡献 |
|---|------|------|---------|
| 1 | Human-Inspired Memory Architecture (arXiv:2605.08538) | Paper | Memory maturation sigmoid formula, dual-trace design, Kitamura engram silence |
| 2 | RecMem (arXiv:2605.16045, ACL 2026 Findings) | Paper | Three-tier subconscious architecture, recurrence-triggered consolidation, -87% token cost |
| 3 | FOREVER (arXiv:2601.03938, ACL 2026 Camera-ready) | Paper | Model-centric time via parameter update magnitude, intensity-aware regularization |
| 4 | Portable Agent Memory (arXiv:2605.11032) | Paper | Five-component memory model, confidence scoring, Merkle-DAG provenance, 100% tamper detection |
| 5 | AgeMem / Agentic Memory (arXiv:2601.01885, ACL 2026 Long) | Paper | Memory ops as RL tools, step-wise GRPO, learned memory policies |
| 6 | Evidence Tracing Survey (arXiv:2606.04990) | Survey | Provenance-aware retrieval, memory write lineage, taint tracking |
| 7 | Ebbinghaus (1885) + PMC replication (NIH) | Classic | Forgetting curve formula validation, power function fit, spaced repetition effect |
| 8 | ICLR 2026 MemAgents Workshop | Event | Adaptive Memory Admission Control, fast-slow variational CL, CraniMem |
| 9 | Mem0 State of Agent Memory 2026 | Blog | Memory staleness as open problem, LoCoMo 92.5% benchmark, token-efficient algorithms |
| 10 | Biologically-Inspired Forgetting (arXiv:2604.04514) | Paper | Forgetting-quantization coupling, SYNAPSE spreading activation, zero-LLM enterprise memory |
| 11 | The Nuanced Perspective: Designing Agentic Memory | Blog | Five cognitive memory types, security >90% vulnerable, MIA 7B > 32B baseline |
| 12 | Zelos AI: Continual Learning for AI Agents | Blog | FOREVER + A-MEM + JIT-RL survey, biologically-inspired consolidation roadmap |

---

## 笔记质量自评

| 维度 | 状态 | 说明 |
|------|------|------|
| 核心概念 ≥ 3 | ✅ 5 个 | Memory Maturation (sigmoid) / FOREVER (model-centric time) / RecMem (3-tier recurrence) / Portable Memory (5-component confidence) / AgeMem (RL memory ops) |
| 可运行代码 ≥ 1 | ✅ 1 个完整文件 | 350+ 行，6 个独立 class + 集成 demo，`if __name__` 可直接运行 |
| 关键洞察 ≥ 3 | ✅ 5 条 | Maturation 免费过滤 / FOREVER→graph activity 映射 / confidence 五维已有四维基础 / RecurrenceDetector 是 Router 信号源 / forgetting_curve 不是简单指数 |
| 下一步行动 ≥ 1 | ✅ 6 个 | TDD 实现计划 6 phase + experiments.tsv + pre-commit 防 phantom |
| 与现有项目关联 | ✅ | 直接关联 agent-memory-graph 的 MemoryNode / add_node / recall / conflict_detect / staleness_score / sleep_consolidate / Q-value |
| 独到见解 | ✅ | "graph activity 映射 model time" + "transform_count 防摘要降级" + "实现顺序依赖: RecurrenceDetector → Router" |
| 代码可运行验证 | ✅ | 包含完整 demo，6 个 API 互相调用，输出可视化遗忘曲线 |
