#!/usr/bin/env python3
"""Research #080 — preference form: full-haystack profile scan prototype.

Hypothesis: for single-session-preference questions, the GT is a synthesis of
user first-person preference lines in the (single) answer session; a
marker-filtered + question-topic-overlap ranked scan over the full haystack
recovers the answer session far better than the production recall window
(answer_session_hit 17/30 = 0.567).

Arms:
  A  prod-window   — answer_session_hit from C481 report (reference)
  B  scan-nomarker — rank ALL user lines by question-term overlap (no marker gate)
  C  scan-marker   — rank only user lines matching preference markers
  D  C + topic-boost — C + bonus if overlap hits a capitalized entity of the line

Metrics: top1/top3 session-hit; entity-coverage of top-3 lines vs GT entities.

Self-contained: python3 preference_profile_scan.py [--data /tmp/lme_s.json]
"""
import json, re, sys, statistics

DATA = sys.argv[sys.argv.index('--data') + 1] if '--data' in sys.argv else '/tmp/lme_s.json'

PREF_MARKERS = [
    r"\bi (?:love|like|enjoy|prefer|adore)\b", r"\bmy favou?rite\b",
    r"\bi(?:'ve| have) been\b", r"\bi use\b", r"\bi(?:'d| would) (?:love|rather)\b",
    r"\bi(?:'m| am) (?:really |such |quite )?a\b", r"\bi(?:'m| am) (?:trying|planning|thinking)\b",
    r"\bi (?:recently|just) (?:started|bought|got|took|gotten)\b",
    r"\bmy (?:go-to|new|current|own)\b",
]
MARKER_RE = re.compile('|'.join(PREF_MARKERS), re.I)

Q_STOP = set('''the a an i you my me can could would should do does any some what which
how why where when who that this these those for with about of to in on at from
and or but so if as it its is are was were be been am being have has had will
recommend suggest recommendations suggestions tips tip advice ideas idea help
find finding look looking give giving show showing tell telling'''.split())

GT_STOP = set('''the user would prefer prefers responses response that suggest suggestions
recommend recommendations or of to for with a an their my your in on and about
such as especially ones well more most really specifically tailored towards
based from previous past current new other another'''.split())

def terms(text):
    return {t for t in re.findall(r"[a-z][a-z'-]{2,}", text.lower()) if t not in Q_STOP}

def gt_entities(gt):
    toks = re.findall(r"[A-Za-z][A-Za-z'-]+", gt)
    return {t.lower() for t in toks if t.lower() not in GT_STOP and len(t) > 3}

def get_sessions(q):
    ids = q.get('haystack_session_ids') or []
    for i, s in enumerate(q['haystack_sessions']):
        sid = str(ids[i]) if i < len(ids) else ''
        if isinstance(s, dict):
            yield sid, s.get('messages', [])
        else:
            yield sid, (s if isinstance(s, list) else [])

def user_lines(q):
    """yield (session_idx, text) for every user line in the haystack."""
    for i, (_sid, msgs) in enumerate(get_sessions(q)):
        for m in msgs:
            role = m.get('role', '') if isinstance(m, dict) else 'user'
            text = m.get('content', '') if isinstance(m, dict) else str(m)
            if role == 'user' and text:
                yield i, text

def rank(q, marker_gate=False, topic_boost=False):
    qt = terms(q['question'])
    scored = []
    for si, text in user_lines(q):
        if marker_gate and not MARKER_RE.search(text):
            continue
        lt = terms(text)
        ov = qt & lt
        score = len(ov)
        if topic_boost and ov:
            caps = {t.lower() for t in re.findall(r"\b[A-Z][a-z]+\b", text)}
            score += 0.5 * len(ov & caps)
        scored.append((score, si, text))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored

def topk_session_hit(scored, k):
    if not scored:
        return 0
    sess = []
    for score, si, _ in scored:
        if si not in sess:
            sess.append(si)
    return 1 if any(s == 0 for s in sess[:k]) else 0  # NOTE: session index not id — see below

def session_topic_rank(q, roles=('user', 'assistant')):
    """Aggregate question-term overlap at SESSION level (all lines)."""
    qt = terms(q['question'])
    scores = []
    for sid, msgs in get_sessions(q):
        bag = set()
        for m in msgs:
            role = m.get('role', '') if isinstance(m, dict) else 'user'
            text = m.get('content', '') if isinstance(m, dict) else str(m)
            if role in roles:
                bag |= terms(text)
        scores.append((len(qt & bag), sid))
    scores.sort(key=lambda x: (-x[0], x[1]))
    return scores


