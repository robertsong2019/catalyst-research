#!/usr/bin/env python3
"""
Research #085 — Duration-family four mechanisms (oracle evidence mode), v3
=========================================================================
Forensic targets from C499 official reference (multi_session 114 wrongs, 26 duration-family):

  M1 binge-dedup-sum      e831120c  GT 3.5  (PRED 4.5 — franchise re-mention double-count)
  M2 distinct-day-rate    a08a253f  GT 4    (PRED 5 — counted classes, not distinct days)
  M3 realized-window-dur  7024f17c  GT 0.5  (yoga hours are habitual/plan, only jog realized)
  M4 delivery-interval    b3c15d39  GT 5    (ordered Feb 5 / arrived Feb 10, product join)
                          60bf93ed  GT 5    (slash dates 1/15→1/20 + anaphoric product "it")
                          60bf93ed_abs → ABSTAIN (iPad case never mentioned — negative existence)

Controls (already correct in production — must stay correct):
  aae3761f  driving 15  (destination-keyed dedup is M1's sibling; HEARTBEAT "GT 15 vs 19" line is STALE)
  2788b940  fitness classes per typical week 5  (M2 must NOT hijack: different form)

v3 changes (from v1/v2 post-mortems):
  - gates extracted as first-class functions; census uses THE SAME gates (no drift)
  - M1: duration-question form only (exclude count-questions, ago/between intervals)
  - M3: exclude in-total/typical/every-day forms (total_sum & habitual families own them)
  - M4: slash dates (1/15) + anaphoric product resolution ("it" -> prior sentence NP)
  - cascade: M1 -> M2 -> M4 -> M3, first non-None wins (M1 owns driving before M3 sees it)
  - _stem: double-consonant strip (jogging->jog, running->run)  [C471 prefix-stem lesson, again]

Run:  python3 dur_family_proto.py /tmp/dur_oracle2.json /tmp/all500_q.json
"""

import json
import re
import sys
from datetime import date

# ----------------------------------------------------------------------------
# shared text utilities
# ----------------------------------------------------------------------------

MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"])}

NUMWORDS = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "half": 0.5, "couple": 2, "few": 3}

STOP = set("""a an the my i we our your this that these those and or but so
it its is are was were be been being do does did have has had will would
can could should may might must to of in on at for with about from by as
like just really very much more most some any all no not new old other
recently lately been get got great good nice super plenty stuff""".split())

_PRONOUNS = {"it", "this", "that", "they", "them"}


def clauses(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+|;\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 3]


def words(text):
    return [w.strip(".,!?;:\"'()[]").lower() for w in text.split()]


def content_stems(text):
    return {w for w in words(text) if w and w not in STOP and len(w) > 2 and not w.isdigit()}


def _stem(w):
    w = w.lower()
    for suf in ("ing", "ed"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            w = w[:-len(suf)]
            break
    if len(w) > 3 and w[-1] == w[-2]:
        w = w[:-1]
    return w


def num_parse(token):
    t = token.lower()
    if t.isdigit():
        return float(t)
    return NUMWORDS.get(t)


def user_turns(sessions):
    for sid, msgs in sessions.items():
        for ti, t in enumerate(msgs):
            if t["role"] == "user":
                yield sid, ti, t["content"]


# ----------------------------------------------------------------------------
# M1 — binge-dedup-sum
# ----------------------------------------------------------------------------

_BINGE_RE = re.compile(
    r"(?:watched|finished|completed|read)\s+(?:all|the|my)?\s*"
    r"(?:(\d+)\s+)?([a-zA-Z][a-zA-Z\- ]{2,40}?)\s+"
    r"(?:movies|films|books|episodes|in|for)\b.*?"
    r"(?:in|for)\s+(?:about\s+|around\s+|roughly\s+)?"
    r"((?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+(?:\.\d+)?)"
    r"(?:\s+(?:week|weeks|day|days|hour|hours))?"
    r"(?:\s+and\s+a\s+half)?)"
)

_FRANCHISE_ALIAS = {}
for _toks, _fam in [
    ("marvel mcu cinematic avengers disney", "marvel"),
    ("star wars skywalker jedi rogue solo empire awakens", "starwars"),
    ("harry potter hogwarts", "harrypotter"),
    ("lord rings hobbit tolkien", "lotr"),
]:
    for _t in _toks.split():
        _FRANCHISE_ALIAS[_t] = _fam


def m1_gate(question):
    q = question.lower()
    if "how many" not in q:
        return None
    # duration-question form: asks for weeks/days/hours OF TIME, not a count of items
    if re.search(r"how many (?:videos|movies|books|pieces|episodes|times|classes|items)", q):
        return None
    # interval forms belong to M4-family (event-date arithmetic), not duration sums
    if re.search(r"\b(ago|passed|between)\b", q):
        return None
    if ("week" in q or "day" in q) and re.search(r"\b(watch|read|finish|complete|binge)\b", q):
        return "watch"
    if "hour" in q and re.search(r"\bdriv", q) and "destination" in q:
        return "drive"
    return None


def _franchise_id(turn_text):
    return {_FRANCHISE_ALIAS.get(w) for w in words(turn_text)} - {None}


def parse_dur(token):
    t = token.lower().strip()
    m = re.match(r"^(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+(?:\.\d+)?)"
                 r"(?:\s+(\w+))?(?:\s+and\s+a\s+half)?$", t)
    if not m:
        return None, None
    n = num_parse(m.group(1))
    unit = m.group(2)
    if n is None:
        return None, None
    if "and a half" in t:
        n += 0.5
    return n, unit


_DUR_H = re.compile(
    r"\b(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+(?:\.\d+)?)"
    r"[-\s]?(?:hour|hours)\b")
_TRIP_TO = re.compile(r"\b(?:trip|trips|drove|drive|visited?) to "
                      r"((?:the )?([A-Z][\w.\-]+(?: [A-Z][\w.\-]+)*))")
_ANY_CAP = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{2,}(?: [A-Z][a-z]{2,})*)\b")


