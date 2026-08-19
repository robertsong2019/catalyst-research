#!/usr/bin/env python3
"""
msagg_proto_v2.py — Multi-Session Aggregation v2 iter2

iter1: hit 0.068 -> 0.113 (9 -> 15 correct of 133)
iter2 fixes (each traceable to an iter1 wrong):
  F1 anchor propagation BEFORE collection (Hawaii 10-day ordering bug)
  F2 word-boundary anchor match ('star' in 'started' substring bug)
  F3 session signature from ALL non-intent sentences (MCU 'all 22' qty)
  F4 instance overhaul: contraction/month/cap-stoplist, scale-run+adjacency,
     N/N-scale sentence escape, cluster_ok category whitelist
  F5 unit-headed walls -> None (pages/minutes/points/hours/times)
  F6 number_total: SUM of distinct counts (was max), N-ary conj, hyponyms
  F7 total_what: money-cue guard, conj-subtype amount attribution,
     no-fallback-when-target-missed (luxury abstain), weight->pounds
  F8 argmax: contraction filter + direct target phrase
  F9 avg: \\bage\\b word boundary, kinship collection, gpa range
  F10 full-day/all-day = 1 day

Usage: python3 msagg_proto_v2.py [--wrong]
"""
import json, re, sys
from collections import defaultdict

WORD2NUM = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
            'twelve': 12, 'fifteen': 15, 'twenty': 20, 'thirty': 30}

INTENT_RE = re.compile(
    r"\b(?:i(?:'m| am|\u2019m)?\s+(?:thinking\s+of|planning|considering|hoping\s+to|"
    r"looking\s+(?:to|at|into)|going\s+to)|i\s+(?:want|would\s+like|'ll|will|plan)\b|"
    r"i'?d\s+like|i\s+think\s+i(?:'ll| will)|planning\s+a|i'll\b)", re.I)

ACQUIRE_RE = re.compile(
    r"\b(?:checking\s+out|check\s+out|you\s+mentioned|models?\s+you\s+mentioned|"
    r"recommend|thinking\s+of\s+(?:getting|buying|trying)|want\s+to\s+(?:get|buy)|"
    r"planning\s+to\s+(?:get|buy)|looking\s+to\s+(?:get|buy)|shopping\s+for|"
    r"in\s+the\s+market\s+for|considering\s+(?:getting|buying))\b", re.I)

UNIT_BLACKLIST = {'gallon', 'gallons', 'pound', 'pounds', 'lb', 'lbs', 'mph', 'kph',
                  'percent', 'dollar', 'dollars', 'mile', 'miles', 'km', 'kilometer',
                  'kilometers', 'kg', 'kilogram', 'kilograms', 'ounce', 'ounces', 'oz',
                  'liter', 'liters', 'litre', 'litres', 'foot', 'feet', 'inch', 'inches',
                  'year', 'years', 'month', 'months', 'week', 'weeks', 'day', 'days',
                  'hour', 'hours', 'minute', 'minutes', 'degree', 'degrees'}

# F5: question head nouns that are structural walls for zero-LLM counting
WALL_HEADS = {'hour', 'hours', 'minute', 'minutes', 'time', 'times', 'page', 'pages',
              'point', 'points'}

HYPONYM = {
    'instrument': {'guitar', 'piano', 'drum', 'violin', 'ukulele', 'bass', 'keyboard',
                   'saxophone', 'flute', 'cello', 'banjo', 'mandolin', 'trumpet',
                   'clarinet', 'synthesizer', 'organ', 'harp', 'trombone', 'viola'},
    'property': {'house', 'condo', 'townhouse', 'bungalow', 'apartment', 'loft',
                 'cottage', 'duplex', 'villa', 'cabin', 'flat'},
    'museum': {'museum', 'gallery', 'exhibition', 'exhibit'},
    'event': {'exhibition', 'lecture', 'tour', 'concert', 'show', 'festival',
              'workshop', 'event', 'meetup', 'screening', 'performance'},
    'service': {'platform', 'app', 'service', 'website', 'provider'},
    'store': {'store', 'market', 'shop', 'grocery'},
    'vehicle': {'bike', 'bicycle', 'car', 'motorcycle', 'scooter', 'truck'},
    'plant': {'plant', 'seedling', 'shrub', 'tree'},
    'course': {'course', 'class', 'module', 'program'},
    'kit': {'kit', 'model'},
    'sibling': {'brother', 'sister'},
}

