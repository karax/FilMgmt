import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIRECTORY = PROJECT_ROOT / "data"
DEFAULT_DATABASE_PATH = DATA_DIRECTORY / "filament.db"
DEFAULT_DATABASE_URL = f"sqlite+pysqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"


def get_database_url() -> str:
    """Return the configured database URL or the local SQLite default."""
    return os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


DATABASE_URL = get_database_url()

