# GEMINI_NEXTGEN_REAL128_20261103 — protected real API research

Only user-approved new Gemini 128 attempts; old ITERATE320/NUANCE256 are exhausted, never reused.

Phase caps: DISCOVERY_A 48, REFINEMENT_B 32, INDEPENDENT_FINAL 48. Private plans and outputs are authenticated RSA3072/AES256-GCM through unique owner-origin GitHub Issue; runner artifact contains ciphertext only. Source messages are never committed or printed. `GEMINI_API_KEY` is injected only at the single paid step. No automatic retry or judge. P0/P1/P2 judgments are manual, post-phase.

Approval starts as `authorized=false` and remains so until signed off and sealed private inputs prepared. Only `config.json` push triggers paid workflow. Each phase's consumed Git tag is created before any API call, and prior phase tags are required. A pre-send encrypted checkpoint records every attempt; restart/re-run is prohibited. A failed FIRST skips only its dependent BACK. All unused planned calls remain unused, never reallocated.

Use `engine.build_first`, `engine.build_back` frozen contracts, with a single common 3.8 BACK profile for both arms. SERVICE's P168A baseline is inherited from already validated `gemini-followup/adapter.py`. The GitHub source tree must not contain real messages, results, Secret, private key, raw plan, or any cached data.