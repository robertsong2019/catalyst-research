#!/usr/bin/env python3
"""
C497 前置研究原型：Event-Centric Comparison Matcher (ECM)
"neither 族" 4 题 —— multi-sentence 证据墙 + meet/become 事件面 + sentence-window kw 匹配

问题形态: "Who did I meet first, X or Y?" / "Who became a parent first, X or Y?"
机制（零 LLM）:
  1. form-gate: 提取事件动词类 + 两个实体槽
  2. 实体归一化: 人名 → token 集; 描述性 NP → 内容词集
  3. 全 haystack 句子级扫描（C472 全图回退模式）, 事件句 = 含动词触发词
  4. sentence-window: 句 ± 邻句（同 turn 内）; 词重叠 + 区分度判别（≥2 内容词或人名命中）
  5. 相对时间解析 → anchor 前天数（vague duration / calendar 双轨）
  6. 回指 join: 名字句无日期 → 同 session 找共享关系 NP 的日期句（Rachel 案）
  7. 比较: 早者胜; 一方缺失 → 弃权（负存在, C489 语义）
"""
import json, re
from datetime import datetime, timedelta

DATA = json.load(open('/tmp/lme_s.json'))
QIDS = ['gpt4_88806d6e', 'gpt4_0a05b494', 'gpt4_fe651585', 'gpt4_fe651585_abs']

STOP = set('''a an the i my me of at on in to from and or who whom did do does with was were is are
that this it her his their she he they guy girl woman man named who's selling maker from'''.split())

# ---------- form gate ----------
# 两种形态: "Who did I meet first, X or Y?" / "Who became a parent first, X or Y?"
GATE_A = re.compile(r'^who did i (meet|get to know) first,\s*(.+?)\s+or\s+(.+?)\?$', re.I)
GATE_B = re.compile(r'^who (became a parent|got married|moved out|graduated) first,\s*(.+?)\s+or\s+(.+?)\?$', re.I)

VERBMAP = {  # 问题动词 → 证据触发词面（事件面: met/conversation with 都是 meet 的表面形式）
    'meet': [r'\bmet\b', r'\bmeet\b', r'\bconversation with\b', r'\bran into\b', r'\bstruck up\b'],
    'get to know': [r'\bmet\b', r'\bconversation with\b'],
    'became a parent': [r'\badopted\b', r'\bborn\b', r'\bgave birth\b', r'\bwelcomed\b'],
    'got married': [r'\bwedding\b', r'\bmarried\b'],
    'moved out': [r'\bmoved\b'],
    'graduated': [r'\bgraduated\b'],
}
RELNOUNS = ['sister-in-law', 'brother', 'sister', 'cousin', 'friend', 'mother', 'father',
            'aunt', 'uncle', 'wife', 'husband', 'partner', 'colleague', 'neighbor', 'boss']

# ---------- time resolution: 表达式 → (anchor 前) 天数 ----------
WEEKDAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
MONTHS = {m: i+1 for i, m in enumerate(
    ['january','february','march','april','may','june','july','august',
     'september','october','november','december'])}

