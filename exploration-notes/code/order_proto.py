#!/usr/bin/env python3
"""
Order-family prototype v2 (Research #078): N-anchor sorting for order questions.

v2 fixes over v1 (2/9):
  - label canonicalization: strip possessive 's, merge containment (longest wins),
    merge same-anchor items
  - min label specificity (>=1 Cap token or >=2 tokens, len>=5)
  - sport prefix tolerates lowercase "the "
  - concert: session-anchored candidates (proper-noun 2+Cap phrases + event phrases);
    anchor = earliest session with fresh/eventive category-noun line
  - debug graduation Alex
"""
import json, re, sys
from datetime import datetime, timedelta

DATA = '/tmp/lme_s.json'

ORDER_RE = re.compile(
    r"(order of|from (the )?(first|earliest) to (the )?(last|latest)"
    r"|which .{0,60} (first|last)|who .{0,30} first, second"
    r"|earliest to latest|starting from the earliest)", re.I | re.S)

FRESH = re.compile(r"\b(today|just|yesterday|this morning|last night|tonight)\b", re.I)
YESTERDAY = re.compile(r"\byester\w{0,8}\b", re.I)
PLANNING = re.compile(
    r"(planning|thinking of|thinking about|considering|want to|would like|"
    r"upcoming|looking forward|in the future|soon|interested in|next time)", re.I)
EVENTIVE = re.compile(
    r"(attended|visited|went to|saw|watched|flew|got back|came back|helped|ordered|"
    r"signed up|redeemed|used a|participated|participate|hiked|took part|completed|"
    r"finished|started|been to|took my|took our|loving|enjoying|on a high|"
    r"riding high|had such a great time|spent|graduated|graduate)", re.I)

AIRLINES = ["American Airlines", "JetBlue", "Delta", "United", "Southwest",
            "Spirit Airlines", "Alaska Airlines", "Frontier", "Allegiant"]
MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

def parse_date(s):
    return datetime.strptime(s.split(' ')[0], "%Y/%m/%d")

def lines_of(q):
    """yield (date, idx, line) for user-role lines"""
    for idx, (sid, ds, msgs) in enumerate(zip(q['haystack_session_ids'],
                                              q['haystack_dates'],
                                              q['haystack_sessions'])):
        d = parse_date(ds)
        for msg in msgs:
            if msg.get('role') == 'user':
                for line in re.split(r'[.\n]', msg.get('content', '')):
                    if line.strip():
                        yield d, idx, line.strip()

# ---------- closed-set extraction ----------
def extract_quoted(qtext):
    return [c.strip() for c in re.findall(r"'([^']{12,})'", qtext)]

def extract_day_clauses(qtext):
    m = re.search(r"(first to last|order from first to last):\s*(.*)", qtext, re.I)
    clauses = re.findall(r"the day (I[^,.:]{10,}?)(?:,| and the day|\s*\?)", qtext)
    return [c.strip() for c in clauses]

def extract_among_names(qtext):
    m = re.search(r"among (.+?)\?", qtext)
    if not m: return []
    names, seen = [], set()
    for n in re.findall(r"\b[A-Z][a-z]{2,}\b", m.group(1)):
        if n not in seen:
            seen.add(n); names.append(n)
    return names

def closed_items(qtext):
    items = extract_quoted(qtext)
    if not items:
        items = extract_day_clauses(qtext)
    if not items:
        items = extract_among_names(qtext)
    return items

def kws_of(item):
    stop = {"the", "a", "an", "i", "my", "for", "at", "on", "in", "to", "of", "and",
            "with", "her", "his", "their", "from", "used", "just", "day"}
    words = [w for w in re.findall(r"[a-z$]+", item.lower()) if w not in stop and len(w) > 2]
    return set(words) or {item.lower()}

