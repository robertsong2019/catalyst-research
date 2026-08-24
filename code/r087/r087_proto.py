#!/usr/bin/env python3
"""Research #087 · Kupdate Direction-Aware Extractor — oracle prototype (v9).

Runnable standalone:
    python3 r087_proto.py            # oracle A/B on 78 kupdate questions
    python3 r087_proto.py -v         # verbose per-question detail

Inputs (auto-detected):
    r087_fixture.json (bundled, self-contained)  OR
    /tmp/r087/ku_corpus.json + /tmp/c508/post_full500.json (full corpus)

Mechanisms (see research note for derivation):
  1. Fact signature: question content words minus stoplist
  2. Direction guard: EARLY (initially/used-to/before-V/prev-measure; entity-noun
     descriptors like "previous company" excluded) vs LATE (default = current value)
  3. Form -> value-type gate: how many -> digit/word-number lines;
     when -> date/weekday lines; "day of the week" -> weekday-only
  4. Value-clause-locality: value token within VAL_WIN chars of a signature word
     (transplanted from #086 delta-family bipartite binding, principle 4)
  5. Yes/No face for binary questions; No only on global sig absence (negative existence)
  6. Ordering: LATE = (later session, user role, more sig hits, later line);
     EARLY = (earlier session, user role, more sig hits, earlier line)
Zero-hijack: no candidates -> fall through to baseline prediction.

Result (oracle, keyword-containment judge, same judge both arms):
    n=78  baseline 22 (0.282)  ->  prototype 54 (0.692)   regressions 2
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, 'r087_fixture.json')
CORPUS = '/tmp/r087/ku_corpus.json'
RESULTS = '/tmp/c508/post_full500.json'

STOP = set('''how what where when who why which do does did is are was were the a an my me i of to in on at for
with about and or if you your it its this that these those usually currently often many much long time week
month year get got have has had'''.split())
ENT_NOUNS = re.compile(r'\bprevious (?:company|tutor|manager|boss|colleague|partner|roommate|job|employer|team|advisor|professor|instructor|supervisor|landlord|neighbor)\b', re.I)
EARLY_RE = re.compile(r'\b(initially|used to|originally)\b|\bbefore (?:i |my |getting|updating|changing|switching|moving|selling|replacing)|\bjust started\b|\bwhen i (?:first|started|began)\b', re.I)
PREV_MEASURE_RE = re.compile(r'\bprevious (?:\w+ )?(?:goal|best|target|level|record|weight|schedule|routine|plan|budget|limit|number|setting|status)\b', re.I)
YESNO_RE = re.compile(r'^(?:do|did|does|is|are|was|were|have|has|had|will|would|can|could|am)\b', re.I)
HOWMANY_RE = re.compile(r'^how (?:many|much)\b', re.I)
WHEN_RE = re.compile(r'^(?:when|what day|what time|how long ago)\b', re.I)
WEEKDAY_Q = re.compile(r'day of the week', re.I)
NUMWORD = r'(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|once|twice|couple|dozen)'
NUMWORD_RE = re.compile(r'\b' + NUMWORD + r'\b', re.I)
VALUE_TOK_RE = re.compile(r'\b\d+(?:\.\d+)?\b|\b' + NUMWORD + r'\b', re.I)
WEEKDAY_RE = re.compile(r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b', re.I)
WHEN_VAL = re.compile(r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|april|june|july|august|september|october|november|december|yesterday|tomorrow)\b|\bago\b|\b\d{1,4}\b', re.I)
VAL_WIN = 70

def norm(s):
    return re.sub(r'[^a-z0-9 ]', ' ', str(s).lower())

def toks(s):
    return [w for w in norm(s).split() if len(w) >= 3 and w not in STOP]

def judge(pred, gt):
    pn, gn = norm(pred), norm(gt)
    gw = [w for w in gn.split() if len(w) >= 2]
    if not gw:
        return pn == gn
    for w in gw:
        if w.isdigit():
            if not re.search(r'(?<!\d)' + w + r'(?!\d)', pn):
                return False
        elif w not in pn:
            return False
    return True

def is_early(qtext):
    if ENT_NOUNS.search(qtext):
        return False
    return bool(EARLY_RE.search(qtext) or PREV_MEASURE_RE.search(qtext))

def word_find(line, word, start=0):
    low, i = line.lower(), line.lower().find(word, start)
    while i != -1:
        l_ok = i == 0 or not line[i - 1].isalpha()
        r_ok = i + len(word) >= len(line) or not line[i + len(word)].isalpha()
        if l_ok and r_ok:
            return i
        i = low.find(word, i + 1)
    return None

def value_near_sig(line, sig):
    best = None
    for mv in VALUE_TOK_RE.finditer(line):
        for sw in sig:
            st = 0
            while True:
                i = word_find(line, sw, st)
                if i is None:
                    break
                d = abs(mv.start() - (i + len(sw)))
                best = d if best is None else min(best, d)
                st = i + 1
    return best

def proto_answer(q):
    qtext = q['question']
    sig = set(toks(qtext))
    if 'answer_sessions' in q:  # fixture mode
        smap = q['answer_sessions']
        ans = set(smap)
        ordered = list(smap)
    else:                       # corpus mode
        ans = set(q['answer_session_ids'])
        smap = dict(zip(q['haystack_session_ids'], q['haystack_sessions']))
        ordered = [s for s in q['haystack_session_ids'] if s in smap]
    early = is_early(qtext)
    yesno = bool(YESNO_RE.match(qtext.strip())) and not HOWMANY_RE.match(qtext.strip())
    howmany = bool(HOWMANY_RE.match(qtext.strip()))
    whenq = bool(WHEN_RE.match(qtext.strip()))
    weekdayq = bool(WEEKDAY_Q.search(qtext))
    cands = []
    for order, sid in enumerate(ordered):
        for li, msg in enumerate(smap[sid]):
            c = msg.get('content', '')
            hits = len(sig & set(norm(c).split()))
            if hits:
                cands.append((hits, msg.get('role') == 'user', order, li, c))
    if yesno:
        if cands:
            return ('Yes.', True, 'yesno')
        g_hits = any(len(sig & set(norm(m.get('content', '')).split()))
                     for sid in ordered for m in smap[sid])
        return ('No.', True, 'yesno') if not g_hits else (None, False, 'yesno-ft')
    if not cands:
        return (None, False, '?')
    if weekdayq:
        vf = [c for c in cands if WEEKDAY_RE.search(c[4])]
        if vf:
            cands = vf
    elif howmany:
        vf = [c for c in cands if re.search(r'\d', c[4]) or NUMWORD_RE.search(c[4])]
        if vf:
            near = [c for c in vf if (value_near_sig(c[4], sig) or 999) <= VAL_WIN]
            cands = near or vf
    elif whenq:
        vf = [c for c in cands if WHEN_VAL.search(c[4])]
        if vf:
            cands = vf
    if early:
        cands.sort(key=lambda x: (x[2], not x[1], -x[0], x[3]))
    else:
        cands.sort(key=lambda x: (x[2], x[1], x[0], x[3]), reverse=True)
    return (cands[0][4], True, f'{"early" if early else "late"}')

def load():
    if os.path.exists(FIXTURE):
        fx = json.load(open(FIXTURE))
        corpus = [{'question_id': f['qid'], 'question': f['question'], 'answer': f['answer'],
                   'answer_sessions': f['answer_sessions']} for f in fx]
        preds = {f['qid']: {'predicted_answer': f['baseline_pred']} for f in fx}
        return corpus, preds
    corpus = {q['question_id']: q for q in json.load(open(CORPUS))}
    R = json.load(open(RESULTS))
    preds = {r['question_id']: r for r in R['results'] if r.get('category') == 'knowledge_update'}
    return list(corpus.values()), preds

def main(verbose=False):
    corpus, preds = load()
    ok = base_ok = regress = fires = 0
    fx = []
    from collections import Counter
    faces = Counter()
    for q in corpus:
        gt = str(q['answer'])
        base_pred = str(preds[q['question_id']].get('predicted_answer', ''))
        p_ans, fired, face = proto_answer(q)
        faces[face] += 1
        final = p_ans if fired else base_pred
        b, p = judge(base_pred, gt), judge(final, gt)
        base_ok += b; ok += p; fires += fired
        if b and not p:
            regress += 1
        if verbose:
            mark = 'V' if p else ('R' if b else ' ')
            print(f"[{mark}] {q['question_id']} {face:6s} GT: {gt[:40]:42s} -> {str(final)[:70]}")
    n = len(corpus)
    print(f'\nn={n} baseline={base_ok} ({base_ok/n:.3f}) proto={ok} ({ok/n:.3f}) fires={fires} regress={regress}')
    print('faces:', dict(faces))
    if fx:
        json.dump(fx, open('/tmp/r087/final_regress.json', 'w'), indent=1)

if __name__ == '__main__':
    main('-v' in sys.argv)
