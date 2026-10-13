# P168A vs PRECISE-F1-R1 — 50 real-DB paired A/B offline audit

Date: 2026-10-13 KST. Analysis is derived from the uploaded `prompt-ab-RUN-20261013-141831-538884.txt` run, **not from new Gemini calls**.

## Grounded run facts
- Run ID `RUN-20261013-141831-538884`; 14:18:23–14:27:41 KST. 50 source conversations, K2L 25 and L2K 25. **SAMPLE_MODE=NEW** (not the previously requested `REGRESSION_20`), therefore the four original regression cases that motivated F1 (#004, #030, #070, #083 in the **prior** 100-case run) are **not proven fixed** by this random/new-source run.
- A `P168A`, prompt SHA `7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43`; B `EXP-P168A-PRECISE-F1-R1`, SHA `9b8a3a34882e9ae06e594bf48695d79910112be6d1230ca86866e9e67abd6472`.
- Equal control `SMART_COMPARE_MODE=A_OFF_B_OFF_JSON`. `CHANGED_FIELDS=forward.k2l,forward.l2k`; eight SMART and four independent back/recovery prompts byte-identical in candidate. H2 diagnostic only.
- All 200 **client** calls complete: two forwards + their independent backs for every one of 50 source texts. No partial failures, no repair, forward/back single-pass errors all zero. This is **not** visibility into provider-internal retries.
- H2 `AUTO_QUALITY_EVALUATION=false`; semantic judgements are independent manual inspections of *source→forward* and *forward→back*, not automatic/native-Lao certification. A reverse failure must not be attributed to forward unless also supported by source→forward.

## Metrics (independent direct calculation from per-case timing + H2 summary)

| Measure | A P168A | B F1 |
|---|---:|---:|
| K2L forward first display average, n25 | 2357.9 ms | 2452.6 ms |
| L2K forward first display average, n25 | 2823.4 ms | 2901.9 ms |
| ALL first display average, n50 | **2590.6 ms** | **2677.2 ms** |
| ALL first display median | 2598.1 ms | 2549.3 ms |
| ALL first-display p95 | 3365.5 ms | 3847.5 ms |
| ALL average input tokens/forward | 1002 | 1082 |
| Forward calls with thought tokens | 1 / 50 | 1 / 50 |
| Forward thought tokens | 296 (#009) | 634 (#049) |
| Forward success | 50/50 | 50/50 |
| Back success (independent) | 50/50 | 50/50 |
| Estimated matched four-path cost, 50 cases | **$0.08289525** | **$0.08479950** |
| Estimated $ per 1000 comparable conversations | $1.657905 | $1.69599 |

- B−A first display mean +86.62 ms (3.34% slower), **median paired delta +74.25ms**. B slower 27/50, faster 23/50.
- Same source/no forward thoughts on either lane for 48/50 cases: paired B−A average **+42.14 ms**. Isolated outliers: #009 A 296 thought (A 4.399s, B 1.993s); #049 B 634 thought (A about 2s, B delayed by 4.714s). **F1 did not reproduce the C2 thought-token explosion.** It also does not establish any F1 speed improvement.
- L2K providerMs A 1870.68ms, B 1892.48ms, difference +21.8ms average. K2L direct path has no provider header, not zero processing.
- Four-path uncached **cost estimate** is +2.30% for B, model tokens incl thinking, not an actual invoice. Costs for both complete paths are populated, unlike C2 MAX_TOKENS cases.
- H2 test environment `visibility:hidden, online:true, effectiveType:4g`. This run cannot isolate provider global load or network congestion across different days.

## Critical quality findings

### Mandatory blockers, attributable at the right stage
- **#013 K2L, B forward critical medical-term regression:** source "임신호르몬 검사인 HCG" / A Lao `ຮໍໂມນຖືພາ`; B Lao `ຮໍໂມນການຕັ້ງຄ່າ` ("configuration/setting hormone"). Independent B back exposes "설정 호르몬". The failure **starts in the forward text**, not just reverse. Serum CBC-vs-hCG identity still preserved but the key hormone concept was corrupted. High-consequence.
- **#011 K2L B forward added waiting:** source only "기숙사에서 쉬고 있으면 되겠다", B Lao introduces `ຖ້າ` wait/conditional-looking wording and independent B back says "쉬면서 기다려도 돼". A has no waiting; B forward semantic addition.
- **#014 L2K B forward source ambiguity forced to "6번(장)"** and outputs multiple unchosen alternatives "설정할게(고를게)". Lao STT text is materially corrupted with repeated numerals; guessing sixth photo is **not demonstrably licensed**. A preserves photo-selection intent more conservatively. B independent back converts into "6번 사진", repeating unsupported concretization.
- **#040 L2K B forward clinic→"클리닉(병원)"**: source names only a clinic; B offers facility alternatives where single faithful output is required. B independent back echoes clinic/hospital alternatives. A clean.
- **#010 L2K B forward and B back specify 시부모님** where source says only `ພໍ່ແມ່` (parents) without kinship side. Context may make this plausible, but the translation must not silently commit; A remains neutral. Both A and B independent backs expose slash alternatives for `ນ້ອງໄພ້`, a separate **shared independent-back output** problem.
- **#023 K2L B forward aspect:** source says "군것질이라도 **하는 게 좋겠다**" (recommendation/assessment); B uses `ໄດ້ກິນ`, and B back "간식이라도 **먹었으니** 다행이야" (already ate). A closer to prospective recommendation.
- **#050 L2K B forward omitted `ຫໍ່` wrapper/packaging on fermented pork and narrowed identity to "발효 소시지"; B back reconstructs just `ສົ້ມໝູ` plus sausage expansion. A preserves `ຫໍ່`. Food morphology/class warrants Lao-native review.
- **#049 K2L B independent back softens** "내년에 오는 건 내가 안 괜찮아" into "별로 내키지 않아"; B forward `ບໍ່ໂອເຄ` remains strong, so the evidence points **primarily to backward softening**.
- **#042 L2K B independent back** switches to Latin English `ultrasound` twice and introduces `ຫາເກີດໄດ້ປະມານ 3 ອາທິດ` ("born ~3 weeks" literal reading), not valid pregnancy-week phrasing. B forward Korean is broadly faithful; failure is **independent back**, not proof B forward is defective.
- **#003 K2L B independent back** changes husband's casual "응, 알았어" to polite "네, 알겠어요"; Lao forward remains similar to A. Independent-back register drift.
- **#025 K2L shared issue:** "저녁식사가 갑자기 엄청 건강해진 것 같아" is returned via independent backs as "뜻밖의 저녁 식사" and an additional third-party "felt/said"; both A/B forward phrasing warrants review.
- **#041 K2L source contains STT typo `바애프다고`**, A guessed busy and B guessed ill; cannot declare either correct without original intended phrase. Treat source ambiguity independently.

### Examples of legitimate improvements, not sufficient to promote F1
- **#007 K2L** original affection "마구 사랑해줬을텐데": A back "사랑한다고 많이 말" narrows physical/expressive affection to verbal declarations; B back "마음껏 사랑도 표현" preserves breadth.
- **#017 K2L** B back "움직일 생각도 하지 말고" tracks original more closely than A "어디로든 꼼짝도".
- **#019 K2L** A independent back substitutes "쌀국수" for original "죽", B independent back returns "죽", while both Lao forwards chose `ເຂົ້າປຽກ` and fidelity of intended Lao food should be reviewed. Since backs are unchanged, improvement may reflect normal model variation or forward wording.
- **#008 L2K** B forward "스르륵 잠들지" captures `ເຜີຫຼັບ` (doze off) better than A's plain "잠들지".
- **#024 L2K** B avoids A's unsupported inference about travel time and states the journey intention.
- **#028 L2K** B forward "체한 건 아니야" is closer to original `ບໍ່ແໝ້ນທ້ອງ` than A's "배탈 난 건 아닌데"; A back confirms stomach upset while B back restores `ແໜ້ນທ້ອງ`.
- **#036 L2K** A and B preserve mother/financial help/avoid borrowing, B slightly more idiomatic.
- **#043 K2L** both preserve photo album functionality, today-morning repair with no meaningful change.
- **#047 K2L** B back preserves praise for hard studying slightly more naturally.

## All 50 cases, four-path manual triage
Legend: `B+`=B output(s) substantively preferable; `A+`=A preferable / B regression; `≈`=materially comparable; `?`=STT/context uncertainty; `BACK`=independent back-specific issue. An opinionated triage for review; **not quantitative native translation grading**.

| # | Dir | Triage | Note |
|---:|---|---|---|
| 001 | K2L | B+ minor | natural `ທີ່ຮັກ` address; both preserve early/health advice |
| 002 | L2K | ≈ | people cooking; noodles after a while preserved |
| 003 | K2L | A+ BACK | B back unexpectedly polite |
| 004 | L2K | A+ minor | B awkward "와서 쉬면서 누워", A concise |
| 005 | K2L | ? shared | source "생활 축하" possibly STT error; both render celebrate life, no unsupported substitution |
| 006 | L2K | ≈ | mother, brother meeting and currency exchange preserved |
| 007 | K2L | B+ | broad affection better than A back's only saying love |
| 008 | L2K | B+ | dozing off nuance |
| 009 | K2L | ≈ | both good, A had 296 thought tokens |
| 010 | L2K | A+ / BACK shared | B commits to in-laws; both reverse slash alternatives |
| 011 | K2L | A+ | B adds waiting |
| 012 | L2K | A+ minor | B chronology awkward "쉬고 나면 자고 일어나서" |
| 013 | K2L | A+ CRITICAL | B corrupts pregnancy hormone to setting hormone |
| 014 | L2K | A+ HIGH | B guesses sixth image, slash/parenthetical alternatives; STT malformed |
| 015 | K2L | ≈ | first photo retouch after meeting wife, worksite photos |
| 016 | L2K | A+ minor | B forward omits explicit work reason; B back recovers it |
| 017 | K2L | B+ minor | advice to stay put and order delivery preserved |
| 018 | L2K | ≈ | school hours/homework/rest, B "수업" natural |
| 019 | K2L | mixed, B+ BACK | B back preserves porridge vs A back rice noodles; B forward loses quote typography |
| 020 | L2K | ≈ | exact same forward, clean back |
| 021 | K2L | ≈ | exact same forward; both backs say confirm/check |
| 022 | L2K | ≈ / BACK risk | B reverse adds stomach-tightness nuance |
| 023 | K2L | A+ | B turns recommendation into eating already completed |
| 024 | L2K | B+ | B does not invent "travel consumes time" |
| 025 | K2L | ? shared | both change sudden healthy dinner into unexpectedly obtained dinner |
| 026 | L2K | ≈ | outdoors cooler than air-conditioned room |
| 027 | K2L | ≈ | intermittent symptoms, husband would pat back |
| 028 | L2K | B+ | indigestion vs stomach upset; clinician context |
| 029 | K2L | ≈ | "that's it" and laughter |
| 030 | L2K | ≈ | identical forward, meeting again |
| 031 | K2L | ≈ | reassurance preserved |
| 032 | L2K | ≈ | uncertain two weeks, possible nuance go/stay |
| 033 | K2L | ≈ | ask doctor tomorrow before decision |
| 034 | L2K | ≈ | eat/sleep, wash and walk |
| 035 | K2L | ≈ | early pregnancy faint test result |
| 036 | L2K | ≈ / B+ minor | mother borrowing elsewhere, financial help |
| 037 | K2L | ≈ | stress, anger and reassurance; B more natural address |
| 038 | L2K | ≈ | don't rush telling |
| 039 | K2L | ≈ | upload many photos; B back adds "줘" |
| 040 | L2K | A+ | B clinic/hospital multiple-choice contamination |
| 041 | K2L | ? SOURCE | `바애프다고` malformed, A busy vs B sick |
| 042 | L2K | A+ BACK | B back English ultrasound & "born in 3 weeks" |
| 043 | K2L | ≈ | photo album |
| 044 | L2K | ≈ | exact money 480k vs 500k preserved |
| 045 | K2L | ≈ | birthday and Facebook |
| 046 | L2K | ≈ | all visible food edible |
| 047 | K2L | B+ minor | studying hard, more needed? |
| 048 | L2K | ≈ | photographer vs photo studio ambiguous; retouching consistent tone |
| 049 | K2L | A+ BACK minor | B back weakens objection to next-year arrival |
| 050 | L2K | A+ | B drops wrapped-food form, over-specifies sausage |

## Decision and next action

**F1 QUALITY HOLD, NO SERVICE PROMOTION.** Strong #013 medical lexical regression is enough for hold. B's minor improvements are real but don't outweigh material additions/concretizations in #011/#014/#023/#040. Because this test used `NEW` and contains no exact target original 4 texts, no established evidence those four defects are fixed.

**Do not ask the user to rerun 50 or 100 new random cases.** Next controlled investigation can be done **offline** with both prior 100-case record and this 50-case log. If a new F2 candidate is developed, isolate the medical-term guard and restrict changes to one direction per controlled step; retain original back and SMART. For direct proof of the intended four repairs, use the *existing* H2 capabilities if it supports exact fixed-case injection; do not falsely claim `REGRESSION_20` guarantees inclusion of specific historical cases. All paid tests need user initiation. Do not patch model output cap/server. Prioritize quality and independent back parity before cost/speed micro-optimizations.

SERVICE baseline V3.61.209/P168A R8/G158A unchanged. No DB, Cloudflare, or backend modifications were performed.
