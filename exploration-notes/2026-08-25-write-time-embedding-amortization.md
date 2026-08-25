# Research #088 — 写时嵌入摊销：FastAppendQueue 钩子路径的架构判决

> 2026-08-25 20:00 deep-exploration-evening · autoresearch 方法论
> 主题：MEMORY Next 头号开发目标「写时嵌入摊销（FastAppendQueue 钩子把 7.5s/题 side-channel 嵌入摊销为零——POST 0.414 已验证通道价值）」
> 前序：#083（嵌入 side-channel 选型判决，MiniLM 26/30 @5 / potion 22/30 / RRF 有害 / form-gated 定案）——本篇是其 next-action #2
> 代码：`code/writetime_embed_amortize.py`（真实 model2vec 引擎，本机 1GB 盒）
> 外部取证：mem0ai/mem0 `mem0/memory/main.py`（3868 行，main 分支）+ getzep/graphiti `graphiti_core/graphiti.py`（1793 行）源码直读 2026-08-25

---

## 1. 结论速览

**判决：写时嵌入是纯架构变更、零检索质量代价（A/B 18/18 位级一致）；最小改动落点不在 FastAppendQueue 而在 bench 内跨题 memo（eval 协议 6.1× 冗余嵌入）；静态档（model2vec）额外解锁合并免重嵌入的代数性质——consolidate() 的向量侧可以零嵌入闭式更新。**

| 臂 | 每题成本 | 全程 embed 调用 | 一致性 |
|----|---------|----------------|--------|
| A query-time（现状语义） | 31ms（potion 实测；MiniLM 投影 7.5s） | 36 次 / 2178 texts | 基准 |
| B write-time（flush 批量+memo） | **3ms**（仅嵌问题） | **19 次 / 138 texts** | **18/18 与 A 全同** |
| B′ 重放同语料 | ~0 | **0 次**（content-hash 全命中） | 幂等 |
| C 合并 ×60（consolidate 模拟） | ~0 | **0 次**（线性加权合并） | 静态档独有 |

真实协议投影（#083 口径：22,002 unique chunks，~270 chunks/题，LME 500 题）：
- query-time 现状：500 × 270 = **135,000 次 chunk 嵌入**（MiniLM 36/s ≈ **62.5 分钟**）
- write-time：22,002 unique 一次性 = **611 秒**（MiniLM）或 **8.9 秒**（potion），此后每题仅嵌问题一次
- **冗余率 6.1×**；盈亏平衡点 = 82 题（611s ÷ 7.5s/题），LME 500 远超

## 2. 生产系统对照（源码取证，非博客转述）

| 系统 | 写时嵌入模式 | 关键代码 | 语义 |
|------|-------------|---------|------|
| **Mem0** | eager batch | `main.py:994` `embed_batch(mem_texts,"add")`；失败**逐条降级**；`:689` update 路径 `embed(entity_text,"update")` 重嵌入 | 写入即嵌入，动作标签区分 add/update，批量优先 |
| **Graphiti/Zep** | lazy on-miss | `graphiti.py:1648` `if node.name_embedding is None: await generate_name_embedding()`；社区更新时 `:1511` 批量补嵌 | None 检查 = 惰性 memo；首用补嵌，更新刷新 |
| **amg 现状** | query-time per-question | `amg_bench_quality.py` 每题对全 haystack 分块+嵌入，无跨题缓存 | eval 协议下的最坏情况 |

**amg 的正确姿势是两者合体**：flush 时 Mem0 式 eager batch（System-2 天然批位置）+ 查询时 Graphiti 式 lazy fallback（预计算 miss → 现嵌，不 fail）。

## 3. 核心概念

1. **摊销边界迁移**：把嵌入成本从查询路径（N_chunks × Q_queries 次）迁到写入路径（N_unique + Q 次）。本质是 Amdahl 视角——查询时嵌入占 side-channel 总成本 >99%，且跨题高度重复（6.1×），是纯冗余而非必要功。
2. **content-hash memo（幂等重放）**：chunk 文本 SHA-1 → 向量缓存。重放/回归/重建索引全零成本；Graphiti 的 `is None` 检查是其退化形式（以节点为单位、不跨模型版本）。
3. **静态嵌入的代数性（本篇新发现）**：model2vec = 查表 + **线性均值池化**，故合并节点向量 = 成员向量加权平均，**免重嵌入**；衰减（decay）= 标量缩放，同样闭式。神经档（MiniLM）无此性质，Mem0 才需要 update 重嵌入——**这是静态档在"记忆是活的"场景的结构性优势**，速度之外的第二张牌。
4. **System-1/System-2 边界即嵌入新鲜度边界**：FastAppendQueue 已定义"append 无处理、flush 全处理"的一致性面；嵌入落在 flush 侧 = side-channel 检索只看已 flush 会话——**与现有图操作的新鲜度语义完全对齐，零新增一致性面**。
5. **双档依赖在写时更从容**：写路径有预算意识（flush 是天然批位置），quality 档 611s 一次性成本可接受；query 路径 7.5s/题则任何档都疼。**摊销让质量档变得可部署**——#083 的双档权衡（4 题 @1 差距换 69× 速度）在写时架构下退化为纯质量问题。

## 4. 代码

