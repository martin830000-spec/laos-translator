# Opus OB1 — independent BACK role-context ablation

OFFLINE ONLY. No paid calls, model probes, new workflow or SERVICE deployment.

FIRST is byte-for-byte the frozen Opus S1/A builder. BACK deletes only the
`couple_context` block. COMMON, BACK instruction, source, model, adaptive LOW,
max_tokens2048 and text output remain unchanged. The source already carries the
speaker's message, while the deleted block independently primes the original
husband/wife roles. The hypothesis is that less route-identity priming could
reduce unsupported relationship completion during BACK. This is weaker than
the Sonnet hypothesis; no controlled causal evidence establishes the role block
as the cause. COMMON still describes a married-couple translation task, so this
is not total context removal.

It differs from OPT184 B's direct-answer instruction and C's all-block
compression. It is not a Sonnet thinking change and does not switch models.
It cannot recover a male-relative distinction that FIRST already omitted,
repair a misread symptom, or restore an unseen original nickname. Prior role
and ambiguity instructions did not guarantee fidelity. Removing route context
may worsen pronouns, kinship terms, spouse speech or naturalness. Those risks
must be tested if this hypothesis is ever prioritized.

At present allocate Opus0 new paid calls. Existing Opus FIRST is slower and
costlier than the target, this candidate changes FIRST0, and the estimated
BACK benefit is uncertain. Keep the actual ablation code as a reproducible
research result, not a claim of improved translation. Do not revive C or claim
its shorter FIRST proves semantic improvement. No further candidate churn is
justified solely by the presence of this prototype.

Use the shared offline CLI with candidate `opus-ob1`; normal requests stay
FIRST1 + own independent BACK1, with a single Opus engine for all four routes.
