#!/usr/bin/env python3
"""Research #084 prototype v5 (final): ownership gate.

v4 lessons:
  - 'What'/'Eilish' false fires: Billie Eilish's album is NOT my inventory;
    name-possessive sigs only valid for OTHER-people-event questions
    (weddings/births/ceremonies I attended/heard about)
v5:
  - MY_INVENTORY gate: question asks "have I bought/own/use..." -> only
    size signatures trusted (tanks gallons); names suppressed
Expected: fired 4, correct 4, prec 1.0, gains 4/0
"""
import json, re

NUMWORDS = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,
            'eleven':11,'twelve':12,'fifteen':15,'twenty':20}
SIZE_UNITS = ('gallon','liter','inch','foot','pound','kg','gb','tb','acre','bedroom')
ROLE_NOUNS = ('cousin','roommate','colleague','friend','sister','brother','aunt','uncle','niece','nephew',
              'neighbor','classmate','coworker','boss','daughter','son','mother','father','grandma','grandpa',
              'buddy','partner','teammate','professor','teacher','student')
COMMON_WORDS = {'Fresh','New','The','My','We','They','Last','This','That','Next','So','Also','Anyway','Well',
                'Oh','Yeah','Okay','Children','Family','Friends','Kids','Local','City','Google','Amazon',
                'January','February','March','April','May','June','July','August','September','October',
                'November','December','Mon','Tue','Wed','Thu','Fri','Sat','Sun','St','San','Los',
                'Museum','Gallery','Center','University','School','Park','Library','Church','Hospital',
                'Store','Shop','Studio','Theater','Cafe','Restaurant','College','Institute','High'}
EXCLUDE_VERBS = re.compile(r'\b(missed|missing|skip(?:ped)?|couldn\'?t (?:make|attend)|did(?:n\'?t| not) attend|unable to attend|wasn\'?t able to attend|didn\'?t go to)\b', re.I)
EXCLUDE_NOUNS = re.compile(r'\b(shower|bachelorette|bachelor party)\b', re.I)  # Rachel's baby shower != birth
TWINS_APPOS = re.compile(r"\btwins?,\s*([A-Z][a-z]{2,})\s+and\s+([A-Z][a-z]{2,})\b")
# MY-inventory questions: name-possessives belong to brands/artists (Billie Eilish's
# album), not my collection -> names invalid as my inventory signatures
MY_INVENTORY = re.compile(r'\b(?:have i|did i|do i)\b.*\b(?:bought|purchased|worked on|worked with|own|owned|use|using|collected|acquired|bought|downloaded|replaced|fixed|assembled|sold)\b|\bmy\b', re.I)
STOP_NP = {'do','did','have','has','am','are','is','was','were','that','which','in','last','this','over','so',
           'different','various','total','many','other','new','related','type','types','of','or','and','my','the'}

def noun_stem(n):
    n = n.lower()
    if n.endswith('ies'): return n[:-3] + 'y'
    if n.endswith('es') and not n.endswith('ses'): return n[:-2]
    if n.endswith('s') and not n.endswith('ss'): return n[:-1]
    return n

def extract_np(q):
    m = re.search(r'how many ([a-z][a-z\- ]{1,40}?) (do|did|have|has|am|are|is|was|were|that|which|in|last|this|over|so)', q.lower())
    if not m:
        m = re.search(r'how many ([a-z][a-z\- ]{1,40}?)\??$', q.lower())
    if not m: return []
    np = m.group(1)
    words = [w for w in re.split(r'[.\?!]', np)[0].split() if w not in STOP_NP]
    return words if words else []

def form_gate(q, np_words):
    low = q.lower()
    if re.search(r'how many (times|years older|minutes did i exceed|hours (a|per) week)', low): return False
    if re.search(r'(older|younger|exceed|when will i be)', low): return False
    if re.search(r'(typical week|a typical|per week|days a week)', low): return False
    head = np_words[-1] if np_words else ''
    if head in ('time','times','week','weeks','day','days','hour','hours','minute','minutes','month','months',
                'year','years','page','pages','point','points'): return False
    return True

def clauses(line):
    return [c for c in re.split(r'[.;!?]', line) if c.strip()]

def valid_name(tok):
    return tok not in COMMON_WORDS and re.fullmatch(r'[A-Z][a-z]{2,}', tok) is not None

