from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Iterator
from uuid import UUID

import pytest
from openai import OpenAIError
from pydantic import ValidationError
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.app.domain.cargo_safety import (
    CargoSafetyReviewState,
    SemanticCheckResult,
    SemanticSafetyCheckOutput,
)
from backend.app.domain.live_evidence import (
    CostEstimate,
    CostStatus,
    LiveProviderReport,
    LiveProviderRunConfig,
    LiveStage,
    PricingSnapshot,
    ProviderCallObservation,
)
from backend.app.evaluation import live_provider
from backend.app.evaluation.live_openai_client import InstrumentedOpenAIClient, ProviderCallBudget
from backend.app.evaluation.live_provider import (
    LiveProviderEvaluator,
    _validate_pricing_snapshot_provenance,
    estimate_cost,
    main,
    render_live_evidence,
    write_artifacts,
)
from backend.app.storage.cargo_safety import CargoSafetyRepository


@contextmanager
def isolated_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def config() -> LiveProviderRunConfig:
    return LiveProviderRunConfig(True, 10, 1, None)


class ScriptedResponses:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = deque(outcomes)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(("responses.create", kwargs))
        return self._next(kwargs)

    def parse(self, **kwargs: object) -> object:
        self.calls.append(("responses.parse", kwargs))
        return self._next(kwargs)

    def _next(self, kwargs: dict[str, object]) -> object:
        outcome = self.outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        if callable(outcome):
            return outcome(kwargs)
        return outcome


class ScriptedSDK:
    def __init__(self, outcomes: list[object]) -> None:
        self.responses = ScriptedResponses(outcomes)


class EvaluatorClock:
    def __init__(self) -> None:
        self.values = deque([1.0, 1.010] * 10)

    def __call__(self) -> float:
        return self.values.popleft()


def valid_semantic_response() -> object:
    return SimpleNamespace(
        model="gpt-test",
        usage=SimpleNamespace(input_tokens=3, output_tokens=5, total_tokens=8),
        output_parsed=SemanticSafetyCheckOutput(
            result=SemanticCheckResult.CONTRADICTION_FOUND,
            explanation="fixture conflict",
            evidence_excerpt="corrosive",
        ),
    )


def semantic_response(result: SemanticCheckResult) -> object:
    return SimpleNamespace(
        model="gpt-test",
        usage=SimpleNamespace(input_tokens=3, output_tokens=5, total_tokens=8),
        output_parsed=SemanticSafetyCheckOutput(
            result=result,
            explanation="fixture result",
            evidence_excerpt=(
                "corrosive"
                if result is SemanticCheckResult.CONTRADICTION_FOUND
                else None
            ),
        ),
    )


def tool_response(name: str, arguments: dict[str, str] | None = None) -> object:
    return SimpleNamespace(
        model="gpt-test",
        usage=SimpleNamespace(input_tokens=3, output_tokens=5, total_tokens=8),
        output=(
            SimpleNamespace(
                type="function_call",
                status="completed",
                name=name,
                arguments=json.dumps(arguments or {}),
            ),
        ),
    )


def invalid_tool_response() -> object:
    return SimpleNamespace(
        model="gpt-test",
        usage=SimpleNamespace(input_tokens=3, output_tokens=5, total_tokens=8),
        output=(),
    )


def send_authorised_response(kwargs: dict[str, object]) -> object:
    context = json.loads(str(kwargs["input"]))
    return tool_response(
        "send_authorised_rta_request",
        {"case_id": context["summary"]["carrier_cases"][0]["id"]},
    )


def scripted_client_for_stages(outcomes: list[object]) -> InstrumentedOpenAIClient:
    return InstrumentedOpenAIClient(
        ScriptedSDK(outcomes), ProviderCallBudget(10), clock=EvaluatorClock()
    )


def valid_observation() -> ProviderCallObservation:
    return ProviderCallObservation(
        call_number=1,
        stage=LiveStage.CONNECTIVITY_SMOKE,
        method="responses.parse",
        configured_model="gpt-test",
        returned_model="gpt-test",
        success=True,
        failure_kind=None,
        latency_ms=12,
        input_tokens=3,
        output_tokens=5,
        total_tokens=8,
        selected_tool=None,
    )


def report_metrics(*, empty: bool = False) -> dict[str, object]:
    return {
        "attempted_provider_call_count": 0 if empty else 1,
        "successful_provider_call_count": 0 if empty else 1,
        "failed_provider_call_count": 0,
        "complete_workflow_count": 0,
        "p50_successful_latency_ms": None if empty else 12,
        "p95_successful_latency_ms": None if empty else 12,
        "latency_provenance": "CLIENT_OBSERVED_REQUEST_LATENCY",
    }


