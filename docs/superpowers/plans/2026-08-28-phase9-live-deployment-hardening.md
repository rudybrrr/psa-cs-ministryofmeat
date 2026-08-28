# Phase 9 Live Model + Deployment Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing operations console deployable on Vercel/Railway with persistent SQLite, restricted browser access, safe health checks, and a separately bounded live-provider evidence path.

**Architecture:** Keep the FastAPI/SQLModel/OR-Tools runtime intact on Railway and the existing Vite client intact on Vercel. Add narrowly scoped configuration/health boundaries, a root backend Docker image, and Phase 9-only evaluation contracts plus an injected OpenAI client proxy so telemetry and spend limits do not modify decision contracts or Phase 8.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLModel/SQLAlchemy, Pydantic 2, OpenAI Python SDK Responses API, pytest/httpx, React/Vite, Docker, Railway, Vercel.

**Spec:** `docs/superpowers/specs/2026-08-28-phase9-live-deployment-hardening-design.md`

## Global Constraints

- Python remains >=3.12,<3.13.
- Mac system Python 3.13 must not be used for project execution; use uv-managed Python 3.12.
- Backend deployment target: Railway.
- Frontend deployment target: Vercel.
- Production hackathon database remains SQLite.
- Railway persistent volume mount path is /data.
- Railway DATABASE_URL is sqlite:////data/transshipment.db.
- Local default DATABASE_URL remains sqlite:///./backend/transshipment.db.
- No Supabase/Postgres/psycopg/Alembic in Phase 9.
- No Redis/workers/Kubernetes/auth/observability SaaS.
- Root Dockerfile is canonical Railway backend deployment artifact.
- Root .dockerignore accompanies it.
- Backend Docker image uses Python 3.12.
- Production dependencies come from frozen uv.lock.
- No frontend build occurs inside backend Docker image.
- Railway PORT must be shell-expanded at runtime.
- No secret may be present at Docker build time.
- Vercel web build uses VITE_API_BASE_URL.
- OPENAI_API_KEY is backend/server-only.
- Railway runtime models: OPENAI_AGENT_MODEL=gpt-5.6-terra and OPENAI_MODEL=gpt-5.6-luna.
- Model names remain environment configurable.
- Phase 8 deterministic evidence remains credential-free, provider-network-free, and semantically/fingerprint compatible.
- Phase 9 live evidence is separate and explicitly labelled: NON-DETERMINISTIC LIVE PROVIDER EVIDENCE.
- Live evaluation requires explicit RUN_LIVE_LLM_TESTS=1.
- Maximum one complete live workflow per evaluator invocation.
- Maximum ten actual OpenAI provider requests per evaluator invocation.
- Provider-call budget is enforced immediately before responses.create / responses.parse.
- SDK automatic retries are disabled inside the instrumented client.
- Existing AgentRuntime retries count as separate actual provider calls.
- Eleventh provider request must be impossible.
- No chain-of-thought/reasoning traces are captured or persisted.
- No prompts, response prose, tool arguments, cargo-note text, credentials, headers, request IDs, or raw provider errors in live artifacts.
- Token counts come only from SDK usage or remain null.
- Latency is client-observed perf_counter latency.
- Cost is ESTIMATED_USD only with a valid pinned official pricing snapshot; otherwise NOT_ESTABLISHED.
- Approved live evaluation spend ceiling: US$5.
- No Phase 10 UI/product polish.
- No changes to solver, dynamic-yard allocation, carrier authority, approvals, DG deterministic policy, AgentRun authority/state machine, canonical replay semantics, or Phase 8 evidence meaning.

## Locked implementation file map

| Path | Change | Responsibility |
|---|---|---|
| `backend/app/storage/database.py` | Modify | `DATABASE_URL` parsing and provider-neutral engine construction. |
| `backend/app/main.py` | Modify | exact CORS installation and database readiness endpoint. |
| `backend/app/domain/live_evidence.py` | Create | immutable Phase 9 report/config/observation/pricing contracts. |
| `backend/app/evaluation/live_openai_client.py` | Create | invocation-scoped shared budget and safe Responses proxy. |
| `backend/app/evaluation/live_provider.py` | Create | opt-in staged evaluator, artifact writer, Markdown renderer, and CLI. |
| `backend/tests/test_deployment_config.py` | Create | database/CORS/health/Docker contract tests. |
| `backend/tests/test_live_openai_client.py` | Create | no-network proxy and hard-cap tests. |
| `backend/tests/test_live_provider_evaluation.py` | Create | no-network evaluator, artifact, and pricing tests. |
| `Dockerfile` | Create | Railway backend-only Python 3.12 image. |
| `.dockerignore` | Create | backend image context boundary. |
| `docs/deployment.md` | Create | exact operator setup, verification, rollback, and authorization gate. |
| `web/src/api/client.ts` | Read only unless secret-sentinel build test proves an existing client defect | Existing `VITE_API_BASE_URL` seam; do not redesign it. |
| `backend/app/services/agent_model.py` and `backend/app/services/semantic_safety.py` | Read only by default | Existing `client=` injection seams; do not change `AgentModelTurn`, `SemanticSafetyCheckOutput`, `AgentModel`, or decision semantics. |
| `backend/app/evaluation/evidence.py`, `backend/app/domain/evidence.py`, `backend/tests/test_phase8_evidence_acceptance.py`, `docs/evaluations/phase8-evidence-report.json`, `docs/evaluations/phase8-evidence-summary.md` | Read only | Frozen Phase 8 deterministic evidence boundary. |

---

### Task 1: Environment-driven database engine configuration

**Files:**
- Modify: `backend/app/storage/database.py`
- Create: `backend/tests/test_deployment_config.py`

**Interfaces:**
- Produces `DATABASE_URL_DEFAULT: str = "sqlite:///./backend/transshipment.db"`, `database_url() -> str`, and `build_engine(url: str) -> Engine`.
- `engine` remains `build_engine(database_url())`; `create_db_and_tables()` and `get_session()` retain their existing signatures.
- Consumed by Task 2 health checks and existing application/test imports.

