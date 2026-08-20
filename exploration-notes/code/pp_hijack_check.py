#!/usr/bin/env python3
"""Hijack-safety check: among all 'how long' questions in full-500, which
match the PP form classifier, and how many of those does the CURRENT
pipeline (C481 reference) already answer correctly?
A new route is zero-cost iff form-matched ∩ currently-correct = 0
(or the route defers when it cannot parse both anchors)."""
import json
import re

DATA = "/tmp/lme_s.json"
REF = "/tmp/c481/lme_s_full500_c481.json"

data = json.load(open(DATA))
by_qid = {q["question_id"]: q for q in data}

hl = [q for q in data if re.match(r"\s*how long\b", q["question"], re.I)]
pp = [q for q in hl if re.match(r"\s*how long\s+(had|have)\b", q["question"],
                                re.I)
      and re.search(r"\b(when|before)\b", q["question"], re.I)]
other_hl = [q for q in hl if q not in pp]
print(f"'how long' questions: {len(hl)} | PP-form: {len(pp)} | "
      f"other: {len(other_hl)}")

ref = json.load(open(REF))
# find results list structure
rows = ref if isinstance(ref, list) else ref.get("results", ref.get("rows"))
if isinstance(rows, dict):
    rows = list(rows.values())
print("ref rows:", len(rows), "| sample keys:", list(rows[0].keys())[:10])

# map qid -> correct?
ref_by_qid = {}
for r in rows:
    qid = r.get("qid") or r.get("question_id")
    ref_by_qid[str(qid)] = r

print("\n== PP-form vs reference ==")
for q in pp:
    r = ref_by_qid.get(q["question_id"], {})
    print(f"  {q['question_id']}: exact={r.get('exact', r.get('correct', '?'))}"
          f" pred={str(r.get('pred', r.get('prediction')))[:60]!r}")

print("\n== other 'how long' (hijack check for loose classifiers) ==")
for q in other_hl:
    print(f"  [{q['question_id']}] {q['question'][:110]}")
