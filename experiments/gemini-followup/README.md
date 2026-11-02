# Gemini REAL400 followup — offline TEST

New paid authorization: **0**. New actual Gemini generation attempts: **0**.
Parent: 10960f1f5dd4a0749b2f792019fde3b1a57ef711. SERVICE is untouched.

Run free contracts:
```
python -m unittest discover -s experiments/gemini-followup -p "test_*.py" -v
```
Python 3.11+, Node.js required. No credentials, dependencies or private data are needed.
The existing sibling gemini-real400 adapter and its baseline dependencies are frozen;
they do not make API requests when building or parsing.

Candidates:
- 38SVC reproduces the exact previous SERVICE payload (1024 cap).
- 38FA/FB/FC/FD use the same 2048 cap, low thinking, message envelope and common instructions.
  Context off/on × plaintext/links+states JSON. FD exactly reproduces old 38D.
  FA is a matched laboratory baseline, not the exact SERVICE payload.
- 31D preserved; 31L removes FIRST metadata; 31LL additionally removes BACK anchors
  while retaining semantic and symptom rules. FIRST/BACK factors compared separately.
- 35M changes old 35T high to supported medium only; 35ML removes FIRST metadata
  while retaining medium and 4096 cap. No new quality/latency claim.
- Fixed-FIRST BACK candidates 31C versus 38P consume identical actual displayed text.
  No original, context, source scaffold, grades or history are accepted by build_back.

Private inputs and full context live outside Git. Plans/exposure logs/old raw results are
backed up privately in Drive LIVE_STATE. Tests contain synthetic placeholders only.
The new code does not silently delete foreign text or correct a failed FIRST.

Recommended future ceiling: **272 attempts**, not currently authorized:
P1=96 (8 real messages ×5 configurations ×2 plus4 synthetic contrasts ×4 FIRST),
P2=48 (8 new husband messages ×3 ×2),
P3=32 (16 frozen prior FIRSTs ×2 BACK),
P4=32 (8 real messages ×2 medium configurations ×2),
FINAL=64 (16 sealed cluster-independent messages ×2 recipes ×2).
Phase order/reallocation may change only within a subsequently approved whole cap.
Failed attempts consume the cap. No auto retries, retranslation or AI judge.

Prepared P1-P4 plans are recommended_only=true. execute.py defaults to offline.
After explicit user authorization, activate only the reviewed next phase, set its
recommended_only=false, hash the exact plan with campaign.digest, and record that hash,
the phase ceiling, actual prior attempts and whole approved ceiling in a NEW approval.
Use a fresh persistent journal; retain all prior journals/results; never reuse a phase.
Provide GEMINI_API_KEY only to approved execution, an RSA3072+ recipient PUBLIC key,
and exclusive encrypted output/journal paths. cryptography is required only for execution.
No paid workflow is installed or triggered by this branch. An authorized worker with
API network access is needed; this session has not tested credentials or paid transport.
Do not use the original REAL400 approval or count any prior remainder.

FINAL text binding is blocked until P1-P4 reviews and candidate freeze. verify_freeze
checks every supplied code/review file and winner hash before bind_final reads messages.
A later code/candidate change invalidates the freeze. Freeze the entire implementation
and exact selected direction-specific FIRST/BACK recipes, not just selected files.
Do not modify candidates after opening FINAL or describe reused data as new FINAL.

metrics.py reports API/ready/wall times separately. Cost estimates use the frozen
previous rate table; current pricing/billing must be checked before paid execution.
Missing usage stays unknown. P2 means acceptable semantic equivalence; no paid model
quality is established by these structural tests.
