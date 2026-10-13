# EXP-P168A-PRECISE-F1-R1 — static audit / HOLD

Date: 2026-10-13 (KST)

## Grounding
- 100-use H2 equal-SMART comparison: `RUN-20261013-133128-97e259` (`A_OFF_B_OFF_JSON`).
- 100-case review: `EXP-P168A-COMPACT-C2-R2_EQUAL_SMART_100CASE_AUDIT_20261013.md`.
- Original source: this branch's `prompt-config.json`, P168A, canonical SHA `7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43`.
- Candidate `EXP-P168A-PRECISE-F1-R1.json`, revision `EXP-P168A-PRECISE-F1-R1`, canonical SHA `9b8a3a34882e9ae06e594bf48695d79910112be6d1230ca86866e9e67abd6472`.
- No edits to SERVICE, working app, diagnostic H2, Cloudflare, Cloud Run, current prompts, database, or archived history.

## Exact change scope
**Only** `forward.k2l` and `forward.l2k` differ from P168A. Byte-equal, readback-verified: **8 SMART rules** and **4 independent-back/recovery fields**. All other properties and schema retained, except candidate metadata revision/description/hash.
- K2L prompt length P168A **3985** → F1 **4169** characters (+184), refining the existing medical/legal document guard to distinguish **진단서**, **진료확인서**, and **혈액검사 결과지** (#083).
- L2K prompt length P168A **4018** → F1 **4488** characters (+470), refining three existing anchors:
  1. **promise vs future action** (#004): `ຈະ` alone must not become a preceding agreement `-기로 했다`;
  2. **ordered vs not yet delivered** (#070): `ສັ່ງ` + `ຍັງບໍ່ທັນມາສົ່ງ` is already ordered/pending, not future intention;
  3. **photography vs copying** (#030): `ຖ່າຍ` alone does not license asserting `복사했다`, especially with a document/form. If original is ambiguous, do not force an unsupported camera/photo interpretation either.
- The replacements modify established anchors instead of appending a new block. They restate original priority: meaning > referents > register > naturalness. No new role assumption, no new inference policy, no new hidden calls.

## Risks and collision checks
- K2L document guard references Korean medical document types in a Lao output prompt, to preserve precise source categories; do not translate this as a prescription to choose one specific Lao governmental form for any document.
- L2K delivery guard is limited to delivery context, not any standalone `ສັ່ງ` in other contexts.
- L2K form/photo guard is deliberately **non-forcing**: Lao `ຖ່າຍແບບ` in #030 may be contextually ambiguous. Test real context; don't count the constraint's existence as semantic success.
- `ຈະ` may appear in reported agreements; if source explicitly conveys consent or a prior decision, preserve it. The guard only forbids unsupported commitments.
- These clarifications add **654 total forward prompt characters**, so **no claim of speed improvement**. Prior C2 compression repeatedly increased observed reasoning; whether returning to P168A reduces such calls is untested until actual model runs.
- A previous 100-case comparison assessed the C2 candidate, not this F1 candidate; none of those outputs prove F1 performance.

## Checks actually performed
1. Source P168A fetched from GitHub TEST `prompt-config.json` and compared with the corresponding `wife/main` `prompt-config.json`; byte-identical original blob.
2. H2 canonical SHA-256 algorithm reproduced, independently validated against `abc`, original P168A SHA, and C2-R2 SHA before creating F1; candidate SHA `9b8a3a...` computed on canonical `schemaVersion,channel,promptRevision,forward,smart,back`.
3. All **4 exact replacement anchors** occurred once.
4. Strict diff: `forward.k2l`, `forward.l2k` only. H2 required fields populated, `channel=TEST`, schema v1. SMART/back equality assertions passed.
5. GitHub TEST write and fresh readback verified exact fields, revision and stored SHA; static guard markers present.
6. **NOT performed:** Gemini inference quality tests; actual H2 runtime import/dry-run on user's browser; JS app runtime/regression smoke. Do not misrepresent static checks as dynamic tests.

## Next test decision, respecting paid-call limits
- **Status: UNTESTED / QUALITY HOLD / SERVICE FROZEN.**
- Since this is built from the original P168A, compare P168A vs F1 with both A/B SMART `OFF`, current H2 JSON mode, and the existing H2 **무료 준비 검사** before any paid run.
- Avoid another 100-case run until high-impact cases (#004/#030/#070/#083, both forward and independent back) are evaluated where the existing diagnostic can directly use them, or at most a small balanced new-source pilot with transparent sampling limitations.
- Prefer paired semantic/source checks and independent-back stability over optimizing tokens by shortening.
- A future **independent back-only** candidate must be separate; examples from prior logs: foreign scripts Thai/English #008/#080, temporal specificity #046, wrong participants. Don't mix this work into F1.

Verdict: Valid, checksum-verified **TEST candidate** suitable for controlled validation, **not an approved fix**, not a SERVICE build.
