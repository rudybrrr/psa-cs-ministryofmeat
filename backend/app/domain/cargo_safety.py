from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from backend.app.domain.models import Decision, FrozenContract, utc_now


class CargoSafetyReviewState(StrEnum):
    PENDING_CHECK = "PENDING_CHECK"
    COMPLETED = "COMPLETED"


class SemanticCheckResult(StrEnum):
    NO_CONTRADICTION_FOUND = "NO_CONTRADICTION_FOUND"
    CONTRADICTION_FOUND = "CONTRADICTION_FOUND"
    INDETERMINATE = "INDETERMINATE"
    CHECK_FAILED = "CHECK_FAILED"


class SemanticCheckFailureKind(StrEnum):
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"


class SemanticSafetyDisposition(StrEnum):
    PASS_THROUGH = "PASS_THROUGH"
    ESCALATE = "ESCALATE"


class CargoNote(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    container_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4000)
    source: str = Field(min_length=1, max_length=200)
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def nonblank(self) -> Self:
        if not self.container_id.strip() or not self.text.strip() or not self.source.strip():
            raise ValueError("cargo note text, source, and container must not be blank")
        return self


class CargoSafetyReview(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    container_id: str = Field(min_length=1, max_length=128)
    cargo_note_id: UUID
    state: CargoSafetyReviewState = CargoSafetyReviewState.PENDING_CHECK
    created_at: AwareDatetime = Field(default_factory=utc_now)
    updated_at: AwareDatetime = Field(default_factory=utc_now)


class SemanticSafetyCheckInput(FrozenContract):
    structured_dangerous_goods: bool
    structured_un_number: str | None = Field(default=None, max_length=64)
    structured_commodity: str = Field(min_length=1, max_length=500)
    note_text: str = Field(min_length=1, max_length=4000)


class SemanticSafetyCheckOutput(FrozenContract):
    result: SemanticCheckResult
    explanation: str = Field(min_length=1, max_length=1000)
    evidence_excerpt: str | None = Field(default=None, min_length=1, max_length=1000)


class SemanticSafetyAssessment(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    incident_id: UUID
    container_id: str
    cargo_note_id: UUID
    result: SemanticCheckResult
    explanation: str = Field(min_length=1, max_length=1000)
    evidence_excerpt: str | None = Field(default=None, max_length=1000)
    failure_kind: SemanticCheckFailureKind | None = None
    structured_dangerous_goods: bool
    structured_un_number: str | None = Field(default=None, max_length=64)
    structured_commodity: str = Field(min_length=1, max_length=500)
    checker_kind: str = Field(min_length=1, max_length=100)
    model_name: str | None = Field(default=None, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=100)
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_failure_shape(self) -> Self:
        if self.result is SemanticCheckResult.CHECK_FAILED:
            if self.failure_kind is None:
                raise ValueError("CHECK_FAILED requires failure_kind")
            if self.evidence_excerpt is not None:
                raise ValueError("CHECK_FAILED must not persist evidence_excerpt")
        elif self.failure_kind is not None:
            raise ValueError("non-failed assessment must not have failure_kind")
        return self


class SemanticSafetyPolicyResult(FrozenContract):
    id: UUID = Field(default_factory=uuid4)
    review_id: UUID
    assessment_id: UUID
    incident_id: UUID
    container_id: str
    disposition: SemanticSafetyDisposition
    automation_blocked: bool
    reason: str = Field(min_length=1, max_length=1000)
    replacement_decision_id: UUID | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)


class CargoSafetyEvaluationResult(FrozenContract):
    review: CargoSafetyReview
    assessment: SemanticSafetyAssessment
    policy_result: SemanticSafetyPolicyResult
    decision: Decision | None = None
