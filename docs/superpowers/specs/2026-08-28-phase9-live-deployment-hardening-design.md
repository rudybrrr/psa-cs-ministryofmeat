# Phase 9: Live Model + Deployment Hardening Design

**Status:** Approved architecture translated into a repository-specific, implementation-ready design

**Date:** 2026-08-28

**Implementation base:** frozen Phase 8 main `2ff0e58d98e586f7904c726a4bb485a8419e2954`

**Scope:** Deploy the existing React/Vite console to Vercel and existing FastAPI application to Railway; make SQLite configuration and cross-origin access production-safe; and add a bounded, opt-in live OpenAI evidence path. This phase preserves all existing recovery, safety, authority, runtime, replay, and Phase 8 deterministic-evidence behavior.

## 1. Goals and non-goals

### Goals

- Run the existing FastAPI/OR-Tools/agent application on Railway with Python 3.12 and a Railway persistent volume-backed SQLite file.
- Run the existing React/Vite console on Vercel, using its existing `VITE_API_BASE_URL` client seam to call Railway directly in production.
- Make `DATABASE_URL` environment-driven while retaining the present local SQLite default.
- Add narrowly configured CORS and a non-mutating database-readiness health endpoint.
- Use `OPENAI_AGENT_MODEL=gpt-5.6-terra` for live agent tool orchestration and `OPENAI_MODEL=gpt-5.6-luna` for live semantic consistency checks, with both remaining environment overrides.
- Produce a separate, explicitly non-deterministic live-provider evidence artifact from bounded real calls without exposing reasoning traces or inventing values.

### Non-goals

Phase 9 does not add Postgres, Supabase, psycopg, Alembic, Redis, workers, Kubernetes, auth, observability SaaS, serverless backend hosting, or a backend rewrite. It does not change the scarce-capacity optimizer, dynamic-yard/reconsideration logic, carrier-recovery semantics, approval validation, DG policy, AgentRun state machine/tool authority, canonical replay, or Phase 8 deterministic evidence/fingerprint. It also adds no Phase 10 UI/product polish and no submission/deck/video assets.

## 2. Current-state evidence and consistency decisions

| Current repository evidence | Phase 9 design consequence |
|---|---|
| `backend/app/storage/database.py` sets `DATABASE_URL = "sqlite:///./backend/transshipment.db"` and always supplies SQLite `check_same_thread`. | Centralize environment-driven engine creation there; apply that argument only when the URL is SQLite. |
| `backend/app/main.py` has an application lifespan that calls `create_db_and_tables(active_engine)`. | Railway cold start and `/healthz` may use existing schema creation/readiness behavior, but health must not create demo state. |
| `web/src/api/client.ts` already prefixes requests with `import.meta.env.VITE_API_BASE_URL ?? ""`; `web/vite.config.ts` owns localhost proxy rules. | No frontend API-client redesign is needed. Vercel supplies the build-time base URL; proxy remains localhost development only. |
| `OpenAIAgentModel` uses Responses function tools and persists the configured model on AgentRun/steps; `OpenAISemanticSafetyChecker` uses structured Responses output and stores model, latency, input tokens, and output tokens. | Reuse these boundaries. Phase 9 adds observable telemetry capture, not prompt authority or a second model client. |
| Agent provider failure becomes deterministic `MODEL_UNAVAILABLE`; semantic missing-key/provider/invalid-output failure becomes `CHECK_FAILED` and blocks automation. | Tests may harden configuration and verify outcomes, but must not change the failure policy. |
| `backend/app/evaluation/evidence.py` removes `OPENAI_API_KEY` and patches both provider constructors; Phase 8 has fingerprinted deterministic JSON/Markdown artifacts. | Live evaluation is a new module/CLI and artifact namespace. No Phase 8 module, command, test, status, or fingerprint changes are permitted. |

The base checkout also contains optional opt-in live smoke tests, guarded by `RUN_LIVE_LLM_TESTS=1`. They are insufficient as Phase 9 evidence because they have no bounded-run ledger, staged workflow, artifact, provenance envelope, or cost rule. The Phase 9 evaluator supersedes them as the documented live verification entry point; ordinary test runs remain credential-free and network-free.

## 3. Production architecture

```text
Browser
  -> Vercel: existing React/Vite operations console
       VITE_API_BASE_URL = https://<railway-public-domain>
  -> Railway: existing FastAPI application + OR-Tools + agent runtime
       DATABASE_URL = sqlite:////data/transshipment.db
       Railway persistent volume mounted at /data
       OPENAI_API_KEY (server-only)
       -> OpenAI Responses API
```

