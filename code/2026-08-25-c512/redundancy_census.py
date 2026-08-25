"""C512-A falsification census: sidechannel trigger-surface redundancy.

#088 projected 6.1x (135k embeds / 22k unique) assuming ALL 500
questions embed their haystack. Reality: the side-channel is
form-gated (C473 discipline) — only pref(embed)+assistant-recall
(hybrid) forms fire, and LME-cleaned per-question haystacks are
nearly disjoint. Run: python3 redundancy_census.py (needs
/tmp/lme_s.json, ~90s).
"""
import json, sys
sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
from amg_bench_quality import chunk_session_text, sidechannel_form

d = json.load(open("/tmp/lme_s.json"))

def chunks_of(q):
    out = []
    for s in (q.get("haystack_sessions") or []):
        msgs = s if isinstance(s, list) else s.get("messages", s.get("turns", []))
        text = " ".join(str(t.get("content", "")) for t in msgs)
        out.extend(chunk_session_text(text))
    return out

forms = {}
for i, q in enumerate(d):
    f = sidechannel_form(str(q.get("question", "")))
    if f:
        forms.setdefault(f, []).append(i)

total_all = 0
for name, idxs in sorted(forms.items()):
    uniq, total = set(), 0
    for i in idxs:
        cs = chunks_of(d[i])
        total += len(cs)
        uniq.update(cs)
    total_all += total
    print(f"{name}: n={len(idxs)} total={total} unique={len(uniq)} "
          f"redundancy={total / max(len(uniq), 1):.2f}x")
print(f"TRIGGER SURFACE: {sum(len(v) for v in forms.values())}/500 questions, "
      f"{total_all} embeds vs #088's projected 135,000")
