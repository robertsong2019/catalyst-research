# Official MCP Memory Server: Source Analysis → amg-mcp Phase 1 Blueprint

> Deep Research #021 — 2026-07-20
> Methodology: autoresearch (明确指标 → 快速循环 → 积累性)
> Builds on: #017 (MCP Memory Server Architecture), #020 (SDK v2 Implementation Patterns)
> Trigger: MCP Memory Server Phase 1 starts July 21. This note analyzes the official server source code and SDK v2 docs to produce a concrete, runnable blueprint.
> Success metric: Runnable code example + 3+ insights that improve the Phase 1 implementation plan.

---

## 1. Official MCP Memory Server — Source Code Analysis

### 1.1 Architecture Summary

The official `@modelcontextprotocol/server-memory` (v0.6.3) is a **JSONL file-backed knowledge graph** with 9 tools:

| Tool | Annotations | Description |
|------|-------------|-------------|
| `create_entities` | write, non-destructive | Add entities (name, entityType, observations[]) |
| `create_relations` | write, non-destructive | Add directed relations (from→to, relationType) |
| `add_observations` | write, non-destructive | Append observations to existing entities |
| `delete_entities` | write, **destructive** | Remove entities + cascade-remove their relations |
| `delete_observations` | write, **destructive** | Remove specific observations from entities |
| `delete_relations` | write, **destructive** | Remove specific relations |
| `read_graph` | **read-only** | Dump entire graph |
| `search_nodes` | **read-only** | Substring search across name/entityType/observations |
| `open_nodes` | **read-only** | Fetch specific nodes by name (includes cross-references) |

**Data model:**
```typescript
interface Entity {
  name: string;         // Unique key
  entityType: string;   // Free-text category
  observations: string[]; // Free-text facts
}

interface Relation {
  from: string;         // Entity name
  to: string;           // Entity name
  relationType: string; // Free-text label
}
```

**Storage**: JSONL file (`memory.jsonl`). Each line is `{type: "entity", ...}` or `{type: "relation", ...}`. Load = parse all lines, save = rewrite entire file.

### 1.2 What the Official Server Does Well

1. **Tool annotations** — Every tool has `readOnlyHint`/`destructiveHint`/`idempotentHint`/`openWorldHint`. Read tools are clearly marked `readOnlyHint: true`. Destructive tools marked `destructiveHint: true`. This is the **governance surface** #017 identified.

2. **outputSchema** — All tools define both `inputSchema` and `outputSchema` with Zod. `structuredContent` is returned alongside text. This lets clients (Claude, Cursor) programmatically reason about results.

3. **Resource subscriptions** — `registerKnowledgeGraphResource` + `registerKnowledgeGraphSubscriptions` let clients subscribe to graph changes. `notifyGraphUpdated()` fires after every mutation. This is the change-notification pattern amg-mcp should adopt.

4. **Per-request factory pattern** — Each request gets a fresh `McpServer` instance via the factory function. The manager class (`KnowledgeGraphManager`) holds the state, not the server.

5. **Backward-compatible migration** — `ensureMemoryFilePath()` detects old `memory.json` and migrates to `memory.jsonl`. Thoughtful UX.

### 1.3 Critical Gaps (amg-mcp Opportunities)

