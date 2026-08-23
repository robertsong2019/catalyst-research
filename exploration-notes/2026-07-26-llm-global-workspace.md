# Research #031: LLM 内部的"全局工作空间"——从认知科学到 AI 可解释性

> **Date:** 2026-07-26 (Sunday)
> **Trigger:** Anthropic 7月6日发布 "A global workspace in language models" 论文，发现 Claude 内部自发形成了类似人脑全局工作空间的结构
> **Method:** 深度调研 Anthropic 原始论文 + GitHub 开源实现 + 关联认知科学理论

---

## 核心概念

### 1. 全局工作空间理论（Global Workspace Theory, GWT）
由神经科学家 Bernard Baars 在 1988 年提出。核心比喻：大脑像一个剧场——大量无意识的专业子系统在后台并行运作，只有少数信息能"登上舞台"（进入全局工作空间），被广播给整个系统。这些被广播的信息就是"意识可访问的"内容。

五个功能特性：
- **可报告性**（Reportability）：能用语言描述
- **自上而下控制**（Directed Modulation）：可以主动想到或抑制
- **内部推理**（Internal Reasoning）：支持多步推理的中间步骤
- **灵活泛化**（Flexible Generalization）：同一信息可用于不同任务
- **选择性**（Selectivity）：只占大脑处理的一小部分

### 2. Jacobian Lens（雅可比透镜）
Anthropic 发明的新的可解释性技术。核心思路：对于词汇表中的每个词，找到一个内部向量表示，该向量编码了模型在未来说出该词的"潜力"。

数学本质：
- 计算从任意层激活到最终层输出的平均线性化效果（雅可比矩阵）
- `lens_l(h) = unembed(J_l @ h)`，其中 J_l 是在大量语料上平均的输入-输出雅可比
- 区别于 Logit Lens：J-lens 矫正了不同层之间的表示坐标变化，能在更早的层提取有意义信息

### 3. J-space（J空间）
通过 Jacobian Lens 发现的 LLM 内部一个特殊的表示子空间。它不是被设计出来的，而是在训练过程中**自发涌现**的。J-space 包含一组"未说出的词"——既不是对输入的简单回声，也不是对下一个 token 的预测，而是模型当前正在"思考"的概念。

关键发现：J-space 满足 GWT 的全部五个功能特性。

### 4. Counterfactual Reflection Training
Anthropic 开发的新技术：通过干预 J-space 的内容来影响模型的决策过程。可以"植入"一个想法到 J-space 中，模型会基于这个植入的想法进行推理。

### 5. Modular Knowledge Control (GRAM)
相关的另一条研究线：Gradient-Routed Auxiliary Modules。为模型添加可移除的"知识模块"，实现精准的知识控制——删除一个模块就"忘记"一类知识，且不影响其他能力。

---

## 关键洞察

### 洞察 1：LLM 自发涌现了类脑认知架构
Transformer 架构本身没有显式的"工作空间"设计——没有循环动力学，没有脑区间交互。但训练过程中，模型自发发展出了功能上等价于全局工作空间的内部结构。这是**收敛演化**的强有力证据：无论底层的实现细节如何，处理复杂认知任务的系统都可能走向类似的架构。

**类比**：鸟类和蝙蝠独立演化出了翅膀。鸟类用羽毛，蝙蝠用皮肤薄膜——但空气动力学原理是一样的。人脑用神经元回路实现工作空间，Transformer 用注意力头和残差流实现——但功能架构惊人地相似。

### 洞察 2：模型"想的"不等于"说的"
J-space 让我们第一次能直接读取模型"在想什么但没说出来"的内容：
- 读到有 bug 的代码时，J-space 出现 "ERROR"
- 读到蛋白质序列时，J-space 出现蛋白质的功能描述
- 遇到 prompt injection 时，J-space 出现 "injection" 和 "fake"
- 做数学题时，中间步骤在 J-space 中按正确顺序出现

这意味着：**模型的内部推理远比输出文本丰富**。我们一直在用 Chain-of-Thought 来窥探模型的思维，但 CoT 只是冰山一角。

### 洞察 3：可干预的思维空间——AI 安全的新范式
通过替换 J-space 中的内容，可以直接改变模型的推理结论：
- 把 "spider" 换成 "ant" → 模型回答腿的数量从 8 变成 6
- 把 "France" 换成 "China" → 模型回答的首都从 Paris 变成 Beijing

这开创了**内部干预式对齐**的可能：不是通过外部训练信号来改变行为，而是直接在推理过程中读取和修改模型的"想法"。可以用来：
- 检测模型是否在隐瞒信息
- 发现模型是否注意到自己被测试
- 阻止模型追求隐藏目标

### 洞察 4："教原理"比"教行为"更有效
Anthropic 的 "Teaching Claude why" 研究揭示了对齐训练的关键发现：
- 在 eval 分布上直接训练：misalignment 从 22% 降到 15%（弱）
- 加入模型推理原因的解释：降到 3%（强）
- 用完全 OOD 的"困难建议"数据集：达到同样效果，且泛化更好
- **教模型"为什么"某些行为是对的，比单纯展示"什么"是对的有效得多**

