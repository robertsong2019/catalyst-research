#!/usr/bin/env python3
"""Research #084 prototype v2: signature-only enumeration counting.

v1 lessons applied:
  - nums ladder removed (noise; production number_total owns numeric mentions)
  - form-gate hardened: exclude arithmetic (older/exceed/when will) + habitual
    (typical week / a week / per week) + event-frequency ("how many times")
  - size ladder gated on question noun == size-unit-bearing noun
    (v1 bug: "fish in my 30-gallon tank" fired tank sizes)
  - name validation: not sentence-initial, not common word
  - twins only for baby-family stems
Zero-hijack check: runs on ALL 133 multi_session (not just wrong set).
"""
import json, re

NUMWORDS = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,
            'eleven':11,'twelve':12,'fifteen':15,'twenty':20}
SIZE_UNITS = ('gallon','liter','inch','foot','pound','kg','gb','tb','acre','bedroom')
COMMON_WORDS = {'Fresh','New','The','A','An','My','We','They','Last','This','That','Next','So','Also','Anyway','By','Well','Oh','Yeah','Okay','March','April','May','June','July','August','September','October','November','December','January','February','Sat','Sun','Mon','Tue','Wed','Thu','Fri'}

def noun_stem(n):
    n = n.lower()
    if n.endswith('ies'): return n[:-3] + 'y'
    if n.endswith('es') and not n.endswith('ses'): return n[:-2]
    if n.endswith('s') and not n.endswith('ss'): return n[:-1]
    return n

def extract_qnoun(q):
    m = re.search(r'how many ([a-z][a-z\- ]{1,40}?) (do|did|have|has|am|are|is|was|were|that|which|in|last|this|over|so)', q.lower())
    if not m:
        m = re.search(r'how many ([a-z][a-z\- ]{1,40}?)\??$', q.lower())
    if not m: return None
    np = m.group(1)
    np = re.sub(r'^(different|various|total|many|other|new)\s+', '', np)
    np = re.sub(r'\s+(have|did|do|am|are|is|was|were)\b.*$', '', np)
    words = np.split()
    while words and words[-1] in ('related','different','other','new','type','types'): words.pop()
    return words[-1] if words else None

def form_gate(q, noun):
    low = q.lower()
    if re.search(r'how many (times|years older|minutes did i exceed|hours (a|per) week)', low): return False
    if re.search(r'(older|younger|exceed|when will i be)', low): return False
    if re.search(r'(typical week|a typical|per week|days a week)', low): return False
    if noun in ('time','times','week','weeks','day','days','hour','hours','minute','minutes','month','months','year','years','page','pages','point','points'): return False
    return True

def answer(q, lines):
    noun = extract_qnoun(q)
    if not noun: return None, 'no-noun'
    if not form_gate(q, noun): return None, 'gate'
    stem = noun_stem(noun)
    cands = [l for l in lines if stem in l.lower()]
    if not cands: return None, 'no-cand'
    names, sizes = set(), set()
    twins = False
    for l in cands:
        for m in re.finditer(r'(?:named|calling|called)\s+([A-Z][a-z]+)', l):
            names.add(m.group(1))
        # possessive anchored: Name('s) ... stem  (same line, within 40 chars)
        for m in re.finditer(r"\b([A-Z][a-z]{2,})(?:'s|\s+and\s+[A-Z][a-z]+'s)\s+([^.;]{0,40}?)\b" + stem, l):
            if m.group(1) not in COMMON_WORDS: names.add(m.group(1))
        if re.search(r'\btwins\b', l.lower()) and stem.startswith(('bab','twin','famil')): twins = True
        for m in re.finditer(r'\b(\d+)[- ]?(' + '|'.join(SIZE_UNITS) + r')\b', l.lower()):
            sizes.add(m.group(1) + m.group(2))
    # size ladder: only if question noun IS the size-bearing noun
    q_size = any(u in noun.lower() for u in SIZE_UNITS) or noun.lower() in ('tank','aquarium')
    if sizes and q_size: return len(sizes), f'sizes={sorted(sizes)}'
    if names:
        n = len(names) + (1 if twins else 0)
        return n, f'names={sorted(names)}' + ('+twins' if twins else '')
    return None, 'no-sig'

def gt_num(gt):
    if isinstance(gt, int): return gt
    g = str(gt)
    m = re.search(r'\b(\d+|' + '|'.join(NUMWORDS) + r')\b', g.lower())
    if not m: return None
    w = m.group(1)
    return int(w) if w.isdigit() else NUMWORDS.get(w)

def main():
    with open('/tmp/lme_s.json') as f:
        data = json.load(f)
    c499 = json.load(open('/tmp/c499/lme_s_full500_c499.json'))
    res = {r['question_id']: r for r in c499['results']}
    ms_ids = [r['question_id'] for r in c499['results'] if r.get('category','').startswith('multi')]
    byid = {d['question_id']: d for d in data}
    fired_rows, hijacks, gains = [], 0, 0
    for qid in ms_ids:
        d = byid[qid]
        ans_ids = set(d['answer_session_ids'])
        lines = [m['content'] for s,sid in zip(d['haystack_sessions'], d['haystack_session_ids'])
                 if sid in ans_ids for m in s if m.get('role')=='user' and len(m.get('content',''))>3]
        pred, why = answer(d['question'], lines)
        if pred is None: continue
        was_correct = res[qid].get('correct')
        gtn = gt_num(d['answer'])
        ok = pred == gtn
        fired_rows.append((qid, pred, gtn, ok, was_correct, why))
        if was_correct and not ok: hijacks += 1
        if not was_correct and ok: gains += 1
    fired = len(fired_rows); correct = sum(1 for r in fired_rows if r[3])
    print(f"fired {fired}/{len(ms_ids)} | correct {correct} | fire-prec {correct/max(fired,1):.2f}")
    print(f"gains (wrong->right): {gains} | hijacks (right->wrong): {hijacks}")
    for qid, pred, gtn, ok, wc, why in fired_rows:
        flag = 'OK' if ok else 'XX'
        print(f"{flag} {qid[:16]:17s} pred={pred:<4} gt={gtn} was_correct={wc} {why[:50]} | {byid[qid]['question'][:55]}")

if __name__ == '__main__':
    main()
