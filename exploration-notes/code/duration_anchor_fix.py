#!/usr/bin/env python3
"""Research #079 — duration_sum over-summing forensics + fix A/B.

Self-contained harness (imports production functions from
projects/agent-memory-graph). Two modes:

  python3 duration_anchor_fix.py --trace    # per-event forensics
  python3 duration_anchor_fix.py --ab       # 4-arm A/B on 133-slice

Root causes (2026-08-21, LME_s full haystacks):
  F1  question anchor set contains the question's own UNIT word
      ('days') -> any sentence mentioning 'days' passes the anchor
      gate (legal/congressional noise = 42/75 junk days).
  F2  generic geographic heads ('city') survive into cap anchors
      -> whole sessions become anchor_ok via the word 'city'.
  F3  within-sentence contrast ('14 days instead of 28 days')
      emits two additive events (supersession misread as sum).

Verdict: F1 = keep (+3/0 on 133-slice, prec 0.70->0.86);
F2 = one-line hardening (no live case on slice, defends the
anchor_ok bypass); F3 = defer (no live case post-F1).
"""
import json, re, sys, time
from collections import defaultdict

sys.path.insert(0, 'projects/agent-memory-graph')
import amg_bench_quality as abq
from amg_bench_quality import (
    counting_form, _cnt_question_anchors, _cnt_anchor_re, _cnt_sents,
    _cnt_durations_days, _cnt_daterange_days, _cnt_proper_nouns,
    _CNT_INTENT_RE, _CNT_GENERIC_HEADS)

UNIT_ANCHOR_STOP = {u.rstrip('s') for u in (
    'day', 'days', 'week', 'weeks', 'hour', 'hours', 'month',
    'months', 'year', 'years', 'minute', 'minutes', 'night',
    'nights', 'time', 'times')}
CONTRAST_RE = re.compile(
    r'\b(instead of|rather than|as opposed to|not\s+\S+\s+but)\b',
    re.I)


def patched_duration_sum(question, sessions, f2=False, f3=False):
    """Production _cnt_duration_sum + F1 (always) + optional F2/F3."""
    q = question.lower()
    want_unit = ('days' if re.search(r'\bdays\b', q)
                 else ('weeks' if re.search(r'\bweeks\b', q) else None))
    if want_unit is None:
        return None
    # F1: measurement units are not topical anchors
    anchors = {a for a in _cnt_question_anchors(question)
               if a.rstrip('s') not in UNIT_ANCHOR_STOP}
    are = _cnt_anchor_re(anchors)
    per_session = defaultdict(
        lambda: {'events': [], 'counts': set(), 'pnouns': set(),
                 'anchor_ok': False})
    cap_anchors = {w.lower()
                   for w in re.findall(r"\b[A-Z][a-z]+\b", question)
                   if w.lower() in anchors}
    if f2:
        cap_anchors -= {'city', 'cities'} | _CNT_GENERIC_HEADS
    cap_are = _cnt_anchor_re(cap_anchors) if cap_anchors else None
    for si, sent in _cnt_sents(sessions):
        if are and are.search(sent):
            per_session[si]['pnouns'] |= _cnt_proper_nouns(sent)
            per_session[si]['counts'] |= {
                int(n) for n in
                re.findall(r'\ball\s+(\d{1,4})\b', sent)}
            if cap_are and cap_are.search(sent):
                per_session[si]['anchor_ok'] = True
    for si, sent in _cnt_sents(sessions):
        sess = per_session[si]
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        if are and not are.search(sent) and not sess['anchor_ok']:
            continue
        durs = _cnt_durations_days(sent)
        if f3 and len(durs) > 1 and CONTRAST_RE.search(sent):
            durs = durs[:1]        # supersession: first value operative
        for days, _span in durs:
            sess['events'].append(round(days, 1))
        dr = _cnt_daterange_days(sent)
        if dr is not None:
            sess['events'].append(round(dr, 1))
    merged = []
    for si, data in sorted(per_session.items()):
        sig = data['counts'] | data['pnouns']
        for days in data['events']:
            hit = next((ev for ev in merged
                        if ev[0] == days and (ev[1] & sig)), None)
            if hit:
                hit[1] |= sig
            else:
                merged.append([days, set(sig)])
    if not merged:
        return None
    if cap_anchors and ' and ' in question.lower():
        ev_sigs = set()
        for ev, sig in merged:
            ev_sigs |= sig
        missing = [a for a in cap_anchors
                   if a not in ev_sigs
                   and not any(a in s for s in ev_sigs)]
        if missing:
            return None
    total = sum(ev[0] for ev in merged)
    val = total / (7.0 if want_unit == 'weeks' else 1.0)
    return f"{round(val, 2):g} {want_unit}"


