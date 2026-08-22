#!/usr/bin/env python3
"""Extract compact subset for embedding side-channel prototype (Research #083).

Targets: single-session-preference (30) + single-session-assistant (56) = 86 questions.
Output: /tmp/c497/embed86.json — small enough to load alongside an embedding model
on a 1GB-RAM box (the 277MB raw JSON cannot co-reside with onnxruntime).
"""
import json, gc, sys

DATA = sys.argv[1] if len(sys.argv) > 1 else "/tmp/lme_s.json"
OUT = "/tmp/c497/embed86.json"
TARGETS = {"single-session-preference", "single-session-assistant"}

with open(DATA) as f:
    data = json.load(f)

rows = []
for q in data:
    if q["question_type"] not in TARGETS:
        continue
    rows.append({
        "qid": q["question_id"],
        "qtype": q["question_type"],
        "question": q["question"],
        "answer": q["answer"],
        "ans_ids": q["answer_session_ids"],
        "sess_ids": q["haystack_session_ids"],
        "sess_texts": q["haystack_sessions"],
    })
del data
gc.collect()

uniq = set()
for r in rows:
    uniq.update(r["sess_ids"])

with open(OUT, "w") as f:
    json.dump(rows, f)

from collections import Counter
print(f"questions: {len(rows)} {dict(Counter(r['qtype'] for r in rows))}")
print(f"unique sessions across targets: {len(uniq)}")
print(f"avg sessions/question: {sum(len(r['sess_ids']) for r in rows)/len(rows):.1f}")
