from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest
from openai import OpenAIError
from pydantic import ValidationError
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.app.domain.cargo_safety import SemanticCheckResult, SemanticSafetyCheckOutput
from backend.app.domain.live_evidence import (
    CostEstimate,
    CostStatus,
    LiveProviderReport,
    LiveProviderRunConfig,
    LiveStage,
    PricingSnapshot,
    ProviderCallObservation,
)
from backend.app.evaluation.live_openai_client import InstrumentedOpenAIClient, ProviderCallBudget
from backend.app.evaluation.live_provider import (
    LiveProviderEvaluator,
    estimate_cost,
    main,
    render_live_evidence,
    write_artifacts,
)


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
        source_revision="test",
        evaluation_base_sha="2ff0e58d98e586f7904c726a4bb485a8419e2954",
        environment="local",
        config=LiveProviderRunConfig(True, 10, 1, None),
        observations=(valid_observation(),),
        stopped_stage=None,
        cost=CostEstimate(
            status=CostStatus.NOT_ESTABLISHED,
            amount_usd=None,
            reason="NO_PRICING_SNAPSHOT",
        ),
    )

    assert report.label == "NON-DETERMINISTIC LIVE PROVIDER EVIDENCE"
    assert report.provider_call_count == 1
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
        source_revision="test",
        evaluation_base_sha="2ff0e58d98e586f7904c726a4bb485a8419e2954",
        environment="local",
        config=LiveProviderRunConfig(True, 10, 1, None),
        observations=(valid_observation(),),
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


def test_complete_fake_workflow_uses_exact_ledger_and_durable_outcomes() -> None:
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


def test_invalid_pricing_snapshot_stops_before_client_construction(
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "pricing.json"
    snapshot_path.write_text('{"provider":"openai"}', encoding="utf-8")
    called = False

    def factory(budget: ProviderCallBudget) -> InstrumentedOpenAIClient:
        nonlocal called
        called = True
        return scripted_client_for_stages([])

    evaluator = LiveProviderEvaluator(
        LiveProviderRunConfig(True, 10, 1, snapshot_path),
        factory,
        isolated_session,
    )

    with pytest.raises(ValueError, match="invalid PHASE9_LIVE_PRICING_SNAPSHOT"):
        evaluator.run()
    assert called is False


def test_non_openai_pricing_snapshot_stops_before_client_construction(
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "pricing.json"
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

    evaluator = LiveProviderEvaluator(
        LiveProviderRunConfig(True, 10, 1, snapshot_path),
        factory,
        isolated_session,
    )

    with pytest.raises(ValueError, match="provider must be openai"):
        evaluator.run()
    assert called is False


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
        source_revision="test",
        evaluation_base_sha="2ff0e58d98e586f7904c726a4bb485a8419e2954",
        environment="local",
        config=config(),
        observations=(valid_observation(),),
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
        source_revision="test",
        evaluation_base_sha="2ff0e58d98e586f7904c726a4bb485a8419e2954",
        environment="local",
        config=config(),
        observations=(),
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
