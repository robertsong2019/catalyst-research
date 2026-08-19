"""Research #074 v5: distinctive-hit-squared scoring, full ssa-56 A/B.

v4 probe lessons:
  - IDF sum still loses to accumulated mid-frequency hits (table
    header)  -> square the weights: rare hits dominate
  - two v4 "wrong" answers were exact-judge artifacts (has/had tense,
    appositive rewording) — mechanism found the right sentence
  - 'Yes, here are...' preamble slipped the lead regex            -> add

v5 = w(kw)^2 with w = 1 + log(N/df) over the assistant-sentence pool,
require >=1 distinctive hit (df <= 8) and raw >= 3, preamble x0.25,
'?' filter, first-max tie-break (v2 lesson: list position is a prior).
"""
import json, math, re, sys
sys.path.insert(0, '/root/.openclaw/workspace/projects/agent-memory-graph')
import amg_bench_quality as B
from amg_bench_quality import run_eval

_PREAMBLE_RE = re.compile(
    r"^(?:sure|absolutely|of course|certainly|yes,?\s*(?:here|of course|sure)|"
    r"great (?:idea|question|news)|"
    r"i(?:'d| would| will) (?:be happy|love|be delighted) to|"
    r"i can help|i'?m happy to|here (?:are|is)|let me know if|"
    r"hope (?:this|that) helps|happy to (?:help|provide|share|suggest)|"
    r"would you like me to)", re.I)


def answer_speaker_recall_v5(question, nodes, min_score=5,
                             distinctive_df=8, floor=10.0):
    # harness passes min_score (v1 raw-hit floor); v5 deliberately uses
    # a lower raw floor (3) + weighted domain floor instead — the v3
    # zero-flip lesson: preamble parasitism is FLOOR-level, answer
    # sentences with distinctive-but-few hits never clear raw>=5.
    min_raw = 3
    kws = B._keywords(question)
    sents = []
    for nid, node in (nodes or {}).items():
        if node.get("role") != "assistant":
            continue
        for sent in B._split_sentences(node.get("label", "")):
            sents.append((sent.strip(), node.get("session_id")))
    if not sents:
        return None, {"reason": "no pool"}
    N = len(sents)
    df = {kw: sum(1 for s, _ in sents if B._keyword_hits(s, [kw]))
          for kw in kws}
    w = {kw: (1.0 + math.log(N / d) if d else 0.0) for kw, d in df.items()}
    best = None
    for s, sid in sents:
        if s.endswith("?"):
            continue
        matched = [kw for kw in kws
                   if w[kw] and B._keyword_hits(s, [kw])]
        raw = len(matched)
        if raw < min_raw:
            continue
        if min(df[kw] for kw in matched) > distinctive_df:
            continue          # no distinctive hit -> not an answer row
        score = sum(w[kw] ** 2 for kw in matched)
        if _PREAMBLE_RE.match(s):
            score *= 0.25
        if best is None or score > best[0]:
            best = (score, s, sid, raw)
    detail = {"version": 5, "pool": N,
              "df": {k: df[k] for k in df if df[k]},
              "best_score": round(best[0], 1) if best else 0}
    if best is None or best[0] < floor:
        return None, detail
    return best[1], detail


def main():
    data = json.load(open('/tmp/c473/ssa56.json'))
    orig = B.answer_speaker_recall
    B.answer_speaker_recall = answer_speaker_recall_v5
    try:
        rep = run_eval(data, judge_mode="exact")
    finally:
        B.answer_speaker_recall = orig
    json.dump(rep, open('/tmp/c473/ssa56_v5.json', 'w'), indent=1)

    base = {r['question_id']: r for r in
            json.load(open('/tmp/c473/ssa56_official.json'))['results']}
    v5 = rep['results']
    c0 = sum(1 for r in v5 if base[r['question_id']]['correct'])
    c1 = sum(1 for r in v5 if r['correct'])
    rescued = [r['question_id'][:8] for r in v5
               if r['correct'] and not base[r['question_id']]['correct']]
    lost = [r['question_id'][:8] for r in v5
            if not r['correct'] and base[r['question_id']]['correct']]
    cat = rep['categories']['single_session_assistant']
    print(f"baseline exact {c0}/56 = {c0/56:.3f}")
    print(f"v5       exact {c1}/56 = {c1/56:.3f}")
    print(f"rescued {len(rescued)}: {rescued}")
    print(f"lost    {len(lost)}: {lost}")
    print(f"evhit {cat['answer_session_hit_rate']}  "
          f"abstain {cat['abstention_rate']}")
    json.dump({"rescued": rescued, "lost": lost},
              open('/tmp/c473/ssa56_v5_flips.json', 'w'))


if __name__ == '__main__':
    main()
