from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Sequence
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, field_validator, model_validator

from backend.app.domain.enums import ApprovalStatus
from backend.app.domain.models import Approval, AuditEvent, CarrierResponse, Decision, RTARequest, FrozenContract, utc_now


class CarrierRecoveryCaseState(StrEnum):
    PREPARED = "PREPARED"
    AWAITING_REQUEST_APPROVAL = "AWAITING_REQUEST_APPROVAL"
    AWAITING_CARRIER = "AWAITING_CARRIER"
    AWAITING_COUNTER_APPROVAL = "AWAITING_COUNTER_APPROVAL"
    RECOMPUTING = "RECOMPUTING"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"


class AuthorizationSubjectKind(StrEnum):
    OUTBOUND_REQUEST = "OUTBOUND_REQUEST"
    COUNTER_PROPOSAL = "COUNTER_PROPOSAL"


class CarrierRecoveryDisposition(StrEnum):
    PRESERVED_VIA_RTA = "PRESERVED_VIA_RTA"
    STILL_ROLL = "STILL_ROLL"
    ESCALATE = "ESCALATE"


class ReconsiderationEvidenceKind(StrEnum):
    EFFECTIVE_CONNECTION_TIMING = "EFFECTIVE_CONNECTION_TIMING"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    COUNTER_REJECTED = "COUNTER_REJECTED"
    RESPONSE_TIMEOUT = "RESPONSE_TIMEOUT"


class RequestCloseReason(StrEnum):
    REQUEST_REJECTED = "REQUEST_REJECTED"
    RESPONSE_TIMEOUT = "RESPONSE_TIMEOUT"


def parse_explicit_utc(value: str) -> datetime:
    if not isinstance(value, str) or not (value.endswith("Z") or value.endswith("+00:00")):
        raise ValueError("timestamp must be explicit UTC ending in Z or +00:00")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("timestamp must be UTC")
    return parsed.astimezone(UTC)


class _UtcContract(FrozenContract):
    @field_validator("*", mode="after")
    @classmethod
    def _timestamps_are_utc(cls, value):
        if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)):
            raise ValueError("timestamps must be UTC")
        return value


class CarrierRecoveryCase(_UtcContract):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    connection_id: str = Field(min_length=1)
    source_evaluation_id: UUID
    affected_container_ids: tuple[str, ...] = Field(min_length=1)
    state: CarrierRecoveryCaseState
    created_at: AwareDatetime = Field(default_factory=utc_now)
    updated_at: AwareDatetime = Field(default_factory=utc_now)

    @field_validator("affected_container_ids")
    @classmethod
    def _snapshot_is_unique_and_nonempty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not container_id for container_id in value) or len(set(value)) != len(value):
            raise ValueError("affected container snapshot must be unique and non-empty")
        return value


class RTARequestContext(_UtcContract):
    case_id: UUID
    request_id: UUID
    payload_fingerprint: str = Field(min_length=1)
    response_deadline: AwareDatetime
    sent_at: AwareDatetime | None = None
    closed_at: AwareDatetime | None = None
    close_reason: RequestCloseReason | None = None
    timeout_observed_at: AwareDatetime | None = None


class ApprovalBinding(_UtcContract):
    case_id: UUID
    proposal_decision_id: UUID
    subject_kind: AuthorizationSubjectKind
    subject_id: UUID
    payload_fingerprint: str = Field(min_length=1)
    created_at: AwareDatetime = Field(default_factory=utc_now)


class EffectiveConnectionTiming(_UtcContract):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    request_id: UUID
    carrier_response_id: UUID
    effective_eta_pta: AwareDatetime
    created_at: AwareDatetime = Field(default_factory=utc_now)


class CarrierRecoveryDecisionLink(_UtcContract):
    case_id: UUID
    decision_id: UUID
    role: str = Field(min_length=1)
    created_at: AwareDatetime = Field(default_factory=utc_now)


