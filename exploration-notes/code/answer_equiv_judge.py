#!/usr/bin/env python3
"""answer_equiv_judge.py — Research #090: tiered answer-equivalence judge (zero-dependency).

Motivation: amg exact_judge 0.444 (C517) vs C519's answer-face paraphrase mismatch —
answers that are semantically right but surface-form different get scored 0 by exact
match, while naive looseness ("tennis" == "table tennis") creates false passes.

Literature grounding:
  - Bulian et al., EMNLP 2022 "Tomayto, Tomahto": answer equivalence is ASYMMETRIC —
    accept answers equivalent to OR IMPROVING OVER the reference; F1 has false
    graduality + is question-blind. BEM (BERT classifier) approximates human AE.
  - Li et al., EMNLP 2024 (PEDANTS): rule-based, question-type-conditioned judge can
    be more stable than EM/BERTScore — cheap and interpretable is a valid design point.
  - Ho Thi et al., GEM@ACL 2026 (2504.11972): LLM-judge correlates 0.85 w/ humans vs
    EM 0.22 / F1 0.40; STRONG on number answers, WEAK on complex entities; zero-shot
    context-free judging works best.

Design: three deterministic tiers between exact match and LLM judging.
  T0  exact          trivial strip equality
  T1  normalized     multiset equality after folding (case/punct/articles/number-words/
                     ordinals/currency/months/honorifics/acronyms)
  T2  typed          question-type-guarded asymmetric check:
                      number -> value+unit signatures (time units canonicalized to seconds)
                      date   -> parsed date tuples, intersection
                      entity -> content-token containment: cand ⊇ ref = IMPROVES,
                                cand ⊂ ref = PARTIAL, pronoun/relative-date guards -> NEEDS_JUDGE

Verdicts: EXACT / NORM_EQ / IMPROVES (credit) · PARTIAL / INCOMPATIBLE / NEEDS_JUDGE (no credit)
"""

from __future__ import annotations
import re
from collections import Counter

CREDIT = {"EXACT", "NORM_EQ", "IMPROVES"}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
MONTH_FOLD = {m + suffix: m for m in MONTHS for suffix in
              ["", "uary", "ruary", "ch", "il", "e", "y", "ust", "ember", "ober"]}
# manual overrides for irregular stems
MONTH_FOLD.update({"sept": "sep", "janu": "jan", "febr": "feb"})

ONES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
        "seventy": 70, "eighty": 80, "ninety": 90}
SCALES = {"hundred": 100, "thousand": 1_000}
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
            "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}

CURRENCY = {"usd": "usd", "eur": "eur", "gbp": "gbp", "cny": "cny",
            "dollar": "usd", "dollars": "usd", "euro": "eur", "euros": "eur",
            "pound": "gbp", "pounds": "gbp", "yen": "cny"}
TIME_UNITS = {"second": 1, "seconds": 1, "sec": 1, "s": 1,
              "minute": 60, "minutes": 60, "min": 60, "mins": 60,
              "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
              "day": 86400, "days": 86400,
              "week": 604800, "weeks": 604800}
DIST_UNITS = {"mile": "mi", "miles": "mi", "km": "km", "kilometer": "km",
              "kilometers": "km", "kilometre": "km", "kilometres": "km"}
OTHER_UNITS = {"gallon": "gal", "gallons": "gal", "liter": "l", "liters": "l",
               "litres": "l", "litre": "l", "kg": "kg", "pound_weight": "lb"}

HONORIFICS = {"dr": "doctor", "dr.": "doctor", "mr": "mister", "mr.": "mister",
              "mrs": "missus", "prof": "professor", "prof.": "professor"}
ACRONYMS = {"nyc": ["new", "york", "city"], "usa": ["united", "states"],
            "uk": ["united", "kingdom"]}

STOP = set("a an the of in on at to for with by from about as is are was were be been "
           "being do does did have has had it its this that these those there here "
           "and or but so if then than when where who what which how why did does "
           "her his their my your our she he they i we you me them us not no yes "
           "very just really much many more most some any".split())
