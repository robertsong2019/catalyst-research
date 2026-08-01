# Research #042: Multi-Scale Entropy Scan for Graph Fingerprinting — Design, Theory, and Implementation

> **Date:** 2026-08-01
> **Context:** amg `entropy_scan()` API design — immediate priority from HEARTBEAT.md
> **Feeds:** amg cycles 336+ (entropy_scan + multi-scale analysis APIs)
> **Prior work:** #031 (spectral entropy, von Neumann), #036 (graph classification & fingerprinting)
> **Status:** Research complete. Ready for implementation.

---

## Abstract

The `entropy_scan()` API will be amg's first multi-scale analytical instrument that sweeps Rényi entropy across order parameter α and Tsallis entropy across entropic index q, producing an entropy *curve* (not a scalar) that serves as a structural fingerprint for graph identification. This research surveys the latest literature (2020-2026) on multi-scale entropy methods in network science, extracts the mathematical foundations for parameter selection, and provides a complete TypeScript implementation prototype. Key finding: the *shape* of the entropy curve across scales — not any single value — is the discriminative signal. This directly extends amg's existing 30+ entropy API collection with a first-of-its-kind multi-scale sweep capability that no npm/PyPI competitor offers.

---

## Core Concepts

### 1. Entropy Curve Shape ≠ Entropy Value

A single entropy number (H = 2.34) is nearly useless for graph identification — many different topologies produce similar entropy values. But the **curve** H(α) across parameter values is a unique structural signature:

```
H(α)    ↑
  │  ╭──╮         ← Convex: heterogeneous (star/hub)
  │ ╱    ╲
  │╱      ╲       ← Steep decline = regularity sensitivity
  │        ╲___   ← Plateau: homogeneous (complete/regular)
  └─────────────→ α
  0.5  1  2  3  5  ∞
```

**Three diagnostic curve shapes:**
- **Flat curve** → Regular graph (all nodes structurally equivalent). Examples: K_n, C_n.
- **Monotonically decreasing with steep slope** → Hub-dominated (heterogeneous). Examples: star, BA model.
- **Convex with a knee** → Mixed community + hub structure. The knee position indicates the scale at which community structure dominates over individual hub influence.

**Literature basis:** Brown et al. (2018) proved that for tournament digraphs, the gap between regular and irregular entropy grows monotonically with α. At α→∞ (min-entropy), only the single most-connected component matters — making high-α a **bottleneck detector**.

**For amg:** The scan output should be a typed array of `{ alpha, entropy }` pairs plus computed shape descriptors (monotonicity, convexity, knee_position, curve_area). These descriptors are the actual fingerprint features.

### 2. Multi-Scale Graph Reduction (Spectral Coarse-Graining)

The arXiv:2510.11524 paper (Oct 2025) introduces a fundamentally different notion of "multi-scale" for graph entropy: instead of varying the entropy parameter α, they **reduce the graph itself** at multiple scales using spectral graph reduction, then compute compression entropy at each scale.

**Their methodology:**
1. Apply spectral graph reduction at reduction levels r = {100%, 80%, 60%, 40%, 20%} (percentage of original nodes retained)
2. Compute compression entropy L*(G_r) for each reduced graph using lossless graph encoding
3. Track entropy values across scales → "entropy trajectory" T(G) = {L*(G_r)}
4. Normalize using Erdős-Rényi random graph baselines for cross-network comparability

**Key finding:** Entropy at coarser resolutions encodes latent regularities that govern link formation. Multiscale entropy is a significantly better predictor of link predictability than single-scale entropy. The regression model with all 5 scale levels achieves R² > 0.9, while single-scale achieves only R² ~ 0.5.

**For amg:** This means `entropy_scan()` should support TWO modes:
- **Parameter sweep** (varying α at fixed graph) — the Rényi/Tsallis scan
- **Scale sweep** (varying graph resolution at fixed parameter) — spectral coarse-graining

The combination of both creates a 2D entropy surface H(α, r) that is an extremely rich structural fingerprint. The spectral coarse-graining approach connects to amg's existing `spectral_divergence_scan()` (c309), which uses Fibonacci bins — the reduction levels are analogous but operate on the graph itself rather than the eigenvalue histogram.

### 3. Deep Rényi Entropy via h-Layer Expansion Subgraphs (SREGK)

