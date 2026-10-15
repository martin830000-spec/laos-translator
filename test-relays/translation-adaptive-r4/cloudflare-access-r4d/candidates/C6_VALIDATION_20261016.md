# R4D Gemini C6 — TEST-only controlled candidate (2026-10-16)
## Change contract
- Parent: `test/r4d-c5-two-forward-paths-20261016`.
- Edited prompt: `gemini-c6-20261016.txt`.
- SHA-256 of exact prompt UTF-8 bytes: `f0fc49415fde0c3765be58a68a3cfc1ef05a6954265a7d121e20a7516ca0f6ac`.
- Profile ID: `R4D_GEMINI_C6`; R4D-PROMPT-V1.
- **Changed exactly one lane:** `GEMINI_WIFE_FORWARD`, to retain explicit Lao second-person subject as Korean addressee (and explicit Lao first-person speaker as speaker).
- **Untouched from C5:** `GEMINI_HUSBAND_FORWARD`, `GEMINI_HUSBAND_BACK`, `GEMINI_WIFE_BACK`.
- No private conversation fixture or API credentials stored in GitHub.

## Offline checks
- PASS: unique four path headers and parser-accepted V1 structure.
- PASS: each Gemini instruction line <=1000 characters; profile file <=16000 bytes.
- PASS: only wife forward instruction changed, compared with C5.
- PASS: privately prepared 4-case fixture accepted by R4D `parseCases`: K=1, L=3, two prior and two held-out sentences.
- PASS: projected 16 paid Gemini requests for 2 engines x 4 cases x forward/back; no provider calls made by preparation.
- Remote GitHub blob SHA verified against downloaded local file: `044246351ce16faec18ede3d0a21f1ec84e2dc9f`.

## Next experiment and gates
1. Existing owner-only R4D diagnostic: import C6 TXT; require status `적용 준비 · R4D_GEMINI_C6`, SHA prefix `f0fc49415fde`.
2. Select only Gemini P168A fixed LOW SMART OFF and Gemini TXT candidate; 4 cases, repeat 1, max calls 20. No Lara/Adaptive.
3. Review Korean→Lao husband forward/back and Lao→Korean wife forward/back separately; focus on second/first-person obligation subject.
4. Only after passing, compare unchanged husband paths and all 12 held-out cases, factoring real latency, uncertainty, and regression.
5. **No promotion**: P168A reference is SMART OFF TEST baseline, not exact SERVICE runtime. SERVICE V3.61.209 / P168A R8 / G158A, general SERVICE, existing Worker, Cloud Run, H2 and both DBs untouched.

Quality status: NOT YET TESTED; HOLD until actual A/B logs received.