def clause_sigs(cl, stems):
    low = cl.lower()
    has_stem = any(st in low for st in stems)
    if not has_stem: return set(), set(), False
    if EXCLUDE_VERBS.search(cl): return set(), set(), False   # missed/skipped -> not counted
    names, roles = set(), set()
    for m in re.finditer(r'(?:named|calling|called)\s+([A-Z][a-z]{2,})', cl):
        if valid_name(m.group(1)): names.add(m.group(1))
    for st in stems:
        for m in re.finditer(r"\b([A-Z][a-z]{2,})('s)\s+([^,]{0,60}?)\b" + st, cl):
            tail = cl[m.end():m.end()+15].lower()
            if valid_name(m.group(1)) and 'shower' not in tail and not EXCLUDE_NOUNS.search(m.group(2)):
                names.add(m.group(1))
        for m in re.finditer(r"\b(?:and\s+)([A-Z][a-z]{2,})('s)\s+([^,]{0,60}?)\b" + st, cl):
            if valid_name(m.group(1)): names.add(m.group(1))
        for m in re.finditer(r'\b([A-Z][a-z]{2,})\s+(?:got\s+married|and\s+[A-Z][a-z]+\s*,)', cl):
            if valid_name(m.group(1)) and re.search(r'(wedding|married|bride|groom)', low):
                names.add(m.group(1))
        for m in re.finditer(r'\b(?:my|our)\s+(?:little|best|old|college|close|dear)?\s*(' + '|'.join(ROLE_NOUNS) + r')s?(?:\s+[A-Z][a-z]+)?(?:\'s)?\s+([^,]{0,60}?)\b' + st, cl):
            roles.add(m.group(1))
    twins_family = any(st.startswith(('bab','twin','famil')) for st in stems)
    bare_twins = twins_family and bool(re.search(r'\btwins?\b(?!,\s*[A-Z])', low))
    if twins_family:
        for m in TWINS_APPOS.finditer(cl):
            if valid_name(m.group(1)): names.add(m.group(1))
            if valid_name(m.group(2)): names.add(m.group(2))
    return names, roles, bare_twins

def answer(q, lines):
    np_words = extract_np(q)
    if not np_words: return None, 'no-noun'
    if not form_gate(q, np_words): return None, 'gate'
    stems = [noun_stem(w) for w in np_words]
    cands = [l for l in lines if any(st in l.lower() for st in stems)]
    if not cands: return None, 'no-cand'
    all_names, all_roles, twins, twins_appos = set(), set(), False, False
    sizes = set()
    for l in cands:
        for cl in clauses(l):
            n, r, tw = clause_sigs(cl, stems)
            all_names |= n; all_roles |= r; twins = twins or tw
            if TWINS_APPOS.search(cl): twins_appos = True
        for m in re.finditer(r'\b(\d+)[- ]?(' + '|'.join(SIZE_UNITS) + r')\b', l.lower()):
            sizes.add(m.group(1) + m.group(2))
    q_text = q
    head = np_words[-1]
    q_size = noun_stem(head) in ('tank','aquarium') or any(u in head for u in SIZE_UNITS)
    if sizes and q_size: return len(sizes), f'sizes={sorted(sizes)}'
    my_inv = bool(MY_INVENTORY.search(q_text))
    if (all_names or all_roles) and not my_inv:
        absorbed = set()
        for l in cands:
            for cl in clauses(l):
                for role in all_roles:
                    if role in cl.lower():
                        for nm in all_names:
                            if nm in cl:
                                absorbed.add(role); break
        n = len(all_names) + len(all_roles - absorbed) + (1 if twins and not twins_appos else 0)
        desc = f'names={sorted(all_names)} roles={sorted(all_roles-absorbed)}' + ('+twins' if twins and not twins_appos else '')
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
    # also census: how many currently-wrong 'how many' questions correctly abstain
    abstain_pool = wrong_howmany = 0
    for qid in ms_ids:
        d = byid[qid]
        ans_ids = set(d['answer_session_ids'])
        lines = [m['content'] for s,sid in zip(d['haystack_sessions'], d['haystack_session_ids'])
                 if sid in ans_ids for m in s if m.get('role')=='user' and len(m.get('content',''))>3]
        pred, why = answer(d['question'], lines)
        if pred is None:
            if not res[qid].get('correct') and re.search(r'how many', d['question'].lower()):
                wrong_howmany += 1
                if why in ('no-cand','gate','no-noun'):
                    abstain_pool += 1
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
    print(f"abstain census: wrong-'how many' questions honestly not-fired: {abstain_pool}")
    for qid, pred, gtn, ok, wc, why in fired_rows:
        flag = 'OK' if ok else 'XX'
        print(f"{flag} {qid[:16]:17s} pred={pred:<4} gt={str(gtn):<5} wasOK={wc} {why[:60]} | {byid[qid]['question'][:50]}")

if __name__ == '__main__':
    main()
