#!/usr/bin/env python3
"""
msagg_proto.py — Multi-Session Answer-Side Aggregation prototype (zero LLM)

Form-triggered deterministic aggregation for LongMemEval multi-session questions.
Three sub-mechanisms (C456/C457 pattern: form decides mechanism, no fabrication):

  1. DURATION_SUM   "How many days/weeks did I spend ..." → extract typed durations
                    from user turns, dedup by context key, sum.
  2. ENTITY_COUNT   "How many <plural noun> have I ..."  → count distinct named
                    instances of the category in user turns (enumeration aware).
  3. TOTAL_SUM      "How much total ... / What is the total ..." → extract $ amounts
                    from user turns, dedup mentions, sum.

Eval harness: fires only when mechanism is confident; otherwise None (fall through
to existing answer path — no fabrication, C457 rule).

Usage: python3 msagg_proto.py [--eval] [--samples N]
"""
import json, re, sys
from collections import defaultdict

WORD2NUM = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
            'twelve': 12, 'fifteen': 15, 'twenty': 20, 'thirty': 30}

# ---------- question form detection ----------

def detect_form(question: str) -> str:
    q = question.strip()
    if re.search(r'\b(days?|weeks?)\b.*\b(spend|spendt|spent|take|took|it take)\b', q, re.I) \
       or re.match(r'^How many (days|weeks)', q, re.I):
        return 'duration_sum'
    if re.match(r'^How (much|many)', q, re.I) and re.search(r'\btotal\b', q, re.I):
        return 'total_sum'
    if re.match(r'^How many\b', q, re.I):
        return 'entity_count'
    return 'none'

# ---------- duration extraction ----------

DUR_PATTERNS = [
    # "5-day", "three day", "7-day" ... + trailing noun (trip/trek/hike/camping)
    (r'\b(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*(day|week)s?\b', 'n_unit'),
    # "a week and a half"
    (r'\ba\s+week\s+and\s+a\s+half\b', 'week_half'),
    # "two weeks" plain
]
UNIT_DAYS = {'day': 1.0, 'week': 7.0}

def _num(tok: str):
    tok = tok.lower()
    if tok in WORD2NUM:
        return float(WORD2NUM[tok])
    try:
        return float(tok)
    except ValueError:
        return None

def extract_durations_days(text: str):
    """Return list of (days, context_key, matched_span)."""
    out = []
    # "a week and a half" first (compound)
    for m in re.finditer(r'\b(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*(day|week)s?\b', text, re.I):
        n = _num(m.group(1))
        if n is None:
            continue
        unit = m.group(2).lower()
        days = n * UNIT_DAYS[unit]
        # context key: up to 6 words after the duration (the activity noun)
        tail = text[m.end():m.end() + 60]
        tail_words = re.sub(r'[^\w\s]', ' ', tail).lower().split()
        ctx = ' '.join(tail_words[:4]) if tail_words else 'none'
        out.append((days, ctx, m.group(0)))
    # compound "a week and a half"
    for m in re.finditer(r'\ba\s+week\s+and\s+a\s+half\b', text, re.I):
        out.append((10.5, 'week and a half', m.group(0)))
    return out

STOP_CTX = {'trip', 'trips', 'to', 'the', 'in', 'and', 'a', 'an', 'of', 'for', 'my', 'at', 'on'}

def _ctx_key(ctx: str) -> str:
    words = [w for w in ctx.split() if w not in STOP_CTX]
    return words[0] if words else ctx

ACTIVITY_ANCHORS = {
    'camping', 'trip', 'trips', 'trek', 'hiking', 'road', 'vacation', 'holiday',
    'backpacking', 'visit', 'tour', 'marathon', 'binge', 'travel', 'watching',
    'watch', 'movies', 'films', 'watched',
}

def _target_family(question: str):
    """Content nouns from the question (target activity/category words)."""
    qwords = set(re.findall(r"[a-z][a-z-]+", question.lower()))
    qwords -= STOP_Q
    fam = set()
    for w in qwords:
        fam.add(w)
        fam.add(_sing(w))
        fam.add(w + 's')
    fam = {w for w in fam if len(w) >= 4}
    return fam

