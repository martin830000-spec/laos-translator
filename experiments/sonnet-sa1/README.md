# Sonnet SA1 — adaptive LOW, frozen S1 words

OFFLINE ONLY. Paid generation, authentication probes and token-count calls: 0.

S1 produced visible draft/correction text despite an existing prohibition. Its
export reports zero thinking tokens under `between_tools`. SA1 changes only
`thinking.type` to `adaptive`: same model, LOW effort, max_tokens2048, all five
S1 prompt blocks, user template and text-only response. Internal deliberation
might reduce unfinished drafting or semantic commitments before emission. This
is an inference, not a measured causal explanation. Adaptive LOW can still skip
thinking, leak commentary, invent a fact, exhaust2048 or increase latency/cost.

This differs from SJ1's single-field JSON format constraint and Haiku's
facts/source-copy structures. No examples, source-specific rule, new schema,
term dictionary, helper model, second draft or retry is added. Previous Haiku
adaptive failures are negative evidence, not proof about this Sonnet setting.
No historical Sonnet adaptive run was found in the recovered evidence; that is
not proof that none exists anywhere. Second/SJ1 raw exports remain missing.

The shared core preserves all text blocks including suspicious text; thinking
blocks stay out of display and BACK. A warning does not repair or certify meaning.
Use `claude-rd-core/cli.py sonnet-sa1 first|back|inspect --side K|L --input ...
--output ...` to prepare a NEW local file. Back accepts only a stored FIRST
response. No network transport or active workflow is installed.

The recommended future experiment is one separately approved24-attempt plan,
not an automatic execution. See the private frozen manifest and final report.
