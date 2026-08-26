from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from uuid import UUID

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from backend.app.domain.agent_runtime import AgentToolInvocationStatus
from backend.app.domain.dynamic_yard import (
    AllocationTradeoffHistory,
    ExpediteCommitmentStatus,
)
from backend.app.domain.evidence import (
    ClaimReproducibility,
    ClaimStatus,
    EvidenceClaim,
    EvidenceReference,
    assert_verified,
)
from backend.app.domain.models import FrozenContract
from backend.app.domain.scarcity import ScarcityEvaluationReport
from backend.app.evaluation.dynamic_yard import reconstruct_phase2_worlds
from backend.app.evaluation.scarcity import comparison_reproducibility_key
from backend.app.orchestration.agent_runtime import (
    AgentRuntimeCoordinator,
    CanonicalAgentRuntimeConfiguration,
)
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.orchestration.scarce_capacity import (
    build_scarce_capacity_workflow,
)
from backend.app.services.canonical_incident import (
    SyntheticCanonicalIncidentService,
)
from backend.app.services.canonical_replay import CanonicalReplayAgentModel
from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
from backend.app.storage.carrier_recovery import (
    CarrierRecoveryRepository,
    RTARequestRecord,
)
from backend.app.storage.dynamic_yard import YardForecastSnapshotRecord


_FIXTURE_ID = "SYN-CANONICAL-24-V1"
_R0 = (
    "SYN-CNT-002",
    "SYN-CNT-004",
    "SYN-CNT-005",
    "SYN-CNT-010",
    "SYN-CNT-011",
    "SYN-CNT-012",
    "SYN-CNT-014",
    "SYN-CNT-015",
)
_R1 = (
    "SYN-CNT-001",
    "SYN-CNT-002",
    "SYN-CNT-004",
    "SYN-CNT-010",
    "SYN-CNT-011",
    "SYN-CNT-012",
    "SYN-CNT-014",
    "SYN-CNT-015",
)
_COMMITTED = ("SYN-CNT-002", "SYN-CNT-004")
_UNHANDLED_CARRIER_MUTATION_ERROR = (
    "material dynamic-yard reconsideration must be handled before carrier mutation"
)


class DynamicYardEvidenceResult(FrozenContract):
    incident_id: UUID
    phase2_report: ScarcityEvaluationReport
    history: AllocationTradeoffHistory
    claims: tuple[EvidenceClaim, ...]


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


def _request_count(session: Session, incident_id: UUID) -> int:
    return len(
        session.exec(
            select(RTARequestRecord).where(
                RTARequestRecord.incident_id == str(incident_id)
            )
        ).all()
    )


def _runtime(session: Session) -> AgentRuntimeCoordinator:
    configuration = CanonicalAgentRuntimeConfiguration.load()
    return AgentRuntimeCoordinator(
        session=session,
        model=CanonicalReplayAgentModel(),
        clock=configuration.clock("before_deadline"),
        configuration=configuration,
    )


