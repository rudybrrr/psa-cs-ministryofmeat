from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.domain.live_evidence import (
    CostEstimate,
    CostStatus,
    LiveProviderReport,
    LiveProviderRunConfig,
    LiveStage,
    PricingSnapshot,
    ProviderCallObservation,
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
