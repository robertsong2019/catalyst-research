#!/usr/bin/env python3
"""Prototype: past-perfect duration answers via absolute-date anchoring.

Mechanism (validated by forensics on 7/7 questions):
  PP-form: "How long had I been <STATE> when/before <EVENT>?"
  1. Extract STATE keywords and EVENT keywords from the two clauses.
  2. Scan user lines for duration expressions:
       ago-type : "N units ago" | "a month ago" | "last month/week/year"
       now-type : "for N units (now)"  (present-perfect tenure)
     Each expression anchors to an ABSOLUTE date: sess_date - N.
  3. Route:
       a) "before I started my current job at <C>": tenure(now-type, mentions C)
          minus total(now-type, profession) -> compound y+m subtraction.
          If no tenure line for C -> ABSTAIN (company never joined).
       b) otherwise: event_abs - state_abs, rendered in dominant unit.
  Output canonical strings; judge = exact w/ normalization (+ day-range).

Run: python3 pp_duration_proto.py            # full 7-question A/B
"""
import json
import re
import sys
from datetime import datetime, timedelta

DATA = "/tmp/lme_s.json"

# ---------- duration expression parsing ----------
NUMW = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12}
UNIT_DAYS = {"year": 365.25, "month": 30.44, "week": 7, "day": 1,
             "hour": 1 / 24, "minute": 1 / 1440}

AGO_RE = re.compile(
    r"\b(?:about\s+|around\s+|over\s+|almost\s+|just\s+|recently\s+)?"
    r"(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    r"\s*(?:and\s+a\s+half\s*)?(years?|months?|weeks?|days?|hours?|minutes?)"
    r"\s+ago\b", re.I)
LAST_RE = re.compile(r"\blast\s+(month|week|year)\b", re.I)
NOW_RE = re.compile(
    r"\bfor\s+(?:about\s+|around\s+|over\s+|almost\s+|just\s+)?"
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    r"\s*(?:and\s+a\s+half\s*)?"
    r"(years?|months?|weeks?|days?|hours?|minutes?)\b(?:\s+now\b)?", re.I)


def num(n):
    return int(n) if n.isdigit() else NUMW.get(n.lower())


def unit_days(u):
    return UNIT_DAYS[u.lower().rstrip("s")]


def parse_dt(s):
    return datetime.strptime(s[:21], "%Y/%m/%d (%a) %H:%M")


def dur_exprs(line):
    """Yield (kind, n, unit, raw) for every duration expression in line."""
    for m in AGO_RE.finditer(line):
        n, u = num(m.group(1)), m.group(2)
        if n:
            yield ("ago", n, u.lower().rstrip("s"), m.group(0))
    for m in LAST_RE.finditer(line):
        u = m.group(1).lower()
        yield ("ago", 1, u if u != "weekend" else "week", m.group(0))
    for m in NOW_RE.finditer(line):
        n, u = num(m.group(1)), m.group(2)
        if n:
            yield ("now", n, u.lower().rstrip("s"), m.group(0))


# ---------- question decomposition ----------
STOP = {"how", "long", "had", "have", "been", "when", "before", "i", "my",
        "me", "the", "a", "an", "to", "of", "in", "at", "for", "on", "new",
        "regularly", "current", "job", "using", "using", "so", "far"}


def kws(clause):
    return [w for w in re.findall(r"[a-z]+", clause.lower())
            if w not in STOP and len(w) >= 3]


def overlap(kw_list, line):
    low = line.lower()
    return sum(1 for w in kw_list if w in low)


# ---------- answer rendering ----------
def render(days, hint_units):
    """Render day-count using the finest sensible unit from the anchors.
    Never rounds a nonzero duration to zero."""
    if days <= 0:
        return "0 days"
    if "week" in hint_units:
        w = days / 7
        r = round(w)
        if 0 < r and abs(w - r) <= 0.5:
            return f"{r} week" + ("s" if r != 1 else "")
    if "month" in hint_units:
        mo = days / 30.44
        r = round(mo)
        if 0 < r and abs(mo - r) <= 0.5:
            return f"{r} month" + ("s" if r != 1 else "")
    d = round(days)
    if "day" in hint_units or d > 0:
        return f"{d} day" + ("s" if d != 1 else "")
    return f"{round(days, 1)} days"


def ym_sub(total_m, part_m):
    """Compound y+m subtraction in months -> canonical string."""
    d = total_m - part_m
    return f"{d // 12} year{'s' if d // 12 != 1 else ''} and {d % 12} month" \
           + ("s" if d % 12 != 1 else "")


def tenure_months(line):
    """Parse 'for [about] N years [and M months] (now)' -> total months."""
    m = re.search(
        r"for\s+(?:about\s+|around\s+|over\s+|almost\s+)?"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"\s*(years?|months?)"
        r"(?:\s+and\s+(\d+|one|two|three|four|five|six|seven|eight|nine|"
        r"ten|eleven|twelve)\s*months?)?\s*(?:now\b)?",
        line, re.I)
    if not m:
        return None
    n = num(m.group(1))
    total = n * (12 if m.group(2).lower().startswith("year") else 1)
    if m.group(3):
        total += num(m.group(3))
    return total


# ---------- main mechanism ----------
BEFORE_JOB_RE = re.compile(
    r"before\s+I\s+started\s+my\s+current\s+job\s+at\s+"
    r"([A-Za-z0-9 .&'-]+?)\s*\??\s*$",
    re.I)