# ---------- label canonicalization ----------
def canon_label(s):
    s = re.sub(r"'s\b", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    # iteratively strip leading lowercase determiners/verbs/filler
    strip = re.compile(r"^(?:the|a|an|finished|completed|recently|attended|back|from|been|to|of|my|at|time|like|loving|free|and)\s+", re.I)
    prev = None
    while prev != s:
        prev = s
        s = strip.sub("", s)
    return s

def merge_items(anchored):
    """anchored: list of (date, idx, label). Merge by substring containment
    (case-insensitive, possessive-stripped) and same-anchor."""
    norm = [(d, i, canon_label(l)) for d, i, l in anchored]
    keep = []
    for a in sorted(norm, key=lambda x: -len(x[2])):
        absorbed = False
        for b in keep:
            if a[2].lower() in b[2].lower():
                absorbed = True; break
            if b[2].lower() in a[2].lower():
                continue  # a is longer; b already in keep stays only if not absorbed later
        if not absorbed:
            keep.append(a)
    # second pass: absorb shorter into longer when containment held
    final = []
    for a in keep:
        if not any(a[2].lower() != b[2].lower() and a[2].lower() in b[2].lower() for b in keep):
            final.append(a)
    return final

# ---------- window ----------
def window_of(qtext, qdate):
    t = qtext.lower()
    m = re.search(r"past (three|two|one|\d+) months?", t)
    if m:
        n = {"three": 3, "two": 2, "one": 1}.get(m.group(1)) or int(m.group(1))
        return (qdate - timedelta(days=30.5 * n), qdate)
    m = re.search(r"past month", t)
    if m:
        return (qdate - timedelta(days=31), qdate)
    m = re.search(r"\b(?:in|during) (january|february|march|april|may|june|july"
                  r"|august|september|october|november|december)\b", t)
    if m:
        mo = MONTHS[m.group(1)]
        y = qdate.year if qdate.month >= mo else qdate.year - 1
        start = datetime(y, mo, 1)
        end = datetime(y + (mo == 12), (mo % 12) + 1, 1) - timedelta(days=1)
        return (start, end)
    return None

def category_of(qtext):
    t = qtext.lower()
    if 'museum' in t: return 'museum'
    if 'airline' in t or 'flew with' in t: return 'airline'
    if 'concert' in t or 'musical event' in t: return 'concert'
    if 'trip' in t: return 'trip'
    if 'sport' in t: return 'sport'
    if 'graduat' in t: return 'graduation'
    return None

# ---------- per-category candidate labels ----------
MUSEUM_PAT = re.compile(
    r"\b((?:[A-Z][\w'-]*\s+)*(?:[A-Z][\w'-]*\s+)?Museum(?:\s+of\s+[A-Z][\w'-]*"
    r"(?:\s+[A-Z][\w'-]*)*)?)")
TRIP_PAT = re.compile(
    r"((?:solo\s+|day\s+|road\s+)?(?:hike|camping trip|road trip|trip)\s+to\s+"
    r"[A-Z][\w'-]*(?:\s+(?:and\s+)?[A-Z][\w'-]*)*)")
SPORT_PAT = re.compile(r"\b((?:(?:[A-Z][\w'-]*|the)\s+)*(?:[a-z]+\s+){0,2}(?:[Gg]ame|[Cc]hampionship|[Pp]layoffs|[Tt]riathlon|[Tt]ournament|5K(?:\s+[Rr]un)?)\b)")
PROP2 = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
FLIGHT_CTX = re.compile(r"(flight|flew|flying|red-eye|miles|delay|round-trip|non-stop|airline)", re.I)

def specific(label):
    if len(label) < 5: return False
    toks = label.split()
    if len(toks) < 2: return False
    return True

def category_items(q, cat, lines):
    items = []
    if cat == 'airline':
        for d, i, line in lines:
            for al in AIRLINES:
                if al.lower() in line.lower() and FLIGHT_CTX.search(line):
                    items.append(al)
    elif cat == 'museum':
        for d, i, line in lines:
            for m in MUSEUM_PAT.finditer(line):
                items.append(m.group(1))
    elif cat == 'trip':
        for d, i, line in lines:
            for m in TRIP_PAT.finditer(line):
                items.append(m.group(1).strip())
    elif cat == 'sport':
        for d, i, line in lines:
            for m in SPORT_PAT.finditer(line):
                lab = m.group(1).strip()
                if specific(lab):
                    items.append(lab)
    return list(dict.fromkeys(items))

# ---------- anchoring ----------
def clauses(line):
    return [c for c in re.split(r',', line) if c.strip()]

def scan_anchor(item_kws, lines, window=None, ctx=None):
    """FRESH evaluated at line level (discourse timestamp); planning/eventive at
    CLAUSE level for the clause containing all item keywords."""
    fresh_hits, vague_hits = [], []
    for d, idx, line in lines:
        if window and not (window[0] <= d <= window[1]):
            continue
        ll = line.lower()
        if not all(k in ll for k in item_kws):
            continue
        if ctx and not ctx.search(line):
            continue
        my_cl = [c for c in clauses(line) if all(k in c.lower() for k in item_kws)]
        if not my_cl:
            my_cl = [line]
        # clause windows: single clause, or clause + following relative clause
        windows = []
        cs = clauses(line) or [line]
        for j, c in enumerate(cs):
            if all(k in c.lower() for k in item_kws):
                windows.append(c)
                if j + 1 < len(cs):
                    windows.append(c + ' ' + cs[j + 1])
        if not windows:
            windows = [line]
        hit = any(EVENTIVE.search(w) and not PLANNING.search(w) for w in windows)
        if FRESH.search(line):
            rd = d - timedelta(days=1) if YESTERDAY.search(line) else d
            fresh_hits.append((rd, idx, line))
        elif hit:
            vague_hits.append((d, idx, line))
    pool = fresh_hits or vague_hits
    if not pool:
        return None
    pool.sort(key=lambda x: (x[0], x[1]))
    return pool[0]

def concert_answer(q, lines, window):
    """Session-anchored concerts. Event phrases from eventive/fresh music lines;
    artists = 2+Cap proper nouns co-occurring (same line) with music nouns,
    anchored to earliest session containing a fresh/eventive music line."""
    MUSIC_LINE = re.compile(r"\b(concert|festival|jazz night|live|tour|merch(?:andise)?)\b", re.I)
    VENUE = re.compile(r"(Center|Arena|Theatre|Theater|Stadium|Pavilion|Hall)$")
    CORE = [re.compile(r"(outdoor concert series(?:\s+in\s+the\s+park)?)"),
            re.compile(r"(music festival(?:\s+in\s+[A-Z][a-z]+)?)"),
            re.compile(r"(jazz night(?:\s+at\s+a\s+local\s+bar)?)"),
            re.compile(r"((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?:concert|tour)(?:\s+at\s+the\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)?)")]
    def ev_ok(line):
        return FRESH.search(line) or (EVENTIVE.search(line) and not PLANNING.search(line))
    sess_by_idx = {}
    for d, i, line in lines:
        sess_by_idx.setdefault(i, []).append((d, line))
    # event phrases (earliest anchor per phrase)
    phrases = {}
    for d, i, line in lines:
        if not (MUSIC_LINE.search(line) and ev_ok(line)):
            continue
        for pat in CORE:
            m = pat.search(line)
            if m:
                key = m.group(1).lower()
                if key not in phrases or (d, i) < phrases[key][:2]:
                    phrases[key] = (d, i, m.group(1))
    # artists
    artists = {}
    for d, i, line in lines:
        if not MUSIC_LINE.search(line):
            continue
        for m in PROP2.finditer(line):
            nm = m.group(1)
            if VENUE.search(nm):
                continue
            if re.search(r"(Festival|Concert|Tour|Series|Music)$", nm):
                continue  # event name, not artist
            artists.setdefault(nm, []).append((d, i))
    anchored = [(d, i, lab) for d, i, lab in phrases.values()]
    phrase_anchors = {(d, i) for d, i, _ in anchored}
    for nm, occ in artists.items():
        best = None
        for d, i in occ:
            for dd, line in sess_by_idx[i]:
                if MUSIC_LINE.search(line) and ev_ok(line):
                    cand = (dd, i)
                    if best is None or cand < best:
                        best = cand
        if best and best not in phrase_anchors:
            if window and not (window[0] <= best[0] <= window[1]):
                continue
            anchored.append((best[0], best[1], nm))
    if window:
        anchored = [a for a in anchored if window[0] <= a[0] <= window[1]]
    anchored = merge_items(anchored)
    anchored.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in anchored] if anchored else None

