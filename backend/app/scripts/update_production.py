import argparse
from pathlib import Path

from app.operations.database import (
    DEFAULT_BACKUP_DIRECTORY,
    OperationsError,
    create_backup,
    database_path_from_url,
)
from app.operations.update import (
    inspect_update_checkout,
    record_update_state,
    resolve_target_revision,
    run_checked,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Conservatively update a clean production checkout."
    )
    parser.add_argument("target", help="Explicit target branch, tag, or commit.")
    parser.add_argument(
        "--repository",
        type=Path,
        default=PROJECT_ROOT,
        help="Production checkout (defaults to this checkout).",
    )
    parser.add_argument(
        "--backup-directory",
        type=Path,
        default=DEFAULT_BACKUP_DIRECTORY,
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate checkout safety and resolve a local target without changing state.",
    )
    args = parser.parse_args(argv)
    repository = args.repository.expanduser().resolve()

    try:
        preflight = inspect_update_checkout(repository)
        print(f"Previous revision: {preflight.previous_revision}")
        print(f"Free space: {preflight.free_bytes} bytes")
        if args.preflight_only:
            target_revision = resolve_target_revision(repository, args.target)
            print(f"Target revision: {target_revision}")
            print("Preflight: OK (no changes made)")
            return 0

        backend_python = repository / "backend" / ".venv" / "bin" / "python"
        npm_directory = repository / "frontend"
        run_checked(
            repository,
            [str(backend_python), "-m", "app.scripts.check_health"],
        )
        backup = create_backup(database_path_from_url(), args.backup_directory)
        print(f"Verified pre-update backup: {backup.database_path}")

        run_checked(repository, ["git", "fetch", "--all", "--tags", "--prune"])
        target_revision = resolve_target_revision(repository, args.target)
        state_path = record_update_state(
            args.backup_directory,
            previous_revision=preflight.previous_revision,
            target_revision=target_revision,
            backup=backup,
        )
        print(f"Target revision: {target_revision}")
        print(f"Update recovery record: {state_path}")

        run_checked(repository, ["git", "merge", "--ff-only", target_revision])
        run_checked(
            repository / "backend",
            [str(backend_python), "-m", "pip", "install", "-r", "requirements.txt"],
        )
        run_checked(npm_directory, ["npm", "ci"])
        run_checked(npm_directory, ["npm", "run", "build"])
        run_checked(
            repository / "backend",
            [str(repository / "backend" / ".venv" / "bin" / "alembic"), "upgrade", "head"],
        )
        run_checked(
            repository,
            ["systemctl", "--user", "restart", "filament-command-center.service"],
        )
        run_checked(
            repository,
            ["systemctl", "--user", "restart", "filament-command-center-web.service"],
        )
        run_checked(
            repository,
            [str(backend_python), "-m", "app.scripts.check_health"],
        )
    except OperationsError as error:
        print(f"Update: FAILED\n{error}")
        print("No automatic rollback was attempted. Follow the production runbook.")
        return 1

    print("Update: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
