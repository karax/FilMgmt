import argparse
import os
from pathlib import Path

from app.operations.database import (
    DEFAULT_BACKUP_DIRECTORY,
    OperationsError,
    database_path_from_url,
    repository_alembic_head,
    restore_backup,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and atomically restore a SQLite backup."
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument(
        "--target",
        type=Path,
        help="SQLite target path (defaults to DATABASE_URL).",
    )
    parser.add_argument(
        "--safety-backup-directory",
        type=Path,
        default=Path(os.getenv("FCC_BACKUP_DIRECTORY", DEFAULT_BACKUP_DIRECTORY)),
        help="Directory for the pre-restore backup of an existing target.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Explicitly authorize replacement when the target exists.",
    )
    parser.add_argument(
        "--confirm-backend-stopped",
        action="store_true",
        help="Confirm filament-command-center.service is stopped.",
    )
    parser.add_argument(
        "--allow-schema-mismatch",
        action="store_true",
        help="Expert recovery only: skip checkout Alembic-head compatibility check.",
    )
    args = parser.parse_args(argv)
    try:
        result = restore_backup(
            args.backup,
            args.target or database_path_from_url(),
            replace=args.replace,
            backend_confirmed_stopped=args.confirm_backend_stopped,
            safety_backup_directory=args.safety_backup_directory,
            expected_alembic_revision=(
                None if args.allow_schema_mismatch else repository_alembic_head()
            ),
        )
    except OperationsError as error:
        print(f"Restore: FAILED\n{error}")
        return 1

    print(f"Restore: OK ({result.restored_path})")
    if result.safety_backup:
        print(f"Pre-restore safety backup: {result.safety_backup}")
    print(f"integrity_check: {result.verification.integrity_check}")
    print(
        "foreign_key_check: "
        f"{result.verification.foreign_key_violations} violations"
    )
    print("Backend remains stopped; start it and run the health command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