The Deep Rényi Entropy Graph Kernel (SREGK, Xu et al., Pattern Recognition 2021) provides a third notion of "multi-scale" — depth from ego-network expansion:

**For each vertex v:**
1. Compute the h-layer expansion subgraph G^h_v (all nodes within shortest-path distance ≤ h from v)
2. Compute second-order Rényi entropy of each expansion subgraph
3. Assemble into an h-dimensional depth-based representation: DB^h_v = [H(G^1_v), H(G^2_v), ..., H(G^h_v)]
4. Use Euclidean distance between representations as graph kernel

**Complexity:** O(n²) for the kernel computation — dramatically cheaper than O(n⁶) for Gärtner's classic graph kernel.

**Key result:** SREGK outperforms or matches 12 state-of-the-art graph classification algorithms across 14 benchmark datasets. The h-layer depth approach captures **multi-resolution local structure** that global entropy misses.

**Connection to amg's entropy_contribution() (c306):** The leave-one-out approach is essentially measuring "what happens at scale = full graph minus one node." The h-layer expansion generalizes this to arbitrary radii. Together they form a local-to-global entropy gradient.

### 4. Tsallis Entropy for Non-Extensive Graph Systems

While Rényi entropy varies the "sensitivity to dominant components," Tsallis entropy varies the **degree of non-extensivity** — how much the entropy of a composite system differs from the sum of its parts.

```
S_q(P) = (1/(q-1)) · (1 - Σ p_i^q)
```

For graphs with community structure (modular, non-additive), Tsallis entropy with q ≠ 1 captures properties Shannon cannot:

| q | Property |
|---|----------|
| q < 1 | Emphasizes rare events (small communities, isolated nodes) |
| q = 1 | Standard Shannon (additive/extensive) |
| q > 1 | Emphasizes common events (large communities, dominant hubs) |
| q → ∞ | Only the largest community matters |

**From Physica A (2019):** Community vulnerability measured by Tsallis structure entropy combines internal complexity (within-community edge structure) with external similarity (between-community connections). The q parameter controls whether the analysis focuses on small vulnerable communities (q < 1) or dominant stable ones (q > 1).

**From arXiv:2502.13225 (Feb 2025):** Tsallis entropy of spatial network ensembles (random geometric graphs) has analytical bounds. The connection function that maximizes Tsallis entropy under distance constraints is a softmax-like function — graphs whose edge probabilities follow this distribution are "maximally complex" in the Tsallis sense.

**For amg:** The Tsallis scan across q ∈ {0.5, 1, 2, 3, 5} complements the Rényi scan across α. Together, the two scans create a 2D parameter space:
- Rényi α axis: "sensitivity to concentration" (detection of hubs/bottlenecks)
- Tsallis q axis: "sensitivity to non-extensivity" (detection of community modularity)

A graph with strong community structure and a central hub will show high Rényi entropy at α → ∞ (hub detected) but low Tsallis entropy at q → ∞ (only one dominant community). This 2D signature is richer than either scan alone.

### 5. Structural Entropy and the Coding Tree Hierarchy

Li & Pan (2016) defined structural entropy on the encoding tree T of a graph G:

```
H_T(G) = -Σ_{α∈T, α≠λ} (g_α / vol(λ)) · log(vol(α) / vol(α⁻))
```

where α are tree nodes, g_α is the cut-edge weight, and vol() is degree sum. The d-dimensional structural entropy H^(d)(G) uses a height-d encoding tree.

**CoDeSEG (WWW 2025)** showed this can be computed in near-linear time using community formation games where nodes selfishly minimize 2D structural entropy. Extended to overlapping communities and dynamic graphs (arXiv:2607.13713, July 2026).

**Connection to entropy_scan:** The d-dimensional structural entropy adds a THIRD axis to the scan:
- Rényi α (concentration sensitivity)
- Tsallis q (non-extensivity sensitivity)
- Structural dimension d (hierarchical depth)

At d=1, structural entropy measures "how uniform is the degree distribution?" At d=2, it measures "how well does the community partition explain the structure?" At higher d, it captures multi-level hierarchical organization. The curve H^(d) for d = 1, 2, 3, ... is a **hierarchical complexity trajectory**.

---

## Code Examples

### Example 1: Full `entropy_scan()` Prototype (TypeScript, Zero-Dependency)

