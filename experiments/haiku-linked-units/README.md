# LA1 — linked verbatim source and target units

Implemented TEST candidate; model translation quality and provider acceptance are
unverified. Current authorized paid calls: **0**. Core adapter/scheduler/CLI have
no HTTP client or key lookup. The prepared Actions bridge reuses the existing
transport and Secret only after its false-by-default approval guard. Its YAML
template is outside `.github/workflows` and has not been registered or run.
There is no deployment, automatic retry or model judge.

## Mechanism

Frozen S47 generates paraphrased `source_people`/`source_events` followed by an
independent global `translation`. Existing responses show both incorrect facts
before rendering and correct facts followed by invented content in translation.

LA1 replaces that representation with ordered adjacent pairs:

```json
{"units":[{"source":"exact first chunk ","target":"target fragment "},{"source":"exact remainder","target":"target remainder"}]}
```

Only the exact concatenation of all model-authored `target` strings becomes the
visible translation. No separate free global rewrite can bypass these pairs.
The preceding `source` in each pair is literal current input, not an inferred
person/event paraphrase. Coherent chunks are chosen by the model while retaining
the complete current message for context; short messages may use one unit.
Within-unit target word order is free. This is a testable conditioning hypothesis,
not a semantic guarantee or a deterministic numeric correction.

Keep the frozen S47 instructions, source-triggered sense groups, model
`claude-haiku-5-5`, LOW/disabled/2048 and original user message. The application
delta is an output-contract paragraph plus a static units schema. There is no
Unicode pattern. Private text is never embedded in schema definitions.

### Difference from earlier failed experiments

S43/R2B removed facts and left a free global translation. S48 retained a flat list
of selected quotes followed by a separate global translation. LA1 couples each
quote directly to its rendered fragment and assembles only those fragments.
This is related to S48, not an unrelated invention; the local coupling and
rendering path are the new intervention. S16/H2's no-explanation/completeness
wording is not claimed as a new mechanism. H1/R14's persona change and SC1's
Unicode decoding pattern are not reused.

## Exact behavior and limits

`inspect_response` accepts only a complete whole JSON object. Multiple JSON
objects, duplicate keys, malformed units and max_tokens are not salvaged.
Target fragments are concatenated without stripping, normalization or invented
separators. The result can still contain a wrong amount, negation, symptom,
meta explanation or language. Negative tests deliberately demonstrate this.

If the source quotes do not reconstruct the input exactly, the result is
preserved with an advisory warning. No readable target is hidden, repaired or
replaced for an alignment warning. Source-copy success is not meaning accuracy.

Long source echoes can increase output tokens, exceed2048, slow first display,
or produce rigid prose. One-unit output may provide little local-coupling
benefit. Unknown words can still be misunderstood. All require actual A/B data.

## Interfaces

- `build_request(visible_text, side, stage, variant='LA1')`
- `inspect_response(response, visible_text, side, stage, variant='LA1')`
- `SinglePassSession(side, variant).run(source, transport, persist)`
- `campaign.schedule(private_manifest)` — no network
- `campaign.run_approved(private_manifest, approval, transport, journal_path, persist)`

`side` is K/L and `stage` is first/back. Every BACK receives only its actual
candidate FIRST's rendered translation. Quote units, original source, Gemini,
history and another candidate's result never cross that boundary.
The supplied transport is called once per eligible stage. Failed FIRST -> only
its BACK is skipped. Other independent sessions continue in the campaign.
Authentication/model-integrity and journal failures are global stops.

The campaign requires exact private-manifest approval and an exclusive new
one-shot journal. It reuses24 historical S47 outputs without sending requests,
and allows at most40 new attempts. `approval.json` is false. A caller still must
establish actual user authorization before enabling a future encrypted Actions
bridge; changing a JSON field is not itself a user's approval.

## Reproduce offline

Run from the repository root:

```powershell
python -m unittest discover -s experiments/haiku-linked-units -p 'test_*.py' -v
python experiments/haiku-linked-units/cli.py prepare-first --side K --input PRIVATE_SOURCE.txt --output PRIVATE_REQUEST.json
python experiments/haiku-linked-units/cli.py prepare-back --side K --input PRIVATE_FIRST_RESPONSE.json --visible-input PRIVATE_SOURCE.txt --output PRIVATE_BACK_REQUEST.json
```

CLI modes only create a new local file or inspect a stored response. Source
reading preserves CRLF, spaces, combining marks and emojis. Never place these
private files in a public Git path. The CLI does not submit model requests.

Final new test suite:15/15 PASS (not SC1's old13 tests). No model output was
generated. The private evidence package contains the exact frozen proposed
manifest, real16 static payload hashes, cause audit and test receipt.

`actions_bridge.py` and `actions-workflow.template.yml` supply the prepared
integration with real48's Secret/encryption infrastructure. Approval is checked
before any state/key read, HTTP or authentication probe. No new key is required.
After explicit approval, register the template in TEST and freeze the exact
approved manifest/commit. That activation work remains; no paid trigger was
installed or dispatched here. Bridge reproduction requires cryptography50.0.2,
the same pinned dependency used in earlier encrypted campaigns.

See `AB_PLAN.md` for the one proposed40-attempt comparison.
