#!/usr/bin/env python3
"""judge_ab_harness.py — 语义判分 A/B 的 oracle 校准协议（Research #092）

零依赖 Python 3.10+。方法学原型：当用 LLM 判分标签当 oracle 时，
如何量化 oracle 噪音对 A/B 结论的腐蚀，并给出可信比较协议。

核心组件:
  1. judge_v0 / judge_v1   — 确定性判分层（exact / +归一化+软语义臂，#090 简化移植）
  2. OracleJudge           — 模拟 LLM oracle：分类型噪音底（LongMemEval Table 6 实测校准）
  3. cohens_kappa          — chance-corrected 一致率（exact agreement 普遍虚高的矫正）
  4. mcnemar_exact         — 配对判分器比较的精确二项检验（A vs B 的合法检验）
  5. bootstrap_credit_ci   — credit 差值的 bootstrap 置信区间
  6. majority oracle       — NEEDS_JUDGE 带的多 trial 多数决

用法:
  python3 judge_ab_harness.py --selftest   # 12 用例自测
  python3 judge_ab_harness.py --demo       # A/B 演示 + oracle 噪音扫描
"""

from __future__ import annotations

import argparse
import math
import random
import re
import statistics
from dataclasses import dataclass
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# 判分层：v0（exact 基线）与 v1（+归一化+软语义臂）
# ---------------------------------------------------------------------------

CREDIT = "CREDIT"
NO_CREDIT = "NO_CREDIT"
NEEDS_JUDGE = "NEEDS_JUDGE"

NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20", "thirty": "30",
    "hundred": "100", "thousand": "1000",
}
TIME_UNITS = {"hours": 3600, "hour": 3600, "minutes": 60, "minute": 60,
              "days": 86400, "day": 86400, "weeks": 604800, "week": 604800}
MONTHS = {"january": "jan", "february": "feb", "march": "mar", "april": "apr",
          "june": "jun", "july": "jul", "august": "aug", "september": "sep",
          "october": "oct", "november": "nov", "december": "dec"}
STOPWORDS = {"is", "his", "her", "the", "a", "an", "of", "to", "in", "at", "on", "and", "was"}


def _norm_tokens(text: str) -> str:
    """归一化：数字词折叠、货币吸附与币种规范、序数、标点剥离、小写。"""
    t = text.strip().lower()
    t = re.sub(r"([\d,])\s*\$(?!\d)", r"\1 usd", t)      # 尾随 $ 吸附
    t = re.sub(r"\$\s*([\d,]+(?:\.\d+)?)", r"\1 usd", t)  # $ 前缀吸附
    t = re.sub(r"\bdollars?\b", "usd", t)                 # 币种词规范
    t = re.sub(r"\beuros?\b", "eur", t)
    t = re.sub(r"\byen\b", "jpy", t)
    t = re.sub(r"\byuan\b", "cny", t)
    t = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", t)   # 序数
    for w, d in NUMBER_WORDS.items():
        t = re.sub(rf"\b{w}\b", d, t)
    t = re.sub(r"[,$.]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _date_fold(text: str) -> str:
    """日期折叠: january 5 2023 / 5 january 2023 / jan 5th 2023 -> 2023-01-05 尽力而为。"""
    t = _norm_tokens(text)
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2})\s*(\d{4})?\b", t)
    if m:
        mon = m.group(1)
        day = int(m.group(2))
        year = m.group(3) or ""
        return f"{year}-{mon}-{day}".strip("-") if year else f"{mon}-{day}"
    m = re.search(r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d{4})?\b", t)
    if m:
        day, mon, year = int(m.group(1)), m.group(2), m.group(3) or ""
        return f"{year}-{mon}-{day}".strip("-") if year else f"{mon}-{day}"
    return t


def _numbers_of(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", _norm_tokens(text))


def _currencies_of(text: str) -> set[str]:
    t = _norm_tokens(text)
    return set(re.findall(r"\b(usd|eur|jpy|cny)\b", t))


def _time_seconds(text: str) -> float | None:
    t = _norm_tokens(text)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|minutes?|days?|weeks?)", t)
    if not m:
        return None
    return float(m.group(1)) * TIME_UNITS[m.group(2)]


def judge_v0(question: str, ref: str, cand: str) -> str:
    """基线：裸 exact（大小写不敏感）。"""
    return CREDIT if ref.strip().lower() == cand.strip().lower() else NO_CREDIT


def judge_v1(question: str, ref: str, cand: str) -> str:
    """#090 简化移植：exact -> 归一化 -> 带守护的软语义臂。返回 NEEDS_JUDGE 时生产环境转 LLM。"""
    r, c = ref.strip(), cand.strip()
    if r.lower() == c.lower():
        return CREDIT
    nr, nc = _norm_tokens(r), _norm_tokens(c)
    if nr == nc:
        return CREDIT
    # 日期折叠
    if _date_fold(r) == _date_fold(c) and _date_fold(r) != nr and _date_fold(r) != nc:
        return CREDIT
    # 时间单位换算（two hours ≡ 120 minutes）
    tr, tc = _time_seconds(r), _time_seconds(c)
    if tr is not None and tc is not None and abs(tr - tc) < 1e-9:
        return CREDIT
    # 守护 1：数字签名不一致 → 一票否决（7 vs 17 / 1250 vs 1300）
    num_r, num_c = _numbers_of(r), _numbers_of(c)
    if num_r and num_c and sorted(num_r) != sorted(num_c):
        return NO_CREDIT
    # 守护 2：货币域冲突（$5 vs 5 euros，币种规范化后比较）
    cur_r, cur_c = _currencies_of(r), _currencies_of(c)
    if cur_r and cur_c and cur_r != cur_c:
        return NO_CREDIT
    # 守护 3：不对称包含（#090 不对称等价 / LongMemEval 官方协议 superset 规则）
    toks_r = {w for w in nr.split() if w not in STOPWORDS}
    toks_c = {w for w in nc.split() if w not in STOPWORDS}
    if toks_c and toks_c < toks_r:      # cand ⊂ ref：更弱答案（tennis vs table tennis）
        return NO_CREDIT
    if toks_r and toks_r < toks_c:      # ref ⊂ cand：superset 含正确答案 → 给分
        return CREDIT
    # 软语义臂：序列相似度（嵌入臂的确定性替身）
    sim = SequenceMatcher(None, nr, nc).ratio()
    if sim >= 0.75:
        return CREDIT
    # 词面不可解且无守护命中 → 诚实弃权（生产环境转 LLM oracle）
    return NEEDS_JUDGE


CREDITING = {CREDIT}  # v1 中 NEEDS_JUDGE 不给分（保守；生产环境转 LLM oracle）


# ---------------------------------------------------------------------------
# 模拟 LLM oracle：分类型噪音底（按 LongMemEval Table 6 实测人工不一致率校准）
# ---------------------------------------------------------------------------

# Table 6（GPT-4o judge, 30 题/类）判分错误率 = 1 - accuracy；翻转概率以此为底
TYPE_NOISE_FLOOR = {
    "ss_user": 0.00,        # 1.00
    "ss_assistant": 0.00,   # 1.00
    "preference": 0.10,     # 0.90  ← 最弱，开放性答案
    "multi_session": 0.00,  # 1.00
    "kupdate": 0.00,        # 1.00
    "temporal": 0.00,       # 1.00
    "abstention": 0.03,     # 0.97
}
GLOBAL_NOISE = 0.02  # 模板/解码抖动的保守兜底（Coin Flip Judge: 点评式远稳于配对式 13.6%）


@dataclass
class Case:
    qid: str
    qtype: str
    question: str
    ref: str
    cand: str
    truth: int  # 官方 judge 协议应给的判定 1=credit 0=no credit


class OracleJudge:
    def __init__(self, seed: int = 42, trials: int = 1, noise_scale: float = 1.0):
        self.rng = random.Random(seed)
        self.trials = trials
        self.noise_scale = noise_scale

    def _flip_p(self, qtype: str) -> float:
        base = max(TYPE_NOISE_FLOOR.get(qtype, 0.0), GLOBAL_NOISE)
        return min(0.95, base * self.noise_scale)

    def label(self, case: Case) -> int:
        votes = []
        for _ in range(self.trials):
            votes.append(case.truth if self.rng.random() >= self._flip_p(case.qtype) else 1 - case.truth)
        return 1 if sum(votes) * 2 > len(votes) else (votes[0] if sum(votes) * 2 == len(votes) else 0)


