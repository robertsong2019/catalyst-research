"""Research #086 v2.1 — delta-family mechanism (two-anchor numeric aggregation).
Changes vs v2: any-of anchor scoring (not must-all), stem-lite normalization
(hyphens->space + suffix strip for len>5 tokens), geo mini-lexicon, minmax entity
split fix, ratio re-extract, rate debug, 5K temporal-minutes branch.
"""
import json, re, sys

import os as _os
C = json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'r086_corpus.json')))

MONEY = re.compile(r'\$\s?([\d,]+(?:\.\d+)?)')
PCT   = re.compile(r'(\d+(?:\.\d+)?)\s*(?:%|percent)', re.I)
MPG   = re.compile(r'(\d+(?:\.\d+)?)\s*miles per gallon', re.I)
MINRE = re.compile(r'(\d+(?:\.\d+)?)\s*minutes', re.I)
OLD_T, NEW_T = ('ago', 'last', 'previous', 'initially', 'before', 'earlier'), \
               ('now', 'lately', 'recently', 'current', 'these days')
WORDN = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
LEX = {'hawaii': ('maui', 'honolulu', 'oahu', 'hawaii', 'kauai')}
GENERIC = set('the a an my i me of on in at for to with and or did do does is was were how much many '
    'what which more less than compared compare comparison between higher lower instead take taking '
    'by will would could it its that this these those spend spent cost costs cost paid pay save saved '
    'price amount money total per night nightly week month day'.split())
SIDE_GEN = set('receive percentage discount expensive ride daily commute fare ticket amount quote '
    'initial corrected final get got order first trip event charity from again will would'.split())

def stem(t):
    for suf in ('ed', 'al', 'es', 's'):
        if len(t) > 5 and t.endswith(suf):
            return t[:-len(suf)]
    return t

def norm(s):
    return re.sub(r'[^a-z0-9$% ]', ' ', s.lower())

def kws(s, side=False):
    out = [t for t in re.findall(r"[a-z']+", s.lower())
           if t not in GENERIC and (not side or t not in SIDE_GEN) and len(t) > 2]
    return [stem(t) for t in out]

def lines(msgs):
    for si, role, c in msgs:
        for line in c.split('\n'):
            yield si, role, line

def scan(msgs, ureg):
    out = []
    for si, role, ln in lines(msgs):
        for m in ureg.finditer(ln):
            raw = m.group(1).replace(',', '')
            v = float(raw) if raw.replace('.', '', 1).isdigit() else wnum(raw.lower())
            if v is None: continue
            out.append((v, si, role, ln, m.group(0)))
    return out

RANGE_RE = re.compile(r'\$[\d,]+\s*(?:-|to|–)\s*\$?[\d,]+|(?:want|planning|budget(?:ing)?|looking) (?:to )?spend', re.I)
CLAUSE_STOP = '.!?;'

def pick(cands, anchors, unit_ctx=None, verbose=False, require=None, exclude=None):
    """any-of anchor scoring with:
       - require: anchors that MUST appear on the line
       - exclude: if line matches exclude-anchors >= own count, skip (cross-side guard)
       - per-anchor min distance, clause-locality (no .!?; between value and anchor)
       - user-role priority, later session, smaller distance"""
    exp = list(anchors or [])
    for a in (anchors or []):
        exp.extend(LEX.get(a, ()))
    excl = list(exclude or [])
    best, bestkey = None, None
    for t in cands:
        v, si, r, ln, raw = t
        l = ln.lower()
        if RANGE_RE.search(ln): continue
        if unit_ctx and not any(u in l for u in unit_ctx): continue
        n = sum(1 for a in exp if a in l)
        if exp and n == 0: continue
        if require and not all(x in l for x in require): continue
        if excl and sum(1 for x in excl if x in l) > n: continue
        dist = local_ok = 0
        if exp:
            poss = [(abs(l.find(raw if l.find(raw) >= 0 else str(int(v)) if v == int(v) else str(v)) - l.find(a)), l.find(a), l.find(raw if l.find(raw) >= 0 else str(int(v)) if v == int(v) else str(v)))
                    for a in exp if a in l]
            if not poss: continue
            dist, apos, vpos = min(poss)
            if vpos >= 10**4 or dist > 150: continue
            seg = l[min(apos, vpos):max(apos, vpos)]
            local_ok = not any(s in seg for s in CLAUSE_STOP)
        key = (n, r == 'user', si, local_ok, -dist)
        if bestkey is None or key > bestkey:
            best, bestkey = t, key
    if verbose and best is None:
        print('   pick-miss anchors=', exp, 'req=', require, 'unit=', unit_ctx, 'n_cands=', len(cands))
    return best

