from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.app.domain.cargo_safety import SemanticCheckResult
from backend.app.services.semantic_safety import FakeSemanticSafetyChecker
from backend.app.storage.repositories import IncidentRepository
from backend.app.storage.database import create_db_and_tables


def test_create_evaluate_list_get_and_history(api_engine, incident) -> None:
    from backend.app.main import create_app
    create_db_and_tables(api_engine)
    app = create_app(database_engine=api_engine, cargo_safety_checker=FakeSemanticSafetyChecker(result=SemanticCheckResult.CONTRADICTION_FOUND))
    from backend.app.storage.database import get_session
    def override_session():
        with Session(api_engine) as session: yield session
    app.dependency_overrides[get_session] = override_session
    with Session(api_engine) as session:
        IncidentRepository(session).create(incident)
    with TestClient(app) as client:
        created = client.post(f"/incidents/{incident.id}/cargo-safety-reviews", json={"container_id": "SYN-CNT-010", "note": {"text": "Shipment includes UN 3480 lithium-ion batteries packed separately.", "source": "hero"}})
        assert created.status_code == 201
        review_id = created.json()["id"]
        evaluated = client.post(f"/cargo-safety-reviews/{review_id}/evaluate")
        assert evaluated.status_code == 201
        assert evaluated.json()["policy_result"]["disposition"] == "ESCALATE"
        assert client.post(f"/cargo-safety-reviews/{review_id}/evaluate", json={"model": "unsafe-user-choice"}).status_code == 422
        assert client.get(f"/incidents/{incident.id}/cargo-safety-reviews").json()[0]["id"] == review_id
        assert client.get(f"/cargo-safety-reviews/{review_id}/history").json()["assessment"]["result"] == "CONTRADICTION_FOUND"


def test_invalid_container_is_422_and_unknown_review_is_404(api_engine, incident) -> None:
    from backend.app.main import create_app
    create_db_and_tables(api_engine)
    app = create_app(database_engine=api_engine)
    from backend.app.storage.database import get_session
    def override_session():
        with Session(api_engine) as session: yield session
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        with Session(api_engine) as session:
            IncidentRepository(session).create(incident)
        response = client.post(f"/incidents/{incident.id}/cargo-safety-reviews", json={"container_id": "SYN-CNT-999", "note": {"text": "x", "source": "test"}})
        assert response.status_code == 422
        assert client.get("/cargo-safety-reviews/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa").status_code == 404
