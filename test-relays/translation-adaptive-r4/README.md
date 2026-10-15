# Isolated R4 Adaptive Translation TEST relay (NOT DEPLOYED)

Staging-only Node.js service for Google Cloud Translation Advanced v3 adaptiveMtTranslate.
It DOES NOT connect to production Cloud Run, Cloudflare, H2, DB or actual spouse app.
No service-account JSON keys, client API keys or test tokens belong in GitHub.

## Configuration before **separately approved** deployment

1. New TEST-only Cloud Run service and dedicated service account, not existing translation service.
2. Enable Cloud Translation API (billing may apply) and give only the TEST runtime identity roles/cloudtranslate.user.
3. Deploy with Cloud Run Application Default Credentials and a 32+ character secret supplied from Secret Manager as R4_TEST_TOKEN.
4. Set GOOGLE_CLOUD_PROJECT, ADAPTIVE_REGION=us-central1, R4_ALLOWED_ORIGIN=https://martin830000-spec.github.io, R4_DAILY_CALL_LIMIT=24, R4_MIN_INTERVAL_MS=1200.
5. Since GitHub Pages is a browser client, Cloud Run private IAM access causes CORS preflight issues. Prefer Identity-Aware Proxy when available. Any optional unauthenticated Cloud Run Invoker deployment must be separately approved and requires the additional in-app shared-token check. CORS is NOT authentication.
6. Default to low Cloud Run max instances=1 and concurrency=1. Local counters are NOT a hard global cost cap, particularly across restarts/revisions. Use Cloud Billing alerts and provider quotas.
7. Request endpoint is POST /api/adaptive-translate JSON {source:"ko",target:"lo",text:"...",pairs:[{source:"...",target:"..."}]}; returns {translation,source,target}. Browser never sees a Google OAuth token.
8. Secrets are never logged or returned; logs do not include translation text. Handler never automatically retries provider calls.

Test locally with npm ci (after a lockfile is generated) and npm test; no Google API calls by mock tests.

Do NOT allow actual paid calls before a human has reviewed/approved the reference sentence pairs in each direction.