def resolve_days_ago(text, anchor):
    """文本 → anchor 前天数（越大越早）。返回 None if 无时间表达。"""
    t = text.lower()
    m = re.search(r'\b(a few|several) months ago\b', t)
    if m: return 90
    m = re.search(r'\b(?:about|around|roughly)? ?(\d+|a|an|one|two|three|four|five|six) months? ago\b', t)
    if m:
        n = {'a':1,'an':1,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6}.get(m.group(1), m.group(1))
        return int(n) * 30
    m = re.search(r'\b(?:a few|several) weeks ago\b', t)
    if m: return 21
    m = re.search(r'\b(?:a couple of|about |around )?(\d+|a|one|two|three|four|five) weeks? ago\b', t)
    if m:
        n = {'a':1,'one':1,'two':2,'three':3,'four':4,'five':5}.get(m.group(1), m.group(1))
        return int(n) * 7
    m = re.search(r'\blast week\b', t)
    if m: return 7
    m = re.search(r'\blast weekend\b', t)
    if m: return 4
    m = re.search(r'\blast (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', t)
    if m:  # 距 anchor 最近的上一个该星期几
        wd = WEEKDAYS.index(m.group(1)); d = 1
        while (anchor - timedelta(days=d)).weekday() != wd: d += 1
        return d
    m = re.search(r'\b(?:a few|several) days ago\b', t)
    if m: return 3
    m = re.search(r'\b(\d+|a|one|two|three) days? ago\b', t)
    if m:
        n = {'a':1,'one':1,'two':2,'three':3}.get(m.group(1), m.group(1))
        return int(n)
    m = re.search(r'\blast month\b', t)
    if m: return 30
    # calendar 轨: in January / on February 12th
    m = re.search(r'\bin (january|february|march|april|may|june|july|august|september|october|november|december)\b', t)
    if m:
        mm = MONTHS[m.group(1)]
        dt = anchor.replace(month=mm, day=15) if anchor.month > mm else None
        if dt: return (anchor - dt).days
    m = re.search(r'\bon (january|february|march|april|may|june|july|august|september|october|november|december) (\d+)(?:st|nd|rd|th)?\b', t)
    if m:
        mm, dd = MONTHS[m.group(1)], int(m.group(2))
        try:
            dt = anchor.replace(month=mm, day=dd)
            if dt <= anchor: return (anchor - dt).days
        except ValueError: pass
    return None

# ---------- entity / sentence utilities ----------
def content_words(np):
    words = re.findall(r"[a-z]+", np.lower())
    return {w for w in words if w not in STOP and len(w) > 2 and w not in RELNOUNS}

def is_name_entity(np):
    # 大写开头 ≥1 个 token 且非句子开头冠词模式 → 视为命名实体
    toks = [t for t in re.findall(r"[A-Za-z][a-z]+", np)]
    return toks and all(t[0].isupper() for t in toks)

def sentences(turn_text):
    parts = re.split(r'(?<=[.!?])\s+', turn_text.replace('\n', ' '))
    return [p.strip() for p in parts if len(p.strip()) > 5]

def hits(pat, s): return re.search(pat, s, re.I) is not None

# ---------- 句子级索引（全 haystack）----------
def index_question(q):
    def L(x): return x if isinstance(x, list) else eval(x)
    hs, hsids, hd = L(q['haystack_sessions']), L(q['haystack_session_ids']), L(q['haystack_dates'])
    qdate = datetime.strptime(q['question_date'].split(' (')[0], '%Y/%m/%d')
    recs = []  # (session_idx, turn_idx, sent_idx, sentence, session_date)
    for si, sess in enumerate(hs):
        sdate = datetime.strptime(hd[si].split(' (')[0], '%Y/%m/%d')
        for ti, turn in enumerate(sess):
            if turn['role'] != 'user': continue
            for xi, s in enumerate(sentences(turn['content'])):
                recs.append((si, ti, xi, s, sdate))
    return recs, qdate

def window_text(recs, i, span=1):
    """句 ± span 同 turn 邻句 = sentence window"""
    si, ti, xi, s, d = recs[i]
    out = [s]
    for j in (i-1, i+1):
        if 0 <= j < len(recs):
            sj, tj, xj, sj_txt, _ = recs[j]
            if (sj, tj) == (si, ti) and abs(xj - xi) <= span:
                out.append(sj_txt)
    return ' '.join(out)

# ---------- 实体 → 证据定位 ----------
def find_entity_evidence(entity, recs, verb_patterns, qdate):
    """返回 (best_days_ago, evidence_sentence) 或 None。"""
    if is_name_entity(entity):
        name_toks = {t.lower() for t in re.findall(r"[A-Za-z][a-z]+", entity)}
        cands = []
        for i, (si, ti, xi, s, d) in enumerate(recs):
            low = s.lower()
            # 人名命中 = 词边界（防 tomato/tom 污染）
            n_hit = sum(1 for t in name_toks if re.search(r'\b' + t + r'\b', low))
            if n_hit and any(hits(p, s) for p in verb_patterns):
                w = window_text(recs, i)
                anchor = d
                days = resolve_days_ago(w, anchor) or resolve_days_ago(s, anchor)
                if days is not None:
                    cands.append((n_hit, days, s))
        if not cands: return None
        cands.sort(key=lambda c: -c[0])          # 名字命中多者优先
        return cands[0][1], cands[0][2]
    else:
        cw = content_words(entity)
        best = None
        for i, (si, ti, xi, s, d) in enumerate(recs):
            # 描述性实体: 不要求动词面（"conversation with a jam maker" 不含 met）——
            # 由 ≥2 内容词重叠 + 窗口内可解析时间 双重判别，干扰句 0-1 重叠进不来
            w = window_text(recs, i); wl = w.lower()
            ov = sum(1 for t in cw if re.search(r'\b' + t + r'\b', wl))
            if ov >= 2 or ov == len(cw):
                days = resolve_days_ago(w, d)
                if days is not None and (best is None or ov > best[0]):
                    best = (ov, days, s)
        return None if not best else (best[1], best[2])

