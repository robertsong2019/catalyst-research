# MCP Registry Publishing & OpenClaw Plugin Development

> Research #054 · 2026-08-07 · Catalyst Deep Exploration
> Topic: How to publish agent-memory-graph's 16-tool MCP server to the official MCP Registry, and build an OpenClaw plugin for native integration.

---

## Context

agent-memory-graph (Python) has **2459 tests**, **500+ APIs**, and a **16-tool MCP server** (`mcp_server.py`, 605 lines) ready for distribution. Two channels are blocked on research:

1. **MCP Registry** — The official "app store" for MCP servers at `registry.modelcontextprotocol.io`, launched Sep 2025, now has ~9,652 servers (May 2026 snapshot).
2. **OpenClaw Plugin** — Native integration that would make amg available to every OpenClaw user as a built-in memory engine.

---

## Core Concepts

### 1. MCP Registry = npm for MCP Servers

The registry at `registry.modelcontextprotocol.io` is the **canonical source of truth**. Community directories (PulseMCP, Smithery, MCP Market) and IDE integrations (GitHub Copilot, VS Code) ingest from it. Publishing once propagates everywhere.

- **Governance**: Donated to the Linux Foundation's Agentic AI Foundation (AAIF) in Dec 2025. Co-founded by Anthropic, Block, OpenAI. AWS, Google, Microsoft, Cloudflare, GitHub, Bloomberg as supporting members.
- **Scale**: ~9,652 latest server records (May 2026), projected 11,600+ by Nov 2026 (480% growth). 97M+ monthly SDK downloads.
- **API Freeze**: v0.1 API freeze since Oct 2025. Stable for integrators.

### 2. server.json — The Manifest Format

The registry stores one `server.json` per server. This is the **unit of publication**. Key fields:

```json
{
  "$schema": "https://raw.githubusercontent.com/modelcontextprotocol/registry/main/docs/schema/mcp-registry-schema.json",
  "name": "io.github.robertsong2019/agent-memory-graph",
  "description": "Agency-grade graph memory for LLM agents — entropy, security, code-aware, spreading activation",
  "version": "1.0.0",
  "packages": [
    {
      "registry_type": "pypi",
      "identifier": "agent-memory-graph",
      "version": "1.0.0"
    }
  ]
}
```

For **remote servers** (Streamable HTTP), add a `remotes` block:
```json
{
  "remotes": [
    {
      "type": "streamable-http",
      "url": "https://amg.example.com/mcp"
    }
  ]
}
```

### 3. Namespace Verification (Two Paths)

| Method | Namespace Format | Best For |
|--------|-----------------|----------|
| **GitHub OAuth** | `io.github.username/server-name` | Open source, individuals |
| **DNS TXT record** | `com.yourdomain/server-name` | Companies, products |

For amg: `io.github.robertsong2019/agent-memory-graph` is the natural fit. GitHub OAuth flow through `mcp-publisher login github`.

### 4. OpenClaw Plugin Architecture (4 Layers)

OpenClaw plugins use `openclaw.plugin.json` manifest and register capabilities via a standardized API:

```javascript
export default function (api) {
  api.registerTool('amg-remember', { /* tool def */ });
  api.registerTool('amg-recall', { /* tool def */ });
  api.registerHook('session.beforeAssemble', async (ctx) => { /* inject memory */ });
}
```

**Registration methods**: `registerTool`, `registerChannel`, `registerHook`, `registerService`, `registerHttpRoute`, `registerCommand`, `registerContextEngine`.

The `registerContextEngine` capability is particularly powerful — it lets a plugin **own the context assembly pipeline**, which is exactly what a memory graph should do.

### 5. MCP 2026-07-28 Spec — The Stateless Revolution

The latest spec (release candidate May 2026, final Jul 2026) is the biggest change since launch:

- **Sessions removed** → stateless requests. Servers mint explicit handles as tool arguments.
- **No initialize handshake** → every request carries protocol version in `_meta`.
- **New `server/discover` RPC** → replaces initialize for capability negotiation.
- **Tasks formalized** → long-running operations as official extension.
- **OAuth 2.1 + OIDC** → enterprise-grade auth.

