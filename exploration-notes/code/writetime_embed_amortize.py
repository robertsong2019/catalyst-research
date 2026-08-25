#!/usr/bin/env python3
"""Research #088 — 写时嵌入摊销原型（FastAppendQueue 钩子路径）

对照三臂（真实 model2vec potion-retrieval-32M 引擎，#083 同款）：
  A. query-time（现状）: 每题把全部 haystack chunks 重新分块+嵌入 → Q×(N+1) 次 embed
  B. write-time（摊销）: flush() 时一次批量嵌入 + 内容哈希 memo + 查询只嵌问题 → N + Q 次
  C. write-time + merge 线性合并: consolidate 合并节点时，静态嵌入的均值池化
     线性性质允许加权平均替代重嵌入 → 合并零 embed

生产对照（源码取证 2026-08-25）：
  - Mem0 main.py:902/994  写路径 embed_batch(mem_texts,"add") + 逐条降级
  - Mem0 main.py:689      update 路径 re-embed（"update" 动作标签）
  - Graphiti graphiti.py:1648  name_embedding is None → generate（懒嵌入 memo）
"""

from __future__ import annotations

import hashlib
import time

WORDS_PER_CHUNK = 150          # amg SIDECHANNEL_WORDS_PER_CHUNK 同款
N_SESSIONS = 120               # 会话数（2× LME 48.3 会话/题均值）

# ── 合成语料：preference/事实陈述风格（LME 侧通道目标域）──────────────
SEEDS = [
    "user prefers {a} over {b} for {ctx}",
    "user mentioned buying a {a} last month",
    "user works on {a} projects during weekends",
    "user dislikes {a} because of {ctx}",
    "user asked about {a} recommendations for {ctx}",
]
A_POOL = ["python", "rust", "vinyl records", "Fender Stratocaster", "mechanical keyboards",
          "trail running", "espresso", "film photography", "analog synths", "road cycling"]
B_POOL = ["java", "golang", "CDs", "Gibson Les Paul", "membrane keyboards",
          "gym treadmills", "instant coffee", "digital cameras", "digital pianos", "swimming"]
CTX_POOL = ["side projects", "weekend hacking", "home studio recording", "daily commute",
            "team tooling", "gift shopping", "hobby budget planning"]


def build_corpus(n_sessions: int) -> list[str]:
    import random
    rng = random.Random(42)
    sessions = []
    for s in range(n_sessions):
        turns = []
        for _ in range(rng.randint(8, 16)):          # 每会话 8-16 turns（~1-3 chunks）
            t = rng.choice(SEEDS)
            turns.append(t.format(a=rng.choice(A_POOL), b=rng.choice(B_POOL),
                                  ctx=rng.choice(CTX_POOL)))
        sessions.append(" ".join(turns))
    return sessions


def chunk(text: str, wpc: int = WORDS_PER_CHUNK) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + wpc]) for i in range(0, len(words), wpc)] or [text]


# ── 引擎：真实静态嵌入 + 计数器 ────────────────────────────────────────
class CountingEngine:
    """model2vec 静态引擎（#083 实测 2463 chunks/s）；每维调用计数。"""

    def __init__(self):
        from model2vec import StaticModel
        self.model = StaticModel.from_pretrained("minishlab/potion-retrieval-32M")
        self.calls = 0          # embed 调用次数
        self.texts = 0          # 嵌入文本条数

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts += len(texts)
        vecs = self.model.encode(texts, normalize=True)
        return [list(map(float, v)) for v in vecs]


# ── Arm A：查询时嵌入（amg_bench_quality 现状语义）─────────────────────
def arm_query_time(engine: CountingEngine, sessions: list[str], queries: list[str]) -> float:
    t0 = time.perf_counter()
    scores: list[tuple[int, float]] = []
    for q in queries:
        # 现状：每题把全部 haystack 重新分块 + 全量嵌入（无跨题缓存）
        all_chunks, sid_of = [], []
        for sid, sess in enumerate(sessions):
            for c in chunk(sess):
                all_chunks.append(c)
                sid_of.append(sid)
        vecs = engine.embed(all_chunks)
        qv = engine.embed([q])[0]                     # 问题向量单独嵌（与 Arm B 同构，
        best, best_s = -1, -1.0                       # 消除同批组成性浮点差）
        for i, v in enumerate(vecs):                  # chunk-max 会话得分
            s = sum(x * y for x, y in zip(v, qv))
            if s > best_s:
                best_s, best = s, sid_of[i]
        scores.append((best, best_s))
    return time.perf_counter() - t0, scores


