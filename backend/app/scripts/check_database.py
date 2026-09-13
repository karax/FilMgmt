import argparse
from pathlib import Path

from app.operations.database import (
    OperationsError,
    database_path_from_url,
    verify_sqlite_database,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run SQLite integrity_check and foreign_key_check."
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="SQLite database path (defaults to DATABASE_URL).",
    )
    args = parser.parse_args(argv)
    try:
        result = verify_sqlite_database(args.database or database_path_from_url())
    except OperationsError as error:
        print(f"Database deep check: FAILED\n{error}")
        return 1
    print("Database deep check: OK")
    print(f"Database: {result.path}")
    print(f"integrity_check: {result.integrity_check}")
    print(f"foreign_key_check: {result.foreign_key_violations} violations")
    print(f"Alembic revision: {result.alembic_revision or 'not present'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

