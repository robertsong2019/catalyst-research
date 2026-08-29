#!/usr/bin/env python3
"""Research #090: 零依赖分层 Answer Equivalence (AE) 判分器原型.

文献锚点:
- Bulian et al., "Tomayto, Tomahto" (EMNLP 2022): 不对称 AE — 接受"等价于或优于参考答案";
  F1 两个实证缺陷: 虚假渐进性 / 与问题无关. 23k 人工标注方法论 = 本 fixture 的微缩版.
- Balamurali et al. 2025 (arXiv:2511.07659): 现成 NLI + 单个词法匹配旗标 ≈ GPT-4o 判分
  (89.9%) — 便宜混合判分器可达 LLM judge 平价.
- Gu et al. 2025 LLM-as-judge survey: position/verbosity/self-preference 偏差 →
  LLM judge 需双口径交叉验证, 不可单点采信.

v1 → v2 迭代记录 (autoresearch 快循环):
  v1: 0.550 (< exact 0.600), 3 false-accepts. 四个真 bug:
      ① 千分位逗号被 tokenize 剥掉 ($2,500 → "$2","500")
      ② 数字核等价无词法守卫 → "three years" vs "three years ago" 假接受
      ③ 包含层只写 pred⊇gt 单向; gold-containment 方向全漏
      ④ 形态层 (weekly/week) 不匹配
  v2: 修四 bug + 月名映射 + 序数后缀剥离 + 单位/功能词规范化.

设计: 分层短路判分, 每次接受带 tier 标签 (可审计, 同 amg judge_llm 双口径精神).
成功标准: 人工标注 fixture 上 accuracy >= exact-match + 15pp 且 false-accept == 0.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------- vocabulary

_WORD_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "twice": 2,
    "once": 1,
}
_MONTHS = {
    "jan": "january", "feb": "february", "mar": "march", "apr": "april",
    "jun": "june", "jul": "july", "aug": "august", "sep": "september",
    "sept": "september", "oct": "october", "nov": "november", "dec": "december",
}
_UNITS = {
    "dollars": "$", "dollar": "$", "usd": "$", "bucks": "$",
    "percent": "%", "percentage": "%", "yrs": "year", "hrs": "hour",
    "wks": "week", "mos": "month", "mins": "minute", "secs": "second",
}
_STOP = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "from",
         "with", "and", "or", "every", "her", "his", "their", "s"}
_DRIFT = {"ago", "about", "approximately", "nearly", "later", "before",
          "approximately", "roughly", "almost"}
_NUM_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


# ---------------------------------------------------------------- canonicalizer

def canon_tokens(s: str) -> list[str]:
    """NFKD → 归一化 token 流. C519 教训: fold 必须在 tokenize 前."""
    s = unicodedata.normalize("NFKD", s).lower()
    s = re.sub(r"(?<=\d),(?=\d)", "", s)          # ① 千分位在 tokenize 前合拢
    s = re.sub(r"([$%])(\d)", r"\1 \2", s)         # 货币/百分号与数字解粘连
    s = re.sub(r"[^\w\s$%]", " ", s)
    out = []
    for t in s.split():
        if t in _STOP:
            continue
        t = _MONTHS.get(t, t)
        t = _UNITS.get(t, t)
        t = str(_WORD_NUM[t]) if t in _WORD_NUM else t
        t = re.sub(r"(\d)(?:st|nd|rd|th)$", r"\1", t)   # 10th → 10
        if len(t) >= 5 and t.endswith("ly") and t[:-2] not in _WORD_NUM:
            t = t[:-2] if not t.endswith("ally") else t[:-4]  # weekly→week (粗)
        if len(t) >= 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]                                  # years→year (粗)
        if t:
            out.append(t)
    return out


def cset(s: str) -> set[str]:
    return set(canon_tokens(s))


def numeric_cores(s: str) -> list[str]:
    return sorted(t for t in canon_tokens(s) if t.isdigit())


def answer_type(a: str, b: str) -> str:
    if numeric_cores(a) or numeric_cores(b):
        return "numeric"
    if re.search(r"\b(19|20)\d{2}\b", a + " " + b):
        return "date"
    return "entity"


# ---------------------------------------------------------------- tiered judge

def answer_equiv_judge(pred: str, gt: str) -> tuple[bool, str]:
    """返回 (accept, tier). tier 记录命中层, 拒绝也带原因 — 可审计."""
    if not pred.strip() or not gt.strip():
        return False, "reject-empty"
    ps, gs = cset(pred), cset(gt)
    if ps == gs:
        return True, "T0-em"

    at = answer_type(gt, pred)
    if at in ("numeric", "date"):
        # ② 数字核等价 AND 非数字 token 集严格相等 — 数字型禁止词法兜底
        if numeric_cores(pred) == numeric_cores(gt) and ps - _digits(ps) == gs - _digits(gs):
            return True, "T1-numeric"
        return False, "reject-numeric-mismatch"

    # ③ 双向包含, 预算 ≤2 个额外词; 漂移守卫: 额外侧不得携带 hedge/temporal 标记
    if gs and gs <= ps and len(ps - gs) <= 2 and not (_DRIFT & (ps - gs)):
        return True, "T2-contain-specific"     # pred 优于参考 (BEM 方向)
    if ps and ps <= gs and len(gs - ps) <= 2 and not (_DRIFT & (gs - ps)):
        # 合取守卫: gold 含 ≥2 个专名时 pred 不得只覆盖真子集 (Kate↔"Kate and Anna")
        gt_pn = {w.lower().strip("'’") for w in gt.split()
                 if w[:1].isupper() and len(w) > 1}
        if len(gt_pn) >= 2 and not (gt_pn <= {t for t in ps}):
            return False, "reject-conjunct-subset"
        return True, "T2-contain-gold"         # pred 被 gold 包含 (不更精确但不错)

    # T3: gold 覆盖率 ≥ 0.8 + 专名守卫 (gold 有大写专名时 pred 须共享至少一个)
    if gs:
        cov = len(gs & ps) / len(gs)
        if cov >= 0.8:
            pn = {w.lower().strip("'’") for w in gt.split() if w[:1].isupper() and len(w) > 1}
            if pn and not (pn & {t for t in ps}):
                return False, "reject-person-guard"
            return True, "T3-entail"
    return False, "reject-lex"


def _digits(s: set[str]) -> set[str]:
    return {t for t in s if t.isdigit()}


# ---------------------------------------------------------------- fixture (BEM 23k 的微缩)

FIXTURE: list[tuple[str, str, bool, str]] = [
    # --- 应接受: paraphrase / word-number / unit / more-specific / gold-containment ---
    ("Shinjuku", "Shinjuku", True, "identity"),
    ("three years", "3 years", True, "word-number"),
    ("3 years", "three years", True, "word-number-rev"),
    ("$2,500", "2500 dollars", True, "money"),
    ("Tokyo", "Tokyo, Japan", True, "gold-containment"),
    ("Kate", "her sister Kate", True, "gold-containment-np"),
    ("climbing", "rock climbing", True, "narrowing"),
    ("the Fitbit tracker", "Fitbit tracker", True, "article"),
    ("Aragón", "Aragón", True, "unicode-nfkd"),
    ("The Legend of Zelda", "Legend of Zelda", True, "article-title"),
    ("weekly", "every week", True, "frequency-paraphrase"),
    ("Melbourne", "Melbourne, Australia", True, "gold-containment-city"),
    ("Jan 10, 2024", "January 10th 2024", True, "date-paraphrase"),
    # --- 应拒绝: 真错 / 部分错 / 语义漂移 / 过载 ---
    ("Harajuku", "Shinjuku", False, "neighbor-swap"),        # C513 近失陷阱
    ("3 years", "2 years", False, "number-mismatch"),
    ("Kate", "her sister Anna", False, "person-mismatch"),
    ("three years", "three years ago", False, "temporal-drift"),
    ("Tokyo", "Tokyo, Japan, in the summer of 2019 for a wedding", False, "overload"),
    ("2019", "January 2019", False, "date-imprecise"),
    ("climbing", "bouldering", False, "lex-near-miss"),
    ("24 hours", "about 24 hours", False, "hedged-numeric"),
    ("Kate", "Kate and Anna", False, "conjunct-subset"),   # 合取答案只答一半 (C447 同族)
]


def run_eval() -> dict:
    n = len(FIXTURE)
    exact_ok = sum(1 for p, g, l, _ in FIXTURE if (cset(p) == cset(g)) == l)
    ae_ok = sum(1 for p, g, l, _ in FIXTURE if answer_equiv_judge(p, g)[0] == l)
    false_accepts = [(t, answer_equiv_judge(p, g)[1]) for p, g, l, t in FIXTURE
                     if not l and answer_equiv_judge(p, g)[0]]
    misses = [(t, answer_equiv_judge(p, g)[1]) for p, g, l, t in FIXTURE
              if l and not answer_equiv_judge(p, g)[0]]
    return {"n": n, "exact_acc": exact_ok / n, "ae_acc": ae_ok / n,
            "false_accepts": false_accepts, "misses": misses}


if __name__ == "__main__":
    r = run_eval()
    print(f"fixture n={r['n']}")
    print(f"exact-match accuracy : {r['exact_acc']:.3f}")
    print(f"AE judge accuracy    : {r['ae_acc']:.3f}  (false-accepts={len(r['false_accepts'])}, misses={len(r['misses'])})")
    print(f"delta                : {r['ae_acc'] - r['exact_acc']:+.3f}")
    for label, items in (("FALSE-ACCEPT", r["false_accepts"]), ("MISS", r["misses"])):
        for tag, tier in items:
            print(f"  [{label}] {tag:24s} ({tier})")
    print("\ntier audit:")
    for p, g, l, tag in FIXTURE:
        ok, tier = answer_equiv_judge(p, g)
        flag = "OK " if ok == l else "MISS"
        print(f"  [{flag}] {tag:24s} -> {'accept' if ok else 'reject':6s} ({tier})  human={l}")