def test_live_config_rejects_missing_opt_in_and_limits() -> None:
    with pytest.raises(TypeError):
        LiveProviderRunConfig()

    with pytest.raises(ValueError, match="RUN_LIVE_LLM_TESTS=1"):
        LiveProviderRunConfig.from_environ(
            {"PHASE9_LIVE_MAX_CALLS": "10", "PHASE9_LIVE_MAX_RUNS": "1"}
        )

    for name, value in (("PHASE9_LIVE_MAX_CALLS", "0"), ("PHASE9_LIVE_MAX_CALLS", "11"), ("PHASE9_LIVE_MAX_RUNS", "2")):
        with pytest.raises(ValueError):
            LiveProviderRunConfig.from_environ(
                {
                    "RUN_LIVE_LLM_TESTS": "1",
                    "PHASE9_LIVE_MAX_CALLS": "10",
                    "PHASE9_LIVE_MAX_RUNS": "1",
                    name: value,
                }
            )


def test_report_contract_rejects_raw_content_and_inconsistent_tokens() -> None:
    report = LiveProviderReport(
        label="NON-DETERMINISTIC LIVE PROVIDER EVIDENCE",
        schema_version="phase9-live-evidence-v1",
        suite_id="phase9-live-provider-evidence",
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        source_revision="b" * 40,
        evaluation_base_sha="2ff0e58d98e586f7904c726a4bb485a8419e2954",
        environment="local",
        config=LiveProviderRunConfig(True, 10, 1, None),
        observations=(valid_observation(),),
        **report_metrics(),
        stopped_stage=None,
        cost=CostEstimate(
            status=CostStatus.NOT_ESTABLISHED,
            amount_usd=None,
            reason="NO_PRICING_SNAPSHOT",
        ),
    )

    assert report.label == "NON-DETERMINISTIC LIVE PROVIDER EVIDENCE"
    assert report.provider_call_count == 1
    payload = report.model_dump(mode="json")
    assert payload["attempted_provider_call_count"] == 1
    assert payload["successful_provider_call_count"] == 1
    assert payload["failed_provider_call_count"] == 0
    assert payload["complete_workflow_count"] == 0
    assert payload["p50_successful_latency_ms"] == 12
    assert payload["p95_successful_latency_ms"] == 12
    assert payload["latency_provenance"] == "CLIENT_OBSERVED_REQUEST_LATENCY"
    with pytest.raises(ValidationError):
        ProviderCallObservation.model_validate(
            {**valid_observation().model_dump(), "raw_error": "secret"}
        )
    with pytest.raises(ValidationError):
        ProviderCallObservation.model_validate(
            {**valid_observation().model_dump(), "total_tokens": 7}
        )


def test_cost_reasons_are_bounded() -> None:
    with pytest.raises(ValidationError):
        CostEstimate(status=CostStatus.NOT_ESTABLISHED, reason="provider said no")


def test_report_call_count_is_bounded() -> None:
    report = LiveProviderReport(
        label="NON-DETERMINISTIC LIVE PROVIDER EVIDENCE",
        schema_version="phase9-live-evidence-v1",
        suite_id="phase9-live-provider-evidence",
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        source_revision="b" * 40,
        evaluation_base_sha="2ff0e58d98e586f7904c726a4bb485a8419e2954",
        environment="local",
        config=LiveProviderRunConfig(True, 10, 1, None),
        observations=(valid_observation(),),
        **report_metrics(),
        stopped_stage=None,
        cost=CostEstimate(status=CostStatus.NOT_ESTABLISHED, reason="NO_PRICING_SNAPSHOT"),
    )
    with pytest.raises(ValidationError):
        LiveProviderReport(
            **{
                **report.model_dump(),
                "config": LiveProviderRunConfig(True, 1, 1, None),
                "observations": (
                    valid_observation(),
                    valid_observation().model_copy(update={"call_number": 2}),
                ),
            }
        )


def test_pricing_snapshot_requires_usd_and_official_provenance() -> None:
    snapshot = dict(
        provider="openai",
        model="gpt-test",
        currency="USD",
        input_unit="token",
        input_price_per_unit=Decimal("0.000001"),
        output_unit="token",
        output_price_per_unit=Decimal("0.000002"),
        official_source_url="https://openai.com/api/pricing/",
        source_date="2026-08-28",
        snapshot_commit_sha="a" * 40,
        estimate_label="ESTIMATED_USD",
    )
    assert PricingSnapshot(**snapshot).currency == "USD"
    with pytest.raises(ValidationError):
        PricingSnapshot(**{**snapshot, "currency": "EUR"})
    with pytest.raises(ValidationError):
        PricingSnapshot(**{**snapshot, "official_source_url": "https://example.com/pricing"})