def _phase3_incompatible_probe() -> dict[str, object]:
    scenario_key = "dynamic-phase3-forecast-mismatch-v1"
    with _isolated_session() as session:
        phase2 = build_scarce_capacity_workflow(session).run()
        incident_id = phase2.incident.id
        yard = DynamicYardWorkflow.for_session(session)
        harness = CanonicalDynamicYardHarness()
        yard.initialize(incident_id, harness.bootstrap_snapshot(incident_id))
        active = harness.discharge_active_snapshot(incident_id)
        yard.ingest(active)
        yard.apply_latest_assessment(incident_id)

        record = session.get(YardForecastSnapshotRecord, str(active.id))
        assert_verified(
            record is not None,
            "dynamic_phase3_incompatible_plan_blocked",
            "active forecast record is missing",
        )
        payload = deepcopy(record.snapshot_json)
        forecasts = payload["container_forecasts"]
        forecast = next(
            row for row in forecasts if row["container_id"] == "SYN-CNT-010"
        )
        forecast.update(
            {
                "p10_ready_at": "2026-08-22T05:46:00.753997Z",
                "p50_ready_at": "2026-08-22T06:04:00Z",
                "p90_ready_at": "2026-08-22T06:21:59.246003Z",
            }
        )
        record.snapshot_json = payload
        session.add(record)
        session.commit()

        compatible = yard.phase3_compatible(incident_id, "SYN-CONN-JV2")
        carrier = CarrierRecoveryRepository(session)
        cases_before = len(carrier.list_cases(incident_id))
        requests_before = _request_count(session, incident_id)
        runtime = _runtime(session)
        run = runtime.create_run(incident_id)
        rejected = runtime._execute_turn(
            run,
            "prepare_rta_request",
            {"connection_id": "SYN-CONN-JV2"},
        )
        invocation = runtime._repository.history(run.id).tool_invocations[-1]
        cases_after = len(carrier.list_cases(incident_id))
        requests_after = _request_count(session, incident_id)

        assert_verified(
            not compatible,
            "dynamic_phase3_incompatible_plan_blocked",
            "forecast mismatch remained Phase 3 compatible",
        )
        assert_verified(
            invocation.status is AgentToolInvocationStatus.REJECTED
            and invocation.error_kind == "ValueError"
            and rejected.step_count == 1,
            "dynamic_phase3_incompatible_plan_blocked",
            "prepare_rta_request was not rejected by the Phase 3 guard",
        )
        assert_verified(
            (cases_before, requests_before) == (cases_after, requests_after),
            "dynamic_phase3_incompatible_plan_blocked",
            "Phase 3 rejection mutated carrier state",
        )
        return {
            "scenario_key": scenario_key,
            "phase3_compatible": compatible,
            "exception_type": invocation.error_kind,
            "case_count_before": cases_before,
            "case_count_after": cases_after,
            "request_count_before": requests_before,
            "request_count_after": requests_after,
        }


def _unhandled_evidence_probe() -> dict[str, object]:
    scenario_key = "dynamic-unhandled-evidence-carrier-guard-v1"
    with _isolated_session() as session:
        phase2 = build_scarce_capacity_workflow(session).run()
        incident_id = phase2.incident.id
        yard = DynamicYardWorkflow.for_session(session)
        harness = CanonicalDynamicYardHarness()
        yard.initialize(incident_id, harness.bootstrap_snapshot(incident_id))
        assessment = yard.ingest(harness.discharge_active_snapshot(incident_id))
        assert_verified(
            assessment is not None
            and yard.latest_unhandled_assessment(incident_id) == assessment,
            "dynamic_evidence_precedes_carrier_mutation",
            "probe did not create unhandled dynamic-yard evidence",
        )

        carrier = CarrierRecoveryRepository(session)
        cases_before = len(carrier.list_cases(incident_id))
        requests_before = _request_count(session, incident_id)
        runtime = _runtime(session)
        run = runtime.create_run(incident_id)
        rejected = runtime._execute_turn(
            run,
            "prepare_rta_request",
            {"connection_id": "SYN-CONN-JV2"},
        )
        invocation = runtime._repository.history(run.id).tool_invocations[-1]
        cases_after = len(carrier.list_cases(incident_id))
        requests_after = _request_count(session, incident_id)
        unhandled_after = yard.latest_unhandled_assessment(incident_id)

        assert_verified(
            invocation.status is AgentToolInvocationStatus.REJECTED
            and invocation.error_kind == "ValueError"
            and invocation.result_summary == _UNHANDLED_CARRIER_MUTATION_ERROR
            and rejected.step_count == 1,
            "dynamic_evidence_precedes_carrier_mutation",
            (
                "material dynamic-yard reconsideration must be handled before "
                "carrier mutation"
            ),
        )
        assert_verified(
            unhandled_after is not None and unhandled_after.id == assessment.id,
            "dynamic_evidence_precedes_carrier_mutation",
            "carrier rejection changed the unhandled assessment",
        )
        assert_verified(
            (cases_before, requests_before) == (cases_after, requests_after),
            "dynamic_evidence_precedes_carrier_mutation",
            "unhandled-evidence rejection mutated carrier state",
        )
        return {
            "scenario_key": scenario_key,
            "unhandled_assessment": True,
            "exception_type": invocation.error_kind,
            "case_count_before": cases_before,
            "case_count_after": cases_after,
            "request_count_before": requests_before,
            "request_count_after": requests_after,
        }