STOP_Q = {'many', 'much', 'have', 'does', 'did', 'that', 'this', 'with', 'from',
          'about', 'what', 'which', 'there', 'been', 'were', 'will', 'would',
          'currently', 'leading', 'worked', 'watched', 'watching', 'spent',
          'spend', 'take', 'took', 'combined', 'total', 'year', 'month', 'past'}

def _proper_nouns(text: str):
    return frozenset(w.lower() for w in re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', text)
                     if w.lower() not in ('The', 'I', 'My', 'We', 'A', 'An'))

def duration_sum(question, sessions):
    """Sum distinct typed durations from user turns (event-level dedup).

    A duration counts only if its sentence shares a target-family word with the
    question (camping question -> 'camping trip' matches, 'road trip' doesn't).
    Dedup key = (days, proper-noun set of sentence) so the same event re-told in
    a later session collapses, but two different trips never do.
    """
    q = question.lower()
    want_unit = 'days' if re.search(r'\bdays\b', q) else ('weeks' if re.search(r'\bweeks\b', q) else None)
    if want_unit is None:
        return None
    target = _target_family(question)
    events = {}  # (days, pnouns|session) -> days
    for s in sessions:
        for t in s['turns']:
            if t.get('role') != 'user':
                continue
            c = t['content']
            for m in re.finditer(r'[^.!?]*[.!?]?', c):
                sent = m.group(0).strip()
                if not sent:
                    continue
                sent_l = sent.lower()
                if not any(f in sent_l for f in target):
                    continue
                durs = extract_durations_days(sent)
                if not durs:
                    continue
                pn = _proper_nouns(sent)
                key_base = tuple(sorted(pn)) if pn else ('anon', s['session_id'])
                for days, _ctx, _span in durs:
                    events[(round(days, 2), key_base)] = days
    if not events:
        return None
    total = sum(events.values())
    val = total / (7.0 if want_unit == 'weeks' else 1.0)
    return f"{round(val,2):g} {want_unit}"

# ---------- entity counting ----------

def head_noun(question: str):
    m = re.match(r'^How many (.+?) (?:do|did|have|has) I\b', question, re.I)
    if not m:
        return None
    np = m.group(1).lower()
    np = re.sub(r'^(items? of|pieces? of|kinds? of|types? of)\s+', '', np)
    np = re.sub(r'^(different|various|distinct)\s+', '', np)
    words = [w for w in re.findall(r"[a-z][a-z-']+", np) if w not in ('of',)]
    if not words:
        return None
    return words[-1]

def _sing(noun):
    if noun.endswith('ies'):
        return noun[:-3] + 'y'
    if noun.endswith('es') and not noun.endswith('ses'):
        return noun[:-2]
    if noun.endswith('s'):
        return noun[:-1]
    return noun

def entity_count(question, sessions):
    """Count distinct named instances of the question's head noun category.

    Strategy: scan user turns; find capitalized product-like named entities
    (multi-word proper nouns / digits+scale markers); dedup case-normalized;
    count only entities in turns whose noun family co-occurs.
    Confidence gate: require >=2 distinct instances or an explicit numeral
    tied to the noun; else None.
    """
    noun = head_noun(question)
    if noun is None:
        return None
    fam = {_sing(noun), noun}
    # plural of singular too ("kit" -> also match "kits")
    fam |= {f + 's' for f in fam}
    fam = {f for f in fam if len(f) >= 3}

    per_turn_instances = []
    explicit_counts = []
    for s in sessions:
        for t in s['turns']:
            if t.get('role') != 'user':
                continue
            c = t['content']
            for m in re.finditer(r'[^.!?]*[.!?]?', c):
                sent = m.group(0).strip()
                if not sent or not any(f in sent.lower() for f in fam):
                    continue  # named instances only in fam sentences
                # explicit numeral + noun in the same sentence
                for em in re.finditer(
                        r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b'
                        r'[^\w]{0,12}(?:\w+\s+){0,2}(' + '|'.join(sorted(fam)) + r')\b', sent, re.I):
                    n = _num(em.group(1))
                    if n and n < 1000:
                        explicit_counts.append((n, em.group(0)))
                # named instances: capitalized / digit-scale-led multiword tokens
                for im in re.finditer(
                        r"\b(?:[A-Z][\w'&-]+(?:\s+(?:of|de)\s?[A-Z][\w'&-]+)*"
                        r"|1/\d+\s+scale|\d+\s+scale|[\\u2019']\d\d)"
                        r"(?:\s+(?:[A-Z][\w'&-]+|\d[\w'-]*|[\\u2019']\d\d))+", sent):
                    per_turn_instances.append(im.group(0))
    if explicit_counts:
        # prefer largest explicit self-report tied to the noun
        best = max(n for n, _ in explicit_counts)
        return str(int(best)) if float(best).is_integer() else f"{best:g}"
    # dedup named instances
    uniq = {re.sub(r'\s+', ' ', x.strip().lower()) for x in per_turn_instances}
    if len(uniq) >= 2:
        return str(len(uniq))
    return None