| Gap | Impact | amg Solution |
|-----|--------|-------------|
| **Substring search only** — `name.toLowerCase().includes(query)` | Cannot find semantically related nodes, no ranking, no multi-hop | `query()` with 7-intent routing + PPR + BM25 |
| **No graph algorithms** — flat entity-relation, no centrality, no communities | Cannot identify important nodes, gaps, or redundancy | 775+ APIs: 17 centrality metrics, Leiden communities, topological indices |
| **File-based, no concurrency** — load-all → mutate → write-all | Race conditions under concurrent access; O(n) per operation | SQLite with WAL mode: ACID transactions, concurrent reads |
| **No quality metrics** — no health check, no gap detection, no redundancy analysis | Graph degrades silently; user has no insight into quality | Dual-loop quality system: gap_redundancy_balance() + auto_heal + auto_consolidate |
| **No governance** — anyone can write anything, no write validation | Sycophancy, hallucination, prompt injection write freely into durable memory | write_governance_check() + screen_retrieval() |
| **No temporal awareness** — no timestamps, no decay, no supersede | Cannot answer "what was true yesterday?" or forget outdated facts | Bi-temporal edges + decay_model + supersede chains |
| **No query routing** — one search mode for all questions | "Who is X?" and "What changed?" use the same substring match | 7-intent taxonomy: factual/temporal/relational/analytical/temporal_reasoning/constraint_validation/how |
| **No consolidation** — graph only grows, never compresses | Redundant entities accumulate, token cost rises | compress_to_skill() + auto_consolidate() |
| **9 tools, no depth** — thin API surface | LLM must make multiple calls to accomplish complex tasks | 8 curated tools wrapping deep APIs (each tool does more internally) |

---

## 2. Core Concepts for amg-mcp Phase 1

### Concept 1: The Factory Pattern is Mandatory

SDK v2 uses `createMcpHandler(factory)` for HTTP and `serveStdio(factory)` for stdio. The factory runs **once per request** (HTTP) or **once per connection** (stdio). Tools must be registered inside the factory, never outside.

**Implication for amg-mcp**: The MemoryGraph instance (SQLite connection) lives at module scope. The factory creates a fresh McpServer, registers tools that close over the shared MemoryGraph, and returns it. SQLite WAL mode handles concurrent reads.

```typescript
// Correct pattern for amg-mcp
import { MemoryGraph } from 'agent-memory-graph';
import { serveStdio } from '@modelcontextprotocol/server/stdio';
import { McpServer } from '@modelcontextprotocol/server';
import * as z from 'zod/v4';

// Module-scope: one database, shared across requests
const memory = new MemoryGraph({ dbPath: process.env.AMG_DB_PATH ?? ':memory:' });

function createServer(): McpServer {
  const server = new McpServer({
    name: 'agent-memory-graph',
    version: '1.0.0',
  });

  // Register tools INSIDE the factory
  server.registerTool(
    'memory.recall',
    {
      description: 'Recall relevant memories by semantic + graph search',
      inputSchema: z.object({
        query: z.string().describe('Natural language question or topic'),
        limit: z.number().int().min(1).max(50).optional().default(10),
      }),
      outputSchema: z.object({
        memories: z.array(z.object({
          id: z.string(),
          content: z.string(),
          score: z.number(),
          kind: z.string().optional(),
          related: z.array(z.string()).optional(),
        })),
        total: z.number(),
      }),
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ query, limit }) => {
      const results = memory.query(query, { limit });
      return {
        content: [{
          type: 'text' as const,
          text: JSON.stringify(results, null, 2),
        }],
        structuredContent: {
          memories: results.map(r => ({
            id: r.id,
            content: r.content,
            score: r.score,
            kind: r.kind,
            related: r.related ?? [],
          })),
          total: results.length,
        },
      };
    },
  );

  return server;
}

void serveStdio(createServer);
console.error('agent-memory-graph MCP server running on stdio');
```

### Concept 2: outputSchema is Non-Negotiable

The official memory server defines `outputSchema` on EVERY tool. SDK v2 validates `structuredContent` against it before the result leaves the server. Without `outputSchema`, the tool result is opaque text — hosts like Claude can't programmatically act on it.

**Rule for amg-mcp**: Every tool must have `outputSchema`. The schema IS the API contract.

