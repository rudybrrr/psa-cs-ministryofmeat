from datetime import UTC, datetime
from uuid import UUID

import pytest

from backend.app.storage.agent_runtime import AgentRuntimeConflict, AgentRuntimeRepository


def make_run(incident_id: UUID):
    from backend.app.domain.agent_runtime import AgentRun

    return AgentRun(
        incident_id=incident_id,
        model_name="fake-agent",
        prompt_version="agent-runtime-v1",
        started_at=datetime(2026, 8, 23, tzinfo=UTC),
        updated_at=datetime(2026, 8, 23, tzinfo=UTC),
    )


def test_only_one_active_run_exists_per_incident(session, incident) -> None:
    repository = AgentRuntimeRepository(session)
    repository.create_run(make_run(incident.id))
    with pytest.raises(AgentRuntimeConflict, match="active"):
        repository.create_run(make_run(incident.id))


def test_pending_invocation_and_ordered_history_survive_reload(session, incident) -> None:
    from backend.app.domain.agent_runtime import AgentStep, AgentStepKind
    repository = AgentRuntimeRepository(session)
    run = repository.create_run(make_run(incident.id))
    step = repository.add_step(
        AgentStep(
            run_id=run.id,
            step_number=1,
            kind=AgentStepKind.TOOL_CALL,
            action_summary="Inspect incident.",
            model_name=run.model_name,
            prompt_version=run.prompt_version,
        )
    )
    invocation = repository.add_invocation_pending(
        run.id, step.id, "get_incident_context", {}
    )

    history = AgentRuntimeRepository(session).history(run.id)
    assert history.run == run
    assert history.steps == (step,)
    assert history.tool_invocations == (invocation,)
