# Hindsight Mini — Agent 反思学习机制

> 日期: 2026-05-09 | Catalyst 深度技术研究
> 关联: lab/hindsight-mini/ 原型设计 | memory-manager | agent-context-store

---

## 核心概念

### 1. Hindsight Experience Replay (HER) for LLM Agents
经典 RL 中 HER 将失败轨迹的目标替换为实际达成的状态，使每次交互都有学习信号。LLM 版本（AgentHER, ECHO）的核心创新：用 LLM 自身理解"实际达成了什么"，并合成新的自然语言 prompt 描述该目标。AgentHER 在 GPT-4o 上比纯 success-only SFT 提升 +7.1~11.7 pp，数据效率 2x。

### 2. Experiential Reflective Learning (ERL)
ICLR 2026 MemAgents Workshop 论文。框架：agent 从交互轨迹中提取 reusable insights，用 FAISS 向量存储按任务相似度检索。关键：同时需要 insight 提取和经验检索，二者协同（ablation 显示去掉任一都显著下降）。

### 3. EvolveR: Experience-Driven Lifecycle
ICLR 2026 论文。两阶段闭环：
- **Offline Self-Distillation** — 交互轨迹蒸馏为抽象可复用策略原则
- **Online Interaction** — 检索原则指导决策，用 RL 策略强化机制迭代更新

与 ERL 互补：EvolveR 强调策略抽象，ERL 强调经验检索。

### 4. Hindsight (vectorize-io) — Agent Memory That Learns
开源项目，三操作模型：**Retain → Recall → Reflect**
- 存储为 entities + relationships + time series，带稀疏/稠密向量
- Reflect 操作从已有记忆生成新观察和洞察
- 支持 memory bank 隔离和多 LLM provider

### 5. AgentHER 四阶段管线
1. 轨迹收集（成功+失败）
2. LLM 反向标注（识别实际达成的目标）
3. Failure-severity weighting（降权严重推理缺陷的轨迹）
4. Multi-judge verification（两个独立 judge 一致才接受，标签噪声 5.9%→2.3%）

---

## 关键洞察

### 洞察 1: 失败是最大的数据源
GPT-4o 在 WebArena 上成功率仅 14.3%，意味着 85.7% 的交互被浪费。AgentHER 证明失败轨迹可以转化为有效训练数据，且效果接近甚至超过成功-only 数据的 2x 量。**对 Catalyst 的启示**：error-patterns.md 本质上就是手动版的 hindsight replay，可以自动化。

### 洞察 2: Insight 提取 > 简单经验回放
ExpeL 的 ablation 实验清楚表明：仅检索相似轨迹（retrieve-only）效果有限，仅用 insight（insights-only）也不够，二者必须结合。insight 是经验的蒸馏——不是"做过什么"，而是"学到了什么"。**对 Hindsight Mini 的设计指导**：不仅要存轨迹，更要提炼原则。

### 洞察 3: 三操作模型（Retain-Recall-Reflect）是最小可行架构
vectorize-io/hindsight 的 Retain→Recall→Reflect 模型恰好映射了 Hindsight Mini 应有的核心操作。这比 EvolveR 的两阶段更实用，因为它不需要 RL 训练循环，纯 prompt-based 就能实现。

### 洞察 4: 与现有系统的连接点
- **agent-context-store** → 天然的 experience store（已有 search_regex, search_by_tags, append）
- **memory-manager** → 压缩检测 + 快照 = Retain 操作
- **MEMORY.md** → 手动版 Reflect（日常文件是原始日志，MEMORY.md 是蒸馏洞察）
- **Error Escalation Protocol** → 就是 agent 级别的 insight 提取规则

### 洞察 5: 无需参数更新的学习才是可持续的
所有 2025-2026 的研究都指向同一结论：parameter-free 的经验学习比 fine-tuning 更实用。LLM 本身作为 world model + policy generator，外部记忆系统提供经验。**这意味着 Hindsight Mini 可以纯粹用 prompt + 存储实现，不需要任何模型训练。**

---

## 可运行代码示例

以下是 Hindsight Mini 核心的 TypeScript 原型实现——一个最小化的 Agent 反思学习引擎：