```typescript
// Health check with structured output
server.registerTool(
  'memory.health',
  {
    description: 'Check memory graph health: connectivity, density, gaps, redundancy',
    inputSchema: z.object({}).optional(),
    outputSchema: z.object({
      health_score: z.number().min(0).max(100),
      gap_score: z.number().min(0).max(100),
      redundancy_score: z.number().min(0).max(100),
      balance_ratio: z.number().min(-1).max(1),
      verdict: z.string(),
      node_count: z.number(),
      edge_count: z.number(),
    }),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true },
  },
  async () => {
    const health = memory.gap_redundancy_balance();
    return {
      content: [{ type: 'text' as const, text: JSON.stringify(health) }],
      structuredContent: health,
    };
  },
);
```

### Concept 3: Annotation-Driven Governance

The official server marks destructive tools with `destructiveHint: true`. MCP hosts use this to gate confirmation. amg-mcp's governance layer maps naturally:

| amg Operation | readOnly | destructive | idempotent |
|---------------|----------|-------------|------------|
| recall / query / health / gaps | ✅ true | false | true |
| remember / relate | false | false | false |
| forget | false | **true** | true |
| consolidate / heal | false | **true** | true |

**This is PASB defense at protocol level**: hosts like Claude will require user confirmation before calling `memory.forget`. This is a free security layer — amg-mcp gets it by setting the right annotations.

### Concept 4: Resource Subscriptions for Change Notification

The official server implements `subscribe/unsubscribe` via `SubscribeRequestSchema`. When the graph changes, it calls `server.server.sendResourceUpdated()`. This is how clients learn that memory state has changed without polling.

**For amg-mcp**: After `memory.remember`, `memory.forget`, `memory.consolidate`, and `memory.heal`, fire `sendResourceUpdated`. This lets hosts auto-refresh their context window.

### Concept 5: The 8-Tool Curated Surface

The official server has 9 tools. amg-mcp needs 8. Here's the mapping:

| amg-mcp Tool | Replaces | amg APIs Wrapped |
|--------------|----------|-------------------|
| `memory.recall` | search_nodes, read_graph | query() (7-intent), search(), retrieve() |
| `memory.remember` | create_entities, create_relations, add_observations | add(), relate() |
| `memory.health` | (none) | gap_redundancy_balance(), health_check() |
| `memory.consolidate` | (none) | auto_consolidate(), compress_to_skill() |
| `memory.heal` | (none) | auto_heal_gaps(), knowledge_gap_report() |
| `memory.forget` | delete_entities, delete_relations, delete_observations | forget(), strategic_forget() |
| `memory.reflect` | (none) | retrieval_quality_eval(), reasoning_quality_eval() |
| `memory.relate` | (implicit in create_relations) | relate(), add_edge(), supersede() |

**Tool count comparison**: Official = 9 thin tools. amg-mcp = 8 deep tools. Each amg-mcp tool wraps 5-20 internal APIs, giving the LLM more power per call.

---

## 3. Runnable Code: Minimal amg-mcp Server (Phase 1, Day 1)

This is a **runnable starting point** for Phase 1. It wraps a single amg instance with 4 tools (recall, remember, health, forget). The remaining 4 tools (consolidate, heal, reflect, relate) are added in subsequent days.