class ContainerReconsiderationResult(_UtcContract):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    container_id: str = Field(min_length=1)
    disposition: CarrierRecoveryDisposition
    prior_decision_id: UUID
    replacement_decision_id: UUID | None = None
    preserved_world_count: int = Field(ge=0)
    world_count: int = Field(gt=0)
    hard_constraints_satisfied: bool
    reconsideration_evidence_kind: ReconsiderationEvidenceKind
    effective_connection_timing_id: UUID | None = None
    rejected_approval_id: UUID | None = None
    timeout_request_context_id: UUID | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _evidence_reference_matches_kind(self):
        references = (
            self.effective_connection_timing_id,
            self.rejected_approval_id,
            self.timeout_request_context_id,
        )
        if sum(item is not None for item in references) != 1:
            raise ValueError("exactly one typed reconsideration evidence reference is required")
        expected = {
            ReconsiderationEvidenceKind.EFFECTIVE_CONNECTION_TIMING: self.effective_connection_timing_id,
            ReconsiderationEvidenceKind.REQUEST_REJECTED: self.rejected_approval_id,
            ReconsiderationEvidenceKind.COUNTER_REJECTED: self.rejected_approval_id,
            ReconsiderationEvidenceKind.RESPONSE_TIMEOUT: self.timeout_request_context_id,
        }[self.reconsideration_evidence_kind]
        if expected is None:
            raise ValueError("reconsideration evidence reference does not match its kind")
        return self


class CarrierSimulationResult(_UtcContract):
    case_id: UUID
    carrier_response_id: UUID | None = None
    no_response_emitted: bool


class CarrierRecoveryHistory(FrozenContract):
    case: CarrierRecoveryCase
    request: RTARequest | None = None
    request_context: RTARequestContext | None = None
    bindings: Sequence[ApprovalBinding] = ()
    approvals: Sequence[Approval] = ()
    carrier_responses: Sequence[CarrierResponse] = ()
    effective_timings: Sequence[EffectiveConnectionTiming] = ()
    decision_links: Sequence[CarrierRecoveryDecisionLink] = ()
    decisions: Sequence[Decision] = ()
    results: Sequence[ContainerReconsiderationResult] = ()
    audit_events: Sequence[AuditEvent] = ()


class _ExplicitUtcCommand(FrozenContract):
    @field_validator("requested_eta_pta", "response_deadline", "effective_at", mode="before", check_fields=False)
    @classmethod
    def _parse_utc(cls, value):
        return parse_explicit_utc(value)


class PrepareCarrierRecoveryCaseCommand(_ExplicitUtcCommand):
    incident_id: UUID
    connection_id: str = Field(min_length=1)
    requested_eta_pta: AwareDatetime
    response_deadline: AwareDatetime

    @model_validator(mode="after")
    def _deadline_follows_requested_timing(self) -> "PrepareCarrierRecoveryCaseCommand":
        if self.response_deadline <= self.requested_eta_pta:
            raise ValueError("response deadline must be later than requested timing")
        return self


class RequestApprovalCommand(FrozenContract):
    case_id: UUID
    proposal_decision_id: UUID
    request_id: UUID
    expected_payload_fingerprint: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    status: ApprovalStatus


class CounterApprovalCommand(FrozenContract):
    case_id: UUID
    proposal_decision_id: UUID
    carrier_response_id: UUID
    expected_payload_fingerprint: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    status: ApprovalStatus


class SimulateCarrierResponseCommand(_ExplicitUtcCommand):
    case_id: UUID
    effective_at: AwareDatetime


class EvaluateTimeoutCommand(_ExplicitUtcCommand):
    case_id: UUID
    effective_at: AwareDatetime


class CarrierRecoveryCaseStateMachine:
    _transitions = {
        CarrierRecoveryCaseState.PREPARED: {CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL},
        CarrierRecoveryCaseState.AWAITING_REQUEST_APPROVAL: {CarrierRecoveryCaseState.AWAITING_CARRIER, CarrierRecoveryCaseState.RECOMPUTING},
        CarrierRecoveryCaseState.AWAITING_CARRIER: {CarrierRecoveryCaseState.AWAITING_COUNTER_APPROVAL, CarrierRecoveryCaseState.RECOMPUTING},
        CarrierRecoveryCaseState.AWAITING_COUNTER_APPROVAL: {CarrierRecoveryCaseState.RECOMPUTING},
        CarrierRecoveryCaseState.RECOMPUTING: {CarrierRecoveryCaseState.COMPLETED, CarrierRecoveryCaseState.ESCALATED},
    }

    def transition(self, case: CarrierRecoveryCase, target: CarrierRecoveryCaseState) -> CarrierRecoveryCase:
        if target not in self._transitions.get(case.state, set()):
            raise ValueError(f"invalid carrier recovery transition: {case.state} -> {target}")
        return case.model_copy(update={"state": target, "updated_at": utc_now()})