- [ ] **Step 1: Write failing configuration tests.**

```python
from types import SimpleNamespace

def test_database_url_defaults_to_existing_local_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url() == "sqlite:///./backend/transshipment.db"

def test_sqlite_only_connect_args(monkeypatch):
    import backend.app.storage.database as database
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_create_engine(url: str, **kwargs: object) -> object:
        calls.append((url, kwargs))
        return SimpleNamespace(url=SimpleNamespace(database="db"))

    monkeypatch.setattr(database, "create_engine", fake_create_engine)
    database.build_engine("sqlite:////data/transshipment.db")
    database.build_engine("postgresql://host/db")
    assert calls == [
        ("sqlite:////data/transshipment.db", {"connect_args": {"check_same_thread": False}}),
        ("postgresql://host/db", {}),
    ]
```

- [ ] **Step 2: Run the focused tests before implementation.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_deployment_config.py -k database -q`

Expected: FAIL because `database_url` and `build_engine` do not exist and the module still hard-codes `DATABASE_URL`.

- [ ] **Step 3: Implement the smallest engine factory.**

Use `os.getenv("DATABASE_URL", DATABASE_URL_DEFAULT)` and `sqlalchemy.engine.make_url(url).get_backend_name()`. Call `create_engine(url, connect_args={"check_same_thread": False})` only for backend name `sqlite`; otherwise call `create_engine(url)` with no SQLite arguments. Do not import a Postgres driver or change repository/domain APIs.

- [ ] **Step 4: Run focused and existing storage/API tests.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_deployment_config.py -k database backend/tests/test_api.py -q`

Expected: PASS; the local default and absolute Railway SQLite URL work, and the captured non-SQLite call has no `connect_args`.

- [ ] **Step 5: Commit the independently reviewable change.**

```bash
git add backend/app/storage/database.py backend/tests/test_deployment_config.py
git commit -m "feat: configure database URL by environment"
```

### Task 2: Exact CORS and health/readiness boundary

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_deployment_config.py`

**Interfaces:**
- Produces `parse_allowed_origins(value: str | None) -> Sequence[str]`, returning local defaults only when unset and rejecting blank, duplicate, wildcard, and non-local HTTP/invalid deployed origins with `ValueError`.
- Produces `GET /healthz`: `200 {"status":"ok","database":"ready"}` after `SELECT 1`; non-2xx `{"status":"unavailable","database":"unavailable"}` on database failure.
- Consumes Task 1 `build_engine`/configured default engine and existing `create_app(database_engine=api_engine)` injection seam.

- [ ] **Step 1: Write failing CORS and readiness tests.**

```python
def test_configured_origin_is_allowed_and_other_origin_is_not(monkeypatch, api_engine):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://console.example.vercel.app")
    app = create_app(database_engine=api_engine)
    assert TestClient(app).options("/healthz", headers={"Origin": "https://console.example.vercel.app", "Access-Control-Request-Method": "GET"}).headers["access-control-allow-origin"] == "https://console.example.vercel.app"

def test_healthz_checks_database_without_creating_incident(api_engine):
    with TestClient(create_app(database_engine=api_engine)) as client:
        assert client.get("/healthz").json() == {"status": "ok", "database": "ready"}
    assert Session(api_engine).exec(select(Incident)).all() == []
```

- [ ] **Step 2: Run the focused tests before implementation.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_deployment_config.py -k 'cors or health' -q`

Expected: FAIL because no parser, middleware, or `/healthz` route exists.

- [ ] **Step 3: Implement exact policy.**

Install `CORSMiddleware` with parsed origins, `allow_methods=["GET", "POST", "OPTIONS"]`, `allow_headers=["Accept", "Content-Type"]`, and `allow_credentials=False`. Implement `/healthz` with a direct `Session(active_engine).exec(text("SELECT 1"))`; catch database exceptions and return the generic non-secret unavailable JSON without OpenAI construction or scenario calls.

- [ ] **Step 4: Run the complete boundary suite.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_deployment_config.py backend/tests/test_agent_runtime_api.py backend/tests/test_cargo_safety_api.py -q`

Expected: PASS; localhost defaults remain usable, configured production origin is exact, unrelated origin lacks allow header, and failure response has no exception text.

- [ ] **Step 5: Commit the independently reviewable change.**

```bash
git add backend/app/main.py backend/tests/test_deployment_config.py
git commit -m "feat: add deployment health and cors boundary"
```

### Task 3: Reproducible Railway backend image

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Modify: `backend/tests/test_deployment_config.py`

**Interfaces:**
- Produces a root image whose command is `sh -c 'uv run --no-sync uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:?PORT is required}"'`.
- Produces an image context including `backend/`, `shared/`, `pyproject.toml`, and `uv.lock`, and excluding secrets, databases, `.git`, `web/`, Node assets, and generated evidence.
- Consumed by Railway and Task 8 Docker smoke; no runtime application interface changes.

- [ ] **Step 1: Write failing Docker contract inspections.**

```python
def test_dockerfile_is_python312_backend_only():
    text = Path("Dockerfile").read_text()
    assert "FROM python:3.12-slim" in text
    assert "RUN uv sync --frozen --no-dev --no-install-project" in text
    assert text.index("RUN uv sync --frozen --no-dev --no-install-project") < text.index("COPY backend ./backend")
    assert "backend.app.main:app" in text and "${PORT:?PORT is required}" in text
    assert "OPENAI_API_KEY" not in text and "VITE_API_BASE_URL" not in text

def test_dockerignore_keeps_runtime_sources_and_excludes_secrets():
    ignored = Path(".dockerignore").read_text().splitlines()
    assert ".env" in ignored and ".git" in ignored and "web" in ignored
    assert "backend" not in ignored and "shared" not in ignored
```

- [ ] **Step 2: Run the focused tests before implementation.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_deployment_config.py -k docker -q`