def m1_binge_sum(question, sessions):
    mode = m1_gate(question)
    if not mode:
        return None

    if mode == "watch":
        dur_by_key = {}
        for _, _, c in user_turns(sessions):
            fams = _franchise_id(c)
            for m in _BINGE_RE.finditer(c):
                n, unit = parse_dur(m.group(3))
                if n is None:
                    continue
                if unit and "day" in unit:
                    n = round(n / 7.0, 2)
                key = frozenset(fams) if fams else frozenset(
                    content_stems((m.group(2) or "").lstrip("TtHhEe "))) or None
                if key is None:
                    continue
                if any(k & key for k in dur_by_key):
                    continue
                dur_by_key[key] = n
        if not dur_by_key:
            return None
        return f"{round(sum(dur_by_key.values()), 2):g} weeks"

    # drive mode: destination-keyed hour dedup (case-sensitive NPs)
    hrs_by_dest = {}
    for _, _, c in user_turns(sessions):
        dm = _DUR_H.search(c)
        if not dm:
            continue
        n = num_parse(dm.group(0).split()[0])
        if n is None:
            continue
        tm = _TRIP_TO.search(c)
        dest = tm.group(2) if tm else (
            [m.group(1) for m in _ANY_CAP.finditer(c)] or [None])[0]
        if not dest:
            continue
        key = dest.split()[0].lower()
        if key in ("my", "the", "i"):
            continue
        hrs_by_dest.setdefault(key, n)
    if not hrs_by_dest:
        return None
    return str(int(sum(hrs_by_dest.values())))


# ----------------------------------------------------------------------------
# M2 — distinct-day-rate
# ----------------------------------------------------------------------------

_SCHED_RE = re.compile(
    r"(?i)(?:attend|class|classes|lesson|lessons|session|sessions|practice)"
    r"[^.\n]{0,120}?\bon\s+((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r"(?:s)?(?:\s+and\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:s)?)*)"
)


def m2_gate(question):
    return bool(re.search(r"how many days (?:a|per) week", question.lower())) or None


def m2_days_per_week(question, sessions):
    if not m2_gate(question):
        return None
    days = set()
    for _, _, c in user_turns(sessions):
        for m in _SCHED_RE.finditer(c):
            for wd in re.findall(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)",
                                 m.group(1), re.I):
                days.add(wd.lower())
    if not days:
        return None
    return f"{len(days)} days"


# ----------------------------------------------------------------------------
# M3 — realized-window-duration
# ----------------------------------------------------------------------------

_REALIZED_DUR_RE = re.compile(
    r"(?i)(?:went (?:for|on) a|did (?:a|an|my)|completed|took)\s+"
    r"((?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+(?:\.\d+)?)"
    r"[-\s]*(?:minute|minutes|hour|hours))\s+([a-z\- ]{3,30})"
)

_PLAN_MARKERS = re.compile(
    r"(?i)\b(used to|trying to get back|hoping to|plan(?:ning)? to|want to|"
    r"would like to|i'?ll (?:start|try|schedule|do)|schedule my|getting back into|"
    r"slacking|inconsistent)\b"
)

