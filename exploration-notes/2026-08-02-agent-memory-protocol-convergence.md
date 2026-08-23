# Research #043: Agent Memory Protocol Convergence — MCP, memorywire, and the Path to Standardization

> **Date**: 2026-08-02
> **Trigger**: HEARTBEAT task "amg: OpenClaw plugin (~200 lines)" + MCP Memory Server priority
> **Status**: ✅ Research complete. Blueprint for amg MCP server + OpenClaw plugin.
> **Maps to**: amg npm publish strategy, MCP Registry publish, OpenClaw plugin

---

## Executive Summary

The agent memory ecosystem is fragmenting along protocol lines. Three layers are converging: **MCP** (tool transport, now stateless as of 2026-07-28), **memorywire** (vendor-neutral memory wire format, v0 draft), and **OpenClaw plugins** (agent lifecycle hooks). amg's npm strategy must address all three to maximize reach. This research analyzes each layer, maps the competitive landscape (Cognee, PlugMem, graph-memory, Neo4j, Maximem, MemOS Cloud), and provides two runnable code examples: a stateless MCP memory server and an OpenClaw plugin skeleton.

---

## Core Concepts

### 1. memorywire: "MCP for Memory"

**Paper**: [arXiv:2606.01138](https://arxiv.org/html/2606.01138v2) (v2, June 2026)

memorywire is a vendor-neutral wire format that treats memory as a first-class protocol primitive — not just another tool endpoint. Its core thesis: "Memory is not a tool. It has its own lifecycle (write, recall, forget, merge, expire), its own taxonomy (semantic, episodic, procedural, emotional), and its own governance surface."

**5 Operations × 4 Types:**

| Operation | Purpose | Key Fields |
|-----------|---------|------------|
| `remember` | Write memory | agent_id, type, content, confidence, source, expires_at, approval_required |
| `recall` | Read memories | agent_id, query, k(1-1000), types(filter), hops(0-3), fusion(rrf/max/weighted) |
| `forget` | Delete memories | agent_id, ids OR filter, hard_delete(bool), reason |
| `merge` | Deduplicate | agent_id, canonical, duplicates, strategy(keep_canonical/merge_content/keep_highest_confidence) |
| `expire` | TTL policy | agent_id, policy(older_than_days ∧ type ∧ confidence_below ∧ no_recall_in_days), action(forget/archive/demote) |

**4 Memory Types:** semantic, episodic, procedural (FSM-encoded), emotional

**Governance Channel:** The novel contribution. When `approval_required=true`, writes are staged behind a `PENDING_APPROVAL_DELETED_AT=-1` sentinel. A diff-and-approve UI lets humans review before commit. This is the "Co-memorize" pattern standardized at the wire-format layer.

**Key Properties:**
- StateLess: Each request carries `agent_id`; no session state
- Async-first: `asyncio.gather(return_exceptions=True)` for fan-out
- RRF default fusion: Score-independent, robust against 1-of-NN malicious backends (proven: recall@5=1.000 under attack where MAX collapses to 0.500)
- JSON Schema 2020-12 source of truth; pydantic models as convenience layer

**MCP Relationship:** memorywire explicitly designs for composition with MCP, not competition. Three modes:
1. **memorywire-as-MCP-tool** (~10 lines glue): Expose 5 operations as MCP tools
2. **memorywire-as-MCP-resource**: Expose recall results as resources
3. **memorywire-as-MCP-extension** (proposed v0.5): `mcp.memory.v0` as formal MCP extension

**Roadmap:** v0 (draft, now) → v0.2 (user study, spec tightening) → v0.5 (freeze + IETF Internet-Draft + MCP-WG proposal) → v1.0 (stable)

### 2. MCP 2026-07-28: Stateless Core

The 2026-07-28 specification is the largest MCP revision since launch. Key changes for memory server design:

| Change | Impact on Memory Servers |
|--------|------------------------|
| **No handshake/sessions** (`initialize`/`initialized` removed) | Any request can hit any server instance. No sticky routing needed. |
| **`Mcp-Session-Id` header removed** | Horizontal scaling without shared session store |
| **Client info in `_meta`** | Every request carries client identity; use for per-agent routing |
| **`server/discover` method** | Clients fetch capabilities on demand, not at connection |
| **Multi Round-Trip Requests (MRTR)** | Replaces elicitation/sampling; enables async governance flows |
| **Header-based routing** (`Mcp-Method` header) | Route `tools/call` to beefier pool, `tools/list` to lightweight |
| **Cacheable list results** | `tools/list` responses cacheable; reduces overhead for tool discovery |
| **Tasks** | Long-running background workflows; perfect for async memory consolidation |

**For amg MCP server**: The stateless core is a perfect fit. amg is already stateless at the API level — every operation carries its graph context. No session management needed.

### 3. OpenClaw Plugin Landscape (Q3 2026)

The OpenClaw memory plugin ecosystem has exploded. At least 10 persistent-memory options exist:

| Plugin | Architecture | Key Differentiator | amg Overlap |
|--------|-------------|-------------------|-------------|
| **Cognee** | Docker + Graph + ECL pipeline | Knowledge graph extraction, Just-Postgres | Medium — graph but no entropy |
| **PlugMem** | Pipeline + coding-agent plugin | OpenClaw plugin shipping now, auto-save on `/reset` | High — similar positioning |
| **graph-memory** | Typed property graph + SQLite | 75% context compression, npm install | Medium — graph but simpler |
| **Neo4j Memory** | Neo4j + FastAPI bridge | Cypher queries, reasoning traces | Low — external DB dependency |
| **Maximem Vity** | Semantic graph + cross-channel | Chrome extension, cross-AI vault | Low — different market |
| **MemOS Cloud** | Cloud-hosted async recall | Cross-device, multi-agent isolation | Low — cloud-only |
| **Lossless Claw** | SQLite + graph compression | Zero data loss on compaction | Medium — SQLite + graph |
| **memU** | Hierarchical knowledge graph | Proactive anticipation | Medium — graph + proactive |
| **Memory LanceDB** | Vector-backed auto-recall | Local vector storage | Low — vector-only |
| **Mem Arch** | Plugin/Hook/Cron architecture | Code-level vs prompt-level memory | Medium — architecture patterns |

**Gap analysis**: No plugin uses entropy-aware retrieval, graph classification, or provenance tracking. amg's 925+ APIs (entropy framework, classification suite, provenance/lineage suite) are completely unique in the plugin ecosystem.

---

## Competitive Analysis: Where amg Fits

### The Protocol Triangle

```
            ┌─────────────────┐
            │   memorywire    │
            │  (wire format)  │
            │  5 ops × 4 types│
            └────────┬────────┘
                     │ composes with
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
┌─────────┐  ┌──────────────┐  ┌────────────┐
│   MCP   │  │  OpenClaw    │  │  Direct    │
│ (transport)│  │  (lifecycle) │  │  (npm)     │
└─────────┘  └──────────────┘  └────────────┘
```

**amg strategy**: Be the **only** library that speaks all three layers:
1. **npm library** — zero-dependency, 6622 tests, TypeScript-native
2. **MCP server** — stateless, 2026-07-28 compatible, 8-14 curated tools
3. **OpenClaw plugin** — lifecycle hooks (SessionStart/PostToolUse/SessionEnd)

No competitor does all three. Cognee has Docker+plugin but no MCP server. PlugMem has OpenClaw plugin but no npm library. Redis Agent Memory Server has MCP but no graph algorithms. graph-memory has npm but no entropy framework.

### Differentiator Matrix

| Capability | amg | Cognee | PlugMem | Mem0 | graph-memory |
|-----------|-----|--------|---------|------|-------------|
| Graph algorithms (entropy, classification) | ✅ 40+ APIs | ❌ | ❌ | ❌ | ❌ |
| Provenance/cascading invalidation | ✅ 4 APIs | ❌ | ❌ | ❌ | ❌ |
| Zero dependencies | ✅ | ❌ Docker | ❌ | ❌ | ✅ |
| MCP server (stateless 2026-07-28) | 🔄 TODO | ❌ | ❌ | ❌ | ❌ |
| OpenClaw plugin | 🔄 TODO | ✅ | ✅ | ❌ | ✅ |
| memorywire-compatible interface | 🔄 TODO | ❌ | ❌ | adapter only | ❌ |
| npm TypeScript-native | ✅ | ❌ Python | ❌ Python | ❌ Python | ✅ |
| Governance/diff-and-approve | partial | ❌ | ❌ | ❌ | ❌ |

---

## Code Examples

### Example 1: Stateless MCP Memory Server (TypeScript, MCP 2026-07-28 compatible)

This is a minimal MCP server that exposes amg's core operations as stateless MCP tools. Compatible with the 2026-07-28 spec (no sessions, `_meta` for client info).

```typescript
// amg-mcp-server.ts — Stateless MCP server for agent-memory-graph
// Compatible with MCP 2026-07-28 specification
// Zero external deps beyond MCP SDK

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

// --- amg imports (from your npm package) ---
// In production: import { MemoryGraph, entropy_scan, graph_classification } from 'agent-memory-graph';

// --- Tool schemas (JSON Schema 2020-12, matching memorywire v0) ---
const rememberSchema = {
  type: "object",
  properties: {
    agent_id: { type: "string", description: "Agent identifier" },
    content: { type: "string", description: "Memory content to store" },
    type: {
      type: "string",
      enum: ["semantic", "episodic", "procedural", "emotional"],
      description: "Memory type (Tulving/Squire taxonomy)"
    },
    confidence: {
      type: "number",
      minimum: 0,
      maximum: 1,
      default: 1.0,
      description: "Confidence score [0,1]"
    },
    source: { type: "string", description: "Origin of this memory" },
    metadata: { type: "object", description: "Free-form metadata" }
  },
  required: ["agent_id", "content", "type"]
};

const recallSchema = {
  type: "object",
  properties: {
    agent_id: { type: "string" },
    query: { type: "string", description: "Recall query" },
    k: { type: "integer", minimum: 1, maximum: 1000, default: 5 },
    types: {
      type: "array",
      items: { type: "string", enum: ["semantic", "episodic", "procedural", "emotional"] },
      description: "Filter by memory types"
    },
    use_entropy_ranking: {
      type: "boolean",
      default: true,
      description: "Use entropy-weighted retrieval (amg unique feature)"
    }
  },
  required: ["agent_id", "query"]
};

const classifySchema = {
  type: "object",
  properties: {
    agent_id: { type: "string" },
    method: {
      type: "string",
      enum: ["graph", "spectral", "hybrid", "rrf", "bayesian", "fingerprint"],
      default: "hybrid",
      description: "Classification method"
    }
  },
  required: ["agent_id"]
};

const provenanceSchema = {
  type: "object",
  properties: {
    agent_id: { type: "string" },
    node_id: { type: "string", description: "Node to trace provenance for" },
    direction: {
      type: "string",
      enum: ["backward", "forward", "full"],
      default: "full",
      description: "backward=deriviation sources, forward=impact, full=both"
    }
  },
  required: ["agent_id", "node_id"]
};

// --- Server setup ---
const server = new McpServer({
  name: "agent-memory-graph",
  version: "0.1.0",
});

// Tool 1: remember — store a memory
server.tool("remember", "Store a memory in the graph", rememberSchema, async (params) => {
  // In production: const graph = getGraph(params.agent_id);
  // graph.add_node({ id: generateId(), content: params.content, type: params.type, ... });
  const id = `mem_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        status: "stored",
        memory_id: id,
        agent_id: params.agent_id,
        type: params.type,
        confidence: params.confidence ?? 1.0,
        timestamp: Date.now()
      })
    }]
  };
});

