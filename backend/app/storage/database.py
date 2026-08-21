from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


DATABASE_URL = "sqlite:///./backend/transshipment.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def create_db_and_tables(database_engine: Engine = engine) -> None:
    SQLModel.metadata.create_all(database_engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
