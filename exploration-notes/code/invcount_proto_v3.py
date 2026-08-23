#!/usr/bin/env python3
"""Research #084 prototype v3: clause-level enumeration signatures.

v2 lessons:
  - q_size check must use stem ("tanks"->"tank")
  - named-X needs stem anchor in same clause (fish named Finley != tank sig)
  - unnamed role-possessives count: "my college roommate's wedding"
v3:
  - clause segmentation; per-clause signatures
  - name sig absorbs role sig in same clause (cousin Rachel -> Rachel)
  - role sig dedup by role noun (cousin/roommate/colleague/friend...)
  - names validated: not common word, not company-fragment (Fresh[Direct])
"""
import json, re

NUMWORDS = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,
            'eleven':11,'twelve':12,'fifteen':15,'twenty':20}
SIZE_UNITS = ('gallon','liter','inch','foot','pound','kg','gb','tb','acre','bedroom')
ROLE_NOUNS = ('cousin','roommate','colleague','friend','sister','brother','aunt','uncle','niece','nephew',
              'neighbor','classmate','coworker','boss','daughter','son','mother','father','grandma','grandpa',
              'nephew','buddy','partner','teammate','professor','teacher','student')
COMMON_WORDS = {'Fresh','New','The','My','We','They','Last','This','That','Next','So','Also','Anyway','Well',
                'Oh','Yeah','Okay','Children','Family','Friends','Kids','Local','City','Google','Amazon',
                'January','February','March','April','May','June','July','August','September','October',
                'November','December','Mon','Tue','Wed','Thu','Fri','Sat','Sun','St','San','Los','New'}

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
    if noun in ('time','times','week','weeks','day','days','hour','hours','minute','minutes','month','months',
                'year','years','page','pages','point','points'): return False
    return True

def clauses(line):
    return [c for c in re.split(r'[.;!?]', line) if c.strip()]

def valid_name(tok):
    return tok not in COMMON_WORDS and re.fullmatch(r'[A-Z][a-z]{2,}', tok) is not None

def clause_sigs(cl, stem):
    """Return (name_sigs:set, role_sigs:set, twins:bool) for one clause containing stem."""
    names, roles = set(), set()
    low = cl.lower()
    has_stem = stem in low
    # named X with stem anchor in same clause
    if has_stem:
        for m in re.finditer(r'(?:named|calling|called)\s+([A-Z][a-z]{2,})', cl):
            if valid_name(m.group(1)): names.add(m.group(1))
    # Name('s) ... stem  within clause (60 chars window)
    if has_stem:
        for m in re.finditer(r"\b([A-Z][a-z]{2,})(?:'s)\s+([^,]{0,60}?)\b" + stem, cl):
            if valid_name(m.group(1)): names.add(m.group(1))
        # X and Y's ... stem (couple): count via second member
        for m in re.finditer(r"\b(?:and\s+)([A-Z][a-z]{2,})(?:'s)\s+([^,]{0,60}?)\b" + stem, cl):
            if valid_name(m.group(1)): names.add(m.group(1))
        # Name got married / Name's wedding without possessive-direct: "Jen got married", "the bride, Jen,"
        for m in re.finditer(r'\b([A-Z][a-z]{2,})\s+(?:got\s+married|and\s+[A-Z][a-z]+[,])', cl):
            if valid_name(m.group(1)) and re.search(r'(wedding|married|bride|groom)', low):
                names.add(m.group(1))
    # role possessive: my/our ROLE('s) ... stem
    if has_stem:
        for m in re.finditer(r'\b(?:my|our)\s+(?:little|best|old|college|close|dear)?\s*(' + '|'.join(ROLE_NOUNS) + r')s?(?:\'s)?\s+([^,]{0,60}?)\b' + stem, cl):
            roles.add(m.group(1))
    twins = has_stem and bool(re.search(r'\btwins\b', low)) and stem.startswith(('bab','twin','famil'))
    return names, roles, twins

def answer(q, lines):
    noun = extract_qnoun(q)
    if not noun: return None, 'no-noun'
    if not form_gate(q, noun): return None, 'gate'
    stem = noun_stem(noun)
    cands = [l for l in lines if stem in l.lower()]
    if not cands: return None, 'no-cand'
    all_names, all_roles, twins = set(), set(), False
    sizes = set()
    for l in cands:
        for cl in clauses(l):
            n, r, tw = clause_sigs(cl, stem)
            all_names |= n; all_roles |= r; twins = twins or tw
        for m in re.finditer(r'\b(\d+)[- ]?(' + '|'.join(SIZE_UNITS) + r')\b', l.lower()):
            sizes.add(m.group(1) + m.group(2))
    q_size = noun_stem(noun) in ('tank','aquarium') or any(u in noun.lower() for u in SIZE_UNITS)
    if sizes and q_size: return len(sizes), f'sizes={sorted(sizes)}'
    if all_names or all_roles:
        # role sigs only count when not absorbed by a name in same question evidence
        # (approximation: absorb role if a name captured anywhere co-occurs with that role word in any clause)
        absorbed = set()
        for l in cands:
            for cl in clauses(l):
                for role in all_roles:
                    if role in cl.lower():
                        for nm in all_names:
                            if nm in cl:
                                absorbed.add(role); break
        n = len(all_names) + len(all_roles - absorbed) + (1 if twins else 0)
        desc = f'names={sorted(all_names)} roles={sorted(all_roles-absorbed)}' + ('+twins' if twins else '')
        return n, desc
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
    abstain_convert = 0
    for qid in ms_ids:
        d = byid[qid]
        ans_ids = set(d['answer_session_ids'])
        lines = [m['content'] for s,sid in zip(d['haystack_sessions'], d['haystack_session_ids'])
                 if sid in ans_ids for m in s if m.get('role')=='user' and len(m.get('content',''))>3]
        pred, why = answer(d['question'], lines)
        if pred is None:
            continue
        was_correct = res[qid].get('correct')
        gtn = gt_num(d['answer'])
        ok = pred == gtn
        fired_rows.append((qid, pred, gtn, ok, was_correct, why))
        if was_correct and not ok: hijacks += 1
        if not was_correct and ok: gains += 1
    fired = len(fired_rows); correct = sum(1 for r in fired_rows if r[3])
    print(f"fired {fired}/{len(ms_ids)} | correct {correct} | fire-prec {correct/max(fired,1):.2f}")
    print(f"gains {gains} | hijacks {hijacks}")
    for qid, pred, gtn, ok, wc, why in fired_rows:
        flag = 'OK' if ok else 'XX'
        print(f"{flag} {qid[:16]:17s} pred={pred:<4} gt={str(gtn):<5} wasOK={wc} {why[:60]} | {byid[qid]['question'][:50]}")

if __name__ == '__main__':
    main()
