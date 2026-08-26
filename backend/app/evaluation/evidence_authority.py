"""Deterministic evidence for backend authority and human-tradeoff boundaries."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
import json
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.app.domain.agent_runtime import (
    AgentModelTurn,
    AgentRunState,
    AgentToolCall,
)
from backend.app.domain.canonical_replay import (
    CanonicalReplayActionType,
    CanonicalReplayStage,
)
from backend.app.domain.carrier_recovery import (
    CounterApprovalCommand,
    EvaluateTimeoutCommand,
    PrepareCarrierRecoveryCaseCommand,
    RequestApprovalCommand,
    SimulateCarrierResponseCommand,
)
from backend.app.domain.dynamic_yard import (
    AllocationRevision,
    ExpediteCommitment,
    ExpediteCommitmentStatus,
    ExpediteReconsiderationAssessment,
    ReconsiderationCandidate,
    ReconsiderationDisposition,
    TradeoffReviewState,
)
from backend.app.domain.enums import ApprovalStatus, IncidentState
from backend.app.domain.evidence import (
    ClaimReproducibility,
    ClaimStatus,
    EvidenceClaim,
    EvidenceReference,
    assert_verified,
)
from backend.app.domain.models import Incident
from backend.app.orchestration.agent_context import AgentToolRegistry
from backend.app.orchestration.agent_runtime import (
    AgentRuntimeCoordinator,
    CanonicalAgentRuntimeConfiguration,
)
from backend.app.orchestration.canonical_replay import project_canonical_replay_stage
from backend.app.orchestration.carrier_recovery import (
    CarrierRecoveryConflict,
    CarrierRecoveryWorkflow,
    build_carrier_recovery_workflow,
)
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.orchestration.scarce_capacity import build_scarce_capacity_workflow
from backend.app.services.agent_model import FakeAgentModel
from backend.app.services.canonical_incident import SyntheticCanonicalIncidentService
from backend.app.services.carrier_simulator import (
    DeterministicCarrierSimulator,
    SyntheticCarrierResponsePlan,
)
from backend.app.services.scenarios import SeededScenarioGenerator
from backend.app.storage.agent_runtime import AgentRuntimeConflict
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository
from backend.app.storage.dynamic_yard import DynamicYardConflict, DynamicYardRepository
from backend.app.storage.repositories import (
    AuditRepository,
    DecisionRepository,
    IncidentRepository,
    ScarcityEvaluationRepository,
)


_FIXTURE_ID = "SYN-CANONICAL-24-V1"
_FORBIDDEN_TOOLS = frozenset(
    {
        "hold_feeder",
        "change_carrier_schedule",
        "override_dg_rule",
        "set_yard_capacity",
    }
)
_AGENT_APPROVAL_AUTHORITY_TOOLS = frozenset(
    {
        "approve_request",
        "approve_counter",
        "approve_rta_request",
        "approve_counter_proposal",
        "record_request_approval",
        "record_counter_approval",
    }
)


class _SharedFixtureService:
    """Makes one canonical fixture object the exact fixture exercised by a probe."""

    def __init__(self, fixture) -> None:
        self._fixture = fixture

    def load(self):
        return self._fixture


@contextmanager
def _isolated_session() -> Iterator[Session]:
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


def _prepare_command(incident_id: UUID, connection_id: str) -> PrepareCarrierRecoveryCaseCommand:
    return PrepareCarrierRecoveryCaseCommand(
        incident_id=incident_id,
        connection_id=connection_id,
        prepared_at="2026-08-22T07:00:00Z",
        requested_eta_pta="2026-08-22T08:00:00Z",
        response_deadline="2026-08-22T09:00:00Z",
    )


def _assert_conflict(operation, claim_id: str, detail: str) -> str:
    try:
        operation()
    except CarrierRecoveryConflict as error:
        return type(error).__name__
    raise AssertionError(f"{claim_id}: {detail}")


def _assert_dynamic_conflict(operation, claim_id: str, detail: str) -> str:
    try:
        operation()
    except DynamicYardConflict as error:
        return type(error).__name__
    raise AssertionError(f"{claim_id}: {detail}")


def _assert_agent_wait_conflict(operation, claim_id: str, detail: str) -> None:
    try:
        operation()
    except AgentRuntimeConflict:
        return
    raise AssertionError(f"{claim_id}: {detail}")


def _carrier_workflow_with_fixture(
    session: Session,
    *,
    fixture_service: _SharedFixtureService,
    simulator: DeterministicCarrierSimulator,
) -> CarrierRecoveryWorkflow:
    return CarrierRecoveryWorkflow(
        fixture_service=fixture_service,
        scenarios=SeededScenarioGenerator(),
        cases=CarrierRecoveryRepository(session),
        incidents=IncidentRepository(session),
        evaluations=ScarcityEvaluationRepository(session),
        decisions=DecisionRepository(session),
        simulator=simulator,
    )


def _approve_request(workflow, case_id: UUID) -> None:
    binding = workflow.history(case_id).bindings[0]
    workflow.record_request_approval(
        RequestApprovalCommand(
            case_id=case_id,
            proposal_decision_id=binding.proposal_decision_id,
            request_id=binding.subject_id,
            expected_payload_fingerprint=binding.payload_fingerprint,
            operator_id="evidence-operator",
            status=ApprovalStatus.APPROVED,
        )
    )


def _authority_probe() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    with _isolated_session() as session:
        phase2 = build_scarce_capacity_workflow(session).run()
        workflow = build_carrier_recovery_workflow(session)
        case = workflow.prepare(_prepare_command(phase2.incident.id, "SYN-CONN-JV2"))
        request_history = workflow.history(case.id)
        request_lengths = (
            len(request_history.approvals),
            len(request_history.effective_timings),
            len(request_history.carrier_responses),
            len(request_history.results),
        )
        unapproved_exception = _assert_conflict(
            lambda: workflow.send_authorised_request(case.id),
            "carrier_request_authority_boundary",
            "unapproved request dispatch was accepted",
        )
        assert_verified(
            (
                len(workflow.history(case.id).approvals),
                len(workflow.history(case.id).effective_timings),
                len(workflow.history(case.id).carrier_responses),
                len(workflow.history(case.id).results),
            )
            == request_lengths,
            "carrier_request_authority_boundary",
            "unapproved request dispatch mutated carrier history",
        )
        binding = workflow.history(case.id).bindings[0]
        wrong_request_exception = _assert_conflict(
            lambda: workflow.record_request_approval(
                RequestApprovalCommand(
                    case_id=case.id,
                    proposal_decision_id=binding.proposal_decision_id,
                    request_id=binding.subject_id,
                    expected_payload_fingerprint="0" * 64,
                    operator_id="evidence-operator",
                    status=ApprovalStatus.APPROVED,
                )
            ),
            "carrier_request_authority_boundary",
            "wrong request fingerprint was accepted",
        )
        wrong_request_history = workflow.history(case.id)
        assert_verified(
            (
                len(wrong_request_history.approvals),
                len(wrong_request_history.effective_timings),
                len(wrong_request_history.carrier_responses),
                len(wrong_request_history.results),
            )
            == request_lengths,
            "carrier_request_authority_boundary",
            "wrong request fingerprint mutated carrier history",
        )

        # A separate incident keeps the requested COUNTER plan and carrier case isolated.
        counter_phase2 = build_scarce_capacity_workflow(session).run()
        counter_workflow = build_carrier_recovery_workflow(session)
        counter_case = counter_workflow.prepare(
            _prepare_command(counter_phase2.incident.id, "SYN-CONN-JV2")
        )
        _approve_request(counter_workflow, counter_case.id)
        counter_workflow.send_authorised_request(counter_case.id)
        counter_workflow.simulate_response(
            SimulateCarrierResponseCommand(
                case_id=counter_case.id,
                effective_at="2026-08-22T08:30:00Z",
            )
        )
        counter_history = counter_workflow.history(counter_case.id)
        counter_binding = counter_history.bindings[-1]
        counter_lengths = (
            len(counter_history.approvals),
            len(counter_history.effective_timings),
            len(counter_history.carrier_responses),
            len(counter_history.results),
        )
        wrong_counter_exception = _assert_conflict(
            lambda: counter_workflow.record_counter_approval(
                CounterApprovalCommand(
                    case_id=counter_case.id,
                    proposal_decision_id=counter_binding.proposal_decision_id,
                    carrier_response_id=counter_binding.subject_id,
                    expected_payload_fingerprint="0" * 64,
                    operator_id="evidence-operator",
                    status=ApprovalStatus.APPROVED,
                )
            ),
            "carrier_counter_authority_boundary",
            "wrong counter fingerprint was accepted",
        )
        wrong_counter_history = counter_workflow.history(counter_case.id)
        assert_verified(
            (
                len(wrong_counter_history.approvals),
                len(wrong_counter_history.effective_timings),
                len(wrong_counter_history.carrier_responses),
                len(wrong_counter_history.results),
            )
            == counter_lengths,
            "carrier_counter_authority_boundary",
            "wrong counter fingerprint mutated carrier history",
        )

        silent_fixture = SyntheticCanonicalIncidentService().load()
        silent_fixture_service = _SharedFixtureService(silent_fixture)
        silent_connection = next(
            profile.container.onward_connection
            for profile in silent_fixture.profiles
            if profile.container.onward_connection.id == "SYN-CONN-EC3"
        )
        silent_connection_before = silent_connection.model_dump(mode="json")
        silent_phase2 = build_scarce_capacity_workflow(session).run()
        silent_workflow = _carrier_workflow_with_fixture(
            session,
            fixture_service=silent_fixture_service,
            simulator=DeterministicCarrierSimulator(
                SyntheticCarrierResponsePlan().load_run("SILENT-RUN")
            ),
        )
        silent_case = silent_workflow.prepare(
            _prepare_command(silent_phase2.incident.id, "SYN-CONN-EC3")
        )
        _approve_request(silent_workflow, silent_case.id)
        silent_workflow.send_authorised_request(silent_case.id)
        silent_result = silent_workflow.simulate_response(
            SimulateCarrierResponseCommand(
                case_id=silent_case.id,
                effective_at="2026-08-22T08:30:00Z",
            )
        )
        silent_history = silent_workflow.history(silent_case.id)
        assert_verified(
            silent_result.no_response_emitted and not silent_history.carrier_responses,
            "carrier_silence_timeout_and_runtime_scope",
            "SILENT-RUN persisted a CarrierResponse",
        )
        assert_verified(
            silent_history.case.connection_id == silent_connection.id
            and silent_history.request is not None
            and silent_history.request.connection_id == silent_connection.id,
            "carrier_silence_timeout_and_runtime_scope",
            "silent carrier workflow did not exercise the snapshotted fixture connection",
        )
        configuration = CanonicalAgentRuntimeConfiguration.load()
        registry_before = AgentToolRegistry(clock=configuration.clock("before_deadline"))
        registry_after = AgentToolRegistry(clock=configuration.clock("after_deadline"))
        inventory_run = AgentRuntimeCoordinator(
            session=session,
            model=FakeAgentModel(()),
            clock=configuration.clock("before_deadline"),
            configuration=configuration,
        ).create_run(silent_phase2.incident.id)
        captured_tools = {
            tool.name
            for registry in (registry_before, registry_after)
            for tool in registry.available_tools(
                session,
                inventory_run.model_copy(update={"state": AgentRunState.RUNNING}),
            )
        }
        terminal = silent_workflow.evaluate_timeout(
            EvaluateTimeoutCommand(
                case_id=silent_case.id,
                effective_at="2026-08-22T09:00:00Z",
            )
        )
        assert_verified(
            terminal.state.value in {"COMPLETED", "ESCALATED"},
            "carrier_silence_timeout_and_runtime_scope",
            "due silent carrier timeout did not reach a terminal carrier state",
        )
        silent_connection_after = silent_connection.model_dump(mode="json")
        assert_verified(
            silent_connection_after == silent_connection_before,
            "carrier_silence_timeout_and_runtime_scope",
            "carrier fixture connection changed during evaluation",
        )

        assert_verified(
            captured_tools.isdisjoint(_FORBIDDEN_TOOLS),
            "carrier_silence_timeout_and_runtime_scope",
            "runtime registry exposed forbidden operational authority",
        )
        assert_verified(
            captured_tools.isdisjoint(_AGENT_APPROVAL_AUTHORITY_TOOLS),
            "carrier_silence_timeout_and_runtime_scope",
            "runtime registry exposed agent approval authority",
        )

        return (
            {
                "unapproved_send_exception": unapproved_exception,
                "unapproved_send_history_unchanged": True,
                "wrong_request_fingerprint_exception": wrong_request_exception,
                "approval_count_after_wrong_fingerprint": len(wrong_request_history.approvals),
            },
            {
                "counter_response_count": len(counter_history.carrier_responses),
                "effective_timing_count_before_approval": len(counter_history.effective_timings),
                "wrong_counter_fingerprint_exception": wrong_counter_exception,
                "effective_timing_count_after_wrong_fingerprint": len(
                    wrong_counter_history.effective_timings
                ),
            },
            {
                "silent_carrier_response_count": len(silent_history.carrier_responses),
                "timeout_terminal_state": terminal.state.value,
                "fixture_connection_unchanged": silent_connection_after
                == silent_connection_before,
                "forbidden_runtime_tools": sorted(captured_tools & _FORBIDDEN_TOOLS),
                "agent_approval_authority_tools": sorted(
                    captured_tools & _AGENT_APPROVAL_AUTHORITY_TOOLS
                ),
            },
        )


def collect_authority_claims(session: Session) -> tuple[EvidenceClaim, ...]:
    """Evaluate carrier authority only in an isolated deterministic backend store."""
    del session
    request_probe, counter_probe, silence_probe = _authority_probe()
    reference = EvidenceReference(
        record_type="CarrierRecoveryHistory",
        stable_key="authority-boundaries:SYN-CANONICAL-24-V1",
        source="CarrierRecoveryWorkflow and AgentToolRegistry",
    )
    reproducibility = ClaimReproducibility(
        deterministic=True,
        included_in_fingerprint=True,
        fixture_ids=(_FIXTURE_ID,),
    )
    shared = {
        "status": ClaimStatus.VERIFIED,
        "evidence_refs": (reference,),
        "caveat": "Synthetic carrier plans and isolated backend state only.",
        "reproducibility": reproducibility,
    }
    return (
        EvidenceClaim(
            claim_id="carrier_request_authority_boundary",
            statement="Carrier dispatch requires an exact approved request binding.",
            observed_value=request_probe,
            **shared,
        ),
        EvidenceClaim(
            claim_id="carrier_counter_authority_boundary",
            statement="Counter timing cannot take effect without exact counter approval.",
            observed_value=counter_probe,
            **shared,
        ),
        EvidenceClaim(
            claim_id="carrier_silence_timeout_and_runtime_scope",
            statement="Silent carrier handling terminates deterministically without forbidden runtime authority.",
            observed_value=silence_probe,
            **shared,
        ),
    )


def _human_review_fixture(session: Session):
    incident = Incident(
        id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        source_event_id="SYN-EVT-HUMAN-TRADEOFF",
        state=IncidentState.RESOLVED,
        created_at=datetime(2026, 8, 22, 5, tzinfo=UTC),
    )
    IncidentRepository(session).create(incident)
    repository = DynamicYardRepository(session)
    snapshot_id = uuid4()
    revision = repository.add_revision(
        AllocationRevision(
            incident_id=incident.id,
            source_phase2_evaluation_id=uuid4(),
            source_forecast_snapshot_id=snapshot_id,
            allocated_container_ids=("SYN-CNT-002", "SYN-CNT-004", "SYN-CNT-005"),
            locked_container_ids=("SYN-CNT-002", "SYN-CNT-004"),
            preserved_connection_total=601,
            expected_preserved_connections=12.02,
            reason="deterministic tradeoff baseline",
        )
    )
    for container_id in revision.allocated_container_ids:
        commitment = repository.add_commitment(
            ExpediteCommitment(
                incident_id=incident.id,
                origin_revision_id=revision.id,
                container_id=container_id,
            )
        )
        if container_id in revision.locked_container_ids:
            repository.transition_commitment(
                commitment.id, ExpediteCommitmentStatus.COMMITTED
            )
    repository.add_assessment(
        ExpediteReconsiderationAssessment(
            incident_id=incident.id,
            source_snapshot_id=snapshot_id,
            prior_allocation_revision_id=revision.id,
            locked_container_ids=revision.locked_container_ids,
            candidate_options=(
                ReconsiderationCandidate(
                    allocated_container_ids=(
                        "SYN-CNT-001",
                        "SYN-CNT-002",
                        "SYN-CNT-004",
                    ),
                    preserved_connection_total=602,
                    expected_preserved_connections=12.04,
                ),
            ),
            preserved_connection_total_before=601,
            preserved_connection_total_after=602,
            expected_preserved_connections_before=12.02,
            expected_preserved_connections_after=12.04,
            disposition=ReconsiderationDisposition.HUMAN_REVIEW_REQUIRED,
            reason="deterministic exact operator selection required",
        )
    )
    return incident, revision


def _tradeoff_persisted_state_fingerprint(history, audit_events) -> str:
    payload = {
        "selections": [item.model_dump(mode="json") for item in history.selections],
        "revisions": [item.model_dump(mode="json") for item in history.revisions],
        "commitments": [item.model_dump(mode="json") for item in history.commitments],
        "audit_events": [item.model_dump(mode="json") for item in audit_events],
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _tradeoff_probe() -> dict[str, object]:
    with _isolated_session() as session:
        incident, baseline = _human_review_fixture(session)
        configuration = CanonicalAgentRuntimeConfiguration.load()
        model = FakeAgentModel(
            (
                AgentModelTurn(
                    tool_call=AgentToolCall(
                        name="request_expedite_feasibility", arguments={}
                    )
                ),
                AgentModelTurn(
                    tool_call=AgentToolCall(name="escalate_agent_run", arguments={})
                ),
            )
        )
        runtime = AgentRuntimeCoordinator(
            session=session,
            model=model,
            clock=configuration.clock("before_deadline"),
            configuration=configuration,
        )
        run = runtime.create_run(incident.id)
        waiting = runtime.advance(run.id)
        assert_verified(
            waiting.wait_kind is not None
            and waiting.wait_kind.value == "HUMAN_TRADEOFF_DECISION",
            "human_tradeoff_backend_authority_boundary",
            "HUMAN_REVIEW_REQUIRED did not create an agent human-tradeoff wait",
        )
        history = DynamicYardWorkflow.for_session(session).history(incident.id)
        review = history.reviews[0]
        option = history.options[0]
        assert_verified(
            review.state is TradeoffReviewState.OPEN,
            "human_tradeoff_backend_authority_boundary",
            "human tradeoff review was not OPEN before operator selection",
        )
        tool_names = {
            tool.name
            for tool in AgentToolRegistry(clock=configuration.clock("before_deadline")).available_tools(
                session, waiting
            )
        }
        assert_verified(
            model.calls == 1
            and "select_tradeoff_option" not in tool_names
            and tool_names.isdisjoint(_AGENT_APPROVAL_AUTHORITY_TOOLS),
            "human_tradeoff_backend_authority_boundary",
            "runtime did not reach the human wait through its public path or registry exposed human authority",
        )
        model_calls_at_human_wait = model.calls
        _assert_agent_wait_conflict(
            lambda: runtime.advance(waiting.id),
            "human_tradeoff_backend_authority_boundary",
            "unresolved human review resumed the public runtime",
        )
        model_calls_while_waiting = model.calls - model_calls_at_human_wait
        assert_verified(
            model_calls_while_waiting == 0,
            "human_tradeoff_backend_authority_boundary",
            "public runtime invoked the model while exact human selection was absent",
        )
        projector = project_canonical_replay_stage(session, incident.id)
        assert_verified(
            projector.stage is CanonicalReplayStage.TRADEOFF_DECISION_REQUIRED
            and projector.next_allowed_action
            is CanonicalReplayActionType.SELECT_TRADEOFF_OPTION
            and projector.auto_replay_may_execute is False
            and projector.requires_human_authority,
            "human_tradeoff_backend_authority_boundary",
            "backend projector did not preserve the exact human authority boundary",
        )
        audit_before = AuditRepository(session).list_for_incident(incident.id)
        history_before = DynamicYardWorkflow.for_session(session).history(incident.id)
        state_before = _tradeoff_persisted_state_fingerprint(
            history_before, audit_before
        )
        stale_exception = _assert_dynamic_conflict(
            lambda: DynamicYardWorkflow.for_session(session).select_tradeoff(
                review.id,
                selected_option_id=option.id,
                expected_options_fingerprint="0" * 64,
                operator_id="evidence-operator",
            ),
            "human_tradeoff_backend_authority_boundary",
            "stale expected-options fingerprint was accepted",
        )
        history_after_stale = DynamicYardWorkflow.for_session(session).history(incident.id)
        audit_after_stale = AuditRepository(session).list_for_incident(incident.id)
        state_after = _tradeoff_persisted_state_fingerprint(
            history_after_stale, audit_after_stale
        )
        stale_unchanged = state_after == state_before
        assert_verified(
            stale_unchanged,
            "human_tradeoff_backend_authority_boundary",
            "stale tradeoff selection mutated selection, revision, commitment, or audit state",
        )
        DynamicYardWorkflow.for_session(session).select_tradeoff(
            review.id,
            selected_option_id=option.id,
            expected_options_fingerprint=review.options_fingerprint,
            operator_id="evidence-operator",
        )
        resumed = runtime.advance(waiting.id)
        assert_verified(
            model.calls == model_calls_at_human_wait + 1
            and resumed.state is AgentRunState.ESCALATED,
            "human_tradeoff_backend_authority_boundary",
            "public runtime did not resume only after exact human selection",
        )
        resolved = DynamicYardWorkflow.for_session(session).history(incident.id)
        committed = sorted(
            item.container_id
            for item in resolved.commitments
            if item.status is ExpediteCommitmentStatus.COMMITTED
        )
        child = resolved.revisions[-1]
        assert_verified(
            committed == ["SYN-CNT-002", "SYN-CNT-004"]
            and child.parent_revision_id == baseline.id
            and set(committed).issubset(child.allocated_container_ids),
            "human_tradeoff_backend_authority_boundary",
            "operator selection did not retain committed tradeoff slots",
        )
        return {
            "review_state_before_selection": review.state.value,
            "model_calls_to_reach_human_wait": model_calls_at_human_wait,
            "model_calls_while_waiting_before_selection": model_calls_while_waiting,
            "selection_tool_in_runtime_registry": "select_tradeoff_option" in tool_names,
            "agent_approval_authority_tools": sorted(
                tool_names & _AGENT_APPROVAL_AUTHORITY_TOOLS
            ),
            "stale_selection_exception": stale_exception,
            "stale_selection_persisted_state_unchanged": stale_unchanged,
            "committed_slots_retained": committed,
            "projector_stage": projector.stage.value,
            "projector_action": projector.next_allowed_action.value,
            "auto_replay_may_execute": projector.auto_replay_may_execute,
            "requires_human_authority": projector.requires_human_authority,
        }


def collect_tradeoff_claims(session: Session) -> tuple[EvidenceClaim, ...]:
    """Evaluate only backend tradeoff projection and persisted selection authority."""
    del session
    probe = _tradeoff_probe()
    return (
        EvidenceClaim(
            claim_id="human_tradeoff_backend_authority_boundary",
            statement="The backend requires an exact operator tradeoff selection before an agent may continue.",
            status=ClaimStatus.VERIFIED,
            observed_value=probe,
            evidence_refs=(
                EvidenceReference(
                    record_type="AllocationTradeoffHistory",
                    stable_key="human-tradeoff:SYN-CANONICAL-24-V1",
                    source="DynamicYardWorkflow, AgentToolRegistry, canonical replay projector",
                ),
            ),
            caveat="This proves backend projector and persisted workflow behavior only; it does not execute any frontend controller.",
            reproducibility=ClaimReproducibility(
                deterministic=True,
                included_in_fingerprint=True,
                fixture_ids=(_FIXTURE_ID,),
            ),
        ),
    )
