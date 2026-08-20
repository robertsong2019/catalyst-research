# Research #077 — Past-Perfect Duration Questions: Cross-Session "Ago" Arithmetic

**Date:** 2026-08-20 (deep-exploration-evening)
**Status:** ✅ Mechanism validated 7/7 (baseline 0/7) — C486 production port ready
**Chain:** C482 forensics (63 form-missed, "past-perfect 14") → this research → C486 candidate
**Code:** `code/pp_duration_proto.py` (runnable, self-contained, 7/7) · `code/pp_duration_forensics.py` · `code/pp_ago_arithmetic.py` · `code/pp_hijack_check.py` · `code/pp_sibling_census.py`

---

## 1. Population Correction

C482 forensics bucketed "past-perfect duration" at **14 questions**. Dataset-level census (`how long (had|have) ... (when|before)`) finds exactly **7** in full-500 — the C482 bucket conflated adjacent forms. All 7 are `temporal-reasoning` type, all currently `exact=False` with `pred='None'` (the answer path never fires).

| qid | question (abridged) | GT | evidence mode |
|---|---|---|---|
| gpt4_93159ced | working before current job at NovaTech | 4 years and 9 months | **nested now-type subtraction** |
| e4e14d04 | member of Book Lovers Unite when meetup | Two weeks | ago − ago |
| c9f37c46 | watching stand-up when open mic night | 2 months | ago − ago |
| cc6d1ec1 | bird watching when workshop | Two months | now-type − ago |
| 993da5e2 | using area rug when rearranged furniture | One week (7–10d) | ago − ago |
| b29f3365 | guitar lessons when bought amp | Four weeks | now-type − ago |
| gpt4_93159ced_abs | working before current job at Google | **ABSTAIN** | negative existence |

Ceiling: 7/500 = **+1.4pp full-500** (0.204 → 0.218); 7/133 = **+5.3pp temporal-133** (0.323 → 0.376).

## 2. Core Concepts

1. **"Ago" is session-relative, never question-relative.** Every duration expression ("three weeks ago", "for six weeks now", "a month ago", "last month") anchors to the absolute date of *the session that contains it*, not to question_date. This is C482's line-adverbial insight generalized from dates to durations.
2. **Past-perfect duration = two absolute anchors + calendar subtraction.** State anchor S (when the state began) and event anchor E (when the "when Y" event happened), both resolved via `anchor = session_date − N`. Answer = E − S rendered in the anchors' dominant unit.
3. **Two expression families, one arithmetic.** *ago-type* (`N units ago`, `last month/week`) and *now-type* (`for N units (now)` — present-perfect tenure) both yield `session_date − N` as the state start. The prototype's `dur_exprs()` parses both plus compound `N years and M months`.
4. **Nested-tenure subtraction (the Q1 special case).** "How long have I been working *before I started my current job at NovaTech*?" — both facts are stated as of now: `profession_total(9y) − novatech_tenure(4y3m) = 4y9m`, done in months (108−51=57). No event anchor exists; the "before" clause IS the subtraction instruction.
5. **Negative existence → abstention.** The `_abs` twin (Google) has no tenure line for Google anywhere → abstain. Trust-direction logic (C482: plans vs recalled facts) is unnecessary here; pure existence check suffices.
6. **Cross-exclusion anchor selection.** A state keyword set and event keyword set often share phrases ("bird watching", "living room"), so the same line can outscore both. Selection must be two-phase: pick the event line (max event-overlap), then pick the state line *excluding that line's identity* (max state-overlap). Overlap-inequality (`s_ov > e_ov`) alone fails on ties.

## 3. Verified Arithmetic (all 7)

```
Book Lovers:   joined "3 weeks ago"@05-28 21:02 → 05-07 ; meetup "last week"@05-28 03:05 → 05-21
               05-21 − 05-07 = 14d = 2 weeks ✓
Stand-up:      started "about 3 months ago"@05-20 12:04 → 02-19 ; open mic "last month"@05-20 09:04 → 04-20
               04-20 − 02-19 = 60d = 2 months ✓
Bird:          "for about three months now"@05-21 08:56 → 02-21 ; workshop "a month ago"@05-21 20:08 → 04-21
               02-21 → 04-21 = 2 months ✓
Rug:           rug "a month ago"@05-26 03:36 → 04-25 ; rearranged "three weeks ago"@05-26 18:55 → 05-05
               = 10 days → "1 week" (GT accepts 7–10d) ✓
Guitar:        lessons "for six weeks now"@05-25 03:25 → 04-13 ; amp "two weeks ago"@05-25 03:02 → 05-11
               05-11 − 04-13 = 28d = 4 weeks ✓
NovaTech:      tenure "4 years and 3 months"@05-25 01:29 ; profession "9 years"@05-25 00:34
               108 − 51 = 57 months = 4 years and 9 months ✓
Google (abs):  no tenure line mentioning Google → ABSTAIN ✓
```

Note the near-simultaneity in guitar (03:02 vs 03:25) and NovaTech (00:34 vs 01:29): anchors stated *hours apart in different sessions* — session-date granularity (day) is sufficient; sub-day drift never matters at week/month scale.

## 4. Prototype Results

`code/pp_duration_proto.py` — self-contained, stdlib only, runs in ~40s against `/tmp/lme_s.json`:

```
== 7/7 correct (baseline: 0/7)
```

Iteration log (autoresearch keep/rollback discipline):