PRONOUNS = {"she", "he", "they", "it", "her", "his", "their", "them", "herself",
            "himself", "hers", "theirs", "who", "whom"}
RELATIVE_TIME = {"yesterday", "today", "tomorrow", "tonight", "last", "next",
                 "ago", "recently", "earlier", "later", "summer", "winter",
                 "spring", "fall", "autumn", "weekend", "morning", "evening", "night"}
FREQ_MARKERS = {"once", "twice", "weekly", "daily", "monthly", "yearly",
                "regularly", "often", "sometimes", "never", "always"}


def _tokens(s: str) -> list[str]:
    # currency symbols become word sentinels so the tokenizer cannot eat them
    s = (s.replace("$", " usd ").replace("€", " eur ")
          .replace("£", " gbp ").replace("¥", " cny "))
    return [t for t in re.split(r"[^0-9a-zA-Z.,-]+", s.lower()) if t]


def _word2num(words: list[str]) -> int | None:
    """Parse a run of number words: [TENS? ONES? SCALES?] or simple compounds."""
    total, chunk = 0, 0
    saw = False
    for w in words:
        if w in ONES:
            chunk += ONES[w]; saw = True
        elif w in TENS:
            chunk += TENS[w]; saw = True
        elif w in SCALES:
            if not saw: return None
            chunk = max(chunk, 1) * SCALES[w]; saw = True
        elif saw:
            break
    return total + chunk if saw else None


def _fold_number(tok: str) -> str:
    """7th->7, 56,355->56355, 1st->1 ... else unchanged."""
    m = re.fullmatch(r"(\d[\d,]*(?:\.\d+)?)((?:st|nd|rd|th))?", tok)
    if not m:
        return tok
    return m.group(1).replace(",", "")


def normalize(s: str) -> list[str]:
    """T1 fold: token stream -> canonical multiset components."""
    out: list[str] = []
    raw = _tokens(s)
    i = 0
    while i < len(raw):
        t = raw[i]
        t = t.rstrip(".") if len(t) > 2 else t
        if t in MONTH_FOLD:
            out.append(MONTH_FOLD[t]); i += 1; continue
        if t in HONORIFICS or t.rstrip(".") in HONORIFICS:
            out.append(HONORIFICS.get(t) or HONORIFICS[t.rstrip(".")]); i += 1; continue
        if t in ACRONYMS:
            out.extend(ACRONYMS[t]); i += 1; continue
        if t in ONES or t in TENS:
            run, j = [], i
            while j < len(raw) and (raw[j] in ONES or raw[j] in TENS or raw[j] in SCALES):
                run.append(raw[j]); j += 1
            n = _word2num(run)
            if n is not None:
                out.append(str(n)); i = j; continue
        if t in ORDINALS:
            out.append(str(ORDINALS[t])); i += 1; continue
        if t in CURRENCY and t not in DIST_UNITS:
            # word currency: attach to previous bare number, or absorb the next one
            if out and re.fullmatch(r"\d+(\.\d+)?", out[-1]):
                out[-1] = f"{out[-1]}|{CURRENCY[t]}"
            elif i + 1 < len(raw):
                nxt_f = _fold_number(raw[i + 1])
                if re.fullmatch(r"\d+(\.\d+)?", nxt_f):
                    out.append(f"{nxt_f}|{CURRENCY[t]}")
                    i += 2
                    continue
                out.append("cur:" + CURRENCY[t])
            else:
                out.append("cur:" + CURRENCY[t])
            i += 1
            continue
        f = _fold_number(t)
        if f != t or re.fullmatch(r"\d+(\.\d+)?", f):
            out.append(f)
        else:
            # strip trailing punctuation leftovers
            out.append(re.sub(r"[.,]+$", "", t))
        i += 1
    return [t for t in out if t]


def _time_value(tok_num: str, unit: str) -> float | None:
    if unit in TIME_UNITS:
        return float(tok_num) * TIME_UNITS[unit]
    return None


