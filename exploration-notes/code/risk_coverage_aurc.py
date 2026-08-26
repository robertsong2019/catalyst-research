#!/usr/bin/env python3
"""Risk-Coverage / AURC 评估器 — 把 amg 弃权门从"单点指标"升级为"曲线指标"。

约定（标准 selective prediction）：score = 作答置信度（越高越该作答）。
  弃权门 = 把低置信题排除在作答集之外；risk-coverage 曲线按置信降序逐题计入。

对照实验：模拟 amg full-500 形状（470 可答 + 30 _abs，可答正确率 0.60），对比两种门：
  Gate A = 熵门型（C448）：宽触发（误伤可答 ~4.5%），abs 题只捕获 ~11/15
  Gate B = neg-exist 型（C513/C516）：窄触发（误伤 ~0.8%），abs 题捕获 15/15
结论预告：AURC/E-AURC（曲线指标）与固定阈值（操作点指标）一致偏向 Gate B，
且 AURC 无需选阈值即可比较信号质量——amg 每次 A/B 选一个阈值=只看曲线上一个点。

引用：Ding et al. CVPRW 2020（AURC 是 AUROC/AUPR/AURC 中唯一可靠指标）；
      Kirichenko et al. AbstentionBench ICML 2025；Zhou et al. ICML 2025（population AURC）。

运行: python3 risk_coverage_aurc.py
"""
import random


# ---------- 1. 核心指标实现（零依赖，可直接移植 amg_bench_quality.py） ----------

def risk_coverage_curve(scored: list[dict]):
    """输入: [{score(作答置信), correct}]。返回 [(coverage, risk)]：
    按置信降序逐题计入作答集，risk = 已作答集合的错误率。
    abstainable 题若被排除（未计入）不产生风险——弃权的收益就体现在这里。"""
    ranked = sorted(scored, key=lambda r: r["score"], reverse=True)
    n, answered, wrong = len(ranked), 0, 0
    points = []
    for r in ranked:
        answered += 1
        wrong += 0 if r["correct"] else 1
        points.append((answered / n, wrong / answered))
    return points


def aurc(points) -> float:
    """Area Under Risk-Coverage curve（梯形积分）。越低越好。
    等价定义：全部 coverage 取值上的平均选择性风险。"""
    (c0, r0), area = (0.0, 0.0), 0.0
    for c, r in points:
        area += (c - c0) * (r0 + r) / 2
        c0, r0 = c, r
    return area


def e_aurc(scored: list[dict]) -> float:
    """Excess AURC = AURC − Oracle AURC（闭式 k²/2n²：对的全部排前面）。
    消除任务难度差，只留"排序质量"——跨题类/跨数据集可比。"""
    n = len(scored)
    if n == 0:
        return 0.0
    k = sum(1 for r in scored if not r["correct"])
    return aurc(risk_coverage_curve(scored)) - k * k / (2 * n * n)


def risk_at_coverage(points, c: float) -> float:
    """Risk@coverage：特定覆盖率下的错误率（如 Risk@90% = 弃 10% 题后的错误率）。"""
    for cov, risk in points:
        if cov >= c - 1e-9:
            return risk
    return points[-1][1] if points else 0.0


def fixed_threshold_decisions(scored: list[dict], threshold: float):
    """C448 式固定阈值操作点：score < threshold 全弃权。
    返回 (正确弃权 abs 数, 误伤可答数)。"""
    good = sum(1 for r in scored if r["score"] < threshold and r["abstainable"])
    bad = sum(1 for r in scored if r["score"] < threshold and not r["abstainable"])
    return good, bad


# ---------- 2. 模拟 full-500 形状数据 ----------

random.seed(517)  # Cycle 517 候选编号
rows = []
for i in range(470):  # 可答题：正确率 0.60；两门少量误伤（false-fire → 低置信）
    entropy_fire = random.random() < 0.045   # 熵门宽：误伤 ~4.5%
    negexist_fire = random.random() < 0.008  # neg-exist 门窄：误伤 ~0.8%（C513/C516 census）
    correct = random.random() < 0.60
    base = random.uniform(0.40, 0.95)  # 未触门时置信与对错无关（两门共享的现实局限）
    rows.append({
        "qid": f"answ_{i:03d}", "correct": correct, "abstainable": False,
        "gateA": random.uniform(0.10, 0.30) if entropy_fire else base,
        "gateB": random.uniform(0.10, 0.30) if negexist_fire else base,
    })
for j in range(30):  # 弃权题（abs30）：15 已被 C513/C516 捕获（低置信），15 残余（中高置信）
    caught = j < 15
    mid = random.uniform(0.35, 0.75)
    a_catches = caught and random.random() < 0.70  # 熵门只多捕 ~70%（启发式盲区）
    rows.append({
        "qid": f"abs_{j:02d}", "correct": False, "abstainable": True,  # 作答必错（GT=IDK）
        "gateA": random.uniform(0.05, 0.30) if a_catches else mid,
        "gateB": random.uniform(0.05, 0.35) if caught else mid,
    })

# ---------- 3. 对比实验：曲线指标 vs 操作点指标 ----------

hdr = f"{'门':<26}{'AURC':>8}{'E-AURC':>9}{'Risk@90%':>10}{'固定0.35正确弃权':>16}{'误伤':>6}"
print(hdr)
for name, key in (("Gate A 熵门型(宽)", "gateA"), ("Gate B neg-exist型(窄)", "gateB")):
    scored = [{"score": r[key], "correct": r["correct"], "abstainable": r["abstainable"]} for r in rows]
    pts = risk_coverage_curve(scored)
    good, bad = fixed_threshold_decisions(scored, 0.35)
    print(f"{name:<26}{aurc(pts):>8.4f}{e_aurc(scored):>9.4f}"
          f"{risk_at_coverage(pts, 0.90):>10.4f}{good:>13}/30{bad:>6}")

# ---------- 4. Calibration ≠ SP 演示（RLSR, arXiv 2607.03528 Fig.1 复现） ----------

# 信号 X：居中对称（近似"校准"），但对错置信分布完全重叠 → 排序无信息量
cal_but_unselective = [
    {"score": 0.5 + (0.4 if random.random() < 0.5 else -0.4) * random.random(),
     "correct": random.random() < 0.5, "abstainable": False}
    for _ in range(200)
]
# 信号 Y：系统性过自信（分数虚高）但排序完美（对的全排在错的前面）
n_corr = sum(1 for r in cal_but_unselective if r["correct"])
miscal_but_selective = [
    {"score": 0.90 + 0.05 * i / max(n_corr, 1) if r["correct"]
     else 0.10 + 0.05 * i / max(200 - n_corr, 1),
     "correct": r["correct"], "abstainable": False}
    for i, r in enumerate(sorted(cal_but_unselective, key=lambda x: x["correct"], reverse=True))
]
print()
print(f"对称校准但排序差: AURC = {aurc(risk_coverage_curve(cal_but_unselective)):.4f}")
print(f"过自信但排序完美: AURC = {aurc(risk_coverage_curve(miscal_but_selective)):.4f}  ← SP 只要求排序")
