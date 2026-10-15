# R4D TEST historical regression suite — release-readiness evidence 2026-10-15

STATE: **OFFLINE TEST BRANCH READY / CLOUDFLARE ACCESS WORKER NOT DEPLOYED**
Confirmed branch tested HEAD (static CI): `3968a0944142bd5527c3dc9079e1abf7c69ef892`.
Offline CI: https://github.com/martin830000-spec/laos-translator/actions/runs/38718298766 — success (mock gateway, server, Wrangler bundle dry-run, static secret checks). No live paid provider call or Worker deployment.

## User research goal
Compare exactly sourced previous P160–P173/P168A Gemini translation failures, 10 husband Korean originals and 10 wife Lao originals, against different translation engines. Use 1/2/3/5 repeated runs of the **same** original to count recurring semantic failure across the four lanes. Preserve exact historical typos as source evidence. Do not use these source originals as Adaptive gold-training examples.

## Changes isolated to branch
- `test-relays/translation-adaptive-r4/cloudflare-access-r4d/index.html`: number of cases selectable 2,4,8,20,50; repetitions selectable 1,2,3,5. For requested 50 enforce exactly 25 K + 25 L and 50 total.
- Preflight 400 max calls per click, total estimated 60,000-character cap retained. Each request remains one forward, one independent back; no automatic retries; abort control retained. More than 400 planned calls is refused, not silently truncated.
- Summary groups forward variations by same original+engine+side+profile identity. Back variations are only compared for *identical* back input (same forward text); differences in independently generated forward translations are not blamed on back prompt. String variation is **not** automatic proof of meaning errors; human native-aware review remains necessary.
- Added independent offline CI assertions that inline script parses, repeat options/caps and 50-case balance guard exist. No public history DB changes.

## Private 20-source fixture
- `/mnt/data/R4D_HISTORICAL_FAILURE_20_PRIVATE_20261015.txt` SHA256 `9c6a1b3694ca4700338d87e9e533eb8413c25b36ae86063e85c8be8f40631283`; 20 source rows, 10 K/10 L, exact historical spelling, all distinct. NOT pushed to public repository.
- `/mnt/data/R4D_HISTORICAL_FAILURE_20_PROVENANCE_20261015.json` corrected SHA256 `bc3def48974cf6f424bdef365a581ee8baa5ca1d5cf5b5d416f82dcd6722553f`. Correction: old provenance accidentally flagged ten F3 wife sources as `human_gold=true`, while the canonical F3 control pack has `manual_gold=UNREVIEWED`. All 20 rows now have `human_gold=false` and `gold_reference_status=UNREVIEWED`. Source texts themselves were not changed.
- Ten K inputs trace to `TRANSLATION_DB1000_P168A_FLAGGED_EVIDENCE_20261011_R1.md` IDs #51, #56, #79, #103, #116, #151, #318, #464, #470, #514. Ten L inputs trace to `FIXED_CASE_CONTROL_PACK_F3_R3R4_20261011.json` W01,W02,W03,W04,W05,W07,W08,W09,W10,W11; cross-checked exact `source_verbatim`. Stochastic variation and as-yet unreviewed ambiguity are labeled separately from confirmed source meaning faults.
- Private messages must not be committed into public GitHub branch, workflow artifacts or public Pages. They may be entered into Access-gated comparator only after verifying gate; avoid sharing unredacted result log in public issues.

## Rollout state & limitations
- Cloudflare Worker `r4d-adaptive-access-test` is presently NOT verified to contain current branch patch. GitHub branch writes do not automatically deploy it; CI is **dry-run only**.
- Connected tools have no authenticated Cloudflare Workers deployment action. To deploy, owner needs a guarded `wrangler deploy` against **r4d-adaptive-access-test** only, preserving Cloudflare Access policies, owner identity, worker secrets and TEST backend. Do not modify SERVICE/GitHub main/H2, existing relay, backend or DB. Confirm Access rejects unauthenticated viewer *before any real test*.
- The previous Adaptive K→L HTTP429 root cause remains unconfirmed until updated TEST diagnostic Worker is deployed and observed; no retry/cap removal.
- Recommended run sequence: 20 cases × two chosen engines × forward+back × 1 = 80 calls; then repeat selected high-risk cases 3 or 5 times. If 20 × 2 engines × 5 × 2 = 400 calls, fits cap. 20 × 8 engines × 3 × 2 = 960 calls — blocked in one session. Total provider charges not guaranteed by count cap.

SERVICE frozen: V3.61.209/P168A R8/G158A. No operation in this work touched SERVICE, Cloud Run, Cloudflare production, H2, or Control/History DB.
