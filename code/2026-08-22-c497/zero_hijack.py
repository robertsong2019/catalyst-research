import json, importlib.util
spec = importlib.util.spec_from_file_location('ecm', '/tmp/c497/ecm_proto.py')
ecm = importlib.util.module_from_spec(spec); spec.loader.exec_module(ecm)

DATA = ecm.DATA
fired = []
for q in DATA:
    qs = q['question'].strip()
    m = ecm.GATE_A.match(qs) or ecm.GATE_B.match(qs)
    if m:
        fired.append((q['question_id'], q['question_type'], qs[:100]))
print(f'gate fired on {len(fired)}/{len(DATA)} questions:')
for f in fired: print(' ', f)

# 与 C489 pairwise which-first 家族的碰撞检查（问题文本形态对比）
overlap = [q['question_id'] for q in DATA if re.search(r'\bwhich\b.*\bfirst\b|\bfirst\b.*\bor\b', q['question'].lower()) and (ecm.GATE_A.match(q['question'].strip()) or ecm.GATE_B.match(q['question'].strip()))]
print('overlap with which-first form:', overlap)
