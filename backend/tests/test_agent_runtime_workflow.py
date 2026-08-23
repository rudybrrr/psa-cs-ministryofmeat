from backend.app.storage.agent_runtime import AgentRuntimeRepository
from backend.app.storage.carrier_recovery import CarrierRecoveryRepository


def test_second_invalid_turn_escalates_invalid_model_output(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentEscalationReason, InvalidAgentModelTurn
    from backend.app.orchestration.agent_runtime import AgentRuntimeCoordinator, CanonicalAgentRuntimeConfiguration
    from backend.app.services.agent_model import FakeAgentModel
    from backend.app.storage.repositories import IncidentRepository

    IncidentRepository(session).create(incident)
    runtime = AgentRuntimeCoordinator(
        session=session,
        model=FakeAgentModel([
            InvalidAgentModelTurn(error_kind="MALFORMED", detail="bad"),
            InvalidAgentModelTurn(error_kind="MALFORMED", detail="bad"),
        ]),
        clock=CanonicalAgentRuntimeConfiguration.load().clock("before_deadline"),
        configuration=CanonicalAgentRuntimeConfiguration.load(),
    )
    run = runtime.create_run(incident.id)
    result = runtime.advance(run.id)
    assert result.escalation_reason is AgentEscalationReason.INVALID_MODEL_OUTPUT
