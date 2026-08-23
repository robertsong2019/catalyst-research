# Hindsight Mini — Agent Self-Reflection via Trajectory Replay

**Date**: 2026-05-13  
**Status**: Research Complete → Ready for lab/ Implementation  
**Priority**: Medium (HEARTBEAT.md 中优先级)

---

## 核心概念

### 1. Hindsight Experience Replay (HER) for LLM Agents
源自 AgentHER (arXiv:2603.21357) — 将失败轨迹重标为成功轨迹用于训练。
- **关键洞察**: 失败轨迹 ≠ 垃圾数据。轨迹达到了某个状态（只是不是目标状态），把这个状态当作"伪目标"就能获得学习信号
- **AgentHER 的创新**: 3阶段流水线 — Failure Detection → Hindsight Extraction → Preference Optimization (DPO)
- **无需微调的轻量版**: 用 Reflexion 风格的语言反馈替代 DPO，保持模型冻结

### 2. Reflexion: Verbal Reinforcement
Reflexion (Shinn et al., 2023) 用语言反馈替代标量奖励：
- Actor → 执行任务 → 获得轨迹
- Evaluator → 评分 → 生成语言反思
- 反思存入长期记忆 → 下次任务作为上下文
- **实测**: AlfWorld 130/134 挑战成功（vs 基线 80%）

### 3. SE-Agent: Trajectory Evolution
SE-Agent (arXiv:2508.02085) 提出轨迹进化：
- **Revision**: 自我反思改进单条轨迹
- **Recombination**: 组合多条轨迹的优势
- **Selection**: 选择最优结果
- 关键操作: τ′ = Revise(τ, R) 其中 R 是反思结果

### 4. Thought-Action Alignment Check
来自 ASE 2025 轨迹分析研究 — 思维与行动的错位是失败主因：
- 即使单个 thought-action misalignment 也可能导致级联失败
- **建议**: 显式验证步骤，确保 action 与 thought 对齐

### 5. Hindsight Mini 设计哲学
将上述研究的精华压缩为可嵌入 OpenClaw 的轻量模块：
- **不微调模型** — 用 memory + prompt 实现反思
- **接入 agent-context-store** — 复用已有存储
- **渐进式** — 从简单反思开始，逐步增加轨迹分析能力

---

## 代码示例: Hindsight Mini 核心 (TypeScript)