// Tool 2: recall — retrieve memories with entropy-weighted ranking
server.tool("recall", "Recall memories using entropy-weighted retrieval", recallSchema, async (params) => {
  // In production:
  // const graph = getGraph(params.agent_id);
  // const results = graph.entropy_weighted_retrieval(params.query, { k: params.k });
  const mockResults = [
    { id: "mem_001", content: "Sample match", score: 0.95, entropy_weight: 0.82 },
    { id: "mem_002", content: "Another match", score: 0.78, entropy_weight: 0.64 }
  ];
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        results: mockResults,
        count: mockResults.length,
        agent_id: params.agent_id,
        ranking_method: params.use_entropy_ranking ? "entropy_weighted" : "bm25"
      })
    }]
  };
});

// Tool 3: classify — graph topology classification
server.tool("classify", "Classify graph topology using entropy fingerprinting", classifySchema, async (params) => {
  // In production:
  // const graph = getGraph(params.agent_id);
  // const result = graph_classification(graph, { method: params.method });
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        method: params.method,
        best_match: "star",
        confidence: 0.89,
        margin: 0.34,
        rankings: [
          { family: "star", score: 0.12 },
          { family: "path", score: 0.46 },
          { family: "tree", score: 0.58 }
        ]
      })
    }]
  };
});

