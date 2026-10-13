# C2-R2 thoughts/latency offline audit — 2026-10-13

## Provenance and guardrails
- H2 log: `prompt-ab-RUN-20261013-125631-52922e.txt` (`RUN-20261013-125631-52922e`), 50 real-use records, 25 K2L + 25 L2K, 198 attempted Gemini calls. All figures below are calculated offline from the user-supplied log; **no new provider calls**.
- A: frozen SERVICE P168A / SHA `7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43`.
- B: candidate `EXP-P168A-COMPACT-C2-R2` / SHA `606f1f2c3a755aea0a38c192aec446d58868b35fd17793cb31d1d84f45920cdc`.
- **Important confound:** actual H2 mode = `A_OFF_B_ON_JSON`, *not* equal SMART. Do not attribute any effect solely to prompt length or SMART.
- SERVICE V3.61.209/P168A R8/G158A, original C2 candidate, H2, live DB, Cloudflare and Cloud Run are immutable for this audit. Four-path evaluation retained: husband forward+independent back, wife forward+independent back.

## Token accounting: distinguish successful calls from rejected calls
| K2L/L2K | A observed thought-positive | A sum | B observed thought-positive | B sum |
|---|---:|---:|---:|---:|
| K2L | 1/25 | 437 | 6/25 | 2645 |
| L2K | 3/25 | 1595 | 12/25, including rejected #046 | 4588 |
| ALL | 4/50 | 2032 | **18/50** including rejected #046 | **7233** |
- H2 summary `thoughtTokens.n=17` and sum 6254 for B **exclude the rejected #046**, with 979 thought tokens. Use 18 / 7233 for all attempted generation traces; 17 / 6254 for successful responses.
- B forward mean input tokens, successful only: 421.6 versus A 993.1; first-display mean B 3904.8ms versus A 3313.4ms, n49 per lane (missing observations differ).
- All the thoughts under B were logged with `thinkingLevel: low`; LOW does **not** imply zero thinking.

## Same-record paired latency — only both successful first displays
| Paired subgroup | n | Mean B first-display minus A | Median B−A | B slower |
|---|---:|---:|---:|---:|
| Neither thought-positive | 29 | **+87.3ms** | +202.2ms | 16/29 |
| B thought-positive only | 15 | **+2217.1ms** | +2368.0ms | 14/15 |
| Both thought-positive | 2 | −167.3ms | −167.3ms | 1/2 |
| A thought-positive only | 2 | −3102.0ms | −3102.0ms | 0/2 |
- Total matched pairs: 48. #008 (A forward timeout) and #046 (B MAX_TOKENS) are excluded from paired first-display comparisons. #011 B independent back timeout does not invalidate its successful forward first display.
- L2K Cloudflare telemetry: when neither side thought (n11), mean B−A providerMs +57.9ms vs mean non-provider +26.3ms. When only B thought (n9), mean providerMs +1396.3ms vs mean non-provider +27.6ms. This associates the delay with observed provider execution, *not with measured Cloudflare overhead*. Provider timing not exposed on K2L direct path.
- Correlation does not establish that shortening the prompt *caused* thoughts; the prompt, SMART, model variability and source mix are not individually controlled in this run.

## SMART condition is not a complete explanation
- Of 49 successful B forward calls, 32 used the unextended base prompt length (K2L 1681 or L2K 1779), and **12/32** had thought tokens. 17 had conditional prompt extension, with **5/17** thought-positive. #046 did not capture prompt length on failed path (logged zero), so its SMART status cannot be inferred from `promptCharsMax`.
- This is observational grouping by logged prompt length, not a causal randomized experiment.
- K2L thought-positive B source median length was 31 characters vs 44 characters for no-thought B records. Short/simple utterances can trigger thoughts: #011 (162 tokens; same forward wording A/B), #019 (485), #021 (624), #043 (468), #047 (466).
- L2K cases also vary; long or speech-recognition-corrupted text is not a universal prerequisite.

## Key per-case flags
- #002 L2K: slash-separated alternatives in B forward and recipient inversion in independent B back.
- #011 K2L: both forward outputs textually identical, yet B thought 162 tokens and B independent back timeout.
- #014 L2K: **both** A 983 and B 979 thoughts, first display around 12s, showing model/provider variability also affects A.
- #021 K2L: likely source typo `울어봤고` for `물어봤고`; B thought 624, 7.56s first display.
- #034 L2K: B thought 174, forward truncated at Korean `먼저` but H2 accepted success; independent B back changes the named dish. Distinguish semantic/fluency incompleteness from API failure.
- #046 L2K: B thoughts 979, candidate 41, `FINISH_MAX_TOKENS` under `maxOutputTokens=1024`, forward rejected and no back; A completed. Do not adjust server/model output cap absent authorization.
- #048 L2K: B forward preserved hospital/friend visit, B independent back inverted participants; repair back separately.
- Partial errors exactly three records: #008 A forward timeout, #011 B back timeout, #046 B forward MAX_TOKENS. A/B client single-pass 1+1 observed where attempted; provider-internal retries unavailable.

## Next H2 controlled checks — existing tool only, no new diagnostic
1. H2 `프롬프트 A/B`; A baseline `P168A`; **A SMART `OFF`**; B mode **`간결 후보 JSON 비교 · SMART OFF`** (`JSON_SMART_OFF`); import unmodified `EXP-P168A-COMPACT-C2-R2.json`; 20 samples balanced 10/10; click **무료 준비 검사**. The saved log **must** state `SMART_COMPARE_MODE=A_OFF_B_OFF_JSON` before interpreting it as equal-SMART.
2. Independent parity check if needed: A SMART `ON`; B mode **`기존 후보 JSON 비교 · SMART ON`** (`JSON`); dry run; verify `SMART_COMPARE_MODE=A_ON_B_ON_JSON`. Source cohorts selected on different runs will vary; do not compare across runs as if exactly paired.
3. Paid Gemini run requires a human click/explicit confirmation in existing H2. Collect both independent back paths, forward/back token counts, p50/p95 first display, thought incidence incl failed traces, cost with missingness, case quality and all regressions. No auto-promotion.
4. Prioritize source/forward and forward/back separately. Retain C2-R2 on **QUALITY HOLD**, and only propose a next prompt after clean control evidence; do not create a new code artifact on this observational audit alone.
