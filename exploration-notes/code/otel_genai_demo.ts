/**
 * otel_genai_demo.ts — E2E: run the REAL lab/agent-observability toolkit,
 * export its trace under OTel GenAI conventions, lint compliance.
 * Run: npx tsx otel_genai_demo.ts   (from code/ dir)
 */
import { AgentObserver } from '/root/.openclaw/workspace/lab/agent-observability/src/index.js';
import { exportGenAiOtlp, lintGenAiSpans, evaluationEventAttributes } from './otel_genai_align.ts';

// 1) Real run through the actual toolkit (policy engine included)
const obs = new AgentObserver();
obs.getPolicyEngine().loadFromJSON([
  { name: 'no-rm', description: 'Block rm', category: 'tool_execution', type: 'blockDestructiveOps' },
]);

obs.startRun('research-agent', 'Summarize GenAI semconv');
obs.llmCall('gpt-4o-mini', 'Summarize the OTel GenAI spec', 'The spec defines gen_ai.* conventions.',
  { promptTokens: 120, completionTokens: 80 });

const denied = obs.toolExecute('bash', 'rm -rf /tmp/x');   // -> policy denies
const allowed = obs.toolExecute('grep', 'gen-ai model/*.md');

obs.memoryOperation('write', { namespace: 'user-prefs', items: 3 });
obs.memoryOperation('read', { namespace: 'user-prefs', results: 2, query: 'dietary preferences' });
obs.retrievalSearch('vector', { top_k: 5, query: 'otel genai' });
obs.endRun();

const spans = obs.getTracer().getSpans() as any[];
console.log(`=== 1) Real run captured: ${spans.length} internal spans ===`);
console.log(spans.map(s => `  ${s.operation}`).join('\n'));

// 2) Export WITHOUT content capture (spec default) + lint
console.log('\n=== 2) GenAI-convention export (captureContent=off, spec default) ===');
const lintOff = lintGenAiSpans(spans);
const otlp = exportGenAiOtlp(spans, { captureContent: false });
for (const s of otlp.resourceSpans[0].scopeSpans[0].spans) {
  const attrs = s.attributes.filter((x: any) => x.key.startsWith('gen_ai.') || x.key === 'error.type')
    .map((x: any) => `${x.key}=${x.value.intValue ?? x.value.stringValue}`).join(' ');
  console.log(`  [${s.kind.replace('SPAN_KIND_', '')}] ${s.name}  ${attrs}`);
}
console.log(`  lint: ${lintOff.ok ? 'PASS ✅' : 'FAIL'} ${lintOff.violations.join('; ')}`);
console.log(`  details events emitted: ${otlp.resourceSpans[0].scopeSpans[0].spans
  .reduce((n: number, s: any) => n + (s.events?.length ?? 0), 0)} (content gated OFF -> must be 0)`);

// 3) Export WITH opt-in content capture -> inference details event appears
console.log('\n=== 3) captureContent=on (opt-in) ===');
const otlpOn = exportGenAiOtlp(spans, { captureContent: true });
const chat = otlpOn.resourceSpans[0].scopeSpans[0].spans.find((s: any) => s.name.startsWith('chat'));
console.log(`  chat span now carries ${chat.events.length} event(s): ${chat.events[0].name}`);
console.log(`  raw: ${JSON.stringify(chat.events[0].attributes.find((a: any) => a.key === 'gen_ai.input.messages')?.value.__raw).slice(0, 90)}...`);

// 4) Denied tool span must be ERROR + error.type (spec: Recording Errors)
const tool = otlp.resourceSpans[0].scopeSpans[0].spans.find((s: any) => s.name.startsWith('execute_tool bash'));
console.log(`\n=== 4) Policy-denied tool span ===`);
console.log(`  status=${tool.status.code}  error.type=${tool.attributes.find((a: any) => a.key === 'error.type')?.value.stringValue}`);

// 5) Evaluator -> gen_ai.evaluation.result events on root span
const evalResults = obs.getReport().evalResults as any[];
console.log(`\n=== 5) Evaluation events (spec v1.38) ===`);
for (const r of evalResults.slice(0, 3)) {
  const ev = evaluationEventAttributes(r.dimension, r.score, r.reason);
  console.log(`  gen_ai.evaluation.result ${JSON.stringify(ev)}`.slice(0, 110) + '...');
}

const lintOn = lintGenAiSpans(spans, { captureContent: true });
console.log(`\n=== 6) Final lint (capture=on): ${lintOn.ok ? 'PASS ✅' : 'FAIL: ' + lintOn.violations.join('; ')} ===`);
console.log(`Denied=${denied.allowed === false}, Allowed=${allowed.allowed === true} (policy engine intact)`);
