# C2-R2 compact experiment — static review (2026-10-13 KST)

STATUS: TEST JSON committed and read back; QUALITY HOLD. No new Gemini API calls, no H2/Pages deployment, no SERVICE/Relay/DB change.

## Baselines and provenance
- SERVICE frozen: V3.61.209 / P168A R8 / G158A / gemini-3.8-flash LOW.
- SERVICE canonical prompt SHA256: `7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43`.
- C1 baseline: `EXP-P168A-COMPACT-C1-R1`, canonical `c7ac0f44ece1499a58cf54866e2ccdaaaaed9f9b6b6dd6e4af4a1ec4f99ca21b`.
- C2-R2 candidate: `EXP-P168A-COMPACT-C2-R2`, canonical `606f1f2c3a755aea0a38c192aec446d58868b35fd17793cb31d1d84f45920cdc`.
- Direct source: Project file `prompt-ab-RUN-20261013-114027-dd6881.txt`, run at 2026-10-13 11:40–11:49 KST. Pairing: 25 husband K2L / 25 wife L2K, A=P168A SMART OFF, B=C1 SMART OFF, 200 attempted generations, zero client-visible errors.
- R7 active quality floor: P168A SERVICE, not P160. Separate release comparison against P168A SMART ON mandatory.
- Google Drive LIVE_STATE R7 policy and P160–P173 history reviewed; `CANONICAL_MANIFEST.json` was not located in available Drive/files search as of this audit (VERIFY_REQUIRED).

## Evidence from C1 vs P168A SMART OFF
- Forward firstDisplay mean A 2486.2 ms vs B 3129.4 ms (+25.9%); p95 A 3242.7 ms vs B 7877.4 ms.
- Input prompt tokens A mean 1004 vs B 243.5 (-75.7%); C1 reported thought tokens 4,684 across 12 forward calls; possible contributor, not established causal proof.
- 50 real conversations estimated uncached, token-derived four-path USD A 0.08076975 vs B 0.07017825; actual billing UNKNOWN.
- C1 keeper observations: #017/#023 seaweed identity in husband forward; #015 photo-comparison nuance; independent back #006/#028/#034 better handling of referent/food perspective in some outputs. These are per-sample observations, not population win rates.
- Regression targets: #019 C1 inferred total savings spent; #004 invented worry plus formal register; #002/#038 formal register; #032 uncertainty changed to emotional confusion; #011/#049 BOTH forward candidates over-specified vague few days; #001/#039 agent/recipient roles; #027/#036 prospective vs completion, follow-up force; #042 speech-act framing requires native/source-noise review.
- Independent back anomaly: A #014 included English explanation and multiple variants, not one Lao translation. In #011 a forward over-specific period was masked by C1 reverse returning '며칠'. Do not award forward success based on reverse alone.

## Candidate scope and static readback
- C2-R1 already existed before this work, hash `b6161aa9f9fa4b354c495241957666bb56165c67f56774dd7750964f5de37f34`, forward lengths 1716/1749; preserved unchanged. C2-R2 instead consolidates source actor/speech-act/aspect/emotion/register invariants to avoid growing case-by-case patches.
- C2-R2 forward.k2l 1681 characters, forward.l2k 1779 (C1 981 and 963); both target approx 1200–1800 characters.
- Exactly two changed prompt fields: `forward.k2l`, `forward.l2k`. All 8 SMART and 4 independent back/recovery strings byte-identical to C1/P168A.
- Canonical SHA-256 recomputed from ordered 6-field config (`schemaVersion,channel,promptRevision,forward,smart,back`); independent known SHA-256 test vector checked and GitHub readback matched. Channel TEST, schemaVersion 1. No runtime model-output quality validation.
- SMART routing effective in previously inspected source only conditionally attaches K2L SELF/HOME/REL, L2K ELDER/REL/READ; the two speech-act SMART values are defined but not assembled. SMART OFF means neither A nor B attaches them.

## Future paid-run protocol (NOT performed)
1. Use existing H2 A/B, no new diagnostic. In a single paired run compare A=P168A SMART OFF and B=C2-R2 SMART OFF, with 25+25 or smaller separately authorized preflight; preserve source IDs, order alternation, firstDisplay mean/p50/p95, tokens/thought tokens/estimated 4-path cost, error and meaning trace.
2. Only after analysis, separately compare C2-R2 against frozen SERVICE-quality P168A SMART ON, ideally with a controlled same-source ON-vs-ON paired run and independently reviewed four paths. No service promotion automatically.
3. Four independent quality lanes: husband K2L forward, husband L2K back, wife L2K forward, wife K2L back. Judge source→forward and forward→back separately; repeated same-text output stochasticity and native Lao naturalness remain UNVERIFIED.
4. Hold if any high-impact actor/recipient, relationship, condition, emotional intensity, politeness, duration, event scope or back hallucination regresses, regardless of average speed/cost.

No existing HISTORY, Control DB, SERVICE, H2 or network route was overwritten.
