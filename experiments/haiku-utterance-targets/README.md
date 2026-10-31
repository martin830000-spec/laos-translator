# LA2: client-grounded utterance boundaries — OFFLINE ONLY

LA1's actual A/B40 produced a missing target separator, a source-space omission,
and locally mistranslated medical/work/name terms despite valid copied source.
This experiment addresses boundary ownership and source-echo overhead only.
It is not evidence of a remedy for the semantic errors.

The client losslessly partitions at explicit sentence punctuation/newlines,
keeps the entire message as shared context, and requests indexed natural target
utterances without model-generated source copies. The display joins complete
utterances by newline. Count/order/unique indexes are mandatory. No guessed Lao
word segmentation, source-specific glossary, medical correction, semantic
validator, automatic retry, second draft or model judge is added.

Differences from S48 flat quotations and LA1: boundaries belong to the client,
targets are complete utterances rather than arbitrary adjacent source fragments,
and there is no source echo or separate rewritten global target. It partly
overlaps earlier translation-only R2B, which already exhibited semantic additions;
therefore it is a bounded engineering hypothesis, not a renewed claim that
translation-only output solves role or fact errors. It cannot make an unknown
Lao term understood. For unpunctuated Lao the full message is one utterance.

Potential disadvantages: extra request bytes from duplicated source input,
paragraph-like chat display, loss of clause-level evidence, unchanged semantic
misinterpretation, abbreviations mistaken for sentence endings. Lower output
tokens/latency and improved model naturalness are unmeasured hypotheses.

There is no transport, executable paid campaign, approval, active workflow or
deployment for LA2. Run `python -m unittest discover -s experiments/haiku-utterance-targets`.
Keep LA1 frozen. Any future model test needs a separate user decision and must
compare all four routes against stored outputs, with fresh ordinary controls,
not merely the boundary case. Wrong-but-valid meaning passes the negative
control deliberately. SERVICE promotion is outside this experiment.
