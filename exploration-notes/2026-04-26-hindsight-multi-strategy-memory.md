# Hindsight: 多策略 Agent 记忆架构深度研究

> 📅 2026-04-26 | 🧪 Catalyst Deep Exploration
> 📄 Paper: [Hindsight is 20/20](https://arxiv.org/abs/2512.12818) (Dec 2025, Vectorize.io + Virginia Tech + Washington Post)
> 💻 Repo: [github.com/vectorize-io/hindsight](https://github.com/vectorize-io/hindsight)
> ⭐ Benchmark: LongMemEval 91.4%, LoCoMo 89.61% (SOTA)

---

## 核心概念 (5个)

### 1. 四网络记忆组织 (Four-Network Memory)

Hindsight 将 Agent 记忆分为四个逻辑网络，每个服务不同的认知角色：

| 网络 | 符号 | 存储 | 示例 |
|------|------|------|------|
| **World** | 𝒲 | 客观世界事实 | "Alice 在 Google 当工程师" |
| **Experience** | ℬ | Agent 自身经历(第一人称) | "我帮用户调试了 Python 脚本" |
| **Opinion** | 𝒪 | 主观信念 + 置信度 | "Python 是最好的入门语言 (c=0.8)" |
| **Observation** | 𝒮 | 从多个事实合成的实体摘要 | "Alice: 软件工程师，喜欢徒步" |

**关键洞察**: 区分"知道的"和"相信的"(epistemic clarity)，这是其他框架都缺少的。Mem0/Zep/MemGPT 都没有事实/观点分离。

### 2. 三操作原语 (Retain, Recall, Reflect)

```
Retain(Bank, Data) → Memory'     // 摄入对话 → 结构化记忆图
Recall(Bank, Query, budget) → Facts  // 四路并行检索 → RRF融合 → reranking
Reflect(Bank, Query, Profile) → (Response, Opinions')  // 偏好条件推理 + 观点演化
```

- **Retain**: 粗粒度叙事提取(2-5条/对话)，而非碎片化句子
- **Recall**: 语义搜索 + BM25 + 图遍历 + 时间过滤 → RRF → Cross-encoder rerank
- **Reflect**: 带行为参数(skepticism, literalism, empathy)的推理层

### 3. 四路并行检索 (Multi-Strategy Recall)

这是性能突破的关键——AMS 目前只有 BM25 + embedding + unified RRF，Hindsight 多了图遍历和时间过滤：

```
Query → ┌─ Semantic Vector Search ──┐
        ├─ BM25 Keyword Search ─────┤
        ├─ Graph Traversal ──────────┼→ RRF Fusion → Cross-encoder Rerank → Top-k (token budget)
        └─ Temporal Filtering ───────┘
```

- **RRF (Reciprocal Rank Fusion)**: `1/(k + rank_i)` 融合多策略排名
- **Token budget**: 返回结果受 token 数限制，而非条数限制
- **Cross-encoder reranking**: 最终精排阶段

### 4. 行为配置文件 (CARA - Coherent Adaptive Reasoning)

```
Profile Θ = {
  skepticism: 1-5,    // 质疑程度
  literalism: 1-5,    // 字面理解程度
  empathy: 1-5,       // 共情程度
  bias_strength: 0-1  // 偏见强度
}
```

观点网络 𝒪 中每个观点 = (text, confidence, timestamp)，通过证据支持/反驳来更新置信度。这让 Agent 能表达稳定的观点同时允许信念演化。

### 5. 实体感知记忆图 (Entity-Aware Memory Graph)

四种边类型：
- **Temporal**: 时间邻近度衰减权重 `exp(-Δt/σ)`
- **Semantic**: 余弦相似度 > 阈值
- **Entity**: 共享实体的记忆互联
- **Causal**: 因果关系链接

实体消解: `sim = α·sim_str + β·sim_co + γ·sim_temp`

---

## 性能基准

| 系统 | LongMemEval | LoCoMo | 特点 |
|------|-------------|--------|------|
| **Hindsight (72B)** | **91.4%** | **89.61%** | 四网络 + 多策略 + 观点演化 |
| Hindsight (20B) | 83.6% | 85.67% | 开源模型 |
| Full-context GPT-4o | ~72% | ~76% | 无记忆系统 |
| Mem0 | 49.0% | - | 向量+图，最大生态 |
| Full-context baseline | 39% | 75.78% | 同backbone无记忆 |
| Hindsight vs baseline | **+44.6%** | **+9.89%** | 提升幅度 |

---

## 可运行代码：Hindsight 风格四网络记忆系统原型

以下是一个零依赖 Python 实现，演示 Hindsight 的核心概念：
四网络记忆组织 + 四路并行检索 + RRF 融合 + 观点演化。

```python
"""
hindsight_mini.py — Hindsight 风格四网络记忆系统原型
零依赖 Python 3.9+，演示核心架构思想

Based on: "Hindsight is 20/20" (arXiv:2512.12818)
- Four-network memory (World, Experience, Opinion, Observation)
- Four-way parallel retrieval (Semantic, BM25, Graph, Temporal)
- RRF (Reciprocal Rank Fusion)
- Opinion evolution with confidence scores
"""

import json
import math
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

# ── Data Structures ──────────────────────────────────────────

@dataclass
class MemoryUnit:
    """Hindsight memory unit: f = (u, b, t, v, τs, τe, τm, ℓ, c, x)"""
    id: str
    text: str
    fact_type: str  # world | experience | opinion | observation
    timestamp_start: float  # τs
    timestamp_end: float    # τe
    timestamp_mention: float  # τm
    confidence: Optional[float] = None  # for opinions
    entities: list = field(default_factory=list)
    embedding: list = field(default_factory=list)  # simplified: TF-IDF-like
    access_count: int = 0

    def token_estimate(self):
        """Rough token count for budget management"""
        return len(self.text.split())

    def to_dict(self):
        return {
            "id": self.id, "text": self.text, "type": self.fact_type,
            "ts": self.timestamp_start, "te": self.timestamp_end,
            "tm": self.timestamp_mention, "confidence": self.confidence,
            "entities": self.entities
        }


class HindsightMini:
    """Mini implementation of Hindsight's four-network memory architecture"""

    def __init__(self):
        self.memories = {}  # id → MemoryUnit
        self.graph_edges = defaultdict(list)  # node_id → [(target_id, weight, type)]
        self.entity_index = defaultdict(set)  # entity → {memory_ids}

    # ── RETAIN ─────────────────────────────────────────────

    def retain(self, text: str, fact_type: str = "world",
               entities: list = None, confidence: float = None,
               ts: float = None, te: float = None):
        """Store a new memory unit (simplified retain operation)"""
        now = datetime.now().timestamp()
        mem_id = hashlib.md5(f"{text}{now}".encode()).hexdigest()[:12]

        mem = MemoryUnit(
            id=mem_id,
            text=text,
            fact_type=fact_type,
            timestamp_start=ts or now,
            timestamp_end=te or now,
            timestamp_mention=now,
            confidence=confidence,
            entities=entities or [],
            embedding=self._simple_embedding(text)
        )

        self.memories[mem_id] = mem

        # Update entity index
        for e in mem.entities:
            self.entity_index[e.lower()].add(mem_id)

        # Build graph links
        self._build_links(mem)

        # Opinion evolution: if new evidence contradicts/supports existing opinions
        if fact_type == "world" and confidence is None:
            self._evolve_opinions(mem)

        return mem_id

    def retain_conversation(self, messages: list, agent_name: str = "Agent"):
        """Simplified narrative fact extraction from conversation"""
        fact_ids = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            now = datetime.now().timestamp()

            # Classify fact type based on role and content
            if role == "assistant":
                fact_type = "experience"
            elif any(w in content.lower() for w in ["think", "believe", "prefer", "like"]):
                fact_type = "opinion"
            else:
                fact_type = "world"

            # Extract entities (simple capitalized words)
            entities = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', content)

            # Create narrative fact (coarse-grained, preserving context)
            text = f"[{role}] {content}"
            mid = self.retain(text, fact_type=fact_type, entities=entities, ts=now, te=now)
            fact_ids.append(mid)

        return fact_ids

    # ── RECALL ─────────────────────────────────────────────

    def recall(self, query: str, token_budget: int = 2000,
               temporal_range: tuple = None) -> list:
        """Four-way parallel retrieval with RRF fusion and token budget"""

        if not self.memories:
            return []

        results = {}

        # Strategy 1: Semantic (TF-IDF cosine similarity)
        semantic = self._search_semantic(query)
        for mid, score in semantic:
            results.setdefault(mid, {})["semantic"] = score

        # Strategy 2: BM25-style keyword matching
        bm25 = self._search_bm25(query)
        for mid, score in bm25:
            results.setdefault(mid, {})["bm25"] = score

        # Strategy 3: Graph traversal (entity-based expansion)
        graph = self._search_graph(query)
        for mid, score in graph:
            results.setdefault(mid, {})["graph"] = score

        # Strategy 4: Temporal filtering
        temporal = self._search_temporal(query, temporal_range)
        for mid, score in temporal:
            results.setdefault(mid, {})["temporal"] = score

        # RRF Fusion (k=60, standard parameter)
        k = 60
        fused = {}
        for mid, strategies in results.items():
            rrf_score = 0.0
            for strategy_name, raw_score in strategies.items():
                # Convert raw score to rank-based RRF
                all_scores = [(m, s.get(strategy_name, 0))
                              for m, s in results.items()
                              if strategy_name in s]
                all_scores.sort(key=lambda x: -x[1])
                rank = next((i+1 for i, (m, _) in enumerate(all_scores) if m == mid), 999)
                rrf_score += 1.0 / (k + rank)
            fused[mid] = rrf_score

        # Sort by fused score, apply token budget
        ranked = sorted(fused.items(), key=lambda x: -x[1])
        selected = []
        tokens_used = 0
        for mid, score in ranked:
            mem = self.memories[mid]
            cost = mem.token_estimate()
            if tokens_used + cost <= token_budget:
                selected.append((mem, score))
                tokens_used += cost
                mem.access_count += 1

        return selected

    # ── REFLECT (simplified CARA) ──────────────────────────

    def reflect(self, query: str, skepticism: float = 3.0,
                empathy: float = 3.0, literalism: float = 3.0) -> dict:
        """Generate a reflection using recalled memories and behavioral profile"""

        memories = self.recall(query)

        # Separate facts from opinions (epistemic clarity)
        facts = [(m, s) for m, s in memories if m.fact_type in ("world", "experience")]
        opinions = [(m, s) for m, s in memories if m.fact_type == "opinion"]
        observations = [(m, s) for m, s in memories if m.fact_type == "observation"]

        # Behavioral profile modulates response construction
        bias = (skepticism + literalism) / 10.0  # 0.2 - 1.0

        response_parts = []

        # High skepticism → prefer facts over opinions
        if facts:
            top_facts = facts[:3]
            for mem, score in top_facts:
                response_parts.append(f"📌 FACT: {mem.text} (score: {score:.4f})")

        # Low skepticism → include opinions
        if opinions and skepticism < 4:
            for mem, score in opinions[:2]:
                conf = mem.confidence or 0.5
                adjusted_conf = conf * (1 - bias * 0.3)  # bias modulates confidence
                response_parts.append(
                    f"💭 OPINION: {mem.text} (confidence: {adjusted_conf:.2f})"
                )

        if observations:
            for mem, score in observations[:2]:
                response_parts.append(f"🔍 OBSERVATION: {mem.text}")

        # Opinion formation: if strong evidence found, create new opinion
        if len(facts) >= 2 and not opinions:
            new_confidence = min(0.9, sum(s for _, s in facts[:3]) / len(facts))
            self.retain(
                f"Based on evidence, {query} → synthesized understanding",
                fact_type="opinion",
                confidence=new_confidence,
                entities=list(set(e for m, _ in facts for e in m.entities))
            )
            response_parts.append(f"🆕 NEW OPINION FORMED (confidence: {new_confidence:.2f})")

        return {
            "query": query,
            "profile": {"skepticism": skepticism, "empathy": empathy, "literalism": literalism},
            "facts_count": len(facts),
            "opinions_count": len(opinions),
            "response_parts": response_parts,
            "total_tokens_used": sum(m.token_estimate() for m, _ in memories)
        }

    # ── Internal Methods ───────────────────────────────────

    def _simple_embedding(self, text: str) -> list:
        """Simple TF-based pseudo-embedding (real Hindsight uses dense vectors)"""
        words = re.findall(r'\w+', text.lower())
        counter = defaultdict(int)
        for w in words:
            counter[w] += 1
        return counter

    def _cosine_sim(self, a: dict, b: dict) -> float:
        """Cosine similarity between two sparse vectors (dicts)"""
        if not a or not b:
            return 0.0
        common = set(a.keys()) & set(b.keys())
        if not common:
            return 0.0
        dot = sum(a[k] * b[k] for k in common)
        mag_a = math.sqrt(sum(v**2 for v in a.values()))
        mag_b = math.sqrt(sum(v**2 for v in b.values()))
        return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0

    def _search_semantic(self, query: str) -> list:
        """Strategy 1: Semantic vector search"""
        q_emb = self._simple_embedding(query)
        scores = []
        for mid, mem in self.memories.items():
            sim = self._cosine_sim(q_emb, mem.embedding)
            if sim > 0:
                scores.append((mid, sim))
        scores.sort(key=lambda x: -x[1])
        return scores[:20]

    def _search_bm25(self, query: str) -> list:
        """Strategy 2: BM25-style keyword matching"""
        q_terms = set(re.findall(r'\w+', query.lower()))
        scores = []
        N = len(self.memories)
        df = defaultdict(int)
        for mem in self.memories.values():
            terms = set(re.findall(r'\w+', mem.text.lower()))
            for t in terms:
                df[t] += 1

        for mid, mem in self.memories.items():
            terms = re.findall(r'\w+', mem.text.lower())
            tf = defaultdict(int)
            for t in terms:
                tf[t] += 1
            dl = len(terms)
            avgdl = sum(len(re.findall(r'\w+', m.text)) for m in self.memories.values()) / max(N, 1)

            k1, b = 1.5, 0.75
            score = 0.0
            for qt in q_terms:
                if qt in tf:
                    idf = math.log((N - df.get(qt, 0) + 0.5) / (df.get(qt, 0) + 0.5) + 1)
                    tf_component = (tf[qt] * (k1 + 1)) / (tf[qt] + k1 * (1 - b + b * dl / avgdl))
                    score += idf * tf_component
            if score > 0:
                scores.append((mid, score))
        scores.sort(key=lambda x: -x[1])
        return scores[:20]

    def _search_graph(self, query: str) -> list:
        """Strategy 3: Entity-based graph traversal"""
        q_entities = set(re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', query))
        q_entities = {e.lower() for e in q_entities}

        scores = {}
        for entity in q_entities:
            if entity in self.entity_index:
                for mid in self.entity_index[entity]:
                    scores[mid] = scores.get(mid, 0) + 1.0
                    # 1-hop expansion
                    for target_id, weight, etype in self.graph_edges.get(mid, []):
                        scores[target_id] = scores.get(target_id, 0) + weight * 0.5

        return sorted(scores.items(), key=lambda x: -x[1])[:20]

    def _search_temporal(self, query: str, temporal_range: tuple = None) -> list:
        """Strategy 4: Temporal filtering (recency-weighted)"""
        now = datetime.now().timestamp()

        # Detect temporal hints in query
        scores = []
        for mid, mem in self.memories.items():
            age_hours = (now - mem.timestamp_mention) / 3600
            recency = math.exp(-age_hours / 168)  # 1-week half-life
            scores.append((mid, recency))

        scores.sort(key=lambda x: -x[1])
        return scores[:20]

    def _build_links(self, mem: MemoryUnit):
        """Build graph edges for a new memory"""
        for other_id, other in self.memories.items():
            if other_id == mem.id:
                continue

            # Semantic link
            sim = self._cosine_sim(mem.embedding, other.embedding)
            if sim > 0.3:
                self.graph_edges[mem.id].append((other_id, sim, "semantic"))
                self.graph_edges[other_id].append((mem.id, sim, "semantic"))

            # Temporal link
            dt = abs(mem.timestamp_mention - other.timestamp_mention) / 3600
            if dt < 48:  # within 48 hours
                w = math.exp(-dt / 24)
                self.graph_edges[mem.id].append((other_id, w, "temporal"))
                self.graph_edges[other_id].append((mem.id, w, "temporal"))

            # Entity link
            shared = set(e.lower() for e in mem.entities) & set(e.lower() for e in other.entities)
            if shared:
                self.graph_edges[mem.id].append((other_id, 1.0, "entity"))
                self.graph_edges[other_id].append((mem.id, 1.0, "entity"))

    def _evolve_opinions(self, new_fact: MemoryUnit):
        """Opinion evolution: update confidence when new evidence arrives"""
        for mid, mem in self.memories.items():
            if mem.fact_type != "opinion":
                continue
            # Check entity overlap
            shared = set(e.lower() for e in new_fact.entities) & set(e.lower() for e in mem.entities)
            if shared and mem.confidence is not None:
                # Supporting evidence boosts confidence slightly
                mem.confidence = min(1.0, mem.confidence + 0.05)

    def stats(self):
        """Memory bank statistics"""
        by_type = defaultdict(int)
        for mem in self.memories.values():
            by_type[mem.fact_type] += 1
        return {
            "total_memories": len(self.memories),
            "by_type": dict(by_type),
            "total_entities": len(self.entity_index),
            "total_edges": sum(len(v) for v in self.graph_edges.values())
        }


# ── Demo / Test ─────────────────────────────────────────────

if __name__ == "__main__":
    hs = HindsightMini()

    # 1. RETAIN: Store various types of memories
    print("=" * 60)
    print("🔬 HINDSIGHT MINI — Four-Network Memory Demo")
    print("=" * 60)

    # World facts
    hs.retain("Alice works at Google as a senior ML engineer",
              fact_type="world", entities=["Alice", "Google"])
    hs.retain("Bob prefers Python over JavaScript for backend development",
              fact_type="world", entities=["Bob", "Python", "JavaScript"])
    hs.retain("The team uses Kubernetes for deployment",
              fact_type="world", entities=["Kubernetes"])

    # Experience
    hs.retain("I helped Alice debug a distributed training issue last week",
              fact_type="experience", entities=["Alice"],
              confidence=0.9)

    # Opinions
    hs.retain("Python is the best language for ML engineering",
              fact_type="opinion", entities=["Python"],
              confidence=0.85)
    hs.retain("Microservices add unnecessary complexity for small teams",
              fact_type="opinion", entities=["Microservices"],
              confidence=0.7)

    # Observation (synthesized)
    hs.retain("Alice: Senior ML engineer at Google, uses Python, works on distributed training",
              fact_type="observation", entities=["Alice", "Google", "Python"])

    print(f"\n📊 Memory Stats: {hs.stats()}")

    # 2. RECALL: Multi-strategy retrieval
    print("\n" + "─" * 60)
    print("🔍 RECALL: 'What programming language does Alice use?'")
    print("─" * 60)
    results = hs.recall("What programming language does Alice use?")
    for mem, score in results:
        print(f"  [{mem.fact_type:12s}] {score:.4f} | {mem.text[:80]}")

    # 3. REFLECT: Preference-conditioned reasoning
    print("\n" + "─" * 60)
    print("💭 REFLECT: 'Should we use Python for the new project?'")
    print("  Profile: high skepticism (4), high empathy (4)")
    print("─" * 60)
    reflection = hs.reflect("Should we use Python for the new project?",
                            skepticism=4, empathy=4)
    for part in reflection["response_parts"]:
        print(f"  {part}")
    print(f"  Facts: {reflection['facts_count']}, Opinions: {reflection['opinions_count']}")

    # Low skepticism profile
    print("\n" + "─" * 60)
    print("💭 REFLECT: 'Should we use Python for the new project?'")
    print("  Profile: low skepticism (2), low empathy (2)")
    print("─" * 60)
    reflection2 = hs.reflect("Should we use Python for the new project?",
                             skepticism=2, empathy=2)
    for part in reflection2["response_parts"]:
        print(f"  {part}")

    # 4. RETAIN conversation and show graph connectivity
    print("\n" + "─" * 60)
    print("💬 RETAIN CONVERSATION: Multi-turn dialogue")
    print("─" * 60)
    conversation = [
        {"role": "user", "content": "Can you help me with the Kubernetes deployment? Alice suggested I ask you."},
        {"role": "assistant", "content": "Sure! I helped Alice with a similar deployment last week. Let me check the cluster config."},
        {"role": "user", "content": "She said you prefer Helm charts over raw YAML"},
        {"role": "assistant", "content": "Yes, Helm charts are more maintainable. I believe infrastructure as code should be versioned and templated."},
    ]
    ids = hs.retain_conversation(conversation)
    print(f"  Created {len(ids)} memory units from conversation")

    # Show updated stats
    print(f"\n📊 Updated Stats: {hs.stats()}")

    # 5. Recall with entity-based graph traversal
    print("\n" + "─" * 60)
    print("🔍 RECALL: 'Tell me about deployment practices'")
    print("─" * 60)
    results = hs.recall("Tell me about deployment practices")
    for mem, score in results:
        print(f"  [{mem.fact_type:12s}] {score:.4f} | {mem.text[:80]}")

    print("\n✅ Demo complete!")
    print("\n💡 Key takeaways from Hindsight:")
    print("   1. Four networks separate facts/beliefs → epistemic clarity")
    print("   2. Four-way retrieval + RRF → 91.4% on LongMemEval")
    print("   3. Behavioral profiles → consistent agent personality")
    print("   4. Opinion evolution → agents that learn, not just remember")
    print("   5. Entity-aware graph → multi-hop reasoning across conversations")
```

**运行方式**:
```bash
python3 hindsight_mini.py
```

---

## 关键洞察 (5条)

### 1. 事实/观点分离是 Agent 记忆的缺失拼图
当前所有主流框架 (Mem0, Zep, MemGPT) 都将事实和观点混存。Hindsight 的四网络让"Agent 知道什么"vs"Agent 相信什么"变得可审计。**这对 AMS 是重要升级方向**——AMS 当前有层级(L0/L1/L2)但没有事实/观点分离。

### 2. 四路并行检索比向量搜索强得多
BM25 + Semantic + Graph + Temporal → RRF 融合。AMS 已有 BM25 + Embedding + Unified RRF (三路)，但缺少 **图遍历** 和 **时间感知过滤**。添加这两路可能显著提升 recall 质量。

### 3. 行为配置文件让 Agent 有"性格"
通过 skepticism/literalism/empathy 参数控制推理风格，观点网络有置信度并能演化。这让同一个 Agent 对不同用户可以有不同的交互风格，且观点演化是可追溯的。**Catalyst 的 SOUL.md 可以转化为行为参数**。

### 4. 叙事式事实提取优于碎片化提取
Hindsight 提取 2-5 条叙事事实(覆盖整个对话)，而非逐句提取。这减少了碎片化问题，让下游检索更鲁棒。AMS 的当前提取是规则驱动的，可以借鉴叙事提取模式。

### 5. Token Budget 比 Top-k 更实用
用 token 数量而非条数限制返回结果，更贴合 LLM 的实际上下文窗口管理需求。AMS 的 searchUnified 可以增加这个特性。

---

## 与现有项目关联

| 项目 | 可借鉴的点 | 优先级 |
|------|-----------|--------|
| **Agent Memory Service** | 四网络组织、图遍历检索、时间感知过滤、token budget | 🔴 High |
| **Catalyst (OpenClaw)** | 行为参数 ← SOUL.md、观点网络 ← MEMORY.md | 🟡 Medium |
| **A2A Trust Extension** | 置信度演化机制可用于信任分数更新 | 🟡 Medium |
| **MCP Server** | Hindsight 的 retain/recall/reflect 可暴露为 MCP tools | 🟢 Low |

---

## AMS 升级路线图建议

### Phase 1: 四网络分类 (2-3天)
```javascript
// 在 MemoryUnit 中添加 factType 字段
// world | experience | opinion | observation
// retain() 时通过内容分析自动分类
```

### Phase 2: 图遍历检索 (2-3天)
```javascript
// 添加 searchGraph(query) 方法
// 基于 entity_index 做多跳遍历
// 融入 searchUnified 的 RRF
```

### Phase 3: 时间感知检索 (1天)
```javascript
// 添加 searchTemporal(query, range) 方法
// 时间衰减权重 + 范围过滤
```

### Phase 4: 观点演化 (2天)
```javascript
// Opinion 网络带 confidence 字段
// 新证据到来时更新 confidence
// reflect() 操作形成/强化观点
```

---

## 下一步行动

1. **实现 `hindsight_mini.py` 到 `lab/hindsight-mini/`** — 验证四网络 + 四路检索原型，运行测试
2. **AMS v0.2.0 添加四网络分类** — MemoryUnit 增加 factType，retain 自动分类
3. **AMS 添加 searchGraph()** — 基于 entity_index 的图遍历，融入 RRF
4. **实验**: 对比三路 vs 四路检索在 AMS 测试数据集上的 recall 质量

---

## 参考资源

- 📄 [Paper](https://arxiv.org/abs/2512.12818) — Hindsight is 20/20 (Dec 2025)
- 💻 [GitHub](https://github.com/vectorize-io/hindsight) — 开源实现，Docker 部署
- 🐍 `pip install hindsight-client` — Python SDK
- 📦 `npm install @vectorize-io/hindsight-client` — Node.js SDK
- 🏠 [hindsight.vectorize.io](https://hindsight.vectorize.io) — 官方文档
- 📊 LongMemEval Benchmark — [arxiv.org/abs/2410.10890](https://arxiv.org/abs/2410.10890)
- 📊 LoCoMo Benchmark — [arxiv.org/abs/2402.10790](https://arxiv.org/abs/2402.10790)

---

_Last updated: 2026-04-26_
