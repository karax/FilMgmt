from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text

from app.db.base import Base
from app.db.config import DEFAULT_DATABASE_URL, get_database_url
from app.db.session import create_database_engine, create_session_factory, engine
from app.models import Manufacturer, Material, PrintJob, PrintJobSpool, PrintSpoolLock, Spool, WeightHistory

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture
def test_engine() -> Iterator[Engine]:
    isolated_engine = create_database_engine(TEST_DATABASE_URL)
    try:
        yield isolated_engine
    finally:
        isolated_engine.dispose()


def test_engine_uses_isolated_sqlite_database(test_engine: Engine) -> None:
    assert test_engine.url.get_backend_name() == "sqlite"
    assert test_engine.url.database == ":memory:"
    assert test_engine.url != engine.url


def test_declarative_base_contains_registered_domain_tables() -> None:
    assert set(Base.metadata.tables) == {
        Manufacturer.__tablename__,
        Material.__tablename__,
            PrintJob.__tablename__,
            PrintJobSpool.__tablename__,
            PrintSpoolLock.__tablename__,
        Spool.__tablename__,
        WeightHistory.__tablename__,
    }


def test_database_connection(test_engine: Engine) -> None:
    with test_engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar_one()

    assert result == 1


def test_sqlite_foreign_keys_are_enabled_centrally(test_engine: Engine) -> None:
    with test_engine.connect() as connection:
        enabled = connection.execute(text("PRAGMA foreign_keys")).scalar_one()

    assert enabled == 1


def test_session_can_be_opened_and_closed(test_engine: Engine) -> None:
    session_factory = create_session_factory(test_engine)

    with session_factory() as session:
        result = session.execute(text("SELECT 1")).scalar_one()

    assert result == 1


def test_database_url_uses_default_when_environment_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_database_url() == DEFAULT_DATABASE_URL


def test_database_url_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    custom_url = "sqlite+pysqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", custom_url)

    assert get_database_url() == custom_url