The FastAPI process remains a stateful Railway service. SQLite remains the production hackathon database; no application behavior becomes conditional on a provider other than its connection URL. Railway persistent storage, not an image-layer or relative working-directory file, owns durable production data.

## 4. Configuration and environment contract

`backend/app/storage/database.py` remains the single database configuration boundary. Its exact contract is:

| Variable | Required | Value / default | Consumer | Handling |
|---|---:|---|---|---|
| `DATABASE_URL` | no | `sqlite:///./backend/transshipment.db` | backend | SQLAlchemy/SQLModel URL. Railway sets `sqlite:////data/transshipment.db`. |
| `ALLOWED_ORIGINS` | no locally; yes in deployed production | comma-separated exact origins | backend | Empty means the explicit local development origin set only; production configuration must include the exact Vercel origin. |
| `OPENAI_API_KEY` | no for startup; yes for live provider operation | Railway secret | backend only | Missing key must preserve fail-safe runtime behavior. Never use a `VITE_` name. |
| `OPENAI_AGENT_MODEL` | no | `gpt-5.6-terra` in Railway | backend | Environment override; local adapter default remains its current `gpt-5.6-luna` until implementation deliberately changes that default with tests. |
| `OPENAI_MODEL` | no | `gpt-5.6-luna` | backend | Semantic-checker environment override/default. |
| `PHASE9_LIVE_MAX_CALLS` | yes for live evaluator | positive integer, invocation supplies a value no greater than 10 | live evaluator | Hard process-wide call cap for one evidence invocation. |
| `PHASE9_LIVE_MAX_RUNS` | yes for live evaluator | `1` | live evaluator | Hard cap for complete workflow attempts. |
| `PHASE9_LIVE_PRICING_SNAPSHOT` | no | unset | live evaluator | Explicit path to a committed, documented pricing snapshot; absence makes cost `NOT_ESTABLISHED`. |

The implementation must validate values at startup/configuration use: malformed URLs, blank origins, duplicate origins, non-HTTPS deployed origins, non-positive limits, or a limit above either documented ceiling fail before a provider call. The evaluator has hard coded upper bounds of 10 calls and 1 complete workflow in addition to environment values, so setting a large environment value cannot expand spend. It makes no automatic retries beyond the existing agent-runtime bounded retry behavior and never schedules background, recurring, or automatic provider work.

For provider neutrality, engine construction derives `connect_args={"check_same_thread": False}` only when `make_url(DATABASE_URL).get_backend_name() == "sqlite"`; non-SQLite URLs receive no SQLite-specific connect arguments. No non-SQLite driver is introduced or tested as a running deployment in this phase.

## 5. Railway backend contract

- Railway installs and runs the existing project with `uv` under Python 3.12 (`>=3.12,<3.13`); macOS system Python 3.13 is not used for repository commands.
- The service starts `backend.app.main:app` with a production ASGI command and listens on Railway’s supplied port.
- Railway attaches a persistent volume at exactly `/data`; `DATABASE_URL=sqlite:////data/transshipment.db` is configured only after that mount exists.
- Application lifespan calls the existing `create_db_and_tables` against the configured engine. This initialization is idempotent and does not seed a canonical incident.
- Railway health checking targets `GET /healthz`. A successful response is `200` JSON `{"status":"ok","database":"ready"}` only after a basic database accessibility probe succeeds. It performs no mutation, accepts no input, returns no configuration or secret, and does not invoke OpenAI. A database failure returns a non-2xx response with generic `{"status":"unavailable","database":"unavailable"}`.
- Required Railway variables are `DATABASE_URL`, `ALLOWED_ORIGINS`, `OPENAI_AGENT_MODEL`, and `OPENAI_MODEL`. `OPENAI_API_KEY` is a Railway secret, optional for process health but required only for live-provider work.

The Phase 9 deployment documentation must state the actual Railway public URL and exact Vercel origin only as operator configuration values, never hard-coded application values or committed secrets.

## 6. Vercel frontend contract

- Vercel builds the existing `web` Vite app without backend code or server secrets.
- Its production build environment sets `VITE_API_BASE_URL` to the exact HTTPS Railway public origin, with no trailing slash. The existing client concatenation continues to form paths such as `https://<railway-public-domain>/incidents/<id>`.
- `VITE_API_BASE_URL` is intentionally public because Vite embeds it in the browser bundle. No `OPENAI_API_KEY`, `DATABASE_URL`, Railway token, or non-public server configuration may use a `VITE_` prefix or appear in frontend source/build output.
- The `web/vite.config.ts` proxy remains only the local `npm run dev` convenience path to `http://127.0.0.1:8000`; Vercel does not proxy API traffic.
- A production build check must scan emitted `web/dist` text for the configured secret value and fail if present. The check uses a disposable test sentinel, not a real secret.