def test_config_does_not_expose_api_key() -> None:
    config = LiveProviderRunConfig.from_environ(
        {
            "RUN_LIVE_LLM_TESTS": "1",
            "PHASE9_LIVE_MAX_CALLS": "10",
            "PHASE9_LIVE_MAX_RUNS": "1",
            "PHASE9_LIVE_PRICING_SNAPSHOT": "pricing.json",
            "OPENAI_API_KEY": "not-a-config-field",
        }
    )
    assert config.pricing_snapshot_path == Path("pricing.json")
    assert "OPENAI_API_KEY" not in config.model_dump()


def test_evaluator_stops_at_first_failed_stage_without_network_afterward() -> None:
    client = scripted_client_for_stages(
        [valid_semantic_response(), OpenAIError("synthetic")]
    )

    report = LiveProviderEvaluator(
        config(), lambda budget: client, isolated_session
    ).run()

    assert report.stopped_stage is LiveStage.SEMANTIC_SAFETY_SMOKE
    assert report.provider_call_count == 2


def test_failed_last_admitted_call_reports_the_concrete_stage() -> None:
    client = InstrumentedOpenAIClient(
        ScriptedSDK([valid_semantic_response(), OpenAIError("synthetic")]),
        ProviderCallBudget(2),
        clock=EvaluatorClock(),
    )
    bounded = LiveProviderRunConfig(True, 2, 1, None)

    report = LiveProviderEvaluator(
        bounded, lambda budget: client, isolated_session
    ).run()

    assert report.stopped_stage is LiveStage.SEMANTIC_SAFETY_SMOKE
    assert report.provider_call_count == 2


def test_successful_latency_percentiles_use_nearest_rank() -> None:
    clock = iter((1.0, 1.010, 2.0, 2.020, 3.0, 3.030))
    client = InstrumentedOpenAIClient(
        ScriptedSDK(
            [
                valid_semantic_response(),
                valid_semantic_response(),
                OpenAIError("synthetic"),
            ]
        ),
        ProviderCallBudget(10),
        clock=lambda: next(clock),
    )

    report = LiveProviderEvaluator(
        config(), lambda budget: client, isolated_session
    ).run()

    assert report.p50_successful_latency_ms == 10
    assert report.p95_successful_latency_ms == 20


def test_canonical_semantic_smoke_requires_the_expected_contradiction() -> None:
    client = scripted_client_for_stages(
        [
            valid_semantic_response(),
            semantic_response(SemanticCheckResult.NO_CONTRADICTION_FOUND),
        ]
    )

    report = LiveProviderEvaluator(
        config(), lambda budget: client, isolated_session
    ).run()

    assert report.stopped_stage is LiveStage.SEMANTIC_SAFETY_SMOKE
    assert report.provider_call_count == 2


def test_runtime_retry_preserves_call_cap_rejection() -> None:
    outcomes = [
        valid_semantic_response(),
        valid_semantic_response(),
        tool_response("pause_agent_run"),
        invalid_tool_response(),
        tool_response("pause_agent_run"),
        invalid_tool_response(),
        tool_response("request_expedite_feasibility"),
        invalid_tool_response(),
        tool_response("prepare_rta_request", {"connection_id": "SYN-CONN-JV2"}),
        invalid_tool_response(),
    ]
    sdk = ScriptedSDK(outcomes)

    def factory(budget: ProviderCallBudget) -> InstrumentedOpenAIClient:
        return InstrumentedOpenAIClient(sdk, budget, clock=EvaluatorClock())

    report = LiveProviderEvaluator(config(), factory, isolated_session).run()

    assert report.stopped_stage is LiveStage.STOPPED_AT_CALL_CAP
    assert report.provider_call_count == 10
    assert len(sdk.responses.calls) == 10


def test_cost_is_not_established_without_pinned_snapshot() -> None:
    client = scripted_client_for_stages([valid_semantic_response()])

    report = LiveProviderEvaluator(
        config(), lambda budget: client, isolated_session
    ).run()

    assert report.cost.status is CostStatus.NOT_ESTABLISHED


def test_exact_model_snapshot_estimates_from_observed_tokens() -> None:
    snapshot = PricingSnapshot(
        provider="openai",
        model="gpt-test",
        currency="USD",
        input_unit="token",
        input_price_per_unit=Decimal("0.000001"),
        output_unit="token",
        output_price_per_unit=Decimal("0.000002"),
        official_source_url="https://openai.com/api/pricing/",
        source_date="2026-08-28",
        snapshot_commit_sha="a" * 40,
        estimate_label="ESTIMATED_USD",
    )
    observation = valid_observation()

    result = estimate_cost(snapshot, (observation,))

    assert result.status is CostStatus.ESTIMATED_USD
    assert result.amount_usd == Decimal("0.000013")


