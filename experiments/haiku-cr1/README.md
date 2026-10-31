# CR1 human parallel retrieval research — NOT a paid recommendation

Source-only local character-ngram retrieval over an attributed, mechanically
filtered FLORES-200 dev Korean/Lao corpus. No private examples, generated target
labels, embeddings API or unseen original in BACK. Exact answer matches excluded;
unrelated/low coverage references abstain. Original LA1 request then stays exact.

Data source: NLLB Team/Meta AI FLORES-200, CC-BY-SA4.0.
https://github.com/facebookresearch/flores/tree/main/flores200
Only dev Korean/Lao was read. No devtest, hidden test or project holdout used.
Build corpus with analysis/build_corpus.py; retain provenance and original license.
Human professional translation does not guarantee every row or colloquial use.

997 aligned pairs,460 budget/script-filtered pairs. Five current diagnostic
queries retrieved0 suitable references at the prechosen conservative thresholds.
Do not lower thresholds just to force references or claim quality improvement.
Keep as a reproducible research artifact; LB1 is the separate practical hypothesis.
