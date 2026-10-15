# C4 / Google Advanced v3 — offline TEST only (2026-10-16)

Do not deploy or merge without user-approved TEST gate. This branch is forked from R4D owner-only TEST and changes no working runtime, Cloud Run, Cloudflare Worker, SERVICE, H2 or databases.

- `../candidates/gemini-c4-20261016.txt`: isolated 4-path Gemini candidate, compatible with R4D V1 prompt file loader. In the diagnostic UI select **Gemini P168A** and **Gemini TXT candidate** only; require `PROFILE R4D_GEMINI_C4` in the exported log. No private original sentences are committed.
- `request.mjs`: **pure offline** builder for Google NMT Advanced glossary and Translation LLM Advanced contextual glossary and a masked-backend-429 classifier. No provider call, OAuth flow or credential handling.
- `request.test.mjs`: 13 offline tests. Run `node --test request.test.mjs` locally.

Google Advanced v3 needs OAuth 2.0 credentials; the existing Basic v2 API key is insufficient. The advanced service requires a separate user-authorized owner-only TEST relay, proper IAM, precreated KO→LO and LO→KO glossaries and human-reviewed translations. Never add a service-account key, auth token, source texts or unreviewed private Lao translations to public GitHub. Choose `glossaryTranslations` from the API result; do not silently use an unmodified translation if missing.

Adaptive `BACKEND_RATE_LIMIT` was created by the R4D Worker as a mask for a Cloud Run TEST upstream HTTP 429. The R4 TEST server implementation contains `LOCAL_RATE_LIMIT` (default 1200 ms interval) and `LOCAL_DAILY_LIMIT` (default 24 calls/instance if unset). Earlier TXT logs did not expose a reason, so the precise trigger in the deployed version remains unconfirmed. Do not attempt paid calls or relax existing rate/cost limits for diagnosis.

Quality gate: four equal forward/back paths, each user request at most one forward and one independent back; identical baseline and candidate test set + new unseen reviewed cases. Report reliability, latency and actual provider charges separately. C4 quality remains unverified.

Authoritative documentation:
- https://docs.cloud.google.com/translate/docs/advanced/glossary
- https://docs.cloud.google.com/translate/docs/translate-text
- https://docs.cloud.google.com/translate/quotas
- https://developers.google.com/identity/protocols/oauth2/service-account
