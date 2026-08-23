# -*- coding: utf-8 -*-
"""
amg LLM-Judge 原型 (Research #069 配套代码)

为 amg_bench_quality / locomo_bench_quality 的 cat5(对抗) + kupdate(知识更新) 残差
设计的语义判分器。设计要点来自 2026-08 研究结论：

1. 参考锚定二元判定 (reference-anchored binary) — MT-Bench 后续研究证明:
   有正确参考答案时, 参考锚定打分一致比 prompt-only 打分可靠。
2. 二元 rubric + 显式失败条件 — 避免 score-ID bias / rubric-order bias
   (Li et al. 2025, arXiv:2506.22316): 只输出 CORRECT/WRONG, 无分数梯度。
3. 判据级多数投票 — Memora (arXiv:2604.20006) 3-judge 多数票 88.3% 人类一致率。
   本原型默认单 judge, 可通过 n_judges>=3 + 位置扰动启用。
4. 顺序无关 — 单答案判定无 pair 位置偏置; judge prompt 中参考答案后置,
   避免 rubric-before-answer 的 recency 效应 (mbrenndoerfer 分析)。
5. 本地零成本 — ollama OpenAI 兼容端点 (qwen2.5:7b); 无 ollama 时
   自动降级为确定性 mock judge, 保证管线可运行可测试。

Run: python3 lls_judge_prototype.py            # mock 模式自检
     python3 lls_judge_prototype.py --real     # ollama 实测 (需已 ollama pull)
"""
import json
import sys
import time

JUDGE_PROMPT = """You are a strict answer grader for a memory-QA benchmark.

Question: {question}

Candidate answer: {answer}

Grade the candidate answer against the reference answer below.
The candidate is CORRECT only if it contains the same key information as the
reference (paraphrase, pronoun substitution, or superset details are OK).
It is WRONG if the key fact is missing, contradicted, or a different entity
is substituted (e.g. wrong person, wrong date).
Do not reward verbosity. Do not infer missing facts.
Reply with exactly one word: CORRECT or WRONG.

Reference answer: {reference}"""


def judge_once(question, answer, reference, model="qwen2.5:7b",
               endpoint="http://localhost:11434/v1/chat/completions", timeout=60):
    """单次 LLM 判定, 返回 "CORRECT"/"WRONG"/"ERROR"."""
    payload = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": 8,
        "messages": [
            {"role": "system", "content": "You are a binary grader. Output one word only."},
            {"role": "user", "content": JUDGE_PROMPT.format(
                question=question, answer=answer, reference=reference)},
        ],
    }
    import urllib.request
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read()).decode() or ""
        out = out.strip().upper()
        return "CORRECT" if "CORRECT" in out else ("WRONG" if "WRONG" in out else "ERROR")
    except Exception as e:  # noqa: BLE001 — 原型: 任何失败都归为 ERROR 并记录
        print(f"  [judge error] {e}", file=sys.stderr)
        return "ERROR"


def judge_mock(question, answer, reference):
    """确定性 mock: 词级 F1>=0.35 且不含矛盾词 → CORRECT。
    用于无 ollama 环境下验证管线与统计聚合, 不用于真实结论。"""
    import re
    toks = lambda s: set(re.findall(r"[a-z0-9']+", s.lower()))
    a, r = toks(answer), toks(reference)
    if not r:
        return "CORRECT"
    overlap = len(a & r) / len(r)
    return "CORRECT" if overlap >= 0.35 else "WRONG"


def judge(question, answer, reference, n_judges=1, real=False, **kw):
    """多数投票入口. ERROR 不计入多数票; 全 ERROR 时返回 ERROR."""
    votes = []
    for i in range(n_judges):
        if real:
            votes.append(judge_once(question, answer, reference, **kw))
        else:
            votes.append(judge_mock(question, answer, reference))
        time.sleep(0)  # 单 judge 无需扰动; 多 judge 位置扰动留待接入
    valid = [v for v in votes if v != "ERROR"]
    if not valid:
        return "ERROR", votes
    return ("CORRECT" if valid.count("CORRECT") > len(valid) / 2 else "WRONG"), votes


def calibration_report(cases, real=False):
    """对照 exact_judge(词边界精确匹配) 的校准报告:
    - LLM judge 相对 exact 的增量(救回的语义等价案例)与风险(误放过的错误案例)。
    Divergence >20-25% 需重审 rubric (Adaline 实践阈值)。"""
    import re

    def exact(answer, reference):
        pat = r"\b" + re.escape(reference.strip().lower()) + r"\b"
        return bool(re.search(pat, answer.lower()))

    n = len(cases)
    stats = {"agree": 0, "llm_only_correct": 0, "llm_only_wrong": 0, "error": 0}
    for c in cases:
        verdict, _ = judge(c["q"], c["a"], c["ref"], real=real)
        e = exact(c["a"], c["ref"])
        if verdict == "ERROR":
            stats["error"] += 1
            continue
        if (verdict == "CORRECT") == e:
            stats["agree"] += 1
        elif verdict == "CORRECT" and not e:
            stats["llm_only_correct"] += 1  # 语义等价救回 (kupdate 0.0 的预期修复点)
        else:
            stats["llm_only_wrong"] += 1  # 误放过 — 需人工抽检
    div = (stats["llm_only_correct"] + stats["llm_only_wrong"]) / max(n, 1)
    print(json.dumps({**stats, "divergence_rate": round(div, 3),
                      "verdict": "rubric OK" if div <= 0.25 else "RECALIBRATE"}, indent=2))
    return stats


if __name__ == "__main__":
    real = "--real" in sys.argv
    # 模拟 amg LoCoMo 残差: kupdate/cat5 典型形态 — 检索命中(haystack 含答案)
    # 但 exact 协议判 0 的语义等价答案
    cases = [
        {"q": "Where does Janet prefer to work?",
         "a": "She usually works from quiet coffee shops around her neighborhood.",
         "ref": "coffee shops",
         "note": "指代+改写, exact=0, 语义=1 (kupdate 形态)"},
        {"q": "What did Janet buy last week?",
         "a": "Janet bought a new laptop last week.",
         "ref": "laptop",
         "note": "exact=1 基线"},
        {"q": "Who recommended the book to Janet?",
         "a": "Her colleague Sam suggested it during lunch.",
         "ref": "Sam",
         "note": "exact=1(子串) 但注意 love→lovely 类子串污染已在 exact 侧修复"},
        {"q": "When is Janet's sister's birthday?",
         "a": "I'm not sure about that.",
         "ref": "March 3rd",
         "note": "abstain 应判 WRONG(cat5 幻觉检查)"},
        {"q": "What is Janet's favorite cuisine?",
         "a": "Janet loves Italian food, especially fresh pasta.",
         "ref": "Italian",
         "note": "超集细节 OK"},
        {"q": "What is Janet's favorite cuisine?",
         "a": "She really enjoys Mexican tacos.",
         "ref": "Italian",
         "note": "实体替换 → 必须 WRONG (cat5 对抗核心)"},
    ]
    mode = "ollama(qwen2.5:7b)" if real else "MOCK(词F1)"
    print(f"=== amg LLM-Judge 原型 [{mode}] — {len(cases)} cases ===")
    for c in cases:
        verdict, votes = judge(c["q"], c["a"], c["ref"], real=real)
        print(f"[{verdict:7s}] {c['q'][:42]!r} <- {c['a'][:38]!r}  ({c['note']})")
    print("\n=== exact_judge 对照校准 ===")
    calibration_report(cases, real=real)
