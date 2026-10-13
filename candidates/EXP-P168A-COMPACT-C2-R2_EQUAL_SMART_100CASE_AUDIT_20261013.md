# Equal-SMART 100-case offline A/B audit — 2026-10-13

## Verified provenance / isolation

- Original user-supplied H2 log: `prompt-ab-RUN-20261013-133128-97e259.txt`, run `RUN-20261013-133128-97e259`, 2026-10-13 13:31–13:51 KST.
- 100 fresh, real-use conversations: K2L husband 50, L2K wife 50, paired A/B by source in each record.
- Baseline A: P168A SHA `7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43`.
- Candidate B: EXP-P168A-COMPACT-C2-R2 SHA `606f1f2c3a755aea0a38c192aec446d58868b35fd17793cb31d1d84f45920cdc`.
- **Correct controlled mode** `SMART_COMPARE_MODE=A_OFF_B_OFF_JSON`, scope ALL. This supersedes the previous confounded 50-case `A_OFF_B_ON_JSON` run. Do not pool absolute comparisons across different sample sets.
- 399 client Gemini calls attempted; expected 400, one B forward failed, so no B back on that case. No observed extra client forward/back generations; provider-internal retries unavailable. No new paid calls for this audit. SERVICE, DB, backend, Cloudflare, H2 untouched.
- Semantic assessments below are manual source→forward and forward→independent-back comparisons, *not automated quality scores* and *not native-speaker Lao certification*.

## Latency and thoughts

