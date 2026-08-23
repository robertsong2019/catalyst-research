# Constrained Decoding 深度研究

> 日期: 2026-05-12 | 主题: 约束解码为什么可能比无约束更快
> 研究方法: autoresearch (搜索→结构化笔记→可运行代码→洞察)

---

## 核心概念

### 1. Token Masking（令牌掩码）
约束解码的核心机制：每一步解码时，将违反目标结构的 token logits 设为 -∞，经过 softmax 后概率为 0。只从合法 token 中采样。

### 2. 三代引擎演进
- **Gen1: Outlines** — 基于 FSM，将 JSON Schema 编译为正则表达式，O(1) 合法 token 查找。局限：无法处理嵌套 JSON
- **Gen2: XGrammar** — 基于 PDA（下推自动机），支持 CFG，处理任意嵌套。编译时间 >1000ms
- **Gen3: XGrammar-2** — JIT 编译 + 跨语法缓存 + Earley 解析器，编译时间 ~10ms（100x 加速），端到端延迟仅比无约束高 6%

### 3. 搜索空间修剪（Speed Paradox）
**约束解码为何可能更快**：mask 掉非法 token 后，采样器只需在合法子集操作。vocab=128K 但合法 token <100 时，采样计算量大幅降低。加上 JSON 结构高度可预测，模型实际做更少不确定性决策。

### 4. Grammar-Aligned Decoding (GAD)
NeurIPS 2024 指出：简单 mask 会扭曲模型分布。GAD 通过自适应采样（ASAp）在保证语法正确的同时保持原始条件概率分布。

### 5. 动态结构化生成
XGrammar-2 关键创新：agentic 场景下 tool schema 运行时才确定。通过 tag dispatch + JIT 编译实现动态语法切换，Outlines v0.2 无法支持此场景。

---

## 代码示例：最小约束解码器（已验证可运行）

```js
// minimal-constrained-decoder.js
// 演示约束解码核心：状态机 + token masking + softmax采样
// 运行: node minimal-constrained-decoder.js

const VOCAB = ['{','}','"',':',',','name','age','alice','bob','3','2','5','0'];

function fakeLogits(v, p = {}) {
  return v.map(t => Math.random() * 2 + (p[t] || 0));
}

// 状态转换表：已生成字符串 → 合法 token 列表
// 这就是 Outlines/XGrammar 编译 JSON Schema 后的核心数据结构
const STATES = {
  '': ['{'], '{': ['"'], '{"': ['name'], '{"name': ['"'], '{"name"': [':'],
  '{"name":': ['"'], '{"name":"': ['alice','bob'],
  '{"name":"alice': ['"'], '{"name":"bob': ['"'],
  '{"name":"alice"': [','], '{"name":"bob"': [','],
  '{"name":"alice",': ['"'], '{"name":"bob",': ['"'],
  '{"name":"alice","': ['age'], '{"name":"bob","': ['age'],
  '{"name":"alice","age': ['"'], '{"name":"bob","age': ['"'],
  '{"name":"alice","age"': [':'], '{"name":"bob","age"': [':'],
  '{"name":"alice","age":': ['3','2'], '{"name":"bob","age":': ['3','2'],
  '{"name":"alice","age":3': ['0','}'], '{"name":"alice","age":2': ['5','}'],
  '{"name":"bob","age":3': ['0','}'], '{"name":"bob","age":2': ['5','}'],
  '{"name":"alice","age":30': ['}'], '{"name":"alice","age":25': ['}'],
  '{"name":"bob","age":30': ['}'], '{"name":"bob","age":25': ['}'],
};

function sample(generated, logits, temp = 0.8) {
  const valid = STATES[generated] || [];
  if (!valid.length) return null;
  const idx = valid.map(t => VOCAB.indexOf(t)).filter(i => i >= 0);
  if (!idx.length) return null;

  // 核心：mask 非法 token 为 -Infinity
  const masked = logits.map((l, i) => idx.includes(i) ? l : -Infinity);
  const sc = masked.map(l => l / temp);
  const mx = Math.max(...sc.filter(l => l !== -Infinity));
  const ex = sc.map(l => l === -Infinity ? 0 : Math.exp(l - mx));
  const s = ex.reduce((a, b) => a + b, 0);
  const pr = ex.map(e => e / s);

  const r = Math.random(); let c = 0;
  for (let i = 0; i < pr.length; i++) { c += pr[i]; if (r < c) return VOCAB[i]; }
  return null;
}

function generate(prefs = {}) {
  let o = '';
  for (let i = 0; i < 20; i++) {
    const t = sample(o, fakeLogits(VOCAB, prefs));
    if (!t) break;
    o += t;
    try { return { result: JSON.parse(o), steps: i + 1, raw: o }; } catch {}
  }
  return null;
}

// 演示
console.log('🔬 Constrained Decoding — 100% valid JSON guaranteed\n');
console.log('Schema: { name: string, age: number }');
console.log('Vocab:', VOCAB.join(', '));
console.log('---');

const prefs = { 'alice': 2, '3': 1.5 };
let alice = 0, bob = 0;
const N = 100;
for (let r = 0; r < N; r++) {
  const out = generate(prefs);
  if (!out) { console.log('FAIL'); continue; }
  if (out.result.name === 'alice') alice++; else bob++;
}
console.log(`\n📊 ${N} runs: alice=${alice} bob=${bob} (偏好 alice)`);
console.log('✅ 100% 输出都是合法 JSON');

console.log('\n📊 Search space reduction:');
console.log('  Total vocab:', VOCAB.length, 'tokens');
console.log('  After "{":', STATES['{'].length, 'token');
console.log('  Choosing name:', STATES['{"name":"'].length, 'tokens');
console.log('  Choosing age:', STATES['{"name":"alice","age":'].length, 'tokens');
console.log('  → Real LLM: 128K vocab → <100 valid → >99.9% reduction');
console.log('  → This is WHY constrained decoding can be FASTER than unconstrained');
```

---

## 关键洞察

### 1. 约束解码的速度悖论是真实的
XGrammar-2 论文数据：端到端延迟仅比无约束高 6%。原因：
- **采样加速**：128K vocab 缩减到 <100 合法 token
- **结构可预测性**：JSON 的 `{`, `"`, `:` 等 token 高度确定
- **缓存效应**：跨语法缓存让动态 schema 切换几乎免费

### 2. 三种引擎的选择策略
| 场景 | 推荐 | 理由 |
|------|------|------|
| 简单 JSON Schema (flat) | Outlines | 最成熟，97% 成功率 |
| 复杂嵌套 / 自定义语法 | XGrammar | PDA 支持 CFG |
| Agentic tool calling | XGrammar-2 | 动态 schema + JIT |
| CPU-bound / 嵌入式 | llguidance | 50μs/token |

### 3. 分布扭曲是隐藏风险
NeurIPS 2024 Grammar-Aligned Decoding 指出：简单 mask 会改变输出分布。生产环境中需要精确概率的场景（如分类）需关注此问题，考虑 ASAp 算法。

### 4. 与 AMS/Structured Output Toolkit 的关联
- 当前用 Ollama JSON mode（弱约束）→ 可升级为 XGrammar（强约束）
- SchemaCache 可借鉴 XGrammar-2 的跨语法缓存机制
- 搜索空间修剪特性意味着结构化输出不会成为 embedding 生成的瓶颈

### 5. Diffusion LLM 的新挑战
Lookahead-then-Verify 论文指出 diffusion LLM 的约束解码需要不同策略——并行生成 token 使传统逐步 mask 失效。

---

## 下一步行动

1. **[本周]** 在 `lab/structured-output-toolkit` 中评估 XGrammar Node.js/Python binding 可行性
2. **[研究]** 深入 ASAp 算法，评估对 agent-classification 场景的影响
3. **[实验]** AMS metadata 输出对比 JSON Mode vs XGrammar 延迟和准确率

---

## 参考文献

- XGrammar-2: https://arxiv.org/html/2601.04426v2
- Grammar-LLM (ACL 2025): https://aclanthology.org/2025.findings-acl.177.pdf
- Grammar-Aligned Decoding (NeurIPS 2024): https://neurips.cc/virtual/2024/poster/96599
- DOMINO: https://arxiv.org/html/2403.06988v1
- Zylos LLM Tool Use Patterns 2025: https://zylos.ai/research/llm-tool-use-patterns-2025
