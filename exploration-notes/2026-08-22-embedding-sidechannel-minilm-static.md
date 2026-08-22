# Research #083 — 嵌入 side-channel：MiniLM/静态嵌入打通 preference 检索桥（选型判决 + 真实数据原型）

> 2026-08-22 20:19 deep-exploration-evening · autoresearch 方法论
> 主题：MEMORY Next「嵌入 side-channel（#080，all-MiniLM 可选依赖，仅 preference/ssa form）」
> 数据：/tmp/lme_s.json（277MB 全量）→ 86 题子集（preference-30 + ssa-56，3983 唯一会话，22002 chunks）
> 代码：`code/embed_extract86.py` + `code/embed_sidechannel_proto.py`（主原型）+ `code/embed_static_arm.py`（静态臂）
> 环境：1GB RAM CPU 盒（本机即目标部署环境的最坏情况）

---

## 1. 结论速览

**判决：#080 证明词法不可达的 preference 检索桥，被 384 维 MiniLM 嵌入在本机数据上直接打通（@5 0.60→0.87）；集成方式应为 form 切换而非 RRF 融合；速度敏感场景有 69× 快的静态嵌入备选，且两者都 torch-free。**

| 类目 | 臂 | hit@1 | hit@5 | 速度（本盒） |
|------|-----|-------|-------|--------------|
| preference-30 | 词法 token-overlap | 3/30 | 18/30 | ~ms |
| preference-30 | **MiniLM int8 ONNX** | **15/30** | **26/30** | 36 chunks/s（611s/22k） |
| preference-30 | 静态 potion-retrieval-32M | 11/30 | 22/30 | **2463 chunks/s（8.9s/22k）** |
| preference-30 | RRF 混合（lex+emb） | 10/30 | 26/30 | — |
| ssa-56 | 词法 | 49/56 | 56/56 | ~ms |
| ssa-56 | **MiniLM** | **56/56** | 56/56 | 同上 |
| ssa-56 | 静态 potion | 55/56 | 56/56 | 同上 |

- 外部证据（agentmemory：BM25 60% → +MiniLM 83% R@5）在本机协议上**复现且更强**（preference @5 60%→87%）。
- 语义真实性抽查 ✅："music store tips" ↔ gold="Fender Stratocaster vs Gibson Les Paul"——类别-实体鸿沟正是被弥合的对象，非表面词巧合。
- RRF 融合在 preference @1 上**有害**（10 < 15）：词法信号近乎随机时，融合把噪声注入排序。集成结论：**form-gated switch（preference→纯嵌入；ssa→词法已 49/56，嵌入做 @1 补齐），不做全局融合**——与 C473「form 分类器即配置面」哲学同构。

## 2. 选型对比（amg `[sidechannel]` 可选依赖视角）

| 维度 | fastembed + all-MiniLM-L6-v2 | model2vec + potion-retrieval-32M | sentence-transformers |
|------|------------------------------|----------------------------------|----------------------|
| 推理机制 | ONNX int8 神经前向 | **纯查表 + mean-pool（无前向）** | torch 神经前向 |
| 额外依赖 | onnxruntime 等（~100MB） | **numpy+safetensors+tokenizers（~30MB，无神经运行时）** | torch（本盒已装但 amg 不可假设） |
| 模型体积 | ~23MB int8 | ~130MB fp32 | ~90MB |
| 维度 | 384 | 512 | 384 |
| 本盒吞吐 | 36 chunks/s | **2463 chunks/s（69×）** | 慢于 fastembed（未测） |
| preference @1/@5 | **15/30 · 26/30（质量王）** | 11/30 · 22/30 | 未测（同源模型族） |
| 确定性 | ✅ 实测 bitwise（两次 embed 逐位相等） | ✅ 结构性（查表+pool 无浮点调度） | torch CPU 多线程有风险 |
| 静态检索 SOTA | — | static-retrieval-mrl-en-v1（HF 官方，≥85% 质量，1024d MRL）是备选 | — |

**推荐双档**：`amg[sidechannel-fast]`（model2vec，0.1s/题，离线近实时）与 `amg[sidechannel]`（fastembed，7.5s/题，质量上限）；运行时探测装了哪个用哪个（OTel 可选依赖先例）。

## 3. 协议与成本

- 检索单元 = session（48.3 会话/题均值）；文本 = turns 拼接；分块 150 词 × 最多 6 块（MiniLM 256 token 上下文），会话得分 = chunk-max 余弦。
- 每题边际成本：~270 chunks ≈ 7.5s（MiniLM）/ 0.11s（静态）。**写时嵌入**（FastAppendQueue/ingest 钩子）可摊销至查询零成本——amg 原生集成路径。
- 22k chunks 全量嵌入内存峰值 <400MB（模型+向量+数据），1GB 盒安全。

## 4. 事故记录：字母序 tie-break 伪影（第一跑）

第一跑把 turn 字典展开成 key 垃圾文本（`"role content role content…"`）→ 所有嵌入相同 → 排序退化为 sid 字典序 → **"嵌入臂 12/30 @1" 全是伪影**（`answer_*` sid 恰好字母序靠前）。暴露信号是词法臂 0/86 的反常（#080 arm B=11/30）。教训入 error-patterns：
1. **好得可疑的数字先查 tie-break**（全同分时 sorted 的第二键就是排序本身）；
2. 基准题解侧 id 前缀（`answer_*`）与语料 id（`ultrachat_*`/`sharegpt_*`）字母序可分 = tie-break 天然偏置，务必随机化第二键或确保分数连续；
3. 词法臂 0/86 的"诚实异常"救了整个结论——**每臂独立 sanity 数字是伪影检测器**。

