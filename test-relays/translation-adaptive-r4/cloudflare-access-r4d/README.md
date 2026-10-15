# R4D Adaptive Translation — isolated Cloudflare Access TEST gateway

**STAGED CODE ONLY — NOT DEPLOYED OR USER-ACCEPTED.** Existing live Services, existing Workers, H2, both DBs, GitHub Pages main, and all SERVICE versions remain untouched.

## Why
The current private R4 Cloud Run passes actual KO→LO and LO→KO tests when invoked via Google Cloud Shell authenticated proxy. GitHub Pages cannot transparently authenticate to that private Cloud Run and embedding the R4_TEST_TOKEN in the browser would expose an access secret.

## Proposed TEST-only architecture (requires separate go/no-go)
- A **new** named Cloudflare Worker (`r4d-adaptive-access-test`) serves the R4D comparator HTML and P168A prompt-config from one origin.
- Enable **Cloudflare Access for the entire single Worker, including workers.dev and previews**, with user email allowlist. The Worker **also checks** `ctx.access`, the expected Access audience, and exact owner email before serving anything.
- R4D HTML keeps the 7 legacy engines; Adaptive uses a relative same-origin POST. There is **no** Cloud Run URL or shared token in browser input, browser source, or localStorage.
- Worker secret `R4_BACKEND_TOKEN` is the existing R4 TEST Secret Manager token, configured only via `wrangler secret put`, **never** committed.
- Worker forwards authenticated, validated requests to **dedicated R4 TEST Cloud Run only**. Because Workers cannot forward a Google Cloud Run IAM ID token from Access without additional federation, making this Worker useful requires **separate explicit user approval** to allow unauthenticated Cloud Run invocation on **r4-adaptive-test only**, while retaining the 64-char random in-app token and Cloudflare Access gate. This changes the TEST service's IAM risk posture; it is NOT done by this code. The Worker will return an upstream error while Cloud Run is private.
- A Cloudflare Durable Object serializes a hard count of at most `R4_MAX_DAILY_CALLS=6` POST attempts per UTC date **through this single Worker/binding**, even across Worker restarts. This is not a Google-wide bill cap and cannot cover direct attempts against the Cloud Run token endpoint. Backend additionally has a per-process 16 call limit (resets on revision restarts).
- No automatic retries; if the R4 server returns an error, the Worker masks it. Optional Adaptive remains off by default. No implicit provider calls at deploy or build time.
- CORS cross-origin workaround is intentionally avoided: serve HTML and API **from the same Access-protected Worker origin**, so iOS third-party cookie restrictions do not break access login.

## Code
- `index.html`: branch-isolated R4C comparator adapted for same-origin Access, no token field, user-reviewed pairs required in both directions.
- `worker.mjs`: Wrangler entrypoint, imports root prompt-config and HTML as Text.
- `gateway-core.mjs`: fail-closed Access/owner checks, payload validation, Durable Object budget, API proxy.
- `gateway-core.test.mjs`: offline mock tests, zero paid provider calls.
- `wrangler.jsonc`: *new* Worker settings, never target any pre-existing Worker.

## Before any deployment
1. Confirm Wrangler can bundle the `Text` HTML import and root JSON import. Run `node --test gateway-core.test.mjs` and `npx wrangler deploy --dry-run` **offline where possible**.
2. Confirm Cloudflare Zero Trust is active for the user's account; select **Worker-level Access**, not merely hostname-level, and restrict to a single owner email and audience.
3. Set secret bindings `R4_OWNER_EMAIL`, `R4_ACCESS_AUD`, `R4_BACKEND_TOKEN` via Wrangler secrets (with secrets entered privately; never print/copy their literal contents into chat). `R4_OWNER_EMAIL` may be stored as a non-secret variable as an alternative.
4. Set `R4_MAX_DAILY_CALLS` to small nonzero limit and verify DO binding, no Access bypass, no public preview.
5. **Explicit user approval required** before allowing unauthenticated Cloud Run Invoker **only for new `r4-adaptive-test`**, to let the Worker connect using its secret. Never apply to existing relay servers or workers.
6. Verify Access disabled state => 403; wrong user/audience => 403; malformed POST => 400; correct secret never appears in HTML or user-visible logs; first live request only after human approval.
7. If the user refuses opening even the TEST backend to internet, **do not deploy this topology**. Alternative: continue authenticated Cloud Shell diagnostics or design a separate Google IAP/federated private bridge.

Source grounding: https://developers.cloudflare.com/workers/configuration/cloudflare-access/ and https://developers.cloudflare.com/workers/runtime-apis/context/ (Static Assets router drops ctx.access; this implementation uses a JS text import, not Static Assets).
