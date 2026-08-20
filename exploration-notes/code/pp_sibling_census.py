#!/usr/bin/env python3
"""Census of the 18 non-PP 'how long' questions: current correctness +
evidence sufficiency (is GT a verbatim 'for N now'/'N ago' expression?)."""
import json
import re
import sys
sys.path.insert(0, ".")
from pp_duration_proto import NUMW, AGO_RE, NOW_RE, LAST_RE

DATA = "/tmp/lme_s.json"
REF = "/tmp/c481/lme_s_full500_c481.json"

data = json.load(open(DATA))
ref = json.load(open(REF))
rows = ref if isinstance(ref, list) else ref.get("results", [])
ref_by_qid = {r["question_id"]: r for r in rows}

hl = [q for q in data if re.match(r"\s*how long\b", q["question"], re.I)]
pp = [q for q in hl if re.match(r"\s*how long\s+(had|have)\b",
                                q["question"], re.I)
      and re.search(r"\b(when|before)\b", q["question"], re.I)]
other = [q for q in hl if q not in pp]

def norm_gt(g):
    g = g.lower()
    words = {v: str(k) for k, v in NUMW.items() if isinstance(k, int) and k > 1}
    out = []
    for tok in re.findall(r"\d+|[a-z]+", g):
        out.append(words.get(tok, tok))
    return " ".join(out)

for q in other:
    r = ref_by_qid[q["question_id"]]
    gt = str(r["ground_truth"])
    # search haystack for a duration expr matching GT numerically
    found = []
    want = norm_gt(gt)
    for sess in q["haystack_sessions"]:
        for turn in sess:
            if turn.get("role") != "user":
                continue
            for m in list(AGO_RE.finditer(turn["content"])) + \
                    list(NOW_RE.finditer(turn["content"])) + \
                    list(LAST_RE.finditer(turn["content"])):
                n = m.group(1).lower()
                n = str(int(n)) if n.isdigit() else str(NUMW.get(n, "?"))
                u = re.search(r"year|month|week|day|hour|minute",
                               m.group(0)).group(0)
                if n in want and u.rstrip("s") in want:
                    found.append(m.group(0))
    status = "OK " if r["correct"] else "WR "
    print(f"[{status}] {q['question_id']:20s} correct={r['correct']} "
          f"gt={gt[:38]!r} verbatim_expr={'YES: ' + found[0] if found else 'no'}")
    print(f"       {q['question'][:100]}")