def test_complete_fake_workflow_uses_exact_ledger_and_durable_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes = [
        valid_semantic_response(),
        valid_semantic_response(),
        tool_response("pause_agent_run"),
        tool_response("pause_agent_run"),
        tool_response("request_expedite_feasibility"),
        tool_response("prepare_rta_request", {"connection_id": "SYN-CONN-JV2"}),
        send_authorised_response,
        tool_response(
            "request_cargo_safety_review", {"container_id": "SYN-CNT-010"}
        ),
        valid_semantic_response(),
        tool_response("pause_agent_run"),
    ]
    client = scripted_client_for_stages(outcomes)
    monkeypatch.setenv("GIT_COMMIT_SHA", "f" * 40)

    report = LiveProviderEvaluator(
        config(), lambda budget: client, isolated_session
    ).run()

    assert report.stopped_stage is None
    assert report.provider_call_count == 10
    assert [item.stage for item in report.observations] == [
        LiveStage.CONNECTIVITY_SMOKE,
        LiveStage.SEMANTIC_SAFETY_SMOKE,
        LiveStage.TOOL_SELECTION_SMOKE,
        *([LiveStage.COMPLETE_WORKFLOW] * 6),
        LiveStage.OPTIONAL_SAMPLE,
    ]
    assert [item.method for item in report.observations] == [
        "responses.parse",
        "responses.parse",
        "responses.create",
        "responses.create",
        "responses.create",
        "responses.create",
        "responses.create",
        "responses.create",
        "responses.parse",
        "responses.create",
    ]
    assert [
        item.selected_tool for item in report.observations if item.selected_tool
    ] == [
        "pause_agent_run",
        "pause_agent_run",
        "request_expedite_feasibility",
        "prepare_rta_request",
        "send_authorised_rta_request",
        "request_cargo_safety_review",
        "pause_agent_run",
    ]
    assert report.agent_run_id is not None
    assert len(report.agent_step_ids) == 6
    assert report.safety_assessment_id is not None
    assert report.final_outcome_id is not None
    assert report.semantic_smoke_review_id is not None
    assert report.semantic_smoke_assessment_id is not None
    assert report.semantic_smoke_policy_result_id is not None
    assert report.attempted_provider_call_count == 10
    assert report.successful_provider_call_count == 10
    assert report.failed_provider_call_count == 0
    assert report.complete_workflow_count == 1
    assert report.p50_successful_latency_ms == 10
    assert report.p95_successful_latency_ms == 10
    checkout_sha = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    assert report.source_revision == checkout_sha


def test_semantic_smoke_persists_and_reports_fail_closed_outcome() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @contextmanager
    def sessions() -> Iterator[Session]:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            yield session

    client = scripted_client_for_stages(
        [valid_semantic_response(), valid_semantic_response(), OpenAIError("stop")]
    )
    try:
        report = LiveProviderEvaluator(config(), lambda budget: client, sessions).run()
        assert report.stopped_stage is LiveStage.TOOL_SELECTION_SMOKE
        assert report.semantic_smoke_review_id is not None
        with Session(engine) as session:
            history = CargoSafetyRepository(session).history(
                UUID(report.semantic_smoke_review_id)
            )
        assert history.review.state is CargoSafetyReviewState.COMPLETED
        assert str(history.assessment.id) == report.semantic_smoke_assessment_id
        assert str(history.policy_result.id) == report.semantic_smoke_policy_result_id
        assert history.policy_result.automation_blocked is True
    finally:
        engine.dispose()


def test_invalid_pricing_snapshot_stops_before_client_construction() -> None:
    snapshot_path = Path(".test-phase9-invalid-pricing-snapshot.json")
    snapshot_path.write_text('{"provider":"openai"}', encoding="utf-8")
    called = False

    def factory(budget: ProviderCallBudget) -> InstrumentedOpenAIClient:
        nonlocal called
        called = True
        return scripted_client_for_stages([])

    try:
        evaluator = LiveProviderEvaluator(
            LiveProviderRunConfig(True, 10, 1, snapshot_path),
            factory,
            isolated_session,
        )

        with pytest.raises(ValueError, match="invalid PHASE9_LIVE_PRICING_SNAPSHOT"):
            evaluator.run()
        assert called is False
    finally:
        snapshot_path.unlink(missing_ok=True)


