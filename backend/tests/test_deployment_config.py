from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.app.storage.repositories import IncidentRecord


def test_deployment_doc_names_required_runtime_contracts():
    text = Path("docs/deployment.md").read_text()
    for required in ("sqlite:////data/transshipment.db", "GET /healthz", "VITE_API_BASE_URL", "RUN_LIVE_LLM_TESTS=1", "US$5"):
        assert required in text


def test_dockerfile_is_python312_backend_only():
    text = Path("Dockerfile").read_text()
    assert "FROM python:3.12-slim" in text
    assert "RUN uv sync --frozen --no-dev --no-install-project" in text
    assert text.index("RUN uv sync --frozen --no-dev --no-install-project") < text.index("COPY backend ./backend")
    assert "backend.app.main:app" in text and "${PORT:?PORT is required}" in text
    assert "OPENAI_API_KEY" not in text and "VITE_API_BASE_URL" not in text


def test_dockerignore_keeps_runtime_sources_and_excludes_secrets():
    ignored = Path(".dockerignore").read_text().splitlines()
    assert ".env" in ignored and ".git" in ignored and "web" in ignored
    assert "backend" not in ignored and "shared" not in ignored


def test_database_url_defaults_to_existing_local_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from backend.app.storage.database import database_url

    assert database_url() == "sqlite:///./backend/transshipment.db"


def test_sqlite_only_connect_args(monkeypatch):
    import backend.app.storage.database as database

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_create_engine(url: str, **kwargs: object) -> object:
        calls.append((url, kwargs))
        return SimpleNamespace(url=SimpleNamespace(database="db"))

    monkeypatch.setattr(database, "create_engine", fake_create_engine)
    database.build_engine("sqlite:////data/transshipment.db")
    database.build_engine("postgresql://host/db")
    assert calls == [
        ("sqlite:////data/transshipment.db", {"connect_args": {"check_same_thread": False}}),
        ("postgresql://host/db", {}),
    ]


def test_cors_configured_origin_is_allowed_and_other_origin_is_not(monkeypatch, api_engine):
    from backend.app.main import create_app

    monkeypatch.setenv("ALLOWED_ORIGINS", "https://console.example.vercel.app")
    app = create_app(database_engine=api_engine)
    allowed = TestClient(app).options(
        "/healthz",
        headers={
            "Origin": "https://console.example.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    blocked = TestClient(app).options(
        "/healthz",
        headers={
            "Origin": "https://other.example.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "https://console.example.vercel.app"
    assert "access-control-allow-origin" not in blocked.headers


def test_parse_allowed_origins_rejects_unsafe_deployed_values():
    from backend.app.main import parse_allowed_origins

    for value in ("", " ", "*", "https://console.example.com,https://console.example.com", "http://console.example.com", "console.example.com"):
        with pytest.raises(ValueError):
            parse_allowed_origins(value)


@pytest.mark.parametrize(
    "value",
    (
        "https://EXAMPLE.com,https://example.com",
        "https://example.com,https://example.com:443",
    ),
)
def test_parse_allowed_origins_rejects_semantic_duplicates(value):
    from backend.app.main import parse_allowed_origins

    with pytest.raises(ValueError):
        parse_allowed_origins(value)


def test_parse_allowed_origins_keeps_port_zero_distinct_from_default_port():
    from backend.app.main import parse_allowed_origins

    assert parse_allowed_origins("https://example.com,https://example.com:0") == (
        "https://example.com",
        "https://example.com:0",
    )


def test_parse_allowed_origins_rejects_empty_explicit_port():
    from backend.app.main import parse_allowed_origins

    with pytest.raises(ValueError):
        parse_allowed_origins("https://example.com:")


def test_healthz_checks_database_without_creating_incident(api_engine):
    from backend.app.main import create_app

    with TestClient(create_app(database_engine=api_engine)) as client:
        assert client.get("/healthz").json() == {"status": "ok", "database": "ready"}
    assert Session(api_engine).exec(select(IncidentRecord)).all() == []


def test_healthz_hides_database_failure_details(monkeypatch, api_engine):
    import backend.app.main as main

    class FailingSession:
        def __init__(self, _):
            pass

        def __enter__(self):
            raise main.SQLAlchemyError("database password: secret")

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(main, "Session", FailingSession)
    with TestClient(main.create_app(database_engine=api_engine)) as client:
        response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    assert "secret" not in response.text
