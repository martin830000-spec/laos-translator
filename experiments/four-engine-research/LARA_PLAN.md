# Lara Free32 R1 — prepared, not published or executed

User confirmed Free account on 2026-10-30. Free balance inquiry is not a prerequisite.
Free quota rejection stops the campaign. No payment, upgrade, key switch, retry or repair call.
Existing R3 actual200 analysis and R4D mock-only code are reused as historical evidence.

## Hypothesis and scope

A: faithful/noTrace, reasoning false. B: identical with ONE conditional native instruction:
“Preserve the actor, recipient, and family relationships expressed in the visible source.”
It applies only when the current visible input contains a listed Korean/Lao kinship term.
BACK reevaluates its own actual FIRST text; it never receives the original, category or expected answer.
No context, glossary, TM, Think, Prosa, auxiliary judge, or automatic detection calls.
K4/L4 synthetic messages; two kinship and two neutral controls per side. Eight source families
are exploratory developer-authored material, not an independent native-reviewed holdout.
No expected translations are included. Sources cover actor/recipient, negation, condition,
future/completed action, quantity, time and ordinary conversation.
Half use A-then-B and half B-then-A. This reduces order bias but cannot eliminate stochastic variance.
Neutral inputs may have identical A/B requests: do not attribute their differences to the instruction.

Eight sources x two arms x FIRST/BACK = **32 maximum translation attempts**:
husband FIRST8/BACK8 and wife FIRST8/BACK8. Authentication is one additional non-translation HTTP request.
No paid requests to Gemini, Google or Azure. Every uncertain/failed translation attempt consumes one slot.
Per-request input safety cap: 2000 Unicode codepoints. This is a campaign safety bound, not a billing estimate.
Observe input/instruction/output codepoints, raw reported usage (if any), request latency per stage.
Provider-billed character count and account remaining balance remain UNKNOWN unless actually reported.
Free account rejection is the quota boundary; do not pretend local character counting verifies billing.

## Technical and result security

Official SDK uses automatic auth retry and 401 replay. Direct HTTPS follows its auth MD5/HMAC-SHA256
and /v2/translate contract instead, with one request per attempt, no redirect or retry.
Raw provider integration is not yet live-validated; protocol rejection is HOLD, not a fallback to the SDK.
HTTPS host/path are fixed. Auth token/key/headers never enter persisted results or logs.
Pre-send and post-response journals are RSA-OAEP-SHA256/AES256-GCM encrypted.
Only out/lara-free32/sealed.json is uploaded. Stdout contains counts/status only, never translation text.
Private result key stays under ignored work/lara-free32-keys on this PC; keep it until decryption/Drive backup.
Manually download the encrypted artifact within seven days, decrypt locally, inspect and back up privately.
If the runner is killed, the latest local encrypted journal may be lost before artifact upload;
the permanent lock forbids automatic replay of that uncertain campaign.

## Review

For each arm and each of four paths, inspect original->FIRST and actual FIRST->BACK separately.
Mark first occurrence vs propagated vs independent BACK error. P0 blocks adoption; relevant P1 patterns HOLD;
P2 wording alone does not justify prompt expansion. Native Lao interpretation uncertainty remains explicit.
Complete API responses are NOT semantic PASS. Compare latency by stage/side and arm (small-sample p95 unstable).
No paid AI evaluator. Use existing audit.mjs structural checker, not roundtrip string similarity as a quality score.

## Exact publication/execution procedure — approval pending

1. Review and approve a TEST-only commit/push containing the research files and .github/workflows/lara-free32.yml.
   A workflow_dispatch workflow must exist on the default branch to register for dispatch.
   Publishing to main may also start existing TEST CI/Pages automation; it does not authorize SERVICE changes.
2. Confirm the pushed source hash/files, then dispatch Lara Free32 isolated TEST ONCE with Free confirmation
   and the local public-key base64 text. Never send the private key as an input.
3. Offline tests run without credentials. The workflow creates permanent tag
   lara-free32-20261030-r1-consumed. Existing tag or rerun attempt prevents authentication/translation.
4. Exactly existing LARA_ACCESS_KEY_ID and LARA_ACCESS_KEY_SECRET are passed only to the execution step.
5. Download/decrypt evidence, perform four-path review, append verified outcome to Drive LIVE_STATE.

No local commit, push, dispatch, tag creation or actual API request was made in preparation.
GitHub connector currently lacks workflow dispatch; authenticated GitHub UI or an approved CLI setup is needed
after publication. Do not ask for plaintext provider keys or assume Repository Secrets are invalid.

## Sources inspected

- https://developers.laratranslate.com/docs/adapt-to-instructions
- https://developers.laratranslate.com/docs/translate-text
- https://github.com/translated/lara-node/blob/main/src/net/lara/client.ts
- https://github.com/translated/lara-node/blob/main/src/crypto/node-crypto.ts
- https://support.laratranslate.com/en/what-happens-when-your-monthly-quota-is-exhausted
