# 代码即动作：从函数调用到自主编程的 Agent 进化史

**日期:** 2026-07-10
**主题:** AI Agent 的行动空间从 JSON 调用进化到代码执行再到编程式编排
**触发:** GPT-5.6 发布 Programmatic Tool Calling + Multi-Agent Ultra 模式

---

## 核心概念 (5个)

### 1. 行动空间 (Action Space)
Agent 能执行的所有操作的集合。从受限的预定义函数列表 → 任意可编程操作。
- JSON Tool Calling: `{tool: "search", args: {query: "..."}}` — 受限、原子化
- Code Action: `results = [search(q) for q in queries]; filter(results)` — 可组合、可迭代

### 2. 程序式工具调用 (Programmatic Tool Calling)
GPT-5.6 引入的能力：模型生成 JavaScript 代码，在隔离的 V8 沙箱中运行，编排多个工具的调用。模型不再"逐个请求"工具，而是"编写程序"来协调工具链。

### 3. 代码技能库 (Code Skill Library)
源自 Voyager 的概念：Agent 将成功的行为保存为可复用的代码函数，形成不断增长的"技能库"。后续任务可以检索和组合已有技能。

### 4. Agent-Computer Interface (ACI)
SWE-Agent 提出的概念：就像人类需要 IDE 一样，Agent 需要专门设计的计算机交互界面。ACI 的设计质量直接决定 Agent 的表现。

### 5. 推理时并行 (Inference-Time Parallelism)
GPT-5.6 Ultra 模式的核心：在推理时协调多个 Agent 并行处理子任务，用更多 token 换取更短延迟和更强结果。这是推理时规模定律的新维度。

---

## 关键系统/论文 (12个)

### 阶段一：文本动作 (2022-2023)

| 系统 | 年份 | 核心贡献 |
|------|------|---------|
| **ReAct** (Yao et al.) | 2022.10 | Reasoning + Acting 范式，LLM 交替输出推理和文本动作 |
| **Toolformer** (Schick et al.) | 2023.02 | LLM 自主学习何时调用外部 API |
| **MM-REACT** (Microsoft) | 2023.03 | 扩展 ReAct 到多模态，文本提示编排视觉专家 |

### 阶段二：代码即动作 (2023-2024)

| 系统 | 年份 | 核心贡献 |
|------|------|---------|
| **Voyager** (NVIDIA/GPT-4) | 2023.05 | Minecraft 中的终身学习 Agent，用可执行代码构建技能库 |
| **LATM** (Cai et al.) | 2023.05 | LLM 作为工具制造者：强大模型造工具，轻量模型用工具 |
| **Eureka** (NVIDIA) | 2023.10 | GPT-4 生成奖励函数代码，83% 任务超越人类专家设计 |
| **CodeAct** (Wang et al.) | 2024.02 (ICML) | 系统验证：可执行 Python 代码作为统一行动空间，成功率提升 20% |
| **OpenCodeInterpreter** | 2024.02 | 开源版 Code Interpreter，68K 多轮交互数据集 |

### 阶段三：Agent 原生界面 (2024-2025)

| 系统 | 年份 | 核心贡献 |
|------|------|---------|
| **SWE-Agent** (Princeton) | 2024.05 | Agent-Computer Interface (ACI)，为 Agent 专门设计的开发环境 |
| **SmolAgents** (HuggingFace) | 2025.01 | 极简代码 Agent 框架，Agent 直接写 Python 代码作为 action |

### 阶段四：编程式编排 + 多Agent (2026)

| 系统 | 年份 | 核心贡献 |
|------|------|---------|
| **GPT-5.6 Programmatic Tool Calling** | 2026.07 | 模型写 JavaScript 编排工具链，隔离 V8 沙箱，ZDR 兼容 |
| **GPT-5.6 Multi-Agent Ultra** | 2026.07 | 默认 4 Agent 并行，最多 16 Agent，推理时规模扩展 |

---

## 关键洞察 (5条)

### 洞察 1：代码是天然的"统一行动空间"
JSON/文本格式的工具调用有三个根本限制：(1) 无法组合（每次只能调一个工具）；(2) 无法迭代（不能循环/条件判断）；(3) 无法携带状态（中间结果需要模型反复记忆）。