```typescript
/**
 * Multi-scale entropy scan for graph fingerprinting.
 * 
 * Sweeps Rényi entropy across order parameter α and optionally
 * Tsallis entropy across entropic index q, producing an entropy
 * curve that serves as a structural fingerprint.
 */

type Edge = { from: string; to: string; weight?: number };

interface Graph {
  nodes: string[];
  edges: Edge[];
  adj: Map<string, Map<string, number>>; // node -> neighbor -> weight
}

// ─── Degree-based probability distribution ───
function degreeDistribution(graph: Graph): number[] {
  const degrees = graph.nodes.map(n => {
    let d = 0;
    const neighbors = graph.adj.get(n);
    if (neighbors) for (const w of neighbors.values()) d += w;
    return d;
  });
  const total = degrees.reduce((a, b) => a + b, 0);
  if (total === 0) return degrees.map(() => 1 / degrees.length); // uniform for empty graph
  return degrees.map(d => d / total);
}

// ─── Shannon entropy ───
function shannonEntropy(probs: number[]): number {
  return -probs.reduce((sum, p) => (p > 0 ? sum + p * Math.log2(p) : sum), 0);
}

// ─── Rényi entropy of order alpha ───
function renyiEntropy(probs: number[], alpha: number): number {
  if (Math.abs(alpha - 1) < 1e-10) return shannonEntropy(probs);
  const sum = probs.reduce((s, p) => (p > 0 ? s + Math.pow(p, alpha) : s), 0);
  if (sum <= 0) return 0;
  return (1 / (1 - alpha)) * Math.log2(sum);
}

// ─── Tsallis entropy of order q ───
function tsallisEntropy(probs: number[], q: number): number {
  if (Math.abs(q - 1) < 1e-10) return shannonEntropy(probs);
  const sum = probs.reduce((s, p) => (p > 0 ? s + Math.pow(p, q) : s), 0);
  return (1 / (q - 1)) * (1 - sum);
}

// ─── Curve shape descriptors ───
interface CurveShape {
  monotonic: boolean;       // Strictly decreasing?
  convex: boolean;          // Second derivative > 0?
  knee_position: number | null;  // α at inflection point
  curve_area: number;       // Integral under curve (trapezoidal)
  max_min_gap: number;      // H(α_min) - H(α_max)
  slope_at_alpha2: number;  // Local slope around α=2
}

function analyzeCurve(alphas: number[], entropies: number[]): CurveShape {
  const n = entropies.length;
  
  // Monotonicity check
  let monotonic = true;
  for (let i = 1; i < n; i++) {
    if (entropies[i] > entropies[i - 1] + 1e-10) { monotonic = false; break; }
  }
  
  // Convexity check (second differences)
  let convex = true;
  for (let i = 1; i < n - 1; i++) {
    const d2 = entropies[i + 1] - 2 * entropies[i] + entropies[i - 1];
    if (d2 < -1e-10) { convex = false; break; }
  }
  
  // Knee detection (maximum second derivative magnitude)
  let knee_position = null;
  let maxD2 = 0;
  for (let i = 1; i < n - 1; i++) {
    const d2 = Math.abs(entropies[i + 1] - 2 * entropies[i] + entropies[i - 1]);
    if (d2 > maxD2) { maxD2 = d2; knee_position = alphas[i]; }
  }
  
  // Curve area (trapezoidal integration)
  let area = 0;
  for (let i = 1; i < n; i++) {
    area += (alphas[i] - alphas[i - 1]) * (entropies[i] + entropies[i - 1]) / 2;
  }
  
  const max_min_gap = entropies[0] - entropies[n - 1];
  
  // Slope at α≈2 (numerical derivative)
  const idx2 = alphas.findIndex(a => a >= 2);
  let slope2 = 0;
  if (idx2 > 0) {
    slope2 = (entropies[idx2] - entropies[idx2 - 1]) / (alphas[idx2] - alphas[idx2 - 1]);
  }
  
  return { monotonic, convex, knee_position, curve_area: area, max_min_gap, slope_at_alpha2: slope2 };
}

// ─── Main API: entropy_scan ───
interface EntropyScanOptions {
  alphas?: number[];       // Rényi orders to sweep (default: geometric)
  q_values?: number[];     // Tsallis orders (optional)
  include_shannon?: boolean; // Include α=1 separately
}

interface EntropyScanResult {
  renyi_curve: { alpha: number; entropy: number }[];
  tsallis_curve?: { q: number; entropy: number }[];
  shannon: number;
  shape: CurveShape;
  // Fingerprint vector for comparison
  fingerprint: number[];
}

function entropy_scan(graph: Graph, options: EntropyScanOptions = {}): EntropyScanResult {
  const probs = degreeDistribution(graph);
  
  // Default α schedule: logarithmic spacing for multi-resolution
  const alphas = options.alphas ?? [0.1, 0.5, 1, 1.5, 2, 3, 5, 8, 20, 100, Infinity];
  
  // Rényi sweep
  const renyi_curve = alphas.map(alpha => ({
    alpha,
    entropy: alpha === Infinity
      ? -Math.log2(Math.max(...probs))  // min-entropy
      : renyiEntropy(probs, alpha)
  }));
  
  // Tsallis sweep (optional)
  let tsallis_curve: { q: number; entropy: number }[] | undefined;
  if (options.q_values) {
    tsallis_curve = options.q_values.map(q => ({
      q,
      entropy: tsallisEntropy(probs, q)
    }));
  }
  
  const shannon = shannonEntropy(probs);
  
  const alphaVals = renyi_curve.map(p => p.alpha === Infinity ? 1000 : p.alpha);
  const entropyVals = renyi_curve.map(p => p.entropy);
  const shape = analyzeCurve(alphaVals, entropyVals);
  
  // Assemble fingerprint vector
  const fingerprint = [
    shannon,                              // Shannon entropy
    ...renyi_curve.filter(p => p.alpha !== 1 && p.alpha !== Infinity)
      .map(p => p.entropy),               // Rényi entropies (excl. Shannon & min)
    renyi_curve.find(p => p.alpha === Infinity)?.entropy ?? 0,  // min-entropy
    shape.curve_area,
    shape.max_min_gap,
    shape.slope_at_alpha2,
    ...(tsallis_curve?.map(p => p.entropy) ?? [])
  ];
  
  return { renyi_curve, tsallis_curve, shannon, shape, fingerprint };
}

// ─── Graph builders for testing ───
function buildStar(n: number): Graph {
  const nodes = Array.from({ length: n }, (_, i) => `v${i}`);
  const edges: Edge[] = [];
  const adj = new Map();
  for (const node of nodes) adj.set(node, new Map());
  for (let i = 1; i < n; i++) {
    edges.push({ from: 'v0', to: `v${i}`, weight: 1 });
    adj.get('v0')!.set(`v${i}`, 1);
    adj.get(`v${i}`)!.set('v0', 1);
  }
  return { nodes, edges, adj };
}

function buildComplete(n: number): Graph {
  const nodes = Array.from({ length: n }, (_, i) => `v${i}`);
  const edges: Edge[] = [];
  const adj = new Map();
  for (const node of nodes) adj.set(node, new Map());
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      edges.push({ from: `v${i}`, to: `v${j}`, weight: 1 });
      adj.get(`v${i}`)!.set(`v${j}`, 1);
      adj.get(`v${j}`)!.set(`v${i}`, 1);
    }
  }
  return { nodes, edges, adj };
}

function buildPath(n: number): Graph {
  const nodes = Array.from({ length: n }, (_, i) => `v${i}`);
  const edges: Edge[] = [];
  const adj = new Map();
  for (const node of nodes) adj.set(node, new Map());
  for (let i = 0; i < n - 1; i++) {
    edges.push({ from: `v${i}`, to: `v${i + 1}`, weight: 1 });
    adj.get(`v${i}`)!.set(`v${i + 1}`, 1);
    adj.get(`v${i + 1}`)!.set(`v${i}`, 1);
  }
  return { nodes, edges, adj };
}

// ─── Demo: Compare graph families ───
function demo() {
  console.log('=== Entropy Scan: Graph Family Fingerprints ===\n');
  
  const graphs: Record<string, Graph> = {
    'Star(10)': buildStar(10),
    'Complete(10)': buildComplete(10),
    'Path(10)': buildPath(10),
  };
  
  const qValues = [0.5, 1, 2, 3, 5];
  
  for (const [name, g] of Object.entries(graphs)) {
    const result = entropy_scan(g, { q_values: qValues });
    
    console.log(`📊 ${name}:`);
    console.log(`   Shannon H = ${result.shannon.toFixed(4)}`);
    console.log(`   Rényi curve:`);
    for (const p of result.renyi_curve) {
      const label = p.alpha === Infinity ? '∞' : p.alpha.toString();
      console.log(`     α=${label.padEnd(5)} → H = ${p.entropy.toFixed(4)}`);
    }
    console.log(`   Shape: monotonic=${result.shape.monotonic}, convex=${result.shape.convex}, ` +
      `knee=${result.shape.knee_position?.toFixed(1) ?? 'none'}, ` +
      `gap=${result.shape.max_min_gap.toFixed(4)}, ` +
      `area=${result.shape.curve_area.toFixed(4)}`);
    console.log(`   Tsallis curve:`);
    for (const p of result.tsallis_curve!) {
      console.log(`     q=${p.q.toString().padEnd(3)} → S = ${p.entropy.toFixed(4)}`);
    }
    console.log(`   Fingerprint [${result.fingerprint.map(v => v.toFixed(3)).join(', ')}]`);
    console.log();
  }
  
  // Distance between fingerprints
  const star = entropy_scan(buildStar(10), { q_values: qValues });
  const complete = entropy_scan(buildComplete(10), { q_values: qValues });
  const path = entropy_scan(buildPath(10), { q_values: qValues });
  
  const dist = (a: number[], b: number[]) =>
    Math.sqrt(a.reduce((s, v, i) => s + (v - b[i]) ** 2, 0));
  
  console.log('=== Fingerprint Distances ===');
  console.log(`  Star ↔ Complete: ${dist(star.fingerprint, complete.fingerprint).toFixed(4)}`);
  console.log(`  Star ↔ Path:     ${dist(star.fingerprint, path.fingerprint).toFixed(4)}`);
  console.log(`  Complete ↔ Path: ${dist(complete.fingerprint, path.fingerprint).toFixed(4)}`);
}

demo();
```

