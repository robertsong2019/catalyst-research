"""Offline per-sentence score landscape for v2's 4 lost questions."""
import json, re, sys
sys.path.insert(0, '/root/.openclaw/workspace/projects/agent-memory-graph')
import amg_bench_quality as B
from amg_bench_quality import LongMemEvalAdapter

sys.path.insert(0, '/tmp/c473')
from ssa_v2_ab import _PREAMBLE_RE, _novelty

data = json.load(open('/tmp/c473/ssa56.json'))
LOST = ['d596882b', 'fca762bc', 'c8f1aeed', 'c7cf7dfd']

for item in data:
    qid = item['question_id']
    if not any(qid.startswith(l) for l in LOST):
        continue
    q = item['question']
    kws = B._keywords(q)
    qwords = set(kws)
    ad = LongMemEvalAdapter(seed_recall_k=40)
    haystack = item.get('haystack_sessions') or []
    sessions = [{"session_id": f"session_{j+1}", "messages": s}
                if isinstance(s, list) else s
                for j, s in enumerate(haystack)]
    hdates = item.get('haystack_dates') or []
    sdates = {}
    for j, dt in enumerate(hdates):
        if j >= len(sessions):
            break
        ss = sessions[j]
        sid = (ss.get('session_id') if isinstance(ss, dict) else None) or f"session_{j+1}"
        sdates[sid] = dt
    ad.ingest_sessions(sessions, session_dates=sdates)

    rows = []
    for nid, node in ad._nodes.items():
        if node.get('role') != 'assistant':
            continue
        for sent in B._split_sentences(node.get('label', '')):
            raw = B._keyword_hits(sent, kws)
            if raw < 5:
                continue
            s = sent.strip()
            nov = _novelty(s, qwords)
            pen = (1.0 if _PREAMBLE_RE.search(s[:120])
                   else 0.5 if _PREAMBLE_RE.search(s) else 0.0)
            rows.append((raw, round(nov, 2), pen,
                         round(raw * (0.3 + 0.7 * nov) * (1 - pen), 2),
                         s[:110]))
    rows.sort(key=lambda r: -r[3])
    print('=' * 108)
    print('QID', qid[:8], '| Q:', q[:100])
    print('GT :', str(item['answer'])[:100])
    print(f"{'raw':>3} {'nov':>4} {'pen':>3} {'v2':>5}  sentence")
    for r in rows[:12]:
        print(f"{r[0]:>3} {r[1]:>4} {r[2]:>3} {r[3]:>5}  {r[4]}")