# ── Arm B：写时嵌入（flush 批量 + 内容哈希 memo）───────────────────────
class WriteTimeMem:
    """FastAppendQueue 钩子语义：append→buffer；flush→一次批量嵌入（memo 去重）；
    查询只嵌问题 + 向量点积。Mem0 的 batch 模式 + Graphiti 的 None 检查模式合体。"""

    def __init__(self, engine: CountingEngine):
        self.engine = engine
        self._buffer: list[str] = []                  # System-1 暂存
        self._memo: dict[str, list[float]] = {}       # content-hash → vec
        self._sess_vecs: dict[int, list[list[float]]] = {}

    def append(self, session: str) -> int:
        self._buffer.append(session)
        return len(self._buffer) - 1

    def flush(self) -> dict:
        t0 = time.perf_counter()
        pending, texts = [], []
        for sess in self._buffer:
            for c in chunk(sess):
                h = hashlib.sha1(c.encode()).hexdigest()
                if h not in self._memo:               # memo 命中 → 零嵌入
                    pending.append((h, c))
                    texts.append(c)
        if texts:                                     # 一次批量前向（Mem0 Phase-3 模式）
            for (h, _), v in zip(pending, self.engine.embed(texts)):
                self._memo[h] = v
        for sess in self._buffer:
            sid = len(self._sess_vecs)
            self._sess_vecs[sid] = [self._memo[hashlib.sha1(c.encode()).hexdigest()]
                                    for c in chunk(sess)]
        n = len(self._buffer)
        self._buffer.clear()
        return {"flushed": n, "new_embeds": len(texts),
                "sec": time.perf_counter() - t0}

    def search(self, q: str) -> tuple[int, float]:
        qv = self.engine.embed([q])[0]                # 查询路径唯一嵌入调用
        best, best_s = -1, -1.0
        for sid, vecs in self._sess_vecs.items():
            s = max(sum(x * y for x, y in zip(v, qv)) for v in vecs)   # chunk-max
            if s > best_s:
                best_s, best = s, sid
        return best, best_s

    def merge_sessions(self, sid_a: int, sid_b: int, w_a: float = 0.5) -> None:
        """consolidate() 合并：静态嵌入=查表均值池化，线性 → 加权平均即合并向量，
        零重嵌入（神经模型无此性质，须 re-embed——Mem0 update 路径）。"""
        a, b = self._sess_vecs[sid_a], self._sess_vecs[sid_b]
        merged = [[w_a * x + (1 - w_a) * y for x, y in zip(va, vb)]
                  for va, vb in zip(a, b)]             # 逐 chunk 对齐加权
        self._sess_vecs[sid_a] = merged
        del self._sess_vecs[sid_b]                    # tombstone：被吸收者退役


def main() -> None:
    sessions = build_corpus(N_SESSIONS)
    queries = [
        "what guitars does the user like",
        "coffee preferences of the user",
        "programming language preferences",
        "weekend hobbies",
        "music gear recommendations",
        "keyboard preferences",
        "exercise routines the user enjoys",
        "camera preferences",
        "what synth gear user owns",
        "gift ideas based on user interests",
        "running vs gym preferences",
        "film vs digital photography taste",
        "studio recording equipment interests",
        "commute listening or reading habits",
        "budget planning for hobbies",
        "team tooling opinions",
        "coffee brewing setup at home",
        "bicycle or guitar shopping plans",
    ]

    n_chunks = sum(len(chunk(s)) for s in sessions)
    nq = len(queries)
    print(f"corpus: {N_SESSIONS} sessions, {n_chunks} chunks, {nq} queries")
    print(f"engine: model2vec potion-retrieval-32M (static, linear mean-pool)\n")

    eng_a = CountingEngine()
    t_a, res_a = arm_query_time(eng_a, sessions, queries)
    print(f"[A] query-time  : {t_a:6.2f}s  embed_calls={eng_a.calls:4d}  "
          f"texts={eng_a.texts:5d}  per-query={t_a/nq*1000:6.0f}ms")

    eng_b = CountingEngine()
    mem = WriteTimeMem(eng_b)
    for s in sessions:
        mem.append(s)
    t_w = time.perf_counter()
    fr = mem.flush()
    t_write = time.perf_counter() - t_w
    t0 = time.perf_counter()
    res_b = [mem.search(q) for q in queries]
    t_q = time.perf_counter() - t0
    agree = sum(1 for (a, _), (b, _) in zip(res_a, res_b) if a == b)
    print(f"[B] write-time  : flush {t_write:5.2f}s ({fr['new_embeds']} new embeds, "
          f"{n_chunks - fr['new_embeds']} memo-hit dupes) + query {t_q:5.3f}s  "
          f"embed_calls={eng_b.calls:4d}  texts={eng_b.texts:5d}  per-query={t_q/nq*1000:6.0f}ms")

    # 二次 ingest 同语料（重放/回归场景）：memo 全命中
    eng_c = CountingEngine()
    mem2 = WriteTimeMem(eng_c)
    mem2._memo = dict(mem._memo)                      # 预载 memo（进程内持久化语义）
    for s in sessions:
        mem2.append(s)
    fr2 = mem2.flush()
    print(f"[B'] re-ingest  : new_embeds={fr2['new_embeds']}  "
          f"embed_calls={eng_c.calls}  (content-hash memo 全命中)")

    # 合并摊销：60 会话两两合并 → 零嵌入
    calls_before = eng_b.calls
    for i in range(0, N_SESSIONS - 1, 2):
        mem.merge_sessions(i, i + 1)
    print(f"[C] merge ×{N_SESSIONS//2}     : embed_calls_delta={eng_b.calls - calls_before} "
          f"(线性加权合并，静态嵌入免重嵌)")

    speedup = t_a / t_q
    print(f"\namortization: query-time {t_a/nq*1000:.0f}ms/q → write-time "
          f"{t_q/nq*1000:.0f}ms/q ({speedup:.0f}× query speedup); "
          f"top-1 agreement A vs B = {agree}/{nq}")


if __name__ == "__main__":
    main()