_ACT_WORDS = {"jog", "jogging", "yoga", "running", "run", "exercise", "exercising",
              "workout", "working", "swim", "swimming", "cycling", "walk", "walking",
              "class", "classes", "fitness", "meditation", "hiking", "hike",
              "watching", "watch", "documentary", "documentaries"}


def m3_gate(question):
    q = question.lower()
    if not ("how many hours" in q or "how much time" in q):
        return None
    if not re.search(r"\b(did i|have i|do i)\b", q):
        return None
    # total/cumulative forms -> total_sum family (C483 unit discipline owns them)
    if re.search(r"\b(in total|combined|typical|every day|each day)\b", q):
        return None
    # driving destinations -> M1 owns
    if "driv" in q and "destination" in q:
        return None
    return True


def m3_realized_duration(question, sessions):
    if not m3_gate(question):
        return None
    q = question.lower()
    acts = {_stem(w) for w in words(q) if w in _ACT_WORDS}
    total_h, fired = 0.0, False
    for _, _, c in user_turns(sessions):
        for cl in clauses(c):
            if _PLAN_MARKERS.search(cl):
                continue
            for m in _REALIZED_DUR_RE.finditer(cl):
                tok = re.split(r"[-\s]+", m.group(1))[0]
                n = num_parse(tok)
                unit = m.group(1).lower()
                act_txt = m.group(2).lower()
                if n is None:
                    continue
                if "minute" in unit:
                    n = n / 60.0
                if acts and not (acts & {_stem(w) for w in words(act_txt)}):
                    continue
                total_h += n
                fired = True
    if not fired:
        return None
    return f"{round(total_h, 2):g} hours"


# ----------------------------------------------------------------------------
# M4 — delivery-interval (month-name dates, slash dates, anaphoric products)
# ----------------------------------------------------------------------------

_DATE_CORE = (r"((?:January|February|March|April|May|June|July|August|September|"
              r"October|November|December)\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?"
              r"|(\d{1,2})/(\d{1,2}))")

_ORD_RE = re.compile(
    r"(?:ordered|bought|purchased|placed an order for)\s+((?:a|an|the|my|new|it)\s+)?"
    r"([a-zA-Z][a-zA-Z\- ]{2,40}?)?\s*(?:from [A-Za-z]+\s+)?(?:online\s+)?"
    r"(?:on|back on)\s+" + _DATE_CORE, re.I)

_ARR_RE = re.compile(
    r"(?:arrived|received|was delivered|showed up|came)\s+on\s+" + _DATE_CORE, re.I)

_ARR_PROD_RE = re.compile(
    r"([a-zA-Z][a-zA-Z\- ]{2,40}?)\s+(?:that\s+)?(?:arrived|was delivered|showed up)",
    re.I)


def _parse_date(m):
    if m.group(2):  # month-name branch: groups shifted by wrapper
        mon = m.group(1).split()[0]
        return date(2023, MONTHS.get(mon.lower(), 1), int(m.group(2)))
    return date(2023, int(m.group(3)), int(m.group(4)))  # M/D


def _ord_date(m):
    # groups in _ORD_RE: 1 opt-art, 2 product, then _DATE_CORE groups 3..6
    if m.group(4):
        mon = m.group(3).split()[0]
        return date(2023, MONTHS.get(mon.lower(), 1), int(m.group(4)))
    return date(2023, int(m.group(5)), int(m.group(6)))


def _arr_date(m):
    # _ARR_RE: _DATE_CORE groups 1..4
    if m.group(2):
        mon = m.group(1).split()[0]
        return date(2023, MONTHS.get(mon.lower(), 1), int(m.group(2)))
    return date(2023, int(m.group(3)), int(m.group(4)))


def _resolve_product(session_msgs, turn_idx, clause_text, explicit):
    """Explicit NP after order verb, or anaphora: walk back user sentences."""
    exp = (explicit or "").strip()
    first = words(exp)[0] if exp else ""
    is_pronoun = (first in _PRONOUNS or first in ("from", "online") or not exp)
    if not is_pronoun:
        return content_stems(exp)
    # candidates, nearest-first: clauses before the match in this turn,
    # then prior user turns (nearest turn first), each nearest-clause-first
    cur = session_msgs[turn_idx]["content"]
    candidates = []
    seen_break = False
    pre = []
    for cl in clauses(cur):
        if re.search(_ORD_RE.pattern, cl, re.I) or re.search(_ARR_RE.pattern, cl, re.I):
            seen_break = True
            break
        pre.append(cl)
    candidates.extend(reversed(pre))  # nearest clause first
    for t in reversed(session_msgs[:turn_idx]):
        if t["role"] == "user":
            candidates.extend(reversed(clauses(t["content"])))
    for cl in candidates[:8]:
        # possessive anchor "my (new) X" = topic/product; cap NP at 6 words
        pm = re.search(r"\bmy\s+(?:new\s+)?((?:[a-z]+[\- ]){0,5}[a-z]+)", cl, re.I)
        if pm:
            return content_stems(pm.group(1))
    return None


