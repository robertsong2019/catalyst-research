/**
 * otel_genai_align.ts — OTel GenAI semantic-convention alignment adapter
 * for lab/agent-observability (agent.run / llm.call / tool.execute / retrieval.search / memory.*)
 *
 * Pinned against open-telemetry/semantic-conventions-genai main @ c739977 (2026-07-30).
 * All gen_ai.* conventions are Status: Development — treat as moving target.
 *
 * Strategy: export-boundary adapter (zero changes to Tracer internals).
 * Internal span names stay; mapping happens at export time, so a future
 * convention rename is a one-file edit (Praesidia's mapping-layer advice).
 *
 * Key mappings:
 *   agent.run       -> invoke_agent {name}   INTERNAL (v1.41 CLIENT/INTERNAL split)
 *   llm.call        -> chat {model}          CLIENT   (+details event, opt-in)
 *   tool.execute    -> execute_tool {name}   INTERNAL (v1.41: name required in span name)
 *   retrieval.search-> retrieval             CLIENT
 *   memory.write    -> upsert_memory         INTERNAL (in-process store: MAY be INTERNAL)
 *   memory.read     -> search_memory         INTERNAL
 * Content (prompt/completion/tool args/memory query+records) is Opt-In per spec:
 * gated by OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT or explicit flag.
 */

export interface AdapterSpan {
  traceId: string;
  spanId: string;
  parentSpanId: string | null;
  operation: string;
  startTime: number;   // performance.now() ms
  endTime: number | null;
  attributes: Record<string, unknown>;
  status: 'ok' | 'error' | 'unset';
  events?: Array<{ name: string; timestamp: number; attributes?: Record<string, unknown> }>;
}

export interface AlignOptions {
  /** Opt-in content capture (spec: off by default; env var mirrors OTel SDKs) */
  captureContent?: boolean;
  /** Cross-turn correlation; defaults to traceId */
  conversationId?: string;
}

const CONTENT_ENV = 'OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT';

function contentAllowed(opts: AlignOptions): boolean {
  return opts.captureContent === true || /^(1|true|yes)$/i.test(process.env[CONTENT_ENV] ?? '');
}

type Attrs = Record<string, unknown>;

interface MappedSpan {
  name: string;
  kind: string;
  operationName: string;
  attributes: Attrs;
  events: Array<{ name: string; timestamp: number; attributes: Attrs }>;
}

/** Map one internal span to GenAI-convention shape (name/kind/attrs/events). */
export function mapSpan(s: AdapterSpan, opts: AlignOptions = {}): MappedSpan {
  const a = s.attributes;
  const conv: Attrs = { 'gen_ai.conversation.id': opts.conversationId ?? s.traceId };
  const events: MappedSpan['events'] = [];
  const capture = contentAllowed(opts);
  let name = s.operation, kind = 'SPAN_KIND_INTERNAL', op = '';

  switch (s.operation) {
    case 'agent.run': {
      op = 'invoke_agent';
      name = `invoke_agent ${a.agentId ?? 'agent'}`;
      kind = 'SPAN_KIND_INTERNAL'; // local framework execution (v1.41 split)
      conv['gen_ai.agent.name'] = a.agentId ?? 'agent';
      if (a.task !== undefined) conv['ao.task'] = a.task; // custom namespace, not gen_ai.*
      break;
    }
    case 'llm.call': {
      op = 'chat';
      const model = String(a['gen_ai.request.model'] ?? a.model ?? 'unknown');
      name = `chat ${model}`;
      kind = 'SPAN_KIND_CLIENT';
      conv['gen_ai.request.model'] = model;
      conv['gen_ai.usage.input_tokens'] = a.promptTokens ?? 0;
      conv['gen_ai.usage.output_tokens'] = a.completionTokens ?? 0;
      // Spec: prompt/completion are Opt-In, aggregated + structured (v1.37 revamp),
      // carried on a dedicated event — never as bare gen_ai.prompt/gen_ai.completion attrs.
      if (capture) {
        events.push({
          name: 'gen_ai.client.inference.operation.details',
          timestamp: s.startTime,
          attributes: {
            'gen_ai.input.messages': [{ role: 'user', parts: [{ type: 'text', content: a['gen_ai.prompt'] ?? '' }] }],
            'gen_ai.output.messages': [{ role: 'assistant', parts: [{ type: 'text', content: a['gen_ai.completion'] ?? '' }], finish_reason: 'stop' }],
          },
        });
      }
      break;
    }
    case 'tool.execute': {
      op = 'execute_tool';
      const tool = String(a['tool.name'] ?? a.tool ?? 'unknown');
      name = `execute_tool ${tool}`; // v1.41: tool name REQUIRED in span name
      kind = 'SPAN_KIND_INTERNAL';
      conv['gen_ai.tool.name'] = tool;
      if (s.status === 'error') conv['error.type'] = 'policy_denied'; // low-cardinality
      if (capture && a['tool.input'] !== undefined) {
        conv['gen_ai.tool.call.arguments'] = JSON.stringify({ input: a['tool.input'] });
      }
      break;
    }
    case 'retrieval.search': {
      op = 'retrieval';
      name = 'retrieval';
      kind = 'SPAN_KIND_CLIENT';
      if (a.method !== undefined) conv['ao.retrieval.method'] = a.method; // custom ns
      if (a.top_k !== undefined) conv['gen_ai.retrieval.top_k'] = a.top_k;
      if (a.query !== undefined && capture) conv['gen_ai.retrieval.query.text'] = a.query; // Opt-In
      break;
    }
    case 'memory.write': {
      // upsert_memory: "create, update, or consolidate ... without the caller choosing which"
      op = 'upsert_memory';
      name = 'upsert_memory';
      kind = 'SPAN_KIND_INTERNAL'; // in-process memory system: spec allows INTERNAL
      if (a.namespace !== undefined) conv['gen_ai.memory.store.id'] = a.namespace;
      if (a.items !== undefined) conv['gen_ai.memory.record.count'] = a.items;
      break;
    }
    case 'memory.read': {
      op = 'search_memory';
      name = 'search_memory';
      kind = 'SPAN_KIND_INTERNAL';
      if (a.namespace !== undefined) conv['gen_ai.memory.store.id'] = a.namespace;
      if (a.results !== undefined || a.items !== undefined) {
        conv['gen_ai.memory.record.count'] = a.results ?? a.items;
      }
      if (a.query !== undefined && capture) conv['gen_ai.memory.query.text'] = a.query; // Opt-In
      break;
    }
    default:
      op = String(s.operation);
      Object.assign(conv, a);
  }
  conv['gen_ai.operation.name'] = op;
  return { name, kind, operationName: op, attributes: conv, events };
}

