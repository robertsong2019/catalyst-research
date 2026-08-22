#!/usr/bin/env python3
"""Research #083 arm S: static embeddings (model2vec potion-retrieval-32M).

Same protocol as embed_sidechannel_proto.py (86q, chunk-max, hit@1/@5) but with a
static embedding model: pure lookup + mean-pool, no neural forward pass.
Purpose: quantify the quality-vs-speed tradeoff of the amg side-channel options.
"""
import json, time
import numpy as np
from model2vec import StaticModel

DATA = "/tmp/c497/embed86.json"
from embed_sidechannel_proto import as_text, chunks_of, toks, rrf_fuse  # reuse

def main():
    t0 = time.time()
    rows = json.load(open(DATA))
    model = StaticModel.from_pretrained("minishlab/potion-retrieval-32M")
    dim = model.embedding.shape[1]
    print(f"model=potion-retrieval-32M dim={dim} ({time.time()-t0:.1f}s)")

    texts, keys = [], []
    seen = {}
    for r in rows:
        for sid, txt in zip(r["sess_ids"], r["sess_texts"]):
            if sid not in seen:
                seen[sid] = len(texts)
                for c in chunks_of(as_text(txt)):
                    texts.append(c); keys.append(sid)
    t1 = time.time()
    vecs = model.encode(texts, normalize=True).astype(np.float32)
    print(f"static-embedded {len(texts)} chunks in {time.time()-t1:.2f}s ({len(texts)/(time.time()-t1):.0f}/s)")
    sid_to_rows = {}
    for i, sid in enumerate(keys):
        sid_to_rows.setdefault(sid, []).append(i)
    qvecs = model.encode([r["question"] for r in rows], normalize=True).astype(np.float32)

    res = {}
    for r, qv in zip(rows, qvecs):
        qt = toks(r["question"])
        lex_scores, emb_scores = [], []
        for sid, txt in zip(r["sess_ids"], r["sess_texts"]):
            lex_scores.append((len(qt & toks(as_text(txt))), sid))
            sim = float(np.max(vecs[sid_to_rows[sid]] @ qv))
            emb_scores.append((sim, sid))
        rank_l = [sid for _, sid in sorted(lex_scores, key=lambda x: (-x[0], x[1]))]
        rank_e = [sid for _, sid in sorted(emb_scores, key=lambda x: (-x[0], x[1]))]
        rank_h = rrf_fuse(rank_l, rank_e)
        gold = set(r["ans_ids"])
        res[r["qid"]] = {"qtype": r["qtype"],
                         "S": (1 if gold & set(rank_e[:1]) else 0, 1 if gold & set(rank_e[:5]) else 0),
                         "H": (1 if gold & set(rank_h[:1]) else 0, 1 if gold & set(rank_h[:5]) else 0)}

    print(f"\n{'category':<28}{'arm':<5}{'hit@1':>7}{'hit@5':>7}")
    for cat in ("single-session-preference", "single-session-assistant"):
        sub = [v for v in res.values() if v["qtype"] == cat]
        for arm in "SH":
            h1 = sum(v[arm][0] for v in sub); h5 = sum(v[arm][1] for v in sub)
            name = {"S": "stat", "H": "hyb"}[arm]
            print(f"{cat:<28}{name:<5}{h1:>5}/{len(sub)}{h5:>5}/{len(sub)}")
    json.dump(res, open("/tmp/c497/embed86_static_results.json", "w"), indent=1)
    print(f"total={time.time()-t0:.1f}s")

if __name__ == "__main__":
    main()
