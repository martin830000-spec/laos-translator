# Sonnet / Opus research core — 2026-10-31

Offline preparation only. `live()` always raises PermissionError. No secrets,
model HTTP, token counting, API authorization probes or paid workflow exists.

Baseline provenance: TEST commit3de7a02c128101080113e5dd786ee5d686b4d522,
engine-comparison-haiku-r2-f1-ib1-20261027.html blob
d81995315f29506f834cc5e513452e7476e5415c. All five S1 strings match that remote
source. The baseline builder also exactly reproduces66 recovered, development-
eligible Opus A request payloads after applying the union of protection lists.
Source text, private output, API credentials and private keys are not in this
directory. s1-prompts.json contains only previously public instructions.

Run offline tests from the repository root:

    python -m unittest discover -s experiments/claude-rd-core -p 'test_*.py' -v

Prepare a request locally (never submit it):

    python experiments/claude-rd-core/cli.py sonnet-sa1 first --side K --input PRIVATE.txt --output PRIVATE_REQUEST.json
    python experiments/claude-rd-core/cli.py sonnet-sa1 back --side K --input PRIVATE_FIRST_RESPONSE.json --output PRIVATE_BACK.json

The response inspector preserves model-authored text exactly, emits advisory
script/draft warnings, separates thinking by content type and leaves semantic
quality UNVERIFIED. Incomplete/empty FIRST preserves partial text as evidence
and produces SKIPPED_DEPENDENCY for BACK. No salvage or automatic correction.

The candidates deliberately differ: SA1 changes one Sonnet thinking parameter;
OB1 deletes one Opus BACK prompt block. Neither is an app integration or a
SERVICE adoption. Do not infer quality, real latency, billing, or native Lao
naturalness from static tests. Explicit future approval must bind a private
source manifest and call cap, with fresh one-shot consumption records. No older
paid authorization, remaining experiment slots or completed lock is reusable.