# ---------- total sum ----------

def total_sum(question, sessions):
    amts = set()
    for s in sessions:
        for t in s['turns']:
            if t.get('role') != 'user':
                continue
            c = t['content']
            for m in re.finditer(r'\$\s?(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', c):
                amts.add(m.group(1))
    if not amts:
        return None
    total = sum(float(a.replace(',', '')) for a in amts)
    total = round(total, 2)
    return f"${total:g}"

# ---------- answer orchestration ----------

def aggregate(question, sessions):
    form = detect_form(question)
    if form == 'duration_sum':
        return duration_sum(question, sessions), form
    if form == 'entity_count':
        return entity_count(question, sessions), form
    if form == 'total_sum':
        return total_sum(question, sessions), form
    return None, form

# ---------- judging ----------

NUMWORD = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
           'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
           'twelve': 12, 'fifteen': 15, 'twenty': 20}

def gt_number(gt: str):
    m = re.match(r'^\$?\s*([\d,]+(?:\.\d+)?)', gt.strip())
    if m:
        return float(m.group(1).replace(',', ''))
    m = re.match(r'^\$?\s*(\w+)', gt.strip().lower())
    if m and m.group(1) in NUMWORD:
        return float(NUMWORD[m.group(1)])
    return None

def pred_number(pred: str):
    if pred is None:
        return None
    m = re.match(r'^\$?\s*([\d,]+(?:\.\d+)?)', pred.strip())
    return float(m.group(1).replace(',', '')) if m else None

def judge(pred, gt) -> bool:
    p, g = pred_number(pred), gt_number(gt)
    if p is None or g is None:
        return False
    return abs(p - g) < 1e-6

# ---------- evaluation ----------

def main():
    with open('/tmp/msagg/multi_evidence_roles.json') as f:
        multi = json.load(f)
    stats = defaultdict(lambda: [0, 0, 0])  # form: [fired, correct, gt_numeric]
    show = []
    for item in multi:
        q, gt = item['question'], str(item['answer'])
        pred, form = aggregate(q, item['evidence_sessions'])
        stats[form][2] += 1
        if pred is not None:
            stats[form][0] += 1
            ok = judge(pred, gt)
            if ok:
                stats[form][1] += 1
            show.append((ok, form, q[:80], pred, gt[:60]))
    total_fired = sum(v[0] for v in stats.values())
    total_correct = sum(v[1] for v in stats.values())
    print(f"{'FORM':<14}{'N':>5}{'FIRED':>7}{'CORRECT':>9}{'PREC':>7}{'HIT':>7}")
    for form, (fired, correct, n_all) in sorted(stats.items()):
        prec = correct / fired if fired else 0
        hit = correct / n_all
        print(f"{form:<14}{n_all:>5}{fired:>7}{correct:>9}{prec:>7.2f}{hit:>7.3f}")
    print(f"\nOVERALL: 133 questions | fired {total_fired} | correct {total_correct} "
          f"| hit {total_correct/133:.3f} (baseline exact multi=0.008)")
    print("\n--- sample outcomes (first 14) ---")
    for ok, form, q, pred, gt in show[:14]:
        mark = '✓' if ok else '✗'
        print(f"  {mark} [{form}] {q}")
        print(f"      pred={pred!r}  gt={gt!r}")

if __name__ == '__main__':
    main()
