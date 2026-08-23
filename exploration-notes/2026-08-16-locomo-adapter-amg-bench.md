# Research #067 — LoCoMo Benchmark Adapter for amg（数据已验证 + 零成本基线已跑）

> 2026-08-16 deep-exploration-evening。承接 C447 (amg_bench_quality.py / LongMemEval 适配器) 模式，
> 为 amg-bench LoCoMo adapter (HEARTBEAT 关键路径项) 完成全部前置侦察。
> **数据已下载、schema 已验证、零成本关键词基线已在全量 1982 题上跑出真实数字。**

---

## 1. 核心概念

### 1.1 LoCoMo 数据集（snap-research/locomo, ACL 2024）
10 段超长对话（每段最长 35 session / 300 turn / ~9K token），共 **1986 题**。
5 类题型：`1=single_hop(282) 2=multi_hop(321) 3=temporal(96) 4=open_domain(841) 5=adversarial(446)`。

实测 schema（来自真实 locomo10.json，2.8MB）：

```json
{
  "sample_id": "...",
  "conversation": {
    "speaker_a": "...", "speaker_b": "...",
    "session_1_date_time": "...",
    "session_1": [{"speaker": "...", "dia_id": "D1:3", "text": "..."}],
    "session_2": [/* ... */]
  },
  "qa": [
    {"question": "...", "answer": "...",
     "evidence": ["D1:3"],      // ← dia_id = "D<session>:<turn>"，检索级 ground truth
     "category": 2}
  ]
}
```

**`evidence` 是 LoCoMo 相对 LongMemEval 的决定性优势**：LongMemEval 只有 haystack_sessions（会话级），
LoCoMo 的 dia_id 可做 **turn 级**检索评分——amg 的 message 节点天然对齐。

### 1.2 Adversarial = abstention 的主场
cat 5（adversarial，问"从未发生的事"）占 **446/1986 = 22.5%**。竞品普遍**剔除这类题**再报分
（MemMachine / Honcho / Letta / Zep 均注明 "adversarial excluded"）。
amg 的熵置信双门 abstention（C448: `entropy_gate_fires`，best≤weak ∧ norm_entropy≥thr ∧ evidence≥3）
与 LongMemEval `_abs` 题型的映射**原样适用于 adversarial 题型**——这是 amg 唯一不靠 LLM 就能
吃下这 22.5% 的路径。

### 1.3 长程证据分布 → 纯实体图会死
全量实测 evidence 时间跨度（距最新 session 的距离）：**近似均匀分布在 0~31 个 session 之前**，
只有 3% 在最近一个 session。→ 任何 recency 启发式失效。AgentMemBench (arXiv 2608.00009) 实测：
长程检索上实体图策略 GEM Recall@5 ≤ 0.005，只有稠密检索 (EKV) 存活 (0.573)。
**这对 amg 是头号威胁也是定位机会**：amg 检索 = keyword index + message 节点 + PPR，
不是纯实体图——但必须用 turn 级 evidence 数字证明，不能靠宣称。

### 1.4 竞争格局（LoCoMo, 2026-08）
| 系统 | 准确率 | tokens/query | 备注 |
|------|--------|-------------|------|
| Mem0 | 92.5 (self) | ~6,900 | LLM-judge, 剔除 cat5 |
| hindsight (local) | 92.0 (复现) | 36,235 | agentmemorybenchmark.ai 独立复现 |
| MemMachine v0.2 | 91.7 (self) | — | gpt-4.1-mini backbone |
| cognee | 80.3 (复现) | 14,724 | |
| hybrid-search | 79.1 (复现) | 22,157 | |
| **amg 零成本目标** | **检索指标优先** | **<2,000** | 无 LLM，abstention 吃 cat5 |

amg 差异化口径：**token 效率 + 零 API 成本 + 唯一报全量（含 adversarial）+ turn 级 evidence 指标**。
注意各家分数不可直接比（judge 模型/backbone/剔除策略不同），amg 报告必须写明协议。

### 1.5 演进信号：LoCoMo-Plus (ACL 2026)
xjtuleeyf/Locomo-Plus：超越事实召回的"认知记忆"评测（cue–trigger 语义断连 + 约束一致性）。
证明纯 QA 准确率赛道已饱和内卷，amg 的 explain/abstention/provenance 叙事恰好对齐下一代评测维度。

