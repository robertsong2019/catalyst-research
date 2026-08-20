#!/usr/bin/env python3
"""Forensics: past-perfect duration questions in LongMemEval_s.

Form: "How long had I been X when Y?" (duration-of-state at event time).
Goals:
  1. Population census over full-500 (not just missed ones).
  2. Evidence anatomy per question: verbatim-duration line vs date-arithmetic
     vs abstain-required (plan, not fact).
  3. Unit map of GT answers.
  4. Check whether evidence lines contain the state verb — i.e. is the
     retrievable anchor the STATE or the EVENT?
Usage: python3 pp_duration_forensics.py
"""
import json
import re
import sys
from collections import Counter

DATA = "/tmp/lme_s.json"

# form classifier: "how long had/have I been <state> when/before <event>"
PP_RE = re.compile(
    r"how long\s+(?:had|have)\s+(?:i|you|he|she|we|they)?\s*"
    r"(?:been\s+)?(.*?)(?:\s+(?:when|before)\s+(.*))?$",
    re.I | re.S,
)

NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "a": 1, "an": 1,
}


def gt_unit(ans: str):
    a = ans.lower()
    for u in ("year", "month", "week", "day", "hour", "minute"):
        if u in a:
            return u + ("s" if not a.endswith(u) else "")
    return "other/abstain"


def find_evidence(question, dates, sessions):
    """Scan haystack for lines mentioning the state noun/verb and a duration."""
    stop = {"how", "long", "had", "have", "been", "when", "before", "i", "my",
            "me", "the", "a", "an", "to", "of", "in", "at", "for", "on",
            "new", "regularly", "current", "job"}
    words = [w for w in re.findall(r"[a-z]+", question.lower())
             if w not in stop and len(w) > 3]
    hits = []
    for sdate, sess in zip(dates, sessions):
        for turn in sess:
            if turn.get("role") != "user":
                continue  # state facts live in user turns
            line = turn.get("content", "")
            low = line.lower()
            dur = re.search(
                r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
                r"eleven|twelve)\s*(?:\+|-)?\s*"
                r"(years?|months?|weeks?|days?|hours?|minutes?)\b", low)
            started = re.search(r"\b(started|began|joined|took up|got into|"
                                r"picked up|been)\b", low)
            key_hits = [w for w in words if w in low]
            if dur and len(key_hits) >= 1:
                hits.append((sdate, "DUR", key_hits, dur.group(0), line[:220]))
            elif started and len(key_hits) >= 2:
                hits.append((sdate, "START", key_hits, started.group(0), line[:220]))
    return hits


def main():
    data = json.load(open(DATA))
    pop = []
    for q in data:
        m = re.match(r"\s*how long\s+(had|have)\b", q["question"], re.I)
        if not m:
            continue
        if not re.search(r"\b(when|before)\b", q["question"], re.I):
            continue
        pop.append(q)

    print(f"== Population: {len(pop)} past-perfect duration questions "
          f"(of {len(data)})")
    units = Counter()
    for q in pop:
        ans = q["answer"]
        abstain = "not enough" in ans.lower() or "haven't" in ans.lower()
        units[gt_unit(ans)] += 1
        ev = find_evidence(q["question"], q["haystack_dates"],
                           q["haystack_sessions"])
        print("\n" + "=" * 78)
        print("QID:", q["question_id"], "| type:", q.get("question_type"))
        print("Q:", q["question"])
        print("GT:", ans[:130], "  [UNIT:", gt_unit(ans) + "]")
        print("q_date:", q.get("question_date"),
              "| ans_sessions:", q.get("answer_session_ids"))
        if not ev:
            print("  !! NO evidence found by scanner")
        for h in ev[:6]:
            print(f"  [{h[0]} {h[1]} kw={h[2][:4]} {h[3]}] {h[4]}")
    print("\n== GT unit distribution:", dict(units))
    # save machine-readable
    out = [{
        "qid": q["question_id"], "q": q["question"], "gt": q["answer"],
        "qdate": q.get("question_date"),
        "ans_sess": q.get("answer_session_ids"),
    } for q in pop]
    json.dump(out, open("/tmp/pp_pop.json", "w"), indent=1)
    print("saved /tmp/pp_pop.json")


if __name__ == "__main__":
    main()