## 7. CORS contract

FastAPI adds `CORSMiddleware` from a parsed allowlist. The only allowed methods and headers are those the existing JSON API needs: `GET`, `POST`, `OPTIONS`, `Accept`, and `Content-Type`. `allow_credentials` is `false`; no cookie/session authentication is in scope. Wildcard origins, methods, or headers are prohibited.

The default local-development origins are `http://127.0.0.1:5173` and `http://localhost:5173`. `ALLOWED_ORIGINS`, when set, replaces those defaults and is the production source of truth; it contains the exact Vercel deployment origin (and an explicitly selected stable production Vercel domain if distinct). Tests prove an allowed origin receives the CORS response header and an unrelated origin does not. The API itself retains its existing unauthenticated hackathon boundary; CORS is not authorization.

## 8. SQLite persistence contract

The local default remains `sqlite:///./backend/transshipment.db`. Railway uses the absolute `/data/transshipment.db` database file, created by application startup when absent. A deployment verification creates a canonical demo incident, records its incident UUID and a durable `AgentRun` or audit record, restarts/redeploys the Railway service without replacing/detaching the volume, then reads that same UUID and durable record successfully. Browser refresh must similarly reload this persisted state through existing read APIs, not browser-only state.

This phase does not add migrations. `SQLModel.metadata.create_all()` may create absent tables on a clean mounted volume; an incompatible future schema change is outside this phase and requires an explicit migration decision.

## 9. OpenAI runtime and safety contract

The agent uses the existing `OpenAIAgentModel` Responses function-tool path. Railway configures `OPENAI_AGENT_MODEL=gpt-5.6-terra`; `OPENAI_AGENT_MODEL` remains an override. The semantic checker uses the existing structured Responses path with `OPENAI_MODEL=gpt-5.6-luna`; `OPENAI_MODEL` remains an override. `OPENAI_API_KEY` is read only by backend adapters and never returned in API responses, artifacts, logs, exceptions, or frontend output.

Live output is evaluated only for permitted observable orchestration. It cannot change deterministic authority: unavailable tools remain unavailable; RTA send still requires operator approval; allocation stays within capacity; dynamic-yard evidence precedes incompatible carrier mutation; tradeoffs remain human-selected; semantic contradiction or checker failure remains fail-closed; audit remains durable; the model cannot classify DG, infer/correct UN numbers, override solver/policy, or create authority. Prompts remain advisory input to the existing adapters, never the owner of these rules.

Provider timeout/error must continue to reach `AgentModelProviderFailure`, use the existing bounded runtime handling, and end in `MODEL_UNAVAILABLE` rather than an invented action. Missing key, timeout, provider error, malformed structured output, or invalid semantic result must continue to produce deterministic `CHECK_FAILED`/escalation with no pass-through.

## 10. Separate live-provider evaluation

### Module ownership

The implementation adds only these Phase 9-owned boundaries:

| File | Responsibility |
|---|---|
| `backend/app/storage/database.py` | Parse `DATABASE_URL`, construct the engine with provider-neutral SQLite-only arguments, and expose the existing session/table APIs. |
| `backend/app/main.py` | Parse CORS configuration, install exact CORS middleware, and expose `GET /healthz` using the active injected/default engine. |
| `backend/app/domain/live_evidence.py` | Frozen report, stage, call observation, token/latency, cap, pricing-snapshot, and redacted failure contracts. |
| `backend/app/evaluation/live_provider.py` | Explicit opt-in bounded staged runner, adapter telemetry collection, artifact validation/writing, and module CLI. |
| `backend/tests/test_deployment_config.py` | Database configuration, CORS, health/readiness, and missing-provider safety tests. |
| `backend/tests/test_live_provider_evaluation.py` | Fake-client deterministic coverage of live-evaluator caps, schema, telemetry, pricing, and redaction. |
| `docs/deployment.md` | Railway/Vercel environment setup, volume, health-check, verification, rollback, and live-evaluation invocation instructions. |

Existing `backend/app/evaluation/evidence.py`, `backend/app/domain/evidence.py`, their tests, and `docs/evaluations/phase8-*` are read-only to Phase 9. Adapter changes are limited to exposing already-returned provider usage/model metadata to the Phase 9 collector through typed return metadata; they must not alter AgentModel or semantic safety decision semantics.

### Entry point and stages