# ── shared data plumbing ──────────────────────────────────────────
def norm(raw):
    return [{'session_id': f's{i}', 'turns': s} if isinstance(s, list)
            else s for i, s in enumerate(raw)]


def load():
    data = json.load(open('/tmp/lme_s.json'))
    roles = json.load(open('/tmp/msagg/multi_evidence_roles.json'))
    return data, roles


# ── --trace mode ─────────────────────────────────────────────────
def trace():
    data, _ = load()
    byid = {it['question_id']: it for it in data}
    for qid, label in [('6cb6f249', 'SOCIAL-MEDIA GT=17'),
                       ('edced276', 'HAWAII+NYC GT=15')]:
        it = byid[qid]
        q, sess = it['question'], norm(it['haystack_sessions'])
        anchors = _cnt_question_anchors(q)
        prod = abq.answer_counting(q, sess)[0]
        fixed = patched_duration_sum(q, sess)
        print(f"\n[{label}] {q}")
        print(f"  anchors={sorted(anchors)}")
        for si, sent in _cnt_sents(sess):
            if _CNT_INTENT_RE.search(sent) or sent.endswith('?'):
                continue
            for days, span in _cnt_durations_days(sent):
                print(f"    EV s{si} +{round(days,1):>5} [{span}] "
                      f"{sent[:90]}")
        print(f"  production = {prod!r}   F1-patched = {fixed!r}"
              f"   GT = {it['answer'][:30]!r}")


# ── --ab mode ────────────────────────────────────────────────────
def pred_number(p):
    if p is None:
        return None
    m = re.search(r'\d+(?:\.\d+)?', str(p))
    return float(m.group(0)) if m else None


def gt_number(gt):
    m = re.search(r'\d+(?:\.\d+)?', str(gt))
    return float(m.group(0)) if m else None


def ab():
    data, roles = load()
    byid = {it['question_id']: it for it in data}
    arms = {
        'A': lambda q, s: abq.answer_counting(q, s)[0],
        'B': lambda q, s: patched_duration_sum(q, norm(s))
                          if counting_form(q) == 'duration_sum'
                          else abq.answer_counting(q, s)[0],
        'C': lambda q, s: patched_duration_sum(q, norm(s), f2=True)
                          if counting_form(q) == 'duration_sum'
                          else abq.answer_counting(q, s)[0],
        'D': lambda q, s: patched_duration_sum(q, norm(s), True, True)
                          if counting_form(q) == 'duration_sum'
                          else abq.answer_counting(q, s)[0],
    }
    score = {k: [0, 0, 0] for k in arms}   # fired-correct / fired / abstain-correct
    for r in roles:
        it = byid.get(r['question_id'])
        if it is None:
            continue
        q, gt = it['question'], str(it['answer'])
        gt_n = gt_number(gt)
        not_enough = ('not enough' in gt.lower()
                      or 'information provided' in gt.lower())
        sess = norm(it['haystack_sessions'])
        for k, fn in arms.items():
            pred = fn(q, sess)
            pn = pred_number(pred)
            if pn is not None:
                score[k][1] += 1
                if gt_n is not None and abs(pn - gt_n) < 1e-6:
                    score[k][0] += 1
            elif not_enough:
                score[k][2] += 1
    n = len(roles)
    print(f"n={n}")
    print(f"{'arm':4} {'f-ok':>5} {'fired':>6} {'prec':>6} "
          f"{'abst-ok':>8} {'hit':>6}")
    for k in 'ABCD':
        fc, f, ac = score[k]
        print(f"{k:4} {fc:>5} {f:>6} {(fc/f if f else 0):>6.2f} "
              f"{ac:>8} {(fc+ac)/n:>6.3f}")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else '--ab'
    t0 = time.time()
    if mode == '--trace':
        trace()
    else:
        ab()
    print(f"({time.time()-t0:.0f}s incl. 277MB dataset load)")