代码天然解决了这些问题：`result = tool_a(x); if result.ok: return tool_b(result.data)`。CodeAct 论文用 17 个模型的消融实验证明，代码行动比 JSON 行动的成功率高出最多 20%。

**为什么不是一开始就用代码？** 因为早期 LLM 的代码生成不够可靠。随着模型能力提升，这个限制已经基本消失。

### 洞察 2：从"工具使用者"到"工具制造者"是质变
LATM 和 Voyager 代表了一个重要转变：Agent 不只是调用预定义工具，而是**创造新工具**。Voyager 在 Minecraft 中自动发现并代码化了数百个可复用技能；LATM 让 GPT-4 为一类任务制造工具，然后 GPT-3.5 就能用这些工具达到 GPT-4 水平。

这意味着 Agent 的能力是**递增的**——今天解决过的问题，明天变成一个函数调用。

### 洞察 3：Agent-Computer Interface 是隐藏的乘数
SWE-Agent 的发现令人惊讶：仅仅改变 Agent 与计算机交互的界面设计，就能让 pass@1 从 2% 跳到 12.5%。这就像给人类工程师从记事本换到 IDE——同样的智能水平，6倍效率差异。

GPT-5.6 的设计判断能力（"inspect and refine the rendered result"）本质上就是一种高级 ACI——模型不只生成代码，还能"看到"渲染结果并修正。

### 洞察 4：推理时并行是新维度
GPT-5.6 Ultra 模式展示了推理时规模定律的新方向：不是让一个模型想更久（reasoning），而是让多个 Agent 并行工作。BrowseComp 和 SEC-Bench Pro 的结果显示，4 Agent 并行比 1 Agent 不仅更快，而且更准。

这暗示了一个深刻的事实：**复杂任务的瓶颈不是推理深度，而是探索广度**。

### 洞察 5：安全边界需要重新设计
当模型从"调用预定义函数"变成"编写任意代码"时，安全模型完全改变了：
- JSON 调用：验证参数即可
- 代码执行：需要沙箱、权限隔离、输出过滤

GPT-5.6 的方案（隔离 V8、无网络/文件系统/子进程、ZDR 兼容）是当前最成熟的设计。但开源 Agent 框架（SmolAgents 等）仍在使用 `exec()` 直接运行模型生成的代码，这是巨大的安全债务。

---

## 可落地 Next Actions

1. **短期（1-2周）:** 将当前项目的 Agent 工具调用从 JSON 格式迁移到代码格式。用 Python `eval()` + 白名单模块的方式开始，不需要完整沙箱。
2. **中期（1-2月）:** 为 Agent 实现技能库机制：成功完成的任务自动保存为可复用函数，新任务可以检索和组合已有技能。
3. **长期（3-6月）** 探索多 Agent 并行模式：将复杂任务分解为子任务，多个 Agent 并行处理，一个协调 Agent 汇总结果。
4. **安全:** 如果运行模型生成的代码，必须使用沙箱（Docker/firejail/E2B）。永远不要直接 `exec()` 模型输出。
5. **学习资源:**
   - 精读 CodeAct 论文 (arXiv:2402.01030)
   - 精读 SWE-Agent 论文 (arXiv:2405.15793)
   - 跑通 SmolAgents 的 CodeAgent 示例
   - 体验 GPT-5.6 的 Programmatic Tool Calling API

---

## 时间线总结

```
2022.10  ReAct — 文本推理 + 文本动作
    ↓
2023.05  Voyager — 代码技能库 + 终身学习
         LATM — LLM 作为工具制造者
    ↓
2023.10  Eureka — 代码生成超越人类专家
    ↓
2024.02  CodeAct — 代码作为统一行动空间 (ICML)
         OpenCodeInterpreter — 开源 Code Interpreter
    ↓
2024.05  SWE-Agent — Agent-Computer Interface
    ↓
2025.01  SmolAgents — 极简代码 Agent 框架
    ↓
2026.07  GPT-5.6 — 程序式工具编排 + 多 Agent 并行
```

---

*研究完成于 2026-07-10 20:25 CST*