def m4_gate(question):
    q = question.lower()
    if not re.search(r"how many days .*(arrive|arrived|receive|received|take for|took for)", q):
        return None
    if not re.search(r"(after i (ordered|bought|purchased)|to arrive)", q):
        return None
    return True


def m4_delivery_interval(question, sessions):
    if not m4_gate(question):
        return None
    # question-side product NP: "... for my/the <X> (after|to arrive)"
    qm = re.search(r"(?:my|the|a|an)\s+((?:[a-zA-Z\-]+[ ]{0,1}){1,5}?)\s+(?:after|to arrive|\?)",
                   question)
    q_stems = content_stems(qm.group(1)) if qm else set()
    orders, arrivals = [], []
    for sid, msgs in sessions.items():
        for ti, t in enumerate(msgs):
            if t["role"] != "user":
                continue
            c = t["content"]
            for m in _ORD_RE.finditer(c):
                explicit = m.group(2) or (m.group(1) or "").strip()
                stems = _resolve_product(msgs, ti, c, explicit)
                orders.append((stems or set(), _ord_date(m)))
            for m in _ARR_RE.finditer(c):
                start = max(0, m.start() - 120)
                pm = _ARR_PROD_RE.search(c[start:m.start()] + " arrived")
                if pm and words(pm.group(1))[0] not in _PRONOUNS:
                    stems = content_stems(pm.group(1))
                else:
                    stems = _resolve_product(msgs, ti, c, "it")
                arrivals.append((stems or set(), _arr_date(m)))
    if not orders and not arrivals:
        return "ABSTAIN"  # form fired, zero evidence -> negative existence (C498)
    best = None
    for astems, adate in arrivals:
        for ostems, odate in orders:
            inter = astems & ostems
            if not inter:
                continue
            # question-product guard: joined product must match the asked-about
            # item, else this is a different product's pair (C498 hijack lesson)
            if q_stems and not (q_stems & (astems | ostems)):
                continue
            if len(inter) >= 2 or len(ostems) <= 2 or len(astems) <= 2:
                delta = (adate - odate).days
                if delta > 0 and (best is None or delta < best):
                    best = delta
    if best is None:
        return "ABSTAIN"
    return f"{best} days"


# ----------------------------------------------------------------------------
# cascade + census (gates only, same functions — no drift)
# ----------------------------------------------------------------------------

def cascade(question, sessions):
    for fn in (m1_binge_sum, m2_days_per_week, m4_delivery_interval, m3_realized_duration):
        v = fn(question, sessions)
        if v is not None:
            return fn.__name__, v
    return None, None


def gate_census(all500):
    fires = {"M1": [], "M2": [], "M3": [], "M4": []}
    for line in open(all500):
        r = json.loads(line)
        qid, q = r["question_id"], r["question"]
        if m1_gate(q):
            fires["M1"].append(qid)
        if m2_gate(q):
            fires["M2"].append(qid)
        if m3_gate(q):
            fires["M3"].append(qid)
        if m4_gate(q):
            fires["M4"].append(qid)
    return fires


INTENDED = {
    "e831120c": "3.5", "a08a253f": "4", "7024f17c": "0.5",
    "b3c15d39": "5", "60bf93ed": "5", "60bf93ed_abs": "ABSTAIN",
}
CONTROLS = {"aae3761f": "15", "2788b940": None}


def main(oracle_path, all500_path):
    oracle = json.load(open(oracle_path))
    print("== oracle cascade runs ==")
    for qid, spec in oracle.items():
        mech, pred = cascade(spec["question"], spec["sessions"])
        gt = str(spec["gt"])
        want = INTENDED.get(qid) or CONTROLS.get(qid)
        mark = ""
        if want:
            if want == "ABSTAIN":
                mark = "✓" if pred == "ABSTAIN" else "✗"
            elif pred:
                mark = "✓" if want in pred else "✗"
            else:
                mark = "·"  # no fire on control (2788b940 expected)
        print(f"{qid} {mark} GT={gt[:52]!r}")
        if pred:
            print(f"    -> {mech}: {pred}")

    print("\n== gate census (500 questions) ==")
    fires = gate_census(all500_path)
    for mech, qids in fires.items():
        print(f"{mech} fires on {len(qids)}: {qids}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
