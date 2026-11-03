# Gemini semantic FIRST / independent BACK — free research

2026-11-03 KST. PROPOSAL ONLY. Authorized 0 / consumed 0 / remaining 0.

K_NEUTRAL_31: Gemini3.1 Flash-Lite minimal, message-only neutral input.
L_STANCE_38: Gemini3.8 Flash low, stance-preserving conversational Korean.
COMPACT_BACK: Gemini3.8 Flash low, only actual displayed FIRST, no family role metadata.
Pure builders and offline graph; paid execution transport is deliberately not installed.
No API keys, private original messages, judge, retry, deployment or operational source change.

`node --test experiments/gemini-semantic/contracts.test.cjs`

29 offline tests verify structural contracts, not translation quality or latency.
Proposal: A40 (FIRST20 BACK20), B24 (FIRST8 BACK16), FINAL64 (FIRST32 BACK32).
A fixes actual frozen SERVICE BACK across both arms. B compares two BACK contracts on
the same displayed FIRST. FINAL is unseen, after candidate/config/prompt freeze.
Daily runtime arm remains SINGLE_PASS (one FIRST + one BACK).

Historical REAL128 provenance caveat: SERVICE-labelled arms used research
NX_BACK_38_FREEZE_V1, not production P168A BACK. Do not call its historical BACK
latency a direct measurement of production BACK. This package includes the exact
frozen P168A service-contract.cjs / prompt-config.json from REAL128 close SHA
ca0e73d41b3a75c79b20eb0d8cdbb2e379cad309 (byte hashes in manifest).
SERVICE model settings low/1024; new FIRST2048; compact BACK1024.
This tests the whole neutral/short contract bundle, not isolated causal proof that
one removed role field caused an error. Do not add case-specific word bans.

New paid approval must be explicit and campaign-specific. Consumed historical
320/256/128 approval cannot unlock this work. No paid workflow is installed.
After approval: bind private source selection, implement reviewed transport with
fresh one-time phase nonce/tag, count before send, skip failed-FIRST dependents,
persist encrypted evidence, stop for stage review, freeze before FINAL.