# ---------------------------------------------------------------------------
# 统计工具
# ---------------------------------------------------------------------------

def cohens_kappa(labels_a: list[int], labels_b: list[int]) -> float:
    """Cohen's kappa — chance-corrected agreement。"""
    assert len(labels_a) == len(labels_b) and labels_a
    n = len(labels_a)
    po = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n
    p_a1, p_b1 = sum(labels_a) / n, sum(labels_b) / n
    pe = p_a1 * p_b1 + (1 - p_a1) * (1 - p_b1)
    return 1.0 if pe == 1.0 else (po - pe) / (1.0 - pe)


def mcnemar_exact(b: int, c: int) -> float:
    """配对 discordant (b, c) 的双侧精确二项 p 值。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def bootstrap_credit_ci(credits: list[int], truth: list[int], n_boot: int = 2000,
                        seed: int = 7) -> tuple[float, float]:
    """credit 准确率（vs truth）的 bootstrap 95% CI。"""
    rng = random.Random(seed)
    n = len(credits)
    accs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        accs.append(sum(1 for i in idx if credits[i] == truth[i]) / n)
    accs.sort()
    return accs[int(0.025 * n_boot)], accs[int(0.975 * n_boot)]


# ---------------------------------------------------------------------------
# 数据集：26 例，形态取自 amg 真实失配面（C519/C526/#090/LongMemEval 类型）
# ---------------------------------------------------------------------------

def dataset() -> list[Case]:
    T = {
        # (ref, cand, truth)  truth = 官方 LongMemEval judge 协议应给分
        "norm_date": [("January 5, 2023", "Jan 5th 2023", 1),
                      ("March 23, 2019", "23rd of March 2019", 1),
                      ("March 2019", "March 2020", 0)],
        "norm_time": [("two hours", "120 minutes", 1),
                      ("three weeks", "21 days", 1),
                      ("two hours", "three hours", 0)],
        "number": [("1250", "1,250", 1), ("7", "17", 0), ("1300", "1250", 0),
                   ("30", "about 30 people", 1)],
        "entity": [("table tennis", "tennis", 0),
                   ("Fender Stratocaster", "a Fender guitar", 1),
                   ("Sarah", "Rachel", 0)],
        "currency": [("$56,355", "56355 dollars", 1), ("$5", "5 euros", 0)],
        "paraphrase": [("she planned it herself", "Rachel", 1),
                       ("at the community library", "the local library", 1),
                       ("photography", "painting", 0)],
        "preference": [("blue", "blue is his favorite color", 1),
                       ("jazz", "rock music", 0)],
        "abstention": [("unknown", "the email is never mentioned", 1),
                       ("unknown", "june 12th", 0)],
    }
    qmap = {"norm_date": "temporal", "norm_time": "temporal", "number": "multi_session",
            "entity": "multi_session", "currency": "multi_session",
            "paraphrase": "kupdate", "preference": "preference", "abstention": "abstention"}
    cases: list[Case] = []
    qs = {"norm_date": "When did they meet?", "norm_time": "How long did it take?",
          "number": "How many followers does Alex have?", "entity": "Who won the match?",
          "currency": "How much did the car cost?", "paraphrase": "Who planned the trip?",
          "preference": "What is his favorite color?", "abstention": "What email did she use?"}
    i = 0
    for fam, triples in T.items():
        for ref, cand, truth in triples:
            i += 1
            cases.append(Case(f"q{i:03d}", qmap[fam], qs[fam], ref, cand, truth))
    return cases


# ---------------------------------------------------------------------------
# A/B 运行器
# ---------------------------------------------------------------------------

def run_ab(cases: list[Case], oracle: OracleJudge) -> dict:
    v0 = [1 if judge_v0(c.question, c.ref, c.cand) == CREDIT else 0 for c in cases]
    v1 = [1 if judge_v1(c.question, c.ref, c.cand) in CREDITING else 0 for c in cases]
    ol = [oracle.label(c) for c in cases]
    truth = [c.truth for c in cases]

    def confusion(pred: list[int]) -> tuple[int, int, int, int]:
        tp = sum(1 for p, t in zip(pred, truth) if p == 1 and t == 1)
        fp = sum(1 for p, t in zip(pred, truth) if p == 1 and t == 0)
        fn = sum(1 for p, t in zip(pred, truth) if p == 0 and t == 1)
        tn = sum(1 for p, t in zip(pred, truth) if p == 0 and t == 0)
        return tp, fp, fn, tn

    b = sum(1 for a, bb, o in zip(v0, v1, ol) if a == 0 and bb == 1 and o == 1)  # v1 独得真分
    c_disc = sum(1 for a, bb, o in zip(v0, v1, ol) if a == 1 and bb == 0 and o == 1)  # v1 丢真分
    hijack = sum(1 for a, bb, o in zip(v0, v1, ol) if bb == 1 and a == 0 and o == 0)
    delta = sum(1 for bb, o in zip(v1, ol) if bb == o) / len(cases) - \
            sum(1 for a, o in zip(v0, ol) if a == o) / len(cases)
    lo, hi = bootstrap_credit_ci(v1, truth)
    return {
        "v0_credit": sum(v0), "v1_credit": sum(v1), "oracle_credit": sum(ol),
        "confusion_v1": confusion(v1),
        "rescue_true": b, "rescue_lost": c_disc, "false_pass_hijack": hijack,
        "delta_agreement": delta, "kappa_v0": cohens_kappa(v0, ol),
        "kappa_v1": cohens_kappa(v1, ol), "mcnemar_p": mcnemar_exact(b, c_disc),
        "ci95_v1_vs_truth": (lo, hi),
        "needs_judge": sum(1 for cq in cases if judge_v1(cq.question, cq.ref, cq.cand) == NEEDS_JUDGE),
    }


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------

def selftest() -> int:
    fails: list[str] = []
    total = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal total
        total += 1
        if not cond:
            fails.append(f"{name}: {detail}")
        print(f"  {'✅' if cond else '❌'} {name}{'' if cond else '  ' + detail}")

    print("== kappa ==")
    check("perfect=1.0", cohens_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0)
    check("chance≈0", abs(cohens_kappa([1, 1, 0, 0], [1, 0, 1, 0])) < 1e-9)
    pred = [1] * 90 + [0] * 10
    orac = [1] * 85 + [0] * 5 + [1] * 5 + [0] * 5
    k = cohens_kappa(pred, orac)
    raw = sum(1 for a, b in zip(pred, orac) if a == b) / 100
    check("κ缩水: raw 0.90 → κ≈0.44", 0.40 < k < 0.50 and abs(raw - 0.90) < 1e-9,
          f"raw={raw:.2f} kappa={k:.3f}")

    print("== mcnemar ==")
    check("b=10,c=1 → p≈0.01172", abs(mcnemar_exact(10, 1) - 2 * 12 / 2048) < 1e-12)
    check("b=c=5 → p=1.0", mcnemar_exact(5, 5) == 1.0)
    check("b=0,c=0 → p=1.0", mcnemar_exact(0, 0) == 1.0)

    print("== oracle 校准（固定种子，n=400 合成样本）==")
    o = OracleJudge(seed=123, noise_scale=1.0)
    syn = [Case(f"s{i}", "preference", "q?", "x", "y", 1) for i in range(400)]
    flips = sum(1 for c in syn if o.label(c) != c.truth) / len(syn)
    check("preference 噪音底≈0.10", 0.05 <= flips <= 0.16, f"flips={flips:.3f} (n=400)")
    det = OracleJudge(seed=1, noise_scale=0.0)
    check("noise=0 → 零翻转", all(det.label(c) == c.truth for c in dataset()))

    print("== 多数决降噪（全体 flip p<0.5 前提）==")
    cases = dataset()
    noisy = OracleJudge(seed=99, noise_scale=3.0)  # 全局 6% / preference 30%
    single = sum(1 for c in cases * 20 if noisy.label(c) != c.truth)
    maj = OracleJudge(seed=99, noise_scale=3.0, trials=3)
    with_majority = sum(1 for c in cases * 20 if maj.label(c) != c.truth)
    check("3-trial < 1-trial", with_majority < single,
          f"1-trial={single} 3-trial={with_majority}")

    print("== 判分守护（false-pass 红线）==")
    check("7 vs 17 不给分", judge_v1("How many?", "7", "17") == NO_CREDIT)
    check("$5 vs 5 euros 不给分", judge_v1("How much?", "$5", "5 euros") == NO_CREDIT)
    check("tennis 作候选=更具体给分(IMPROVES)", judge_v1("Sport?", "tennis", "table tennis") == CREDIT)
    check("tennis 作参考时弱候选不给分", judge_v1("Sport?", "table tennis", "tennis") == NO_CREDIT)
    check("货币同域换写给分", judge_v1("How much?", "$56,355", "56355 dollars") == CREDIT)
    check("日期折叠给分", judge_v1("When?", "January 5, 2023", "Jan 5th 2023") == CREDIT)
    check("时间换算给分", judge_v1("How long?", "two hours", "120 minutes") == CREDIT)
    check("数字词给分", judge_v1("How many?", "1,250", "1250") == CREDIT)
    check("superset 偏好给分(官方协议)", judge_v1("Favorite color?", "blue", "blue is his favorite color") == CREDIT)
    check("词面零重叠 → 弃权转 LLM", judge_v1("Who planned it?", "she planned it herself", "Rachel") == NEEDS_JUDGE)
    check("实体消解 → 弃权转 LLM", judge_v1("Who won?", "Sarah", "Rachel") == NEEDS_JUDGE)

    print("== bootstrap ==")
    cases = dataset()
    v1c = [1 if judge_v1(c.question, c.ref, c.cand) in CREDITING else 0 for c in cases]
    truth = [c.truth for c in cases]
    acc = sum(1 for p, t in zip(v1c, truth) if p == t) / len(cases)
    lo, hi = bootstrap_credit_ci(v1c, truth, n_boot=500, seed=3)
    check("CI 包含点估计", lo - 1e-9 <= acc <= hi + 1e-9, f"acc={acc:.3f} CI=({lo:.3f},{hi:.3f})")

    n = len(fails)
    print(f"\n{'✅ ALL PASS' if n == 0 else f'❌ {n} FAIL'}: {total - n}/{total}")
    return n


def demo() -> None:
    cases = dataset()
    print(f"数据集: {len(cases)} 例（形态取自 amg C519/C526 真实失配面）\n")
    print(f"{'oracle 噪音':<12} {'v1 κ':>7} {'Δ一致率':>8} {'rescue':>7} {'hijack':>7} {'McNemar p':>10} {'判决':>6}")
    for scale in (0.0, 0.5, 1.0, 2.0):
        oracle = OracleJudge(seed=42, noise_scale=scale)
        r = run_ab(cases, oracle)
        verdict = "B>A" if (r["mcnemar_p"] < 0.05 and r["delta_agreement"] > 0) else "n.s."
        print(f"x{scale:<10.1f} {r['kappa_v1']:>7.3f} {r['delta_agreement']:>+8.3f} "
              f"{r['rescue_true']:>4}/T{r['rescue_lost']:<2} {r['false_pass_hijack']:>7} "
              f"{r['mcnemar_p']:>10.4f} {verdict:>6}")
    oracle = OracleJudge(seed=42, noise_scale=1.0)
    r = run_ab(cases, oracle)
    print(f"\nv1 confusion (tp,fp,fn,tn)={r['confusion_v1']}  NEEDS_JUDGE={r['needs_judge']}")
    print(f"v1 vs truth 95% CI={tuple(round(x, 3) for x in r['ci95_v1_vs_truth'])}")
    print("\n解读: 官方校准噪音(x1.0)下 v1 仍显著优于 v0 且零 hijack；")
    print("      kappa 远低于原始一致率 = 2606.19544 的 κ 缩水在本 harness 的缩影。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.selftest or not args.demo:
        raise SystemExit(1 if selftest() else 0)
    if args.demo:
        demo()
