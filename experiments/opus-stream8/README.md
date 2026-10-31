# Approved Opus C stream8

Exactly four frozen sources (K2/L2), FIRST4 plus own completed display BACK4,
maximum8 attempts. Existing 120 baseline is never replayed. The decoder and C
prompts are unchanged; only stream:true is added. No H/S calls, probes, retry,
fallback, automatic repair or monetary gate. A failed FIRST skips only its BACK.

Private encrypted input/output channel reuses s47-realuse16 crypto. Public
logs contain counts/status only. A separate consumed tag and journal prevent
reuse. Real wire chunks, events, partial text and previews remain private.

Timings start immediately before HTTP open. read1 receives available chunks.
first_text_received_ms is the receive time of the chunk first decoded into
non-whitespace text; display_ready_ms is after parsing that chunk. Neither is
an actual browser/app render measurement. api_complete_ms is message_stop.
PENDING previews are append-only; BACK waits for end_turn and message_stop.
