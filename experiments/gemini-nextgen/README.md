# Gemini NEXTGEN 2026-11-03 — TEST-only research, **0 paid calls**

New research from `GEMINI_NUANCE256_20261103` locked result, on an **independent branch** `research/gemini-nextgen-20261103`. No SERVICE or prior campaign file is edited.

## What is genuinely different?

- **BOUND:** Unlike 31T5–31T9/38CG (natural-language fidelity rules appended to a system prompt), serialize source, direction, speaker/listener and static household context as separately keyed **JSON DATA inside the one user part**, with a concise stable system rule. This isolates the current source *structurally* in the request, not by accumulating more warnings. Important: serialization alone is **NOT** model-level semantic isolation; it needs live tests.
- **FEWSHOT:** Use the same boundary contract plus **two fixed, public synthetic bilingual minimal-pair examples** to demonstrate conditional versus factual present. 0 user data in examples and 0 retrieval from previously failed cases. Unlike BOUND it has additional tokens and risk of example copying, weather-domain bias and incorrect Lao expression. Examples are not yet checked by a Lao native speaker; **do not assume quality improvement or production readiness**.
- **DIRECTION:** Separate K (husband→wife, Korean→Lao) and L (wife→husband, Lao→Korean) audience and register constraints; independent BACK is strictly a function of displayed FIRST and fixed direction only. Output is single plain text; prior 3.5 Flash native JSON was not validated by the old attempt and is not silently repeated.
- **MODEL:** Stable IDs as documented by Google: `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` (not `gemini-3.5-flash`), `gemini-3.8-flash`. Legacy 3.1 `minimal` is observed in prior raw successful requests; 3.5-Lite `minimal` and 3.8 `low` are currently documented. All are unverified with this code at the Gemini endpoint until approved live calls.

## Source & safety

- `candidates.py` is request building and output extraction **only**, no API networking or secrets. Usage `build_first(profile, original, private_context)` once and `build_independent_back(actual_displayed_first, first_side)` once. The pure helper `as_rest_request_parts()` separates the external `model` route from the standard `generateContent` JSON request body; still **not tested against live Gemini endpoint**. **Do not call BACK when FIRST failed.** No hidden repair, retry or AI judge.
- `extract_display_once(response)` accepts one `STOP` candidate and one visible text part; it preserves translation wording except outer whitespace. Thai and Han script create **warning-only** notices. Non-STOP, including MAX_TOKENS, fails that call without auto-retry.
- `test_contracts.py`: 18 **synthetic offline tests**, no key/HTTP, quality untested.
- `dry_run.py`: synthetic-only payload byte-size print, **not** estimated token count, speed or quality.
- `approval.json`: `authorized=false`, `execution_enabled=false`, `maximum_new_attempts=0`; original ITERATE320 and NUANCE256 approvals are consumed and cannot be transferred.
- `proposed-plan.json`: a **proposed**, not approved 128-call research plan with development / frozen independent FINAL split.

No personal original text, real raw API outputs, private context, token secrets, private keys, or local conversation data are committed. No paid workflow is enabled on this branch. No release or SERVICE changes.

## Limits

The old NUANCE256 FIRST quality signals are non-native tentative, and the six-per-direction FINAL-B pair cannot establish reliable overall performance. An offline JSON builder contract PASS **does not imply Lao translation PASS**. Human/native-language blinded review and real API latency/usage are outstanding. Model spelling, thinking and price should be rechecked at paid-run time.

## Public sources reviewed

- Google Prompt design strategies: https://ai.google.dev/gemini-api/docs/prompting-strategies
- Gemini models: https://ai.google.dev/gemini-api/docs/models
- Gemini thinking: https://ai.google.dev/gemini-api/docs/thinking
- Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- LoResMT 2026 on related-language pivot and few-shot sensitivity: https://aclanthology.org/2026.loresmt-1.14/
- FLORES-200 reference evaluation methodology (outside of private spouse domain): https://github.com/facebookresearch/flores/blob/main/flores200/README.md