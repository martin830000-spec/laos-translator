# Gemini alternative V2 — blocked before paid execution

Authorized maximum: 500 requests per model in independent V2 campaigns. Actual: 0/500 each. The configuration is locked (false/0). This directory contains BASE freeze, approval/checkpoint/empty ledgers, offline gate checks and unexecuted hypothesis review only. There is no new paid runner or activation workflow.

The current Work executor has no configured GCS identity. The public GitHub research repository cannot hold private plaintext outputs. The previous GCS-to-Work path used a CMS-encrypted artifact; the V2 instruction forbids that path. A direct GCS Console browser check returned Site Unavailable. No safe end-to-end plaintext recovery route has yet been verified. Drive upload/readback works independently; it does not prove the runner-to-Drive leg. No IAM, secrets, sharing or old campaign locks were changed.

Resume condition: an already-authorized private plaintext GCS-to-Work/Drive readback path must pass a non-sensitive free roundtrip, owner-only permission check and SHA256 verification first. If such access is not available in the next environment, a user-authorized environment connection is required; do not publish outputs, expose credentials or restore file encryption as a workaround. Then recheck current branch/BASE, select non-overlapping samples, implement candidates, run free checks and activate only the approved first stage. Authorization does not need to be renewed merely because no calls were used.

Offline checks: `node experiments/gemini-alternative-v2/test.cjs` and `python3 experiments/gemini-alternative-v2/test_gate.py`. Free checks are not translation quality evidence. Existing BASE and all previous research files remain unchanged.