def collect_dynamic_yard_claims(session: Session) -> DynamicYardEvidenceResult:
    phase2 = build_scarce_capacity_workflow(session).run()
    incident_id = phase2.incident.id
    yard = DynamicYardWorkflow.for_session(session)
    harness = CanonicalDynamicYardHarness()
    yard.initialize(incident_id, harness.bootstrap_snapshot(incident_id))
    assessment = yard.ingest(harness.discharge_active_snapshot(incident_id))
    assert_verified(
        assessment is not None,
        "dynamic_reconsideration_r0_r1",
        "active evidence produced no assessment",
    )
    yard.apply_latest_assessment(incident_id)
    history = yard.history(incident_id)

    fixture = SyntheticCanonicalIncidentService().load()
    worlds = reconstruct_phase2_worlds(phase2.report, fixture)
    reconstructed_key = comparison_reproducibility_key(
        fixture,
        worlds,
        phase2.report.baseline,
        phase2.report.scenario_aware_evaluations,
        phase2.report.pareto_evaluations,
        phase2.report.selected_allocation,
    )
    assert_verified(
        worlds.assumptions.seed == phase2.report.seed,
        "dynamic_phase2_worlds_reconstructed",
        "seed drift",
    )
    assert_verified(
        len(worlds.worlds) == phase2.report.scenario_count,
        "dynamic_phase2_worlds_reconstructed",
        "world-count drift",
    )
    assert_verified(
        reconstructed_key == phase2.report.reproducibility_key,
        "dynamic_phase2_worlds_reconstructed",
        "Phase 2 comparison key drift",
    )

    assert_verified(
        len(history.revisions) == 2 and len(history.assessments) == 1,
        "dynamic_reconsideration_r0_r1",
        "canonical history does not contain exactly R0, R1, and one assessment",
    )
    r0, r1 = history.revisions
    persisted_assessment = history.assessments[0]
    cancelled = tuple(
        sorted(
            item.container_id
            for item in history.commitments
            if item.status is ExpediteCommitmentStatus.CANCELLED
        )
    )
    replacement_planned = tuple(
        sorted(
            item.container_id
            for item in history.commitments
            if item.origin_revision_id == r1.id
            and item.status is ExpediteCommitmentStatus.PLANNED
        )
    )
    committed_commitments = tuple(
        item
        for item in history.commitments
        if item.status is ExpediteCommitmentStatus.COMMITTED
    )
    committed = tuple(
        sorted(item.container_id for item in committed_commitments)
    )

    assert_verified(
        r0.allocated_container_ids == _R0
        and r1.allocated_container_ids == _R1
        and cancelled == ("SYN-CNT-005",)
        and replacement_planned == ("SYN-CNT-001",)
        and committed == _COMMITTED,
        "dynamic_reconsideration_r0_r1",
        "canonical reconsideration facts drifted",
    )
    assert_verified(
        (
            persisted_assessment.preserved_connection_total_before,
            persisted_assessment.preserved_connection_total_after,
        )
        == (601, 602),
        "dynamic_preserved_total_change",
        "canonical preserved total change drifted",
    )
    assert_verified(
        (
            persisted_assessment.expected_preserved_connections_before,
            persisted_assessment.expected_preserved_connections_after,
        )
        == (12.02, 12.04),
        "dynamic_expected_preserved_change",
        "canonical expected-preserved change drifted",
    )
    assert_verified(
        r0.locked_container_ids == _COMMITTED
        and r1.locked_container_ids == _COMMITTED
        and all(container_id in r1.allocated_container_ids for container_id in _COMMITTED)
        and all(item.origin_revision_id == r0.id for item in committed_commitments),
        "dynamic_committed_allocations_immutable",
        "committed allocation membership or lineage drifted",
    )

    phase3_probe = _phase3_incompatible_probe()
    unhandled_probe = _unhandled_evidence_probe()
    assert_verified(
        yard.history(incident_id) == history,
        "dynamic_evidence_precedes_carrier_mutation",
        "isolated negative probes changed successful canonical state",
    )

    dynamic_reference = EvidenceReference(
        record_type="AllocationTradeoffHistory",
        stable_key=f"dynamic-yard:{_FIXTURE_ID}",
        source="DynamicYardRepository.history",
        record_id=str(incident_id),
    )
    phase2_reference = EvidenceReference(
        record_type="ScarcityEvaluationReport",
        stable_key=f"phase2:{_FIXTURE_ID}:{phase2.report.seed}",
        source="ScarcityEvaluationRepository",
        record_id=str(phase2.report.id),
    )
    reproducibility = ClaimReproducibility(
        deterministic=True,
        included_in_fingerprint=True,
        fixture_ids=(_FIXTURE_ID,),
        benchmark_reproducibility_key=phase2.report.reproducibility_key,
    )
    shared = {
        "status": ClaimStatus.VERIFIED,
        "evidence_refs": (dynamic_reference,),
        "caveat": "Synthetic canonical dynamic-yard scenarios only.",
        "reproducibility": reproducibility,
    }

    claims = (
        EvidenceClaim(
            claim_id="dynamic_reconsideration_r0_r1",
            statement="Canonical discharge evidence deterministically replaces 005 with 001.",
            observed_value={
                "r0": list(r0.allocated_container_ids),
                "r1": list(r1.allocated_container_ids),
                "cancelled": list(cancelled),
                "planned": list(replacement_planned),
                "committed": list(committed),
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="dynamic_preserved_total_change",
            statement="Canonical reconsideration changes preserved total from 601 to 602.",
            observed_value={
                "before": persisted_assessment.preserved_connection_total_before,
                "after": persisted_assessment.preserved_connection_total_after,
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="dynamic_expected_preserved_change",
            statement="Canonical reconsideration changes expected preserved connections from 12.02 to 12.04.",
            observed_value={
                "before": persisted_assessment.expected_preserved_connections_before,
                "after": persisted_assessment.expected_preserved_connections_after,
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="dynamic_committed_allocations_immutable",
            statement="Committed allocations 002 and 004 retain their commitment lineage in R1.",
            observed_value={
                "r0_locked": list(r0.locked_container_ids),
                "r1_locked": list(r1.locked_container_ids),
                "committed": list(committed),
                "commitment_origin": "R0",
            },
            **shared,
        ),
        EvidenceClaim(
            claim_id="dynamic_phase2_worlds_reconstructed",
            statement="Dynamic-yard evaluation reconstructs the persisted Phase 2 worlds and comparison key.",
            observed_value={
                "seed": worlds.assumptions.seed,
                "world_count": len(worlds.worlds),
                "comparison_key": reconstructed_key,
            },
            status=ClaimStatus.VERIFIED,
            evidence_refs=(phase2_reference,),
            caveat="Synthetic canonical Phase 2 fixture and seed only.",
            reproducibility=reproducibility,
        ),
        EvidenceClaim(
            claim_id="dynamic_phase3_incompatible_plan_blocked",
            statement="A forecast mismatch blocks Phase 3 carrier-request preparation before mutation.",
            observed_value=phase3_probe,
            **shared,
        ),
        EvidenceClaim(
            claim_id="dynamic_evidence_precedes_carrier_mutation",
            statement="Unhandled material dynamic-yard evidence blocks carrier mutation.",
            observed_value=unhandled_probe,
            **shared,
        ),
    )
    return DynamicYardEvidenceResult(
        incident_id=incident_id,
        phase2_report=phase2.report,
        history=history,
        claims=claims,
    )