// Tool 4: trace_provenance — dependency lineage analysis
server.tool("trace_provenance", "Trace derivation lineage and cascading impact", provenanceSchema, async (params) => {
  // In production:
  // const graph = getGraph(params.agent_id);
  // const result = graph.derivation_lineage_report(params.node_id);
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        node_id: params.node_id,
        direction: params.direction,
        roots: ["source_001", "source_002"],
        bottleneck_score: 1.5,
        fan_in: 2,
        fan_out: 3,
        completeness: 0.85,
        summary: "2 source nodes → 3 dependent nodes. ⚠ Bottleneck score > 1: single point of failure."
      })
    }]
  };
});

// Tool 5: entropy_scan — multi-scale Rényi entropy sweep
server.tool("entropy_scan", "Multi-scale entropy analysis of graph topology", {
  type: "object",
  properties: {
    agent_id: { type: "string" },
    alpha_values: {
      type: "array",
      items: { type: "number" },
      default: [0.5, 1, 2, 3, 5, Infinity],
      description: "Rényi alpha values to sweep"
    }
  },
  required: ["agent_id"]
}, async (params) => {
  // In production:
  // const graph = getGraph(params.agent_id);
  // const result = entropy_scan(graph, { alpha: params.alpha_values });
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        alpha_sweep: [
          { alpha: 0.5, entropy: 2.71 },
          { alpha: 1.0, entropy: 2.31 },
          { alpha: 2.0, entropy: 1.85 },
          { alpha: 3.0, entropy: 1.42 },
          { alpha: 5.0, entropy: 0.91 },
          { alpha: "Infinity", entropy: 0.44 }
        ],
        shape: {
          monotonicity: "decreasing",
          range: 2.27,
          convergence_cv: 0.03,
          personality: "hierarchical"
        },
        fingerprint_distance_to_star: 0.12
      })
    }]
  };
});

