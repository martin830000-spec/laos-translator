# Gemini model-specific prompt research, 2026-11-02

TEST branch only. No SERVICE, main, infrastructure, data or active-policy changes.
New authorization: at most 320 generateContent attempts including failures, independent
of the closed 152/200 campaign. No retries, external suppliers or AI judging calls.

The control is the exact P168A R8 service-contract.cjs and prompt-config.json frozen
by gemini-auto200. The model IDs and supported levels remain 3.1/3.5 MINIMAL and
3.8 LOW, maxOutputTokens 1024. Standard synchronous generateContent, no Priority,
JSON schema, streaming, cache creation or post-generation correction is introduced.

New candidates are identified by 31N, 35N and 38N. Model-specific instructions are
defined in adapter.py. Each current request and actual system prompt is preserved
with SHA256 in the private evidence; BACK receives exactly its completed FIRST's
display string as its only user message. No initial source or reference is available
to BACK. The source itself remains byte-exact, including emoji and malformed input.

31N tests a compact positive translation contract with source-clause scope, rather
than adding another temporal patch to R13 C1/C2/C3. This is related to prior
source-first research, not a claim that clause rules are unprecedented or proven.
35N moves a Lao target-language instruction to the start of the Lao-target system
and uses a compact task contract in place of the long English rule stack. It is
distinct from the stopped 35J JSON-format mechanism. 38N consolidates the inherited
meaning constraints and keeps explicit conversational readability. Compression is
only a hypothesis; omissions and regressions count against it.

The private client selects only already-authorized LIVE500 DEVELOPMENT records
after split/source-SHA and protected-hash validation. Case-level references and
private originals are not committed. Existing protection metadata is applied before
showing eligible sources. No HOLDOUT or SEALED source is selected. Newly selected
DEVELOPMENT is not a certified unseen holdout, and related conversations may be
correlated. P2 is passing; uncertainty is REVIEW and is not a confirmed failure.

Reproduce the request without a key or API call:

```sh
python -m unittest discover -s experiments/gemini-prompt320 -p 'test_*.py' -v
python -c "import sys;sys.path.insert(0,'experiments/gemini-prompt320');import adapter,json;print(json.dumps(adapter.build('오늘 저녁에 전화할게.','K','first','31N'),ensure_ascii=False))"
```

Frozen per-phase configs/approval/manifests and a consumption tag prevent accidental
replay. The committed consumed config is not a standing grant for another paid run.
Only encrypted private payloads and public-key handshakes pass through GitHub issues
and artifacts. Private decryption keys and API keys are never included in evidence.
API timings do not measure mobile screen paint. Usage estimates are not invoices.