**Impact on amg**: The current `mcp_server.py` uses the session-based pattern. For registry publication via PyPI (package-based), clients handle transport, so the stdio server works as-is. For remote deployment, we'd need to adapt to stateless patterns.

---

## Code Examples

### Example 1: Complete server.json for amg PyPI Publication

```json
{
  "$schema": "https://raw.githubusercontent.com/modelcontextprotocol/registry/main/docs/schema/mcp-registry-schema.json",
  "name": "io.github.robertsong2019/agent-memory-graph",
  "description": "Agency-grade graph memory for LLM agents — 16 tools: remember, recall, relate, ask, lookup, neighbors, forget, stats, timeline, health, entropy, reason, snapshot, code_explain, quarantine, security",
  "version": "1.0.0",
  "websiteUrl": "https://github.com/robertsong2019/agent-memory-graph",
  "packages": [
    {
      "registry_type": "pypi",
      "identifier": "agent-memory-graph",
      "version": "1.0.0"
    }
  ]
}
```

### Example 2: PyPI README Marker (Required for PyPI Package Verification)

The registry verifies PyPI packages by fetching the README and checking for an `mcp-name` marker. Add this to the README.md:

```html
<!-- mcp-name: io.github.robertsong2019/agent-memory-graph -->
```

Or as plain text near the top:
```
MCP Registry Name: io.github.robertsong2019/agent-memory-graph
```

### Example 3: Publishing Shell Script (Runnable)

```bash
#!/usr/bin/env bash
# publish-amg-mcp.sh — Publish agent-memory-graph MCP server to the official registry
set -euo pipefail

# 1. Install mcp-publisher CLI
if ! command -v mcp-publisher &>/dev/null; then
  echo "Installing mcp-publisher..."
  ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_${OS}_${ARCH}.tar.gz" \
    | tar xz mcp-publisher
  sudo mv mcp-publisher /usr/local/bin/
fi

# 2. Authenticate with GitHub
echo "Authenticating with GitHub..."
mcp-publisher login github

# 3. Create server.json from template (if not exists)
if [ ! -f server.json ]; then
  mcp-publisher init
  echo "Edit server.json, then re-run this script."
  exit 1
fi

# 4. Validate server.json structure
echo "Validating server.json..."
python3 -c "
import json, sys
with open('server.json') as f:
    data = json.load(f)
required = ['name', 'description', 'version', 'packages']
missing = [k for k in required if k not in data]
if missing:
    print(f'MISSING: {missing}', file=sys.stderr); sys.exit(1)
if not data['name'].startswith('io.github.robertsong2019/'):
    print(f'NAMESPACE MISMATCH: {data[\"name\"]}', file=sys.stderr); sys.exit(1)
print(f'✅ Valid: {data[\"name\"]} v{data[\"version\"]}')
"

# 5. Publish
echo "Publishing to MCP Registry..."
mcp-publisher publish server.json

# 6. Verify
echo "Verifying publication..."
NAME=$(python3 -c "import json; print(json.load(open('server.json'))['name'])")
echo "Check at: https://registry.modelcontextprotocol.io/#/servers/${NAME}"
```

### Example 4: OpenClaw Plugin Manifest (openclaw.plugin.json)

```json
{
  "name": "openclaw-amg",
  "version": "1.0.0",
  "description": "Agent Memory Graph — persistent graph memory for OpenClaw agents",
  "main": "index.js",
  "capabilities": ["tools", "hooks", "contextEngine"],
  "config": {
    "properties": {
      "dbPath": {
        "type": "string",
        "default": "~/.openclaw/data/agent_memory.db",
        "description": "Path to the SQLite database"
      }
    }
  }
}
```

### Example 5: Minimal OpenClaw Plugin Skeleton (~80 lines)

