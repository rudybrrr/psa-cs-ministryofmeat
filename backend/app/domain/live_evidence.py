from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
import math
from pathlib import Path
import statistics
from typing import Literal, Mapping, Self
from urllib.parse import urlparse

from pydantic import AwareDatetime, Field, field_validator, model_validator

from backend.app.domain.models import FrozenContract


class LiveStage(StrEnum):
    CONNECTIVITY_SMOKE = "CONNECTIVITY_SMOKE"
    SEMANTIC_SAFETY_SMOKE = "SEMANTIC_SAFETY_SMOKE"
    TOOL_SELECTION_SMOKE = "TOOL_SELECTION_SMOKE"
    COMPLETE_WORKFLOW = "COMPLETE_WORKFLOW"
    OPTIONAL_SAMPLE = "OPTIONAL_SAMPLE"
    STOPPED_AT_CALL_CAP = "STOPPED_AT_CALL_CAP"
    STOPPED_AT_RUN_CAP = "STOPPED_AT_RUN_CAP"


class LiveFailureKind(StrEnum):
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


class CostStatus(StrEnum):
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    ESTIMATED_USD = "ESTIMATED_USD"


class LiveProviderRunConfig(FrozenContract):
    run_live_llm_tests: Literal[True]
    max_calls: int = Field(gt=0, le=10)
    max_workflows: int = Field(gt=0, le=1)
    pricing_snapshot_path: Path | None

    def __init__(
        self,
        run_live_llm_tests: bool,
        max_calls: int,
        max_workflows: int,
        pricing_snapshot_path: Path | None,
        **data: object,
    ) -> None:
        super().__init__(
            run_live_llm_tests=run_live_llm_tests,
            max_calls=max_calls,
            max_workflows=max_workflows,
            pricing_snapshot_path=pricing_snapshot_path,
            **data,
        )

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> Self:
        if environ.get("RUN_LIVE_LLM_TESTS") != "1":
            raise ValueError("live tests require RUN_LIVE_LLM_TESTS=1")
        try:
            max_calls = int(environ["PHASE9_LIVE_MAX_CALLS"])
            max_workflows = int(environ["PHASE9_LIVE_MAX_RUNS"])
        except (KeyError, ValueError) as exc:
            raise ValueError("live tests require positive call and workflow limits") from exc
        snapshot = environ.get("PHASE9_LIVE_PRICING_SNAPSHOT")
        return cls(True, max_calls, max_workflows, Path(snapshot) if snapshot else None)


class ProviderCallObservation(FrozenContract):
    call_number: int = Field(gt=0)
    stage: LiveStage
    method: Literal["responses.create", "responses.parse"]
    configured_model: str = Field(min_length=1)
    returned_model: str | None = Field(default=None, min_length=1)
    success: bool
    failure_kind: LiveFailureKind | None
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    selected_tool: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def valid_outcome_and_tokens(self) -> Self:
        if self.success != (self.failure_kind is None):
            raise ValueError("successful calls have no failure kind; failed calls require one")
        if (
            self.total_tokens is not None
            and self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens != self.input_tokens + self.output_tokens
        ):
            raise ValueError("total tokens must match supplied input and output tokens")
        return self


class PricingSnapshot(FrozenContract):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    currency: Literal["USD"]
    input_unit: Literal["token"]
    input_price_per_unit: Decimal = Field(ge=0)
    output_unit: Literal["token"]
    output_price_per_unit: Decimal = Field(ge=0)
    official_source_url: str = Field(min_length=1)
    source_date: date
    snapshot_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    estimate_label: Literal["ESTIMATED_USD"]

    @field_validator("official_source_url")
    @classmethod
    def official_openai_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname not in {"openai.com", "www.openai.com"}:
            raise ValueError("pricing provenance must be an official OpenAI HTTPS URL")
        return value


class CostEstimate(FrozenContract):
    status: CostStatus
    amount_usd: Decimal | None = Field(default=None, ge=0)
    reason: Literal[
        "NO_PRICING_SNAPSHOT",
        "INVALID_PRICING_SNAPSHOT",
        "MODEL_MISMATCH",
        "INCOMPLETE_TOKEN_USAGE",
    ] | None = None
    pricing_snapshot_commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")

    @model_validator(mode="after")
    def valid_cost_shape(self) -> Self:
        if self.status is CostStatus.ESTIMATED_USD:
            if (
                self.amount_usd is None
                or self.pricing_snapshot_commit_sha is None
                or self.reason is not None
            ):
                raise ValueError("estimated USD cost requires amount and pricing snapshot only")
        elif (
            self.amount_usd is not None
            or self.pricing_snapshot_commit_sha is not None
            or self.reason is None
        ):
            raise ValueError("unestablished cost requires an allowlisted reason only")
        return self


class LiveProviderReport(FrozenContract):
    label: Literal["NON-DETERMINISTIC LIVE PROVIDER EVIDENCE"]
    schema_version: Literal["phase9-live-evidence-v1"]
    suite_id: Literal["phase9-live-provider-evidence"]
    generated_at: AwareDatetime
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    evaluation_base_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    environment: Literal["local", "deployed"]
    config: LiveProviderRunConfig
    fixture_ids: tuple[str, ...] = ()
    observations: tuple[ProviderCallObservation, ...]
    attempted_provider_call_count: int = Field(ge=0)
    successful_provider_call_count: int = Field(ge=0)
    failed_provider_call_count: int = Field(ge=0)
    complete_workflow_count: int = Field(ge=0, le=1)
    p50_successful_latency_ms: float | None = Field(default=None, ge=0)
    p95_successful_latency_ms: float | None = Field(default=None, ge=0)
    latency_provenance: Literal["CLIENT_OBSERVED_REQUEST_LATENCY"]
    stopped_stage: LiveStage | None
    cost: CostEstimate
    semantic_smoke_review_id: str | None = None
    semantic_smoke_assessment_id: str | None = None
    semantic_smoke_policy_result_id: str | None = None
    agent_run_id: str | None = None
    agent_step_ids: tuple[str, ...] = ()
    safety_assessment_id: str | None = None
    final_outcome_id: str | None = None

    @property
    def provider_call_count(self) -> int:
        return len(self.observations)

    @model_validator(mode="after")
    def observations_are_numbered_once(self) -> Self:
        numbers = [item.call_number for item in self.observations]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("observations must be consecutively numbered from one")
        if len(self.observations) > self.config.max_calls:
            raise ValueError("observations cannot exceed the configured call cap")
        successful = sum(item.success for item in self.observations)
        if (
            self.attempted_provider_call_count != len(self.observations)
            or self.successful_provider_call_count != successful
            or self.failed_provider_call_count != len(self.observations) - successful
        ):
            raise ValueError("serialized provider call counts must match observations")
        latencies = sorted(
            item.latency_ms
            for item in self.observations
            if item.success and item.latency_ms is not None
        )
        expected_p50 = float(statistics.median(latencies)) if latencies else None
        expected_p95 = (
            float(latencies[math.ceil(0.95 * len(latencies)) - 1])
            if latencies
            else None
        )
        if (
            self.p50_successful_latency_ms != expected_p50
            or self.p95_successful_latency_ms != expected_p95
        ):
            raise ValueError("latency percentiles must match successful observations")
        if self.complete_workflow_count > self.config.max_workflows:
            raise ValueError("complete workflow count exceeds configured cap")
        return self