Expected: FAIL because neither root deployment artifact exists.

- [ ] **Step 3: Create the exact artifacts.**

Create exactly this root `Dockerfile` using the repository’s installed uv version `0.11.31` and Python `3.12-slim`:

```dockerfile
FROM ghcr.io/astral-sh/uv:0.11.31 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend ./backend
COPY shared ./shared
CMD ["sh", "-c", "uv run --no-sync uvicorn backend.app.main:app --host 0.0.0.0 --port \"${PORT:?PORT is required}\""]
```

Create exactly this root `.dockerignore`:

```text
.env
.git
.pytest_cache
.venv
__pycache__
*.pyc
*.db
*.sqlite
docs
web
node_modules
package-lock.json
```

The image includes only `backend/`, `shared/`, `pyproject.toml`, and `uv.lock`; it does not copy `.env`, database files, `web/`, Node assets, docs, or evaluation output. Use the shell `CMD` above so `PORT` expands at container runtime, never Docker build time.

- [ ] **Step 4: Run static and available local-container checks.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_deployment_config.py -k docker -q && docker build -t psa-phase9-local .`

Expected: static tests PASS; if Docker is available, build PASS with no secrets supplied. If Docker is unavailable, record the exact unavailable command/output in the implementation handoff and leave runtime container verification for Task 9.

- [ ] **Step 5: Commit the independently reviewable change.**

```bash
git add Dockerfile .dockerignore backend/tests/test_deployment_config.py
git commit -m "build: add railway backend image"
```

### Task 4: Live evidence contracts

**Files:**
- Create: `backend/app/domain/live_evidence.py`
- Modify: `backend/tests/test_live_provider_evaluation.py`

**Interfaces:**
- Produces frozen Pydantic contracts: `LiveStage`, `LiveFailureKind`, `CostStatus`, `CostEstimate`, `ProviderCallObservation`, `PricingSnapshot`, `LiveProviderReport`, and `LiveProviderRunConfig`.
- `LiveProviderRunConfig(run_live_llm_tests: Literal[True], max_calls: int, max_workflows: int, pricing_snapshot_path: Path | None)` and `LiveProviderRunConfig.from_environ(environ: Mapping[str, str]) -> LiveProviderRunConfig` require opt-in, positive limits, cap `max_calls` at 10 and `max_workflows` at 1, and contain no API key field.
- `ProviderCallObservation(call_number: int, stage: LiveStage, method: Literal["responses.create", "responses.parse"], configured_model: str, returned_model: str | None, success: bool, failure_kind: LiveFailureKind | None, latency_ms: int | None, input_tokens: int | None, output_tokens: int | None, total_tokens: int | None, selected_tool: str | None)` is the only per-request data shape.
- `LiveProviderReport` requires literal label `NON-DETERMINISTIC LIVE PROVIDER EVIDENCE`, suite ID `phase9-live-provider-evidence`, safe provenance, and no free-form request/response/error fields.

- [ ] **Step 1: Write failing contract tests.**

```python
from datetime import UTC, datetime
from pathlib import Path

def valid_observation() -> ProviderCallObservation:
    return ProviderCallObservation(
        call_number=1, stage=LiveStage.CONNECTIVITY_SMOKE,
        method="responses.parse", configured_model="gpt-test", returned_model="gpt-test",
        success=True, failure_kind=None, latency_ms=12,
        input_tokens=3, output_tokens=5, total_tokens=8, selected_tool=None,
    )

def test_live_config_rejects_missing_opt_in_and_limits():
    with pytest.raises(ValueError, match="RUN_LIVE_LLM_TESTS=1"):
        LiveProviderRunConfig.from_environ({"PHASE9_LIVE_MAX_CALLS": "10", "PHASE9_LIVE_MAX_RUNS": "1"})

def test_report_requires_literal_label_and_safe_observation_shape():
    report = LiveProviderReport(
        label="NON-DETERMINISTIC LIVE PROVIDER EVIDENCE", schema_version="phase9-live-evidence-v1",
        suite_id="phase9-live-provider-evidence", generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        source_revision="test", evaluation_base_sha="2ff0e58d98e586f7904c726a4bb485a8419e2954",
        environment="local", config=LiveProviderRunConfig(True, 10, 1, None),
        observations=(valid_observation(),), stopped_stage=None,
        cost=CostEstimate(status=CostStatus.NOT_ESTABLISHED, amount_usd=None, reason="NO_PRICING_SNAPSHOT"),
    )
    assert report.label == "NON-DETERMINISTIC LIVE PROVIDER EVIDENCE"
    with pytest.raises(ValidationError):
        ProviderCallObservation.model_validate({**valid_observation().model_dump(), "raw_error": "secret"})
```

- [ ] **Step 2: Run the focused tests before implementation.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_live_provider_evaluation.py -k 'config or contract' -q`

Expected: FAIL because the domain module and types do not exist.

- [ ] **Step 3: Implement immutable, narrow contracts.**

Use `ConfigDict(extra="forbid", frozen=True)`. Permit only stage, method, configured/returned model, safe failure category, integer latency, nullable token counts, selected tool name, durable UUID/string references, cap counts, UTC timestamp, source revision, fixture identity, and pricing state. Model validators reject a total inconsistent with supplied total, non-USD pricing, non-official/missing provenance, and forbidden raw-content fields by omission rather than redaction transforms.

