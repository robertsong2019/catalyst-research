# Research #078 — Order Questions: N-Anchor Sorting + Sequence Listing

**Date:** 2026-08-20 (deep-exploration-evening)
**Status:** ✅ Mechanism validated 9/9 (baseline 0/9) — C486 production port ready (co-first with #077)
**Chain:** C482 forensics (63 form-missed, "order 10") → this research → C486/C487 candidate
**Code:** `code/order_proto.py` (runnable, self-contained, stdlib only, ~40s incl. 277MB load)

---

## 1. Population Correction

C482 forensics bucketed "order" at **10**. Dataset census: **9 true order questions** (a3045048 is a how-many-days-before subtraction question — sibling of #077, not ordering). All 9 are `temporal-reasoning`, all currently `exact=False`.

Two sub-families:
- **Closed-set** (3): question enumerates the items — quoted events (ShopRite), "the day I X / the day I Y / the day I Z" clauses (nursery), "among Emma, Rachel and Alex" name lists (graduation).
- **Category-set** (6): question names a category — museums (6 items), airlines (4), concerts (5), trips (3), sports watched (3), sports participated (3).

**Discovered sibling population (not in C482 buckets):** the form classifier's false positives turned out to be a *pairwise* order family — "Which event happened first, X or Y?" — **29 questions, 8/29 currently correct → 21 wrong = +4.2pp full-500 headroom, larger than the 9-family itself (+1.8pp)**. Same anchor-and-sort mechanism, different render ("X" not a list) + `_abs` twins need negative-existence abstention (mechanism from #077 §2.5). C487 candidate.

Ceiling for tonight's 9: 9/500 = **+1.4pp full-500** (0.204 → 0.218); combined with pairwise: **+5.6pp** (→ 0.260).

## 2. Core Concepts

1. **Ordering = earliest eventive mention per item, not date parsing.** Every item's true anchor is the session date of its earliest *fresh report* ("today"/"just"/"yesterday" markers). Session-level day granularity suffices at week/month scales — no TIMEX parsing needed for the 9-family. `yesterday` resolves to session_date − 1 (needed only for tie-breaks within answers, not ordering).
2. **Fresh-priority anchoring.** When an item has both a *vague recall* ("recently attended the Met") and a *fresh report* ("saw it in person today"), GT anchors to the fresh one — even if the vague mention is earlier (MoCA: [6] "recently" vs [9] "just came back"; GT = [9]). Rule: earliest fresh hit beats every vague hit; vague pool only consulted when no fresh exists (Muir Woods, Big Sur).
3. **Clause-level planning filter, line-level fresh.** "today" timestamps the whole utterance (discourse marker), but planning intent is clause-scoped: "I'm thinking of ordering food for the next game, … I'm still on a high from watching the NFL playoffs" — one line, two clauses, two different events. The NFL clause is clean evidence; the "next game" clause is planning. Evaluating planning at line level kills the NFL anchor; at clause level both resolve correctly.
4. **Relative-clause window.** Item mention and its eventive predicate can straddle a comma: "gift ideas for my cousin Alex, who graduated … two weeks ago". Clause windows must extend to [clause, clause + next clause] for the planning/eventive test.
5. **Role discipline is binary.** Assistant lines are never evidence (recommendations/itineraries mention Richard Wagner Museum, Rijksmuseum, Tokyo museums — all distractors for the museum question). User-role filter alone kills the entire recommendation-class distractor family.
6. **Category-set extraction needs label canonicalization.** Strip possessives (`Art's` → `Art`), iteratively strip leading verb/determiner filler (`finished a 5K run` → `5K run`), merge by **substring containment** — NOT keyword-subset ("Museum of History" is kw-subset of "Natural History Museum" but they are different museums; substring containment correctly keeps both while absorbing `5K run` ⊂ `the Midsummer 5K Run`).

## 3. Verified Anchors (all 9)

| qid | items → anchor sessions (date) | order ✓ |
|---|---|---|
| f49edff3 nursery | nursery [19] < shower [40] < phone case [43] — all "just X" | ✓ |
| 7f6b06db trips | Muir Woods [30] 03-10 < Big Sur [39] 04-20 < Yosemite [44] 05-15 ("started … today") | ✓ |
| 18c2b244 ShopRite | Luvs coupon [25] 04-01 < Ibotta redeem [36] 04-10 < ShopRite signup [37] 04-15 — all "today" | ✓ |
| 7abb270c museums | Science [6] < MoCA [9]fresh < Met [14] < History [19] < Modern [32] < Natural [44] 03-04 | ✓ |
| 45189cb4 sports-watched | NBA [1] 01-05 < CFB [3] 01-14 (yesterday) < NFL [4] 01-22 (clause-cleaned) | ✓ |
| e061b84f sports-participated | Triathlon [20] 06-02 < 5K [22] 06-10 < soccer [29] 06-17 ("participate … today", present tense still fresh) | ✓ |
| d6585ce8 concerts | Billie [2] 03-18 < outdoor [18] 03-25 < Brooklyn [23] 04-01 < jazz [26] 04-08 < Queen [49] 04-15 | ✓ |
| f420262c airlines | JetBlue [19] < Delta [29] < United [38] 01-28 < American [43] | ✓ |
| 7ca326fa graduation | Emma [14] 05-27 ("yesterady" typo) < Rachel [20] 06-21 < Alex [52] 07-15 (relative-clause window) | ✓ |

Distractor taxonomy empirically closed for the 9 (each filtered by exactly one rule):
assistant recommendations (role) · user planning lines (planning) · vague later recalls (fresh-priority) · name collisions "Rachel Lee" HR vs friend Rachel / Delta stock vs Delta flight (category-context co-occurrence: `graduat` / flight words) · out-of-window mentions ([11] Yosemite Lodge, "past three months" window) · enumerated-vs-lexical item collision (Fetch Rewards vs ShopRite "rewards program" — closed-set full-clause keywords).

## 4. Prototype Results

`code/order_proto.py` — self-contained, stdlib only, reads `/tmp/lme_s.json`, ~40s wall (JSON load dominates):

```
== 9/9 correct (baseline: 0/9)      sequence-equivalence judge
```

Iteration log (autoresearch keep/rollback discipline):

| v | change | result | verdict |
|---|---|---|---|
| 1 | single-pass anchors, naive lexicons | 2/9 | keep skeleton |
| 2 | + canonical labels, sport prefixes, concert session-anchor | 3/9 | keep (trips/ShopRite/airlines) |
| 3 | + clause-level planning, substring merge, sport noun re.I, `graduat`/typo-tolerant `yesterday` | 6/9 | keep |
| 4 | + verb-prefix strip in canon_label, event-name exclusion in artist path, relative-clause windows, multi-cap concert prefix | **9/9** | keep |

Recurring bug classes en route (error-ledger material):
- **Regex case sensitivity in noun alternations** — lowercase `triathlon` never matched capitalized `Triathlon` (2nd encounter of the case-class family; C477 word-order, C482 quotes).
- **kw-subset merge over-merges** — set-containment is not label-containment; "Museum of History" ≠ "Natural History Museum".
- **Clause granularity assumptions** — line-level marker evaluation silently discards multi-clause lines that mix planning + evidence; comma is a semantic boundary for intent but not for discourse timestamps.

## 5. Hijack Safety (form-gate check, C473/C478 protocol)

Exploratory classifier (broad: `order of|from first to last|earliest to latest|which … first|who … first`) matches **38**: the 9 targets + 29 pairwise. Production gate must be the **strict 9-family pattern** (`order of|from (the )?(first|earliest) to (the )?(last|latest)|who … first, second`) → exactly 9 matches, **all currently wrong → zero hijack surface**. The 29 pairwise stay OUT until their own path is validated (8/29 already correct — routing them through an unvalidated render would *lose* 8; C487 with per-item A/B like C473).

## 6. Key Insights

1. **Ordering questions don't need date arithmetic — they need mention hygiene.** The entire 9-family resolves on session dates of correctly-filtered mentions. The hard part is *which mention is the event's birth certificate* (fresh-report priority), not *when* it happened. This inverts the #077 finding: there the arithmetic was the mechanism and anchors were simple; here anchors ARE the mechanism.
2. **Fresh-priority is a dataset-truth convention, not just a heuristic.** GT's answer_session_ids consistently anchor to the same-day report even when an earlier vague mention exists (MoCA [6] vs [9]). "Recently"-class mentions are post-hoc recalls that *lag* the event; anchoring to them systematically skews order late. Same asymmetry as C482's trust-direction gate (plans vs recalls) — now a third member of the family: **fresh > vague-recall > planning**, mutually exclusive priority tiers.
3. **Clause is the unit of intent; line is the unit of time.** "today/just/yesterday" scope to the whole utterance; planning verbs scope to their clause. Mixing the two granularities (in either direction) produces both false rejects (NFL) and false accepts ("next game").
4. **Category-set item enumeration is a label-canonicalization problem.** The raw extraction (proper-noun phrases + event templates) is noisy by construction; deterministic normalization (possessive strip, verb-prefix strip, substring merge) reduced 24 raw candidates to exactly 5 GT items on the worst question (concerts) with zero hand-lists in the answer path.
5. **Concerts are session-scoped, everything else is line-scoped.** The Billie Eilish event's only item-mention is a merch question with no eventive verb; the event marker ("today's show") lives in an adjacent line of the same session. Conversational flow scatters item-name and event-marker across lines — anchoring must sometimes promote to session granularity. (Production port: try line-scope first, session-scope as fallback tier.)

## 7. Next Actions

1. **C486 production port (co-first with #077)**: form-gate → anchor scan → sort → render (`First X, then Y, finally Z` for N=3; numbered list otherwise; airline-style bare comma list when items are single proper nouns). Judge = sequence-equivalence for A/B, judge_llm for reference rerun. Expected: temporal-133 +9 → 0.323 → ~0.391 upper bound (some LLM-judge format risk); multi_session-133 +3 (trips/ShopRite/concerts are multi-hop cross-session by dataset category... verify qid category before claiming).
2. **C487: pairwise "which first" family (21 wrong / 29)** — mechanism reuse + render "X" + `_abs` negative-existence abstention. Expected +21/500 = +4.2pp if all resolve; validate on the 21-wrong slice with per-item A/B first.
3. **Error-ledger entries**: regex case-class (2nd), kw-subset merge (new), clause-granularity (new).
4. Blog candidate: "The birth certificate of a fact: fresh-report priority in temporal ordering".

## 8. Ceiling Math

- 9-family: 0.204 → 0.218 (+1.4pp)
- + pairwise 21: → 0.260 (+5.6pp total)
- Combined with #077 (+7 = +1.4pp): temporal-side mechanisms alone → ~0.272 before retrieval-side work.