# F4: categories where distinct named instances beat explicit self-reports
CLUSTER_OK = {'kit', 'model', 'instrument', 'property', 'tank', 'vehicle', 'bike',
              'plant', 'course', 'condo', 'house'}

GENERIC_HEADS = {'trip', 'trips', 'trek', 'treks', 'hike', 'hikes', 'thing', 'things',
                 'item', 'items', 'stuff', 'one', 'ones', 'time', 'times'}

STOP_Q = {'many', 'much', 'have', 'does', 'did', 'that', 'this', 'with', 'from',
          'about', 'what', 'which', 'there', 'been', 'were', 'will', 'would',
          'currently', 'leading', 'worked', 'watched', 'watching', 'spent',
          'spend', 'take', 'took', 'combined', 'total', 'year', 'month', 'past',
          'recent', 'recently', 'different', 'various', 'distinct', 'all', 'my',
          'me', 'i', 'in', 'on', 'at', 'the', 'a', 'an', 'of', 'for', 'and',
          'or', 'to', 'how', 'is', 'was', 'are', 'do', 'number', 'amount',
          'new', 'last', 'first', 'including', 'before', 'after', 'making',
          'offer', 'currently', 'own', 'led', 'simultaneously', 'excluding'}

MONTHS = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
          'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11,
          'december': 12}
WEEKDAYS = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}
# capitalized tokens that are never instance names
CAP_STOP = {"i'm", "i've", "i'll", "i'd", "it's", "that's", "they're", "we're",
            "you're", "don't", "doesn't", "didn't", "can't", "won't", "he's",
            "she's", "there's", "let's", "what's", 'by', 'can', 'now', 'since',
            'when', 'what', 'how', 'the', 'do', 'does', 'did', 'so', 'and',
            'but', 'if', 'then', 'also', 'by', 'for', 'from', 'with', 'my',
            'im', 'ive', 'ill', 'id'} | set(MONTHS) | WEEKDAYS

def _num(tok):
    tok = tok.lower()
    if tok in WORD2NUM:
        return float(WORD2NUM[tok])
    try:
        return float(tok)
    except ValueError:
        return None

def _sing(noun):
    if noun.endswith('ies'):
        return noun[:-3] + 'y'
    if noun.endswith('s') and not noun.endswith('ss'):
        return noun[:-1]
    return noun

def _sents(sessions, role='user'):
    for si, s in enumerate(sessions):
        for t in s.get('turns', []):
            if t.get('role') != role:
                continue
            for m in re.finditer(r'[^.!?]*[.!?]?', t.get('content', '')):
                sent = m.group(0).strip()
                if sent:
                    yield si, sent

def _proper_nouns(text):
    """F4/F8: capitalized runs, minus contractions/months/weekdays/cap-stop."""
    out = set()
    for w in re.findall(r"\b[A-Z][A-Za-z&'-]*\b", text):
        wl = w.lower()
        if wl in CAP_STOP or wl in ('the', 'i', 'my', 'we', 'a', 'an'):
            continue
        out.add(wl)
    return out

def _content_tokens(text):
    return {w.lower() for w in re.findall(r"[A-Za-z][\w&'#-]*", text)
            if w.lower() not in STOP_Q | GENERIC_HEADS and len(w) > 2}


def _np_fam(question):
    """All content words of the counted NP (robust vs trailing modifiers)."""
    ql = question.lower()
    m = re.match(r'^how many ([a-z][\w\s-]{1,60}?)(?:\s+(?:do|did|have|has)\s+i|\s+i\s+(?:do|did|have|has|had|currently)|\s+(?:in|on|at|from|across|over|during|before|after|last|this|due)\b|[?.])', ql)
    if not m:
        m = re.match(r'^what (?:is|was) the total number of ([a-z][\w\s-]{1,60}?)(?:\s+i\b|\s+(?:do|did|have|has)\s+i|\bthat\b|,|\bby\b|\bfrom\b|[?.])', ql)
    if not m:
        return None, None
    np = m.group(1)
    parts = re.split(r'\s+and\s+|,\s+|\s+or\s+', np)
    subs, fam = [], set()
    for part in parts:
        ws = [w for w in re.findall(r"[a-z][\w-]+", part)
              if w not in STOP_Q and w not in GENERIC_HEADS and len(w) >= 4]
        if not ws:
            continue
        h = ws[-1]
        for w in ws:
            fam |= {w, _sing(w), w + 's', _sing(w) + 's'}
        if len(parts) >= 2 and h not in subs:
            subs.append(h)
    return fam, (subs if len(subs) >= 2 else None)