def number_signature(s: str) -> set[tuple]:
    """(value, unit) pairs; time units canonicalized to seconds, currencies kept."""
    toks = normalize(s)
    sig: set[tuple] = set()
    for idx, t in enumerate(toks):
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:\|(\w+))?", t)
        if not m:
            continue
        val = float(m.group(1))
        cur = m.group(2)
        nxt = toks[idx + 1] if idx + 1 < len(toks) else ""
        if cur:
            sig.add((val, "cur:" + cur))
        elif nxt in TIME_UNITS:
            sec = _time_value(m.group(1), nxt)
            if sec is not None:
                sig.add((sec, "time"))
        elif nxt in DIST_UNITS:
            sig.add((val, "dist:" + DIST_UNITS[nxt]))
        elif nxt in OTHER_UNITS:
            sig.add((val, OTHER_UNITS[nxt]))
        else:
            sig.add((val, None))
    return sig


DAY_RE = r"(\d{1,2})(?:st|nd|rd|th)?"
YEAR_RE = r"(\d{4})"


def date_signature(s: str) -> set[tuple]:
    """Parse (y, m, d) tuples from month-name patterns; y may be None."""
    toks = [re.sub(r"[.,]+$", "", t) for t in _tokens(s)]
    dates: set[tuple] = set()
    for i, t in enumerate(toks):
        m = MONTH_FOLD.get(t)
        if not m:
            continue
        y = d = None
        # month d(,)? y?  — e.g. mar 23 2019 / jan 5 (day = 1-2 digits, never a year)
        mo = re.fullmatch(DAY_RE, toks[i + 1]) if i + 1 < len(toks) else None
        if mo:
            d = int(mo.group(1))
            yo = re.fullmatch(YEAR_RE, toks[i + 2]) if i + 2 < len(toks) else None
            if yo:
                y = int(yo.group(1))
        if d is not None:
            dates.add((y, MONTHS[m], d)); continue
        # d( of)? month (y)? — e.g. 23rd of march 2019 (look back through "of")
        j = i - 1
        if j >= 0 and toks[j] == "of":
            j -= 1
        po = re.fullmatch(DAY_RE, toks[j]) if j >= 0 else None
        if po:
            d = int(po.group(1))
            yo = re.fullmatch(YEAR_RE, toks[i + 1]) if i + 1 < len(toks) else None
            if yo:
                y = int(yo.group(1))
            dates.add((y, MONTHS[m], d))
    # ISO dates
    for t in toks:
        mo = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
        if mo:
            dates.add((int(mo.group(1)), int(mo.group(2)), int(mo.group(3))))
    return dates


def _residue(toks: list[str]) -> list[str]:
    """Content left after consuming number/unit/currency tokens."""
    out = []
    for t in toks:
        if re.fullmatch(r"\d+(\.\d+)?(\|\w+)?", t):
            continue
        if t in TIME_UNITS or t in DIST_UNITS or t in OTHER_UNITS or t in CURRENCY \
                or t.startswith("cur:"):
            continue
        if t == "s":
            continue  # possessive remnant from "X's"
        out.append(t)
    return [t for t in out if t not in STOP]


def question_type(q: str) -> str:
    ql = " " + re.sub(r"[^a-z ]", " ", q.lower()) + " "
    if re.search(r"\bwhen\b|\bwhat date\b|\bwhich day\b|\bwhat day\b", ql):
        return "date"
    if re.search(r"\bhow many\b|\bhow much\b|\bhow long\b|\bhow old\b|\bhow often\b", ql):
        return "number"
    return "entity"