/** Attach gen_ai.evaluation.result events (spec v1.38) to the root span. */
export function evaluationEventAttributes(dimension: string, score: number, reason: string): Attrs {
  return {
    'gen_ai.evaluation.name': dimension,
    'gen_ai.evaluation.score.value': score,
    'gen_ai.evaluation.score.label': score >= 0.8 ? 'pass' : 'warn', // low cardinality
    'gen_ai.evaluation.explanation': reason,
  };
}

const hex = (s: string, n: number) => s.replace(/-/g, '').padEnd(n, '0').slice(0, n);

/** Full trace -> OTLP-JSON shape (resourceSpans). Times anchored to wall clock. */
export function exportGenAiOtlp(spans: AdapterSpan[], opts: AlignOptions = {}, epochAnchorMs = Date.now() - performance.now()) {
  const convSpans = spans.map(s => {
    const m = mapSpan(s, opts);
    const startNs = String(Math.round((epochAnchorMs + s.startTime) * 1e6));
    const endNs = s.endTime !== null ? String(Math.round((epochAnchorMs + s.endTime) * 1e6)) : startNs;
    const attrs = Object.entries(m.attributes).map(([k, v]) => ({
      key: k,
      value: typeof v === 'number' ? { intValue: v } : { stringValue: String(v) },
    }));
    return {
      traceId: hex(spans[0].traceId, 32),
      spanId: hex(s.spanId, 16),
      parentSpanId: s.parentSpanId ? hex(s.parentSpanId, 16) : undefined,
      name: m.name,
      kind: m.kind,
      startTimeUnixNano: startNs,
      endTimeUnixNano: endNs,
      status: { code: s.status === 'error' ? 'STATUS_CODE_ERROR' : 'STATUS_CODE_OK' },
      attributes: attrs,
      events: m.events.map(e => ({
        name: e.name,
        timeUnixNano: String(Math.round((epochAnchorMs + e.timestamp) * 1e6)),
        attributes: Object.entries(e.attributes).map(([k, v]) => ({
          key: k,
          value: typeof v === 'object' && v !== null
            ? { kvlistValue: { values: [] } , __raw: v }
            : { stringValue: String(v) },
        })),
      })),
    };
  });
  return { resourceSpans: [{ scopeSpans: [{ spans: convSpans }] }] };
}

export interface LintResult { ok: boolean; violations: string[] }

/** Compliance lint against the pinned spec commit. Cheap CI gate. */
export function lintGenAiSpans(spans: AdapterSpan[], opts: AlignOptions = {}): LintResult {
  const v: string[] = [];
  const capture = contentAllowed(opts);
  for (const s of spans) {
    const m = mapSpan(s, opts);
    const n = m.name;
    const fail = (msg: string) => v.push(`${s.operation}(${s.spanId.slice(0, 8)}): ${msg}`);
    // 1. operation.name is Required on every GenAI span
    if (!m.attributes['gen_ai.operation.name']) fail('missing gen_ai.operation.name');
    // 2. span-name formats (v1.41: execute_tool requires tool name; memory/retrieval bare)
    const rules: Array<[string, RegExp]> = [
      ['agent.run', /^invoke_agent \S+$/], ['llm.call', /^chat \S+$/],
      ['tool.execute', /^execute_tool \S+$/], ['retrieval.search', /^retrieval$/],
      ['memory.write', /^upsert_memory$/], ['memory.read', /^search_memory$/],
    ];
    const rule = rules.find(([op]) => op === s.operation);
    if (rule && !rule[1].test(n)) fail(`span name "${n}" violates format ${rule[1]}`);
    // 3. error spans must carry error.type
    if (s.status === 'error' && !m.attributes['error.type']) fail('error span without error.type');
    // 4. Opt-In gating: no content on spans unless capture enabled
    if (!capture) {
      for (const banned of ['gen_ai.prompt', 'gen_ai.completion', 'gen_ai.memory.query.text',
        'gen_ai.memory.records', 'gen_ai.retrieval.query.text', 'gen_ai.tool.call.arguments']) {
        if (banned in m.attributes) fail(`content attribute ${banned} present without opt-in`);
      }
      if (m.events.some(e => e.name === 'gen_ai.client.inference.operation.details'))
        fail('inference details event present without opt-in');
    }
    // 5. usage attributes should be ints
    for (const t of ['gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens']) {
      if (t in m.attributes && !Number.isInteger(m.attributes[t])) fail(`${t} not integer`);
    }
  }
  return { ok: v.length === 0, violations: v };
}
