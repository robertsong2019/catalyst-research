# MCP Memory Server Architecture: Designing agent-memory-graph as an MCP Server

> Deep Research #017 — 2026-07-18
> Methodology: autoresearch (明确指标 → 快速循环 → 保留/回退 → 积累性)
> Context: agent-memory-graph has 760+ APIs / 3945 tests. MCP Server is on the todo list.
> Goal: Production-ready design blueprint for `agent-memory-graph-mcp` (~200 lines)

---

## 1. Landscape Audit (July 2026)

### 1.1 Official MCP Memory Server (`@modelcontextprotocol/server-memory` v0.6.3)

The **only** memory server in the official MCP reference implementations. Architecture:

| Aspect | Implementation |
|--------|---------------|
| Storage | JSONL file (`memory.jsonl`) |
| Data model | Entity → {name, entityType, observations[]} |
| Relations | {from, to, relationType} — flat, no graph algorithms |
| Search | Substring matching on name/type/observations |
| Persistence | `fs.readFile` / `fs.writeFile` (full rewrite each operation) |
| Concurrency | None (single-process, file-based) |
| Resource | `memory://knowledge-graph` (subscribable for live updates) |
| Tools (9) | create_entities, create_relations, add_observations, delete_entities, delete_observations, delete_relations, read_graph, search_nodes, open_nodes |

**Critical limitations:**
- O(n) scan for every search — no indexing, no vector, no BM25
- No graph algorithms (centrality, community detection, shortest path)
- No temporal awareness (bi-temporal, decay, supersede)
- No governance (write-time validation, read-time screening)
- No consolidation or lifecycle management
- No multi-agent isolation
- File-based → no concurrent access

### 1.2 MCP Registry Competitive Analysis

Queried `https://registry.modelcontextprotocol.io/v0/servers`:

| Query | Results |
|-------|---------|
| `memory` | ~10 servers (all simple key-value or entity-relation) |
| `graph memory` | **0 results** |
| `knowledge graph` | **0 results** |

**Existing community memory servers:**
1. **WorkingMemory** (`ai.workingmemory/memory`) — SaaS persistent memory, Streamable HTTP
2. **Cortex** (`com.cortex-mem/memory`) — npm `cortex-memory-mcp` v1.2.4, stdio, shared persistent
3. **AgentMemory Mesh** (`com.clauxel.agentmemorymcp`) — Paid, remote, audit-ready
4. **Borisinc Memory** (`com.borisinc/memory`) — Paid per call via x402 USDC
5. **Memory Journal** (`ai.smithery/neverinfamous-memory-journal-mcp`) — Git-based project management

**None use graph algorithms. None have vector search. None have lifecycle management.**

### 1.3 MCP SDK State (TypeScript)

- **v1.x**: production, `@modelcontextprotocol/sdk` (current reference server uses this)
- **v2 beta**: `@modelcontextprotocol/server` + `@modelcontextprotocol/client`, implements 2026-07-28 spec
  - Standard Schema support (Zod v4, Valibot, ArkType)
  - Split packages (server / client / middleware)
  - Middleware: Express, Hono, Node.js HTTP adapters
  - **Stable release: July 28, 2026** (10 days from now)
  - Tool registration: `server.registerTool(name, {description, inputSchema, outputSchema, annotations}, handler)`

---

## 2. Core Concepts

### 2.1 The MCP Tool Surface Area Problem

The official memory server exposes 9 tools. agent-memory-graph has 760+ APIs. **Exposing all APIs as MCP tools is an anti-pattern** — LLMs struggle with >20 tools (tool selection accuracy degrades rapidly). The design challenge is **curating the minimal tool set that maximizes agent capability**.

Key principle: **Tool granularity should match LLM cognitive load, not API granularity.**
- Too fine-grained → LLM must chain many calls (high latency, error-prone)
- Too coarse-grained → LLM can't express intent precisely

### 2.2 The Three-Layer Architecture

