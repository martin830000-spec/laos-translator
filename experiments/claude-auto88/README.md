# FCA1 native-format contract alignment — isolated TEST

Completed 2026-11-02: new translation API attempts46/approved88, unused42.
Phase1:14 new Sonnet FIRST plus2 exact historical S2 baselines reused. Phase2:32 new calls (Sonnet16 FIRST and Opus16 independent BACK). Phase3:0/32, stopped for no demonstrated practical advantage on fresh normal messages.

Candidate B changes only two output-contract sentences in frozen S2 system text so the one-field native JSON contract and legacy plaintext instructions are aligned. All meaning instructions, current source bytes, model, thinking between_tools, LOW effort, max_tokens2048 and native schema remain fixed. A is frozen S2. Both use frozen Opus OPT C for BACK. No external parser, graph, examples, name answers, extra analysis model or post-processing.

Observed quality is useful within the small tested scope. Historical diagnostic gains do not prove structural improvement. Fresh normal outputs largely pass P2 in both arms; context-dependent REVIEW remains. No general semantic superiority or faster FIRST across both directions was demonstrated. A short-sample husband-direction latency signal is retained in the private report. Preserve candidate for offline inspection; freeze this approach. SERVICE and active policy are unchanged. The model itself is not rejected.

## Reproduce without new paid calls

1. Check out this research branch; do not merge into SERVICE.
2. Run contract checks: `python -m unittest discover -s experiments/claude-auto88 -p "test_*.py" -v`.
3. Download the private evidence ZIP provided to the authorized owner, extract it privately, then run `python verify_evidence.py` there. This replays saved payloads, extraction and FIRST→BACK edges without network/API calls.
4. To prepare a payload from your own local UTF-8 source file, without sending it: `python experiments/claude-auto88/offline_prepare.py --input local-source.txt --side K --stage first --arm B --output new-payload.json`.
5. For an independent BACK payload use only an exact actual FIRST display file, `--stage back`, same side, and a new output path. Never provide original/history/another candidate result.

No live API key is read by `offline_prepare.py`. Output files are created exclusively and never overwritten. JSON validity is not semantic correctness; extraction preserves any repetition/commentary inside translation. Thai/Chinese text is not automatically deleted or retransmitted.

The approved phase consumption tags and run_attempt1 guard remain. Do not delete them, rerun this campaign, refill failures or reuse unused calls. Any future live research needs a separate authorized plan. Mobile paint was unmeasured; Lao native-speaker validation was not performed.
