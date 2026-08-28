from types import SimpleNamespace


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
