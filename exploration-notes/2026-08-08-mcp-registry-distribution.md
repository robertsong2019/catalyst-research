# MCP Registry & Distribution Strategy — 2026-08-08

> **Research Target:** How to publish agent-memory-graph's 16-tool MCP server to the official MCP Registry and maximize distribution.
> **Relevance:** Unblocks HEARTBEAT.md "MCP registry publish" — amg Python MCP server is ready at 16 tools.

---

## 核心概念 (5)

### 1. Official MCP Registry (registry.modelcontextprotocol.io)

The official registry launched **September 8, 2025** in preview, reached **API freeze v0.1** on October 24, 2025, and now hosts **~2,000 servers** (9,652 latest-version records / 28,959 total with history as of May 2026). Governed under the **Linux Foundation** since December 2025.

- **Purpose:** "App store for MCP servers" — discovery + publication
- **Governance:** Registry Working Group led by Radoslav Dimitrov (Stacklok), with maintainers from Anthropic, GitHub, PulseMCP
- **API:** REST, currently at v0.1 freeze. Core endpoints: `GET /v0/servers` (list), `GET /v0/servers/{id}` (detail), `POST /v0/publish` (publish)
- **Trust model:** Reviewer-based approval — trusted reviewers from Anthropic, GitHub, Microsoft verify schema validity

### 2. server.json Manifest Format

