# R4C — Translation LLM Adaptive TEST staging, 2026-10-15

Status: BRANCH CODE ONLY. No Cloud Run deployment, no Cloud IAM changes, no paid API calls.
Development branch: test/engine-compare-r4-lara-tuning-foundation-20261015

Staged files:
- engine-comparison-test-r4-20261015.html — optional 8th comparison lane Google Translation LLM Adaptive, off by default.
- test-relays/translation-adaptive-r4/server.js — isolated Cloud Run TEST service using ADC and Cloud Translation v3.
- test-relays/translation-adaptive-r4/server.test.js — offline tests for payload, token, CORS, rate and per-process daily count.
- test-relays/translation-adaptive-r4/package.json and README.md.

Offline/connector mock tests completed:
- Service handler returned simulated statuses 204,401,403,200,429,200,200,429; no provider network calls.
- Browser 7 lanes × 8 cases × forward/back => 112 mocked calls, 56 results.
- Browser 8 lanes with Adaptive × 8 cases × forward/back => 128 mocked calls, 64 results; 8 KO→LO and 8 LO→KO Adaptive calls.
- Bad Adaptive reference pairs reject BEFORE all paid calls; no TEST token/reference texts persisted in localStorage.
- P168A 4-route prompt selection and Gemini LOW static tests previously passed.
- Actual provider auth, response quality, charges, Cloud Run deployment, CORS in production browsers, native Lao verification NOT tested.

Security: No Google service account key in GitHub Pages; runtime scoped role cloudtranslate.user after explicit IAM permission setup. Separate TEST service only. CORS is not authentication; public Cloud Run should not be enabled without explicit decision, use IAP or a risk-reviewed TEST token flow. R4_TEST_TOKEN must be kept in Secret Manager and never committed.
Cloud Run local per-process quota and rate checking do NOT provide hard account-wide budget caps. Apply Cloud Billing alerts and provider quotas if deployed.
Adaptive supports Korean and Lao and up to five vetted example pairs per direction. Do not use test cases themselves as reference examples.

Locked refs before final verification: couple TEST main 23f46ee6072cd09afe4a2f3de7cd7886e43f0095; SERVICE couple wife/main 8b26aedb04d0e395069b511d325244b3bdcebaa5; SERVICE general korean-lao-general/main f8cf8439f7349475a512803b41f55e8aaff90693.
Previous R3 engine-comparison-test-20261014.html remains unchanged. H2/Cloudflare/Cloud Run/History DB/Control DB remain untouched.

NEXT: obtain user-controlled Google Cloud project permissions to create new TEST runtime service account and deploy isolated private Cloud Run service; select an authenticated browser path, then verify with minimal live calls only when explicitly authorized. Do not advance SERVICE.
Google docs: https://docs.cloud.google.com/translate/docs/advanced/adaptive-translation
Google v3 REST: https://docs.cloud.google.com/translate/docs/reference/rest/v3/projects.locations/adaptiveMtTranslate
Cloud Run CORS/IAP: https://docs.cloud.google.com/run/docs/authenticating/end-users