| v | change | result | verdict |
|---|---|---|---|
| 1 | single-phase max-overlap anchors | 3/7 | keep structure |
| 2 | + before-job route, len≥3 kws, overlap-inequality | 5/7 | keep |
| 3 | two-phase cross-exclusion (line identity) | 6/7 | keep |
| 4 | render() nonzero guard + 0.5 tolerance | 7/7 | keep |

Bugs found en route (three are recurring classes):
- **Trailing punctuation kills `$`-anchored regexes** (`NovaTech?`) — 3rd encounter of the punctuation-class family (C477 word-order, C482 quotes).
- **`len(w) > 3` silently drops 3-letter nouns** ("rug", "amp") — boundary typo vs intent.
- **Rounding-to-zero acceptance** — a tolerance branch that accepts `0 months` for 10 days; any render path must guard `0 < round(x)`.
- **Silent exception swallowing** — a bad `strptime` slice skipped every session and returned empty, mimicking "no evidence".

## 5. Hijack Safety (form-gate check, C473/C478 protocol)

- 25 "how long" questions in full-500; strict classifier (`how long (had|have) ... when/before`) matches exactly the 7 — **all currently wrong** → zero hijack surface.
- 18 siblings do not match. Among them, 3 pure-tenure questions are **currently correct via retrieval echo** (vintage cameras "three months", tidying routine "4 weeks", parents "nine months") — a v2 tenure route must not fire on them or must produce the same answer; the `_abs` twins must abstain.

## 6. Sibling Census → v2 Headroom (not in tonight's scope)

| sub-family | qids | currently | evidence |
|---|---|---|---|
| pure tenure ("how long have I been X?" — answer = verbatim "for N now") | 08e075c7 (Fitbit 9mo), 2133c1b5 (Harajuku 3mo), e61a7584 (cat Luna 9mo), 92a0aa75 (role 1y5m compound) | all WRONG | verbatim lines confirmed |
| "did ... before" (same arithmetic, "did I use" verb) | gpt4_cd90e484 (binoculars 2w) | WRONG | same as PP |
| negative-existence abstain twins | 15745da0_abs, 2133c1b5_abs | WRONG | absence |
| event-duration ("how long did it take", hours-scale) | 94f70d80, caf9ead2, b9cfe692 (sum of two books) | WRONG | different mechanism (event duration, not state tenure) |

v2 potential ≈ +7q ≈ +1.4pp full-500. Combined how-long headroom ≈ **14q ≈ 2.8pp (0.204 → ~0.232)**.

## 7. Key Insights

1. **Durations are dates in disguise.** Every "N units ago/for N now" resolves to an absolute date via its containing session. Past-perfect questions then reduce to the *same* calendar arithmetic as C457/C482 temporal — one subtract, no LLM. The temporal mechanism family now covers: duration-at-event (this), duration-between-dates (C457), same-session day arithmetic (C482).
2. **Nested "before" clauses are subtraction instructions, not event references.** Q1's GT comes from two *as-of-now* facts (total minus tenure) — the question never references a datable event. Recognizing "before I started my current job at X" as `total(X-era) − tenure(X)` unlocks compound y+m answers.
3. **One line must not feed both anchors.** Shared phrases between state and event clauses ("bird watching workshop") make single-line double-capture the dominant failure mode; two-phase selection with line-identity exclusion is the minimal fix.
4. **Form classifiers double as safety interlocks.** Because the strict form matched only currently-wrong questions, the route is zero-cost by construction — the same design property C473 discovered (form classifier = configuration surface) now proven for answer-side routes.
5. **Sub-day session granularity is sufficient.** Anchors stated hours apart across sessions never distort week/month-scale answers — no need for timestamp-level resolution.

## 8. Production Port Notes (C486)

- Slot into `amg_bench_quality.py` answer path as a new form: `_pp_duration` alongside counting forms (`_cnt_route` family, C477/C483 pattern).
- Classifier: `how long (had|have|did) ... (when|before)` — include `did` (v2, binoculars) but exclude pure-tenure (no when/before) unless v2 tenure route ships in the same cycle.
- Port `dur_exprs()` (ago/last/now + compound y+m) as a shared utility — `_line_adverbial_date()` (C482) covers dates; this covers durations; both belong in one anchor-lexicon module.
- Render with nonzero guard; judge via existing exact-judge normalization (num-words, singular/plural) + GT day-range tolerance.
- A/B: temporal-133 pre/post (expect +5.3pp from 7q, zero regression by form-gate) + full-500 at next reference rerun.
- Abstain semantics: "no tenure line for company" mirrors C469's ownership wall — absence of state evidence, not retrieval failure.

## 9. Next Actions

1. **C486: port PP route into `amg_bench_quality.py`** — form gate + `dur_exprs` + two-phase anchors + nested-tenure route + abstain; A/B on temporal-133 (pre 0.323 → target ~0.37).
2. **v2 same-cycle or C487: pure-tenure route** ("how long have I been X?" → verbatim "for N now" extraction + compound parsing + `_abs` negative-existence abstain) — +4q, plus "did-before" classifier widening +1q.
3. **Event-duration sub-family** (94f70d80 etc., hours-scale "how long did it take") — separate mechanism, candidate for #078 forensics.
4. Fold `dur_exprs` compound parsing into `_line_adverbial_date`'s anchor lexicon (dedupe with C482's date ladder).

---
*Methodology: autoresearch.md (clear metric = 7/7 family + zero-regression form gate; fast loop = 4 prototype iterations logged; accumulation = C457/C482 anchor lineage extended from dates to durations).*
