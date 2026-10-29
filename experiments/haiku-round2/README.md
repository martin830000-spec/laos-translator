# Haiku round 2 — initial128 completed; candidates rejected

Current status 2026-10-29: user approved the first128 only. All128 completed, no retries.
Both new candidates introduced new P0 and were rejected. Further paid calls STOP/HOLD;
SERVICE promotion HOLD. See [RESULTS_INITIAL128.md](RESULTS_INITIAL128.md) and the
original evidence/review links there. Holdout24 and new old22 regression were not run
because neither candidate passed development. Committed approval remains disabled.
The approved one-shot workflow has a consumed permanent tag; do not rerun it.

The following is the preserved free-preparation design and historical status, before approval.

2026-10-29 KST. No new model calls. SERVICE promotion HOLD.

## Evidence and interpretation

Original ZIP: https://drive.google.com/file/d/1GWZtbFCVwd4Ak2p8HQNijDvW0XoUV9I8/view
Prior final Actions: https://github.com/martin830000-spec/laos-translator/actions/runs/40783659740
`prior-manifest.json` hashes all seven extracted files. `prior-index.csv` preserves all 488
path inputs/translations with original request hashes; severity cells deliberately remain
UNREVIEWED rather than fabricating 488 expert labels. Full raw response/configuration
objects remain in the original ZIP. 11 runs, S01–S50: 400 development + 88 final responses.

Observed successes and regressions, reusing the existing report and raw outputs:

| Group | Useful evidence | Failure / interpretation |
|---|---|---|
| S01–05 | S05 symptom senses and third-person readings improve | JSON alone S02 still turns vomiting into laughter; facts are not a verifier |
| S06–10 | S08 role/document distinctions help | S07 Thai script; effort increase does not consistently fix bill |
| S11–15 | S12/S14 receipt versus invoice improves | S15 mixes listener/kinship; more effort not a quality guarantee |
| S16–20 | S18 separate people/events preserves motion in L004 | S17/S19 come→go; appreciation remains weakened |
| S21–25 | S21 bill and unpaid state maintained | S25 combined rules reintroduce kinship alternatives |
| S26–30 | Contradictory receipt/unpaid source retained | K004 invented ownership persists; fact schema not sufficient |
| S31–35 | S31 explicit name retained; S33 neutral sibling improves | S33 erases genuine name in KX02/LX01; blanket semantics unsafe |
| S36–40 | S38 conditional senses keeps name and pronoun distinction | KX02 still adds my friend; single-case success not general proof |
| S41–45 | S41 role constraints useful | S44 sister→bride; S43 kinship regression; simple schema alone already tried |
| S46–50 | S47 retains four diagnostics | S46 symptom addition; S48 script leakage; S49 no effective payload change |

Four-path final22 review (11 original sources each side, 2 arms):
- K FIRST: S47 HK08 inserts explicit first-person sender absent from source. Treat as
  unsupported actor commitment, separate from BACK kinship error. HK09 tense remains uncertain.
- K BACK (L→K): HK08 S47 grandmother becomes aunt alternatives; new P0 in BACK.
- L FIRST: HL02 baseline misreads pronoun as name; S47 fixes person but outputs alternatives.
  Both HL04 outputs omit explicit female sibling information (P1 in prior report).
- L BACK (K→L): HL04 cannot recover lost gender without inventing information; HL07 malformed
  ending requires Lao review. Correct BACK may hide FIRST error; never use roundtrip agreement as gold.

Do not repeat the earlier '2 to 1 P0' count as a complete audit or accuracy improvement.
HK08 actor addition was outside that aggregate; HK09 attribution is unresolved. Native Lao
independent adjudication is absent. These are observations, not experimentally isolated causes.

## New falsifiable hypotheses

Static mechanism: S47 neutral-sibling sense group triggers on the substrings `동생` and
`ນ້ອງ`, including explicitly gendered compounds. Its instruction then says to use a neutral
form without possessives. This conflicts with explicit gender/owner preservation in the core.
HL04 is consistent with that risk, but the original baseline also loses gender, so causality
is NOT established. R2A replaces that note with a symmetric explicit/unspecified information
contract. No sentence-specific answer, grandmother lookup, fixed actor or time rewrite added.