def _stem(w: str) -> str:
    for suf in ("ingly", "edly", "ing", "ies", "ied", "ers", "er", "ed", "es", "ly", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            base = w[: -len(suf)]
            if suf == "ies":
                base += "y"
            return base
    return w


def _content_tokens(s: str) -> set[str]:
    return {t for t in normalize(s)
            if t not in STOP and not re.fullmatch(r"\d+(\.\d+)?(\|\w+)?", t)
            and t != "s" and t not in ("time",)}


def judge(question: str, candidate: str, reference: str) -> tuple[str, dict]:
    """Return (verdict, trace). CREDIT = {EXACT, NORM_EQ, IMPROVES}."""
    trace: dict = {"qtype": question_type(question)}

    # T0 exact (trivial strip)
    if candidate.strip().lower() == reference.strip().lower():
        return "EXACT", trace

    # T1 normalized multiset equality
    nc, nr = normalize(candidate), normalize(reference)
    if Counter(nc) == Counter(nr):
        return "NORM_EQ", trace

    qtype = trace["qtype"]

    # T2 — date: parsed-tuple intersection; unparseable -> NEEDS_JUDGE
    if qtype == "date":
        dc, dr = date_signature(candidate), date_signature(reference)
        trace["dates"] = (sorted(map(str, dc)), sorted(map(str, dr)))
        if dc and dr:
            # match ignoring year only when BOTH sides lack year info
            def keys(ds, with_year):
                return {(y, m, d) if with_year else (m, d) for (y, m, d) in ds}
            wy = any(y for y, _, _ in dc | dr)
            return ("NORM_EQ" if keys(dc, wy) & keys(dr, wy) else "INCOMPATIBLE"), trace
        if ({w for w in nc} & RELATIVE_TIME) or ({w for w in nr} & RELATIVE_TIME):
            return "NEEDS_JUDGE", trace  # relative/seasonal time, unresolved
        # bare day-of-month comparison when neither side names a month
        nums_c = [t for t in nc if re.fullmatch(r"\d{1,2}", t)]
        nums_r = [t for t in nr if re.fullmatch(r"\d{1,2}", t)]
        if nums_c and nums_r:
            return ("NORM_EQ" if Counter(nums_c) == Counter(nums_r) else "INCOMPATIBLE"), trace
        return "NEEDS_JUDGE", trace

    # T2 — number: value+unit signatures
    if qtype == "number":
        sc, sr = number_signature(candidate), number_signature(reference)
        trace["num_sig"] = (sorted(sc), sorted(sr))
        if not sc and not sr:
            return "NEEDS_JUDGE", trace
        # currency conflict guard: same value, different currency => wrong
        for (v1, u1) in sc:
            for (v2, u2) in sr:
                if v1 == v2 and u1 and u2 and u1.startswith("cur:") and u2.startswith("cur:") and u1 != u2:
                    return "INCOMPATIBLE", trace
                if u1 and u2 and (u1.startswith("dist:") != u2.startswith("dist:")):
                    continue
                if v1 == v2 and u1 and u2 and u1 != u2 and (
                        u1.startswith("dist:") and u2.startswith("dist:")):
                    return "INCOMPATIBLE", trace  # 5 miles != 5 km
        vals_c, vals_r = {v for v, _ in sc}, {v for v, _ in sr}
        # time normalization may make values equal with unit "time"
        if sc & sr or (vals_c & vals_r):
            if sc == sr and Counter(_residue(nc)) == Counter(_residue(nr)):
                return "NORM_EQ", trace  # e.g. "2 hours" == "120 minutes" canonically
            if vals_r <= vals_c:
                return "IMPROVES", trace  # candidate superset of reference values
            return "PARTIAL", trace  # candidate misses some reference values
        return "INCOMPATIBLE", trace

    # T2 — entity: asymmetric containment on content tokens
    cc, cr = _content_tokens(candidate), _content_tokens(reference)
    trace["content"] = (sorted(cc), sorted(cr))
    if not cr:
        return "NEEDS_JUDGE", trace
    # pronoun guard: candidate resolved by coref we can't do here
    if (cc & PRONOUNS) and not (cr & PRONOUNS):
        return "NEEDS_JUDGE", trace
    if cr <= cc:
        extra = cc - cr
        return ("IMPROVES" if extra else "NORM_EQ"), trace
    if cc < cr:
        # stem overlap salvage -> partial, else weaker/wrong
        stems_c, stems_r = {_stem(t) for t in cc}, {_stem(t) for t in cr}
        if stems_c <= stems_r:
            return "PARTIAL", trace
        return "PARTIAL", trace
    stems_c, stems_r = {_stem(t) for t in cc}, {_stem(t) for t in cr}
    if stems_c & stems_r or (cc | cr) & FREQ_MARKERS:
        return "NEEDS_JUDGE", trace
    if not (stems_c & stems_r):
        return "INCOMPATIBLE", trace
    return "NEEDS_JUDGE", trace


# --------------------------------------------------------------------------- #
# Self-test: 22 cases modeled on observed LME/amg answer-face mismatch shapes
# --------------------------------------------------------------------------- #
CASES = [
    # (question, candidate, reference, expected)
    ("When did she move?", "January 5, 2023", "Jan 5th 2023", "NORM_EQ"),
    ("How much did it cost?", "It cost $56,355", "56355 dollars", "IMPROVES"),
    ("How many workshops?", "two", "2", "NORM_EQ"),
    ("Who built it?", "Gustave Eiffel's company", "Gustave Eiffel", "IMPROVES"),
    ("What sport does he play?", "tennis", "table tennis", "PARTIAL"),
    ("How many?", "7", "17", "INCOMPATIBLE"),
    ("How much?", "$5", "5 euros", "INCOMPATIBLE"),
    ("Where was she born?", "Boston, MA", "Boston", "IMPROVES"),
    ("When did they meet?", "the 23rd of March, 2019", "March 23, 2019", "NORM_EQ"),
    ("Who is her doctor?", "Dr. Smith", "Doctor Smith", "NORM_EQ"),
    ("What city?", "NYC", "New York City", "NORM_EQ"),
    ("How often does she go?", "once a week", "weekly", "NEEDS_JUDGE"),
    ("What is his job?", "senior software engineer", "software engineer", "IMPROVES"),
    ("What is his job?", "engineer", "software engineer", "PARTIAL"),
    ("How many cats?", "three cats", "3", "IMPROVES"),
    ("When did they meet?", "last summer", "in the summer of 2022", "NEEDS_JUDGE"),
    ("What is her degree in?", "a Bachelor's in biology", "biology", "IMPROVES"),
    ("How long did it take?", "two hours", "2 hours", "NORM_EQ"),
    ("How long did it take?", "2 hours", "120 minutes", "NORM_EQ"),
    ("How far is it?", "about 5 miles", "5 kilometers", "INCOMPATIBLE"),
    ("Who planned it?", "she planned it herself", "Rachel", "NEEDS_JUDGE"),
    ("When did he call?", "yesterday", "on March 3, 2021", "NEEDS_JUDGE"),
    # amg counting-family shapes
    ("How many total?", "2440 dollars total", "$2440", "IMPROVES"),
    ("What day?", "the 7th", "7", "NORM_EQ"),
    ("How old is she?", "32 years old", "32", "IMPROVES"),
    # asymmetry: "her cousin's farm" is MORE specific than reference "the farm" —
    # Bulian AE: equivalent-or-improves => credit (whether the possessive is TRUE
    # is the LLM tier's question, not the deterministic tier's).
    ("Where was the wedding?", "at her cousin's farm", "the farm", "IMPROVES"),
]


def run_tests() -> int:
    fails = 0
    print(f"{'verdict':<13} expected      case")
    print("-" * 78)
    for q, c, r, want in CASES:
        got, _ = judge(q, c, r)
        ok = got == want
        fails += (not ok)
        mark = " " if ok else "✗"
        print(f"{mark} {got:<12} {want:<12} {q[:24]!r} {c[:26]!r} vs {r[:22]!r}")
    credit = sum(1 for q, c, r, w in CASES if judge(q, c, r)[0] in CREDIT)
    print("-" * 78)
    print(f"{len(CASES) - fails}/{len(CASES)} expectations met; "
          f"credit verdicts: {credit}; non-credit: {len(CASES) - credit}")
    return fails


if __name__ == "__main__":
    raise SystemExit(run_tests())