Add a new opt-in module CLI, `python -m backend.app.evaluation.live_provider`, that requires `RUN_LIVE_LLM_TESTS=1`, `OPENAI_API_KEY`, `PHASE9_LIVE_MAX_CALLS`, and `PHASE9_LIVE_MAX_RUNS`. It writes a new JSON artifact and Markdown projection beneath `docs/evaluations/live/`; neither file name overlaps a Phase 8 artifact. Every artifact begins with the literal label `NON-DETERMINISTIC LIVE PROVIDER EVIDENCE` and has `suite_id = "phase9-live-provider-evidence"`.

The CLI performs exactly this progression, stopping immediately on a failed stage or exhausted configured cap:

1. configuration/connectivity smoke: one minimal agent or semantic request, recording whether a provider response was received;
2. one semantic-safety smoke using the canonical DG contradiction fixture and observing the persisted fail-closed outcome;
3. one agent tool-selection smoke with exactly one exposed tool, observing the selected tool;
4. one complete canonical live-agent workflow through existing public orchestration and durable AgentRun history;
5. at most one repeated single-call tool-selection or semantic-check smoke, only when the call cap permits it, to observe a small latency/token sample;
6. deployed Vercel-to-Railway verification repeats no full workflow automatically. It creates/progresses the canonical replay demo through Vercel and Railway, verifies persisted reads/refresh, and performs at most one explicit live semantic or agent smoke through that deployed route if budget remains.

The evaluator never executes more than one complete workflow, ten total provider calls, or any stage after a failure. It records `STOPPED_AT_CALL_CAP`, `STOPPED_AT_RUN_CAP`, or the concrete failed stage rather than silently continuing. A live invocation without the explicit opt-in flag exits before constructing an OpenAI client. This ensures normal test, CI, and Phase 8 paths remain network-free.

### Observations and provenance

The machine-readable report contains only observed facts:

- report schema/suite/label, UTC timestamp, source revision, evaluation base SHA, fixture/configuration identities, environment class (`local` or `deployed`), and configured caps;
- per call: stage, provider/model identity reported by the configured adapter, success/failure category, wall-clock request latency in milliseconds, input/output/total token counts when returned by the SDK response, and selected function-tool name when applicable;
- durable identifiers for the AgentRun, AgentStep, safety review/assessment, and final outcome when created;
- aggregate attempted/successful/failed call counts, complete workflow count, and p50/p95 over the observed successful request latencies only;
- optional cost-estimation section following the rules below.

It excludes prompt bodies, cargo-note text, response prose, hidden reasoning, reasoning summaries, tool arguments, API keys, headers, provider request IDs, and arbitrary exception bodies. Failures use a small stable category such as `CONFIGURATION_ERROR`, `PROVIDER_TIMEOUT`, `PROVIDER_ERROR`, `INVALID_OUTPUT`, `MODEL_UNAVAILABLE`, or `UNEXPECTED_FAILURE` plus stage; they do not serialize raw errors.

Token accounting takes input/output values only from the Responses SDK’s returned usage object. The evaluator records absent values as `null`, not `0`, and computes `total_tokens` only when the provider supplied it or when both input and output values are observed and the derivation is labelled `input_plus_output`. No token estimate is inferred from strings, prompt length, or local tokenizer output.

Latency is measured by `time.perf_counter()` around each adapter call and stored as integer milliseconds, labelled client-observed request latency. It includes client-side SDK overhead and is not asserted to be provider-only latency, an SLA, or a stable performance benchmark. Percentiles use nearest-rank over the successful observed values and are omitted when no successful calls exist.

### Cost-estimation rules

Cost is `NOT_ESTABLISHED` unless the invocation receives `PHASE9_LIVE_PRICING_SNAPSHOT` pointing to a committed JSON snapshot that validates before the first provider call. A valid snapshot contains provider, model, currency `USD`, separate input/output price units and prices, official source URL, source publication/access date, snapshot commit SHA, and an explicit statement that it is an estimate. The evaluator refuses a snapshot whose model does not exactly equal an observed model, whose currency/unit is unknown, or whose provenance is incomplete.

When valid pricing and both required observed token dimensions exist, estimated cost is calculated from those recorded values and the snapshot units, rendered as `ESTIMATED_USD`, and identifies the snapshot. It is never presented as billed cost. If either token dimension or valid pricing is absent, the report writes `NOT_ESTABLISHED` with the reason. Phase 9 commits no made-up price table and makes no provider-pricing claim without a pinned official snapshot.

## 11. Testing strategy

New deterministic tests cover database URL parsing and SQLite-only connect arguments; local/default and configured CORS headers; `/healthz` successful readiness, database failure, non-mutation, and no demo initialization; and configured model identity/failure-safe missing-key behavior. New live-evaluator tests inject fake adapter responses and clocks to prove schema validation, literal labeling, cap enforcement, stop-on-failure, null token behavior, token derivation, latency percentile behavior, price-snapshot validation, and secret/redaction rules without a network call.