```typescript
// hindsight-mini.ts — 可运行的核心实现
// 依赖: 无外部依赖，纯 TypeScript

interface TrajectoryStep {
  thought: string;
  action: string;
  result: string;
  timestamp: number;
}

interface Trajectory {
  task: string;
  goal: string;
  steps: TrajectoryStep[];
  outcome: 'success' | 'failure' | 'partial';
  finalState: string;
}

interface Reflection {
  taskId: string;
  summary: string;
  mistakes: string[];
  corrections: string[];
  patterns: string[];
  confidence: number;
  timestamp: number;
}

interface HindsightEntry {
  originalTrajectory: Trajectory;
  reflection: Reflection;
  relabeledGoal: string;  // HER: 实际达到的状态作为伪目标
  lessons: string[];      // 提取的可复用教训
}

/**
 * Hindsight Mini — 轻量级 Agent 自反思引擎
 * 
 * 核心循环:
 * 1. 记录轨迹 (Trajectory)
 * 2. 评估结果 (Evaluate) 
 * 3. 生成反思 (Reflect)
 * 4. 重标目标 (Relabel — HER)
 * 5. 存储教训 (Store)
 */
class HindsightMini {
  private memory: HindsightEntry[] = [];
  private readonly maxMemory = 100;

  constructor(initialMemory?: HindsightEntry[]) {
    if (initialMemory) this.memory = initialMemory;
  }

  /**
   * 核心方法: 处理一条轨迹，生成反思
   */
  processTrajectory(trajectory: Trajectory): HindsightEntry {
    // Step 1: 识别失败点 (Failure Detection)
    const failurePoints = this.detectFailures(trajectory);

    // Step 2: 生成反思 (Reflection Generation)
    const reflection = this.generateReflection(trajectory, failurePoints);

    // Step 3: HER 重标 — 用实际达到的状态作为伪目标
    const relabeledGoal = trajectory.finalState;

    // Step 4: 提取教训 (Lesson Extraction)
    const lessons = this.extractLessons(trajectory, reflection);

    const entry: HindsightEntry = {
      originalTrajectory: trajectory,
      reflection,
      relabeledGoal,
      lessons,
    };

    this.store(entry);
    return entry;
  }

  /**
   * 失败检测: 找到 thought-action misalignment
   */
  private detectFailures(t: Trajectory): number[] {
    const failures: number[] = [];
    
    for (let i = 0; i < t.steps.length; i++) {
      const step = t.steps[i];
      // 检测1: 结果为空或错误
      if (!step.result || step.result.includes('error') || step.result.includes('Error')) {
        failures.push(i);
      }
      // 检测2: thought 和 action 不一致 (简单启发式)
      const actionWords = step.action.toLowerCase().split(/\s+/);
      const thoughtKeywords = step.thought.toLowerCase().split(/\s+/).filter(
        w => w.length > 4
      );
      const overlap = actionWords.filter(w => thoughtKeywords.includes(w)).length;
      if (overlap === 0 && thoughtKeywords.length > 2) {
        failures.push(i);
      }
    }

    return [...new Set(failures)]; // 去重
  }

  /**
   * 反思生成: 结构化分析失败原因
   */
  private generateReflection(t: Trajectory, failures: number[]): Reflection {
    const mistakes: string[] = [];
    const corrections: string[] = [];
    const patterns: string[] = [];

    for (const idx of failures) {
      const step = t.steps[idx];
      mistakes.push(`Step ${idx}: thought="${step.thought}" but action="${step.action}"`);

      // 生成修正建议
      if (step.result.includes('error')) {
        corrections.push(`Step ${idx}: 在 action 之前应验证前置条件`);
      } else {
        corrections.push(`Step ${idx}: action 应与 thought 的意图保持一致`);
      }
    }

    // 模式识别: 检查是否有重复的错误模式
    const recentEntries = this.memory.slice(-10);
    for (const entry of recentEntries) {
      for (const mistake of entry.reflection.mistakes) {
        for (const currentMistake of mistakes) {
          if (this.similarity(mistake, currentMistake) > 0.5) {
            patterns.push(`重复模式: ${mistake}`);
          }
        }
      }
    }

    return {
      taskId: `${t.task}-${Date.now()}`,
      summary: `轨迹包含 ${failures.length} 个失败点，${t.steps.length} 个总步骤`,
      mistakes,
      corrections,
      patterns,
      confidence: failures.length === 0 ? 1.0 : 
                  Math.max(0.1, 1 - failures.length / t.steps.length),
      timestamp: Date.now(),
    };
  }

  /**
   * 教训提取: 从反思中生成可复用的规则
   */
  private extractLessons(t: Trajectory, r: Reflection): string[] {
    const lessons: string[] = [];

    // 从失败中提取
    for (let i = 0; i < r.mistakes.length; i++) {
      if (r.corrections[i]) {
        lessons.push(`规则: ${r.corrections[i]} (来源: ${r.mistakes[i]})`);
      }
    }

    // 从成功步骤中提取 (HER 思想: 正例也有价值)
    for (let i = 0; i < t.steps.length; i++) {
      if (!r.mistakes.some(m => m.startsWith(`Step ${i}:`))) {
        lessons.push(`正例: Step ${i} 的 thought-action 对齐良好`);
      }
    }

    return lessons;
  }

  /**
   * 获取相关历史教训 (用于注入 prompt)
   */
  getRelevantLessons(taskDescription: string, limit = 5): string[] {
    const allLessons = this.memory.flatMap(e => e.lessons);
    // 简单相关性排序: 按 overlap 排序
    return allLessons
      .sort((a, b) => 
        this.similarity(b, taskDescription) - this.similarity(a, taskDescription)
      )
      .slice(0, limit);
  }

  /**
   * 生成反思 prompt 增量 (直接注入到 agent 的 system prompt)
   */
  buildReflectionContext(task: string): string {
    const lessons = this.getRelevantLessons(task);
    const recentReflections = this.memory.slice(-3).map(e => 
      `- ${e.reflection.summary} (${e.reflection.mistakes.length} mistakes)`
    );

    return [
      '## Historical Reflections',
      ...recentReflections,
      '',
      '## Applicable Lessons',
      ...lessons,
      '',
      '## Guidance',
      '- Verify thought-action alignment at each step',
      '- Check preconditions before executing actions',
      '- If a pattern of failures appears, try a different approach',
    ].join('\n');
  }

  private store(entry: HindsightEntry): void {
    this.memory.push(entry);
    if (this.memory.length > this.maxMemory) {
      this.memory.shift(); // FIFO
    }
  }

  private similarity(a: string, b: string): number {
    const wordsA = new Set(a.toLowerCase().split(/\s+/));
    const wordsB = new Set(b.toLowerCase().split(/\s+/));
    const intersection = [...wordsA].filter(w => wordsB.has(w)).length;
    const union = new Set([...wordsA, ...wordsB]).size;
    return union === 0 ? 0 : intersection / union; // Jaccard similarity
  }

  // 序列化 (用于接入 agent-context-store)
  serialize(): string {
    return JSON.stringify(this.memory);
  }

  static deserialize(data: string): HindsightMini {
    const memory = JSON.parse(data) as HindsightEntry[];
    return new HindsightMini(memory);
  }
}

// ============ 可运行测试 ============

function runDemo() {
  const engine = new HindsightMini();

  // 模拟一条失败轨迹
  const failedTrajectory: Trajectory = {
    task: 'search-and-summarize',
    goal: '搜索最新的 RAG 论文并总结关键发现',
    steps: [
      {
        thought: '我需要搜索 RAG 相关的最新论文',
        action: 'tavily_search("RAG retrieval augmented generation 2026")',
        result: 'Found 5 papers on RAG techniques...',
        timestamp: Date.now() - 5000,
      },
      {
        thought: '应该提取第一篇论文的内容',
        action: 'delete_file("important_config.yml")',  // action 与 thought 不匹配!
        result: 'Error: permission denied',
        timestamp: Date.now() - 3000,
      },
      {
        thought: '继续总结论文内容',
        action: 'summarize(papers[0])',
        result: '',
        timestamp: Date.now() - 1000,
      },
    ],
    outcome: 'failure',
    finalState: '部分完成：搜索成功但未能提取和总结',
  };

  // 处理轨迹
  const entry = engine.processTrajectory(failedTrajectory);

  console.log('=== Hindsight Mini Demo ===\n');
  console.log('反思摘要:', entry.reflection.summary);
  console.log('\n识别的错误:');
  entry.reflection.mistakes.forEach(m => console.log('  ❌', m));
  console.log('\n修正建议:');
  entry.reflection.corrections.forEach(c => console.log('  ✅', c));
  console.log('\nHER 重标目标:', entry.relabeledGoal);
  console.log('\n提取的教训:');
  entry.lessons.forEach(l => console.log('  📝', l));

  // 生成反思上下文
  console.log('\n=== 下次任务的 Prompt 增量 ===\n');
  console.log(engine.buildReflectionContext('search-papers'));
}

runDemo();
```

