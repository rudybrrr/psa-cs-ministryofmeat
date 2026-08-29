# Phase 9 deployment and operator checklist

This is an operator-only runbook. It is not application configuration. Do not
put real URLs, keys, tokens, or other secrets in this file or in the frontend.
Task 9 is a separate manual checkpoint: stop and obtain separate, explicit
human authorization before creating resources, invoking a live CLI, making a
provider call, or spending the US$5 evaluation ceiling.

## Local release gates

Use Python 3.12 and the repository lockfile:

```bash
UV_CACHE_DIR=/private/tmp/psa-uv-cache uv run --python 3.12 --extra dev pytest backend/tests -q
UV_CACHE_DIR=/private/tmp/psa-uv-cache uv run --python 3.12 --extra dev pytest backend/tests/test_deployment_config.py -q
UV_CACHE_DIR=/private/tmp/psa-uv-cache uv lock --check
```

The deterministic suite is credential-free and network-free. Do not set
`OPENAI_API_KEY` for ordinary tests.

## Railway backend

- Deploy from the repository root using the root `Dockerfile`. It uses Python
  3.12 and starts `backend.app.main:app` on Railway's required `PORT`.
- Attach a persistent Railway volume at exactly `/data` before configuring the
  database. Set `DATABASE_URL=sqlite:////data/transshipment.db`.
- Set `ALLOWED_ORIGINS` to the exact HTTPS Vercel origin, comma-separated only
  when more than one exact origin is deliberately supported. Do not use `*`, a
  path, or a trailing-slash variant.
- Set `OPENAI_AGENT_MODEL=gpt-5.6-terra` and `OPENAI_MODEL=gpt-5.6-luna`.
- Store `OPENAI_API_KEY` as a Railway server-only secret. It is not required
  for startup or `GET /healthz`; never expose it through `VITE_` variables,
  logs, responses, artifacts, or the Docker image.

Configure the Railway health check as `GET /healthz`. Expect HTTP 200 with
`{"status":"ok","database":"ready"}`. A database failure must be non-2xx
and generic; health checks do not create demo data or call OpenAI.

## Vercel frontend

- Set the Vercel project root to `web/`.
- Build with `npm run build`.
- Set `VITE_API_BASE_URL` to the public HTTPS Railway API origin with no
  trailing slash (for example, `https://railway-public-domain.example`). This
  value is public and is intentionally embedded in the browser bundle.
- Do not put `OPENAI_API_KEY`, `DATABASE_URL`, Railway tokens, or any other
  server secret in a `VITE_` variable.

After building, run a secret-sentinel scan against `web/dist` using disposable
sentinel values (never real secrets). The build must contain the public API
base only and must not contain the server-key or database sentinels.

## Verification after human authorization

Only after the separate Task 9 authorization gate, set uncommitted operator
values for the Railway public URL and exact Vercel origin, then verify:

```bash
curl --fail --silent --show-error "$RAILWAY_URL/healthz"
curl --silent --include --request OPTIONS "$RAILWAY_URL/healthz" \
  --header "Origin: $VERCEL_ORIGIN" \
  --header 'Access-Control-Request-Method: GET'
curl --silent --include --request OPTIONS "$RAILWAY_URL/healthz" \
  --header 'Origin: https://unrelated.example' \
  --header 'Access-Control-Request-Method: GET'
```

Confirm the exact Vercel origin receives `access-control-allow-origin` and the
unrelated origin does not. Create one canonical demo, record its identifier,
restart/redeploy Railway without replacing `/data`, then read the same
identifier and durable audit/run state. Refresh the Vercel browser view and
confirm it reloads that state from the API. Local SQLite tests are not proof of
Railway persistence.

## Rollback and live evaluation

Rollback is configuration-first: restore the previous Vercel deployment and
Railway release while retaining the same `/data` volume. If necessary, remove
`OPENAI_API_KEY` to disable live provider actions safely. Never delete,
reinitialize, or replace the SQLite volume as a rollback step.

The bounded live evaluator is opt-in and must not run until separately
authorized. It requires `RUN_LIVE_LLM_TESTS=1`, a temporary
`OPENAI_API_KEY`, `PHASE9_LIVE_MAX_CALLS` no greater than 10, and
`PHASE9_LIVE_MAX_RUNS=1`; stop if the run would exceed the US$5 ceiling:

```bash
RUN_LIVE_LLM_TESTS=1 PHASE9_LIVE_MAX_CALLS=10 PHASE9_LIVE_MAX_RUNS=1 \
  UV_CACHE_DIR=/private/tmp/psa-uv-cache uv run --python 3.12 --extra dev \
  python -m backend.app.evaluation.live_provider \
  --output-json /tmp/phase9-live-provider.json \
  --output-markdown /tmp/phase9-live-provider.md
```

Do not commit live artifacts or claim deployment verification without the
human-authorized observation. Missing authorization means stop: create no
Railway/Vercel resources, set no real key, invoke no live CLI, and spend no
provider budget.