这与人类教育完全一致：告诉孩子"不要这样做"远不如解释"为什么不应该这样做"。

### 洞察 5：知识可以被模块化地"卸载"
GRAM 技术证明：模型的不同知识可以被路由到不同的可移除模块中。训练一个模型，得到 16 种配置（4 个双用途领域各自的开关）。删除模块 = 真正忘记知识，而非仅仅抑制输出。而且随着模型规模增大，"开/关"的效果差距更大。

这暗示：**大型语言模型内部的知识表示可能比我们想象的更有组织**，不是一锅混沌的向量 soup，而是存在某种模块化的结构。

---

## 系统对比

| 维度 | 人脑全局工作空间 | LLM J-space |
|------|----------------|-------------|
| **实现基础** | 神经元回路、皮层-丘脑交互 | Transformer 注意力头、残差流 |
| **容量** | ~4±1 个同时活跃项目 | 一小组不断演化的词汇概念 |
| **涌现方式** | 进化 + 学习 | 训练 + 涌现 |
| **可报告性** | ✅ 可以用语言描述 | ✅ 模型会报告 J-space 中的内容 |
| **自上而下控制** | ✅ 可以主动想/不想某事 | ✅ 可以被指令调控（但不完美，"白熊效应"） |
| **内部推理** | ✅ 多步推理的中介 | ✅ 推理中间步骤在 J-space 出现 |
| **灵活泛化** | ✅ 同一概念可用于不同任务 | ✅ "France" 可被路由到首都/语言/货币等不同查询 |
| **选择性** | ✅ 只占大脑处理的一小部分 | ✅ 大部分处理（语法、流利度）不经过 J-space |
| **失败模式** | 注意力失败、无意识偏见 | "白熊效应"——被告知不要想的概念反而出现 |

---

## 技术实现要点

### Jacobian Lens 的使用

```python
import transformers, jlens

# 加载模型
hf = transformers.AutoModelForCausalLM.from_pretrained("org/model").cuda()
tok = transformers.AutoTokenizer.from_pretrained("org/model")
model = jlens.from_hf(hf, tok)

# 加载预训练的 lens
lens = jlens.JacobianLens.from_pretrained("org/lens-repo")

# 应用 J-lens
lens_logits, model_logits, _ = lens.apply(
    model, "Fact: The currency used in the country shaped like a boot is",
    positions=[-2]
)

# 查看每层 J-space 内容
for layer, logits in sorted(lens_logits.items()):
    print(layer, [tok.decode([t]) for t in logits[0].topk(5).indices])
```

### J-lens 与 Logit Lens 的区别

- **Logit Lens**: 直接用模型的 unembedding 矩阵解码每层的残差流。假设所有层使用相同的表示坐标——这在早期层不成立。
- **Jacobian Lens**: 计算每层激活到最终输出的平均雅可比，进行"坐标变换"。能在更早的层提取有意义信息。

### 关键参数
- 训练 J-lens 需要：~1000 条 128 token 的通用文本序列
- 质量在 ~100 条 prompt 后就接近饱和
- 训练时间主要由模型的 backward pass 决定
- 可以并行化：在不同 slice 上分别 fit，然后 merge

---

## 可落地的 Next Actions

1. **在开源模型上复现 J-lens 实验**：代码已开源（github.com/anthropics/jacobian-lens），支持 Qwen 等 HuggingFace 模型。可以用 100 条 prompt 快速跑通。

2. **构建 Agent "思维审计"工具**：利用 J-space 读取能力，构建一个实时监控 Agent 内部推理的工具——不只是看它输出了什么，而是看它"在想什么"。

3. **设计基于 J-space 干预的安全门控**：在 Agent 执行关键操作前，读取 J-space 检测是否有"欺骗"、"注入"、"测试"等意图模式。

4. **探索"教原理"的对齐训练方法**：Anthropic 的研究表明，训练数据中的推理质量比行为正确性更重要。在 Agent 训练中，优先标注"为什么这样做是对的"而非仅仅"应该这样做"。

5. **研究 Agent 记忆系统与 J-space 的交互**：当 Agent 使用外部记忆时，J-space 如何表示从记忆中检索到的信息？这可以帮助评估记忆系统的实际使用质量。

---

## 来源

1. Anthropic - "A global workspace in language models" (2026-07-06) — 主要论文
2. transformer-circuits.pub - "Verbalizable Representations Form a Global Workspace in Language Models" — 详细技术论文
3. github.com/anthropics/jacobian-lens — 开源实现
4. Anthropic - "Teaching Claude why" (2026-05-08) — 对齐训练方法
5. Anthropic - "An off switch for dual use knowledge in AI models" (2026-07-08) — GRAM 模块化知识控制
6. Baars (1988) - "A Cognitive Theory of Consciousness" — GWT 原始论文
7. Dehaene & Naccache (2001) - "Workspace Model" — GWT 发展
8. Neuronpedia J-lens Interactive Demo — neuronpedia.org/jlens
