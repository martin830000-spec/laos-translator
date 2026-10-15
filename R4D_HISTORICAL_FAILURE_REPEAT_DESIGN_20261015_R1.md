# R4D TEST — Historical Gemini failure replay & 3/5 repeat offline design (2026-10-15)

**Status:** offline TEST branch changes, NOT deployed to Cloudflare Worker / Pages. No live provider API calls. SERVICE, H2, Cloud Run, Cloudflare service, History DB/Control DB unchanged.

## User purpose
Replay **exact prior Korean/Lao real-use source messages that failed during P160–P173 and related prompt experiments** across eight engines. Compare original meaning, actual forward text and independent back text per engine, and check recurrence with 1, 2, 3 or 5 independent trials. This is NOT Adaptive few-shot example training and not random newly fabricated sentences.

## TEST implementation
- Isolated private-access comparator source `test-relays/translation-adaptive-r4/cloudflare-access-r4d/index.html`.
- Repeat selector now 1/2/3/5; case selector now 2/4/8/20/50.
- Existing mandatory run-level 400 maximum requests, 60,000-character preflight, stop/abort, explicit run button, per-engine credentials, TEST-only backend and no automatic retry unchanged. No silent cap increase.
- Summary now separates **forward text variability for same original source** from **back text variability for byte-identical forward text**. Groups include prompt identity/SHA so C1 versus C2 never masquerade as same-condition repeats.
- Variation of wording or outputs is NOT automatically scored as a semantic error. API 429s count as operational failures, not mistranslation.
- The 8-engine suite is computationally expensive: 20 cases x 8 engines x 2 calls x 3 runs = 960 requests and x 5 = 1600, beyond safe 400 per-run cap. Recommended phased focus: 20 cases x 2 candidate engines x 2 translation calls x 5 = 400. All costs are charged by respective providers; no currency budget guarantee.
- No code path reading live DB automatically was added, avoiding public-GitHub exposure, new DB credentials and changes to H2. Historical failures imported by manual input `K|...`/`L|...` using the existing case textarea.

## Private replay fixture created (NOT in public GitHub)
Private local-only artifact `R4D_HISTORICAL_FAILURE_20_PRIVATE_20261015.txt`: exactly **20 unique exact historical source texts**, 10 husband K2L and 10 wife L2K interleaved. Private provenance JSON `R4D_HISTORICAL_FAILURE_20_PROVENANCE_20261015.json` records per-case historical IDs and risk type. Confidential content must never be committed to this public repo.
- K historical IDs: #51, #56, #79, #103, #116, #151, #318, #464, #470, #514 from 2026-10-11 1000-record flagged evidence archive; includes confirmed, higher-risk and variability cases, not all proven erroneous.
- L historical IDs: F3 W01, W02, W03, W04, W05, W07, W08, W09, W10, W11 from preserved 14-case controlled pack; excluded ambiguous STT/polysemy W06 and kinship uncertainty W12.
- TXT SHA256: `9c6a1b3694ca4700338d87e9e533eb8413c25b36ae86063e85c8be8f40631283`. Exact originals retained, including historical typo(s). Not a native Lao gold reference dataset; human review required.
- 20-source content length excluding `K|`/`L|` = 1,365 Unicode characters. 20 x 2 engines x forward/back x 5 repetitions = 400 calls, preflight estimated 27,300 characters, within existing limits before other conditions.

## Verified
- TEST branch `6fa4806fc56ee19f9c499b8d58427411bae4a8f3` has repeat UI and static offline guard tests.
- GitHub Actions `https://github.com/martin830000-spec/laos-translator/actions/runs/38715598503`: SUCCESS, with inline script syntax check and mock/backend gateway tests, no paid API calls.
- Browser live device / Worker TEST deployment and actual 1/3/5 round translations **NOT yet tested**; no claim of live parity.

## Safe test method
1. Import the original C2 unified profile TXT and paste private historical 20-source case file contents into the case textarea in the Access-gated TEST comparator **only**; never paste user messages into GitHub issues/public code.
2. Set 20 cases, pick two candidate engines, repeat 1 initially; export full TXT/JSON (all four paths).
3. After human semantic judgement, repeat only relevant engine/case subsets 3 times, then 5 times as needed; preserve prompt hash, model, forward, back, latency, HTTP failure, round.
4. Distinguish forward failures, back-only failures (back input must be byte-identical), linguistic variation, source ambiguity and operational/API 429. Retain historic failures and fixes, never infer accuracy from plain string match.
5. Promote nothing to SERVICE from this isolated R4D stress suite; full real runtime four-path quality and cost gate still apply.
