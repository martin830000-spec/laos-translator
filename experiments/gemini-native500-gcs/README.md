# Gemini 3.5 / 3.6 MODEL_NATIVE_OPT500 — private GCS execution architecture

Status: **OFFLINE TESTED; LIVE WIF/BILLING NOT READY** (2026-11-07).

The old Issue/public-key/encrypted-artifact handshake is replaced for future activation by
a research-branch GitHub Actions → short-lived Google WIF → private GCS plan → Gemini API
→ private GCS result flow. No custom encryption code, no personal source in GitHub or
Actions artifacts, and no operation on SERVICE or TEST main. This is a research-only
implementation, **not** a production change.

## Code and activation

- `experiments/gemini-native500-gcs/runner.py`: single-pass GCS runner for either model.
- `.github/workflows/gemini-native500-{35,36}.yml`: dedicated WIF protected workers.
- `.github/workflows/gemini-native500-gcs-readiness.yml`: free-only identity/bucket test.
- `experiments/gemini35-native500/config.json`, `gemini36-native500/config.json`:
  still `enabled=false,max_new=0,prior_actual=0` and **do not trigger generation**.
- The new workflow triggers only on an owner's push of `activation-gcs.json` in the
  corresponding model directory. No activation files have been created.
- The old `runner.py` files remain historical source but are not invoked by the
  new workflows. No GitHub Issue creation or handshake is part of the new flow.

## Verified IAM blocker

The pre-existing deployment WIF credential was checked from
`research/gemini-model-native500-20261107` in Actions 42359441737.
Google rejected it with `unauthorized_client: The given credential is rejected by
the attribute condition`. **Do not** put research code on `main`, weaken deployment
WIF permissions, or use the deployment service account to bypass this condition.

A dedicated research trust binding and principal are needed and must be authorized
and provisioned separately through Google Cloud IAM. The following GitHub repository
variables are expected by the workflows:

- `NATIVE500_WIF_PROVIDER`: dedicated WIF provider (or a safely scoped provider
  that explicitly authorizes only this research repository/branch).
- `NATIVE500_RESEARCH_SA`: least-privilege research service-account email.

The public WIF/GCS readiness workflow 42359830149 deliberately failed because
these variables are not configured. No identity or permission change was made.

The runner currently uses GCS bucket `lao-translator-src-460077888071` and prefix
`research/gemini-model-native500-20261107/`. It fails closed unless
Uniform bucket-level access and Public Access Prevention are **enforced**.
GCS IAM must permit scoped bucket-metadata read and object read/create on this
research prefix (and object creation for the research `preflight` subprefix).
Do not grant an unrestricted administrative role to this research identity.
If the existing source bucket cannot meet these safety requirements, create a
separate private research bucket through an authorized GCP administration process,
then review and change the hardcoded bucket value **before** any private plan upload.

## Private task plan contract

The planned private JSON file is GCS-only:
`gs://<BUCKET>/research/gemini-model-native500-20261107/<35|36>/plans/<PLAN_SHA256>.json`

Its exact raw byte SHA256 must match the `plan_sha256` in both model config and
`activation-gcs.json`. Top-level keys are `campaign`, `model`, `phase`,
`prior_actual`, and `tasks`.

Each task has a unique ASCII `slot`, a `case_id`, one `path` (KF, KB, LF, LB)
and model-specific `variant`. A FIRST has a private `input` string; its BACK must
have **only** a `from_slot` reference to its preceding FIRST, never the original
input. The runtime uses the **actual displayed FIRST** for the BACK call.
All tasks are validated before the first Gemini request.

`activation-gcs.json` provides `campaign`, `model`, `phase`, `max_new`,
`plan_sha256`, `plan_object`, and `run_nonce`; the model's `config.json`
must match these values and require `enabled=true`, max_new within the model's
independent 500-call approval, a future deadline, and a nonduplicated run.
No source sentences or translations belong in activation or config.

A dedicated research GitHub Actions identity must successfully authenticate,
read the frozen private plan, verify its hash and schema, and create a unique
`RUN_STARTED.json` GCS object with `if_generation_match=0` **before** any paid
request. A separate private GCS journal object is atomically created **before**
each send. Results are written to private GCS per-slot objects; no retry.
Failed FIRST means the dependent BACK is skipped. Duplicate launch fails rather
than billing the same plan again. GitHub logs print metadata/attempt counts only.

Current task plans and activation files **do not exist**; the previous Work run
reserved sample IDs but did not create a new GCS plan. Do not pretend it did.

## Verified, unverified, and next steps

Verified: all 36 offline worker/SMART tests and GCS plan-schema tests passed using
**synthetic inputs**, no generation, in research-branch Actions. The user-approved
limits remain 0/500 actual for each model. Main production/test SHAs are unchanged.

Not yet verified:
- Dedicated research WIF authorization on this research branch.
- Bucket security metadata and least-privilege object read/write.
- Private plan creation/staging and exact SHA validation.
- End-to-end encrypted-at-rest GCS output upload under real WIF.
- Actual Gemini translation quality, usage, speed, and costs.

Next: authorize/create dedicated research WIF + narrowly scoped storage access;
set the two repository variables; rerun the no-generation readiness workflow;
stage the private corpus-derived plans into private GCS; then verify all immutable
config/activation/call caps. Only then use the user's existing model-specific
500-call approvals for research. Keep SERVICE/TEST unchanged.
