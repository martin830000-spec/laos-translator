# Haiku root-cause offline diagnostics (2026-11-02)

Read-only diagnostic; no HTTP transport, credentials, model inference, correction, retries, or deployment.

- replay_diagnostic.py reconstructs declared units display exactly, records alignment/empty-target warnings, and checks the actual producer display against BACK input.
- test_replay_diagnostic.py uses synthetic fixtures only. Run: python -m unittest discover -s experiments/haiku-root-cause-20261102 -p 'test_*.py' -v
- validate_relations checks human annotation span provenance only. It cannot certify Lao semantics.
- public_receipt.json contains counts only. Private originals, model outputs, annotations, and archived requests remain outside GitHub.

An exact source echo and valid JSON do not prove semantic fidelity. A blank target may be merged into an adjacent target; warn for manual global review, never automatically mark a semantic failure. Incomplete responses are not salvaged. No new translation candidate was implemented because the examined alternatives overlap earlier failed methods or lack an independently verified semantic parser.

No API workflow is added. Frozen candidates and SERVICE are unchanged. Contract success is not translation-quality improvement.
