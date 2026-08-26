from __future__ import annotations

from sqlmodel import select

from backend.app.domain.agent_runtime import AgentToolInvocationStatus
from backend.app.domain.evidence import ClaimStatus
from backend.app.orchestration.agent_runtime import (
    AgentRuntimeCoordinator,
    CanonicalAgentRuntimeConfiguration,
)
from backend.app.orchestration.dynamic_yard import DynamicYardWorkflow
from backend.app.orchestration.scarce_capacity import (
    build_scarce_capacity_workflow,
)
from backend.app.services.agent_model import FakeAgentModel
from backend.app.services.dynamic_yard import CanonicalDynamicYardHarness
from backend.app.storage.carrier_recovery import (
    CarrierRecoveryRepository,
    RTARequestRecord,
)
from backend.app.storage.dynamic_yard import YardForecastSnapshotRecord


EXPECTED_CLAIM_IDS = {
    "dynamic_reconsideration_r0_r1",
    "dynamic_preserved_total_change",
    "dynamic_expected_preserved_change",
    "dynamic_committed_allocations_immutable",
    "dynamic_phase2_worlds_reconstructed",
    "dynamic_phase3_incompatible_plan_blocked",
    "dynamic_evidence_precedes_carrier_mutation",
}


def _request_count(session, incident_id) -> int:
    return len(
        tuple(
            session.exec(
                select(RTARequestRecord).where(
                    RTARequestRecord.incident_id == str(incident_id)
                )
            ).all()
        )
    )


def _runtime(session) -> AgentRuntimeCoordinator:
    configuration = CanonicalAgentRuntimeConfiguration.load()
    return AgentRuntimeCoordinator(
        session=session,
        model=FakeAgentModel([]),
        clock=configuration.clock("before_deadline"),
        configuration=configuration,
    )


def test_dynamic_collector_proves_exact_canonical_reconsideration(session) -> None:
    from backend.app.evaluation.evidence_dynamic_yard import (
        collect_dynamic_yard_claims,
    )

    result = collect_dynamic_yard_claims(session)
    claims = {claim.claim_id: claim for claim in result.claims}

    assert set(claims) == EXPECTED_CLAIM_IDS
    assert {claim.status for claim in claims.values()} == {ClaimStatus.VERIFIED}
    assert result.incident_id == result.history.revisions[0].incident_id
    assert result.phase2_report.incident_id == result.incident_id
    assert claims["dynamic_reconsideration_r0_r1"].observed_value == {
        "r0": [
            "SYN-CNT-002",
            "SYN-CNT-004",
            "SYN-CNT-005",
            "SYN-CNT-010",
            "SYN-CNT-011",
            "SYN-CNT-012",
            "SYN-CNT-014",
            "SYN-CNT-015",
        ],
        "r1": [
            "SYN-CNT-001",
            "SYN-CNT-002",
            "SYN-CNT-004",
            "SYN-CNT-010",
            "SYN-CNT-011",
            "SYN-CNT-012",
            "SYN-CNT-014",
            "SYN-CNT-015",
        ],
        "cancelled": ["SYN-CNT-005"],
        "planned": ["SYN-CNT-001"],
        "committed": ["SYN-CNT-002", "SYN-CNT-004"],
    }
    assert claims["dynamic_preserved_total_change"].observed_value == {
        "before": 601,
        "after": 602,
    }
    assert claims["dynamic_expected_preserved_change"].observed_value == {
        "before": 12.02,
        "after": 12.04,
    }


def test_phase3_incompatible_evidence_blocks_prepare_without_mutation(session) -> None:
    phase2 = build_scarce_capacity_workflow(session).run()
    incident_id = phase2.incident.id
    yard = DynamicYardWorkflow.for_session(session)
    harness = CanonicalDynamicYardHarness()
    yard.initialize(incident_id, harness.bootstrap_snapshot(incident_id))
    active = harness.discharge_active_snapshot(incident_id)
    yard.ingest(active)
    yard.apply_latest_assessment(incident_id)

    record = session.get(YardForecastSnapshotRecord, str(active.id))
    assert record is not None
    payload = dict(record.snapshot_json)
    forecasts = [dict(row) for row in payload["container_forecasts"]]
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
    payload["container_forecasts"] = forecasts
    record.snapshot_json = payload
    session.add(record)
    session.commit()

    assert not yard.phase3_compatible(incident_id, "SYN-CONN-JV2")
    carrier = CarrierRecoveryRepository(session)
    before_cases = tuple(carrier.list_cases(incident_id))
    before_requests = _request_count(session, incident_id)
    runtime = _runtime(session)
    run = runtime.create_run(incident_id)

    rejected = runtime._execute_turn(
        run,
        "prepare_rta_request",
        {"connection_id": "SYN-CONN-JV2"},
    )
    invocation = runtime._repository.history(run.id).tool_invocations[-1]

    assert invocation.status is AgentToolInvocationStatus.REJECTED
    assert invocation.error_kind == "ValueError"
    assert rejected.step_count == 1
    assert tuple(carrier.list_cases(incident_id)) == before_cases
    assert _request_count(session, incident_id) == before_requests


def test_unhandled_evidence_precedes_carrier_mutation(session) -> None:
    phase2 = build_scarce_capacity_workflow(session).run()
    incident_id = phase2.incident.id
    yard = DynamicYardWorkflow.for_session(session)
    harness = CanonicalDynamicYardHarness()
    yard.initialize(incident_id, harness.bootstrap_snapshot(incident_id))
    assessment = yard.ingest(harness.discharge_active_snapshot(incident_id))
    assert assessment is not None
    assert yard.latest_unhandled_assessment(incident_id) == assessment

    carrier = CarrierRecoveryRepository(session)
    before_cases = tuple(carrier.list_cases(incident_id))
    before_requests = _request_count(session, incident_id)
    runtime = _runtime(session)
    run = runtime.create_run(incident_id)

    rejected = runtime._execute_turn(
        run,
        "prepare_rta_request",
        {"connection_id": "SYN-CONN-JV2"},
    )
    invocation = runtime._repository.history(run.id).tool_invocations[-1]

    assert invocation.status is AgentToolInvocationStatus.REJECTED
    assert invocation.error_kind == "ValueError"
    assert invocation.result_summary == (
        "material dynamic-yard reconsideration must be handled before "
        "carrier mutation"
    )
    assert rejected.step_count == 1
    assert yard.latest_unhandled_assessment(incident_id) == assessment
    assert tuple(carrier.list_cases(incident_id)) == before_cases
    assert _request_count(session, incident_id) == before_requests
