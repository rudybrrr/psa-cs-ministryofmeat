from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.app.domain.enums import IncidentState
from backend.app.domain.models import Incident


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(test_engine) -> Iterator[Session]:
    with Session(test_engine) as database_session:
        yield database_session


@pytest.fixture
def api_engine() -> Iterator[Engine]:
    database_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield database_engine
    database_engine.dispose()


@pytest.fixture
def client(api_engine: Engine) -> Iterator[TestClient]:
    from backend.app.main import create_app
    from backend.app.storage.database import get_session

    application = create_app(database_engine=api_engine)

    def override_get_session() -> Iterator[Session]:
        with Session(api_engine) as database_session:
            yield database_session

    application.dependency_overrides[get_session] = override_get_session
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


@pytest.fixture
def incident() -> Incident:
    return Incident(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        source_event_id="SYN-EVT-PERSIST-001",
        state=IncidentState.INCIDENT_RECEIVED,
        created_at=datetime(2026, 8, 21, 5, 0, tzinfo=UTC),
    )