The registry requires a standardized `server.json` manifest (inspired by npm's `package.json`). Key fields:

```json
{
  "$schema": "https://raw.githubusercontent.com/modelcontextprotocol/registry/main/src/schema.json",
  "name": "io.github.robertsong2019/agent-memory-graph",
  "description": "Cognitive memory graph for AI agents — 550+ APIs, entropy framework, spreading activation, OWASP security suite",
  "version": "1.0.0",
  "websiteUrl": "https://github.com/robertsong2019/agent-memory-graph",
  "packages": [
    {
      "registryType": "pypi",
      "identifier": "agent-memory-graph",
      "version": "1.0.0",
      "transport": { "type": "stdio" }
    }
  ]
}
```

**Critical rules:**
- `name` uses **reverse DNS namespace** (e.g., `io.github.username/server-name`)
- Must match the namespace you're authenticated to publish under
- `packages[].transport.type` can be `stdio` or `streamable-http`
- Each tool must have a valid `inputSchema` in the server's tool definitions

### 3. MCP 2026-07-28 Spec — The Stateless Revolution

The biggest protocol change since launch went **final on July 28, 2026**:

| Before (2025-11-25) | After (2026-07-28) |
|---------------------|---------------------|
| Initialize handshake required | **No handshake** — each POST is self-describing |
| Session-based (Mcp-Session-Id) | **Stateless** — every request stands alone |
| HTTP+SSE transport | **Deprecated** (12-month window) → Streamable HTTP |
| Roots, Sampling, Logging = core | **Deprecated** → use OTel for logging, direct LLM calls for sampling |
| No formal deprecation policy | **SEP-2596**: 12-month minimum deprecation window |

**Impact on amg:** The current `mcp_server.py` uses the old `mcp.server.Server` + `stdio_server` pattern. For registry publication, it must be updated to the 2026-07-28 protocol version using **FastMCP 3.x** or **mcp SDK v2.x**.

### 4. Distribution Channels (3 Layers)

```
Layer 1: Official MCP Registry
  └─ registry.modelcontextprotocol.io (the canonical source)
  └─ Discovered by Claude Desktop, Cursor, VS Code, etc.

Layer 2: Smithery (smithery.ai)
  └─ 30K+ developers, hosted + local options
  └─ Handles OAuth, versioning, analytics
  └─ `smithery install --server=github.com/user/repo`

Layer 3: Direct Distribution
  └─ PyPI (`pip install agent-memory-graph`)
  └─ npm (TypeScript SDK)
  └─ GitHub Releases
  └─ OpenClaw Plugin (~200 lines, fastest for OpenClaw users)
```

**Smithery security note:** GitGuardian found a critical path traversal vulnerability in Smithery's hosted build pipeline (2025) that could expose all hosted servers' secrets. Since patched, but highlights the risk of centralized hosting.

### 5. FastMCP 3.x — The De Facto Standard

FastMCP (now maintained by PrefectHQ) powers **70% of all MCP servers across all languages**. Key features for publishing:

- **FastMCP 3.0** (January 19, 2026): Component versioning, granular authorization, **OpenTelemetry instrumentation** built-in, multiple provider types
- **FastMCP 3.3** (May 15, 2026): Slim packaging split — standalone component imports don't pull in server stack
- **Migration:** `from mcp.server.fastmcp import FastMCP` → `from fastmcp import FastMCP`
- **2026-07-28 support:** FastMCP 3.x handles stateless protocol automatically

---

## 可运行代码示例

### Example 1: Minimal server.json for amg MCP Registry Publication

```json
{
  "$schema": "https://raw.githubusercontent.com/modelcontextprotocol/registry/main/src/schema.json",
  "name": "io.github.robertsong2019/agent-memory-graph",
  "description": "Cognitive memory graph with 550+ APIs: entropy framework, spreading activation, OWASP security suite, code-aware analysis",
  "version": "1.0.0",
  "websiteUrl": "https://github.com/robertsong2019/agent-memory-graph",
  "repository": {
    "type": "git",
    "url": "https://github.com/robertsong2019/agent-memory-graph"
  },
  "license": "MIT",
  "keywords": ["mcp", "memory", "graph", "agent", "entropy", "cognitive"],
  "packages": [
    {
      "registryType": "pypi",
      "identifier": "agent-memory-graph",
      "version": "1.0.0",
      "transport": { "type": "stdio" }
    }
  ]
}
```

### Example 2: Publish via mcp-publisher CLI

```bash
#!/bin/bash
# MCP Registry Publishing Script for agent-memory-graph
# Prerequisites: Go installed (for building CLI from source)

# Step 1: Build the mcp-publisher CLI
git clone https://github.com/modelcontextprotocol/registry /tmp/mcp-registry
cd /tmp/mcp-registry
make publisher

# Step 2: Authenticate with GitHub (one-time)
./bin/mcp-publisher login github
# → Opens browser for GitHub OAuth flow
# → Grants publish rights to io.github.robertsong2019/ namespace

# Step 3: Validate manifest before publishing
./bin/mcp-publisher publish --dry-run --file=/root/.openclaw/workspace/projects/agent-memory-graph/server.json
# → Validates schema, checks namespace auth, reports errors

# Step 4: Publish for real
./bin/mcp-publisher publish --file=/root/.openclaw/workspace/projects/agent-memory-graph/server.json

# Step 5: Verify
curl -s "https://registry.modelcontextprotocol.io/v0/servers?q=agent-memory-graph" | jq '.servers[] | {name, version, description}'
```

### Example 3: FastMCP 3.x Server Skeleton (2026-07-28 compatible)

```python
#!/usr/bin/env python3
"""
agent-memory-graph MCP Server (2026-07-28 spec via FastMCP 3.x)
Run: python3 mcp_server_v2.py
Install: pip install fastmcp
"""

from fastmcp import FastMCP
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from memory_graph import MemoryGraph

mcp = FastMCP(
    "agent-memory-graph",
    version="1.0.0",
    dependencies=["sqlite3"],  # native, no extra deps
)

_graph: MemoryGraph | None = None

def get_graph() -> MemoryGraph:
    global _graph
    if _graph is None:
        _graph = MemoryGraph()
    return _graph

# --- Core memory tools ---

@mcp.tool()
def remember(label: str, kind: str = "concept", data: str = "", tags: list[str] | None = None) -> dict:
    """Store a new memory node in the cognitive graph."""
    g = get_graph()
    node = g.add_node(label=label, kind=kind, data=data, tags=tags or [])
    return {"id": node.id, "label": node.label, "kind": node.kind}

@mcp.tool()
def recall(query: str, limit: int = 10) -> list[dict]:
    """Retrieve memories by semantic similarity search."""
    g = get_graph()
    results = g.search_unified(query, limit=limit)
    return [{"id": r.id, "label": r.label, "score": getattr(r, "score", 0)} for r in results]

@mcp.tool()
def relate(source_id: str, target_id: str, relation: str = "related_to") -> dict:
    """Create a typed edge between two memory nodes."""
    g = get_graph()
    edge = g.link(source_id, target_id, relation=relation)
    return {"source": source_id, "target": target_id, "relation": relation}

# --- Advanced tools ---

@mcp.tool()
def entropy(graph_id: str = "default") -> dict:
    """Compute Shannon entropy of the memory graph structure."""
    g = get_graph()
    return g.entropy_summary()

@mcp.tool()
def security(action: str = "dashboard") -> dict:
    """OWASP ASI06 security suite: trust scores, quarantine, audit."""
    g = get_graph()
    if action == "dashboard":
        return g.security_dashboard()
    elif action == "audit":
        return g.memory_audit_report()
    return {"error": f"Unknown action: {action}"}

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Example 4: Smithery Installation Config (smithery.yaml)

```yaml
# smithery.yaml — for Smithery distribution
name: agent-memory-graph
description: Cognitive memory graph with entropy framework and OWASP security
version: 1.0.0
runtime: python
entrypoint: mcp_server.py
config:
  schema:
    AMG_DB_PATH:
      type: string
      default: "~/.openclaw/data/agent_memory.db"
      description: "Path to the SQLite database file"
transport: stdio
```

---

## 关键洞察 (5)

### #221 — 无状态协议是分发催化剂

The 2026-07-28 stateless spec **removes the biggest barrier to MCP server distribution**: session management. Previously, every MCP server needed to maintain per-client session state, making horizontal scaling and registry hosting complex. Now, a stdio MCP server is truly stateless — each `tools/call` carries everything needed. This means **registry-hosted servers become trivially deployable**, and `pip install` + stdio is sufficient for 90% of use cases.

### #222 — PyPI优先策略是正确选择

amg's Python-first strategy aligns perfectly with the MCP ecosystem:
- **FastMCP** (Python) powers 70% of MCP servers
- **PyPI** is the dominant `registryType` for Python MCP servers in the registry
- The `mcp-publisher` CLI accepts `registryType: "pypi"` directly
- Once on PyPI, registry publication is a metadata-only step (no code hosting needed)

**Action:** Finish PyPI publish FIRST, then registry publish is just a `server.json` submission.

### #223 — 安全审计是注册的隐形门槛

The GitGuardian discovery of path traversal in Smithery's build pipeline reveals that **MCP server security is now a first-class concern**. The official registry has trusted reviewers who check for:
- Schema validity
- Capability implementation correctness
- Basic security scanning

amg already has the **OWASP ASI06 Security Suite** (6 APIs), which is a unique differentiator. The server.json description should explicitly mention "OWASP ASI06 security suite" as a keyword — no other MCP memory server has this.

### #224 — FastMCP迁移是技术债，也是机会

Current amg MCP server uses the old `mcp.server.Server` pattern. Migration to FastMCP 3.x:
- **Pros:** Automatic 2026-07-28 compliance, built-in OTel (aligns with Cycle 374/381 telemetry work), component versioning, CLI tools, MCP Inspector support
- **Cons:** Adds `fastmcp` as a dependency, requires testing all 16 tools
- **Effort:** ~2-3 hours for 16 tools (mostly mechanical decorator changes)
- **ROI:** Unlocks registry publication + Smithery distribution + modern protocol compliance

### #225 — OpenClaw Plugin 是最快的分发路径

While the MCP Registry requires reviewer approval and Smithery has its own process, the **OpenClaw plugin (~200 lines)** is the fastest distribution channel for the existing user base. It bypasses external review entirely and reaches OpenClaw users directly. The plugin can wrap the existing MCP server or even call the Python API directly.

**Priority order for maximum distribution:**
1. OpenClaw plugin (days, direct users)
2. PyPI publish (days, Python ecosystem)
3. MCP Registry (weeks, Claude Desktop/Cursor users)
4. Smithery (weeks, hosted/enterprise users)

---

## Next Actions

### Immediate (This Week)
1. **Write `server.json`** for agent-memory-graph — use Example 1 above as template
2. **Create PyPI package** — `pyproject.toml` + `python -m build` + `twine upload`
3. **Build `mcp-publisher` CLI** — `git clone` + `make publisher` (~5 min)

### Short Term (Next 2 Weeks)
4. **Migrate MCP server to FastMCP 3.x** — mechanical refactor of 16 tools to `@mcp.tool()` decorators
5. **Submit to MCP Registry** — `mcp-publisher publish` after PyPI is live
6. **Create Smithery config** — `smithery.yaml` for hosted distribution

### Validation Criteria
- [ ] `server.json` passes `mcp-publisher publish --dry-run`
- [ ] Registry search returns amg after publication
- [ ] `pip install agent-memory-graph && python -m agent_memory_graph.mcp_server` works
- [ ] All 16 tools functional via MCP Inspector
- [ ] 2026-07-28 protocol version reported in initialize response

---

## Quality Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 5 concepts | Registry, server.json, Stateless spec, Distribution channels, FastMCP |
| Runnable code (≥1) | ✅ 4 examples | server.json template, publish script, FastMCP skeleton, Smithery config |
| Key insights (≥3) | ✅ 5 insights | #221-225, each connects to amg project decisions |
| Next actions (≥1) | ✅ 6 actions | Prioritized: PyPI → Registry → Smithery |
| Project relevance | ✅ High | Directly unblocks HEARTBEAT.md "MCP registry publish" |
| Unique perspective | ✅ | Security differentiator (#223), distribution priority pyramid (#225), FastMCP migration ROI (#224) |

**Sources:** Official MCP Registry (github.com/modelcontextprotocol/registry), Developers Digest stateless migration guide, FastMCP docs (gofastmcp.com), MCP Python SDK (py.sdk.modelcontextprotocol.io), GitGuardian security analysis, Smithery.ai, Microsoft Learn publisher guide.
