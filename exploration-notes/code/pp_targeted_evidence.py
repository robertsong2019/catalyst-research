#!/usr/bin/env python3
"""Targeted full-line evidence extraction for the 4 unresolved pp-questions."""
import json
import re

DATA = "/tmp/lme_s.json"

TARGETS = [
    ("gpt4_93159ced", ["novatech", "working professionally", "before nova",
                       "started.*job", "4 years", "9 years"]),
    ("cc6d1ec1", ["bird"]),
    ("993da5e2", ["rug"]),
    ("b29f3365", ["guitar lesson"]),
]

def main():
    data = json.load(open(DATA))
    for qid, keys in TARGETS:
        q = next(x for x in data if x["question_id"] == qid)
        print("=" * 86)
        print("Q:", q["question"], "| GT:", q["answer"][:90])
        for sdate, sid, sess in zip(q["haystack_dates"],
                                    q["haystack_session_ids"],
                                    q["haystack_sessions"]):
            for turn in sess:
                if turn.get("role") != "user":
                    continue
                low = turn["content"].lower()
                if any(re.search(k, low) for k in keys):
                    print(f"--- [{sdate} | {sid}]")
                    print(turn["content"][:600].replace("\n", " "))
        print()

if __name__ == "__main__":
    main()