| Metric | A P168A | B C2-R2 |
|---|---:|---:|
| Forward first display mean, observed successful | 2708.5ms (n100) | 3245.1ms (n99) |
| First display median | 2570.5ms | 2869.6ms |
| First display p95 | 3704.1ms | 6064.8ms |
| Mean forward input tokens, successful | 997.9 | 408.6 |
| Thought-positive forward calls, **all traces including failed** | **5/100** | **29/100** |
| Total logged forward thought tokens, including failed | 2204 | **11183** |
| Thought-positive successful forward calls | 5/100 | **28/99** |
| Thought tokens successful only | 2204 | **10201** |
| Forward success | 100/100 | 99/100 |
| Independently generated back success | 100/100 | 99/100 (B #061 not attempted) |

- Per direction thoughts, all traces: K2L A2/797, B14/6782 (includes failed #061 982); L2K A3/1407, B15/4401.
- Same-record paired successful first displays: 99 matches, B−A mean **+534.3ms**, median **+207.6ms**, B slower 64/99.
- Both A and B without forward thoughts **67 pairs**: B−A mean **+25ms**, median +61ms; B slower 37/67.
- Only B with forward thoughts **27 pairs**: B−A mean **+2436ms**, median +2259ms; B slower **27/27**.
- Only A with forward thoughts 4 pairs: B faster by mean 2462ms. Both thought-positive 1 pair: B faster by 4668ms. Failed B #061 excluded from paired first display.
- On L2K (Cloudflare path), mean paired B−A first-display difference +382.8ms = observed providerMs delta +378.3ms and residual +4.4ms. This is association, not a claim to measure Gemini's unexposed internal thinking duration.
- Four-path independent back durations: husband A mean 2255ms (n50), B mean 2017ms (n49); wife A 2989ms (n50), B 3122ms (n50). Back thought occurrences A5 (1667 tokens) vs B3 (515 tokens); back prompts identical per candidate, variations cannot be attributed to back prompt changes.
- **Failure** K2L #061 B `FINISH_MAX_TOKENS` with 982 thought tokens, 38 answer tokens, `maxOutputTokens=1024`; B forward not accepted and B independent back not run. A success. The similar previous 50-case B #046 was also capped after 979 thoughts under different SMART settings. No silent claims of an output-cap fix.

## Cost: strictly complete matched four-path data

Rate from H2 (uncached estimate, not invoice): input $0.75/M; output including thoughts $3.75/M.

| Same complete records | A USD | B USD | B/A |
|---|---:|---:|---:|
| Husband K2L, 49 | 0.08591025 | 0.07791375 | −9.31% |
| Wife L2K, 50 | 0.07909800 | 0.06964950 | −11.95% |
| **Total, 99** | **0.16500825** | **0.14756325** | **−10.57%** |

- Exclude #061 from BOTH lanes to avoid treating unobserved B back usage as zero. H2 correctly sets 100-case B `totalUsd=null` because a four-path record is incomplete.
- B #061 nevertheless incurred recorded forward use (384 input, 38 answer, 982 thoughts); actual billed amount unknown.
- Lower estimated token cost does not offset observed first-display deterioration and MAX_TOKENS failure.

## Four-path qualitative review, focus on actionable cases

### Husband K2L forward and independent Lao→Korean back
- #003 A independent back changed **our/we** to **I**; B independent back preserved **we**. Good B chain.
- #005 A back implied the speaker himself would go tomorrow; B back restored husband inferring **wife** was going tomorrow. B good.
- #007 source refers to photo **retouching**; B Lao and back use retouch/edit more precisely than A generic change/modify.
- #011 A back changed congratulating into praise; B back preserved congratulating/blessing. B improvement though `ອວຍພອນ` is more expansive than plain congratulations.
- #035 A forward produced slash alternatives `ແຕກ/ຂີ້ຮ້າຍ`; B provided one clear reading. B improvement.
- #049 A independent back turned couple's casual Korean into repeated `-요` formality; B preserved casual tone.
- #069 A independent back invented **good hospital** and became polite; B restored 'get checked and come back', though B independent back also polite. Distinguish forward correctness from back-register drift.
- #083: source asks for **진단서** (medical certificate/diagnosis document) and blood result. A Lao uses `ໃບຢັ້ງຢືນການແພດ`; B `ໃບຢັ້ງຢືນການກວດພະຍາດ`, and B back became **진료 확인서**, not 진단서. Potential document-type regression in high-consequence paperwork context.
- #085 A forward/back reduced 'you worked so hard' to 'you are tired'; B partially restored **고생 많았어**, although residual '피곤하네' remains. B improvement but not perfect.
- #089 B preserved October 18/24 distinctions and tentative plans.
- #099 source '너무 다행이다' (relief), A back '기쁘네' (happiness), B back preserved relief.
- #061 B forward failed MAX_TOKENS; severe reliability regression.

### Wife L2K forward and independent Korean→Lao back
- #002 source proverb `ອົດສົ້ມຈື່ງໄດ້ກິນຫວານ`: B preserves literal **sour→sweet** whereas A adapts it to bitter→sweet; both convey patience but B is more literal.
- #004 B forward wrote **회사 직원이 작성해 주기로 했어** (agreement/promise) when source merely says the employee **will** write it. B independent back inserted `ຕົກລົງ` (agreement), confirming forward-added commitment. A is safer.
- #008 B forward '초음파' is contextually clearer than A '에코', but B **independent back** inserted Thai `ตรวจ`, foreign-script regression.
- #010/#074 A forward switches to polite `-요`, B uses natural spouse banmal and keeps content.
- #020 source food `ມຶກກຸ໊ບ`: A forward guesses **쭈꾸미**; B recognizes a squid snack but adds **마라**, not explicit in source. Verify actual product before treating B as fully correct.
- #024 B forward clarifies 'like' on social posts; improves A's generic 'press'.
- #030 original `ຖ່າຍແບບ` 'took a photo of form', A forward '서식 찍어 왔어', B forward **양식 복사해 왔어**. B materially changed the action to photocopy; B back confirms `ກັອບປີ້`. Strong B regression.
- #046 both Korean forward outputs describe '몇 분'; B **independent back** invented `ສອງສາມນາທີ` (2–3 minutes) where source unspecified. Independent-back regression only.
- #058 B Korean forward says teacher checking homework; B back omits the initial action **enter to look**, turning it into 'go in first'. Subtle independent-back loss.
- #070 source says food **already ordered**, delivery pending; B forward '치킨 시켜 먹으려고 하는데' weakens completed order to intended ordering; A forward '주문해서 ... 시켰는데' better preserves completion. Original dish transcription may be ambiguous and requires source-context verification.
- #080 B independent back inserts stray English **Los** into Lao, A back clean.
- #084 source just `ບອກແລ້ວ` = already told/said; A '말했잖아' adds mildly reproachful stance; B '말했어' reduces unsupported reproach.
- #092 source `ຂ້ອຍກິນແຕ່...` past/ongoing 'ate only tofu pudding', B forward **먹었어** vs A '먹을게' future. B more faithful.
- #054 source contains contradictory amounts 480,000 kip and 'not yet 50,000 kip'; neither lane should silently reinterpret or 'fix' the user's numbers. Flag input anomaly separately, not model regression.
- #068 song label `인영` ambiguous; B back substituted a doll-related song name, possible proper-name interpretation drift; confirm intended title before semantic verdict.
- #090 B independent back explicitly `ອ້າຍ` to denote addressed husband, close to source; A also preserves second-person semantics.

## Verdict and next gate

- **C2-R2: QUALITY HOLD / SPEED REGRESSION CONFIRMED**, as measured in this equal-SMART run.
- C2 is not categorically worse in meaning; targeted improvements in kin/actor, register, photo-editing, empathy and uncertainty coexist with material regressions in document terms, committed intent, already-completed actions, backtranslation foreign-script purity and reliability.
- Continue P168A SERVICE frozen. No promotion, no new Gemini calls. Avoid automatically assuming prompt compression *causes* reasoning increase; now we have an equal-SMART association but no randomized prompt-structure decomposition. No unsupported claim of global Gemini outage.
- **Next offline design:** pivot away from C2 as a presumed speed optimization; preserve P168A detailed structure as the quality floor and consider a minimal, isolated TEST candidate changing only demonstrated semantic failures (actor/recipient, promise vs possibility, completed vs planned, certificate class) with constant SMART and unchanged independent back at first. Separately plan a controlled independent-back revision for output purity and spurious specificity, not bundled into forward candidate. No new H2 tool, no automatic quality scoring, no expensive runs without explicit permission.
