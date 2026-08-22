#!/usr/bin/env python3
"""Research #083 prototype: embedding side-channel for preference/ssa retrieval bridge.

Four arms on 86 LME_s questions (30 preference + 56 single-session-assistant):
  L  lexical    — token-overlap ranking (replicates #080 arm B)
  E  embedding  — all-MiniLM-L6-v2 ONNX int8, chunk-max cosine
  H  hybrid RRF — reciprocal rank fusion of L and E (k=60)
  D  determinism — same text embedded twice, bitwise compare

Metric: answer_session_hit@1 / @5 (gold session in top-k), per category.
Data: /tmp/c497/embed86.json (produced by embed_extract86.py)
"""
import json, re, sys, time, gc
import numpy as np
from fastembed import TextEmbedding

DATA = "/tmp/c497/embed86.json"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_WORDS = 150          # MiniLM context 256 tokens ≈ 190 words; stay safe
MAX_CHUNKS = 6             # covers ~900 words per session
RRF_K = 60

STOP = set("""a an the and or but if of to in on for with at by from as is are was were be been
being do does did have has had i you he she it we they me my your his her its our their this
that these those what which who whom when where why how any some would should could can will
just about there here also very get got like know think want need""".split())

def toks(s):
    return {t for t in re.findall(r"[a-z]{2,}", s.lower()) if t not in STOP}

def as_text(x):
    """session may be a str, a list of turn dicts {'role','content'}, or a list of strs."""
    if isinstance(x, str):
        return x
    parts = []
    for t in x:
        if isinstance(t, dict):
            parts.append(str(t.get("content", "")))
        elif isinstance(t, str):
            parts.append(t)
        else:
            parts.append(" ".join(map(str, t)))
    return " ".join(parts)

def chunks_of(text):
    words = text.split()
    out = []
    for i in range(0, min(len(words), CHUNK_WORDS * MAX_CHUNKS), CHUNK_WORDS):
        out.append(" ".join(words[i:i + CHUNK_WORDS]))
    return out or [""]

def rrf_fuse(rank_a, rank_b):
    """rank_a/rank_b: list of session ids in rank order. Returns fused rank order."""
    score = {}
    for r, sid in enumerate(rank_a):
        score[sid] = score.get(sid, 0.0) + 1.0 / (RRF_K + r + 1)
    for r, sid in enumerate(rank_b):
        score[sid] = score.get(sid, 0.0) + 1.0 / (RRF_K + r + 1)
    return [sid for sid, _ in sorted(score.items(), key=lambda kv: -kv[1])]

def main():
    t0 = time.time()
    rows = json.load(open(DATA))
    print(f"loaded {len(rows)} questions ({time.time()-t0:.1f}s)")

    # ---------- arm D: determinism ----------
    model = TextEmbedding(model_name=MODEL)
    e1 = list(model.embed(["The user would prefer responses about stand-up comedy."]))[0]
    e2 = list(model.embed(["The user would prefer responses about stand-up comedy."]))[0]
    det = bool(np.array_equal(e1, e2))
    print(f"model={MODEL} dim={len(e1)} deterministic={det}")

    # ---------- unique-session chunk cache ----------
    texts, keys = [], []
    seen = {}
    for r in rows:
        for sid, txt in zip(r["sess_ids"], r["sess_texts"]):
            if sid not in seen:
                seen[sid] = len(texts)
                for c in chunks_of(as_text(txt)):
                    texts.append(c); keys.append(sid)
    print(f"unique sessions={len(seen)} total chunks={len(texts)} ({time.time()-t0:.1f}s)")

    t1 = time.time()
    vecs = np.asarray([v for v in model.embed(texts, batch_size=16)], dtype=np.float32)
    print(f"embedded {len(texts)} chunks in {time.time()-t1:.1f}s ({len(texts)/(time.time()-t1):.1f}/s)")
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    sid_to_rows = {}
    for i, sid in enumerate(keys):
        sid_to_rows.setdefault(sid, []).append(i)

    qtexts = [r["question"] for r in rows]
    qvecs = np.asarray([v for v in model.embed(qtexts, batch_size=16)], dtype=np.float32)
    qvecs /= np.linalg.norm(qvecs, axis=1, keepdims=True) + 1e-12

    # ---------- evaluate ----------
    res = {}
    for r, qv in zip(rows, qvecs):
        qt = toks(r["question"])
        sess_ids, sess_texts = r["sess_ids"], r["sess_texts"]
        # L: lexical token overlap
        lex_scores, emb_scores = [], []
        for sid, txt in zip(sess_ids, sess_texts):
            rowsix = sid_to_rows[sid]
            st = toks(as_text(txt))
            lex_scores.append((len(qt & st), sid))
            sim = float(np.max(vecs[rowsix] @ qv))
            emb_scores.append((sim, sid))
        rank_l = [sid for _, sid in sorted(lex_scores, key=lambda x: (-x[0], x[1]))]
        rank_e = [sid for _, sid in sorted(emb_scores, key=lambda x: (-x[0], x[1]))]
        rank_h = rrf_fuse(rank_l, rank_e)
        gold = set(r["ans_ids"])
        res[r["qid"]] = {
            "qtype": r["qtype"],
            "L": (1 if gold & set(rank_l[:1]) else 0, 1 if gold & set(rank_l[:5]) else 0),
            "E": (1 if gold & set(rank_e[:1]) else 0, 1 if gold & set(rank_e[:5]) else 0),
            "H": (1 if gold & set(rank_h[:1]) else 0, 1 if gold & set(rank_h[:5]) else 0),
        }

    # ---------- report ----------
    print(f"\n{'category':<28}{'arm':<5}{'hit@1':>7}{'hit@5':>7}   n")
    for cat in ("single-session-preference", "single-session-assistant"):
        sub = [v for v in res.values() if v["qtype"] == cat]
        for arm in "LEH":
            h1 = sum(v[arm][0] for v in sub); h5 = sum(v[arm][1] for v in sub)
            name = {"L": "lex", "E": "emb", "H": "hyb"}[arm]
            print(f"{cat:<28}{name:<5}{h1:>5}/{len(sub)}{h5:>5}/{len(sub)}")
    allr = list(res.values())
    for arm in "LEH":
        h1 = sum(v[arm][0] for v in allr); h5 = sum(v[arm][1] for v in allr)
        name = {"L": "lex", "E": "emb", "H": "hyb"}[arm]
        print(f"{'ALL-86':<28}{name:<5}{h1:>5}/{len(allr)}{h5:>5}/{len(allr)}")
    print(f"\ndeterministic={det} total={time.time()-t0:.1f}s")

    json.dump({"deterministic": det, "res": res},
              open("/tmp/c497/embed86_results.json", "w"), indent=1)

if __name__ == "__main__":
    main()