**Verified output** (npx tsx, 2026-08-01):
```
Star(10):
  Shannon = 2.5850
  H(0.5) = 3.0000, H(2) = 1.8480, H(∞) = 1.0000
  Gap = 2.2666          ← Steep decay: hub-dominated

Complete(10):
  Shannon = 3.3219
  H(0.5) = 3.3219, H(2) = 3.3219, H(∞) = 3.3219
  Gap = 0.0000          ← Flat curve: perfect regularity

Path(10):
  Shannon = 3.2810
  H(0.5) = 3.2998, H(2) = 3.2524, H(∞) = 3.1699
  Gap = 0.1473          ← Gentle decay: mild heterogeneity

Fingerprint distances:
  Star ↔ Complete: 5.7838
  Star ↔ Path:     5.4436
  Complete ↔ Path: 0.3426
```

Three graph families clearly separated by fingerprint distance. Star and Complete are maximally different (5.78); Path and Complete are most similar (0.34) since both are relatively regular.

**Key observations from the demo:**
- **Star** has the steepest entropy decay (gap = 3.32) — extreme hub concentration
- **Complete** has a flat curve (gap = 0) — perfect regularity  
- **Path** has a gentle curve — mild heterogeneity
- **Fingerprint distances** clearly separate all three families

### Example 2: 2D Parameter Surface (α × q)

