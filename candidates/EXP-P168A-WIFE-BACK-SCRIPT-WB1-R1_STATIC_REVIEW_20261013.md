# WB1 R1: wife independent back Lao-script purity — STATIC REVIEW

Date: 2026-10-13 (KST) | **TEST-only; QUALITY HOLD; no inference performed**

## Purpose and ground truth

Fix a **single error family** identified in existing 2026-10-13 H2 runs: Thai-script fragments or stray Latin/English words in the *wife's independent Korean→Lao back-translation*. No user/spouse message content or private fixed test sources are included in this public-repository document. Previous audit references:
- `RUN-20261013-133128-97e259`: #008 (Thai-script fragment), #080 (stray Latin fragment), #046 (spurious number/time in reverse; separate **out-of-scope** defect).
- `RUN-20261013-141831-538884`: #042 (English word inserted in Lao reverse, plus separate pregnancy-time semantic distortion).
- `RUN-20261013-125631-52922e`: #002 and #048 (speaker/role problems **out of scope**).

Do not assume all of these will improve: only unsupported foreign-script insertion is directly addressed by the single modification. Names, numeric ranges, pregnancy-week vs birth-age, speaker inversion and time specificity remain independently assessed.

## Candidate identity and strict diff

- P168A TEST runtime base: `prompt-config.json`, canonical SHA `7d28766e1f9938a531fed5870585cb4a3afe735e2c41cc25b511ff7f677ddd43`.
- Candidate: `EXP-P168A-WIFE-BACK-SCRIPT-WB1-R1.json`.
- Revision: `EXP-P168A-WIFE-BACK-SCRIPT-WB1-R1`.
- Candidate canonical SHA: `ba7e198673375f1edc56e50d83bc0109efc036798a206b24a03cd0499a76537a`.
- **Changed field: `back.wife` ONLY**, from 2301 to 2819 characters. Existing output instruction extended in place to enforce natural Lao script for common translated words without emitting Thai letters or unasked English/Latin fragments.
- Exceptions preserve source-present Latin strings, URL, internationally standard technical acronyms, identifiers, and recognized proper/brand names even when Korean uses Hangul for the brand. No name/term deletion or forced language purity when identity would change.
- Byte unchanged vs P168A: `forward.k2l`, `forward.l2k`, all eight `smart.*` fields, `back.husband`, `back.husbandRecovery`, **`back.wifeRecovery`**. Normal single-pass testing uses the independent back, not a retry/recovery prompt. Changing the recovery prompt now would confound the single-field test.
- Metadata revised; schema `1`, channel `TEST`. SERVICE V3.61.209 / P168A R8 / G158A remains frozen. No H2/UI, backend, Cloudflare, DB or deployment change.

## What was actually verified

1. Fetched original `prompt-config.json` from TEST repo, separately checked against `wife/main` P168A metadata and common blob.
2. H2-compatible canonical SHA-256 algorithm validated against known `abc` digest and P168A canonical SHA before calculating the new candidate SHA.
3. Exactly one replacement anchor in `back.wife`; no appended duplicate sections, no modifications to previous prohibitions on meaning invention, register, role, tense, number or incomplete input.
4. GitHub write and **fresh readback** checked required field types, source equality for all unchanged fields, exact field diff `back.wife`, guard presence, SHA metadata.
5. Inspected H2 `promptCompareCandidateConfig`, `pcChanged`, and `promptCompareCandidateBack`: JSON comparison can detect and apply back-only candidate via isolated clones, without a new H2 build.
6. **NOT performed**: Gemini calls, direct runtime browser test, native Lao linguistic grade, service promotion or dynamic smoke test.

## Fixed evidence and test caveat

A private file in the user's current ChatGPT artifact workspace, `KO_LAO_WIFE_BACK_WB1_FIXED_INPUT_PRIVATE_20261013.json`, contains **8 historical wife (L2K) examples** with cached Korean forward texts and both observed Lao independent-back outcomes. This contains personal conversation content; **DO NOT upload it to this public GitHub repo** or cite it as source for public logs. Categories: 3 targeted script/Latin failures; 3 other semantic/role regression controls; 2 preservation controls.

**Critical confound:** Existing H2 A/B normally regenerates forward Korean independently on A and B, even when the two forward prompts are byte-identical. Therefore differences between back outputs may come from different forward strings, not from `back.wife`. For a decisive back-only test, feed **identical cached Korean forward text** to the two back prompts (if the existing H2 workflow supports it without new tool changes), or restrict interpretation to records where A and B forward strings are exactly equal. Do not claim the four-path run itself isolates the back prompt otherwise. H2's common `SMART_SCOPE ... back unchanged` log label describes the SMART toggle, not a back-only candidate's `CHANGED_FIELDS` diff.

## Gate

- **Static-ready TEST candidate, QUALITY HOLD.**
- First inspect the eight private fixed-source examples offline; no paid calls necessary for that review.
- If a future paid test is explicitly requested, existing H2 `JSON_SMART_OFF` comparing original P168A vs WB1 is capable of loading the candidate. However the standard 20-record default includes 10 husband records where **nothing changed**, and may include zero target examples. Do not suggest another random 20/50/100 case run as proof of the script fix.
- Any future production candidate must pass unchanged meaning, identity/brands/acronyms, numeric/timing, person/register, no Thai-script/unsolicited English, reliable latency and cost, with no new regressions in the other three paths.
