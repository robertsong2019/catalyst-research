#!/usr/bin/env python3
"""Fired-but-wrong forensics — Research #072 (2026-08-18).

Dissects the 9 LongMemEval_s temporal questions where the C457
temporal-arithmetic gate FIRED but answered WRONG (28 fired total,
19 correct, 9 wrong). Produces the per-question anchor resolution,
gold-session fix-locality test, and the control-group check that
fired-correct == same-day narration.

Requires:
  /tmp/lme_s.json               (LongMemEval_s, 277 MB, HF original)
  /tmp/lme_s_full500_evhit.json (run_eval output with honest qids,
                                 C467 artifact)
  amg repo on sys.path          (amg_bench_quality)

Run:  python3 fw9_forensics.py
"""
import json
import re
import sys

sys.path.insert(0, '/root/.openclaw/workspace/projects/agent-memory-graph')
from amg_bench_quality import (temporal_arith_form, _anchor_keywords,
                               _keyword_hits, duration_units, parse_lme_date)

DATA = '/tmp/lme_s.json'
RESULTS = '/tmp/lme_s_full500_evhit.json'


def best_line(anchor, dated_lines):
    """Exact reproduction of answer_temporal_arith.best_line (first-max
    wins — list-position tie-break)."""
    ks = _anchor_keywords(anchor)
    if not ks:
        return None, ks
    best, best_hits = None, 0
    for line, sdate, sid, role in dated_lines:
        hits = _keyword_hits(line, ks)
        if hits > best_hits:
            best, best_hits = (hits, sdate, sid, role), hits
    return best, ks


def build_lines(q):
    """All haystack lines, dated: (line, session_date, sid, role)."""
    hsid = q.get('haystack_session_ids') or []
    hdates = [parse_lme_date(d) for d in (q.get('haystack_dates') or [])]
    dated_lines, sid_date = [], {}
    for i, sess in enumerate(q.get('haystack_sessions') or []):
        sid = hsid[i] if i < len(hsid) else f'idx{i}'
        sd = hdates[i] if i < len(hdates) else ''
        sid_date[sid] = sd
        msgs = sess if isinstance(sess, list) else sess.get('messages', [])
        for m in msgs:
            for line in m.get('content', '').split('\n'):
                line = line.strip()
                if line:
                    dated_lines.append((line, sd, sid, m.get('role', '?')))
    return dated_lines, sid_date


def main():
    res = json.load(open(RESULTS))

    def gate(r):
        ret = r['retrieval'] if isinstance(r['retrieval'], dict) else eval(r['retrieval'])
        return ret.get('gate')

    fired_wrong = [r for r in res['results']
                   if r['category'] == 'temporal_reasoning'
                   and gate(r) == 'temporal_arith' and not r['correct']]
    fired_ok = [r for r in res['results']
                if r['category'] == 'temporal_reasoning'
                and gate(r) == 'temporal_arith' and r['correct']]
    print(f'fired={len(fired_wrong)+len(fired_ok)} '
          f'correct={len(fired_ok)} wrong={len(fired_wrong)}')

    data = json.load(open(DATA))
    qmap = {q.get('question_id'): q for q in data}

    print('\n########## WRONG (forensics) ##########')
    for r in fired_wrong:
        q = qmap[r['question_id']]
        question = q['question']
        qdate = parse_lme_date(q.get('question_date'))
        gold_sids = set(q.get('answer_session_ids') or [])
        form = temporal_arith_form(question)
        kind, unit, a, b = form
        golds = [int(x) for x in re.findall(r'\d+', str(q['answer']))]
        dated_lines, sid_date = build_lines(q)

        print('=' * 92)
        print(f"{r['question_id']}  {kind}/{unit}  qdate={qdate}")
        print(f"Q:  {question}")
        print(f"GT: {q['answer']}   PA: {r['predicted_answer']}")

        resolved = {}
        for anchor in [x for x in (a, b) if x]:
            best, ks = best_line(anchor, dated_lines)
            if best:
                hits, sdate, sid, role = best
                print(f"  ANCHOR {anchor!r} kw={ks}")
                print(f"    -> {sdate} [{sid[:26]}] {role} hits={hits} "
                      f"gold={sid in gold_sids}")
                # runner-up candidates (tie diagnostics)
                cands = sorted(
                    ((_keyword_hits(l, ks), sd, s2, ro, l)
                     for l, sd, s2, ro in dated_lines
                     if _keyword_hits(l, ks) > 0),
                    key=lambda t: -t[0])[:3]
                for h, sd, s2, ro, l in cands:
                    print(f"      h={h} {sd} [{s2[:24]}]{'*G*' if s2 in gold_sids else '  '}: {l[:100]}")
                resolved[anchor] = sdate
            else:
                print(f'  ANCHOR {anchor!r} -> NO HITS')
                resolved[anchor] = None

        ev = sorted({sid_date.get(s) for s in gold_sids if sid_date.get(s)})
        print(f'  gold event dates: {ev}')

        # fix-locality: would gold-session anchoring produce GT?
        if kind in ('ago', 'since') and qdate:
            for gd in ev:
                n = duration_units(qdate, gd, unit)
                ceil_n = -(-abs((parse_lme_date(qdate) and
                                 __import__('datetime').date.fromisoformat(qdate)) -
                                __import__('datetime').date.fromisoformat(gd)).days // 7) if unit == 'week' else n
                print(f'    gold {gd}: floor={n} ceil_week={ceil_n} '
                      f'GT-in={n in golds or ceil_n in golds}')
        elif kind == 'between' and len(ev) >= 2:
            n = duration_units(ev[0], ev[-1], unit)
            print(f'    gold span {ev[0]}..{ev[-1]}: {n} (+1 inclusive={n+1}) '
                  f'GT-in={(n in golds) or (n + 1 in golds)}')

    print('\n########## CONTROL (fired-correct) ##########')
    same_day = tot = 0
    for r in fired_ok:
        q = qmap[r['question_id']]
        qdate = parse_lme_date(q.get('question_date'))
        golds = [int(x) for x in re.findall(r'\d+', str(q['answer']))] or [0]
        _, sid_date = build_lines(q)
        ev = sorted({sid_date.get(s) for s in (q.get('answer_session_ids') or [])
                     if sid_date.get(s)})
        if not ev:
            continue
        form = temporal_arith_form(q['question'])
        kind, unit, a, b = form
        tot += 1
        if kind in ('ago', 'since') and qdate:
            hit = any(duration_units(qdate, g, unit) in golds for g in ev)
        elif kind == 'between' and len(ev) >= 2:
            hit = duration_units(ev[0], ev[-1], unit) in golds
        else:
            continue
        same_day += hit
        print(f"  {r['question_id'][:16]} {kind}/{unit} "
              f"gold-session-arithmetic-matches-GT={hit}")
    print(f'\nCONTROL: {same_day}/{tot} fired-correct are pure '
          f'session-date arithmetic (same-day narration).')


if __name__ == '__main__':
    main()