def anaphora_join(entity, recs, verb_patterns, qdate):
    """名字句无日期 → 同 session 共享关系 NP / 共享专名的日期句 join（Rachel 案）。
    名字句只要求含名字（parent 场景名字句常无事件动词: "sister-in-law, Rachel, is doing great"）。"""
    name_toks = {t.lower() for t in re.findall(r"[A-Za-z][a-z]+", entity)}
    for i, (si, ti, xi, s, d) in enumerate(recs):
        low = s.lower()
        if not sum(1 for t in name_toks if re.search(r'\b' + t + r'\b', low)):
            continue
        # 关系 NP + 共现专名作 join key
        keys = {n for n in RELNOUNS if n in low}
        proper = {t for t in re.findall(r'\b[A-Z][a-z]+\b', s)}
        for j, (sj, tj, xj, sj_txt, dj) in enumerate(recs):
            if sj != si: continue  # 同 session 内
            jl = sj_txt.lower()
            if not any(hits(p, sj_txt) for p in verb_patterns): continue  # 日期句须含事件动词
            share_rel = any(n in jl for n in keys)
            share_proper = bool(proper & {t for t in re.findall(r'\b[A-Z][a-z]+\b', sj_txt)} - {t for t in name_toks if t[0].isupper()})
            if share_rel or share_proper:
                days = resolve_days_ago(sj_txt, dj)
                if days is not None:
                    return days, sj_txt
    return None

# ---------- main ----------
def answer(q):
    m = GATE_A.match(q['question'].strip())
    if m:
        verb, e1, e2 = m.group(1).lower(), m.group(2).strip(), m.group(3).strip()
    else:
        m = GATE_B.match(q['question'].strip())
        if not m: return None
        verb, e1, e2 = m.group(1).lower(), m.group(2).strip(), m.group(3).strip()
    vp = VERBMAP[verb]
    recs, qdate = index_question(q)
    r1 = find_entity_evidence(e1, recs, vp, qdate)
    r2 = find_entity_evidence(e2, recs, vp, qdate)
    if r1 is None and is_name_entity(e1):
        r1 = anaphora_join(e1, recs, vp, qdate)
    if r2 is None and is_name_entity(e2):
        r2 = anaphora_join(e2, recs, vp, qdate)
    if r1 is None or r2 is None:
        missing = e1 if r1 is None else e2
        return ('ABSTAIN', f"no parent/meet evidence for: {missing}")
    d1, ev1 = r1; d2, ev2 = r2
    return (e1, d1, ev1) if d1 > d2 else (e2, d2, ev2)

if __name__ == '__main__':
    print('=== ECM prototype on neither-family 4 questions ===')
    n_ok = 0
    for qid in QIDS:
        q = next(x for x in DATA if x['question_id'] == qid)
        out = answer(q)
        pred, gt = out[0], q['answer']
        if 'not enough' in gt.lower():
            ok = (pred == 'ABSTAIN'); kind = 'abstain-twin'
        else:
            ok = (str(pred).lower() == gt.lower()); kind = 'compare'
        n_ok += ok
        print(f"\n[{qid}] {kind}")
        print(f"  Q: {q['question']}")
        print(f"  GT: {gt}")
        print(f"  PRED: {out if out else 'GATE-MISS'}")
        print(f"  {'✅' if ok else '❌'}")
    print(f"\n=== {n_ok}/4 ===")
