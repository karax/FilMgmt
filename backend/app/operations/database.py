from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from app.db.config import get_database_url

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BACKUP_DIRECTORY = PROJECT_ROOT / "backups"
SQLITE_HEADER = b"SQLite format 3\x00"


class OperationsError(RuntimeError):
    """An expected, operator-actionable maintenance failure."""


@dataclass(frozen=True)
class DatabaseVerification:
    path: Path
    size_bytes: int
    sha256: str
    integrity_check: str
    foreign_key_violations: int
    alembic_revision: str | None


@dataclass(frozen=True)
class BackupResult:
    database_path: Path
    manifest_path: Path
    verification: DatabaseVerification


@dataclass(frozen=True)
class RestoreResult:
    restored_path: Path
    safety_backup: Path | None
    verification: DatabaseVerification


def database_path_from_url(database_url: str | None = None) -> Path:
    url = make_url(database_url or get_database_url())
    if url.get_backend_name() != "sqlite" or not url.database:
        raise OperationsError("Operations commands currently support file-backed SQLite only.")
    if url.database == ":memory:":
        raise OperationsError("An in-memory SQLite database cannot be backed up or restored.")
    return Path(url.database).expanduser().resolve()


def repository_alembic_head() -> str:
    config = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if not head:
        raise OperationsError("Could not determine the repository Alembic head revision.")
    return head


def verify_sqlite_database(
    path: Path,
    *,
    manifest_path: Path | None = None,
    expected_alembic_revision: str | None = None,
) -> DatabaseVerification:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise OperationsError(f"SQLite database does not exist: {path}")
    with path.open("rb") as database_file:
        if database_file.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            raise OperationsError(f"Not a SQLite database: {path}")

    sha256 = _sha256(path)
    manifest = _load_manifest(manifest_path or manifest_path_for(path))
    if manifest is not None:
        if manifest.get("database_filename") != path.name:
            raise OperationsError("Backup manifest names a different database file.")
        if manifest.get("sha256") != sha256:
            raise OperationsError("Backup checksum does not match its manifest.")
        if manifest.get("database_size_bytes") != path.stat().st_size:
            raise OperationsError("Backup size does not match its manifest.")

    try:
        connection = sqlite3.connect(_readonly_uri(path), uri=True, timeout=10)
        try:
            integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
            foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
            alembic_revision = _read_alembic_revision(connection)
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise OperationsError(f"SQLite verification failed: {error}") from error

    integrity = "; ".join(str(row[0]) for row in integrity_rows)
    if integrity.lower() != "ok":
        raise OperationsError(f"SQLite integrity_check failed: {integrity}")
    if foreign_key_rows:
        raise OperationsError(
            f"SQLite foreign_key_check found {len(foreign_key_rows)} violation(s)."
        )
    if manifest is not None and manifest.get("alembic_revision") != alembic_revision:
        raise OperationsError("Backup Alembic revision does not match its manifest.")
    if expected_alembic_revision and alembic_revision != expected_alembic_revision:
        actual = alembic_revision or "missing"
        raise OperationsError(
            "Backup schema is incompatible with this checkout: "
            f"expected {expected_alembic_revision}, found {actual}."
        )

    return DatabaseVerification(
        path=path,
        size_bytes=path.stat().st_size,
        sha256=sha256,
        integrity_check="ok",
        foreign_key_violations=0,
        alembic_revision=alembic_revision,
    )