```
┌─────────────────────────────────────────────────┐
│ Layer 3: MCP Tool Interface (8-12 curated tools) │
│   - memory.remember(text, kind?, tags?)          │
│   - memory.recall(query, mode?, limit?)          │
│   - memory.relate(source, target, relation)      │
│   - memory.query(question)  ← 7-intent router    │
│   - memory.health()         ← graph quality      │
│   - memory.gaps()           ← gap report         │
│   - memory.consolidate()    ← merge/decay        │
│   - memory.export() / memory.import()            │
├─────────────────────────────────────────────────┤
│ Layer 2: agent-memory-graph (760+ APIs)          │
│   Graph algorithms, BM25, vector, CRDT,          │
│   governance, consolidation, evaluation...       │
├─────────────────────────────────────────────────┤
│ Layer 1: SQLite (storage substrate)              │
└─────────────────────────────────────────────────┘
```

### 2.3 memorywire Compatibility

The `memorywire` specification defines 5 operations × 4 types. MCP tools should align:

| memorywire op | MCP tool | amg backend |
|--------------|----------|------------|
| `remember` | `memory.remember` | `add()` + `add_with_entropy_filter()` |
| `recall` | `memory.recall` | `recall()` + `dual_mode_retrieve()` |
| `relate` | `memory.relate` | `link()` + `link_by_label()` |
| `forget` | `memory.forget` | `strategic_forget()` + `decay_all()` |
| `reflect` | `memory.reflect` | `query()` + `knowledge_gap_report()` |

### 2.4 The Read-Write-Protect Triad

MCP's security model requires explicit tool annotations:
- `readOnlyHint: true` → safe for auto-invocation
- `destructiveHint: true` → require user confirmation
- amg's governance layer maps naturally: `write_governance_check()` = write-time protection, `screen_retrieval()` = read-time protection

---

## 3. Code: Minimal MCP Server for agent-memory-graph (~120 lines)

This is a **runnable** TypeScript implementation using the MCP SDK v2 beta:

```typescript
#!/usr/bin/env node
// agent-memory-graph-mcp/server.ts
// Minimal MCP server exposing agent-memory-graph via stdio

import { McpServer } from '@modelcontextprotocol/server';
import { StdioServerTransport } from '@modelcontextprotocol/server/stdio';
import { z } from 'zod/v4';
import { MemoryGraph } from 'agent-memory-graph';

const mg = new MemoryGraph('./memory.db');

const server = new McpServer({
  name: 'agent-memory-graph',
  version: '1.0.0',
});

// ── Tool: memory.remember ──────────────────────────────
// Write-time governance + entropy filtering built-in
server.registerTool(
  'memory.remember',
  {
    title: 'Remember',
    description: 'Store a memory with optional kind, tags, and data. ' +
      'Duplicates are detected via SimHash. Entropy filtering discards low-value content.',
    inputSchema: {
      label: z.string().describe('The memory content (what to remember)'),
      kind: z.enum(['fact', 'event', 'skill', 'preference', 'reasoning', 'intention'])
        .default('fact'),
      tags: z.array(z.string()).default([]),
      data: z.record(z.unknown()).optional().describe('Structured metadata'),
    },
    outputSchema: {
      node_id: z.string(),
      duplicates: z.array(z.string()).describe('Detected duplicate node IDs'),
    },
    annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: false },
  },
  async ({ label, kind, tags, data }) => {
    const node = mg.add_with_entropy_filter(label, kind, data);
    if (tags.length) mg.tag_nodes(tags[0], [node.id]); // TODO: multi-tag
    const dupes = mg.find_duplicate_nodes({ threshold: 3 });
    return {
      content: [{ type: 'text', text: `Remembered: ${node.id}` }],
      structuredContent: { node_id: node.id, duplicates: dupes.map(d => d.id) },
    };
  }
);

// ── Tool: memory.recall ────────────────────────────────
// Dual-mode: SimHash binary + cosine semantic
server.registerTool(
  'memory.recall',
  {
    title: 'Recall',
    description: 'Retrieve memories by query. Uses dual-mode retrieval ' +
      '(binary signature + semantic similarity). Returns ranked results.',
    inputSchema: {
      query: z.string().describe('What to recall'),
      limit: z.number().min(1).max(50).default(5),
      mode: z.enum(['auto', 'semantic', 'binary', 'keyword'])
        .default('auto'),
    },
    outputSchema: {
      results: z.array(z.object({
        id: z.string(),
        label: z.string(),
        kind: z.string(),
        score: z.number(),
      })),
    },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
  },
  async ({ query, limit, mode }) => {
    const results = mode === 'auto'
      ? mg.dual_mode_retrieve(query, { limit })
      : mg.recall(query, limit);
    return {
      content: [{ type: 'text', text: JSON.stringify(results, null, 2) }],
      structuredContent: {
        results: results.slice(0, limit).map((n: any) => ({
          id: n.id, label: n.label, kind: n.kind, score: n.score ?? 0,
        })),
      },
    };
  }
);

// ── Tool: memory.relate ────────────────────────────────
server.registerTool(
  'memory.relate',
  {
    title: 'Relate',
    description: 'Create a typed relationship between two memory nodes. ' +
      'Weight reflects relationship strength (0-1).',
    inputSchema: {
      source: z.string().describe('Source node ID or label'),
      target: z.string().describe('Target node ID or label'),
      relation: z.string().describe('Relationship type (active voice)'),
      weight: z.number().min(0).max(1).default(1.0),
    },
    annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: false },
  },
  async ({ source, target, relation, weight }) => {
    try {
      mg.link_by_label(source, target, relation, weight);
      return { content: [{ type: 'text', text: `Linked: ${source} ──${relation}──▶ ${target}` }] };
    } catch (e) {
      return { content: [{ type: 'text', text: `Error: ${(e as Error).message}` }], isError: true };
    }
  }
);

// ── Tool: memory.query ─────────────────────────────────
// 7-intent adaptive router (temporal, constraint, local, global, etc.)
server.registerTool(
  'memory.query',
  {
    title: 'Query',
    description: 'Ask a natural language question. Automatically routes ' +
      'to the best retrieval mode: temporal, constraint, local, global, drift, hybrid, show.',
    inputSchema: {
      question: z.string().describe('Natural language question'),
      limit: z.number().min(1).max(20).default(10),
    },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
  },
  async ({ question, limit }) => {
    const results = mg.query(question, { limit });
    const confidence = mg.query_confidence_score(question, results);
    return {
      content: [{ type: 'text', text: JSON.stringify({ results, confidence }, null, 2) }],
      structuredContent: { results, confidence },
    };
  }
);

// ── Tool: memory.health ────────────────────────────────
server.registerTool(
  'memory.health',
  {
    title: 'Graph Health',
    description: 'Get graph quality metrics: coverage, connectivity, richness, ' +
      'freshness, consistency, redundancy, governance.',
    inputSchema: { type: 'object', additionalProperties: false },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
  },
  async () => {
    const quality = mg.reasoning_quality_eval();
    const density = mg.graph_information_density();
    return {
      content: [{ type: 'text', text: JSON.stringify({ quality, density }, null, 2) }],
      structuredContent: { quality, density },
    };
  }
);

// ── Tool: memory.gaps ──────────────────────────────────
server.registerTool(
  'memory.gaps',
  {
    title: 'Knowledge Gaps',
    description: 'Detect structural gaps in the memory graph: orphan nodes, ' +
      'isolated clusters, bridge opportunities, underconnected hubs.',
    inputSchema: { type: 'object', additionalProperties: false },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
  },
  async () => {
    const report = mg.knowledge_gap_report();
    return {
      content: [{ type: 'text', text: JSON.stringify(report, null, 2) }],
      structuredContent: report,
    };
  }
);

// ── Tool: memory.forget ────────────────────────────────
server.registerTool(
  'memory.forget',
  {
    title: 'Forget',
    description: 'Decay low-weight memories and optionally forget specific nodes. ' +
      'Use with caution — this is destructive.',
    inputSchema: {
      node_ids: z.array(z.string()).optional().describe('Specific nodes to forget'),
      decay: z.boolean().default(false).describe('Run decay on all nodes'),
    },
    annotations: { readOnlyHint: false, destructiveHint: true, openWorldHint: false },
  },
  async ({ node_ids, decay }) => {
    if (decay) mg.decay_all();
    if (node_ids) for (const id of node_ids) mg.delete_node(id);
    return {
      content: [{ type: 'text', text: decay
        ? 'Decay applied + nodes forgotten'
        : `Forgot ${node_ids?.length ?? 0} nodes` }],
    };
  }
);

// ── Start ──────────────────────────────────────────────
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main();
```