// Tool annotations for governance (MCP 2026-07-28 spec)
// These hints help clients make routing decisions
server.tool("health", "Check memory server health", {}, async () => ({
  content: [{
    type: "text",
    text: JSON.stringify({
      status: "ok",
      version: "0.1.0",
      uptime: process.uptime(),
      graph_stats: { nodes: 0, edges: 0, entropy: 0 }
    })
  }]
}));

// --- Start server (stateless transport) ---
const transport = new StdioServerTransport();
await server.connect(transport);

console.error("[amg-mcp] Stateless MCP server ready (spec 2026-07-28)");
```

**Running it:**
```bash
# Install deps
npm install @modelcontextprotocol/sdk

# Run
npx tsx amg-mcp-server.ts

# Or configure in Claude Desktop / Cursor / OpenClaw:
# {
#   "mcpServers": {
#     "agent-memory-graph": {
#       "command": "node",
#       "args": ["amg-mcp-server.js"]
#     }
#   }
# }
```

### Example 2: OpenClaw Plugin Skeleton for amg

```typescript
// openclaw-plugin-amg/index.ts — OpenClaw plugin for agent-memory-graph
// Lifecycle hooks: SessionStart → inject context, PostToolUse → capture, SessionEnd → consolidate

import type { PluginContext, PluginHooks } from "openclaw";

// In production: import { MemoryGraph, entropy_weighted_retrieval } from "agent-memory-graph";

const AMG_PLUGIN_ID = "agent-memory-graph";

interface AMGConfig {
  graphPersistence: "file" | "memory";
  filePath?: string;
  maxContextInjection: number;  // max memories to inject per turn
  entropyRanking: boolean;
  autoConsolidate: boolean;
}

const defaultConfig: AMGConfig = {
  graphPersistence: "memory",
  maxContextInjection: 10,
  entropyRanking: true,
  autoConsolidate: true,
};

class AMGPlugin {
  private config: AMGConfig;
  private graphs: Map<string, any> = new Map(); // agent_id → MemoryGraph

  constructor(config: Partial<AMGConfig> = {}) {
    this.config = { ...defaultConfig, ...config };
  }

