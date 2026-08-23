#!/usr/bin/env python3
"""Distilled core of dur_family_proto.py v3 — two killer decisions, zero deps.
Run: python3 dur_family_core_demo.py"""
import re

FRANCHISE = {}
for toks, fam in [("marvel mcu cinematic avengers", "marvel"),
                  ("star wars skywalker jedi", "starwars")]:
    for t in toks.split():
        FRANCHISE[t] = fam

_BINGE = re.compile(
    r"(?:watched|finished|completed)\s+(?:all\s+)?(?:the\s+)?(?:of\s+)?(?:the\s+)?"
    r"(?:\d+\s+)?[a-zA-Z\- ]*?(?:movies|films)\b[^.]*?\bin\s+"
    r"(one|two|three|four|five|six|seven|eight|nine|ten|a|an)"
    r"\s+weeks?(\s+and\s+a\s+half)?", re.I)

def m1_watch_dedup_sum(user_texts):
    """Franchise-keyed dedup: a re-mention of the same franchise updates nothing.
    e831120c: 'all 22 MCU movies in two weeks' (turn 1) + 'the main films in
    a week and a half' (turn 2, starwars) + MCU recap mention (turn 3)
    -> 2 + 1.5 = 3.5 weeks; naive re-mention sum = 4.5."""
    nums = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    dur = {}
    for text in user_texts:
        fams = {FRANCHISE.get(w.lower().strip(".,!?;:")) for w in text.split()} - {None}
        if not fams:
            continue
        m = _BINGE.search(text)
        if not m:
            continue
        n = nums[m.group(1).lower()] + (0.5 if m.group(2) else 0)
        key = frozenset(fams)
        if any(k & key for k in dur):   # same franchise already recorded
            continue
        dur[key] = n
    return round(sum(dur.values()), 2)

def m4_guard(question, order_evt, arrival_evt):
    """Question-product guard: join only if the joined product matches the
    asked-about item; otherwise negative existence -> ABSTAIN (C498)."""
    qm = re.search(r"(?:my|the|a|an)\s+([a-z\- ]+?)\s+(?:after|to arrive)", question)
    if not qm:
        return "ABSTAIN"
    q_stems = {w for w in qm.group(1).split() if len(w) > 2}
    prod = set(order_evt["product"]) | set(arrival_evt["product"])
    if q_stems & prod:
        return f"{arrival_evt['day'] - order_evt['day']} days"
    return "ABSTAIN"

if __name__ == "__main__":
    # e831120c evidence (distilled): MCU binge + SW binge + a later MCU recap
    texts = ["I watched all 22 Marvel Cinematic Universe movies in two weeks!",
             "Then I finished the main Star Wars films in a week and a half.",
             "My friends could not believe I watched all the Marvel movies in two weeks."]
    assert m1_watch_dedup_sum(texts) == 3.5      # naive = 2+1.5+2 = 5.5? no: 4.5
    # 60bf93ed: backpack ordered 1/15 arrived 1/20 (join=5d), question asks iPad case
    q = "How many days did it take for my iPad case to arrive after I ordered it?"
    order = {"product": ["laptop", "backpack"], "day": 15}
    arrival = {"product": ["laptop", "backpack"], "day": 20}
    assert m4_guard(q, order, arrival) == "ABSTAIN"
    q2 = "How many days did it take for my laptop backpack to arrive?"
    assert m4_guard(q2, order, arrival) == "5 days"
    print("demo OK: m1=3.5 weeks, m4 guard abstains on unmatched product, joins on match")
