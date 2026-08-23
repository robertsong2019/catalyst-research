# Hindsight Experience Replay for LLM Agents

**Date:** 2026-05-22
**Topic:** 将强化学习中的 Hindsight Experience Replay (HER) 适配到 LLM Agent，从失败轨迹中学习
**Related Projects:** Hindsight Mini, agent-context-store, agent-observability

---

## 核心概念

### 1. Hindsight Experience Replay (HER)
HER 是强化学习中的经典技术（Andrychowicz et al., 2017）：当 Agent 未能达到目标 G 时，不丢弃这条轨迹，而是用"实际达到的状态 G'"作为新目标来重新标注。公式化：将 (s, a, G, r=0) 转化为 (s, a, G', r=1)。核心洞察：**每个失败都隐含着某个替代目标的成功。**

### 2. AgentHER — 四阶段管线
2026 年的 AgentHER 论文（arXiv 2603.21357）首次系统性地将 HER 适配到 LLM Agent：
1. **Failure Classification** — 对失败轨迹分级（轻微/严重），严重推理缺陷的轨迹降权
2. **Outcome Extraction** — 从失败轨迹中提取实际完成了什么
3. **Prompt Relabeling** — 用 LLM 生成一个新目标 prompt，使该轨迹成为合法的成功示范
4. **Multi-Judge Verification** — 两个独立 judge 交叉验证 relabel 质量，精度达 97.1%

### 3. ECHO — 在线经验整合
ECHO（arXiv 2510.10304）是另一个方向：不修改训练数据，而是在推理时重写失败的 scratchpad 轨迹，将"本可以成功"的路径写入记忆供后续参考。与 AgentHER 的区别：ECHO 是 runtime 优化，AgentHER 是 offline 数据增强。

### 4. Experiential Reflective Learning (ERL)
ERL（arXiv 2603.24639）关注从成功和失败的对比中提取**启发式规则（heuristics）**，存入持久池，推理时按相关性检索注入。比 ExpeL 的改进：不是把所有经验拼入 prompt（会爆 context），而是做 heuristic-level 的压缩 + 检索。

### 5. Agent Observability 与 Hindsight 的交汇
Braintrust 2026 指南提出四阶段可观测性路径：capture → context → score → enforce。其中 "convert recurring failures into eval cases" 本质上就是 hindsight 思想在生产系统中的应用。

---

## 可运行代码示例：HindsightReplayStore

以下是一个基于 agent-context-store 理念的轻量级 Hindsight Replay 实现，可直接运行：

```python
"""
hindsight_replay_store.py
==========================
轻量级 Hindsight Experience Replay for LLM Agent trajectories.
纯 Python + JSON，零外部依赖。可直接 python hindsight_replay_store.py 运行。

设计理念：
- 每个失败轨迹不一定被丢弃，可能被"重标目标"后复用
- severity 权重过滤严重缺陷
- 简单的 heuristic 提取（对比成功/失败轨迹的差异）
"""

import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone


@dataclass
class Trajectory:
    """一条 Agent 执行轨迹"""
    id: str
    original_goal: str
    steps: list[str]          # 每步的 action description
    final_state: str          # 实际达到的终态描述
    success: bool             # 是否完成了 original_goal
    severity: str = "none"    # none | minor | major — 失败严重程度
    relabeled_goal: Optional[str] = None  # hindsight 重标后的目标
    relabeled_confidence: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def make_id(goal: str, steps: list[str]) -> str:
        content = goal + "|" + "|".join(steps)
        return hashlib.sha256(content.encode()).hexdigest()[:12]


@dataclass
class Heuristic:
    """从成功/失败对比中提取的启发式规则"""
    id: str
    pattern: str          # 失败模式描述
    advice: str           # 建议动作
    source_trajectory_ids: list[str]
    confidence: float = 1.0

    @staticmethod
    def make_id(pattern: str) -> str:
        return hashlib.sha256(pattern.encode()).hexdigest()[:12]


class HindsightReplayStore:
    """
    Hindsight Experience Replay 存储引擎。
    
    三大功能：
    1. store_trajectory — 存储轨迹，自动分级
    2. relabel — 对失败轨迹做 hindsight relabeling
    3. extract_heuristics — 对比成功/失败轨迹提取启发式规则
    """

    def __init__(self):
        self.trajectories: dict[str, Trajectory] = {}
        self.heuristics: dict[str, Heuristic] = {}

    def store_trajectory(self, goal: str, steps: list[str],
                         final_state: str, success: bool,
                         severity: str = "none") -> Trajectory:
        """存储一条轨迹"""
        tid = Trajectory.make_id(goal, steps)
        traj = Trajectory(
            id=tid, original_goal=goal, steps=steps,
            final_state=final_state, success=success, severity=severity,
        )
        self.trajectories[tid] = traj
        return traj

    def relabel(self, traj_id: str, new_goal: str, confidence: float = 0.8) -> Optional[Trajectory]:
        """
        对失败轨迹做 hindsight relabeling。
        条件：轨迹必须失败、severity 不能是 major、confidence >= 阈值。
        """
        traj = self.trajectories.get(traj_id)
        if not traj:
            return None
        if traj.success:
            return None  # 成功的不需要 relabel
        if traj.severity == "major":
            return None  # 严重缺陷的不值得 relabel
        if confidence < 0.6:
            return None  # 置信度过低

        traj.relabeled_goal = new_goal
        traj.relabeled_confidence = confidence
        return traj

    def get_training_data(self) -> list[dict]:
        """
        获取训练数据：成功轨迹 + relabeled 轨迹。
        模拟 AgentHER 的 SFT 数据打包。
        """
        data = []
        for traj in self.trajectories.values():
            if traj.success:
                data.append({
                    "goal": traj.original_goal,
                    "steps": traj.steps,
                    "label": "success",
                    "weight": 1.0,
                })
            elif traj.relabeled_goal and traj.relabeled_confidence >= 0.7:
                data.append({
                    "goal": traj.relabeled_goal,
                    "steps": traj.steps,
                    "label": "relabeled",
                    "weight": traj.relabeled_confidence * 0.8,  # 降权
                })
        return data

    def extract_heuristics(self) -> list[Heuristic]:
        """
        对比成功和失败轨迹，提取启发式规则。
        简化版 ERL 的 heuristic extraction。
        """
        successes = [t for t in self.trajectories.values() if t.success]
        failures = [t for t in self.trajectories.values() if not t.success]

        heuristics = []
        for fail in failures:
            # 找最相似的成功轨迹（简单按目标文本长度相似度）
            best_match = None
            best_sim = 0
            for succ in successes:
                sim = self._text_similarity(fail.original_goal, succ.original_goal)
                if sim > best_sim:
                    best_sim = sim
                    best_match = succ

            if best_match and best_sim > 0.3:
                pattern = f"Failed goal: {fail.original_goal[:50]}"
                advice = f"Succeeded approach: {' -> '.join(best_match.steps[:3])}"
                hid = Heuristic.make_id(pattern)
                if hid not in self.heuristics:
                    h = Heuristic(
                        id=hid, pattern=pattern, advice=advice,
                        source_trajectory_ids=[fail.id, best_match.id],
                        confidence=best_sim,
                    )
                    self.heuristics[hid] = h
                    heuristics.append(h)

        return heuristics

    def get_relevant_heuristics(self, goal: str, top_k: int = 3) -> list[Heuristic]:
        """检索与当前目标相关的启发式规则"""
        scored = []
        for h in self.heuristics.values():
            sim = self._text_similarity(goal, h.pattern)
            scored.append((sim, h))
        scored.sort(key=lambda x: -x[0])
        return [h for _, h in scored[:top_k]]

    def stats(self) -> dict:
        total = len(self.trajectories)
        success = sum(1 for t in self.trajectories.values() if t.success)
        relabeled = sum(1 for t in self.trajectories.values() if t.relabeled_goal)
        return {
            "total_trajectories": total,
            "successes": success,
            "failures": total - success,
            "relabeled": relabeled,
            "training_samples": success + relabeled,
            "utilization_rate": (success + relabeled) / total if total else 0,
            "heuristics": len(self.heuristics),
        }

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """简单的 Jaccard 相似度（词级）"""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)

    def export_json(self) -> str:
        return json.dumps({
            "trajectories": {k: asdict(v) for k, v in self.trajectories.items()},
            "heuristics": {k: asdict(v) for k, v in self.heuristics.items()},
        }, indent=2, ensure_ascii=False)


# ============================================================
# 运行示例
# ============================================================
if __name__ == "__main__":
    store = HindsightReplayStore()

    # --- 存储成功轨迹 ---
    store.store_trajectory(
        goal="在 GitLab 项目中列出所有未更新的 issue",
        steps=["navigate(/issues?state=opened)", "filter(updated<30d)", "summarize()"],
        final_state="返回 8 个 stale issue 的列表",
        success=True,
    )

    # --- 存储失败轨迹 ---
    store.store_trajectory(
        goal="在 GitLab 项目中列出所有 a11y 标签的 issue",
        steps=["navigate(/issues?state=opened)", "filter(labels=all)", "summarize()"],
        final_state="返回了所有 issue 但未按 a11y 标签过滤",
        success=False,
        severity="minor",  # 轻微失败，可 relabel
    )

    store.store_trajectory(
        goal="删除 GitLab 中的所有过期分支",
        steps=["navigate(/branches)", "repeat(delete, 5x)", "timeout()"],
        final_state="超时，仅删除了 2/5 分支",
        success=False,
        severity="major",  # 严重失败，不 relabel
    )

    store.store_trajectory(
        goal="合并 feature-x 分支到 main",
        steps=["navigate(/merge_requests)", "create_mr(feature-x→main)", "approve()", "merge()"],
        final_state="MR 创建并合并成功",
        success=True,
    )

    # --- Hindsight Relabeling ---
    # 失败轨迹 1：虽然没按 a11y 过滤，但成功列出了所有 issue
    traj_ids = [t.id for t in store.trajectories.values()]
    for tid in traj_ids:
        traj = store.trajectories[tid]
        if not traj.success and traj.severity == "minor":
            store.relabel(tid, "列出 GitLab 项目中所有打开的 issue（不带过滤）", confidence=0.85)

    # --- 提取启发式规则 ---
    heuristics = store.extract_heuristics()

    # --- 输出结果 ---
    print("=" * 60)
    print("HindsightReplayStore 演示")
    print("=" * 60)

    stats = store.stats()
    print(f"\n📊 统计:")
    print(f"  总轨迹数: {stats['total_trajectories']}")
    print(f"  成功: {stats['successes']}")
    print(f"  失败: {stats['failures']}")
    print(f"  已 Relabel: {stats['relabeled']}")
    print(f"  可用训练样本: {stats['training_samples']}")
    print(f"  利用率: {stats['utilization_rate']:.0%}")
    print(f"  启发式规则: {stats['heuristics']}")

    print(f"\n📚 训练数据:")
    for sample in store.get_training_data():
        print(f"  [{sample['label']}] weight={sample['weight']:.2f}")
        print(f"    goal: {sample['goal']}")
        print(f"    steps: {' -> '.join(sample['steps'])}")

    print(f"\n💡 启发式规则:")
    for h in heuristics:
        print(f"  [{h.id}] conf={h.confidence:.2f}")
        print(f"    pattern: {h.pattern}")
        print(f"    advice: {h.advice}")

    print(f"\n🔍 查询相关 heuristics (goal='列出 GitLab issue'): ")
    for h in store.get_relevant_heuristics("列出 GitLab issue"):
        print(f"  → {h.advice}")

    print("\n✅ 利用率从 50% → 75%（2成功 + 1 relabeled / 4 总计）")
    print("   （AgentHER 论文报告 3.7x 数据增长，从 ~25% → ~90%）")
```

**运行方式：**
```bash
python3 hindsight_replay_store.py
```

**预期输出：**
```
============================================================
HindsightReplayStore 演示
============================================================

📊 统计:
  总轨迹数: 4
  成功: 2
  失败: 2
  已 Relabel: 1
  可用训练样本: 3
  利用率: 75%
  启发式规则: 1

📚 训练数据:
  [success] weight=1.00
    goal: 在 GitLab 项目中列出所有未更新的 issue
    ...
  [relabeled] weight=0.68
    goal: 列出 GitLab 项目中所有打开的 issue（不带过滤）
    ...
  [success] weight=1.00
    goal: 合并 feature-x 分支到 main
    ...

✅ 利用率从 50% → 75%
```

---

## 关键洞察

### 1. 失败是最大的数据来源
LLM Agent 在真实任务中失败率极高（GPT-4o 在 WebArena 仅 14-20% 成功率），这意味着 **70-85% 的执行数据被浪费**。AgentHER 证明了这些"废数据"通过 relabel 可以变成有效训练信号，数据利用率提升 3.7 倍。对于 OpenClaw 的 agent-observability 系统，这意味着应该**主动记录失败轨迹而非只记成功**。

### 2. Relabel ≠ Rewriting — 保持轨迹完整性的关键
AgentHER 只重标目标（goal），不修改轨迹本身（trajectory）。这比 ECHO 的轨迹重写更安全——避免了"编造成功历史"的风险。在实现 Hindsight Mini 时应该遵循同样原则：**只改目标标签，不改执行记录**。这与 agent-context-store 的 append-only 语义天然契合。

### 3. Severity Weighting 是质量守门员
不是所有失败都值得 relabel。AgentHER 用 MQM-style 错误分析将失败分为 minor/major，major 级别的轨迹（如循环重复同一动作）直接丢弃。两个独立 judge 交叉验证将标注噪声从 5.9% 降到 2.3%。**在生产系统中，质量过滤比数量更重要。**

### 4. Heuristic Extraction > Raw Trajectory Replay
ERL 的核心发现：从成功/失败对比中提取的 **抽象启发式规则** 比原始轨迹更有效且更省 context。OpenClaw 的 HEARTBEAT 错误升级机制（memory/error-patterns.md）本质上就是一种手动 heuristic extraction。可以自动化这个过程。

### 5. 这与现有项目的关系
- **agent-context-store** → 天然的轨迹存储后端，merge_content + get_or_create + snapshot 支持轨迹的增量记录和回放
- **agent-observability** → 已有的 trace/span 架构可以直接作为 HER 的输入数据源
- **Hindsight Mini** → 实验性原型，验证"失败轨迹 + relabel + heuristic"的闭环

---

## 下一步行动

1. **实现 Hindsight Mini v0.1** — 基于上面的 `HindsightReplayStore` 代码，接入 agent-context-store 作为持久化后端，创建 `lab/hindsight-mini/`。核心 API：`record_execution()`, `relabel_failures()`, `extract_heuristics()`, `get_training_samples()`。

2. **为 agent-observability 添加 failure tracking** — 在现有的 91 个 tests 基础上，增加 trajectory-level 的失败记录和 severity classification，为后续 HER 管线提供数据。

3. **评估 AgentHER 论文中的 Multi-Judge Verification** — 是否可以在 OpenClaw 中用两个不同模型（如 GLM + GPT）做交叉验证？这对标注质量有多大提升？

---

## 参考文献

- Andrychowicz et al. (2017) "Hindsight Experience Replay" — 原始 HER 论文
- AgentHER (arXiv 2603.21357) "Hindsight Experience Replay for LLM Agent Trajectory Relabeling" — 2026
- ECHO (arXiv 2510.10304) "Sample-Efficient Online Learning in LM Agents via Hindsight Trajectory Rewriting" — 2025
- ERL (arXiv 2603.24639) "Experiential Reflective Learning for Self-Improving LLM Agents" — 2026
- Braintrust "Agent Observability: The Complete Guide for 2026"
- Yohei Nakajima "Better Ways to Build Self-Improving AI Agents" — NeurIPS 2025 survey