  // Lifecycle: SessionStart — load graph and inject relevant context
  async onSessionStart(ctx: PluginContext) {
    const agentId = ctx.agentId ?? "default";
    const graph = await this.loadGraph(agentId);
    this.graphs.set(agentId, graph);

    // Inject memory context using entropy-weighted retrieval
    const recentTopics = ctx.recentMessages?.slice(-5).map(m => m.content).join(" ") ?? "";
    if (recentTopics.length > 0) {
      const results = graph.entropy_weighted_retrieval
        ? graph.entropy_weighted_retrieval(recentTopics, { k: this.config.maxContextInjection })
        : [];

      if (results.length > 0) {
        const memoryBlock = results.map((r: any) =>
          `- [${r.type}] ${r.content} (confidence: ${r.confidence ?? '?'})`
        ).join("\n");
        ctx.injectSystemContext(`[Memory Graph — ${results.length} relevant memories]\n${memoryBlock}`);
      }
    }
  }

  // Lifecycle: PostToolUse — capture tool results as episodic memories
  async onPostToolUse(ctx: PluginContext, toolName: string, result: any) {
    const agentId = ctx.agentId ?? "default";
    const graph = this.graphs.get(agentId);
    if (!graph) return;

    // Auto-capture significant tool outputs as episodic memories
    if (toolName === "write" || toolName === "edit") {
      graph.add_node?.({
        id: `ep_${Date.now()}`,
        content: `Tool ${toolName} modified file`,
        type: "episodic",
        source: `tool:${toolName}`,
        confidence: 0.7,
        metadata: { timestamp: Date.now() }
      });
    }
  }

  // Lifecycle: SessionEnd — consolidate and persist
  async onSessionEnd(ctx: PluginContext) {
    const agentId = ctx.agentId ?? "default";
    const graph = this.graphs.get(agentId);
    if (!graph) return;

    // Run entropy-guided consolidation
    if (this.config.autoConsolidate && graph.consolidate) {
      const stats = graph.consolidate();
      console.log(`[amg-plugin] Consolidated: ${JSON.stringify(stats)}`);
    }

    // Persist
    if (this.config.graphPersistence === "file" && this.config.filePath) {
      await this.saveGraph(agentId, graph);
    }

    this.graphs.delete(agentId);
  }

  // Expose slash commands
  getSlashCommands() {
    return [
      {
        command: "/remember",
        description: "Store a fact in the memory graph",
        handler: async (ctx: PluginContext, args: string) => {
          const agentId = ctx.agentId ?? "default";
          const graph = this.graphs.get(agentId);
          if (!graph) return "Memory graph not initialized.";
          graph.add_node?.({
            id: `sem_${Date.now()}`,
            content: args,
            type: "semantic",
            confidence: 1.0,
            source: "user:slash-command"
          });
          return `✅ Stored: "${args}"`;
        }
      },
      {
        command: "/recall",
        description: "Search memories in the graph",
        handler: async (ctx: PluginContext, args: string) => {
          const agentId = ctx.agentId ?? "default";
          const graph = this.graphs.get(agentId);
          if (!graph) return "Memory graph not initialized.";
          const results = graph.entropy_weighted_retrieval
            ? graph.entropy_weighted_retrieval(args, { k: 5 })
            : [];
          if (results.length === 0) return "No matching memories found.";
          return results.map((r: any, i: number) =>
            `${i + 1}. [${r.type}] ${r.content}`
          ).join("\n");
        }
      },
      {
        command: "/entropy",
        description: "Show graph entropy statistics",
        handler: async (ctx: PluginContext) => {
          const agentId = ctx.agentId ?? "default";
          const graph = this.graphs.get(agentId);
          if (!graph) return "Memory graph not initialized.";
          // Use amg's entropy_profile if available
          if (graph.entropy_profile) {
            const profile = graph.entropy_profile();
            return JSON.stringify(profile, null, 2);
          }
          return "Entropy analysis not available.";
        }
      }
    ];
  }

  private async loadGraph(agentId: string): Promise<any> {
    // In production: use actual MemoryGraph from agent-memory-graph
    // const graph = new MemoryGraph();
    // if (this.config.graphPersistence === "file") {
    //   const data = await fs.readFile(this.getFilePath(agentId), "utf-8");
    //   graph.deserialize(data);
    // }
    // return graph;
    return {
      add_node: (node: any) => console.log(`[amg] add_node: ${node.id}`),
      entropy_weighted_retrieval: (q: string, opts: any) => [],
      consolidate: () => ({ merged: 0, forgotten: 0 }),
      entropy_profile: () => ({ shannon: 2.31, renyi: { "2": 1.85 }, von_neumann: 1.42 })
    };
  }