# ---------------- form detection ----------------

def detect_form(question):
    q = question.strip()
    ql = q.lower()
    if re.match(r'^what is the total number of (days|weeks)', ql):
        return 'duration_sum'
    if re.search(r'\bhow many (days|weeks)\b', ql) or \
       (re.search(r'\b(days|weeks)\b', ql) and re.search(r'\b(spend|spent|take|took)\b', ql) and ql.startswith('how')):
        return 'duration_sum'
    if re.match(r'^how (much|many)\b', q, re.I) and re.search(r'\btotal\b', ql):
        return 'total_sum'
    if re.match(r'^what is the total number', ql) or re.match(r'^what was the total number', ql):
        return 'number_total'
    if re.match(r'^what (is|was) the total\b', ql) and \
       re.search(r'\$|money|cost|spent|spend|earned|paid|pay\b', ql):
        return 'total_what'
    if re.match(r'^what (is|was) the total\b', ql) and re.search(r'\bweight\b', ql):
        return 'weight_total'
    if re.search(r'\baverage\b', ql):
        return 'avg'
    if re.match(r'^which\b', ql) and re.search(r'\bmost\b', ql):
        return 'argmax'
    if re.match(r'^how many\b', q, re.I):
        return 'entity_count'
    return 'none'

# ---------------- question anatomy ----------------

def question_anchors(question):
    toks = set()
    for w in re.findall(r"[A-Za-z][\w'-]*", question):
        wl = w.lower()
        if wl in STOP_Q or wl in GENERIC_HEADS or wl in UNIT_BLACKLIST or wl in WALL_HEADS:
            continue
        if len(wl) < 4 and not w[0].isupper():
            continue
        toks.add(wl)
    return {t for t in toks if len(t) >= 4}

def _anchor_re(anchors):
    if not anchors:
        return None
    return re.compile(r'\b(' + '|'.join(re.escape(a) for a in sorted(anchors, key=len, reverse=True)) + r')\b', re.I)

def conj_subtypes(question, n_ary=True):
    """'for/of X and Y' (and comma lists when n_ary) -> subtype token list."""
    ql = question.lower()
    m = re.search(r'\b(?:for|of|from)\s+(?:my\s+|the\s+|both\s+)?([a-z][\w\s,]+?)\s+and\s+([a-z][\w\s-]+?)[?.]', ql)
    if not m:
        return None
    def head(phrase):
        ws = [w for w in re.findall(r"[a-z][\w-]+", phrase) if w not in STOP_Q]
        return ws[-1] if ws else None
    subs = []
    if n_ary:
        for part in re.split(r',\s+|\s+and\s+', m.group(1) + ' and ' + m.group(2)):
            h = head(part)
            if h and h not in {s for s in subs}:
                subs.append(h)
    else:
        a, b = head(m.group(1)), head(m.group(2))
        subs = [a, b] if a and b and a != b else []
    subs = [s for s in subs if s]
    return subs if len(subs) >= 2 else None

def head_noun(question):
    m = re.match(r'^How many (.+?) (?:do|did|have|has) I\b', question, re.I)
    if not m:
        m = re.match(r'^How many (.+?) I (?:currently )?(?:have|had|own|bought|viewed|led)\b', question, re.I)
    if not m:
        m = re.match(r'^What (?:is|was) the total number of (.+?)(?:\s+(?:do|did|have|has)\s+I|\s+I\s+(?:do|did|have|has|had))?[?.]', question, re.I)
    if not m:
        return None
    np = m.group(1).lower()
    np = re.sub(r'^(items? of|pieces? of|kinds? of|types? of|different|various|distinct)\s+', '', np)
    words = [w for w in re.findall(r"[a-z][a-z-']+", np) if w not in ('of',)]
    return words[-1] if words else None

# ---------------- duration_sum ----------------

