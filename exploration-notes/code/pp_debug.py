#!/usr/bin/env python3
"""Debug: show which anchors the prototype picks, per question."""
import json
import sys
sys.path.insert(0, ".")
from pp_duration_proto import (parse_dt, dur_exprs, kws, overlap, AGO_RE,
                               BEFORE_JOB_RE)

DATA = "/tmp/lme_s.json"

for qid in sys.argv[1:]:
    data = json.load(open(DATA))
    q = next(x for x in data if x["question_id"] == qid)
    question = q["question"]
    print("=" * 80)
    print("Q:", question)
    print("before-job match:", BEFORE_JOB_RE.search(question))
    if re.search(r"\bwhen\b", question, re.I) if (re := __import__("re")) else None:
        state_clause, event_clause = question.split(" when ", 1) if " when " in question else question.split(" When ", 1)
    else:
        state_clause, event_clause = question.split(" before ", 1)
    import re as _re
    state_clause = _re.sub(r"^\s*how long\s+(had|have)\s+(i\s+)?(been\s+)?",
                           "", state_clause, flags=_re.I)
    sk, ek = kws(state_clause), kws(event_clause)
    print("state kws:", sk, "| event kws:", ek)
    best_state = best_event = None
    for sdate, sess in zip(q["haystack_dates"], q["haystack_sessions"]):
        try:
            dt = parse_dt(sdate)
        except Exception:
            continue
        for turn in sess:
            if turn.get("role") != "user":
                continue
            line = turn["content"]
            for kind, n, u, raw in dur_exprs(line):
                anchor = dt - __import__("datetime").timedelta(
                    days=n * {"year": 365.25, "month": 30.44, "week": 7,
                              "day": 1}[u])
                s_ov, e_ov = overlap(sk, line), overlap(ek, line)
                if s_ov > 0 and (best_state is None or s_ov > best_state[0]):
                    best_state = (s_ov, str(anchor)[:10], raw,
                                  line[:100].replace("\n", " "))
                if e_ov > 0 and (best_event is None or e_ov > best_event[0]):
                    best_event = (e_ov, str(anchor)[:10], raw,
                                  line[:100].replace("\n", " "))
    print("STATE:", best_state)
    print("EVENT:", best_event)
    if best_state and best_event:
        print("days:", abs((__import__("datetime").date.fromisoformat(
            best_event[1]) - __import__("datetime").date.fromisoformat(
            best_state[1])).days))