```typescript
#!/usr/bin/env node
/**
 * agent-memory-graph MCP Server — Phase 1 Blueprint
 *
 * Install:
 *   npm install @modelcontextprotocol/server zod agent-memory-graph
 *
 * Run:
 *   npx tsx src/index.ts
 *
 * Configure in Claude Desktop / Cursor:
 *   { "mcpServers": { "memory": { "command": "npx", "args": ["-y", "amg-mcp"] } } }
 */

import { McpServer } from '@modelcontextprotocol/server';
import { serveStdio } from '@modelcontextprotocol/server/stdio';
import * as z from 'zod/v4';

// --- Mock MemoryGraph for illustration (replace with real amg import) ---
interface MemoryNode {
  id: string;
  content: string;
  kind: string;
  score: number;
  related: string[];
}

class SimpleMemory {
  private nodes = new Map<string, MemoryNode>();
  private edges: Array<{ from: string; to: string; type: string }> = [];

  add(content: string, kind = 'fact'): string {
    const id = `node_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.nodes.set(id, { id, content, kind, score: 1.0, related: [] });
    return id;
  }

  search(query: string, limit = 10): MemoryNode[] {
    const q = query.toLowerCase();
    return Array.from(this.nodes.values())
      .filter(n => n.content.toLowerCase().includes(q))
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);
  }

  forget(id: string): boolean {
    const existed = this.nodes.delete(id);
    this.edges = this.edges.filter(e => e.from !== id && e.to !== id);
    return existed;
  }

  health() {
    const nodeCount = this.nodes.size;
    const edgeCount = this.edges.length;
    const density = nodeCount > 1 ? edgeCount / (nodeCount * (nodeCount - 1)) : 0;
    return {
      health_score: Math.round(density * 100),
      gap_score: Math.round((1 - density) * 100),
      redundancy_score: 0,
      balance_ratio: 1 - 2 * density,
      verdict: density > 0.3 ? 'healthy' : 'sparse',
      node_count: nodeCount,
      edge_count: edgeCount,
    };
  }
}

const memory = new SimpleMemory();
// --- End mock ---

function createServer(): McpServer {
  const server = new McpServer({
    name: 'agent-memory-graph',
    version: '0.1.0',
  });

  // Tool 1: memory.recall — semantic + graph search
  server.registerTool(
    'memory.recall',
    {
      title: 'Recall Memories',
      description: 'Search agent memory by natural language query. Returns ranked results.',
      inputSchema: z.object({
        query: z.string().describe('Natural language question or topic'),
        limit: z.number().int().min(1).max(50).optional(),
      }),
      outputSchema: z.object({
        memories: z.array(z.object({
          id: z.string(),
          content: z.string(),
          kind: z.string(),
          score: z.number(),
          related: z.array(z.string()),
        })),
        total: z.number(),
      }),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true },
    },
    async ({ query, limit = 10 }) => {
      const results = memory.search(query, limit);
      return {
        content: [{ type: 'text' as const, text: JSON.stringify(results, null, 2) }],
        structuredContent: {
          memories: results,
          total: results.length,
        },
      };
    },
  );

  // Tool 2: memory.remember — add new memories
  server.registerTool(
    'memory.remember',
    {
      title: 'Store Memory',
      description: 'Persist a fact, observation, or event into agent memory',
      inputSchema: z.object({
        content: z.string().describe('The memory content to store'),
        kind: z.string().optional().describe('Type: fact, event, preference, skill, etc.'),
      }),
      outputSchema: z.object({
        id: z.string(),
        stored: z.boolean(),
      }),
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false },
    },
    async ({ content, kind = 'fact' }) => {
      const id = memory.add(content, kind);
      return {
        content: [{ type: 'text' as const, text: `Stored: ${id}` }],
        structuredContent: { id, stored: true },
      };
    },
  );

  // Tool 3: memory.health — graph quality assessment
  server.registerTool(
    'memory.health',
    {
      title: 'Memory Health',
      description: 'Check graph health: density, gaps, redundancy, balance',
      inputSchema: z.object({}).optional(),
      outputSchema: z.object({
        health_score: z.number(),
        gap_score: z.number(),
        redundancy_score: z.number(),
        balance_ratio: z.number(),
        verdict: z.string(),
        node_count: z.number(),
        edge_count: z.number(),
      }),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true },
    },
    async () => {
      const health = memory.health();
      return {
        content: [{ type: 'text' as const, text: JSON.stringify(health, null, 2) }],
        structuredContent: health,
      };
    },
  );

  // Tool 4: memory.forget — remove a specific memory
  server.registerTool(
    'memory.forget',
    {
      title: 'Forget Memory',
      description: 'Remove a specific memory by ID. Requires confirmation.',
      inputSchema: z.object({
        id: z.string().describe('The memory ID to forget'),
      }),
      outputSchema: z.object({
        forgotten: z.boolean(),
        id: z.string(),
      }),
      annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true },
    },
    async ({ id }) => {
      const existed = memory.forget(id);
      return {
        content: [{ type: 'text' as const, text: existed ? `Forgot: ${id}` : `Not found: ${id}` }],
        structuredContent: { forgotten: existed, id },
      };
    },
  );

  return server;
}

