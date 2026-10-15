# R4D — C1→C2 통합 8엔진 품질 진단 및 TEST 429 원인 노출 기록
Date: 2026-10-15 (KST)
Status: C2 TEST CANDIDATE / NO LIVE C2 A-B / SERVICE HOLD
Scope: martin830000-spec/laos-translator branch test/r4d-access-gateway-isolated-20261015
Baseline source: ko-lao-engine-compare-r4b-1792055222887.txt (16 engine-case records; 15 complete, 1 Adaptive K→L HTTP 429).
C1 file: test-relays/translation-adaptive-r4/cloudflare-access-r4d/candidates/R4D_UNIFIED_C1_8_ENGINE.txt
C1 prompt SHA-256: dd2c828c373cef9b8c25354898b157052519c2f43dcdcf7eabedf306d53ee622
C2 file: test-relays/translation-adaptive-r4/cloudflare-access-r4d/candidates/R4D_UNIFIED_C2_8_ENGINE.txt
C2 prompt SHA-256: ceed99e929095fdf637300b2c0b7663d7d889e35edbbc6e2292aa69523e5566c
C2 Git blob SHA: 3fb010e3f4fec034c3b1f7d80e7cd89c60bc0fda

## Baseline timing (milliseconds, ROUND 1, 2 different sentences per engine except Adaptive=1; not reliable p95)
| Engine | Completed K/L | Forward average | Independent back average | Sum average |
|---|---:|---:|---:|---:|
| Azure | 2/2 | 441 | 289 | 730 |
| Google NMT | 2/2 | 408 | 418 | 826 |
| Google Translation LLM base | 2/2 | 547 | 593 | 1140 |
| Lara default Faithful | 2/2 | 1301 | 756 | 2057 |
| Lara C1 tuned Faithful | 2/2 | 1253 | 833 | 2086 |
| Gemini C1 LOW | 2/2 | 1701 | 1873 | 3574 |
| Gemini P168A reference LOW SMART OFF | 2/2 | 3314 | 2008 | 5322 |
| Google Adaptive TEST C1 | 1/2 (L only) | 867 | 2237 | 3104 |

## Four independent direction findings
1. Husband K→L forward: P168A reference preserved planned submission versus completed approval and conversational correction. Gemini C1 preserved core action but became abstract/formal. Lara default and tuned inserted explicit addressee and agreement/consent not stated by the Korean source. Azure/NMT/TLLM base introduced changes to temporal/causal/modal meaning. Adaptive K→L forward failed HTTP 429 and HAS NO quality result.
2. Husband L→K independent back: P168A reference preserved source's conversational register and approval distinction; C1 drifted to formal. Lara default/tuned introduced 'you' and agreement. Azure back interpreted 'not saying approved' as 'not approved'; Google NMT back shifted to future 'no guarantee'; TLLM back invented a causal explanation.
3. Wife L→K forward: P168A reference, Gemini C1 and Translation LLM base preserved 'dizzy, not headache, sit and rest.' Lara C1 preserved sitting but over-formalized speech (저는 ... 싶습니다); Lara default omitted sitting. Azure/NMT used past tense 'wanted' instead of current desire.
4. Wife K→L independent back: Gemini C1 preserves general symptom/causality and sitting. P168A back rendered first-person source with 'ນ້ອງ' rather than neutral 'ຂ້ອຍ' — baseline is NOT error-free. Lara C1 back includes a new 'briefly' detail. Adaptive L path completed, though its Lao back omitted explicit first-person. Native-speaker Lao naturalness remains unverified.
NOTE: Four *paths* are two case forward/back pairs; with two cases total this is qualitative triage, not a quality ranking.

## Adaptive 429 code audit / safe TEST-only change
- Cloudflare TEST gateway previously normalized ANY backend HTTP 429 to {error:BACKEND_RATE_LIMIT}, masking Cloud Run's reason.
- Cloud Run TEST server.js enforces R4_MIN_INTERVAL_MS (default 1200ms) independent of its R4_DAILY_CALL_LIMIT=0 setting; 0 removes daily quota only.
- R4D browser index.html spaces Adaptive requests by nextAdaptiveAt+2500ms in a single tab, but concurrency across sessions, prior requests, inconsistent deployed env, and origin status cannot be ruled out.
- Root cause for *this* 429 remains UNCONFIRMED without contemporaneous backend logs or a revised TEST run. Do not misclassify as poor translation quality or claim solved.
- TEST gateway now exposes only allowlisted backend reasons LOCAL_RATE_LIMIT and LOCAL_DAILY_LIMIT (or UNKNOWN_BACKEND_429), plus bounded retryAfterMs where present. No provider exceptions, secrets, automatic retries, auth loosening, or cap changes.
- Changed TEST files: cloudflare-access-r4d/gateway-core.mjs and gateway-core.test.mjs. Cloud Run server.js unchanged.
- TEST-only commits: C2 candidate create (before 9649e54); 429 diagnostic patch 9649e54d8a427425bef9a7291a6e3d9e0bfd44c1; offline regression extension 5f18615582d65de1a90e480566623b6580c3e977.
- Offline CI of final commit PASSED, run https://github.com/martin830000-spec/laos-translator/actions/runs/38712360163 : Node mock gateway tests PASS, Cloud Run offline tests PASS, Wrangler dry-run PASS, browser-secret invariant PASS. No live provider translation calls or TEST deployment by this CI.
- Separate observed CI failure for intermediate patch was fixed by updating test expectation at final commit. Only final CI success is sign-off for static integrity.

## C2 design, caveats and next gate
- Gemini 4 routes: actor omission, negation/time/modality, plan versus outcome, independence of back translation, casual spoken register, body actions/posture, no invented kinship.
- Lara 4 routes: two lines max and <=19 whitespace-delimited words/line, aimed at subject hallucination and stiff formality.
- Adaptive each direction: preserves 1 C1 example, adds 1 context example; TEST-only provisional, Lao native review required before any promotion.
- Unpromptable Azure / Google NMT / basic Translation LLM stay identical controls.
- Important comparator limitation: Gemini P168A uses LOW/SMART OFF configuration reference and does not reproduce the complete SERVICE assembly.
- No live C2 results, no speed p95 claim, no actual user-device acceptance, no SERVICE promotion.
- Next: deploy TEST diagnostics only with explicit deploy consent; verify 429 reason via one bounded owner-authenticated request where needed. Compare C1 versus C2 on the SAME Korean+Lao input and identical model/settings, examine four paths and call durations, add blind holdout and native review, then decide HOLD/PASS. Do not repeat full 200-call sweep without evidence.

## Frozen production
Couple SERVICE V3.61.209 / P168A R8 / G158A; general SERVICE V3.61.207; Cloud Run/Cloudflare SERVICE, H2, History/Control DB, SERVICE prompts and data all unchanged.

## Post-audit append: C2 file-parser integrity CI (2026-10-15 KST)
- Added offline C2 TXT parser/SHA/4-lane/Lara-limit/Adaptive-pair regression test; final code commit ff5204a31605204ed8372e793c3fca12f46fd121.
- Final complete CI SUCCESS: https://github.com/martin830000-spec/laos-translator/actions/runs/38712981191
- All offline steps PASS: Node gateway mock tests, Cloud Run local mock tests, Wrangler dry-run, browser-secret invariant. Verified exact C2 text SHA-256 ceed99e929095fdf637300b2c0b7663d7d889e35edbbc6e2292aa69523e5566c. No paid API translation or deployment.
- This is a new appended record; previous audit and raw R4B evidence are preserved.
