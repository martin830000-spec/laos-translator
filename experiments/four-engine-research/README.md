# Four-engine research: recovery and offline preparation

2026-10-30 KST. Baseline main: 001b4e1ec0f8a9e0b3c6109e5b2bbbafbea74142.
Only this fresh checkout is writable. Existing GitHub/laos-translator and ChatGPT/research-repo are preserved.

## Verified evidence

Private Drive evidence ZIP: 1HW-jvw_QgVB9wMitQkFKAyNKfdFWNl3Z.
SHA256: 620868f3b554534ccf9f90d2984e62e41b39d5974ee98803ab26b494d8e79e07.
All 11 manifest files were checked against size and SHA256 after download.
Local copies are under ignored work/four-engine-evidence, never public GitHub artifacts.
Recovered: C1/C3 source, C1 FIRST strings, Lara R4 source, historical sections and 200-call analysis.
Missing: original 2x2/C1/C2/C3 result TXT, original engine200 TXT, complete historical independent C1 BACK bundle.
User reports these TXT originals exist in ChatGPT Library; this environment has not acquired them.
Do not rerun old experiments to replace unavailable evidence.

## Current findings and next decisions

- Gemini: current neutral comparator uses LOW/temp0/2048, unlike C1 MINIMAL/1024.
  Neutral parser joins all text parts and does not validate finishReason. This is a static finding,
  not evidence that the C1 active clone path has the same defect or that parsing caused its P0s.
  Keep MINIMAL; recover raw/independent BACK before any new paid experiment.
- Lara: prior R4D is mock evidence only. Review conditional native instructions against faithful,
  changing one option only. Context/glossaries require trustworthy inputs and separate hypotheses.
  Free balance query failure is not a stop condition. Free-plan/no-overage confirmation IS required.
  Quota refusal means immediate HOLD; no retry, new key, paid upgrade, or fallback.
- TLLM: standard and Adaptive are separate lanes. Adaptive needs verified existing v3 authentication
  and reviewed reference pairs disjoint from evaluation families. No new auth/server creation.
- Azure: preserve fast historical baseline. Lao custom support and English-only dictionary constraints
  do not currently justify direct ko-lo customization or a paid retest.

## Offline tools

Run: node --test experiments/four-engine-research/audit.test.mjs
Inspect a private Gemini response: node experiments/four-engine-research/audit.mjs gemini PRIVATE.json
Inspect normalized pairs: node experiments/four-engine-research/audit.mjs pairs PRIVATE.json
No transport or credentials are included. These tools do not assign P0/P1/P2 or claim semantic PASS.
Fixture success is not provider SDK, billing, real translation, native fluency, or speed validation.

## Execution boundary

No commits, pushes, Actions triggers, generation calls or SERVICE changes in this preparation.
GitHub Secrets cannot be read back by this connector; local gh/GitHub token/provider keys are absent.
Existing Actions secrets remain the intended execution route, not a reason to request plaintext keys.
An isolated reviewed workflow must be published before it can use those secrets; no workflow is live yet.
Gemini/TLLM/Azure paid calls require exact call scope/cost and separate user approval.
Future records must retain four paths, actual FIRST-only BACK input, failure/finish status,
request latency (not browser firstDisplay), provider usage/cost, and independent semantic reviews.
Private input/results must use the existing encrypted handoff pattern, not plaintext public artifacts.
