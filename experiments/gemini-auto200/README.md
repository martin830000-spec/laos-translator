# Gemini autonomous200 TEST, 2026-11-02

Isolated research only. Main and SERVICE are unchanged. No deployment or automatic scheduling.

## Contracts

`service-contract.cjs` and `prompt-config.json` are byte-identical frozen P168A R8 request/display contracts. Standard profiles change only the model and its supported thinking level: 3.1/3.5 MINIMAL, 3.8 LOW, all maxOutputTokens 1024. This is a practical configuration comparison, not a thinking-only causal experiment.

`35J` adds actual Gemini native JSON responseMimeType/responseSchema and an outer-contract clarification. It extracts the single translation string strictly, preserves contamination inside it, and applies only the existing SERVICE display transforms. JSON validity does not prove language or semantic quality. This method was stopped after mixed actual results, including an all-Latin Lao-target message.

`38P` changes only FIRST's native service_tier to priority; BACK stays standard. Tier application and premium cost must be verified from the response header. Missing/unsupported tier does not trigger a retry. `31H` uses 3.1 FIRST and standard3.8 BACK, with the actual FIRST as sole BACK user input. It cannot repair a FIRST omission by seeing the original.

## Free reproduction

Python3 + Node18+; the offline adapter has no key dependency.

```sh
python -m unittest discover -s experiments/gemini-auto200 -p 'test_*.py' -v
python experiments/gemini-auto200/offline_prepare.py --side K --variant 31H --text "오늘 저녁에 전화할게."
```

For BACK, pass the actual displayed FIRST, set the original route side and `--stage back`. Never pass original input, another candidate output, history, reference translation, or evaluations. These commands perform zero API requests.

The owner-only private evidence archive contains original UTF-8 inputs, provider HTTP bodies, usage, IDs, case-level manual verdicts, frozen phase code, ledgers and a network-free verification script. The Actions transport is authenticated and encrypted. Public code/logs contain no personal messages or key values.

## Execution and limits

Phases have new consumption tags and manifests; limits48/72/80 and total200 include failures. FIRST failures skip their dependent BACK. Existing tags prevent replay, run_attempt must be1, no SDK retries, redirects, AI judge, hidden retranslation, cache padding or deployment. The committed config refers to an already consumed research phase and is not a grant for further paid execution. New research needs a separate explicit budget.

Private verdicts distinguish P0/P1, passing P2, REVIEW, and faithful propagation of FIRST errors. Lao native review and mobile screen paint were not measured. Direct provider timings are not phone timings; historical stored FIRST plus a new BACK is not a concurrent roundtrip measurement.
