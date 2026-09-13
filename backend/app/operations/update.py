from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from app.operations.database import BackupResult, OperationsError


@dataclass(frozen=True)
class UpdatePreflight:
    previous_revision: str
    free_bytes: int


def inspect_update_checkout(repository: Path) -> UpdatePreflight:
    repository = repository.resolve()
    status = _capture(repository, ["git", "status", "--porcelain"])
    if status.strip():
        raise OperationsError(
            "Update refused: the working tree is dirty. Preserve or commit local changes; "
            "the updater will not reset them."
        )
    revision = _capture(repository, ["git", "rev-parse", "HEAD"]).strip()
    free_bytes = shutil.disk_usage(repository).free
    return UpdatePreflight(revision, free_bytes)


def resolve_target_revision(repository: Path, target: str) -> str:
    if not target.strip() or target.startswith("-"):
        raise OperationsError("An explicit branch, tag, or commit is required.")
    return _capture(
        repository.resolve(),
        ["git", "rev-parse", "--verify", f"{target}^{{commit}}"],
    ).strip()


def record_update_state(
    backup_directory: Path,
    *,
    previous_revision: str,
    target_revision: str,
    backup: BackupResult,
    created_at: datetime | None = None,
) -> Path:
    timestamp = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    backup_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = backup_directory / f"update-{timestamp.strftime('%Y-%m-%dT%H%M%SZ')}.json"
    if path.exists():
        raise OperationsError(f"Update record already exists: {path}")
    payload = {
        "created_at": timestamp.isoformat().replace("+00:00", "Z"),
        "previous_revision": previous_revision,
        "target_revision": target_revision,
        "verified_backup": str(backup.database_path),
        "backup_sha256": backup.verification.sha256,
        "alembic_revision": backup.verification.alembic_revision,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def run_checked(repository: Path, command: Sequence[str]) -> None:
    try:
        subprocess.run(list(command), cwd=repository, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise OperationsError(f"Command failed: {' '.join(command)}") from error


def _capture(repository: Path, command: Sequence[str]) -> str:
    try:
        return subprocess.run(
            list(command),
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise OperationsError(f"Command failed: {' '.join(command)}") from error

