# GEMINI_MULTI1000 C-stage GitHub Actions recovery

Status (2026-11-07): **READY FOR SAFE OFFLINE CHECKS; PAID EXECUTION DORMANT**.

## Grounded history
- Original approval: at most 1,000 generated API calls.
- Actual generation attempts: **172** (ACCESS 4, A 96, B 72).
- C: **0**, FINAL: **0**. Unused: **828**. Not automatically transferable.
- Previous C code commit `c8754fc5fce0f67844b1028a33d14f0eb22ece05` changed `activation.json` but produced no matching GitHub Actions run. Trigger/event/index cause was **not proven**.
- Research closure at `b103db8d5a8860821a335edbc75c1112a3559f57` set `config.json` disabled and `max_new=0`, preserved the 172 attempts, and ran free closure check.
- Google Drive LIVE_STATE final private evidence and verification are preserved. No earlier A/B API calls should be replayed.

## New, isolated Actions
1. `.github/workflows/gemini-multi1000-c-readiness.yml`
   - Push trigger: `experiments/gemini-multi1000/c-readiness-trigger.json` (or editing this workflow).
   - **NO GEMINI_API_KEY, NO generateContent**. Validates closed ledger, C candidate request generation on four paths, Python/Node syntax, 3.6 LOW/max1024, and exact source binding.
   - Observed successful runs: 42322778927 and 42322805040.
2. `.github/workflows/gemini-multi1000-c-protected.yml`
   - Prepared but deliberately **dormant**. Push trigger ONLY on new `experiments/gemini-multi1000/c-paid-activation.json`.
   - Preflight requires new explicit user authorization and matched C config; `phase=C`, `prior_actual=172`, `max_new` between 1 and 72, new unique C resume consumption tag, non-expired deadline, and a fresh encrypted GitHub Issue (not old closed #211). After the gate, uses the existing sealed handshake and one-shot sender.
   - As of this document, `c-paid-activation.json` DOES NOT EXIST, `config.json` remains disabled, the old deadline has expired and Issue #211 is closed: it is not runnable as paid research without an explicit future action.

## Future authorized research continuation (NOT performed here)
Only after a user's explicit decision to resume paid C-stage research:
1. Re-read current private evidence, research source, latest user decision and GitHub SHA. Reconcile the existing 172 attempts before any calls.
2. Prepare a new encrypted plan for **C only**, up to 72 *additional* attempts and within the original remaining limit. Never put real Korean/Lao conversations, API keys, or private keys into the public repository or Issues as plaintext.
3. Open a fresh protected encrypted Issue; update `config.json` with a fresh deadline, `phase=C`, `enabled=true`, `prior_actual=172`, exact `plan_sha256`, fresh `issue_number`, `max_new<=72` and new unique `gemini-multi1000-20261107-c-resume-...` tag.
4. Add `c-paid-activation.json` **last** with matching `approval=USER_APPROVED_C_RESUME`, `explicit_authorization=true`, `phase=C`, `prior_actual=172`, `max_new`, and `plan_sha256`; this pushes the protected workflow.
5. Verify the *actual* Actions run ID before sending an encrypted C plan. If no run appears, STOP without repeated push/paid retry. Validate the encrypted handshake and single-shot ledger.
6. After a successful C result, inspect output and separately decide on a new independent FINAL. Do not auto-spend remaining calls.

## Service/approval protection
No SERVICE or TEST main changes, no Cloudflare/Cloud Run/DB changes, no redeployment, no API generation performed during this recovery. Preserve `closure.json` as historical stop evidence. C resume must not silently turn the research branch into an operating app deployment.