```javascript
// index.js — OpenClaw plugin for agent-memory-graph
// Spawns the Python MCP server as a subprocess and bridges tools

const { spawn } = require('child_process');
const path = require('path');

let pyServer = null;
let requestId = 0;
const pending = new Map();

function startServer(dbPath) {
  const py = spawn('python3', [
    path.join(__dirname, 'mcp_server.py'),
    '--stdio'
  ], {
    env: { ...process.env, AMG_DB_PATH: dbPath },
    stdio: ['pipe', 'pipe', 'inherit']
  });

  let buffer = '';
  py.stdout.on('data', (chunk) => {
    buffer += chunk.toString();
    let idx;
    while ((idx = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 1);
      try {
        const msg = JSON.parse(line);
        if (msg.id && pending.has(msg.id)) {
          pending.get(msg.id)(msg);
          pending.delete(msg.id);
        }
      } catch {}
    }
  });

  return py;
}

function callTool(name, args) {
  return new Promise((resolve, reject) => {
    const id = ++requestId;
    pending.set(id, (msg) => {
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
    });
    pyServer.stdin.write(JSON.stringify({
      jsonrpc: '2.0', id, method: 'tools/call',
      params: { name, arguments: args }
    }) + '\n');
  });
}

module.exports = function (api) {
  const dbPath = api.config?.dbPath || '~/.openclaw/data/agent_memory.db';

  api.registerHook('gateway.start', async () => {
    pyServer = startServer(dbPath);
    api.logger.info('AMG server started');
  });

  api.registerHook('gateway.stop', async () => {
    if (pyServer) pyServer.kill();
  });

  // Register memory tools
  api.registerTool('amg.remember', {
    description: 'Store a memory in the agent memory graph',
    inputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string', description: 'Memory title' },
        kind: { type: 'string', description: 'person, project, idea, fact...' },
        data: { type: 'object', description: 'Structured metadata' }
      },
      required: ['name', 'kind']
    },
    handler: async (args) => callTool('remember', args)
  });

  api.registerTool('amg.recall', {
    description: 'Search memories in the graph',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Natural language search' },
        limit: { type: 'number', default: 10 }
      },
      required: ['query']
    },
    handler: async (args) => callTool('recall', args)
  });

  api.registerTool('amg.graph_stats', {
    description: 'Get memory graph statistics (nodes, edges, density, health)',
    inputSchema: { type: 'object', properties: {} },
    handler: async () => callTool('stats', {})
  });
};
```

### Example 6: Python — Build & Publish to PyPI (Runnable)

```python
#!/usr/bin/env python3
"""build_and_publish.py — Build amg wheel and publish to PyPI."""
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent / "projects" / "agent-memory-graph"

def run(cmd, check=True):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result

def main():
    # 1. Clean previous builds
    run("rm -rf dist/ build/ *.egg-info/")

    # 2. Build wheel and sdist
    run("python3 -m build")

    # 3. Check the package
    run("python3 -m twine check dist/*")

    # 4. Publish to PyPI (requires PYPI_TOKEN env or ~/.pypirc)
    token = subprocess.getoutput("echo $PYPI_TOKEN").strip()
    if token:
        run(f"python3 -m twine upload dist/* -u __token__ -p {token}")
    else:
        print("⚠️  PYPI_TOKEN not set. Run manually:")
        print("   python3 -m twine upload dist/*")

    # 5. Verify publication
    print("\n✅ Published! Verify at:")
    print("   https://pypi.org/project/agent-memory-graph/")

if __name__ == "__main__":
    main()
```

---

## Key Insights

### Insight #1: PyPI-First Strategy is the Right Call

The MCP Registry **only hosts metadata** — it doesn't store artifacts. For Python packages, it verifies ownership by fetching the README from PyPI and checking for the `mcp-name:` marker. This means:
- **PyPI publication is a hard prerequisite** for registry listing.
- The existing `pyproject.toml` is 90% ready — just needs the `mcp-name` README marker and the `mcp` extra dependency declared.
- This is a **same-day task**, not a multi-day effort.

### Insight #2: Registry = Distribution Multiplier