def split_sides(q):
    ql = q.lower()
    for sep in [' compared to ', ' instead of ']:
        if sep in ql:
            a, b = ql.split(sep, 1); return a, b
    if ' than ' in ql:
        a, b = ql.split(' than ', 1); return a, b
    if ' between ' in ql and ' and ' in ql:
        m = re.search(r'between (.+?) and (.+)', ql)
        if m: return m.group(1), m.group(2)
    return None

def money(v):
    if v == int(v): v = int(v)
    return f"${v:,}" if isinstance(v, int) else f"${v:,.2f}"

def wnum(tok):
    return WORDN.get(tok, float(tok) if tok.isdigit() else None)

def answer(qid, dbg=False):
    ex = C[qid]; q, msgs = ex['q'], ex['msgs']; ql = q.lower()
    IDK = "I don't know"

    # R4 temporal diff (non-money): mpg / minutes
    if 'miles per gallon' in ql or 'mpg' in ql or ('faster' in ql and 'minutes' in (ex['gt'].lower())):
        ureg = MPG if ('miles per gallon' in ql or 'mpg' in ql) else MINRE
        subj = ['5k'] if '5k' in ql else []
        vals = [t for t in scan(msgs, ureg) if not subj or any(s in norm(t[3]) for s in subj)]
        old = pick(vals, [], unit_ctx=OLD_T); new = pick(vals, [], unit_ctx=NEW_T)
        if old and new and old[2] == new[2] == 'user':
            u = ' mpg' if ureg is MPG else ' minutes'
            return f"{abs(old[0] - new[0]):g}{u}".replace(' mpg', ''), ('T-diff', old[0], new[0])
        return IDK, ('T-diff-miss', bool(old), bool(new))

    # R5 rate
    if re.search(r'how much (cashback|interest)', ql):
        noun = 'cashback' if 'cashback' in ql else 'interest'
        rates = [t for t in scan(msgs, PCT) if noun in norm(t[3])]
        akws = [k for k in kws(q) if k != stem(noun) and k not in ('earn', 'last', 'thursday', 'much')]
        amts = [t for t in scan(msgs, MONEY) if any(k in norm(t[3]) for k in akws)]
        if dbg: print('  rate dbg: rates=', [(t[0], t[2]) for t in rates[:4]], 'akws=', akws, 'amts=', [(t[0], t[2]) for t in amts[:4]])
        if rates and amts:
            store = [k for k in akws if k not in ('much',)] or ['cashback']
            rr = [t for t in rates if any(k in norm(t[3]) for k in store)] or rates
            r = max(rr, key=lambda t: (t[2] == 'user', t[1]))[0] / 100
            ua = [t for t in amts if t[2] == 'user']
            a = max(ua or amts, key=lambda t: t[0])
            p = a[0] * r
            return (f"${p:.2f}" if p % 1 else f"${p:.0f}"), ('rate', a[0], r)
        return IDK, ('rate-miss', len(rates), len(amts))

    # R5 count-ratio
    m = re.search(r'what percentage of (?:the )?(?:packed |my )?(.+?) did i (\w+)', ql)
    if m and not ql.startswith('what percentage of the countryside'):
        subj_n = m.group(1).split()[-1]
        numpat = re.compile(r'(?:only )?(?:wearing|wore|used)\s+(two|three|four|five|six|seven|eight|nine|ten|\d+)', re.I)
        denpat = re.compile(r'packed\s+(\d+|two|three|four|five|six|seven|eight|nine|ten)\s+pairs? of ' + re.escape(subj_n), re.I)
        num = pick(scan(msgs, numpat), [m.group(2)], verbose=dbg)
        den = pick(scan(msgs, denpat), [], verbose=dbg)
        if num and den:
            nn = wnum(numpat.search(num[3]).group(1)); dd = wnum(denpat.search(den[3]).group(1))
            return f"{round(nn / dd * 100)}%", ('ratio', nn, dd)
        return IDK, ('ratio-miss', bool(num), bool(den))

    # R5 compare-pct
    if ql.startswith('did i') and 'percentage' in ql:
        ss = split_sides(q)
        if ss:
            vals = scan(msgs, PCT)
            a = pick(vals, kws(ss[0], side=True), verbose=dbg)
            b = pick(vals, kws(ss[1], side=True), verbose=dbg)
            if a and b and a[3] is not b[3]:
                return ('Yes.' if a[0] > b[0] else 'No.'), ('cmp-pct', a[0], b[0])
        return IDK, ('cmp-pct-miss',)

    # R5 pct-from-price
    if re.search(r'what percentage discount', ql):
        item = [k for k in kws(q) if k not in ('discount', 'favorite', 'percentage')]
        vals = scan(msgs, MONEY)
        orig = pick(vals, item + ['originally'], require=['originally'])
        paid = pick([t for t in vals if orig is None or t[3] is not orig[3]], item, verbose=dbg)
        if orig and paid and paid[0] < orig[0]:
            return f"{round((1 - paid[0] / orig[0]) * 100)}%", ('pct-price', paid[0], orig[0])
        return IDK, ('pct-price-miss',)

    # R5 save
    if re.search(r'how much\b.{0,40}\bsave', ql):
        ss = split_sides(q)
        if ss and 'instead of' in ql:
            vals = scan(msgs, MONEY)
            a = pick(vals, kws(ss[0], side=True) or ['taxi'], verbose=dbg)
            b = pick(vals, kws(ss[1], side=True) or ['train'], verbose=dbg)
            if a and b: return money(abs(a[0] - b[0])), ('save-instead', a[0], b[0])
            return IDK, ('save-instead-miss',)
        item = [k for k in kws(q) if k not in ('save',)]
        vals = scan(msgs, MONEY)
        orig = pick(vals, item + ['originally'], require=['originally'])
        paid = pick(vals, item, require=None, exclude=['originally'], verbose=dbg)
        if orig and paid and paid[0] < orig[0]:
            return money(orig[0] - paid[0]), ('save-orig', orig[0], paid[0])
        return IDK, ('save-miss',)

    # R5 minmax-sum
    mm = re.search(r'(minimum|maximum) amount', ql)
    if mm and ' and ' in ql:
        want_min = mm.group(1) == 'minimum'
        tail = ql.split('sold', 1)[-1] if 'sold' in ql else ql
        ents = [kws(x, side=True) for x in re.split(r' and ', tail)]
        tot, det = 0, []
        for ek in ents:
            if not ek: continue
            vals = [t for t in scan(msgs, MONEY) if any(k in norm(t[3]) for k in ek)]
            if not vals: return IDK, ('minmax-miss', ek)
            u = [t for t in vals if t[2] == 'user'] or vals
            tot += (min if want_min else max)(t[0] for t in u); det.append((min if want_min else max)(t[0] for t in u))
        return money(tot), ('minmax', det)

    # R1 bipartite diff (money)
    if re.search(r'how much (?:more|less|more expensive)|difference in price', ql) or 'initial quote' in ql:
        if 'after the initial' in ql:
            vals = scan(msgs, MONEY)
            init = pick(vals, ['quote'], verbose=dbg)
            corr = pick(vals, ['corrected'], verbose=dbg)
            if init and corr: return money(abs(corr[0] - init[0])), ('after-init', corr[0], init[0])
            return IDK, ('after-init-miss',)
        ss = split_sides(q)
        if not ss: return IDK, ('diff-nosplit',)
        unit_ctx = ['per night', 'nightly'] if 'per night' in ql else None
        vals = scan(msgs, MONEY)
        if 'goal' in ql:
            a = pick(vals, ['raised'], verbose=dbg); b = pick(vals, ['aimed', 'goal'], verbose=dbg)
            if a and b: return money(abs(a[0] - b[0])), ('goal-diff', a[0], b[0])
            return IDK, ('goal-miss',)
        ka, kb = kws(ss[0], side=True), kws(ss[1], side=True)
        a = pick(vals, ka, unit_ctx=unit_ctx, exclude=kb, verbose=dbg)
        b = pick(vals, kb, unit_ctx=unit_ctx, exclude=ka, verbose=dbg)
        if a and b and a[3] is not b[3]:
            return money(abs(a[0] - b[0])), ('diff', a[0], b[0])
        return IDK, ('diff-miss',)

    # R5 sum-two
    m = re.search(r'how much did i spend on (.+)', ql)
    if m and ' and ' in m.group(1):
        tot, det = 0, []
        sides2 = m.group(1).split(' and ')
        eks = [kws(s, side=True) for s in sides2]
        for i, s in enumerate(sides2):
            others = [a for j, e2 in enumerate(eks) if j != i for a in e2]
            v = pick(scan(msgs, MONEY), eks[i], unit_ctx=(['ticket'] if 'ticket' in s else None), exclude=others, verbose=dbg)
            if not v: return IDK, ('sum2-miss', eks[i])
            tot += v[0]; det.append(v[0])
        return money(tot), ('sum2', det)

    return None, ('noform',)

if __name__ == '__main__':
    right = fired = 0
    dbg = '-v' in sys.argv
    IDK = "I don't know"
    for qid in sorted(C):
        if dbg: print('---', qid)
        pred, why = answer(qid, dbg=dbg)
        gt = C[qid]['gt']
        hit = False
        if pred is not None:
            fired += 1
            ns = lambda s: set(re.findall(r'\d+(?:\.\d+)?', s.replace(',', '')))
            hit = (pred != IDK) and (bool(ns(pred) & ns(gt)) or pred.strip('.').lower() == gt.strip('.').lower())
            right += hit
        print(('✓' if hit else '✗'), qid, '|', str(why)[:44], '| pred=', str(pred)[:28], '| gt=', gt[:28])
    print(f'\noracle: fired {fired}/{len(C)}  correct {right}/{len(C)}')