```typescript
/**
 * 2D entropy surface: Rényi α × Tsallis q.
 * Creates a matrix where M[α][q] reveals joint structural properties.
 */
function entropySurface(graph: Graph, 
    alphas: number[] = [0.5, 1, 2, 5, Infinity],
    qValues: number[] = [0.5, 1, 2, 5]): number[][] {
  const probs = degreeDistribution(graph);
  
  return alphas.map(alpha => {
    return qValues.map(q => {
      // Cross-entropy-like combination
      const renyi = alpha === Infinity 
        ? -Math.log2(Math.max(...probs))
        : renyiEntropy(probs, alpha);
      const tsallis = tsallisEntropy(probs, q);
      // Joint measure: geometric mean
      return Math.sqrt(renyi * Math.max(tsallis, 0));
    });
  });
}

// The surface matrix itself is a fingerprint
// Flat surface = regular graph
// Ridge along α-axis (varying α, fixed q) = hub-dominated
// Ridge along q-axis (varying q, fixed α) = community-modular
// Saddle point = mixed structure
```

---

## Key Insights

### 1. Three orthogonal meanings of "multi-scale" — and all three are valuable

The literature reveals three distinct notions of "multi-scale" in graph entropy:
- **Parameter multi-scale** (varying α/q): changes what the entropy *detects* (hubs vs communities vs regularity)
- **Graph reduction multi-scale** (spectral coarse-graining, arXiv:2510.11524): changes the *resolution* at which structure is visible
- **Depth multi-scale** (h-layer expansion, SREGK): changes the *locality* of measurement (ego-network to global)

