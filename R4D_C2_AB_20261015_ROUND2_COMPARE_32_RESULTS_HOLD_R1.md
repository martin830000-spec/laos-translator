# R4D 8-engine C1 ↔ C2 cumulative export analysis — 2026-10-15 KST

Status: **HOLD** (quality and performance not yet proven; SERVICE unchanged)
Source original user-uploaded log: `ko-lao-engine-compare-r4b-1792056716358.txt`
Actual log records: 32 (ROUND 1 C1: 16, 15 complete/1 Adaptive K HTTP429; ROUND 2 C2: 16, 15 complete/1 Adaptive K HTTP429). ROUND 1 is identical to the earlier user-provided R4B log; thus NOT concurrent cross-over A/B.
Candidate C1 SHA256: `dd2c828c373cef9b8c25354898b157052519c2f43dcdcf7eabedf306d53ee622`
Candidate C2 SHA256: `ceed99e929095fdf637300b2c0b7663d7d889e35edbbc6e2292aa69523e5566c`
P168A reference SHA256: `7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43` (LOW, SMART OFF comparator; NOT exact SERVICE runtime).

## Four equal-status lane judgments
1. Husband K→L forward: Gemini C2 shortened abstract phrasing; correctly maintains tomorrow submission versus already approved today. No explicit addressee invented, though agreement/consent nuance persists in `ຕົກລົງກັນ`. Lara C2 removed C1's inserted `ເຈົ້າ` / implied addressee. Positive improvement.
2. Husband L→K independent back: Gemini C2 better colloquial Korean and preserved approved-completed contrast. Lara C2: `오늘 승인받기로 한 건 아니야` changes completed approval claim into a **plan to obtain approval**; important semantic regression despite more natural tone. This lane HOLDS Lara C2.
3. Wife L→K forward: Gemini C2 `머리가 아픈 건 아닌데 좀 어지러워서 앉아서 쉬고 싶어` retains all critical symptoms, intention, and posture, with familiar register (C1 polite `싶어요`; exact desired honorific depends on chat). Lara C2 retains sitting, dizziness, headache negation; less stiff than `싶습니다` but `싶다` remains bookish and not natural spoken couple style.
4. Wife K→L independent back: Gemini C2 uses `ວິນໆ` instead of clearer `ວິນຫົວ`; lexical specificity/naturalness requires Lao-native review, and the speaker pronoun is omitted (may be okay in context; do not mark a proven actor error). Lara C2 retains cause + sit/rest, removes extraneous short duration `ແປັບໜຶ່ງ` introduced in C1; needs native review.

## Timing, paired K/L means of forward+back milliseconds (not p95)
| Engine | C1 ROUND 1 | C2 ROUND 2 | Delta |
|---|---:|---:|---:|
| Gemini prompt C1→C2 LOW | 3574 | 3947 | +373 |
| Lara tuned C1→C2 Faithful | 2086 | 2141 | +55 |
| P168A fixed reference (control) | 5322 | 5775 | +453 |
| Lara basic (control) | 2057 | 2109 | +52 |
| Azure (control) | 730 | 470 | -260 |
| Google NMT (control) | 825 | 670 | -155 |
| Google Translation LLM (control) | 1140 | 1110 | -30 |
| Adaptive L only (incomplete; not a full K/L mean) | 3104 | 3079 | -25 |

Gemini candidate separate directional round total: husband K 3978→3909 ms (-69), wife L 3170→3985 ms (+815).
Lara candidate separate directional round total: husband K 2448→2428 ms (-20), wife L 1723→1853 ms (+130).
Sample size one per language per round and non-random order: do NOT claim significant speed gains/losses. P168A SMART OFF reference is NOT the full production execution path.

## Adaptive failure triage
K forward **HTTP 429 BACKEND_RATE_LIMIT** in both rounds; no forward or back quality measurement for K in either round. L forward/back success in both rounds, C2 output effectively identical to C1.
Gateway in the prior TEST GitHub commit exposes a safe diagnostic backend `reason` of LOCAL_RATE_LIMIT / LOCAL_DAILY_LIMIT / UNKNOWN_BACKEND_429, but was NOT deployed as part of the earlier work. This log only has `{error:BACKEND_RATE_LIMIT}`; it cannot prove which backend limit triggered. Cloud Run TEST daily=0 removes daily limit ONLY, minimum request interval still applies. No retry, cap loosening, or prod modification proposed.

## Decision and narrow next work
- **HOLD C2** as a unified candidate; preserve favorable Gemini C2 conversational improvements.
- Before C3: isolate Lara's 'approval was already obtained' versus 'approval will be obtained' back-translation drift with exact same Lara forward text. Avoid treating first forward stochastic differences as back-prompt improvements.
- Update only future TEST candidate, not C1/C2 originals, to address Lara's completed-vs-planned negative scope and `싶다` register; avoid global lexical substitution.
- Run focused holdout across both language directions / all four paths, compare P168A baseline in equal conditions. Verify one Adaptive K request after deployed safe 429 diagnostic if separately approved.
- User API keys and SERVICE must remain untouched. No live paid calls or deployments made in this analysis.
