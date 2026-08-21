from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
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
def incident() -> Incident:
    return Incident(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        source_event_id="SYN-EVT-PERSIST-001",
        state=IncidentState.INCIDENT_RECEIVED,
        created_at=datetime(2026, 8, 21, 5, 0, tzinfo=UTC),
    )