R2B differs from R2A only in translation-only JSON. This tests whether generated fact fields
encourage unsupported commitments after correcting the scoped instruction. S43 already failed
with translation-only output; this is an interaction test, not a claim that simplicity is new.
S38 and frozen S47 are comparator arms, not assumed winners. Candidate bytes frozen before
authoring holdout24. No further candidate edits based on its future output.

## Bounded campaign proposal (not authorized to run yet)

Maximum 50 evidence-supported revisions and 800 total API attempts across the campaign,
including controls, failed attempts and any future evaluator calls (none planned). No retries.
Start with 16 new development sources (K8/L8) × four arms × FIRST/BACK = at most 128.
After complete semantic review, select at most one candidate; freeze its exact bytes.
Run final fresh holdout24 (K12/L12) × S47/candidate × FIRST/BACK = at most 96.
Run old22 as regression only for that candidate = at most 44; reuse old S47 outputs with a
historical/unpaired label. Total first decision cycle <=268. No blind filling to 50 or 800.

Stop with no new defensible hypothesis, two reviewed rounds without gain, or when regression
dominates. Reject a candidate on any new P0 or any path's P0/P1 deterioration; never offset a
bad path by another path's gains. Uncertain/partial labels mean HOLD. P2 variants allowed.
Speed/cost are recorded only and never enter selection. Review source→FIRST and FIRST→BACK
independently, recording error span, reason, severity, first-occurrence path and confidence.
Use blinded arm IDs for adjudication. Quality improvement requires independent final holdout
and regression evidence; static checks alone never qualify. Naturalness/ambiguity needs Lao
language review, not regex scoring or model-generated facts.

New sets are public synthetic, not private conversation data. Exact disjointness from the 488
sources is checked; semantic independence from all historical project data is not guaranteed.
Holdout is independent of tuning outputs but not an independently authored native gold corpus;
its Lao wording needs review before paid validation. Do not tune against holdout after exposure.

## Execution safety and current limits

`runner.py` defaults to a network-free preflight with an injectable transport for free tests.
`--paid` refuses with committed approval.json approved=false, before accessing credentials.
A prepared one-request HTTP transport is reachable only after explicit approval is recorded,
exact candidate/case hashes are bound and model metadata is verified. No paid workflow exists.
It journals payload/settings before every attempt, raw response before parsing, outputs and
usage, and stops immediately on technical error. A permanent exclusive campaign lock blocks
relaunch after success/crash; no automatic resume. Initial128 has a hard 128-call cap and a
90-second request timeout. Raw HTTP failures persist before parse failure. Any later batch
requires review and a new bounded plan counted against the same 800-attempt campaign total;
this commit does not launch later batches. Model metadata/pricing require read-only verification.
Do not use the old campaign approval token or issue trigger as authorization.

Semantic adaptation requires review evidence. There is no autonomous quality oracle and no
unbounded model-driven prompt mutation. Remaining work before live execution: explicit paid
approval, read-only model verification and Lao holdout review. First128 execution is prepared.
Subsequent batch plans require reviewed original results and cumulative budget accounting;
no placeholder fifty-step loop is pre-authorized or enabled.

Offline checks: `python runner.py`; `python -m unittest discover -s . -p 'test_*.py' -v`.
The GitHub workflow is offline-only, read permission, five-minute timeout, no secrets.
Only this research folder and its offline workflow change. Application/H2/DB/Cloudflare/
Cloud Run/SERVICE/old backups untouched. Runtime deployment and device E2E not tested.

Drive fixed manifest/handoff are historical STALE_POINTER references; CURRENT_DEVELOPMENT_DIRECTION
and dated 2026-10-29 handoff are authoritative, with the latest user request overriding old
speed/cost selection rules. Production source HEAD checked, not a deployment health claim.

