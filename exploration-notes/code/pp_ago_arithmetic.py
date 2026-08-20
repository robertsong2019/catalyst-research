#!/usr/bin/env python3
"""Verify the cross-session 'ago' arithmetic hypothesis for past-perfect
duration questions. For each of the 7 questions:
  1. Extract ALL duration/ago expressions + their containing session dates.
  2. Extract event-clause mentions (the 'when Y' event) + their 'ago' lines.
  3. Compute absolute dates and E - S, compare to GT.
"""
import json
import re
from datetime import datetime, timedelta

DATA = "/tmp/lme_s.json"

AGO_RE = re.compile(
    r"\b(?:about\s+|around\s+|over\s+|almost\s+|just\s+)?"
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    r"\s*(?:\+|-)?\s*(years?|months?|weeks?|days?|hours?|minutes?)\s+ago\b",
    re.I)
LAST_RE = re.compile(r"\blast\s+(month|week|year|weekend)\b", re.I)
NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
UNIT_D = {"year": 365, "month": 30, "week": 7, "day": 1,
          "hour": 1/24, "minute": 1/1440}

def parse_dt(s):
    return datetime.strptime(s[:21], "%Y/%m/%d (%a) %H:%M")

def ago_to_days(m):
    n = int(m.group(1)) if m.group(1).isdigit() else NUMW.get(m.group(1).lower(), None)
    if n is None:
        return None
    unit = m.group(2).lower().rstrip("s")
    return n * UNIT_D[unit]

def last_to_days(word):
    return {"month": 30, "week": 7, "year": 365, "weekend": 7}.get(word, None)

def scan(q):
    """All (session_date, line) containing ago/last-month expressions."""
    out = []
    for sdate, sess in zip(q["haystack_dates"], q["haystack_sessions"]):
        try:
            dt = parse_dt(sdate)
        except Exception:
            continue
        for turn in sess:
            if turn.get("role") != "user":
                continue
            line = turn["content"]
            for m in AGO_RE.finditer(line):
                d = ago_to_days(m)
                if d:
                    out.append((dt, d, m.group(0), line[max(0, m.start()-120):m.end()+120]))
            for m in LAST_RE.finditer(line):
                d = last_to_days(m.group(1).lower())
                if d:
                    out.append((dt, d, "last " + m.group(1), line[max(0, m.start()-120):m.end()+120]))
    return out

def main():
    data = json.load(open(DATA))
    pop = [q for q in data
           if re.match(r"\s*how long\s+(had|have)\b", q["question"], re.I)
           and re.search(r"\b(when|before)\b", q["question"], re.I)]
    for q in pop:
        print("=" * 86)
        print("Q:", q["question"])
        print("GT:", q["answer"][:120])
        hits = scan(q)
        for dt, d, expr, ctx in hits:
            abs_date = dt - timedelta(days=d)
            print(f"  [{dt:%m-%d %H:%M}] '{expr}' -> abs~{abs_date:%m-%d}")
            print(f"      ...{ctx.replace(chr(10), ' ')[:200]}")
    print("\nNote: for GT verification, locate state lines vs event lines manually.")

if __name__ == "__main__":
    main()