`code/writetime_embed_amortize.py` —— 三臂对照（可运行，~30s 含模型加载）：

```python
# 核心 1：flush 时 Mem0 式批量 + memo 去重（Arm B 摊销主体）
pending, texts = [], []
for sess in self._buffer:
    for c in chunk(sess):
        h = hashlib.sha1(c.encode()).hexdigest()
        if h not in self._memo:               # memo 命中 → 零嵌入
            pending.append((h, c)); texts.append(c)
if texts:                                     # 一次批量前向
    for (h, _), v in zip(pending, self.engine.embed(texts)):
        self._memo[h] = v

# 核心 2：查询只嵌问题（Arm B 查询路径的全部嵌入成本）
def search(self, q):
    qv = self.engine.embed([q])[0]
    ...  # chunk-max 点积，纯 numpy 语义

# 核心 3：consolidate 合并 = 静态嵌入的闭式更新（Arm C，零嵌入）
merged = [[w_a * x + (1 - w_a) * y for x, y in zip(va, vb)]   # 线性加权平均
          for va, vb in zip(a, b)]
del self._sess_vecs[sid_b]                    # tombstone：被吸收者退役
```

运行：`python3 code/writetime_embed_amortize.py`
实测输出：31ms/q → 3ms/q（12×），embed texts 2178 → 138（−94%），18/18 top-1 一致，重放 0 嵌入，合并 60 次 0 嵌入。

## 5. 关键洞察

1. **无损性是位级确定性给的**（18/18）：model2vec 跨实例/跨批组成/批内重复三种情况实测逐位相等——同文本同向量，故写时与查询时两臂的检索结果**必然**全同。摊销改造因此不需要任何检索质量回归测试以外的辩护；反过来，神经档若未来引入（批内 padding 或量化抖动）需补一致性断言。
2. **最小改动落点是 bench 的跨题 memo，不是 FastAppendQueue**：eval harness 每题重嵌自己 haystack，6.1× 冗余全在协议内部。给 `amg_bench_quality.py` 加进程级 content-hash 缓存（~20 行）即可把 POST 臂 1135s 砍到 ~120s（22k unique @potion 8.9s + 500 题问题嵌入）。**这是 C512 的一天版**；FastAppendQueue 钩子是生产库正确性版本。
3. **静态档把 #081 的 tombstone 哲学延伸到向量侧**：知识编辑判决（tombstone > rewrite）在嵌入维度的对应物——被合并者向量直接退役（tombstone），幸存者向量加权更新（代数闭式），**永不重嵌入**。神经档做不到：Mem0 的 `"update"` 动作标签就是为重嵌入存在的。amg 若以静态档为 side-channel 默认，consolidate() 的向量维护是 O(1) 标量运算。
4. **新鲜度没有变差，只是显式化**：side-channel 在 flush 前看不到 buffer——但 System-1 本来就是 keyword-only 读，图操作本来就有这个边界。嵌入没有引入新的一致性面，它**搭了现有 System-2 的便车**。
5. **分母 bug 教训（error-pattern 级）**：`agree/{Q}` 用全局常量 Q 做分母而 queries 实为 18 条，制造出"18/20 不一致"的假象，一度把确定性引擎当成可疑对象排查了三轮（同批组成性→跨实例→列表长度）。**比率打印必须用 len(实际集合)，禁止用平行常量**——已第三次遇到"显示层 bug 伪装成数据异常"（tie-break 伪影 #083 / stale-base 台账 08-24 / 本次分母）。

## 6. 下一步行动

1. **C512-A（最小改动，bench 内 memo）**：`amg_bench_quality.py` side-channel 路径加进程级 `content-hash → vec` 缓存（跨题复用）。预期 POST 臂 1135s → ~2min 内；得分零变化（确定性保证）；解锁全量 sweep 的可行性。验证标准：embed texts 计数 ≤ 22,002 + 500。
2. **C512-B（生产化，FastAppendQueue 钩子）**：`flush()` 尾部接 `embed_buffered_sessions()` → `graph.add_embeddings_batch`（存储层已存在，`memory_graph.py:10474`）；查询侧 sidechannel_form 读预计算向量，miss 回退现嵌（Graphiti lazy 模式，不 fail）。A/B 验证：POST 切片逐题零翻转。
3. **合并语义（C513 候选）**：`consolidate()` 静态档加权平均嵌入 / 神经档 re-embed 队列 + `embedding_model_version` 字段进 `knowledge_freshness_report`（模型升级 = staleness 可见）。
4. **README 弹药**："write-time amortization: 7.5s/query → ~0, lossless by construction（位级确定性）+ merge without re-embedding（静态档代数性）"——side-channel 章节的两条差异化。

## 7. 质量自评

- 可运行代码 ✅（三臂真实引擎跑通，30s 复现，含确定性三重验证）
- 独到见解 ✅（静态嵌入线性合并性=向量侧 tombstone / bench 6.1× 冗余判定最小落点 / 摊销让质量档可部署 / 新鲜度零新增一致性面）
- 项目关联 ✅（直接映射 C512-A/B + consolidate 向量维护 + README；接续 #083 next-action #2 与 #081 tombstone 哲学）
- 方法论对齐 ✅（明确指标：texts 计数/每题延迟/一致率；分母事故完整记录；负结果保留：神经档无代数性）