## 5. 核心概念

1. **检索桥（retrieval bridge）**：从问题到证据会话的定位能力。#080 证明 preference 的词法桥 unique-best 仅 4/30；本篇证明嵌入桥 @5 26/30——桥的材质从"词形匹配"换成"语义邻近"后同一个缺口关闭。
2. **form-gated side-channel**：嵌入通道只在 preference/ssa form 触发（C473 form 分类器即配置面），主干保持零 LLM。与 RRF 全局融合相反——后者在词法弱 form 上被证明有害。
3. **静态嵌入（static embeddings）**：每 token 一个固定向量，句向量=查表均值池化，无神经前向。model2vec/Potion 族在 BEIR 上以 15-50× 小、500× 快换取 ~85% 质量；本实验 preference @1 差距 4 题（11 vs 15）。
4. **写时嵌入 vs 查询时嵌入**：会话向量在 ingest/FastAppendQueue 时算好存图（amg 有现成 embedding 存储位），查询时只剩一次 question embed + 矩阵乘——把 7.5s/题成本变成 0。
5. **双档可选依赖（profiled extras）**：`[sidechannel-fast]`（静态）/`[sidechannel]`（神经）运行时探测，质量与速度两个市场都不放弃——OTel telemetry 已验证的 amg 发布模式。

## 6. 代码

`code/embed_sidechannel_proto.py` —— 主原型（四臂：词法/嵌入/RRF/确定性，~3 分钟复现，模型首次下载 23MB）：

```python
# 核心：chunk-max 余弦——长会话切成 150 词块，会话得分 = max(块余弦)
vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12   # 归一化一次
sid_to_rows = {}                                                # sid -> chunk 行号
for i, sid in enumerate(keys):
    sid_to_rows.setdefault(sid, []).append(i)
...
sim = float(np.max(vecs[sid_to_rows[sid]] @ qv))               # 会话语义得分
# RRF 融合（被判有害的集成方式，保留作负结果）
score[sid] = score.get(sid, 0.0) + 1.0 / (RRF_K + r + 1)
```

运行：`python3 code/embed_extract86.py && python3 code/embed_sidechannel_proto.py`
（提取脚本先从 277MB 原始 JSON 落 86 题子集——1GB 盒上模型与全量数据不可同驻）

## 7. 关键洞察

1. **外部证据→自有数据复现是研究杠杆**：#080 只拿到 agentmemory 的 60→83% 外部数字，本篇用自家协议复现出 60→87%——C497+ 落地时不再依赖"别人的 benchmark 说嵌入有用"，而是"我们的 form 协议实测有用"。
2. **RRF 不是弱词法场景的默认答案**：融合的前提是两路信号都有区分度；词法 @1=3/30 时融合净损 -5 题。**集成方式应由各 form 的单臂基线决定**——这把"hybrid 检索最佳实践"精细化成了"per-form 集成决策"。
3. **速度-质量谱系两端都可部署**：69× 的速度差只换 4 题 @1——如果 amg 选写时嵌入 + 静态模型，查询路径完全零神经运行时、零延迟惩罚，仍拿到 11/30 @1（词法的 3.7 倍）。**"可选加速器"可以同时是"默认可用"**。
4. **tie-break 是隐藏的排序器**：全同分时 `sorted(key=(-score, sid))` 的 sid 就是唯一决定因素——基准数据 id 命名（answer_* 前缀）可以凭空造出 40% 的假命中率。任何"打平常见"的打分器都要审视第二键。
5. **答案侧仍是墙，但墙后移了**：#080 的三面墙（词法桥/echo 协议/答案重建）中本篇只推倒第一面；exact 分数不会因此自动上涨（GT 是合成元描述），但**喂给 LLM judge 的上下文从错误会话变成正确会话**——为 ollama 解锁后的 judge 实验铺平检索侧。

## 8. 下一步行动

1. **C498 候选（嵌入 side-channel 生产化）**：`amg_bench_quality.py` 加 form-gated 嵌入通道——preference/ssa form 触发、会话级 chunk-max 余弦、词法结果保留为无嵌入依赖回退；`import model2vec` 探测式（ImportError→跳过，与 OTel 先例一致）。预期：ssa evhit 0.929→~1.0、preference hit 0.567→~0.87；exact 不动（答案侧墙），honest-attribution 叙事 +1。
2. **写时嵌入路径**：FastAppendQueue/ingest_sessions 钩子存会话向量（FastAppendQueue 已有 lazy consolidation 语义），查询侧零摊销——第二 cycle 候选。
3. **ollama 联动实验**（解锁后）：正确会话 + LLM judge = preference exact 的真实测量（检索侧已就绪）；judge prompt 钉 hash（#080 纪律）。
4. **README 弹药**：`amg[sidechannel]` 双档 + "BM25 60%→嵌入 87% @5 零 LLM" + 确定性实测——差异化的第 N 根支柱。

## 9. 质量自评

- 可运行代码 ✅（三个脚本 30 分钟全复现，含 22k chunks 两引擎）
- 独到见解 ✅（per-form 集成决策 > 全局 RRF / tie-break 隐藏排序器 / 双档可选依赖 / 外部证据自有化）
- 项目关联 ✅（直接映射 C498 生产化 + FastAppendQueue 写时嵌入 + README 差异化）
- 方法论对齐 ✅（明确指标 hit@1/@5、伪影事故完整记录、负结果（RRF、静态 @1 差距）保留入笔记）
