# H2 fixed-input wife-back A/B runner — TEST and Pages main code release

Date: 2026-10-13 KST

## Purpose and privacy
Allow **only** the wife's independent Korean→Lao back-translation to be compared for **eight fixed Korean inputs** in controlled P168A vs WB1 runs. Do not regenerate the forward Korean message on either lane. The private user-provided fixed-case fixture `KO_LAO_WIFE_BACK_WB1_FIXED_INPUT_PRIVATE_20261013.json` is NOT stored in this public repository. Its historical text, original Lao, and model outputs are excluded from this public report.

## Changes
- Only `diagnostic-h2-20261010.html` changed: insert an optional collapsible UI into existing `프롬프트 A/B 검사` and add local fixture loading, gated verification, 8×A/B back-only execution, stop, progress, local-only TXT export. The old four-path H2 controls and implementation remain byte-for-byte unchanged. No new diagnostic app built.
- The original H2 is kept intact plus three additions: HTML panel (+1404 chars), JS runner (+9558 chars), event handlers (+688 chars). A separate diff-parity script removed these three insertions and verified that the remaining source is byte-identical to the former Pages `main` H2.
- The private JSON schema is `KO_LAO_WIFE_INDEPENDENT_BACK_FIXED_CASES_V1` and must contain exactly 8 unique cases, each with `fixedKoreanInputsForBackComparison[0].text`. The **first historical Korean forward variant per case** is frozen as an identical A/B independent-back input. Alternative historical variants are not injected and not called.
- H2 free preflight verifies: TEST opener/source fingerprints, base P168A, SMART OFF equal-mode `A_OFF_B_OFF_JSON`, candidate WB1 revision and canonical hash `ba7e198673375f1edc56e50d83bc0109efc036798a206b24a03cd0499a76537a`, strict `CHANGED_FIELDS=back.wife`, forward and SMART parity.
- Only an explicit user click on `동일문장 역번역 16회 시작` followed by confirmation allows up to 16 Gemini calls. The routine calls `promptCompareCandidateBack('L2K', fixedKorean, cfg)` **only**. No call to `promptCompareCandidateForward`, no DB sample fetch, no real-use DB history writes. The file is read only in browser memory; only the selected Korean back-input texts go to the model via the existing app path when the user authorizes the paid run.
- Sequential A/B order alternates for each case, providing symmetry against first/second ordering effects. End state resets only diagnostic clone frames. Stop applies between calls and preserves partial results; it cannot cancel an in-flight Gemini request.
- The local exported TXT records both same inputs, independent backs, timing, token metadata when exposed, Thai-script/Latin warnings, and estimated billed-price rates if usage is present. Static foreign-script detectors are **advisory**; names, codes, brands and legitimate technical Latin spellings must not be automatically marked wrong.

## Verification actually performed
1. GitHub fetched the original `main` and TEST branch H2; original byte hashes identical `204fed2b5e12c262e11bb2c75f6bbe9cfcccd22e`.
2. New TEST H2 JS code compiled via JS parser `new Function`; checked all new DOM IDs unique.
3. Simulated eight-record schema test: invalid 7-case fixture rejected; valid 8-case fixed fixture accepted.
4. Simulated free preflight: zero model calls; compared expected P168A/WB1 SHA and isolated field `back.wife`.
5. **Mocked execution** under direct simulated user confirmation: exactly 16 `promptCompareCandidateBack` calls (8 P168A, 8 WB1), **zero** `promptCompareCandidateForward`, identical Korean fixed text in the two lanes for every case, local result log created, diagnostic clone frames reset, legacy A/B control restored.
6. Independently checked the actual private 8-case fixture's schema, eight distinct IDs, valid Korean text and length bounds using only a local file inspection; no case text exposed.
7. Existing H2 source otherwise unchanged by mechanical inverse diff of exactly 3 inserted ranges.
8. Updated only the H2 file on diagnostic Pages branch `main`, commit `cb2f9916e4e609d8c6091e677015f5f75a372c89`. New H2 blob SHA `69ce25fd86c37cce549109d2b60e2fde5f14c3db` is identical on TEST and Pages `main`.
9. Independently fetched `martin830000-spec/wife/main` prompt config after the H2 update: P168A SHA `7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43`, existing Git blob `b1323967ef529e0c960d6e7ab707ea43659b8b6a`. SERVICE V3.61.209/P168A R8/G158A preserved.
10. **NOT verified:** actual live GitHub Pages caching/rendering (external URL not accessible in this verification environment); browser runtime interaction on real device; real Gemini quality/latency changes (zero new Gemini calls). Do not advertise WB1 as quality fixed. H2 deployment commit is confirmed in `main`, but do not claim that a Pages CDN build has completed without an independent check.

## User next action (when ready)
Open the existing TEST main app's H2. In `프롬프트 A/B 검사`, select P168A / A SMART OFF / B JSON SMART OFF and import `EXP-P168A-WIFE-BACK-SCRIPT-WB1-R1.json`; expand `아내 독립 역번역 · 고정문장 A/B` and locally import the private fixed-8 JSON. Click `고정 8건 무료 준비 검사`. If it passes, click the separate `동일문장 역번역 16회 시작` and approve the cost confirmation. **Do not click the older generic `A/B 검사 시작`**, which runs up to 80 Gemini calls on 20 source records and does not guarantee the historical error sentences.

This does **not** constitute a SERVICE promotion, an automatic semantic quality grade, or permission for other backend changes. Candidate WB1 remains QUALITY HOLD pending human review of real model outputs.