def test_non_openai_pricing_snapshot_stops_before_client_construction() -> None:
    snapshot_path = Path(".test-phase9-non-openai-pricing-snapshot.json")
    snapshot_path.write_text(
        PricingSnapshot(
            provider="not-openai",
            model="gpt-5.6-luna",
            currency="USD",
            input_unit="token",
            input_price_per_unit=Decimal("0.000001"),
            output_unit="token",
            output_price_per_unit=Decimal("0.000002"),
            official_source_url="https://openai.com/api/pricing/",
            source_date="2026-08-28",
            snapshot_commit_sha="a" * 40,
            estimate_label="ESTIMATED_USD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    called = False

    def factory(budget: ProviderCallBudget) -> InstrumentedOpenAIClient:
        nonlocal called
        called = True
        return scripted_client_for_stages([])

    try:
        evaluator = LiveProviderEvaluator(
            LiveProviderRunConfig(True, 10, 1, snapshot_path),
            factory,
            isolated_session,
        )

        with pytest.raises(ValueError, match="provider must be openai"):
            evaluator.run()
        assert called is False
    finally:
        snapshot_path.unlink(missing_ok=True)


def test_pricing_snapshot_path_must_be_repository_contained_and_tracked(
    tmp_path: Path,
) -> None:
    checkout_sha = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    snapshot = PricingSnapshot(
        provider="openai",
        model="gpt-5.6-luna",
        currency="USD",
        input_unit="token",
        input_price_per_unit=Decimal("0.000001"),
        output_unit="token",
        output_price_per_unit=Decimal("0.000002"),
        official_source_url="https://openai.com/api/pricing/",
        source_date="2026-08-28",
        snapshot_commit_sha=checkout_sha,
        estimate_label="ESTIMATED_USD",
    )
    outside = tmp_path / "pricing.json"
    untracked = Path(".test-phase9-pricing-snapshot.json")
    outside.write_text(snapshot.model_dump_json(), encoding="utf-8")
    untracked.write_text(snapshot.model_dump_json(), encoding="utf-8")
    called = False

    def factory(budget: ProviderCallBudget) -> InstrumentedOpenAIClient:
        nonlocal called
        called = True
        return scripted_client_for_stages([])

    try:
        with pytest.raises(ValueError, match="repository-contained"):
            LiveProviderEvaluator(
                LiveProviderRunConfig(True, 10, 1, outside),
                factory,
                isolated_session,
            ).run()
        with pytest.raises(ValueError, match="Git-tracked"):
            LiveProviderEvaluator(
                LiveProviderRunConfig(True, 10, 1, untracked),
                factory,
                isolated_session,
            ).run()
        assert called is False
    finally:
        untracked.unlink(missing_ok=True)


def test_pricing_snapshot_sha_must_identify_a_commit_containing_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "checkout"
    snapshot_path = repo_root / "docs" / "pricing.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot = PricingSnapshot(
        provider="openai",
        model="gpt-5.6-luna",
        currency="USD",
        input_unit="token",
        input_price_per_unit=Decimal("0.000001"),
        output_unit="token",
        output_price_per_unit=Decimal("0.000002"),
        official_source_url="https://openai.com/api/pricing/",
        source_date="2026-08-28",
        snapshot_commit_sha="a" * 40,
        estimate_label="ESTIMATED_USD",
    )
    snapshot_path.write_text(snapshot.model_dump_json(), encoding="utf-8")

    def fake_git(args, **kwargs):
        if args[1] == "ls-files":
            return subprocess.CompletedProcess(args, 0, stdout=b"")
        if args[1:3] == ("show", f"HEAD:{snapshot_path.relative_to(repo_root)}"):
            return subprocess.CompletedProcess(args, 0, stdout=snapshot_path.read_bytes())
        if args[1] == "show":
            return subprocess.CompletedProcess(args, 1, stdout=b"")
        if args[1:3] == ("merge-base", "--is-ancestor"):
            return subprocess.CompletedProcess(args, 0, stdout=b"")
        raise AssertionError(f"unexpected git command: {args}")

    monkeypatch.setattr(subprocess, "run", fake_git)

    with pytest.raises(ValueError, match="contain the snapshot path"):
        _validate_pricing_snapshot_provenance(snapshot_path, snapshot, repo_root)


def test_pricing_snapshot_provenance_accepts_committed_path_without_self_reference(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "checkout"
    repo_root.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(
            ("git", *args),
            cwd=repo_root,
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()

    git("init")
    git("config", "user.email", "phase9-tests@example.invalid")
    git("config", "user.name", "Phase 9 Tests")
    git("config", "commit.gpgsign", "false")
    snapshot_path = repo_root / "docs" / "pricing.json"
    snapshot_path.parent.mkdir(parents=True)
    initial = PricingSnapshot(
        provider="openai",
        model="gpt-5.6-luna",
        currency="USD",
        input_unit="token",
        input_price_per_unit=Decimal("0.000001"),
        output_unit="token",
        output_price_per_unit=Decimal("0.000002"),
        official_source_url="https://openai.com/api/pricing/",
        source_date="2026-08-28",
        snapshot_commit_sha="a" * 40,
        estimate_label="ESTIMATED_USD",
    )
    snapshot_path.write_text(initial.model_dump_json(), encoding="utf-8")
    git("add", "docs/pricing.json")
    git("commit", "-m", "add pricing snapshot path")
    path_commit = git("rev-parse", "HEAD")
    snapshot = initial.model_copy(update={"snapshot_commit_sha": path_commit})
    snapshot_path.write_text(snapshot.model_dump_json(), encoding="utf-8")
    git("add", "docs/pricing.json")
    git("commit", "-m", "pin pricing snapshot path commit")

    _validate_pricing_snapshot_provenance(snapshot_path, snapshot, repo_root)


@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    (
        ("input_price_per_unit", Decimal("0.000009")),
        ("official_source_url", "https://www.openai.com/api/pricing/"),
    ),
)
def test_pricing_snapshot_provenance_rejects_changed_validated_payload_fields(
    tmp_path: Path, changed_field: str, changed_value: object
) -> None:
    repo_root = tmp_path / "checkout"
    repo_root.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(
            ("git", *args),
            cwd=repo_root,
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()

    git("init")
    git("config", "user.email", "phase9-tests@example.invalid")
    git("config", "user.name", "Phase 9 Tests")
    git("config", "commit.gpgsign", "false")
    snapshot_path = repo_root / "docs" / "pricing.json"
    snapshot_path.parent.mkdir(parents=True)
    historical_payload = {
        "provider": "openai",
        "model": "gpt-5.6-luna",
        "currency": "USD",
        "input_unit": "token",
        "input_price_per_unit": Decimal("0.000001"),
        "output_unit": "token",
        "output_price_per_unit": Decimal("0.000002"),
        "official_source_url": "https://openai.com/api/pricing/",
        "source_date": "2026-08-28",
        "snapshot_commit_sha": "a" * 40,
        "estimate_label": "ESTIMATED_USD",
        changed_field: changed_value,
    }
    historical = PricingSnapshot.model_validate(historical_payload)
    snapshot_path.write_text(historical.model_dump_json(), encoding="utf-8")
    git("add", "docs/pricing.json")
    git("commit", "-m", "add historical pricing snapshot")
    snapshot_commit = git("rev-parse", "HEAD")
    current = PricingSnapshot.model_validate(
        {
            **historical_payload,
            "input_price_per_unit": Decimal("0.000001"),
            "official_source_url": "https://openai.com/api/pricing/",
            "snapshot_commit_sha": snapshot_commit,
        }
    )
    snapshot_path.write_text(current.model_dump_json(), encoding="utf-8")
    git("add", "docs/pricing.json")
    git("commit", "-m", "change validated pricing snapshot field")

    with pytest.raises(ValueError, match="validated payload fields"):
        _validate_pricing_snapshot_provenance(snapshot_path, current, repo_root)


def test_pricing_snapshot_does_not_require_agent_and_semantic_models_to_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = PricingSnapshot(
        provider="openai",
        model="gpt-5.6-luna",
        currency="USD",
        input_unit="token",
        input_price_per_unit=Decimal("0.000001"),
        output_unit="token",
        output_price_per_unit=Decimal("0.000002"),
        official_source_url="https://openai.com/api/pricing/",
        source_date="2026-08-28",
        snapshot_commit_sha="a" * 40,
        estimate_label="ESTIMATED_USD",
    )
    snapshot_path = tmp_path / "pricing.json"
    snapshot_path.write_text(snapshot.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(live_provider, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        live_provider,
        "_validate_pricing_snapshot_provenance",
        lambda path, loaded, repo_root: None,
    )
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.6-luna")
    monkeypatch.setenv("OPENAI_AGENT_MODEL", "gpt-5.6-terra")

    loaded = LiveProviderEvaluator(
        LiveProviderRunConfig(True, 10, 1, snapshot_path),
        lambda budget: scripted_client_for_stages([]),
        isolated_session,
    )._load_snapshot()

    assert loaded == snapshot


def test_artifacts_are_safe_and_restricted_to_live_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.app.evaluation import live_provider

    fake_module = tmp_path / "backend" / "app" / "evaluation" / "live_provider.py"
    monkeypatch.setattr(live_provider, "__file__", str(fake_module))
    report = LiveProviderReport(
        label="NON-DETERMINISTIC LIVE PROVIDER EVIDENCE",
        schema_version="phase9-live-evidence-v1",
        suite_id="phase9-live-provider-evidence",
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        source_revision="b" * 40,
        evaluation_base_sha="2ff0e58d98e586f7904c726a4bb485a8419e2954",
        environment="local",
        config=config(),
        observations=(valid_observation(),),
        **report_metrics(),
        stopped_stage=None,
        cost=CostEstimate(
            status=CostStatus.NOT_ESTABLISHED, reason="NO_PRICING_SNAPSHOT"
        ),
    )
    output_json = Path("docs/evaluations/live/report.json")
    output_markdown = Path("docs/evaluations/live/report.md")

    write_artifacts(report, output_json, output_markdown)

    json_text = (tmp_path / output_json).read_text(encoding="utf-8")
    markdown_text = (tmp_path / output_markdown).read_text(encoding="utf-8")
    assert LiveProviderReport.model_validate_json(json_text) == report
    assert markdown_text == render_live_evidence(report)
    for forbidden in ("OPENAI_API_KEY", "fixture conflict", "corrosive", "phase8-"):
        assert forbidden not in json_text + markdown_text
    assert "NO_PRICING_SNAPSHOT" in markdown_text
    assert "CLIENT_OBSERVED_REQUEST_LATENCY" in markdown_text
    durable = report.model_copy(
        update={
            "semantic_smoke_review_id": "smoke-review",
            "semantic_smoke_assessment_id": "smoke-assessment",
            "semantic_smoke_policy_result_id": "smoke-policy",
            "agent_run_id": "agent-run",
            "agent_step_ids": ("step-1", "step-2"),
            "safety_assessment_id": "hero-assessment",
            "final_outcome_id": "hero-outcome",
        }
    )
    durable_text = render_live_evidence(durable)
    for value in (
        "smoke-review",
        "smoke-assessment",
        "smoke-policy",
        "agent-run",
        "step-1",
        "hero-assessment",
        "hero-outcome",
    ):
        assert value in durable_text
    estimated = report.model_copy(
        update={
            "cost": CostEstimate(
                status=CostStatus.ESTIMATED_USD,
                amount_usd=Decimal("0.000013"),
                pricing_snapshot_commit_sha="a" * 40,
            )
        }
    )
    estimated_text = render_live_evidence(estimated)
    assert "0.000013" in estimated_text
    assert "a" * 40 in estimated_text
    with pytest.raises(ValueError, match="docs/evaluations/live"):
        write_artifacts(report, Path("outside.json"), output_markdown)
    with pytest.raises(ValueError, match="distinct"):
        write_artifacts(report, output_json, output_json)


def test_cost_requires_complete_exact_model_usage() -> None:
    snapshot = PricingSnapshot(
        provider="openai",
        model="gpt-test",
        currency="USD",
        input_unit="token",
        input_price_per_unit=Decimal("0.000001"),
        output_unit="token",
        output_price_per_unit=Decimal("0.000002"),
        official_source_url="https://openai.com/api/pricing/",
        source_date="2026-08-28",
        snapshot_commit_sha="a" * 40,
        estimate_label="ESTIMATED_USD",
    )
    incomplete = valid_observation().model_copy(update={"output_tokens": None})
    mismatch = valid_observation().model_copy(update={"returned_model": "gpt-other"})

    assert estimate_cost(snapshot, (incomplete,)).reason == "INCOMPLETE_TOKEN_USAGE"
    assert estimate_cost(snapshot, (mismatch,)).reason == "MODEL_MISMATCH"


def test_cost_is_not_established_when_any_observed_model_mismatches_snapshot() -> None:
    snapshot = PricingSnapshot(
        provider="openai",
        model="gpt-5.6-luna",
        currency="USD",
        input_unit="token",
        input_price_per_unit=Decimal("0.000001"),
        output_unit="token",
        output_price_per_unit=Decimal("0.000002"),
        official_source_url="https://openai.com/api/pricing/",
        source_date="2026-08-28",
        snapshot_commit_sha="a" * 40,
        estimate_label="ESTIMATED_USD",
    )
    terra = valid_observation().model_copy(
        update={
            "configured_model": "gpt-5.6-terra",
            "returned_model": "gpt-5.6-terra",
        }
    )
    luna = valid_observation().model_copy(
        update={
            "call_number": 2,
            "configured_model": "gpt-5.6-luna",
            "returned_model": "gpt-5.6-luna",
        }
    )

    result = estimate_cost(snapshot, (terra, luna))

    assert result.status is CostStatus.NOT_ESTABLISHED
    assert result.reason == "MODEL_MISMATCH"


def test_cli_validates_configuration_then_builds_the_bounded_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.evaluation import live_provider

    monkeypatch.setenv("RUN_LIVE_LLM_TESTS", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("PHASE9_LIVE_MAX_CALLS", "10")
    monkeypatch.setenv("PHASE9_LIVE_MAX_RUNS", "1")
    report = LiveProviderReport(
        label="NON-DETERMINISTIC LIVE PROVIDER EVIDENCE",
        schema_version="phase9-live-evidence-v1",
        suite_id="phase9-live-provider-evidence",
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        source_revision="b" * 40,
        evaluation_base_sha="2ff0e58d98e586f7904c726a4bb485a8419e2954",
        environment="local",
        config=config(),
        observations=(),
        **report_metrics(empty=True),
        stopped_stage=None,
        cost=CostEstimate(
            status=CostStatus.NOT_ESTABLISHED, reason="NO_PRICING_SNAPSHOT"
        ),
    )
    monkeypatch.setattr(LiveProviderEvaluator, "run", lambda self: report)
    written: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        live_provider,
        "write_artifacts",
        lambda result, output_json, output_markdown: written.append(
            (output_json, output_markdown)
        ),
    )

    result = main(
        [
            "--output-json",
            "docs/evaluations/live/report.json",
            "--output-markdown",
            "docs/evaluations/live/report.md",
        ]
    )

    assert result == 0
    assert written == [
        (
            Path("docs/evaluations/live/report.json"),
            Path("docs/evaluations/live/report.md"),
        )
    ]


@pytest.mark.parametrize(
    ("output_json", "output_markdown"),
    [
        ("outside.json", "docs/evaluations/live/report.md"),
        (
            "docs/evaluations/phase8-live-provider.json",
            "docs/evaluations/live/report.md",
        ),
        (
            "docs/evaluations/live/report.json",
            "docs/evaluations/live/report.json",
        ),
    ],
)
def test_cli_rejects_output_paths_before_evaluator_or_client_work(
    output_json: str,
    output_markdown: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.evaluation import live_provider

    monkeypatch.setenv("RUN_LIVE_LLM_TESTS", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("PHASE9_LIVE_MAX_CALLS", "10")
    monkeypatch.setenv("PHASE9_LIVE_MAX_RUNS", "1")
    monkeypatch.delenv("PHASE9_LIVE_PRICING_SNAPSHOT", raising=False)
    touched = False

    def forbidden_evaluator(*args: object, **kwargs: object) -> None:
        nonlocal touched
        touched = True
        raise AssertionError("evaluator must not be constructed")

    monkeypatch.setattr(live_provider, "LiveProviderEvaluator", forbidden_evaluator)

    with pytest.raises(ValueError):
        main(
            [
                "--output-json",
                output_json,
                "--output-markdown",
                output_markdown,
            ]
        )
    assert touched is False


def test_untracked_pricing_is_rejected_before_live_client_import_in_fresh_process() -> None:
    checkout_sha = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    snapshot_path = Path(".test-phase9-fresh-process-untracked-pricing.json")
    snapshot_path.write_text(
        PricingSnapshot(
            provider="openai",
            model="gpt-5.6-luna",
            currency="USD",
            input_unit="token",
            input_price_per_unit=Decimal("0.000001"),
            output_unit="token",
            output_price_per_unit=Decimal("0.000002"),
            official_source_url="https://openai.com/api/pricing/",
            source_date="2026-08-28",
            snapshot_commit_sha=checkout_sha,
            estimate_label="ESTIMATED_USD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    script = """
import builtins
import os
import sys

real_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.startswith("backend.app.evaluation.live_openai_client"):
        raise AssertionError("live client imported before pricing validation")
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded_import

from backend.app.evaluation.live_provider import main

os.environ.update({
    "RUN_LIVE_LLM_TESTS": "1",
    "OPENAI_API_KEY": "synthetic-test-key",
    "PHASE9_LIVE_MAX_CALLS": "10",
    "PHASE9_LIVE_MAX_RUNS": "1",
    "PHASE9_LIVE_PRICING_SNAPSHOT": sys.argv[1],
})
try:
    main([
        "--output-json", "docs/evaluations/live/report.json",
        "--output-markdown", "docs/evaluations/live/report.md",
    ])
except ValueError as error:
    assert "Git-tracked" in str(error)
else:
    raise AssertionError("untracked pricing snapshot was accepted")
"""

    try:
        result = subprocess.run(
            [sys.executable, "-c", script, str(snapshot_path)],
            cwd=Path.cwd(),
            env={**os.environ, "OPENAI_API_KEY": "", "RUN_LIVE_LLM_TESTS": ""},
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
    finally:
        snapshot_path.unlink(missing_ok=True)