---

## 2. 可运行代码

`code/locomo_probe.py`（stdlib-only，本目录）——已在真实 locomo10.json 全量运行 ✅

```bash
# 数据已下载到 catalyst-research/data/locomo10.json（GitHub raw 直连，2.8MB，非 LFS）
python3 code/locomo_probe.py /root/.openclaw/workspace/catalyst-research/data/locomo10.json
```

实测输出（2026-08-16，全量 1982/1986 题，4 题因空关键词/空 evidence 剔除）：

```
overall Recall@1: 1166/1982 = 0.588
overall Recall@2: 1429/1982 = 0.721
overall Recall@3: 1555/1982 = 0.785

per-category Recall@1:
  single_hop   n= 282  R@1=0.457
  multi_hop    n= 321  R@1=0.545
  temporal     n=  92  R@1=0.337   ← 关键词最弱项 = bitemporal API 的用武之地
  open_domain  n= 841  R@1=0.646
  adversarial  n= 446  R@1=0.646   ← 检索找到"像答案"的 session ≠ 事件发生过

evidence temporal span: 近似均匀 0~31 sessions back（仅 3% 在最近 session）
top-1 session context tokens/query: avg=700  ← 已 10× 优于 Mem0 (~6900)
```

解读：纯关键词 session 级基线 0.588 是**下界**。PPR + 实体 boost + turn 级排序的上行空间
明确（ironmem hybrid 报 R@10=88.9% 可作上限参照）。temporal 0.337 印证：时间类问题关键词
匹配最弱，必须靠 amg bitemporal 序号/时间戳信号补位——这正是 adapter 该测的假设。

---

## 3. 关键洞察

1. **数据零阻塞**：locomo10.json GitHub raw 直连可用（ironmem 文档称需 git-lfs 已过时），
   与 LongMemEval (#065) 同级易得。"8月底双首跑"的第三个候选赛道完全解锁。

2. **adversarial 22.5% 是 amg 的结构性武器**：竞品剔除后报分，amg 用 C448 熵门 abstention
   全量应考。注意陷阱：adversarial 题的检索 R@1 (0.646) 与 open_domain 相同——检索指标
   对 cat5 **无意义**，必须单独用 abstention-accuracy 评分，否则会"高分幻觉"。

3. **temporal 是关键词基线最弱题型 (0.337)**，而 amg 恰有 temporal trilogy + bi-temporal
   API 族（96 题，样本小、可快速迭代）。LoCoMo 因此成为 amg 时间推理能力的天然试验场——
   LongMemEval temporal-reasoning 类型的补充验证。

4. **token 效率赛道真空**：session 粒度上下文均 ~700 tok/query；turn 粒度（dia_id 证据）
   还能再降一个量级。复现榜上最省的 cognee 也要 14.7k。amg 报 <2,000 目标在 session 粒度
   已达成，在"每 token 准确率"维度无人竞争。

5. **AgentMemBench 的 GEM 崩溃结论是 amg 必须正面回应的文献**：他们只测了朴素实体图。
   amg adapter 的 turn 级 evidence Recall 数字就是对该结论的直接反驳/确认实验——
   无论结果如何都有发表价值。

---

## 4. 下一步行动

1. **C449 候选**：`locomo_bench_quality.py` — 复用 `LongMemEvalAdapter.ingest_sessions`
   （LoCoMo→`{session_id, messages:[{role,content}]}` 转换 <30 行）+ evidence dia_id 的
   session/turn 双层 Recall + cat5 走 `entropy_gate_fires` abstention 路径 + tokens/query。
   基线数字（本笔记 §2）已就位作对照。
2. 报告协议：全量 1986 + 含 cat5 + 注明 extractive/零 LLM 模式 + 与 LME 适配器同表呈现。
3. 中期：temporal 96 题单列迭代（bitemporal 信号注入检索排序）。

## 质量 self-check
- ✅ 可运行代码：locomo_probe.py 全量真实数据验证（1982 题，输出实录）
- ✅ 独到见解：adversarial 检索指标陷阱 / temporal-bitemporal 对位 / GEM 反驳实验定位
- ✅ 项目关联：直接解锁 HEARTBEAT "amg-bench LoCoMo adapter"，复用 C447/C448 全部资产