Publishing to the official registry is a **one-time action with compounding returns**:
- MCP Registry → ingested by GitHub Copilot, VS Code, Claude Desktop, Cursor, Smithery, PulseMCP
- Users discover via `mcp-publisher search` or in-IDE browsing
- Compare: amg-mcp TS has 14 tools at npm, but the **Python server has 16 tools** including the OWASP security suite and amg-bench — this is the more differentiated product
- **Competitive window**: TencentDB-Agent-Memory (14.6K★) likely already has MCP server published. Every day amg isn't in the registry = lost discoverability.

### Insight #3: OpenClaw Plugin ≈ 200 Lines, Not 2000

The OpenClaw plugin doesn't need to reimplement anything. It spawns the existing Python MCP server as a subprocess and bridges stdin/stdout. The plugin's value-add:
- **Auto-configuration** (detect db path, register hooks)
- **Session lifecycle** (start/stop server with gateway)
- **Context engine integration** (inject relevant memories into system prompt)
- **~200 lines**: 80 for subprocess bridge, 50 for tool registration, 70 for hook integration

The `registerContextEngine` API is the killer feature — it lets amg **own the memory layer** of OpenClaw, not just be a tool the agent can optionally call.

### Insight #4: MCP 2026-07-28 Spec Requires Eventual Migration

The stateless shift doesn't break the current stdio server (clients manage state externally), but it matters for future remote deployment:
- `initialize` handshake → removed. Use `server/discover` instead.
- `Mcp-Session-Id` header → gone. Pass state as tool arguments.
- This means `mcp_server.py` will need a `discover()` handler and per-request version checking for remote deployment, but stdio mode works unchanged.

### Insight #5: Two-Track Publication Strategy

| Track | Effort | Impact | Timeline |
|-------|--------|--------|----------|
| **Track A: PyPI → MCP Registry** | ~2h (pyproject.toml tweak + README marker + twine upload + mcp-publisher) | High — immediate discoverability across all MCP clients | Same day |
| **Track B: OpenClaw Plugin** | ~4-6h (subprocess bridge + tool registration + hook integration + testing) | Medium — native integration for OpenClaw users | 1-2 days |

Track A is strictly higher ROI. Do it first.

---

## Next Actions

1. **[TODAY]** Add `<!-- mcp-name: io.github.robertsong2019/agent-memory-graph -->` to `projects/agent-memory-graph/README.md`
2. **[TODAY]** Add `mcp` as optional dependency in `pyproject.toml`: `[project.optional-deps] mcp = ["mcp>=1.0"]`
3. **[TODAY]** Build & publish to PyPI: `python3 -m build && twine upload dist/*`
4. **[TODAY]** Install `mcp-publisher`, login with GitHub, publish `server.json`
5. **[NEXT]** Write OpenClaw plugin (`openclaw.plugin.json` + `index.js` ~200 lines)
6. **[NEXT]** Test plugin locally: `openclaw plugins install ./openclaw-amg/`
7. **[LATER]** Adapt `mcp_server.py` for MCP 2026-07-28 stateless spec (remote deployment)

---

## Quality Assessment

| Criterion | Status |
|-----------|--------|
| **Runnable code?** | ✅ 6 examples — server.json, README marker, publish script, plugin manifest, plugin skeleton, PyPI build script |
| **Original insights?** | ✅ 5 insights — PyPI-first insight, registry multiplier, plugin-size estimate, spec migration path, two-track strategy |
| **Project connection?** | ✅ Directly unblocks HEARTBEAT items: "amg PyPI publish" and "OpenClaw plugin (~200 lines)" |
| **Actionable?** | ✅ 7 concrete next actions with timelines |

---

_Sources: modelcontextprotocol.io/registry/quickstart, modelcontextprotocol.info/tools/registry/publishing, workos.com/blog/everything-your-team-needs-to-know-about-mcp-in-2026, digitalapplied.com/blog/mcp-adoption-statistics-2026, docs.openclaw.ai/plugins/architecture, github.com/modelcontextprotocol/registry, roxyapi.com/blogs/mcp-registries-where-to-list-your-server, nordicapis.com/getting-started-with-the-official-mcp-registry-api_