def answer_pp(q):
    question = q["question"]
    m = BEFORE_JOB_RE.search(question)
    if m:  # route (a): tenure subtraction
        company = m.group(1).strip().rstrip("?.")
        best_tenure, best_total = None, None
        for sdate, sess in zip(q["haystack_dates"], q["haystack_sessions"]):
            try:
                dt = parse_dt(sdate)
            except Exception:
                continue
            for turn in sess:
                if turn.get("role") != "user":
                    continue
                line = turn["content"]
                low = line.lower()
                if company.lower() in low:
                    tm = tenure_months(line)
                    if tm is not None and ("work" in low or "job" in low):
                        best_tenure = tm
                if "working professionally" in low or \
                        ("working" in low and "for" in low):
                    tm = tenure_months(line)
                    if tm is not None and company.lower() not in low:
                        best_total = tm
        if best_tenure is None:
            return "ABSTAIN: no tenure line for " + company
        if best_total is None or best_total < best_tenure:
            return "ABSTAIN: unparsable tenure/total"
        return ym_sub(best_total, best_tenure)

    # route (b): event_abs - state_abs
    if re.search(r"\bwhen\b", question, re.I):
        state_clause, event_clause = re.split(r"\bwhen\b", question, 1,
                                              flags=re.I)
    else:
        state_clause, event_clause = re.split(r"\bbefore\b", question, 1,
                                              flags=re.I)
    # drop leading "How long had I been"
    state_clause = re.sub(r"^\s*how long\s+(had|have)\s+(i\s+)?(been\s+)?",
                          "", state_clause, flags=re.I)
    sk, ek = kws(state_clause), kws(event_clause)
    best_state, best_event = None, None  # (abs_date, n, unit)
    scored = []  # (line_id, s_ov, e_ov, anchor, n, u)
    for si, (sdate, sess) in enumerate(zip(q["haystack_dates"],
                                           q["haystack_sessions"])):
        try:
            dt = parse_dt(sdate)
        except Exception:
            continue
        for ti, turn in enumerate(sess):
            if turn.get("role") != "user":
                continue
            line = turn["content"]
            for kind, n, u, raw in dur_exprs(line):
                anchor = dt - timedelta(days=n * unit_days(u))
                scored.append(((si, ti), overlap(sk, line), overlap(ek, line),
                               anchor, n, u))
    # phase 1: event anchor = max e_ov (tie: max s_ov distance, i.e. prefer
    # lines whose event-overlap dominates); require e_ov >= 2.
    ev_c = [x for x in scored if x[2] >= 2]
    if ev_c:
        best_event = max(ev_c, key=lambda x: (x[2], -x[1]))
    # phase 2: state anchor = max s_ov among lines OTHER than the event line
    # (cross-exclusion by line identity, not by overlap inequality).
    st_c = [x for x in scored if x[1] >= 2 and x[0] != (best_event[0]
                                                       if best_event else None)]
    if st_c:
        best_state = max(st_c, key=lambda x: (x[1], -x[2]))
    if not best_state or not best_event:
        return "ABSTAIN: missing " + ("state" if not best_state else "event") \
               + " anchor"
    s_anchor, e_anchor = best_state[3], best_event[3]
    s_u, e_u = best_state[5], best_event[5]
    days = abs((e_anchor - s_anchor).days)
    return render(days, [s_u, e_u])


# ---------- judging ----------
def norm(s):
    s = s.lower().strip()
    s = re.sub(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
               lambda m: str(num(m.group(0)) if not m.group(0).isdigit()
                             else int(m.group(0))), s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def judge(pred, gt):
    p, g = norm(pred), norm(gt)
    if "abstain" in p:
        return "not enough" in g.lower() or "haven't" in g.lower()
    if "not enough" in g.lower():
        return False
    # GT range: "Answers ranging from X to Y days are also acceptable"
    rng = re.search(r"ranging from (\d+) to (\d+) days", g)
    base = norm(re.split(r"Answers ranging", gt)[0])
    if rng:
        m = re.search(r"(\d+)", p)
        if m and int(rng.group(1)) <= int(m.group(1)) <= int(rng.group(2)):
            return True
    if p == base:
        return True
    # singular/plural + article tolerance
    ps = re.sub(r"\b(a|an|the)\b|s\b", "", p).split()
    bs = re.sub(r"\b(a|an|the)\b||s\b", "", base).split()
    return ps == bs


def main():
    data = json.load(open(DATA))
    pop = [q for q in data
           if re.match(r"\s*how long\s+(had|have)\b", q["question"], re.I)
           and re.search(r"\b(when|before)\b", q["question"], re.I)]
    ok = 0
    for q in pop:
        try:
            pred = answer_pp(q)
        except Exception as e:
            pred = f"ERROR: {e}"
        j = judge(pred, q["answer"])
        ok += j
        print(f"[{'PASS' if j else 'MISS'}] {q['question_id']}")
        print(f"   Q:   {q['question'][:100]}")
        print(f"   GT:  {q['answer'][:100]}")
        print(f"   PRED: {pred}")
    print(f"\n== {ok}/{len(pop)} correct (baseline: 0/{len(pop)})")
    json.dump([{"qid": q["question_id"], "pred": answer_pp(q)}
               for q in pop], open("/tmp/pp_proto_results.json", "w"), indent=1)


if __name__ == "__main__":
    main()