def extract_durations_days(text):
    out = []
    for m in re.finditer(r'\b(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*(day|week)s?\b', text, re.I):
        n = _num(m.group(1))
        if n is None:
            continue
        out.append((n * (7.0 if m.group(2).lower().startswith('week') else 1.0), m.group(0)))
    for m in re.finditer(r'\ba\s+week\s+and\s+a\s+half\b', text, re.I):
        out.append((10.5, m.group(0)))
    for m in re.finditer(r'\b(?:full|all)[- ]day\b', text, re.I):   # F10
        out.append((1.0, m.group(0)))
    return out

def extract_daterange_days(text):
    m = re.search(r'\b(' + '|'.join(MONTHS) + r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s*(?:to|-|through|until)\s+(\d{1,2})(?:st|nd|rd|th)?\b', text, re.I)
    if m:
        d1, d2 = int(m.group(2)), int(m.group(3))
        if 0 < d1 < 32 and 0 < d2 < 32 and d2 > d1:
            return float(d2 - d1)
    return None

def duration_sum(question, sessions):
    q = question.lower()
    want_unit = 'days' if re.search(r'\bdays\b', q) else ('weeks' if re.search(r'\bweeks\b', q) else None)
    if want_unit is None:
        return None
    anchors = question_anchors(question)
    are = _anchor_re(anchors)

    per_session = defaultdict(lambda: {'events': [], 'counts': set(), 'pnouns': set(), 'anchor_ok': False})
    # F1: propagate session anchors FIRST (proper-noun anchors only — activity
    # words like 'camping' appear in gear-discussion sessions and pollute)
    cap_anchors = {w.lower() for w in re.findall(r"\b[A-Z][a-z]+\b", question)
                   if w.lower() in anchors}
    cap_are = _anchor_re(cap_anchors) if cap_anchors else None
    for si, sent in _sents(sessions):
        if are and are.search(sent):
            per_session[si]['pnouns'] |= _proper_nouns(sent)
            per_session[si]['counts'] |= {int(n) for n in re.findall(r'\ball\s+(\d{1,4})\b', sent)}
            if cap_are and cap_are.search(sent):
                per_session[si]['anchor_ok'] = True
    # F3: enrich signature from all non-intent sentences of anchor-ok sessions
    for si, sent in _sents(sessions):
        sess = per_session[si]
        if not sess['anchor_ok']:
            continue
        if sent.endswith('?') or INTENT_RE.search(sent):
            continue
        sess['pnouns'] |= _proper_nouns(sent)

    for si, sent in _sents(sessions):
        sess = per_session[si]
        if sent.endswith('?') or INTENT_RE.search(sent):
            continue
        if are and not are.search(sent) and not sess['anchor_ok']:
            continue
        durs = extract_durations_days(sent)
        dr = extract_daterange_days(sent)
        for days, span in durs:
            sess['events'].append(round(days, 1))
        if dr is not None:
            sess['events'].append(round(dr, 1))

    # F1-dedup: merge equal values across sessions on signature overlap
    merged = []   # [days, sig]
    for si, data in sorted(per_session.items()):
        sig = data['counts'] | data['pnouns']
        for days in data['events']:
            hit = next((ev for ev in merged if ev[0] == days and (ev[1] & sig)), None)
            if hit:
                hit[1] |= sig
            else:
                merged.append([days, set(sig)])
    if not merged:
        return None
    # conjoined proper-place completeness: 'Hawaii and Seattle' — each needs an event
    if cap_anchors and ' and ' in question.lower():
        ev_sessions_pn = set()
        for ev, sig in merged:
            ev_sessions_pn |= {s for s in sig}
        missing = [a for a in cap_anchors if a not in ev_sessions_pn and not any(a in s for s in ev_sessions_pn)]
        if missing:
            return None
    total = sum(ev[0] for ev in merged)
    val = total / (7.0 if want_unit == 'weeks' else 1.0)
    return f"{round(val, 2):g} {want_unit}"

# ---------------- entity_count ----------------

SCALE_RUN = re.compile(r"\b(\d+(?:/\d+)?(?:\.\d+)?\s*(?:-?\s*(?:gallon|piece|bedroom|door|seat|step|speed|inch|foot|pound|lb)\b|\s*scale\b))", re.I)
CAP_RUN = re.compile(r"\b([A-Z][A-Za-z&'\u2019-]*(?:\s+(?:[A-Z][A-Za-z&'\u2019-]+|\d[\w'-]*)){0,4})")

def _instance_candidates(sent, fam_re):
    """Bidirectional instance extraction:
    - CAP/scale run immediately before a fam noun (gap<=1 word)
    - fam noun followed by apposition ", a Yamaha FG800" / ", a 5-piece Pearl Export"
    - fam-initial runs: "Museum of Modern Art" (run starts with fam noun)
    CAP runs must be multi-token or contain a digit; 'and' joins allowed (couples).
    """
    cands = []
    fam_hits = list(fam_re.finditer(sent))
    cap_run = re.compile(r"\b([A-Z][A-Za-z&'\u2019-]*(?:\s+(?:and\s+)?(?:[A-Z][A-Za-z&'\u2019-]+|\d[\w'-]*)){0,5})")
    scale_run = SCALE_RUN
    for fm in fam_hits:
        fs = fm.start()
        # (a) look back: nearest cap-run or scale-run ending within 1 word of fam
        window = sent[max(0, fs - 50):fs]
        best = None
        for cm in cap_run.finditer(window):
            toks = [t for t in cm.group(1).split() if t.lower() not in CAP_STOP and t.lower() != 'and']
            if not toks:
                continue
            gap_ok = window[cm.end():].strip()
            if len(gap_ok.split()) <= 1 and (len(toks) >= 2 or any(ch.isdigit() for t in toks for ch in t)):
                best = ' '.join(toks)
        for sm in scale_run.finditer(window):
            if len(window[sm.end():].strip().split()) <= 3:
                best = sm.group(1)
        if best:
            cands.append(best)
        # (b) apposition after fam: fam + ,? (a|an|the|my|named)? CAP/scale run
        after = sent[fm.end():fm.end() + 45]
        am = re.match(r"\s*,?\s*(?:a|an|the|my|named|called)\s+((?:\d[\w/-]*|[A-Z][A-Za-z&'\u2019-]*)(?:\s+(?:and\s+)?(?:[A-Z][A-Za-z&'\u2019-]+|\d[\w'-]*)){0,4})", after)
        if am:
            toks = [t for t in am.group(1).split() if t.lower() not in CAP_STOP and t.lower() != 'and']
            if toks and (len(toks) >= 2 or any(ch.isdigit() for t in toks for ch in t)):
                cands.append(' '.join(toks))
        # (c) fam-initial run: fam noun + following capitalized words
        tail = sent[fm.end():fm.end() + 40]
        cm2 = re.match(r"\s+(?:of\s+)?((?:[A-Z][A-Za-z&'\u2019-]*\s*){1,4})", tail)
        if cm2:
            toks = [fm.group(1)] + [t for t in cm2.group(1).split() if t.lower() not in CAP_STOP]
            if len(toks) >= 2:
                cands.append(' '.join(toks))
    # dedup preserving order
    seen, out = set(), []
    for c in cands:
        k = c.lower()
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out

def _cluster_tokens(mention):
    return {t for t in re.findall(r"[a-z0-9][\w&'#/-]*", mention.lower())
            if t not in STOP_Q and t not in GENERIC_HEADS and t not in CAP_STOP and len(t) > 1}

def entity_count(question, sessions):
    noun = head_noun(question)
    if noun is None:
        return None
    if noun in WALL_HEADS:          # F5
        return None
    base = _sing(noun)
    fam2, subs2 = _np_fam(question)
    fam = {base, noun} | {base + 's', noun + 's'} | HYPONYM.get(base, set()) | HYPONYM.get(noun, set())
    if fam2:
        fam |= {f for f in fam2 if len(f) >= 3}
    fam = {f for f in fam if len(f) >= 3}
    fam_re = re.compile(r'\b(' + '|'.join(sorted(fam)) + r')\b', re.I)
    subtypes = subs2 or conj_subtypes(question)
    anchor_exclude = _anchor_after_on_the(question)
    scale_escape = re.compile(r'\b\d+\s*/\s*\d+\s*scale\b', re.I)

    clusters, subtype_counts, explicit_counts = [], defaultdict(list), []
    qmonth = next((mo for mo in MONTHS if re.search(r'\b' + mo + r'\b', question.lower())), None)
    month_scoped = qmonth is not None
    for si, sent in _sents(sessions):
        low = sent.lower()
        if sent.endswith('?'):
            continue
        if month_scoped:
            ok_m = re.search(r'\b' + qmonth + r'\b', low) or (
                re.search(r'\b(\d{1,2})/(\d{1,2})\b', low) and int(re.search(r'\b(\d{1,2})/(\d{1,2})\b', low).group(1)) == MONTHS[qmonth])
            if not ok_m:
                continue
        fam_hit = bool(fam_re.search(sent))
        if not fam_hit and not scale_escape.search(sent):
            continue
        # explicit numerals (F2-safe unit blacklist)
        for em in re.finditer(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b'
                              r'[^\w]{0,3}(?:\w+\s+){0,2}(' + '|'.join(sorted(fam)) + r')\b', sent, re.I):
            n = _num(em.group(1))
            if n is None or n >= 1000:
                continue
            after = sent[em.end(1):em.start(2)].strip().lower().strip(' -')
            parts = after.split()
            if parts and parts[0].rstrip('s') in {u.rstrip('s') for u in UNIT_BLACKLIST}:
                continue
            st = None
            if subtypes:
                for s_ in subtypes:
                    if re.search(r'\b' + re.escape(s_) + r's?\b', low):
                        st = s_
                        break
            if subtypes:
                if st:
                    subtype_counts[st].append(n)
            else:
                explicit_counts.append(n)
        if ACQUIRE_RE.search(sent):
            continue
        for r in _instance_candidates(sent, fam_re):
            toks = _cluster_tokens(r)
            if not toks or len(toks) < 1:
                continue
            if anchor_exclude and (toks & anchor_exclude):
                continue
            merged = next((cl for cl in clusters if (cl & toks) and (cl <= toks or toks <= cl)), None)
            if merged:
                merged |= toks
            else:
                clusters.append(set(toks))
    if subtypes:
        vals = [max(subtype_counts[s_]) for s_ in subtypes if subtype_counts.get(s_)]
        if len(vals) < len(subtypes):
            return None
        return str(int(sum(vals)))
    best = max(explicit_counts) if explicit_counts else 0
    if base in CLUSTER_OK or noun in CLUSTER_OK:
        if len(clusters) >= 2 and len(clusters) > best:
            return str(len(clusters))
    if best:
        return str(int(best))
    if len(clusters) >= 2 and (base in CLUSTER_OK or noun in CLUSTER_OK):
        return str(len(clusters))
    return None

def _anchor_after_on_the(question):
    m = re.search(r'\b(?:on|for|at)\s+the\s+([a-z][\w\s-]{2,40}?)(?:[?.,]|neighborhood|$)', question.lower())
    if not m:
        return set()
    return {w for w in re.findall(r"[a-z][\w-]+", m.group(1)) if w not in STOP_Q}

# ---------------- What-routing ----------------

def _target_nouns(question):
    return question_anchors(question)

def total_money(question, sessions):
    targets = _target_nouns(question)
    subs = conj_subtypes(question)
    tre = _anchor_re(targets)
    amounts_t, amounts_all = [], []
    sub_amt = defaultdict(set)
    for si, sent in _sents(sessions):
        if sent.endswith('?') or INTENT_RE.search(sent):
            continue
        found = [float(x.replace(',', '')) for x in re.findall(r'\$\s?(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', sent)]
        if not found:
            continue
        amounts_all.extend(found)
        low = sent.lower()
        if subs:
            for s_ in subs:
                if re.search(r'\b' + re.escape(s_) + r's?\b', low):
                    sub_amt[s_] |= set(found)
        elif tre and tre.search(sent):
            amounts_t.extend(found)
    if subs:
        vals = []
        for s_ in subs:
            if sub_amt.get(s_):
                vals.append(max(sub_amt[s_]) if len(sub_amt[s_]) > 1 else list(sub_amt[s_])[0])
            else:
                return None
        return f"${round(sum(vals), 2):g}"
    if amounts_t:
        return f"${round(sum(set(amounts_t)), 2):g}"
    if targets and not amounts_all:
        return None
    if amounts_all:
        return f"${round(sum(set(amounts_all)), 2):g}"
    return None

def weight_total(question, sessions):
    targets = _target_nouns(question)
    tre = _anchor_re(targets)
    vals = []
    for si, sent in _sents(sessions):
        if sent.endswith('?') or INTENT_RE.search(sent):
            continue
        for m in re.finditer(r'\b(\d{1,4}(?:\.\d+)?)\s*(?:-?\s*(?:pounds?|lbs?))\b', sent, re.I):
            if tre and not tre.search(sent):
                continue
            vals.append(float(m.group(1)))
    if not vals:
        return None
    uniq = sorted(set(vals), reverse=True)
    return f"{round(sum(uniq), 1):g} pounds"

def number_total(question, sessions):
    fam, subtypes = _np_fam(question)
    if not fam:
        return None
    fam = {f for f in fam if len(f) >= 3}
    for w in list(fam):
        fam |= HYPONYM.get(w, set()) | HYPONYM.get(_sing(w), set())
    sub_counts, all_counts = defaultdict(set), set()
    for si, sent in _sents(sessions):
        low = sent.lower()
        if sent.endswith('?') or INTENT_RE.search(sent):
            continue
        if not any(re.search(r'\b' + re.escape(f) + r'\b', low) for f in fam):
            continue
        if subtypes:
            for s_ in subtypes:
                if re.search(r'\b' + re.escape(s_) + r's?\b', low):
                    for em in re.finditer(r'\b(\d{1,3}(?:,\d{3})*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty)\b[^\w]{0,3}(?:\w+\s+){0,2}' + re.escape(s_) + r's?\b', sent, re.I):
                        n = _num(em.group(1))
                        if n and n < 10000:
                            sub_counts[s_].add(n)
        else:
            for em in re.finditer(r'\b(\d{1,3}(?:,\d{3})*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty)\b[^\w]{0,3}(?:\w+\s+){0,2}(' + '|'.join(sorted(fam)) + r')\b', sent, re.I):
                n = _num(em.group(1))
                if n and n < 1000000:
                    after = sent[em.end(1):em.start(2)].strip().lower().strip(' -')
                    parts = after.split()
                    if parts and parts[0].rstrip('s') in {u.rstrip('s') for u in UNIT_BLACKLIST}:
                        continue
                    all_counts.add(n)
    if subtypes:
        vals = []
        for s_ in subtypes:
            if not sub_counts.get(s_):
                return None
            vals.append(max(sub_counts[s_]))
        return str(int(sum(vals)))
    if all_counts:
        return str(int(sum(all_counts)))     # F6: SUM of distinct
    return None

KIN_RE = re.compile(r"\b(?:parents?|grandparents?|grandma|grandpa|mother|father|mom|dad|"
                    r"brother|sister|i'?m|i\s+am|my\s+age)\b", re.I)

def avg_of_numbers(question, sessions):
    ql = question.lower()
    if re.search(r'\bgpa\b', ql):
        nums = []
        for si, sent in _sents(sessions):
            if sent.endswith('?') or INTENT_RE.search(sent):
                continue
            if not re.search(r'\bgpa\b', sent.lower()):
                continue
            for m in re.finditer(r'\b(\d(?:\.\d{1,2})?)\b', sent):
                v = float(m.group(1))
                if 0.5 <= v <= 4.0:
                    nums.append(v)
        if len(nums) >= 2:
            return f"{round(sum(nums)/len(nums), 2):g}"
        return None
    if re.search(r'\bage\b', ql):   # F9: word boundary via regex
        nums = []
        for si, sent in _sents(sessions):
            if sent.endswith('?') or INTENT_RE.search(sent):
                continue
            if not KIN_RE.search(sent):
                continue
            for m in re.finditer(r'\b(\d{1,3})\b', sent):
                v = float(m.group(1))
                if 18 <= v <= 105:
                    nums.append(v)
        if len(nums) >= 3:
            return f"{round(sum(nums)/len(nums), 1):g}"
        return None
    return None

def argmax_entity(question, sessions):
    ql = question.lower()
    money = 'money' in ql or 'spend' in ql or 'spent' in ql or 'cost' in ql
    followers = 'follower' in ql
    ent_totals = defaultdict(float)
    for si, sent in _sents(sessions):
        if sent.endswith('?') or INTENT_RE.search(sent):
            continue
        vals = []
        if money:
            vals = [float(x.replace(',', '')) for x in re.findall(r'\$\s?(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', sent)]
        elif followers:
            vals = [float(x.replace(',', '')) for x in re.findall(r'\b(\d{1,6}(?:,\d{3})*)\s+followers?\b', sent, re.I)]
        if not vals:
            continue
        m = re.search(r"\b(?:at|on|from|in)\s+((?:[A-Z][\w&'-]*\s*){1,3})", sent)
        if m:
            key = m.group(1).strip()
            toks = [w for w in key.split() if w.lower() not in CAP_STOP]
            if not toks:
                continue
            ent_totals[' '.join(toks)] += max(vals)
        else:
            ents = _proper_nouns(sent)
            if not ents:
                continue
            ent_totals[' '.join(sorted(ents))] += max(vals)
    if not ent_totals:
        return None
    best = max(ent_totals.items(), key=lambda kv: kv[1])
    return ' '.join(w.capitalize() for w in best[0].split())

def total_sum(question, sessions):
    amts = set()
    for si, sent in _sents(sessions):
        if sent.endswith('?') or INTENT_RE.search(sent):
            continue
        for m2 in re.finditer(r'\$\s?(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', sent):
            amts.add(m2.group(1))
    if not amts:
        return None
    total = round(sum(float(a.replace(',', '')) for a in amts), 2)
    return f"${total:g}"

# ---------------- orchestration & judging ----------------

def aggregate(question, sessions):
    form = detect_form(question)
    fn = {'duration_sum': duration_sum, 'entity_count': entity_count,
          'total_sum': total_sum, 'total_what': total_money,
          'weight_total': weight_total, 'number_total': number_total,
          'avg': avg_of_numbers, 'argmax': argmax_entity}
    if form in fn:
        try:
            return fn[form](question, sessions), form
        except Exception:
            return None, form
    return None, form

NUMWORD = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
           'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
           'twelve': 12, 'fifteen': 15, 'twenty': 20}