**运行方式:**
```bash
# 使用 ts-node 或 deno
npx ts-node hindsight-mini.ts
# 或
deno run hindsight-mini.ts
```

---

## 关键洞察

### 洞察 1: HER 的本质是"数据增强"而非"训练技巧"
AgentHER 证明重标失败轨迹可以提升 8-9% 成功率（Qwen-7B: 17.8% → 27.8%）。但在 Hindsight Mini 中我们不微调模型，而是用**语言反馈**实现类似效果 — 将反思存入 memory，作为后续任务的上下文。这是一种"prompt-level HER"。

### 洞察 2: Thought-Action Misalignment 是头号杀手
ASE 2025 的轨迹分析表明，即使一个 thought-action 错位也可能导致级联失败。Hindsight Mini 的 `detectFailures()` 方法专门检测这类问题。**实用建议**: 每个 agent step 后加一个轻量 alignment check 比事后分析更有效。

### 洞察 3: 模式识别比单次反思更有价值
重复的错误模式（如"总是忘记检查前置条件"）比一次性错误更值得修复。Hindsight Mini 的 `patterns` 字段跨轨迹追踪重复模式。这与 AGENTS.md 的 Error Escalation Protocol 思路一致 — 第3次出现就写规则阻止。

### 洞察 4: 轻量级的边界
- **不需要微调** — 保持模型冻结，用 memory 实现"学习"
- **不需要外部评估器** — 用启发式规则检测失败
- **渐进升级路径** — 从启发式 → LLM-as-judge → 轨迹进化 (SE-Agent)

### 洞察 5: 与现有项目的天然集成点
- `agent-context-store` (76/76 tests) → 作为 HindsightEntry 的持久化后端
- `agent-memory-graph` (30/30 tests) → 跨轨迹的模式识别用图遍历
- AGENTS.md Error Escalation Protocol → Hindsight Mini 是其自动化实现

---

## 下一步行动

1. **创建 `lab/hindsight-mini/`** — 将上面代码放入 `src/hindsight-mini.ts`，加测试
2. **接入 agent-context-store** — 实现 `HindsightStore` 接口，用 SQLite 持久化
3. **集成 OpenClaw agent 循环** — 在 agent step 后自动调用 `detectFailures()`，失败时触发反思
4. **Benchmark** — 用 AgentHER 的 WebArena 指标思路，在 OpenClaw 内部任务上测量反思前后的成功率差

---

## 参考文献

- **AgentHER**: arXiv:2603.21357 — HER for LLM Agent Trajectory Relabeling (2026)
- **Reflexion**: Shinn et al., 2023 — Verbal reinforcement via self-reflection
- **SE-Agent**: arXiv:2508.02085 — Self-Evolution Trajectory Optimization
- **HiR**: Hindsight Instruction Replay — instruction-level relabeling (Zhang et al., 2025)
- **ASE 2025 Trajectory Study** — Thought-Action-Result trajectory analysis