def answer(q):
    qtext, qdate = q['question'], parse_date(q['question_date'])
    lines = list(lines_of(q))
    window = window_of(qtext, qdate)

    ci = closed_items(qtext)
    if ci:
        anchored = []
        for item in ci:
            a = scan_anchor(kws_of(item), lines, window)
            if a:
                anchored.append((a[0], a[1], item))
        anchored.sort(key=lambda x: (x[0], x[1]))
        return [x[2] for x in anchored], 'closed'

    cat = category_of(qtext)
    if not cat:
        return None, 'no-category'
    if cat == 'concert':
        return concert_answer(q, lines, window), 'concert'

    ctx = FLIGHT_CTX if cat == 'airline' else (
        re.compile(r"graduat", re.I) if cat == 'graduation' else None)
    if cat == 'graduation':
        ci = extract_among_names(qtext)
        anchored = []
        for item in ci:
            a = scan_anchor({item.lower()}, lines, window, ctx)
            if a:
                anchored.append((a[0], a[1], item))
        anchored.sort(key=lambda x: (x[0], x[1]))
        return [x[2] for x in anchored], 'graduation'

    cands = category_items(q, cat, lines)
    anchored = []
    for lab in cands:
        a = scan_anchor(kws_of(lab), lines, window, ctx)
        if a:
            anchored.append((a[0], a[1], lab))
    anchored = merge_items(anchored)
    anchored.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in anchored], cat