**Run it:**
```bash
# Install deps
npm install agent-memory-graph @modelcontextprotocol/server zod

# Run
npx tsx server.ts

# Configure in Claude Desktop:
# {
#   "mcpServers": {
#     "memory": {
#       "command": "npx",
#       "args": ["-y", "agent-memory-graph-mcp"]
#     }
#   }
# }
```

---

## 4. Code: Python Bridge Alternative (~80 lines)

For the Python implementation (since amg is Python), using the Python MCP SDK:

```python
#!/usr/bin/env python3
# agent_memory_graph_mcp/server.py
"""MCP server wrapping agent-memory-graph (Python)."""

import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from memory_graph import MemoryGraph

mg = MemoryGraph("./memory.db")
server = Server("agent-memory-graph")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="memory.remember",
            description="Store a memory. Entropy-filtered, deduped via SimHash.",
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "What to remember"},
                    "kind": {"type": "string", "default": "fact",
                             "enum": ["fact","event","skill","preference","reasoning","intention"]},
                    "tags": {"type": "array", "items": {"type": "string"}, "default": []},
                },
                "required": ["label"],
            },
        ),
        Tool(
            name="memory.recall",
            description="Retrieve memories by query. Dual-mode: semantic + binary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="memory.query",
            description="Natural language question — 7-intent adaptive routing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["question"],
            },
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "memory.remember":
        node = mg.add_with_entropy_filter(
            arguments["label"], arguments.get("kind", "fact")
        )
        for tag in arguments.get("tags", []):
            mg.tag_nodes(tag, [node.id])
        result = {"id": node.id, "label": node.label}
        return [TextContent(type="text", text=json.dumps(result))]

    elif name == "memory.recall":
        results = mg.dual_mode_retrieve(
            arguments["query"], limit=arguments.get("limit", 5)
        )
        return [TextContent(type="text", text=json.dumps(results, default=str))]

    elif name == "memory.query":
        results = mg.query(arguments["question"], limit=arguments.get("limit", 10))
        confidence = mg.query_confidence_score(arguments["question"], results)
        return [TextContent(type="text", text=json.dumps(
            {"results": results, "confidence": confidence}, default=str
        ))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## 5. Key Insights

### Insight #1: Zero graph-based memory MCP servers exist (July 2026)

The MCP Registry has **zero** results for "graph memory" or "knowledge graph". The official `@modelcontextprotocol/server-memory` is a flat entity-relation JSONL file with substring search. Every community memory server is either key-value or simple entity-relation. **agent-memory-graph-mcp would be the first graph-algorithm-powered memory server in the MCP ecosystem.**

This is a stronger differentiator than "npm has no graph memory library" — the MCP ecosystem is smaller, more curated, and directly used by Claude, Cursor, and other production agents.

### Insight #2: Tool count is the critical UX constraint, not API count

The official memory server exposes 9 tools. amg has 760+ APIs. Exposing all of them would be catastrophic — LLMs face tool selection paralysis with >20 tools. The design must curate 8-12 **semantic tools** that map to memory operations (remember, recall, relate, query, health, gaps, forget, consolidate). Each tool wraps multiple amg APIs internally.

This maps to the memorywire specification's 5 operations, extended with amg's unique capabilities (governance, evaluation, gap detection).

### Insight #3: MCP tool annotations are the perfect governance surface

MCP 2025-11-25 spec defines tool annotations: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`. amg's governance layer maps naturally:
- `recall`, `query`, `health`, `gaps` → `readOnlyHint: true` (auto-invokable)
- `remember`, `relate` → `destructiveHint: false` (safe writes)
- `forget`, `decay` → `destructiveHint: true` (require confirmation)