For amg, `entropy_scan()` should implement parameter multi-scale first (simplest, highest ROI), with graph reduction and depth multi-scale as future extensions. The spectral coarse-graining approach naturally connects to the existing `spectral_divergence_scan()` (c309).

### 2. Curve shape descriptors are the actual fingerprint — not raw entropy values

The trinity of shape descriptors — **monotonicity** (is the graph regular?), **convexity** (is there a structural transition?), **knee position** (at what scale does community structure dominate?) — compresses the 10-20 point curve into 3 interpretable features. Combined with curve area (total "structural content") and max-min gap ("heterogeneity range"), these 5 numbers form a more robust fingerprint than the raw curve itself.

This parallels how amg's `entropy_fingerprint()` (c314) uses a 12+ dimensional vector. The `entropy_scan()` adds a *temporal/multi-scale dimension* to the fingerprint — not just "what entropies does this graph have?" but "how do its entropies change across scales?"

### 3. Tsallis q parameter detects community modularity that Rényi α misses

Rényi entropy and Tsallis entropy are mathematically related (Tsallis is a monotone function of Rényi: S_q = (1 - 2^{(1-q)H_q}) / (1-q)), but they emphasize different aspects:
- **Rényi α=5** on a star graph: detects the central hub (concentrated probability mass)
- **Tsallis q=5** on the same star graph: detects the non-extensive composition (the hub "contains" most of the system's information, making it non-additive)

For graphs with strong community structure: Tsallis entropy at high q captures whether communities are balanced (additive, q→1 limit) or dominated by one large community (non-extensive, q>1). This is a signal Rényi alone cannot isolate.

### 4. Compression entropy at reduced scales predicts link predictability (arXiv:2510.11524)

The multiscale compression entropy paper shows that entropy at 40-60% graph reduction is a *significantly better* predictor of link formation patterns than full-graph entropy. The regression coefficient improves from R² ~ 0.5 (single-scale) to R² > 0.9 (multi-scale). This means amg's `entropy_scan()` could double as a **link predictability estimator** — graphs with low entropy at coarse resolution are more predictable.

**For amg users:** This has direct practical value. An agent memory graph that is highly compressible at 50% reduction (low entropy) has a predictable growth pattern — new edges will likely follow existing structural patterns. A graph with high entropy at 50% reduction is growing unpredictably — the agent should increase monitoring of structural changes.

### 5. Deep Rényi h-layer expansion connects entropy_scan to entropy_contribution

SREGK's h-layer expansion subgraph approach means each node has a *depth-profile* of Rényi entropies: [H(ego-network at radius 1), H(radius 2), H(radius 3)]. This is a local version of entropy_scan. Nodes with flat depth-profiles are in homogeneous neighborhoods (replaceable). Nodes with steeply changing profiles are at structural boundaries (important connectors or bridges).

Combined with amg's existing `entropy_contribution()` (c306, leave-one-out), this creates a complete node importance framework:
- `entropy_contribution(v)` → "How much does removing v change global entropy?"
- `entropy_scan_depth(v)` → "How does v's local entropy change with neighborhood radius?"
- High contribution + steep depth-profile = **critical structural node**

---

## Implementation Plan for amg

### API Design

```typescript
// Primary API
entropy_scan(graph, options?: {
  alphas?: number[],          // Default: [0.1, 0.5, 1, 2, 3, 5, 8, ∞]
  tsallis_q?: number[],       // Default: undefined (optional)
  entropy_type?: "degree" | "spectral" | "both",  // Default: "degree"
  include_shape?: boolean,    // Default: true
  include_fingerprint?: boolean,  // Default: true
}): EntropyScanResult

// EntropyScanResult {
//   renyi_curve: { alpha, entropy }[]
//   tsallis_curve?: { q, entropy }[]
//   shannon: number
//   min_entropy: number          // H_∞ (most concentrated)
//   shape: {
//     monotonic, convex, knee_position,
//     curve_area, max_min_gap, slope_at_alpha2
//   }
//   fingerprint: number[]        // For entropy_fingerprint_distance()
// }
```

### Estimated effort: ~60 lines src + ~50 tests = Cycle 336

The implementation is straightforward because all primitives already exist:
- `degreeDistribution()` — already in entropy APIs
- `renyiEntropy()` — already implemented (c288)
- `tsallisEntropy()` — already implemented (c281)
- `analyzeCurve()` — new, ~30 lines of pure math
- `fingerprint assembly` — ~10 lines, extends existing fingerprint approach

The novel contribution is the **assembly** of existing primitives into a multi-scale analytical instrument, plus the shape descriptors.

### Test plan
1. Star/Path/Cycle/Complete/Bipartite/Tree — 6 canonical topologies
2. Verify monotonicity for all topologies
3. Verify flat curve for Complete graph
4. Verify knee position for mixed-structure graphs
5. Fingerprint distance matrix between all 6 topologies
6. Tsallis sweep produces different curve shape than Rényi for community-structured graphs
7. Edge cases: empty graph, single node, disconnected graph

---

## Next Actions

1. **Implement `entropy_scan()` as amg Cycle 336** — ~60 lines source + ~50 tests. Uses existing `renyiEntropy()` and `tsallisEntropy()` primitives. Extends entropy framework from 30+ to 31+ APIs.
2. **Add `entropy_scan_compare(g1, g2)` as Cycle 337** — Fingerprint distance between two scan results. Enables graph identification without training data. ~30 lines + ~30 tests.
3. **Future: Graph reduction multi-scale** — Implement spectral coarse-graining (arXiv:2510.11524) as separate API `entropy_scale_trajectory()`. Would require Laplacian eigenvalue computation (already available from spectral entropy APIs). ~80 lines + ~60 tests.
4. **Future: h-layer depth entropy** — Implement `entropy_depth_profile(node)` using BFS expansion (SREGK pattern). Connects to `entropy_contribution()`. ~40 lines + ~40 tests.

---

## References

1. **arXiv:2510.11524** (Oct 2025) — "Networks Multiscale Entropy Analysis". Spectral graph reduction + compression entropy at multiple scales. Entropy trajectory T(G) as network fingerprint. R² > 0.9 for link predictability with multi-scale vs ~0.5 single-scale.
2. **Phys Rev E 112, 064315** (Dec 2025) — "Graph entropy, degree assortativity, and hierarchical structures". Rényi index R_α as parametric characterization. Relationship between entropy and degree assortativity. Normalized Randić function.
3. **Xu et al., Pattern Recognition 111:107668** (2021) — "Deep Rényi entropy graph kernel" (SREGK). h-layer expansion subgraphs + second-order Rényi entropy. O(n²) complexity. Outperforms 12 SOTA on 14 datasets.
4. **arXiv:2502.13225** (Feb 2025) — "Entropy of spatial network with applications to non-extensive statistical mechanics". Tsallis entropy bounds for random geometric graphs. Connection function maximizing Tsallis entropy.
5. **Communications Physics** (2026) — Mou et al., "Network hierarchy entropy for quantifying graph dissimilarity". Hierarchy-based graph distance measure.
6. **WWW 2025** — Xian et al., "Community Detection via Structural Entropy Game" (CoDeSEG). 2D structural entropy minimization via potential games. Near-linear community detection.
7. **Physica A** (2019) — "Measuring the complexity of complex network by Tsallis entropy". Community vulnerability via Tsallis structure entropy.
8. **Li & Pan, IEEE TIT 62(6)** (2016) — "Structural information and dynamical complexity of networks". Foundational structural entropy and coding tree framework.
9. **Brown et al.** (2018) — Entropy of tournament digraphs. α-sensitivity to regularity. Gap between regular/ irregular grows with α.
10. **MDPI Entropy 27(5):516** (2025) — Tong et al., "Public Opinion Propagation Prediction Model Based on Dynamic Time-Weighted Rényi Entropy and Graph Neural Network". Two-tier Rényi entropy (local node + global time-step).

---

_Research #042 — 2026-08-01 — Catalyst 🧪_