- [ ] **Step 4: Run focused domain tests.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_live_provider_evaluation.py -k 'config or contract' -q`

Expected: PASS; invalid configuration/artifact payloads fail before any client construction.

- [ ] **Step 5: Commit the independently reviewable change.**

```bash
git add backend/app/domain/live_evidence.py backend/tests/test_live_provider_evaluation.py
git commit -m "feat: add live evidence contracts"
```

### Task 5: Instrumented OpenAI client and shared hard budget

**Files:**
- Create: `backend/app/evaluation/live_openai_client.py`
- Create: `backend/tests/test_live_openai_client.py`

**Interfaces:**
- Produces `ProviderCallBudget(max_calls: int = 10)` with `admit(method: Literal["responses.create", "responses.parse"]) -> int` and read-only `attempted_calls`/`remaining_calls`.
- Produces `InstrumentedOpenAIClient(client: OpenAI, budget: ProviderCallBudget, clock: Callable[[], float] = perf_counter)` exposing `.responses.create(*args, **kwargs)` and `.responses.parse(*args, **kwargs)`.
- Produces `LiveProviderCallCapExceeded(OpenAIError)` and `observations: Sequence[ProviderCallObservation]`; successful calls return the exact SDK response object. A cap-exhausted call raises `LiveProviderCallCapExceeded` before invoking the fake/SDK method so current adapters retain provider-failure semantics.
- Consumed by Task 6 via existing `OpenAIAgentModel(client=instrumented_client)` and `OpenAISemanticSafetyChecker(client=instrumented_client)` constructors.

- [ ] **Step 1: Write failing no-network proxy tests.**

```python
from collections import deque
from types import SimpleNamespace

