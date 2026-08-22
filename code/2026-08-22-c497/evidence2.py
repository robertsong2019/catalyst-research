import json
data = json.load(open('/tmp/lme_s.json'))
targets = {'gpt4_88806d6e','gpt4_0a05b494','gpt4_fe651585','gpt4_fe651585_abs'}
KEYS = ['met','meet','tom','mark','sarah','jam','farmer','tourist','australia','rachel','alex','twin','adopt','born','parent','january','thursday','saturday','week','month']
for q in data:
    if q['question_id'] not in targets: continue
    def L(x): return x if isinstance(x, list) else eval(x)
    hs, hsids, aid = L(q['haystack_sessions']), L(q['haystack_session_ids']), L(q['answer_session_ids'])
    hd = L(q['haystack_dates'])
    print('='*80); print(q['question_id'], '->', q['question'], '| GT:', q['answer'])
    # also scan ALL haystack user turns (evidence may live outside answer sessions)
    for si, sess in enumerate(hs):
        sid = hsids[si]
        marks = []
        for t, turn in enumerate(sess):
            if turn['role'] != 'user': continue
            for sent in turn['content'].replace('\n',' ').split('. '):
                low = sent.lower()
                if any(k in low for k in KEYS):
                    marks.append((t, sent.strip()))
        if marks:
            tag = '★ANS' if sid in aid else '    '
            print(f'{tag} {sid} @ {hd[si]}')
            seen=set()
            for t, s in marks:
                k=(t,s[:60])
                if k in seen: continue
                seen.add(k)
                print(f'    [{t}] {s[:280]}')
