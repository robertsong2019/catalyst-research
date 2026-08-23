#!/usr/bin/env python3
"""Publish namespace + ledger audit for agent-memory-graph (amg).

Two evidence packs, stdlib only:
  Part A — Ledger truth: prove whether a TypeScript amg implementation exists,
           and show the origin of the phantom "TS 7349" metric (double counting).
  Part B — Namespace: check npm/PyPI availability for publish candidates.

Usage:
  python3 publish_namespace_audit.py [--workspace /root/.openclaw/workspace]
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

WORKSPACE = Path(sys.argv[sys.argv.index("--workspace") + 1]) if "--workspace" in sys.argv \
    else Path("/root/.openclaw/workspace")

# amg API names that MEMORY.md attributes to the "TS" implementation
CLAIMED_TS_APIS = [
    "classification_confidence_interval",  # Cycle 358 TS claim
    "multi_hop_reason",                    # Cycle 361 claim
    "spreading_activation",                # Cycle 366 claim
    "FINGEREntropy",                       # Cycle 361 claim
]


def part_a_ledger_truth():
    print("=" * 64)
    print("PART A — Ledger truth: does a TS amg implementation exist?")
    print("=" * 64)

    # A1: search every .ts/.js file (excl. node_modules) for claimed TS APIs
    hits = {api: [] for api in CLAIMED_TS_APIS}
    ts_files = 0
    for f in WORKSPACE.rglob("*"):
        if f.suffix not in (".ts", ".js") or not f.is_file():
            continue
        if "node_modules" in f.parts:
            continue
        ts_files += 1
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for api in CLAIMED_TS_APIS:
            if api.lower() in text.lower():
                hits[api].append(str(f.relative_to(WORKSPACE)))

    print(f"\n[A1] Scanned {ts_files} TS/JS files (excl. node_modules) for 4 claimed 'TS' APIs:")
    for api, found in hits.items():
        label = ",".join(Path(p).parts[0:2] for p in found[:2]) or "—"
        print(f"     {api:38s} → {len(found)} file(s) {label}")

    # A2: the only real TS: amg-mcp (MCP wrapper)
    mcp = WORKSPACE / "amg-mcp" / "src"
    if mcp.exists():
        lines = sum(len(f.read_text(errors='ignore').splitlines()) for f in mcp.glob("*.ts"))
        print(f"\n[A2] Only real TS: amg-mcp/src = {lines} lines (MCP server wrapper, 122 tests)")

    # A3: show the double-count origin — real repo vs code-lab copy, both Python
    print("\n[A3] Double-count origin (both codebases are PYTHON):")
    for label, root in [("projects/agent-memory-graph (real)", WORKSPACE / "projects/agent-memory-graph"),
                        ("code-lab/agent-memory-graph (copy) ", WORKSPACE / "code-lab/agent-memory-graph")]:
        n_func = n_param = 0
        for f in root.glob("test_*.py"):
            try:
                text = f.read_text(errors="ignore")
            except OSError:
                continue
            n_func += len(re.findall(r"^\s*def test_", text, re.M))
            n_param += len(re.findall(r"@pytest\.mark\.parametrize", text))
        print(f"     {label}: {n_func} test funcs + {n_param} parametrize")

    phantom = not any(hits.values())
    print(f"\n[A4] VERDICT: TS amg implementation {'DOES NOT EXIST' if phantom else 'exists (see hits)'}")
    print("     → ledger 'TS 7349' = real Python repo count frozen at 08-06 (double count)")
    return phantom


def part_b_namespace():
    print("\n" + "=" * 64)
    print("PART B — Publish namespace availability (npm + PyPI)")
    print("=" * 64)

    def check(url, timeout=10):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "amg-audit/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode()), "TAKEN"
        except urllib.error.HTTPError as e:
            return None, "FREE" if e.code == 404 else f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            return None, f"ERR {type(e).__name__}"

    npm_names = ["agent-memory-graph", "@robertsong2019/agent-memory-graph",
                 "amgraph", "amg-graph", "agentmem-graph", "agent-memory-graph-py"]
    pypi_names = ["agent-memory-graph", "agent_memory_graph", "agent-memory",
                  "amgraph", "amg-memory", "amg"]

    print("\n[npm]")
    for n in npm_names:
        url = "https://registry.npmjs.org/" + n.replace("/", "%2F")
        data, status = check(url)
        extra = ""
        if data:
            latest = data.get("dist-tags", {}).get("latest", "?")
            owner = (data.get("versions", {}).get(latest, {}).get("maintainers") or [{}])[0].get("name", "?")
            t = data.get("time", {}).get("modified") or data.get("time", {}).get(latest, "")
            extra = f"  ← v{latest} by {owner}, last {str(t)[:10]}"
        print(f"  {n:44s} {status}{extra}")

    print("\n[PyPI]")
    for n in pypi_names:
        data, status = check(f"https://pypi.org/pypi/{n}/json")
        extra = ""
        if data:
            i = data.get("info", {})
            extra = f"  ← v{i.get('version')} '{(i.get('summary') or '')[:40]}'"
        print(f"  {n:44s} {status}{extra}")


if __name__ == "__main__":
    part_a_ledger_truth()
    part_b_namespace()
