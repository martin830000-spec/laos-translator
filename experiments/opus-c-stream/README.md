# Opus C incremental display — OFFLINE TEST ONLY

The real20/120 comparison retained meaning relatively well with Opus C, but
average FIRST completed in3.548s (maximum8.197s), and a full pair in6.962s.
The research transport currently reads a complete JSON body before showing
anything. This candidate makes that client buffering step testable: unchanged
Opus C request plus `stream:true`, incremental text prefixes, and separate
first-visible-text/complete timings. It changes no prompt, thinking, effort,
token cap, lexical rule or model. There is no HTTP client or live trigger here.

The SSE decoder handles UTF8 byte splits, CRLF frames, typed content blocks,
cumulative usage and termination. Thinking/signature events are retained in
the event journal and excluded from visible text and BACK. Opus C's existing
outer-whitespace trim is preserved with a pending whitespace buffer, so each
visible prefix only appends. Tags, odd language, mistakes and explanations are
never stripped, corrected or replaced. Partial text remains on failure.

BACK is prepared only after message_stop with end_turn and nonempty text.
Refusal, error or incomplete streams skip their dependent BACK, without retry,
fallback or resumed generation. Only actual completed FIRST display text goes
into BACK. Streamed previews are PENDING and must not be marked final by a UI.

This does not fix Haiku conditional/phone interpretation, Sonnet date errors,
or Opus literal final-tag leakage. It does not reduce model cost, thinking,
generation time or guarantee1–2s display. Up-front thinking can delay the first
text too. The original 120 were non-streaming; real TTFT is UNMEASURED. Offline
re-serialization of stored outputs is a parser test, not real streaming data.

Next proposed test: Opus C streaming only, K2/L2, FIRST4+own BACK4=8 new calls,
separate approval required. Reuse real20 non-streaming outputs as references;
measure first text versus completion within each same streaming request rather
than replaying completed baseline calls. Retain all four routes and adverse
outputs. No generation occurred for this candidate. No SERVICE integration.

Reproduce: `python -m unittest discover -s experiments/opus-c-stream -p 'test_*.py' -v`.
The Python API is build_request(), Decoder.feed()/event()/finish(), prepare_back().
See https://platform.claude.com/docs/en/build-with-claude/streaming for the wire protocol.
