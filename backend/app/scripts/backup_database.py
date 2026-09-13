import argparse
import os
from pathlib import Path

from app.operations.database import (
    DEFAULT_BACKUP_DIRECTORY,
    OperationsError,
    create_backup,
    database_path_from_url,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create and verify an online SQLite backup."
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="SQLite source path (defaults to DATABASE_URL).",
    )
    parser.add_argument(
        "--backup-directory",
        type=Path,
        default=Path(os.getenv("FCC_BACKUP_DIRECTORY", DEFAULT_BACKUP_DIRECTORY)),
    )
    args = parser.parse_args(argv)
    try:
        result = create_backup(
            args.database or database_path_from_url(),
            args.backup_directory,
        )
    except OperationsError as error:
        print(f"Backup: FAILED\n{error}")
        return 1

    verification = result.verification
    print(f"Backup: OK ({result.database_path})")
    print(f"Manifest: OK ({result.manifest_path})")
    print(f"integrity_check: {verification.integrity_check}")
    print(f"foreign_key_check: {verification.foreign_key_violations} violations")
    print(f"SHA-256: {verification.sha256}")
    print(f"Alembic revision: {verification.alembic_revision or 'not present'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

