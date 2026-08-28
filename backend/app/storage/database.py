import os
from collections.abc import Iterator

from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, SQLModel, create_engine


DATABASE_URL_DEFAULT: str = "sqlite:///./backend/transshipment.db"


def database_url() -> str:
    return os.getenv("DATABASE_URL", DATABASE_URL_DEFAULT)


def build_engine(url: str) -> Engine:
    if make_url(url).get_backend_name() == "sqlite":
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)


engine = build_engine(database_url())


def create_db_and_tables(database_engine: Engine = engine) -> None:
    SQLModel.metadata.create_all(database_engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
