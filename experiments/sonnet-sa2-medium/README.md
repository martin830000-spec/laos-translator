# Sonnet SA2 MEDIUM — OFFLINE ONLY, NOT AUTHORIZED FOR GENERATION

SA1 real8 A/B24 has completed. All16 SA1 responses reported thinking_tokens0,
and two FIRSTs exposed draft/correction prose. One dependent BACK returned
refusal/reasoning_extraction. Adaptive LOW did not show the intended separate
thinking channel in this sample; this is not proof that the API ignored the
setting, nor access to the model's internal reasoning.

SA2 changes exactly one request field relative to frozen SA1:
output_config.effort low -> medium. The Sonnet-specific official prompting
guide says medium generally thinks before replies, whereas LOW often skips
thinking on simpler requests. Whether that applies to these translations and
improves meaning is UNMEASURED. Model, adaptive thinking, S1 prompt blocks,
source, max_tokens2048 and response/display logic stay unchanged. No extra
instruction asking for reasoning, source-specific exception, JSON grammar,
facts summary, glossary, second model or regeneration is added.

This is a model-specific missing-mechanism hypothesis, not a claim that effort
changes are a new general technique. Previous Haiku adaptive/medium experiments
failed and Opus adaptive LOW had semantic errors and latency. Those results
are contrary evidence, not proof that Sonnet MEDIUM will improve. Recovered
Sonnet S1/SJ1 did not provide a Sonnet adaptive MEDIUM comparison.

The 2048 budget now may leave less room for text, and first-display latency and
cost may worsen. This is a material risk, not fixed by an offline test. MEDIUM
can still choose the wrong Lao meaning or expose drafts. There is no measured
translation quality, token cost, latency, refusal reduction or native Lao
naturalness result for SA2. Do not promote or run it automatically.

Refusals remain failures; no fallback or retry. Do not strip commentary from a
FIRST to force its BACK to succeed. Only actual visible FIRST text can cross
the BACK boundary. Existing model-authored text is preserved, with advisory
warnings only. `prepare_back` accepts no original source or hidden analysis.

No live transport, new paid workflow, approval or model probe is supplied.
Prepare local files with `python experiments/sonnet-sa2-medium/cli.py first --side K --input PRIVATE.txt --output PRIVATE_REQUEST.json`.
Run `python -m unittest discover -s experiments/sonnet-sa2-medium -p 'test_*.py' -v`.

Sources: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5
and https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback .
