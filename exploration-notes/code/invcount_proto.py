#!/usr/bin/env python3
"""Research #084 prototype v1: inventory/entity enumeration counting (zero-LLM).

Sub-family of multi_session "How many X" questions where the count is over
NAMED/SIGNED entities (babies, tanks, weddings, festivals...), NOT over
hyponym-gap types (clothing items). Mechanism:
  1. form-gate: "how many" + countable noun head
  2. candidate lines = user lines (oracle evidence = answer sessions) containing
     the noun stem  -> hyponym-gap questions naturally fire 0 lines -> abstain
  3. entity signature extraction (named X / N-unit size / number-adjacent)
  4. dedup by signature; twins x2; count
Oracle evidence ceiling experiment (production retrieval differs, evhit 0.955).
"""
import json, re, sys
from collections import defaultdict

NUMWORDS = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,
            'eleven':11,'twelve':12,'fifteen':15,'twenty':20,'thirty':30,'fifty':50,'hundred':100,
            'a':1,'an':1,'first':1,'second':2,'third':3}

def noun_stem(noun):
    n = noun.lower()
    for suf in ('ies',):
        if n.endswith(suf): return n[:-3] + 'y'
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

def line_candidates(lines, stem):
    return [l for l in lines if stem and stem in l.lower()]

def sig_extract(line, stem):
    """Extract countable signatures from one candidate line."""
    sigs = []
    low = line.lower()
    # 1. "named X" / "name is X" proper-name births
    for m in re.finditer(r'(?:named|calling|called)\s+([A-Z][a-z]+)', line):
        sigs.append(('name', m.group(1)))
    # 2. N-unit size signatures: 20-gallon, 5-gallon
    for m in re.finditer(r'\b(\d+)[- ]?(gallon|liter|inch|foot|pound|kg|gb|tb|acre|bedroom)\b', low):
        sigs.append(('size', m.group(1) + m.group(2)))
    # 3. number-adjacent-to-stem: "three weddings", "2 tanks"
    for m in re.finditer(r'\b(\d+|' + '|'.join(NUMWORDS) + r')\s+' + stem, low):
        v = m.group(1)
        sigs.append(('num', int(v) if v.isdigit() else NUMWORDS[v]))
    # 4. possessive/name-before-stem: "Rachel's baby", "Mike and Emma's daughter"
    for m in re.finditer(r"\b([A-Z][a-z]+)(?:\s+and\s+[A-Z][a-z]+)?'s\s+[a-z]*\s*" + stem, line):
        sigs.append(('poss', m.group(1)))
    # 5. twins
    if re.search(r'\btwins\b', low): sigs.append(('twins', 2))
    return sigs

def count_signatures(all_sigs):
    names = {s[1] for s in all_sigs if s[0] in ('name','poss')}
    sizes = {s[1] for s in all_sigs if s[0]=='size'}
    nums  = [s[1] for s in all_sigs if s[0]=='num']
    twins = any(s[0]=='twins' for s in all_sigs)
    n_names = len(names)
    if twins: n_names += 1  # twins keyword adds 1 extra baby
    return names, sizes, nums, twins, n_names

def answer(q, lines):
    stem_raw = extract_qnoun(q)
    if not stem_raw: return None, 'no-noun'
    stem = noun_stem(stem_raw)
    cands = line_candidates(lines, stem)
    if not cands: return None, 'no-cand'   # hyphen-gap -> honest abstain
    all_sigs = []
    for l in cands: all_sigs.extend(sig_extract(l, stem))
    if not all_sigs: return None, 'no-sig'
    names, sizes, nums, twins, n_names = count_signatures(all_sigs)
    # decision ladder: size-signatures first (tanks), then names, then max(num)
    if sizes: return len(sizes), f'sizes={sorted(sizes)}'
    if names: return n_names, f'names={sorted(names)}'
    if nums: return max(nums), f'nums={nums}'
    return None, 'undecided'

def gt_num(gt):
    if isinstance(gt, int): return gt
    g = str(gt)
    m = re.search(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|fifty|hundred)\b', g.lower())
    if not m: return None
    w = m.group(1)
    return int(w) if w.isdigit() else NUMWORDS.get(w)

def main():
    with open('/tmp/lme_s.json') as f:
        data = json.load(f)
    c499 = json.load(open('/tmp/c499/lme_s_full500_c499.json'))
    wrong_ms = {r['question_id'] for r in c499['results']
                if r.get('category','').startswith('multi') and not r.get('correct')}
    byid = {d['question_id']: d for d in data}
    hits = fired = 0
    rows = []
    for d in data:
        qid = d['question_id']
        if not qid in wrong_ms: continue
        if not re.search(r'how many', d['question'].lower()): continue
        ans_ids = set(d['answer_session_ids'])
        lines = [m['content'] for s,sid in zip(d['haystack_sessions'], d['haystack_session_ids'])
                 if sid in ans_ids for m in s if m.get('role')=='user' and len(m.get('content',''))>3]
        pred, why = answer(d['question'], lines)
        gtn = gt_num(d['answer'])
        is_abs_q = qid.endswith('_abs') or 'insufficient' in str(d['answer']).lower() or 'not mention' in str(d['answer']).lower()
        fired += pred is not None
        ok = (pred == gtn) if pred is not None else False
        hits += ok
        rows.append((qid[:14], d['question'][:58], pred, gtn, why[:40], is_abs_q))
    print(f"entity-count wrong-q pool: {len(rows)} | fired: {fired} | correct: {hits} | fire-prec: {hits/max(fired,1):.2f}")
    for r in rows:
        flag = 'OK ' if r[2]==r[3] else ('AB ' if r[2] is None else 'XX ')
        print(f"{flag}{r[0]:15s} pred={str(r[2]):5s} gt={str(r[3]):5s} {r[4]:42s} {r[1]}")

if __name__ == '__main__':
    main()