def create_backup(
    source_path: Path,
    backup_directory: Path = DEFAULT_BACKUP_DIRECTORY,
    *,
    created_at: datetime | None = None,
    filename_prefix: str = "filament-command-center",
) -> BackupResult:
    source_path = source_path.expanduser().resolve()
    if not source_path.is_file():
        raise OperationsError(f"Source database does not exist: {source_path}")

    timestamp = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    timestamp_text = timestamp.strftime("%Y-%m-%dT%H%M%SZ")
    backup_directory = backup_directory.expanduser().resolve()
    backup_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(backup_directory, 0o700)
    destination = backup_directory / f"{filename_prefix}-{timestamp_text}.sqlite"
    manifest = manifest_path_for(destination)
    if destination.exists() or manifest.exists():
        raise OperationsError(f"Backup destination already exists: {destination}")

    temporary = backup_directory / f".{destination.name}.{os.getpid()}.part"
    temporary_manifest = manifest.with_name(f".{manifest.name}.{os.getpid()}.part")
    published = False
    try:
        source = sqlite3.connect(_readonly_uri(source_path), uri=True, timeout=30)
        target = sqlite3.connect(temporary)
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
            source.close()
        os.chmod(temporary, 0o600)
        verification = verify_sqlite_database(temporary)
        os.replace(temporary, destination)

        payload = {
            "format_version": 1,
            "created_at": timestamp.isoformat().replace("+00:00", "Z"),
            "database_filename": destination.name,
            "database_size_bytes": destination.stat().st_size,
            "sha256": verification.sha256,
            "git_revision": _git_revision(),
            "alembic_revision": verification.alembic_revision,
            "integrity_check": verification.integrity_check,
            "foreign_key_violations": verification.foreign_key_violations,
        }
        temporary_manifest.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary_manifest, 0o600)
        os.replace(temporary_manifest, manifest)
        final_verification = verify_sqlite_database(destination, manifest_path=manifest)
        published = True
        return BackupResult(destination, manifest, final_verification)
    except (OSError, sqlite3.DatabaseError) as error:
        raise OperationsError(f"Could not create verified SQLite backup: {error}") from error
    finally:
        temporary.unlink(missing_ok=True)
        temporary_manifest.unlink(missing_ok=True)
        if not published:
            destination.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)


def restore_backup(
    backup_path: Path,
    target_path: Path,
    *,
    replace: bool,
    backend_confirmed_stopped: bool,
    safety_backup_directory: Path | None = None,
    expected_alembic_revision: str | None = None,
) -> RestoreResult:
    backup_path = backup_path.expanduser().resolve()
    target_path = target_path.expanduser().resolve()
    if not backend_confirmed_stopped:
        raise OperationsError(
            "Restore refused: stop the backend and pass explicit stopped-service confirmation."
        )
    if backup_path == target_path:
        raise OperationsError("Restore source and target must be different files.")
    if target_path.exists() and not replace:
        raise OperationsError(
            "Restore refused: target exists; explicit replacement confirmation is required."
        )

    verify_sqlite_database(
        backup_path,
        expected_alembic_revision=expected_alembic_revision,
    )
    safety_backup: Path | None = None
    if target_path.exists():
        safety_directory = safety_backup_directory or target_path.parent / "backups"
        safety_backup = create_backup(
            target_path,
            safety_directory,
            filename_prefix="pre-restore",
        ).database_path

    target_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target_path.with_name(f".{target_path.name}.{os.getpid()}.restore")
    try:
        with backup_path.open("rb") as source, temporary.open("xb") as destination:
            shutil.copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        os.chmod(temporary, 0o600)
        verify_sqlite_database(
            temporary,
            expected_alembic_revision=expected_alembic_revision,
        )
        os.replace(temporary, target_path)
        _fsync_directory(target_path.parent)
        verification = verify_sqlite_database(
            target_path,
            expected_alembic_revision=expected_alembic_revision,
        )
        return RestoreResult(target_path, safety_backup, verification)
    except OSError as error:
        raise OperationsError(f"Could not restore SQLite backup: {error}") from error
    finally:
        temporary.unlink(missing_ok=True)


def manifest_path_for(database_path: Path) -> Path:
    return database_path.with_suffix(database_path.suffix + ".manifest.json")


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(path.as_posix(), safe='/')}?mode=ro"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OperationsError(f"Could not read backup manifest: {error}") from error
    if not isinstance(payload, dict):
        raise OperationsError("Backup manifest must contain a JSON object.")
    return payload


def _read_alembic_revision(connection: sqlite3.Connection) -> str | None:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
    ).fetchone()
    if table is None:
        return None
    row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return str(row[0]) if row else None


def _git_revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