  private async saveGraph(agentId: string, graph: any): Promise<void> {
    // const data = graph.serialize();
    // await fs.writeFile(this.getFilePath(agentId), data);
  }

  private getFilePath(agentId: string): string {
    return `${this.config.filePath ?? "./.amg"}/${agentId}.json`;
  }
}

// --- Plugin export ---
export default function createPlugin(config?: Partial<AMGConfig>): { id: string; hooks: PluginHooks } {
  const instance = new AMGPlugin(config);
  return {
    id: AMG_PLUGIN_ID,
    hooks: {
      onSessionStart: (ctx) => instance.onSessionStart(ctx),
      onPostToolUse: (ctx, tool, result) => instance.onPostToolUse(ctx, tool, result),
      onSessionEnd: (ctx) => instance.onSessionEnd(ctx),
      slashCommands: instance.getSlashCommands(),
    }
  };
}
```

**Plugin manifest (`openclaw.plugin.json`):**
```json
{
  "name": "agent-memory-graph",
  "version": "0.1.0",
  "description": "Entropy-aware graph memory with provenance tracking, classification, and multi-scale analysis",
  "author": "Catalyst",
  "license": "MIT",
  "homepage": "https://github.com/robertsong2019/agent-memory-graph",
  "config": {
    "graphPersistence": { "type": "string", "default": "memory" },
    "maxContextInjection": { "type": "number", "default": 10 },
    "entropyRanking": { "type": "boolean", "default": true },
    "autoConsolidate": { "type": "boolean", "default": true }
  }
}
```

---

## Key Insights

### 1. Memory is becoming a protocol primitive, not just a tool endpoint

memorywire's central argument is correct: wrapping `remember`/`recall`/`forget` as three opaque MCP tools is lossy. The type taxonomy collapses into a string parameter, governance sits outside the protocol, and the lifecycle (write→consolidate→forget) is invisible to the transport. However, memorywire-as-MCP-tool is still the pragmatic path for adoption today — it's 10 lines of glue code and any MCP-compatible agent can use it. The strategic play is: ship the MCP tool wrapper now, align the interface with memorywire's schema for forward compatibility, and upgrade to a formal MCP extension when memorywire v0.5 stabilizes.

### 2. The MCP 2026-07-28 stateless core eliminates the biggest objection to MCP memory servers

Before 2026-07-28, MCP required session state, making horizontal scaling impossible without shared session stores. The new spec removes this entirely — every request is self-contained, carrying client info in `_meta`. For amg's MCP server, this means: deploy behind any load balancer, no Redis for session sharing, route by `Mcp-Method` header (heavy `tools/call` to beefier instances, lightweight `tools/list` to any). The `Tasks` primitive also enables async memory consolidation as a first-class MCP workflow — the server can spawn a consolidation task and report progress.

### 3. OpenClaw plugins: the distribution channel amg is absent from

At least 10 memory plugins exist for OpenClaw, including direct competitors (Cognee, PlugMem, graph-memory). amg has ZERO presence in this ecosystem despite having 925+ APIs and 6622 tests. Every day without an OpenClaw plugin, users choose a competitor. The plugin skeleton above (~150 lines) implements the three critical lifecycle hooks (SessionStart→inject, PostToolUse→capture, SessionEnd→consolidate) plus three slash commands (`/remember`, `/recall`, `/entropy`). The `/entropy` command is a unique differentiator — no competitor exposes graph entropy analysis to the user.

### 4. memorywire's RRF fusion validates amg's architecture choice

memorywire uses RRF (k=60) as the default fusion algorithm across multiple memory backends, proving RRF's robustness against adversarial injection (recall@5=1.000 under 1-of-NN attack). amg already uses RRF in its `rrf_classification()` (c326) and `hybrid_classification()` APIs. The memorywire paper independently validates this design choice. For the MCP server: if amg ever supports multiple memory backends (file + Redis + vector store), RRF fusion is the proven default.

### 5. The governance gap is amg's unpicked lock

memorywire's governance channel (diff-and-approve for sensitive writes) is a feature no OpenClaw plugin has. amg's `write_governance_check()` already exists but is not exposed through any user-facing interface. Adding an `approval_required` parameter to the MCP `remember` tool, plus a slash command `/pending` that shows staged writes, would give amg a governance capability that no competitor (Mem0, Cognee, PlugMem, graph-memory) offers. This maps directly to memorywire's Co-memorize pattern — amg can implement it today without waiting for memorywire v0.5.

---

## Action Items

### Immediate (Week of August 3)
1. **Implement amg MCP server** — Adapt the skeleton above with real MemoryGraph integration. 8 tools: `remember`, `recall`, `classify`, `trace_provenance`, `entropy_scan`, `health`, `forget`, `merge`. Target: ~300 lines TypeScript + ~100 lines tests. Register on MCP Registry.
2. **Implement amg OpenClaw plugin** — Adapt the skeleton above with lifecycle hooks. Target: ~200 lines TypeScript. Publish to ClawHub.
3. **Align tool schemas with memorywire v0** — Use the same field names (`agent_id`, `type`, `confidence`, `source`, `approval_required`) so the MCP wrapper is forward-compatible with memorywire v0.5.

### Short-term (August)
4. **Add governance slash commands** — `/pending` (list staged writes), `/approve <id>`, `/reject <id>`. Maps to memorywire Co-memorize pattern.
5. **Add `Tasks` support for async consolidation** — Use MCP 2026-07-28 Tasks primitive for background memory consolidation. Non-blocking; report progress.
6. **Write `docs/MEMORYWIRE-COMPATIBILITY.md`** — Document which memorywire v0 operations and fields amg supports, which are partial, and the roadmap to full compatibility.

### Medium-term (September)
7. **Implement memorywire-compatible adapter** — A thin adapter that makes amg's MemoryGraph implement memorywire's `MemoryStore` Protocol. Enables drop-in compatibility with any memorywire-compatible client.
8. **Track memorywire v0.2 spec changes** — Particularly: `privacy_intent` block, `signed RecallHit` envelopes, stable per-record id requirement, expire empty-policy guard.
9. **Position amg README** — Lead with "The only agent memory library with entropy-aware retrieval, graph classification, and provenance tracking. Available as npm library, MCP server, and OpenClaw plugin."

---

## References

- **memorywire paper**: [arXiv:2606.01138v2](https://arxiv.org/html/2606.01138v2) — Vendor-neutral wire format, 5 ops × 4 types, RRF fusion, governance channel
- **MCP 2026-07-28 spec**: [modelcontextprotocol.io/specification/2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28) — Stateless core, MRTR, header routing
- **MCP blog post**: [blog.modelcontextprotocol.io/posts/2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28) — Release candidate overview
- **Cognee OpenClaw plugin**: [cognee.ai/blog/integrations](https://www.cognee.ai/blog/integrations/what-is-openclaw-ai-and-how-we-give-it-memory-with-cognee) — Plugin architecture guide
- **PlugMem**: [github.com/TIMAN-group/PlugMem](https://github.com/TIMAN-group/PlugMem) — OpenClaw plugin shipping now
- **graph-memory plugin**: [skillsllm.com/skill/graph-memory](https://skillsllm.com/skill/graph-memory) — 75% context compression
- **OpenClaw memory comparison**: [maximem.ai/openclaw/memory-comparison](https://www.maximem.ai/openclaw/memory-comparison) — 10-plugin landscape
- **AI Memory Solutions Q3 2026**: [mnemoverse.com/docs/library/ai-memory-solutions-2026-q3](https://mnemoverse.com/docs/library/ai-memory-solutions-2026-q3) — Competitive landscape
- **MCP security analysis**: [orca.security](https://orca.security/resources/blog/bringing-memory-to-ai-mcp-a2a-agent-context-protocols) — Attack surfaces
- **PLUR Engram Spec**: [plur.ai/blog/open-standard-ai-agent-memory](https://plur.ai/blog/open-standard-ai-agent-memory) — Data layer standard

---

## Quality Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 3 concepts | memorywire protocol, MCP 2026-07-28, OpenClaw plugin landscape |
| Runnable code (≥1) | ✅ 2 examples | MCP server (TypeScript, stateless), OpenClaw plugin skeleton |
| Key insights (≥3) | ✅ 5 insights | Protocol primitive, stateless enabler, distribution gap, RRF validation, governance gap |
| Action items (≥1) | ✅ 9 items | 3 immediate, 3 short-term, 3 medium-term |
| Relation to existing work | ✅ | Maps to Research #021 (MCP server), #026 (npm strategy), #037 (benchmark harness), #041 (provenance) |
| Unique perspective | ✅ | Protocol triangle analysis, governance as unpicked lock, entropy as plugin differentiator |
