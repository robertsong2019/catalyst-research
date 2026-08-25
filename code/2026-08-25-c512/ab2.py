"""C512-A definitive A/B (fixed single-wrap counter, slim memo)."""
import json, sys, time
sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
import amg_bench_quality as abq

COUNTER = {"texts": 0, "calls": 0}
WRAPPED = {"done": False}

def counting_probe():
    eng = abq.probe_sidechannel_engine.__wrapped__() if hasattr(
        abq.probe_sidechannel_engine, "__wrapped__") else None
    return eng

# wrap the REAL engine's embed_fn exactly once
eng = abq.probe_sidechannel_engine()
assert eng is not None, "no real engine"
_orig_fn = eng._embed_fn
def fn(texts):
    COUNTER["texts"] += len(texts)
    COUNTER["calls"] += 1
    return _orig_fn(texts)
eng._embed_fn = fn

def run_arm(memo_on):
    eng.chunk_memo = {} if memo_on else None
    eng.chunk_memo_hits = 0
    eng.chunk_memo_misses = 0
    COUNTER["texts"] = 0
    COUNTER["calls"] = 0
    t0 = time.time()
    report = abq.run_eval(abq.load_data("/tmp/c512/slice.json")
                          if hasattr(abq, "load_data") else DATA,
                          sidechannel=True)
    dt = time.time() - t0
    return report, dt, dict(COUNTER), eng.memo_stats()

with open("/tmp/c512/slice.json", encoding="utf-8") as f:
    DATA = json.load(f)
print(f"slice: {len(DATA)} pref questions", flush=True)

off, t_off, c_off, _ = run_arm(False)
print(f"ARM OFF: {t_off:.1f}s embed_texts={c_off['texts']} "
      f"calls={c_off['calls']}", flush=True)
on, t_on, c_on, s_on = run_arm(True)
print(f"ARM ON : {t_on:.1f}s embed_texts={c_on['texts']} "
      f"calls={c_on['calls']} memo={s_on}", flush=True)

def same(a, b):
    ra, rb = a["results"], b["results"]
    if len(ra) != len(rb):
        return False, "row count"
    for i, (x, y) in enumerate(zip(ra, rb)):
        for k in set(x) | set(y):
            if "latency" in k or k.endswith("_ms") or "time" in k:
                continue
            u, v = x.get(k), y.get(k)
            if isinstance(u, float) and isinstance(v, float):
                if u != v and not (u != u and v != v):
                    return False, f"row {i}.{k}: {u!r} vs {v!r}"
            elif u != v:
                return False, f"row {i}.{k}: {u!r} vs {v!r}"
    return True, "bitwise identical"

ok, why = same(off, on)
print(f"LOSSLESS: {ok} ({why})")
print(f"exact off={off.get('accuracy')} on={on.get('accuracy')}")
json.dump({"off": c_off | {"sec": round(t_off, 1)},
           "on": c_on | {"sec": round(t_on, 1), "memo": s_on},
           "lossless": ok, "why": why},
          open("/tmp/c512/ab2_result.json", "w"), indent=1)
