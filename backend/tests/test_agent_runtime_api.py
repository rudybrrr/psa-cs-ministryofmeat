from backend.app.storage.agent_runtime import AgentRuntimeRepository


def test_agent_api_rejects_authority_body_and_unknown_run(api_engine, incident) -> None:
    from fastapi.testclient import TestClient
    from sqlmodel import Session

    from backend.app.main import create_app
    from backend.app.storage.database import create_db_and_tables, get_session
    from backend.app.storage.repositories import IncidentRepository

    create_db_and_tables(api_engine)
    with Session(api_engine) as session:
        IncidentRepository(session).create(incident)
    app = create_app(database_engine=api_engine)
    def override():
        with Session(api_engine) as session:
            yield session
    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        assert client.post(f"/incidents/{incident.id}/agent-runs", json={"model": "unsafe"}).status_code == 422
        assert client.post("/agent-runs/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/advance").status_code == 404
        schema = client.get("/openapi.json").json()
    assert "requestBody" not in schema["paths"]["/incidents/{incident_id}/agent-runs"]["post"]
    assert "requestBody" not in schema["paths"]["/agent-runs/{run_id}/advance"]["post"]