# ---------- judge ----------
CANON = {
    'gpt4_f49edff3': ['nursery', 'baby shower', 'phone case'],
    'gpt4_7f6b06db': ['muir', 'big sur', 'yosemite'],
    'gpt4_18c2b244': ['coupon|luvs|buy one', 'ibotta', 'shoprite'],
    'gpt4_7abb270c': ['science', 'contemporary', 'metropolitan', 'history', 'modern', 'natural'],
    'gpt4_45189cb4': ['nba|staples', 'college football', 'nfl|playoff'],
    'gpt4_e061b84f': ['triathlon', '5k|midsummer', 'soccer'],
    'gpt4_d6585ce8': ['billie', 'outdoor', 'brooklyn|festival in', 'jazz', 'queen|adam'],
    'gpt4_f420262c': ['jetblue', 'delta', 'united', 'american'],
    'gpt4_7ca326fa': ['emma', 'rachel', 'alex'],
}

def judge(qid, pred_items):
    canon = CANON.get(qid)
    if not canon: return None
    if len(pred_items) != len(canon): return False
    for item, c in zip(pred_items, canon):
        if not any(alt.lower() in item.lower() for alt in c.split('|')):
            return False
    return True

def main():
    data = json.load(open(DATA))
    byid = {q['question_id']: q for q in data}
    ids = list(CANON)
    ok = 0
    for qid in ids:
        q = byid[qid]
        pred, mode = answer(q)
        j = judge(qid, pred or [])
        ok += bool(j)
        print(f"[{'OK ' if j else 'FAIL'}] {qid} ({mode}) n={len(pred or [])}/{len(CANON[qid])}")
        for it in (pred or []):
            print(f"        - {it[:110]}")
    print(f"\n== {ok}/{len(ids)} correct (baseline: 0/{len(ids)})")

if __name__ == '__main__':
    main()