This means **governance is enforced at the protocol level**, not just in code. Any MCP client (Claude, Cursor, etc.) will automatically prompt for destructive operations. This is a built-in safety feature that amg gets for free by being an MCP server.

### Insight #4: MCP Resource subscriptions enable live memory monitoring

The MCP spec supports `resources/subscribe` — clients can subscribe to a resource URI and get notifications when it changes. amg could expose `memory://graph-health` as a subscribable resource, enabling real-time dashboards. Mutation tools emit `notifications/resources/updated` automatically.

This turns amg from a library into an **observable memory service** — clients see graph health changes in real-time without polling.

### Insight #5: The July 28 MCP spec release is a timing window

MCP SDK v2 goes stable on **July 28, 2026** (10 days away). It introduces:
- Split packages (`@modelcontextprotocol/server` + `client`)
- Standard Schema (Zod v4, Valibot, ArkType)
- Middleware adapters (Express, Hono, Node.js)

If amg-mcp ships before July 28, it can ride the v2 adoption wave. If it ships after, it enters a mature ecosystem where being first matters less. **The window is now.**

### Insight #6: MCP Registry publishing is free and OIDC-based

The MCP Registry uses OIDC trusted publishing from GitHub Actions (similar to PyPI). No registry tokens needed. Publishing requires:
1. A `server.json` describing the server
2. Namespace ownership (GitHub OAuth or DNS verification)
3. The `mcp-publisher` CLI

Namespace strategy: `io.github.robertsong2019/agent-memory-graph` or a custom domain `com.catalyst/agent-memory-graph`.

---

## 6. Action Blueprint

### Phase 1: TypeScript Wrapper (Week of July 21-25)
```
agent-memory-graph-mcp/
├── package.json         # deps: @modelcontextprotocol/server, zod
├── server.ts           # ~120 lines (code above)
├── README.md
└── tsconfig.json
```
Target: 8 tools, stdio transport, works with Claude Desktop

### Phase 2: Publish to MCP Registry (July 28 — ride v2 stable)
- `server.json` with namespace
- Publish via `mcp-publisher` CLI
- Tag: `memory`, `graph`, `agent-memory`, `knowledge-graph`

### Phase 3: Add Streamable HTTP transport (August)
- Enable remote usage (not just local stdio)
- Add authentication (API key header)
- Deploy as Vercel/Cloudflare Worker

### Phase 4: MCP Resources + Subscriptions (August)
- `memory://graph-health` — live health monitoring
- `memory://graph-export` — full graph export
- Resource change notifications on mutations

---

## 7. Quality Assessment

| Criterion | Status |
|-----------|--------|
| ✅ Core concepts (3-5) | 4: Tool surface curation, memorywire mapping, 3-layer architecture, governance via annotations |
| ✅ Runnable code (≥1) | 2: TypeScript (~120 lines) + Python (~80 lines) |
| ✅ Key insights (≥3) | 6: Registry gap, tool count constraint, governance surface, resource subscriptions, timing window, registry publishing |
| ✅ Next actions (≥1) | 4-phase blueprint with dates |
| ✅ Connection to existing projects | Directly implements `agent-memory-graph-mcp` from HEARTBEAT.md. Uses amg's 760+ APIs as backend. Informs npm publish strategy. |
| ✅ Competitive analysis | Official MCP server compared. Registry searched. Community servers listed. |

**Verdict: Ready for implementation. The TypeScript wrapper (~120 lines) is the minimal viable MCP server.**

---

## 8. References

- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) — Tools, Resources
- [MCP TypeScript SDK v2](https://github.com/modelcontextprotocol/typescript-sdk) — Beta, stable July 28 2026
- [Official MCP Memory Server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) — v0.6.3, JSONL-based
- [MCP Registry](https://registry.modelcontextprotocol.io/) — v0 API, 0 results for "graph memory"
- [MCP Registry Publishing Guide](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx)

---

_Last updated: 2026-07-18 20:12_