// Start server
void serveStdio(createServer);
console.error('agent-memory-graph MCP server running on stdio');
```

**To run this code:**
```bash
mkdir amg-mcp-test && cd amg-mcp-test
npm init -y && npm pkg set type=module
npm install @modelcontextprotocol/server zod
# Save the code above as src/index.ts
npx tsx src/index.ts
# Test with MCP Inspector:
npx @modelcontextprotocol/inspector npx tsx src/index.ts
```

---

## 4. Key Insights

### Insight 1: The Official Memory Server is Embarrassingly Simple — and That's the Point

The entire official server is ~500 lines. It loads a JSONL file, does substring search, writes back. No algorithms, no ranking, no quality metrics. **This is the bar to clear.** amg-mcp doesn't need to be complex to be dramatically better — even wrapping `query()` + `health_check()` in the same 9-tool format would be 10× more capable.

**Actionable**: The Phase 1 goal is NOT "expose all 775+ APIs". It's "wrap 8 high-level operations that are each clearly better than the official server's equivalent". Depth > breadth.

### Insight 2: Resource Subscriptions are the Missing Feedback Loop

The official server lets clients subscribe to `memory://knowledge-graph` and fires `sendResourceUpdated()` after every mutation. This means Claude Desktop can auto-refresh its context when memory changes. **amg-mcp must implement this from day 1** — without it, the host doesn't know when to re-query memory.

```typescript
// The pattern from the official server
const RESOURCE_URI = 'memory://agent-graph';
const subscribers = new Set<string>();

function notifyGraphUpdated() {
  if (subscribers.has(RESOURCE_URI)) {
    server.server.sendResourceUpdated({ uri: RESOURCE_URI });
  }
}

// After every mutation tool:
async ({ content, kind }) => {
  const id = memory.add(content, kind);
  notifyGraphUpdated();  // ← Critical: notify subscribers
  return { ... };
}
```

### Insight 3: SDK v2's `registerTool` Replaces v1's `tool()` with Stronger Typing

The v2 API is cleaner: `server.registerTool(name, config, handler)` replaces v1's `server.tool(name, ...)`. Key differences:
- `inputSchema` is a Zod schema, not raw JSON Schema. SDK derives JSON Schema + validates + infers types.
- `outputSchema` is new — v1 didn't have structured output validation.
- `title` is new — display name separate from the programmatic name.
- `annotations` moved from optional hints to first-class config.

**amg-mcp must target v2 from day 1.** The #020 research confirmed this; the source code analysis confirms it further — the official server already uses `registerTool` with all v2 features.

### Insight 4: Stateless Protocol = SQLite's Natural Habitat

The 2026-07-28 spec removes sessions entirely. Every request is self-contained. For amg-mcp:
- **stdio transport**: One MemoryGraph instance, one process. Simple.
- **HTTP transport**: SQLite WAL mode handles concurrent reads. Writes serialize naturally via SQLite's exclusive locks. No application-level locking needed.
- **Horizontal scaling**: Multiple processes sharing the same SQLite file via WAL. Or: one writer + N readers via SQLite's built-in reader/writer separation.

