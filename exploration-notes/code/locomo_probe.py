#!/usr/bin/env python3
"""locomo_probe.py — LoCoMo schema probe + zero-cost session-recall baseline.

Research #067 companion. Stdlib-only: parses locomo10.json (verified
schema from snap-research/locomo), runs a keyword session-retrieval
baseline with per-category Recall@k, and measures evidence temporal
span (long-horizon difficulty). Ground truth = ``evidence`` dia_ids.

Usage:
    python3 locomo_probe.py [path/to/locomo10.json] [--limit N]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CATEGORIES = {1: "single_hop", 2: "multi_hop", 3: "temporal",
              4: "open_domain", 5: "adversarial"}

STOP = {"i", "the", "my", "we", "you", "it", "what", "when", "where",
        "who", "how", "that", "this", "there", "so", "and", "but",
        "did", "does", "do", "is", "are", "was", "were", "of", "or",
        "about", "say", "said", "tell", "told", "their", "with",
        "from", "any", "which", "why", "user", "current", "now",
        "a", "an", "in", "on", "at", "for", "to", "his", "her",
        "they", "them", "me", "him", "she", "he"}


def keywords(question: str) -> list[str]:
    words = re.findall(r"[A-Za-z']+", question.lower())
    return [w.removesuffix("'s") for w in words
            if len(w) > 2 and w not in STOP]


def token_hits(text: str, kws: list[str]) -> int:
    tokens = re.findall(r"[a-z']+", text.lower())
    return sum(1 for kw in kws if kw in tokens)


def parse_entry(entry: dict):
    """→ (sessions: list[(sid, turns_text)], qa: list[dict])."""
    conv = entry["conversation"]
    sessions = []
    for n in range(1, 40):
        key = f"session_{n}"
        if key not in conv:
            break
        turns = conv[key]
        sessions.append((n, [t["text"] for t in turns]))
    return sessions, entry["qa"]


def evidence_sessions(evidence: list[str]) -> set[int]:
    """"D1:3" → session 1."""
    out = set()
    for d in evidence:
        m = re.match(r"D(\d+)", str(d))
        if m:
            out.add(int(m.group(1)))
    return out


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).parent / "locomo10.json")
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) \
        if "--limit" in sys.argv else 0

    data = json.loads(Path(path).read_text())
    if limit:
        data = data[:limit]

    per_cat = defaultdict(lambda: Counter())
    span_dist = Counter()          # distance from last session
    overall = Counter()
    ctx_tokens = []

    for entry in data:
        n_sessions = len(re.findall(r'"session_\d+"',
                       json.dumps(list(entry["conversation"].keys()))))
        sessions, qa_list = parse_entry(entry)
        last = len(sessions)
        # Precompute per-session joined text + token sets.
        sess_text = {n: " ".join(turns) for n, turns in sessions}
        sess_tokens = {n: set(re.findall(r"[a-z']+",
                          t.lower())) for n, t in sess_text.items()}

        for qa in qa_list:
            cat = qa.get("category")
            gold = evidence_sessions(qa.get("evidence", []))
            kws = keywords(qa["question"])
            if not kws or not gold:
                continue
            # Score each session by distinct keyword hits.
            scores = sorted(
                ((sum(1 for kw in kws if kw in sess_tokens[n]), n)
                 for n in sess_tokens),
                key=lambda x: (-x[0], x[1]))
            ranked = [n for s, n in scores if s > 0] or [scores[0][1]]
            for k in (1, 2, 3):
                hit = bool(gold & set(ranked[:k]))
                per_cat[cat][f"r@{k}"] += hit
                overall[f"r@{k}"] += hit
                per_cat[cat][total_k := f"n@{k}"] += 1
                overall[f"n@{k}"] += 1
            overall["questions"] += 1
            per_cat[cat]["questions"] += 1
            span_dist[last - max(gold)] += 1
            ctx_tokens.append(len(sess_text[ranked[0]].split()) * 1.3)

    print(f"questions evaluated: {overall['questions']}")
    for k in (1, 2, 3):
        n, c = overall[f"n@{k}"], overall[f"r@{k}"]
        print(f"  overall Recall@{k}: {c}/{n} = {c / n:.3f}")
    print("\nper-category Recall@1:")
    for cat in sorted(per_cat):
        c = per_cat[cat]
        name = CATEGORIES.get(cat, f"cat{cat}")
        r1 = c["r@1"] / c["n@1"] if c["n@1"] else 0
        print(f"  {name:12s} n={c['n@1']:4d}  R@1={r1:.3f}")
    print("\nevidence temporal span (sessions back from latest):")
    for dist in sorted(span_dist):
        n = span_dist[dist]
        print(f"  -{dist:2d}: {n:4d} ({n / overall['questions']:.1%})")
    if ctx_tokens:
        print(f"\ntop-1 session context tokens/query: "
              f"avg={sum(ctx_tokens) / len(ctx_tokens):.0f} "
              f"(target < 2000; Mem0 ~6900)")


if __name__ == "__main__":
    main()