Existing full backend tests, frontend unit tests, `npm run typecheck`, `npm run build`, `npm run lint`, `uv lock --check`, and `git diff --check` remain release gates. Phase 8 tests and its regeneration command run with `OPENAI_API_KEY` absent and provider constructors blocked; their report and fingerprint must remain byte/semantic-compatible under their existing volatile-field rules. The separately opt-in live CLI is never part of default pytest, frontend test, build, or deployment health checks.

## 12. Deployment verification and rollback

Verification proceeds in order: Railway cold start and `/healthz`; mounted-volume schema initialization; persistence across restart/redeploy; direct CORS allow/reject probes; Vercel production build with public API base; frontend secret-sentinel scan; bounded live stages; then one Vercel-to-Railway canonical demo creation/progression, refresh, and durable-state read. Missing OpenAI configuration is verified as safe `MODEL_UNAVAILABLE`/`CHECK_FAILED`, not a deployment outage.

Rollback is configuration-first: restore the prior Vercel deployment and Railway release while retaining the same `/data` volume, or set `OPENAI_API_KEY` absent to disable live provider actions safely. Do not delete, reinitialize, or replace the SQLite volume as rollback. A health/readiness failure prevents Railway rollout completion; a live-evidence failure stops that evaluation and records the failed stage without changing deterministic Phase 8 evidence.

## 13. Exact acceptance criteria

Phase 9 is complete only when all of the following are demonstrably true:

1. The Phase 9 branch preserves Python `>=3.12,<3.13` and Railway runs the existing FastAPI service with Python 3.12.
2. With `DATABASE_URL` unset, the engine uses `sqlite:///./backend/transshipment.db`; with Railway configuration it uses `sqlite:////data/transshipment.db`.
3. SQLite receives `check_same_thread=False`; a non-SQLite URL reaches engine construction without SQLite-only connect arguments, with no new database dependency installed.
4. Railway cold start creates/checks tables on `/data` and `GET /healthz` returns only the documented non-secret readiness response without creating a canonical incident or calling OpenAI.
5. A durable incident/run/audit record survives a Railway restart or redeploy that retains the mounted `/data` volume, and refresh retrieves it through API reads.
6. `ALLOWED_ORIGINS` accepts the configured exact Vercel origin and rejects an unrelated origin; no credentialed wildcard CORS policy exists.
7. Vercel’s built console calls the Railway URL through `VITE_API_BASE_URL`; Vite’s localhost proxy remains development-only.
8. The built frontend contains no supplied server-secret sentinel and no backend secret is configured with a `VITE_` name.
9. Railway config selects `gpt-5.6-terra` for the agent and `gpt-5.6-luna` for semantic checking, while both remain environment-configurable and `OPENAI_API_KEY` remains server-only.
10. Missing key, provider timeout/error, and invalid semantic output retain the existing `MODEL_UNAVAILABLE` and fail-closed `CHECK_FAILED`/escalation outcomes.
11. The opt-in Phase 9 CLI produces a schema-valid JSON artifact and Markdown projection labelled `NON-DETERMINISTIC LIVE PROVIDER EVIDENCE`, separate from all Phase 8 artifact paths.
12. Live stages execute in order, record only allowed observable facts, stop on the first failure, and cannot exceed one complete workflow or ten provider calls even when environment limits are larger.
13. Token counts are SDK-observed or null; latency is client-observed and labelled; absent values are never invented or represented as zero.
14. Cost is either an explicitly sourced, pinned-snapshot `ESTIMATED_USD` calculation from observed tokens or `NOT_ESTABLISHED`; no unsourced price or billed-cost claim appears.
15. The Phase 8 command remains credential-free/network-free, retains its deterministic fingerprint semantics, and still labels live token/cost/latency claims as deferred.
16. The deployed end-to-end console can create and progress the canonical demo through Vercel to Railway, SQLite, and—only for the explicit live step—OpenAI, while deterministic authority, capacity, dynamic-yard, human-tradeoff, DG, and audit invariants remain enforced by existing code.
17. No Phase 10 UI/product work, database migration, serverless rewrite, or unrelated refactor is included.

## 14. Phase 10 handoff boundary

Phase 9 hands off a deployed, persistent, bounded-live-verified operations console plus non-deterministic provider evidence. It deliberately does not alter presentation hierarchy, interaction polish, visual design, copy, screenshots, decks, videos, or submission storytelling; those remain Phase 10/11 work and require their own approved scope.