def main():
    ds = json.load(open(DATA))
    prefs = [q for q in ds if q['question_type'] == 'single-session-preference']
    print(f'preference questions: {len(prefs)}')

    # session id mapping: answer sessions are matched by position via answer_session_ids
    stats = {'B_nomarker': [0, 0, 0], 'C_marker': [0, 0, 0], 'D_boost': [0, 0, 0]}
    for q in prefs:
        ans_ids = {str(a) for a in (q.get('answer_session_ids') or [])}
        sids = [str(sid) for sid, _ in get_sessions(q)]
        assert any(s in ans_ids for s in sids), f"answer session not found: {q['question_id']}"
        gents = gt_entities(q['answer'])
        for name, kw in [('B_nomarker', dict()),
                         ('C_marker', dict(marker_gate=True)),
                         ('D_boost', dict(marker_gate=True, topic_boost=True))]:
            scored = rank(q, **kw)
            if not scored:
                continue
            top = scored[:3]
            # session-level: did top-3 lines come from the answer session?
            top_sess = {sids[si] for _, si, _ in top}
            if top_sess & ans_ids:
                stats[name][0] += 1  # top3-any session hit
            # entity coverage of top-3 lines
            lt = set()
            for _, _, text in top:
                lt |= {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z'-]+", text)}
            if gents:
                cov = len(gents & lt) / len(gents)
                if cov >= 0.7:
                    stats[name][1] += 1
                stats[name][2] += cov
    n = len(prefs)
    print(f"{'arm':<16} {'top3-sess-hit':>13} {'ent-cov>=0.7':>12} {'avg-cov':>8}")
    print(f"{'A_prod(ref)':<16} {17:>10}/30   {0:>9}/30   {'—':>8}")
    for name, (hit, cov7, covs) in stats.items():
        print(f"{name:<16} {hit:>10}/30   {cov7:>9}/30   {covs/n:>8.3f}")

    # Arm E: two-stage — session topic localization (all roles) -> marker lines inside
    e_top1 = e_top2 = e_cov7 = 0
    e_cov_sum = 0.0
    for q in prefs:
        ans_ids = {str(a) for a in (q.get('answer_session_ids') or [])}
        ranked = session_topic_rank(q)
        top2 = [sid for _, sid in ranked[:2]]
        pick = top2[0] if top2 else None
        if pick in ans_ids:
            e_top1 += 1
        if ans_ids & set(top2):
            e_top2 += 1
            # entity coverage from marker lines of the HIT session (use the hit one if in top2)
            target = (ans_ids & set(top2)).pop()
        elif pick:
            target = pick
        else:
            continue
        gents = gt_entities(q['answer'])
        lt = set()
        for sid, msgs in get_sessions(q):
            if sid != target:
                continue
            for m in msgs:
                role = m.get('role', '') if isinstance(m, dict) else 'user'
                text = m.get('content', '') if isinstance(m, dict) else str(m)
                if role == 'user' and MARKER_RE.search(text):
                    lt |= {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z'-]+", text)}
        if gents:
            cov = len(gents & lt) / len(gents)
            e_cov_sum += cov
            if cov >= 0.7:
                e_cov7 += 1
    print(f"{'E_2stage':<16} {e_top2:>3}/30 top2 ({e_top1}/30 top1)  {e_cov7:>4}/30   {e_cov_sum/n:>8.3f}")

    # Arm F: decisive diagnostic — is the answer session the UNIQUE lexical best at all?
    # (session-level bag-of-terms overlap, user lines; raw + stemmed)
    raw_best = stem_best = 0
    for q in prefs:
        ans_ids = {str(a) for a in (q.get('answer_session_ids') or [])}
        qt = terms(q['question'])
        scores = []
        for sid, msgs in get_sessions(q):
            bag = set()
            for m in msgs:
                role = m.get('role', '') if isinstance(m, dict) else 'user'
                text = m.get('content', '') if isinstance(m, dict) else str(m)
                if role == 'user':
                    bag |= terms(text)
            scores.append((len(qt & bag), sid))
        best = max(s for s, _ in scores)
        winners = [sid for s, sid in scores if s == best]
        if len(winners) == 1 and winners[0] in ans_ids:
            raw_best += 1
    print(f"{'F_lexbest(user)':<16} {raw_best:>3}/30 unique lexical best — preference is lexical-unreachable" if raw_best < 10 else f"{'F_lexbest(user)':<16} {raw_best:>3}/30")

if __name__ == '__main__':
    main()
