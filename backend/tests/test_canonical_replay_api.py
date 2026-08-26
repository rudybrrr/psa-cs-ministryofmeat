from uuid import uuid4

from backend.app.domain.canonical_replay import CanonicalReplayActionType, CanonicalReplayStage, CanonicalReplayStatus
from backend.app.services.canonical_replay import CANONICAL_REPLAY_MODEL_NAME


def _create_incident(client) -> str:
    response = client.post("/synthetic/scenarios/canonical-scarcity")
    assert response.status_code == 201
    return response.json()["incident_id"]


def test_demo_run_creation_persists_canonical_model_binding(client, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    incident_id = _create_incident(client)
    response = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs")
    assert response.status_code == 201
    body = response.json()
    assert body["model_name"] == CANONICAL_REPLAY_MODEL_NAME
    fetched = client.get(f"/agent-runs/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["model_name"] == CANONICAL_REPLAY_MODEL_NAME


def test_demo_run_creation_unknown_incident_is_404(client) -> None:
    response = client.post(f"/synthetic/scenarios/{uuid4()}/canonical-replay/agent-runs")
    assert response.status_code == 404


def test_demo_run_creation_conflicts_with_active_run(client) -> None:
    incident_id = _create_incident(client)
    first = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs")
    assert first.status_code == 201
    second = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs")
    assert second.status_code == 409


def test_demo_run_creation_refuses_body(client) -> None:
    incident_id = _create_incident(client)
    response = client.post(
        f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs",
        json={"model": "override"},
    )
    assert response.status_code == 422


def test_stage_endpoint_projects_read_only_view(client) -> None:
    incident_id = _create_incident(client)
    response = client.get(f"/synthetic/scenarios/{incident_id}/canonical-replay/stage")
    assert response.status_code == 200
    view = response.json()
    assert view["stage"] == CanonicalReplayStage.READY_FOR_PRE_DISCHARGE.value
    assert view["ordinal"] == 2
    assert view["progress_label"] == "Stage 2 of 16"
    assert view["status"] == CanonicalReplayStatus.PENDING_ACTION.value
    assert view["next_allowed_action"] == CanonicalReplayActionType.BOOTSTRAP_PRE_DISCHARGE.value
    assert view["guided_can_execute"] is True
    assert view["auto_replay_may_execute"] is True
    assert view["requires_human_authority"] is False
    assert view["deviation_reason"] is None
    again = client.get(f"/synthetic/scenarios/{incident_id}/canonical-replay/stage")
    assert again.status_code == 200
    assert again.json() == view


def test_stage_endpoint_unknown_incident_is_404(client) -> None:
    response = client.get(f"/synthetic/scenarios/{uuid4()}/canonical-replay/stage")
    assert response.status_code == 404


def test_production_run_creation_remains_openai_bound_and_body_free(client, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    incident_id = _create_incident(client)
    created = client.post(f"/incidents/{incident_id}/agent-runs")
    assert created.status_code == 201
    assert created.json()["model_name"] != CANONICAL_REPLAY_MODEL_NAME
    refused = client.post(f"/incidents/{incident_id}/agent-runs", json={"model": "x"})
    assert refused.status_code == 422


def test_demo_run_advances_credential_free_through_canonical_model(client, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    incident_id = _create_incident(client)
    assert client.post(f"/synthetic/scenarios/{incident_id}/dynamic-yard/bootstrap").status_code == 201
    created = client.post(f"/synthetic/scenarios/{incident_id}/canonical-replay/agent-runs")
    assert created.status_code == 201
    advanced = client.post(f"/agent-runs/{created.json()['id']}/advance")
    assert advanced.status_code == 200
    run = advanced.json()
    assert run["state"] == "WAITING"
    assert run["wait_kind"] == "NEW_OPERATIONAL_EVIDENCE"
    history = client.get(f"/agent-runs/{run['id']}/history").json()
    assert [(invocation["tool_name"], invocation["arguments"]) for invocation in history["tool_invocations"]] == [
        ("pause_agent_run", {})
    ]
    assert all(step["model_name"] == CANONICAL_REPLAY_MODEL_NAME for step in history["steps"])
    stage = client.get(f"/synthetic/scenarios/{incident_id}/canonical-replay/stage").json()
    assert stage["stage"] == CanonicalReplayStage.WAITING_FOR_ACTIVE_EVIDENCE.value


def test_production_advance_without_credentials_still_escalates_model_unavailable(client, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    incident_id = _create_incident(client)
    created = client.post(f"/incidents/{incident_id}/agent-runs")
    run_id = created.json()["id"]
    advanced = client.post(f"/agent-runs/{run_id}/advance")
    assert advanced.status_code == 200
    assert advanced.json()["state"] == "ESCALATED"
    assert advanced.json()["escalation_reason"] == "MODEL_UNAVAILABLE"