class FakeResponses:
    def __init__(self, responses: list[object]) -> None:
        self.responses = deque(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []
    def create(self, **kwargs: object) -> object:
        self.calls.append(("responses.create", kwargs)); return self.responses.popleft()
    def parse(self, **kwargs: object) -> object:
        self.calls.append(("responses.parse", kwargs)); return self.responses.popleft()

class FakeSDK:
    def __init__(self, responses: list[object]) -> None:
        self.responses = FakeResponses(responses)

class FakeClock:
    def __init__(self) -> None: self.values = deque([1.0, 1.012] * 10)
    def __call__(self) -> float: return self.values.popleft()

def sdk_response() -> object:
    return SimpleNamespace(model="gpt-test", usage=SimpleNamespace(input_tokens=3, output_tokens=5, total_tokens=8))

def test_create_and_parse_share_ten_call_budget():
    sdk = FakeSDK([sdk_response() for _ in range(10)])
    client = InstrumentedOpenAIClient(sdk, ProviderCallBudget(10), clock=FakeClock())
    for _ in range(5): client.responses.create(model="gpt-test")
    for _ in range(5): client.responses.parse(model="gpt-test")
    with pytest.raises(LiveProviderCallCapExceeded): client.responses.create(model="gpt-test")
    assert len(sdk.responses.calls) == 10

def test_response_identity_usage_and_redaction():
    response = sdk_response(); sdk = FakeSDK([response]); client = InstrumentedOpenAIClient(sdk, ProviderCallBudget(), clock=FakeClock())
    assert client.responses.create(input="secret", model="gpt-test") is response
    assert client.observations[0].input_tokens == 3
    assert "secret" not in client.observations[0].model_dump_json()
```

- [ ] **Step 2: Run the focused tests before implementation.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_live_openai_client.py -q`

Expected: FAIL because the proxy and budget do not exist.

- [ ] **Step 3: Implement the pre-request proxy.**

Construct the underlying live SDK client with `max_retries=0`. In each proxy method call `budget.admit()` before delegating, wrap only the delegated method in `perf_counter`, extract only SDK model/usage scalar fields after success, map exceptions to `LiveFailureKind` without retaining exception text, and re-raise the original error. Do not retain args, kwargs, prompts, payloads, response text, headers, request IDs, or tool arguments. The shared budget object is passed to both adapters; no telemetry is written to `AgentStep` or `SemanticSafetyAssessment`.

- [ ] **Step 4: Run focused plus adapter failure tests.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_live_openai_client.py backend/tests/test_agent_model_adapter.py backend/tests/test_semantic_safety_adapter.py -q`

Expected: PASS; calls 1–10 delegate, 11 cannot reach the fake SDK, create/parse share the cap, a second agent-runtime attempt consumes another admission, and normal adapter failures stay fail-safe.

- [ ] **Step 5: Commit the independently reviewable change.**

```bash
git add backend/app/evaluation/live_openai_client.py backend/tests/test_live_openai_client.py
git commit -m "feat: bound live provider requests"
```

### Task 6: Bounded live-provider evaluator, artifacts, and pricing

**Files:**
- Create: `backend/app/evaluation/live_provider.py`
- Modify: `backend/tests/test_live_provider_evaluation.py`

**Interfaces:**
- Produces `LiveProviderEvaluator(config: LiveProviderRunConfig, client_factory: Callable[[ProviderCallBudget], InstrumentedOpenAIClient], session_factory: Callable[[], ContextManager[Session]])`.
- Produces `run() -> LiveProviderReport`, `write_artifacts(report: LiveProviderReport, output_json: Path, output_markdown: Path) -> None`, and `render_live_evidence(report: LiveProviderReport) -> str`.
- Produces `estimate_cost(snapshot: PricingSnapshot | None, observations: Sequence[ProviderCallObservation]) -> CostEstimate`; it returns `NOT_ESTABLISHED` without an exact valid snapshot and complete observed input/output token pairs.
- CLI requires `RUN_LIVE_LLM_TESTS=1`, `OPENAI_API_KEY`, `PHASE9_LIVE_MAX_CALLS`, `PHASE9_LIVE_MAX_RUNS`, `--output-json`, and `--output-markdown`; it does not import/create `OpenAI` before configuration validation.
- Consumes Task 4 contracts and Task 5 single shared proxy; outputs only `docs/evaluations/live/` paths, never Phase 8 paths.
- The normal successful evaluator sequence consumes nine actual provider requests: connectivity semantic `parse` (1), canonical semantic smoke `parse` (1), one-tool agent `create` (1), complete hero five agent `create` calls plus one safety `parse` (6). The optional final one-tool sample is attempted only when all nine prior calls succeeded and consumes request 10. Any agent runtime retry consumes one more admission and may legitimately stop at cap.

- [ ] **Step 1: Write failing evaluator and pricing tests.**

```python
from contextlib import contextmanager
from collections import deque
from decimal import Decimal
from types import SimpleNamespace
from openai import OpenAIError
from backend.app.domain.cargo_safety import SemanticCheckResult, SemanticSafetyCheckOutput
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

@contextmanager
def isolated_session() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session: yield session
    finally:
        engine.dispose()

def config() -> LiveProviderRunConfig:
    return LiveProviderRunConfig(True, 10, 1, None)

class ScriptedResponses:
    def __init__(self, outcomes: list[object]) -> None: self.outcomes = deque(outcomes)
    def create(self, **kwargs: object) -> object: return self._next()
    def parse(self, **kwargs: object) -> object: return self._next()
    def _next(self) -> object:
        outcome = self.outcomes.popleft()
        if isinstance(outcome, Exception): raise outcome
        return outcome

class ScriptedSDK:
    def __init__(self, outcomes: list[object]) -> None: self.responses = ScriptedResponses(outcomes)

class EvaluatorClock:
    def __init__(self) -> None: self.values = deque([1.0, 1.010] * 10)
    def __call__(self) -> float: return self.values.popleft()

def valid_semantic_response() -> object:
    return SimpleNamespace(model="gpt-test", usage=SimpleNamespace(input_tokens=3, output_tokens=5, total_tokens=8), output_parsed=SemanticSafetyCheckOutput(result=SemanticCheckResult.CONTRADICTION_FOUND, explanation="fixture conflict", evidence_excerpt="corrosive"))

def scripted_client_for_stages(outcomes: list[object]) -> InstrumentedOpenAIClient:
    return InstrumentedOpenAIClient(ScriptedSDK(outcomes), ProviderCallBudget(10), clock=EvaluatorClock())

def test_evaluator_stops_at_first_failed_stage_without_network_afterward():
    client = scripted_client_for_stages([valid_semantic_response(), OpenAIError("synthetic")])
    report = LiveProviderEvaluator(config(), lambda budget: client, isolated_session).run()
    assert report.stopped_stage is LiveStage.SEMANTIC_SAFETY_SMOKE
    assert report.provider_call_count == 2

def test_cost_is_not_established_without_pinned_snapshot():
    client = scripted_client_for_stages([valid_semantic_response()])
    assert LiveProviderEvaluator(config(), lambda budget: client, isolated_session).run().cost.status is CostStatus.NOT_ESTABLISHED

def test_exact_model_snapshot_estimates_from_observed_tokens():
    snapshot = PricingSnapshot(provider="openai", model="gpt-test", currency="USD", input_unit="token", input_price_per_unit=Decimal("0.000001"), output_unit="token", output_price_per_unit=Decimal("0.000002"), official_source_url="https://openai.com/api/pricing/", source_date="2026-08-28", snapshot_commit_sha="a" * 40, estimate_label="ESTIMATED_USD")
    observation = ProviderCallObservation(call_number=1, stage=LiveStage.CONNECTIVITY_SMOKE, method="responses.parse", configured_model="gpt-test", returned_model="gpt-test", success=True, failure_kind=None, latency_ms=12, input_tokens=3, output_tokens=5, total_tokens=8, selected_tool=None)
    result = estimate_cost(snapshot, (observation,))
    assert result.status is CostStatus.ESTIMATED_USD and result.amount_usd == Decimal("0.000013")
```

- [ ] **Step 2: Run the focused tests before implementation.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_live_provider_evaluation.py -q`

Expected: FAIL because the evaluator, renderer, CLI, and pricing calculation do not exist.

- [ ] **Step 3: Implement the staged evaluator and exact complete hero workflow.**

Validate configuration before `client_factory` is called. Use one `ProviderCallBudget` and one injected `InstrumentedOpenAIClient` for both `OpenAIAgentModel(client=client)` and `OpenAISemanticSafetyChecker(client=client)`. The evaluator does not call a private state transition or reproduce optimizer/carrier/safety logic. It orchestrates these existing public calls in this exact order, recording each expected durable state and the proxy observation count after each model/checker call:

```python
from uuid import UUID
from backend.app.domain.agent_runtime import AgentEscalationReason, AgentRunState, AgentWaitKind
from backend.app.domain.carrier_recovery import CounterApprovalCommand, RequestApprovalCommand, SimulateCarrierResponseCommand
from backend.app.domain.enums import ApprovalStatus
from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
from backend.app.orchestration.carrier_recovery import build_carrier_recovery_workflow
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.orchestration.cargo_safety import CargoSafetyWorkflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.services.agent_model import OpenAIAgentModel
from backend.app.services.canonical_replay import CANONICAL_COUNTER_EFFECTIVE_AT, CANONICAL_SAFETY_CONTAINER_ID, CANONICAL_SAFETY_NOTE_SOURCE, CANONICAL_SAFETY_NOTE_TEXT, GUIDED_OPERATOR_ID
from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
from backend.app.services.semantic_safety import OpenAISemanticSafetyChecker
from backend.app.domain.carrier_recovery import AuthorizationSubjectKind
from backend.app.storage.agent_runtime import AgentRuntimeConflict

phase2 = build_scarce_capacity_workflow(session).run()
incident_id = phase2.incident.id
yard = DynamicYardWorkflow.for_session(session)
harness = CanonicalDynamicYardHarness()
yard.initialize(incident_id, harness.bootstrap_snapshot(incident_id))
configuration = CanonicalAgentRuntimeConfiguration.load()
runtime = AgentRuntimeCoordinator(
    session=session, model=OpenAIAgentModel(client=client),
    clock=configuration.clock("before_deadline"), configuration=configuration,
    cargo_safety_checker=OpenAISemanticSafetyChecker(client=client),
)
run = runtime.create_run(incident_id)
paused = runtime.advance(run.id)
assert paused.wait_kind is AgentWaitKind.NEW_OPERATIONAL_EVIDENCE
yard.ingest(harness.discharge_active_snapshot(incident_id))
reconsidered = runtime.advance(run.id)
assert reconsidered.state is AgentRunState.RUNNING
prepared = runtime.advance(run.id)
assert prepared.wait_kind is AgentWaitKind.REQUEST_APPROVAL
case_id = UUID(prepared.wait_subject_id)
carrier = build_carrier_recovery_workflow(session)
request_binding = next(item for item in carrier.history(case_id).bindings if item.subject_kind is AuthorizationSubjectKind.OUTBOUND_REQUEST)
carrier.record_request_approval(RequestApprovalCommand(case_id=case_id, proposal_decision_id=request_binding.proposal_decision_id, request_id=request_binding.subject_id, expected_payload_fingerprint=request_binding.payload_fingerprint, operator_id=GUIDED_OPERATOR_ID, status=ApprovalStatus.APPROVED))
sent = runtime.advance(run.id)
assert sent.wait_kind is AgentWaitKind.CARRIER_RESPONSE_OR_TIMEOUT
carrier.simulate_response(SimulateCarrierResponseCommand(case_id=case_id, effective_at=CANONICAL_COUNTER_EFFECTIVE_AT))
try:
    runtime.advance(run.id)
except AgentRuntimeConflict:
    pass
else:
    raise AssertionError("canonical COUNTER must require counter approval")
assert runtime.get_run(run.id).wait_kind is AgentWaitKind.COUNTER_APPROVAL
counter_binding = next(item for item in carrier.history(case_id).bindings if item.subject_kind is AuthorizationSubjectKind.COUNTER_PROPOSAL)
carrier.record_counter_approval(CounterApprovalCommand(case_id=case_id, proposal_decision_id=counter_binding.proposal_decision_id, carrier_response_id=counter_binding.subject_id, expected_payload_fingerprint=counter_binding.payload_fingerprint, operator_id=GUIDED_OPERATOR_ID, status=ApprovalStatus.APPROVED))
review = CargoSafetyWorkflow.for_session(session, checker=OpenAISemanticSafetyChecker(client=client)).create_review(incident_id, CANONICAL_SAFETY_CONTAINER_ID, CANONICAL_SAFETY_NOTE_TEXT, CANONICAL_SAFETY_NOTE_SOURCE)
terminal = runtime.advance(run.id)
assert terminal.state is AgentRunState.ESCALATED and terminal.escalation_reason is AgentEscalationReason.SAFETY_REVIEW_REQUIRED
assert CargoSafetyWorkflow.for_session(session, checker=OpenAISemanticSafetyChecker(client=client)).history(review.id).policy_result.automation_blocked is True
```

The expected normal model sequence is exactly five `responses.create` calls for `pause_agent_run`, `request_expedite_feasibility`, `prepare_rta_request` with `SYN-CONN-JV2`, `send_authorised_rta_request`, and `request_cargo_safety_review` for `SYN-CNT-010`; the final safety action makes one `responses.parse` call. `AgentRun.step_count == 6` is an established durable outcome, not a sixth model choice. Approvals and simulated carrier response are evaluator-orchestrated synthetic operator/carrier actions through existing durable workflow commands; the model receives no approval tool and never approves anything.

The normal admission ledger is fixed: connectivity semantic `parse` = call 1; canonical semantic smoke `parse` = call 2; single-exposed-tool agent `create` = call 3; hero pause `create` = call 4; R0-to-R1 reconsideration `create` = call 5; JV2 preparation `create` = call 6; authorised send `create` = call 7; safety-review selection `create` = call 8; safety evaluation `parse` = call 9. Assert the reconsideration history records R0 then R1, with totals 601 -> 602 and expected preserved 12.02 -> 12.04, before request preparation. After the hero, make one optional single-tool `create` as call 10 only if calls 1–9 succeeded without retry. Stop immediately after any failed stage, cap exception, or durable invariant failure; do not move to a later stage.

- [ ] **Step 4: Implement exact pricing behavior.**

Load `PHASE9_LIVE_PRICING_SNAPSHOT` only when set. Require pinned snapshot fields `provider`, exact `model`, `currency="USD"`, input/output units and rates, official source URL, source date, snapshot commit SHA, and estimate label. Calculate only with observed input and output token counts; otherwise emit `NOT_ESTABLISHED`. Reject mismatched model/provenance before provider construction. Do not add prices to repository source or infer costs from text.

- [ ] **Step 5: Run evaluator tests and no-network guard.**

Run: `RUN_LIVE_LLM_TESTS= uv run --python 3.12 --extra dev pytest backend/tests/test_live_provider_evaluation.py backend/tests/test_live_openai_client.py -q`

Expected: PASS; default tests construct no real SDK client, artifacts exclude forbidden content, report stages/caps/pricing are deterministic under fakes, and no output path begins with `docs/evaluations/phase8-`.

- [ ] **Step 6: Commit the independently reviewable change.**

```bash
git add backend/app/evaluation/live_provider.py backend/tests/test_live_provider_evaluation.py
git commit -m "feat: add bounded live provider evidence"
```

### Task 7: Deployment and operator documentation

**Files:**
- Create: `docs/deployment.md`
- Modify: `backend/tests/test_deployment_config.py`

**Interfaces:**
- Produces an operator-only checklist naming environment variables, no secrets, the root Dockerfile, Railway `/data` volume and `/healthz`, Vercel `web/` root/build, `VITE_API_BASE_URL`, CORS exact origin, persistence/rollback checks, live authorization gate, and `uv --python 3.12` commands.
- Consumed by Task 9 manual/deployment authorization checkpoint; it is not application configuration.

- [ ] **Step 1: Write failing documentation contract tests.**

```python
def test_deployment_doc_names_required_runtime_contracts():
    text = Path("docs/deployment.md").read_text()
    for required in ("sqlite:////data/transshipment.db", "GET /healthz", "VITE_API_BASE_URL", "RUN_LIVE_LLM_TESTS=1", "US$5"):
        assert required in text
```

- [ ] **Step 2: Run the focused test before documentation exists.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_deployment_config.py -k deployment_doc -q`

Expected: FAIL because `docs/deployment.md` does not exist.

- [ ] **Step 3: Write the exact operator guide.**

Document Railway Dockerfile deployment, mount `/data`, configure `DATABASE_URL=sqlite:////data/transshipment.db`, `ALLOWED_ORIGINS`, models, and server-only key; document Vercel project root `web`, build `npm run build`, and public Railway API base with no trailing slash. Include persistence/redeploy and rollback instructions, browser refresh checks, secret-sentinel build scan, and the explicit stop requiring separate human authorization before any resource creation or live CLI invocation.

- [ ] **Step 4: Run focused docs/config tests.**

Run: `uv run --python 3.12 --extra dev pytest backend/tests/test_deployment_config.py -q`

Expected: PASS; documentation and all local deployment boundaries agree.

- [ ] **Step 5: Commit the independently reviewable change.**

```bash
git add docs/deployment.md backend/tests/test_deployment_config.py
git commit -m "docs: add phase 9 deployment guide"
```

### Task 8: Deterministic release gates and Phase 8 non-regression

**Files:**
- Modify only if a test failure reveals an in-scope defect in a Task 1–7 owned file; otherwise no files.

**Interfaces:**
- Consumes all local implementation interfaces and frozen Phase 8 command/artifact paths.
- Produces command output proving local behavior only; it cannot prove Railway persistence, Vercel routing, or live-provider observations.

- [ ] **Step 1: Verify Phase 8 provider isolation before broader checks.**

Run: `OPENAI_API_KEY= uv run --python 3.12 --extra dev python -m backend.app.evaluation.evidence --output-json /tmp/phase8-phase9-check.json --output-markdown /tmp/phase8-phase9-check.md --runtime-repetitions 20`

Expected before and after Phase 9: exit 0; report validates with the existing fingerprint semantics; `live_model_token_usage`, `live_model_cost`, and `live_model_latency` remain `DEFERRED`; no provider construction/network call occurs.

- [ ] **Step 2: Run local backend and frontend release gates without live credentials.**

Run:

```bash
OPENAI_API_KEY= uv run --python 3.12 --extra dev pytest
uv lock --check
cd web && npm ci && npm test -- --run && npm run typecheck && npm run build && npm run lint
```

Expected before fixes: any in-scope regression fails with its focused test name. Expected after fixes: all commands exit 0; no live evaluator is invoked.

- [ ] **Step 3: Verify output boundaries and available Docker runtime.**

Run:

```bash
git diff --check
git status --short
cd web
rm -rf dist
OPENAI_API_KEY=PHASE9_SERVER_SECRET_SENTINEL DATABASE_URL=PHASE9_DATABASE_SECRET_SENTINEL VITE_API_BASE_URL=https://api.example.invalid npm run build
if rg -F -n 'PHASE9_SERVER_SECRET_SENTINEL' dist || rg -F -n 'PHASE9_DATABASE_SECRET_SENTINEL' dist; then exit 1; fi
cd ..
docker build -t psa-phase9-local .
container_id=$(docker run -d -e PORT=8000 -e DATABASE_URL=sqlite:////tmp/transshipment.db -p 18000:8000 psa-phase9-local)
trap 'docker rm -f "$container_id" >/dev/null 2>&1 || true' EXIT
for attempt in {1..30}; do curl --fail --silent --show-error http://127.0.0.1:18000/healthz > /tmp/psa-phase9-health.json && break; sleep 1; done
test -s /tmp/psa-phase9-health.json
test "$(cat /tmp/psa-phase9-health.json)" = '{"status":"ok","database":"ready"}'
docker rm -f "$container_id"
trap - EXIT
```

Expected: the Vite build embeds only `VITE_API_BASE_URL`; the `if rg` condition exits non-zero if either server-secret sentinel reaches `web/dist`. If Docker is available, the detached disposable container returns exactly the documented health JSON, then the trap/manual removal cleans it up. If Docker is unavailable, run the frontend sentinel command, record the Docker command/output as unavailable, and do not substitute a claim of Railway verification.

- [ ] **Step 4: Commit only a necessary in-scope correction.**

```bash
git add backend/app/storage/database.py backend/app/main.py backend/app/domain/live_evidence.py backend/app/evaluation/live_openai_client.py backend/app/evaluation/live_provider.py backend/tests Dockerfile .dockerignore docs/deployment.md
git commit -m "fix: complete phase 9 release gates"
```

Expected: create this commit only when Step 1–3 required an actual correction; otherwise create no verification-only commit and retain the task outputs in the handoff.

### Task 9: Manual authorization checkpoint and post-deployment verification

**Files:**
- Create after explicit authorization only: `docs/evaluations/live/${ARTIFACT_STAMP}-phase9-live-provider.json`
- Create after explicit authorization only: `docs/evaluations/live/${ARTIFACT_STAMP}-phase9-live-provider.md`
- Modify after explicit authorization only: `docs/deployment.md` only to record non-secret verified deployment URL/date if the operator approves committing it.

**Interfaces:**
- Consumes deployed Railway URL, deployed Vercel origin, Railway `/data` volume, server-side model/key configuration, Task 6 CLI, and the shared ten-call budget.
- Produces honest non-deterministic evidence and external verification observations; it never alters Phase 8 artifacts or deterministic decision semantics.

- [ ] **Step 1: Stop for explicit human authorization.**

Do not create Railway/Vercel resources, set a real key, run a live CLI, or spend API funds until the human explicitly authorizes this task. Present the required settings: Railway root Dockerfile, `/data` volume, `DATABASE_URL`, exact `ALLOWED_ORIGINS`, models, secret key; Vercel root `web`, `VITE_API_BASE_URL`; and the US$5 ceiling.

Expected before authorization: no external resources, provider calls, or live artifacts exist.

- [ ] **Step 2: Verify deployed infrastructure in isolation.**

After authorization, set `RAILWAY_URL` to the Railway HTTPS public origin and `VERCEL_ORIGIN` to the exact Vercel HTTPS origin; neither value is committed. Run:

```bash
curl --fail --silent --show-error "$RAILWAY_URL/healthz"
curl --silent --include --request OPTIONS "$RAILWAY_URL/healthz" --header "Origin: $VERCEL_ORIGIN" --header 'Access-Control-Request-Method: GET'
curl --silent --include --request OPTIONS "$RAILWAY_URL/healthz" --header 'Origin: https://unrelated.example' --header 'Access-Control-Request-Method: GET'
```

Expected: health returns ready JSON; exact Vercel origin receives the configured CORS header; unrelated origin does not. Create a canonical demo, retain its returned identifier, restart/redeploy Railway without replacing `/data`, then GET the identifier and refresh the Vercel browser view to prove durable state. Do not represent local SQLite tests as this proof.

- [ ] **Step 3: Run the bounded live sequence only after infrastructure verification.**

The Phase 9 evidence CLI runs locally on the authorized operator Mac using an explicitly supplied ephemeral `OPENAI_API_KEY`; Railway secrets are never assumed to be visible to local `uv run`. Set `ARTIFACT_STAMP` to the UTC timestamp selected for this evidence run, export the key only in the current shell, and remove it after the command. The deployed Vercel-to-Railway live check is separate: it uses Railway’s configured server-only key through the existing browser/API route and consumes no local CLI credential.

```bash
export OPENAI_API_KEY
RUN_LIVE_LLM_TESTS=1 PHASE9_LIVE_MAX_CALLS=10 PHASE9_LIVE_MAX_RUNS=1 \
uv run --python 3.12 --extra dev python -m backend.app.evaluation.live_provider \
  --output-json "docs/evaluations/live/${ARTIFACT_STAMP}-phase9-live-provider.json" \
  --output-markdown "docs/evaluations/live/${ARTIFACT_STAMP}-phase9-live-provider.md"
unset OPENAI_API_KEY
```

Expected: local connectivity, semantic safety, single-tool selection, at most one complete workflow, and at most one final sample proceed in order only while budget remains. Stop at first failed stage/cap; an eleventh actual request cannot occur. Record model/usage/latency/durable outcomes only, label artifacts literally, and calculate cost only from a validated official snapshot; otherwise retain `NOT_ESTABLISHED`. The separate deployed check makes at most one explicitly authorized live provider action through Vercel -> Railway: create canonical scarcity, POST dynamic-yard bootstrap, create a real `/incidents/{incident_id}/agent-runs`, then POST its `/advance` and observe `WAITING / NEW_OPERATIONAL_EVIDENCE`. It is skipped when the local artifact reaches the US$5 ceiling.

- [ ] **Step 4: Commit only honest external evidence.**

```bash
git add docs/evaluations/live docs/deployment.md
git commit -m "docs: record phase 9 live provider evidence"
```

Expected: commit only artifacts actually observed after authorization. If a stage fails or no authorization occurs, commit no fabricated evidence and leave deployment acceptance criteria pending.

## Spec-to-task coverage and external-proof boundary

| Spec section / acceptance criterion | Implementing task | Proof boundary |
|---|---|---|
| Goals, non-goals, Python/database configuration, SQLite-only engine (1–3) | 1 | Local deterministic tests; Railway volume proof is Task 9. |
| Railway Docker contract and `/data` persistence (5, 8, AC 1–5, 17) | 2, 3, 7 | Docker contract/local smoke; deployed persistence requires Task 9. |
| Vercel, CORS, secret boundary (6, 7, AC 6–8) | 2, 7, 8 | Local middleware/build checks; deployed browser/CORS requires Task 9. |
| Runtime models and existing fail-safe behavior (9, AC 9–10) | 5, 6, 7 | Fake clients locally; live behavior requires Task 9. |
| Separate live evidence, telemetry, cost, artifacts (10, AC 11, 13–14) | 4, 5, 6 | Fake deterministic tests locally; live facts require Task 9. |
| Ten-request shared budget, retry behavior, no forbidden capture (10, AC 12) | 5, 6 | Fake SDK proves boundary; live run verifies observed result in Task 9. |
| Phase 8 separation and regression (11, AC 15) | 8 | Deterministic local command only. |
| Rollback, operator setup, manual authorization, deployed sequence (12–14, AC 16) | 7, 9 | Task 9 only after explicit human authorization. |

## Plan self-review

- Spec coverage: every Phase 9 design section and all 17 acceptance criteria map to Tasks 1–9 above; Railway/Vercel persistence and live-model facts are explicitly reserved for Task 9.
- Completeness scan: no unresolved markers, unnamed work, vague test/error steps, angle-bracket substitutions, or ellipses are present; every code task names files, produced interfaces, pre-change failure command, post-change command, and focused commit.
- Type/signature consistency: Task 1 supplies `build_engine` to Task 2; Task 4 contracts supply Task 5 observations/config and Task 6 report/artifacts; Task 5’s proxy is injected through existing adapter `client=` seams without altering their contracts; Task 6 owns its CLI and artifact writer; Task 9 consumes only those interfaces.
- Hero review: Task 6 follows the existing guided hero’s public workflow/API ordering, has five agent `create` decisions plus one semantic `parse`, preserves the durable six-step outcome, and leaves request/counter approval to explicit synthetic operator commands outside the model.
- Build/release review: Task 3 validates `uv sync --frozen --no-dev --no-install-project` in a cacheable dependency layer before backend/shared copies; Task 8 uses sentinel rejection and a bounded self-cleaning detached Docker smoke.
- Safety and external-proof review: no task changes deterministic authority, Phase 8 semantics, database technology, or Phase 10 UI; default tests use fakes and absent credentials; the shared pre-request budget prevents an eleventh provider request; contracts omit prohibited content and secrets. The local evidence CLI uses an explicitly supplied operator key, while Railway/Vercel proof requires explicit authorization and is never claimed from local checks.