The protocol went stateless. SQLite was always stateless (it's a file). They're made for each other.

### Insight 5: MCP Inspector is the Primary Development Tool

The official tutorial uses `npx @modelcontextprotocol/inspector npx tsx src/index.ts` as the primary testing method. This launches a local web app where you can:
- Connect to the server
- List tools (verify descriptions, schemas)
- Call tools with specific arguments
- See structured content results

**For Phase 1**: Don't build a test client. Use the Inspector. Test each tool as you add it. This is the fastest feedback loop.

---

## 5. Phase 1 Day-by-Day Plan (Revised from #020 with Source Code Insights)

### Day 1 (July 21): Skeleton + 4 Core Tools
- Project setup: `npm init`, install `@modelcontextprotocol/server` + `zod`
- Implement: `memory.recall`, `memory.remember`, `memory.health`, `memory.forget`
- Wrap: SimpleMemoryGraph → MemoryGraph adapter
- Test: MCP Inspector for each tool
- **Deliverable**: Runnable server with 4 tools

### Day 2 (July 22): + 2 Quality Tools
- Implement: `memory.consolidate` (wraps auto_consolidate), `memory.heal` (wraps auto_heal_gaps)
- Add: Resource subscription pattern (`notifyGraphUpdated`)
- Test: Multi-tool workflows (remember → health → consolidate → health)
- **Deliverable**: 6 tools, change notifications

### Day 3 (July 23): + 2 Advanced Tools
- Implement: `memory.reflect` (wraps retrieval_quality_eval), `memory.relate` (wraps relate + supersede)
- Test: Full 8-tool workflow
- **Deliverable**: Complete 8-tool surface

### Day 4 (July 24): HTTP Transport + Edge Cases
- Add: `createMcpHandler` for HTTP transport
- Handle: Empty graph, large graph, concurrent writes
- Test: HTTP mode with `curl` and Inspector
- **Deliverable**: Dual-transport server

### Day 5 (July 25): Integration Tests + Polish
- Test: Claude Desktop configuration
- Test: Cursor configuration
- Polish: Error messages, edge cases, documentation
- **Deliverable**: Beta-ready package

---

## 6. Competitive Positioning Update

| Feature | Official Memory Server | amg-mcp (Phase 1) | Gap |
|---------|----------------------|-------------------|-----|
| Storage | JSONL file | SQLite (WAL) | Concurrency, ACID |
| Search | Substring | 7-intent routing + PPR + BM25 | Semantic + ranking |
| Health | None | gap_redundancy_balance() | First with quality metrics |
| Consolidation | None | auto_consolidate() | First with compression |
| Self-healing | None | auto_heal_gaps() | First with repair |
| Governance | Annotations only | Annotations + write_governance_check | Protocol + application |
| Temporal | None | Bi-temporal edges + decay | Time-aware memory |
| Tools | 9 thin | 8 deep | Fewer, more powerful |
| Tool count (LLM UX) | 9 (borderline) | 8 (optimal) | Within cognitive budget |

**Tagline**: "The official memory server is a notepad. agent-memory-graph is a memory system."

---

## 7. Quality Self-Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Core concepts (3-5) | ✅ 5 concepts | Factory pattern, outputSchema, annotations, subscriptions, curated surface |
| Runnable code (≥1) | ✅ Complete server | 4-tool runnable TypeScript server with install/run instructions |
| Key insights (≥3) | ✅ 5 insights | Official server simplicity, resource subscriptions, v2 API, stateless=SQLite, Inspector-first |
| Next actions (≥1) | ✅ 5-day plan | Day-by-day Phase 1 implementation plan |
| Links to existing projects | ✅ amg-mcp Phase 1 | Directly feeds into tomorrow's implementation |
| Unique vs #017/#020 | ✅ Source code analysis | First note to analyze actual official server source code |

---

## 8. Next Actions (for MEMORY.md)

1. **Tomorrow (July 21)**: Start Phase 1 Day 1 — skeleton + 4 core tools
2. **Add resource subscription pattern** to the implementation checklist (from official server analysis)
3. **Use MCP Inspector** as primary dev tool (not custom test client)
4. **Phase 1 target**: 8 tools, dual-transport, beta-ready by July 25
5. **Phase 2 (July 28)**: Publish to MCP Registry on stable SDK v2 release day