def _numval(s):
    if s is None:
        return None
    s = str(s).strip()
    m = re.match(r'^\$?\s*([\d,]+(?:\.\d+)?)', s)
    if m:
        return float(m.group(1).replace(',', ''))
    m = re.match(r'^\$?\s*(\w+)', s.lower())
    if m and m.group(1) in NUMWORD:
        return float(NUMWORD[m.group(1)])
    # sentence-style GT: first numeric claim ("I have worked on or bought five model kits")
    m = re.search(r'\b(five|four|three|two|one|zero|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|\d+(?:,\d{3})*)\b', s.lower())
    if m:
        tok = m.group(1)
        if tok in NUMWORD:
            return float(NUMWORD[tok])
        return float(tok.replace(',', ''))
    return None

def judge(pred, gt):
    if pred is None:
        return False
    p, g = _numval(pred), _numval(gt)
    if p is not None and g is not None:
        return abs(p - g) < 1e-6
    pl, gl = str(pred).lower().strip(), str(gt).lower().strip()
    return pl in gl or gl in pl

def run(wrong_only=False):
    multi = json.load(open('/tmp/msagg/multi_evidence_roles.json'))
    stats = defaultdict(lambda: [0, 0, 0])
    rows = []
    for item in multi:
        q, gt = item['question'], str(item['answer'])
        pred, form = aggregate(q, item['evidence_sessions'])
        stats[form][2] += 1
        if pred is not None:
            stats[form][0] += 1
            ok = judge(pred, gt)
            if ok:
                stats[form][1] += 1
            rows.append((ok, form, q, pred, gt))
    print(f"{'FORM':<14}{'N':>5}{'FIRED':>7}{'CORRECT':>9}{'PREC':>7}{'HIT':>7}")
    tf = tc = 0
    for form, (fired, correct, n_all) in sorted(stats.items()):
        prec = correct / fired if fired else 0
        hit = correct / n_all
        tf += fired; tc += correct
        print(f"{form:<14}{n_all:>5}{fired:>7}{correct:>9}{prec:>7.2f}{hit:>7.3f}")
    print(f"\nv2i2 OVERALL: fired {tf} | correct {tc} | hit {tc/133:.3f}  (i1: 58/15/0.113, v1: 32/9/0.068)")
    if wrong_only:
        print('\n--- wrong ---')
        for ok, form, q, pred, gt in rows:
            if not ok:
                print(f"  ✗ [{form}] pred={str(pred)[:30]!r} gt={gt[:42]!r} Q: {q[:72]}")
    return rows

if __name__ == '__main__':
    run(wrong_only='--wrong' in sys.argv)
