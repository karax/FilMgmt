from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.config import DATABASE_URL


def create_database_engine(database_url: str) -> Engine:
    """Create an engine with connection options appropriate for its backend."""
    url = make_url(database_url)
    connect_args: dict[str, bool] = {}

    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        if url.database and url.database != ":memory:":
            Path(url.database).expanduser().resolve().parent.mkdir(
                parents=True,
                exist_ok=True,
            )

    database_engine = create_engine(database_url, connect_args=connect_args)

    if url.get_backend_name() == "sqlite":
        event.listen(database_engine, "connect", _enable_sqlite_foreign_keys)

    return database_engine


def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
    """Enable SQLite foreign-key enforcement for every new connection."""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_session_factory(bind: Engine) -> sessionmaker[Session]:
    """Create a configured SQLAlchemy session factory."""
    return sessionmaker(bind=bind, autoflush=False, expire_on_commit=False)


engine = create_database_engine(DATABASE_URL)
SessionLocal = create_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