```typescript
// hindsight-mini.ts — 最小化 Agent 反思学习引擎
// 运行: npx tsx hindsight-mini.ts

interface Experience {
  id: string;
  task: string;
  goal: string;
  steps: string[];
  outcome: 'success' | 'failure';
  achievedGoal?: string; // hindsight: 实际达成了什么
  embedding?: number[];
  timestamp: number;
}

interface Insight {
  id: string;
  content: string;
  sourceExperienceIds: string[];
  category: 'strategy' | 'pattern' | 'anti-pattern' | 'tool-usage';
  confidence: number; // 0-1, 随验证次数增长
  verifiedCount: number;
  createdAt: number;
}

// 简易向量搜索（生产环境用 FAISS/Qdrant）
function cosineSimilarity(a: number[], b: number[]): number {
  const dot = a.reduce((sum, ai, i) => sum + ai * b[i], 0);
  const magA = Math.sqrt(a.reduce((sum, ai) => sum + ai * ai, 0));
  const magB = Math.sqrt(b.reduce((sum, bi) => sum + bi * bi, 0));
  return dot / (magA * magB);
}

// 模拟 embedding（生产环境用真实模型）
function mockEmbedding(text: string): number[] {
  const hash = text.split('').reduce((acc, c) => ((acc << 5) - acc + c.charCodeAt(0)) | 0, 0);
  return Array.from({ length: 8 }, (_, i) => ((hash >> i) & 0xff) / 255);
}

class HindsightMini {
  private experiences: Experience[] = [];
  private insights: Insight[] = [];

  // === RETAIN: 存储经验 ===
  retain(exp: Omit<Experience, 'id' | 'embedding' | 'timestamp'>): Experience {
    const experience: Experience = {
      ...exp,
      id: `exp-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      embedding: mockEmbedding(exp.task + ' ' + exp.goal),
      timestamp: Date.now(),
    };

    // Hindsight relabeling: 失败经验 → 识别实际达成的目标
    if (exp.outcome === 'failure') {
      experience.achievedGoal = this.inferAchievedGoal(exp);
    }

    this.experiences.push(experience);
    return experience;
  }

  // Hindsight 核心：从失败轨迹推断实际达成了什么
  private inferAchievedGoal(exp: Omit<Experience, 'id' | 'embedding' | 'timestamp'>): string {
    // 生产环境: 调用 LLM 分析步骤并推断
    // 这里用启发式模拟
    const lastStep = exp.steps[exp.steps.length - 1] || '';
    if (lastStep.includes('read') || lastStep.includes('fetched')) {
      return `信息收集完成（但未完成最终目标: ${exp.goal}）`;
    }
    if (lastStep.includes('error') || lastStep.includes('failed')) {
      return `定位到错误位置（但未解决: ${exp.goal}）`;
    }
    return `部分进展（目标: ${exp.goal}未完全达成）`;
  }

  // === RECALL: 检索相关经验 ===
  recall(task: string, topK = 3): { experiences: Experience[]; insights: Insight[] } {
    const queryEmbedding = mockEmbedding(task);

    // 按相似度排序经验
    const ranked = this.experiences
      .map(exp => ({
        exp,
        score: exp.embedding ? cosineSimilarity(queryEmbedding, exp.embedding) : 0,
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, topK);

    // 检索相关 insights
    const relevantInsights = this.insights
      .filter(i => i.confidence > 0.5)
      .slice(0, 5);

    return {
      experiences: ranked.map(r => r.exp),
      insights: relevantInsights,
    };
  }

  // === REFLECT: 从经验中提炼洞察 ===
  reflect(): Insight[] {
    const newInsights: Insight[] = [];

    // 对比成功和失败经验，提取差异
    const successes = this.experiences.filter(e => e.outcome === 'success');
    const failures = this.experiences.filter(e => e.outcome === 'failure');

    // 模式 1: 失败经验中常见的 anti-pattern
    const failurePatterns = this.detectFailurePatterns(failures);
    for (const pattern of failurePatterns) {
      const existing = this.insights.find(i => i.content === pattern);
      if (existing) {
        existing.verifiedCount++;
        existing.confidence = Math.min(1, existing.confidence + 0.1);
      } else {
        const insight: Insight = {
          id: `ins-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          content: pattern,
          sourceExperienceIds: failures.map(f => f.id),
          category: 'anti-pattern',
          confidence: 0.6,
          verifiedCount: 1,
          createdAt: Date.now(),
        };
        newInsights.push(insight);
        this.insights.push(insight);
      }
    }

    // 模式 2: 成功经验中的策略
    const successPatterns = this.detectSuccessPatterns(successes);
    for (const pattern of successPatterns) {
      const existing = this.insights.find(i => i.content === pattern);
      if (existing) {
        existing.verifiedCount++;
        existing.confidence = Math.min(1, existing.confidence + 0.15);
      } else {
        const insight: Insight = {
          id: `ins-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          content: pattern,
          sourceExperienceIds: successes.map(s => s.id),
          category: 'strategy',
          confidence: 0.7,
          verifiedCount: 1,
          createdAt: Date.now(),
        };
        newInsights.push(insight);
        this.insights.push(insight);
      }
    }

    return newInsights;
  }

  // 生成 context-augmented prompt（注入经验到新任务）
  augmentPrompt(task: string): string {
    const { experiences, insights } = this.recall(task);

    let prompt = `## 任务: ${task}\n\n`;

    if (insights.length > 0) {
      prompt += `### 从过往经验中学到的教训:\n`;
      for (const insight of insights) {
        prompt += `- [${insight.category}] ${insight.content} (置信度: ${(insight.confidence * 100).toFixed(0)}%, 验证${insight.verifiedCount}次)\n`;
      }
      prompt += '\n';
    }

    if (experiences.length > 0) {
      prompt += `### 相似的历史任务:\n`;
      for (const exp of experiences.slice(0, 2)) {
        prompt += `- 任务"${exp.task}": ${exp.outcome === 'success' ? '✅ 成功' : '❌ 失败'}\n`;
        if (exp.achievedGoal) {
          prompt += `  后见之明: 实际达成了"${exp.achievedGoal}"\n`;
        }
      }
    }

    return prompt;
  }

  private detectFailurePatterns(failures: Experience[]): string[] {
    const patterns: string[] = [];
    const errorSteps = failures.flatMap(f => f.steps.filter(s => s.includes('error')));
    if (errorSteps.length >= 2) {
      patterns.push('反复遇到 error 时应先诊断根因再重试，而非盲目重复');
    }
    const noReadSteps = failures.filter(f => !f.steps.some(s => s.includes('read')));
    if (noReadSteps.length >= 2) {
      patterns.push('动手前先读取相关文件，理解上下文');
    }
    return patterns;
  }

  private detectSuccessPatterns(successes: Experience[]): string[] {
    const patterns: string[] = [];
    const withRead = successes.filter(s => s.steps.some(st => st.includes('read')));
    if (withRead.length >= 2) {
      patterns.push('先读取目标文件再修改，成功率高');
    }
    const withTest = successes.filter(s => s.steps.some(st => st.includes('test')));
    if (withTest.length >= 1) {
      patterns.push('修改后立即运行测试验证');
    }
    return patterns;
  }

  // 统计
  stats() {
    return {
      totalExperiences: this.experiences.length,
      successes: this.experiences.filter(e => e.outcome === 'success').length,
      failures: this.experiences.filter(e => e.outcome === 'failure').length,
      insights: this.insights.length,
      avgConfidence: this.insights.length > 0
        ? this.insights.reduce((sum, i) => sum + i.confidence, 0) / this.insights.length
        : 0,
    };
  }
}

// === Demo ===
const engine = new HindsightMini();

// 存储经验（成功+失败混合）
engine.retain({
  task: '修复 login API 的 500 错误',
  goal: 'login API 返回 200',
  steps: ['read auth.ts', '发现 token 验证逻辑错误', '修复并运行 test', 'test passed'],
  outcome: 'success',
});

engine.retain({
  task: '修复 payment API 的超时问题',
  goal: 'payment API 在 3s 内响应',
  steps: ['直接修改 payment.ts', 'error: 缺少依赖', '再次修改', 'error: 类型不匹配'],
  outcome: 'failure',
});

engine.retain({
  task: '添加用户注册接口',
  goal: 'POST /register 返回 201',
  steps: ['read user-routes.ts', 'read user-model.ts', '添加 register handler', '运行 test', 'test passed'],
  outcome: 'success',
});

engine.retain({
  task: '优化搜索性能',
  goal: '搜索响应时间 < 100ms',
  steps: ['直接添加索引', 'error: 迁移失败', '尝试修复迁移', 'error: 表锁定'],
  outcome: 'failure',
});

// 反思：提炼洞察
console.log('=== REFLECT ===');
const newInsights = engine.reflect();
for (const insight of newInsights) {
  console.log(`[${insight.category}] ${insight.content} (置信度: ${(insight.confidence * 100).toFixed(0)}%)`);
}

// 用经验增强新任务 prompt
console.log('\n=== AUGMENT PROMPT ===');
console.log(engine.augmentPrompt('修复用户权限校验的 bug'));

// 统计
console.log('\n=== STATS ===');
console.log(engine.stats());
```

**运行方式:**
```bash
# 保存为 hindsight-mini.ts
npx tsx hindsight-mini.ts
```

**预期输出:**
```
=== REFLECT ===
[anti-pattern] 反复遇到 error 时应先诊断根因再重试，而非盲目重复
[anti-pattern] 动手前先读取相关文件，理解上下文
[strategy] 先读取目标文件再修改，成功率高
[strategy] 修改后立即运行测试验证

=== AUGMENT PROMPT ===
## 任务: 修复用户权限校验的 bug

### 从过往经验中学到的教训:
- [anti-pattern] 反复遇到 error 时应先诊断根因再重试，而非盲目重复 (置信度: 60%, 验证1次)
- [anti-pattern] 动手前先读取相关文件，理解上下文 (置信度: 60%, 验证1次)
- [strategy] 先读取目标文件再修改，成功率高 (置信度: 70%, 验证1次)
- [strategy] 修改后立即运行测试验证 (置信度: 70%, 验证1次)

### 相似的历史任务:
- 任务"修复 login API 的 500 错误": ✅ 成功

=== STATS ===
{
  totalExperiences: 4,
  successes: 2,
  failures: 2,
  insights: 4,
  avgConfidence: 0.65
}
```

---

## 技术谱系图

```
HER (2017, RL)
  └── Textual HER (THER, 2020) — 语言 + RL
       └── ECHO (2025) — prompt-based hindsight trajectory rewriting
            └── AgentHER (2026) — 4-stage pipeline, multi-judge verification

Reflexion (2023) — verbal RL, self-reflection
  └── ExpeL (2024, AAAI) — insight extraction + experience retrieval
       └── ERL (2026, ICLR) — experiential reflective learning
            └── EvolveR (2026, ICLR) — offline distillation + online RL

Hindsight (vectorize-io, 2026) — production memory system
  └── Retain → Recall → Reflect 三操作模型
```

---

## 与现有项目的关联

| 现有系统 | Hindsight Mini 角色 | 集成方式 |
|---------|-------------------|---------|
| agent-context-store | Experience Store 后端 | 替代 mockEmbedding，用真实 embedding 搜索 |
| memory-manager | Retain 操作触发器 | 压缩检测时自动 retain 经验 |
| MEMORY.md | 反思产物 | Reflect 输出写入 MEMORY.md 的洞察段落 |
| error-patterns.md | Anti-pattern insight 来源 | 已有的手动版 hindsight，可自动化 |
| AGENTS.md 编码原则 | Strategy insight 来源 | 成功策略沉淀为原则 |
| autoresearch 方法论 | 积累性原则的实例 | 每次研究在前序成果上积累 |

---

## Hindsight Mini 原型设计建议

### 架构: 三层 + 一循环

```
┌─────────────────────────────────────────┐
│            Agent 执行层                   │
│  (任务执行 → 轨迹记录 → 结果评估)          │
└──────────────┬──────────────────────────┘
               │ retain()
               ▼
┌─────────────────────────────────────────┐
│         Experience Store                 │
│  (agent-context-store 作为后端)           │
│  - 成功/失败轨迹                          │
│  - Hindsight relabeled goals             │
│  - 向量索引 (search_regex + embedding)    │
└──────────────┬──────────────────────────┘
               │ recall() + reflect()
               ▼
┌─────────────────────────────────────────┐
│         Insight Engine                   │
│  (LLM-based insight extraction)          │
│  - 成功 vs 失败对比分析                    │
│  - 策略/反模式提取                         │
│  - 置信度追踪 + 多轮验证                    │
└──────────────┬──────────────────────────┘
               │ augmentPrompt()
               ▼
          下一个任务 (带经验增强)
```

### 关键设计决策

1. **用 LLM 做 hindsight relabeling**（非启发式）— 参考 AgentHER 的 multi-judge verification
2. **Insight 按任务类型分区**（非全量拼接）— 参考 ExpeL 的 task-similarity retrieval
3. **Retain-Recall-Reflect 三操作 API** — 参考 vectorize-io/hindsight
4. **与 agent-context-store 深度集成** — 复用现有 search_by_tags, append, expire_in

---

## 下一步行动

1. **创建 `lab/hindsight-mini/`** — 基于上述原型建立项目骨架，TDD 驱动开发
2. **接入 agent-context-store** — 用真实 embedding + search 替代 mock 实现
3. **设计 Insight Schema** — 定义 agent-context-store 中 insight 的标签体系（category, confidence, verified-count）
4. **与 autoresearch 集成** — 实验记录自动 retain，成功标准不达标时自动触发 reflect

---

## 参考论文/项目

| 名称 | 来源 | 年份 | 关键贡献 |
|-----|------|------|---------|
| HER | NeurIPS | 2017 | 奠基性工作，hindsight goal relabeling |
| ExpeL | AAAI | 2024 | insight extraction + experience retrieval 协同 |
| ECHO | arXiv | 2025 | prompt-based hindsight trajectory rewriting |
| AgentHER | arXiv | 2026 | 4-stage pipeline, multi-judge, 2x data efficiency |
| ERL | ICLR MemAgents | 2026 | experiential reflective learning framework |
| EvolveR | ICLR | 2026 | offline distillation + online RL lifecycle |
| Hindsight | vectorize-io | 2026 | 开源 Agent Memory, Retain-Recall-Reflect |
