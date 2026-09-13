from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

import pytest
from alembic import command
from alembic.config import Config

from app.operations.database import (
    OperationsError,
    create_backup,
    repository_alembic_head,
    restore_backup,
    verify_sqlite_database,
)
from app.operations.health import run_health_checks
from app.operations.update import inspect_update_checkout, record_update_state
from app.scripts.check_health import main as health_main

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent


@pytest.fixture
def representative_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    database = tmp_path / "representative.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database}")
    command.upgrade(Config(str(BACKEND_ROOT / "alembic.ini")), "head")
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO manufacturers(id,name,created_at,updated_at) "
            "VALUES(1,'Ops Maker',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO materials(id,name,category,created_at,updated_at) "
            "VALUES(1,'OPS PLA','PLA',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO spools("
            "id,code,manufacturer_id,material_id,color_name,diameter_mm,"
            "initial_filament_weight_g,current_filament_weight_g,currency,status,"
            "needs_drying,created_at,updated_at) VALUES("
            "1,'FIL-OPS',1,1,'Blue',1.75,1000,750,'EUR','OPEN',0,"
            "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO weight_history(id,spool_id,weight_g,source,created_at) "
            "VALUES(1,1,750,'MANUAL',CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO print_jobs(id,name,status,created_at,updated_at) "
            "VALUES(1,'Restore drill print','PLANNED',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO print_job_spools("
            "id,print_job_id,spool_id,position,estimated_weight_g,created_at,updated_at) "
            "VALUES(1,1,1,0,25,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        connection.commit()
    finally:
        connection.close()
    return database


def test_backup_is_verified_and_contains_representative_data(
    representative_database: Path, tmp_path: Path
) -> None:
    result = create_backup(
        representative_database,
        tmp_path / "backups",
        created_at=datetime(2026, 9, 12, 21, 0, tzinfo=timezone.utc),
    )

    assert result.database_path.name == "filament-command-center-2026-09-12T210000Z.sqlite"
    assert result.verification.integrity_check == "ok"
    assert result.verification.foreign_key_violations == 0
    connection = sqlite3.connect(result.database_path)
    try:
        assert connection.execute("SELECT name FROM manufacturers").fetchone() == ("Ops Maker",)
        assert connection.execute("SELECT name FROM materials").fetchone() == ("OPS PLA",)
        assert connection.execute("SELECT code FROM spools").fetchone() == ("FIL-OPS",)
        assert connection.execute("SELECT weight_g FROM weight_history").fetchone() == (750,)
        assert connection.execute("SELECT name FROM print_jobs").fetchone() == (
            "Restore drill print",
        )
        assert connection.execute("SELECT estimated_weight_g FROM print_job_spools").fetchone() == (25,)
    finally:
        connection.close()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(result.database_path.read_bytes()).hexdigest()
    assert manifest["alembic_revision"] == repository_alembic_head()
    assert manifest["integrity_check"] == "ok"
    assert manifest["foreign_key_violations"] == 0


def test_online_backup_uses_sqlite_while_source_connection_remains_open(
    representative_database: Path, tmp_path: Path
) -> None:
    active_connection = sqlite3.connect(representative_database)
    try:
        active_connection.execute("SELECT 1").fetchone()
        result = create_backup(representative_database, tmp_path / "online")
    finally:
        active_connection.close()
    assert verify_sqlite_database(result.database_path).integrity_check == "ok"


def test_restore_preserves_records_and_creates_pre_restore_backup(
    representative_database: Path, tmp_path: Path
) -> None:
    source_backup = create_backup(representative_database, tmp_path / "source")
    target = tmp_path / "target.sqlite"
    target.write_bytes(representative_database.read_bytes())
    connection = sqlite3.connect(target)
    try:
        connection.execute("UPDATE manufacturers SET name='Changed after backup'")
        connection.commit()
    finally:
        connection.close()

    result = restore_backup(
        source_backup.database_path,
        target,
        replace=True,
        backend_confirmed_stopped=True,
        safety_backup_directory=tmp_path / "safety",
        expected_alembic_revision=repository_alembic_head(),
    )

    assert result.safety_backup is not None
    restored = sqlite3.connect(target)
    safety = sqlite3.connect(result.safety_backup)
    try:
        assert restored.execute("SELECT name FROM manufacturers").fetchone() == ("Ops Maker",)
        assert restored.execute("SELECT code FROM spools").fetchone() == ("FIL-OPS",)
        assert restored.execute("SELECT count(*) FROM weight_history").fetchone() == (1,)
        assert restored.execute("SELECT count(*) FROM print_jobs").fetchone() == (1,)
        assert restored.execute("SELECT count(*) FROM print_job_spools").fetchone() == (1,)
        assert safety.execute("SELECT name FROM manufacturers").fetchone() == (
            "Changed after backup",
        )
    finally:
        restored.close()
        safety.close()


def test_restore_rejects_corruption_checksum_mismatch_and_implicit_overwrite(
    representative_database: Path, tmp_path: Path
) -> None:
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"not sqlite")
    with pytest.raises(OperationsError, match="Not a SQLite"):
        restore_backup(
            corrupt,
            tmp_path / "unused.sqlite",
            replace=True,
            backend_confirmed_stopped=True,
        )

    backup = create_backup(representative_database, tmp_path / "backups")
    with backup.database_path.open("ab") as changed:
        changed.write(b"changed")
    with pytest.raises(OperationsError, match="checksum"):
        verify_sqlite_database(backup.database_path)

    clean_backup = create_backup(representative_database, tmp_path / "clean")
    target = tmp_path / "existing.sqlite"
    target.write_bytes(representative_database.read_bytes())
    with pytest.raises(OperationsError, match="explicit replacement"):
        restore_backup(
            clean_backup.database_path,
            target,
            replace=False,
            backend_confirmed_stopped=True,
        )
    with pytest.raises(OperationsError, match="stop the backend"):
        restore_backup(
            clean_backup.database_path,
            tmp_path / "new.sqlite",
            replace=True,
            backend_confirmed_stopped=False,
        )


def test_health_checks_return_healthy_and_detect_unreachable_backend(
    representative_database: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = tmp_path / "gcode"
    storage.mkdir()

    class Response:
        status = 200

        def __init__(self, body: bytes) -> None:
            self.body = body

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, _: int) -> bytes:
            return self.body

    def healthy_urlopen(request: object, timeout: int) -> Response:
        assert timeout == 5
        url = getattr(request, "full_url")
        return Response(
            b'{"status":"ok"}' if url.endswith("/api/health") else b"<!doctype html><html></html>"
        )

    monkeypatch.setattr("app.operations.health.urlopen", healthy_urlopen)
    base_url = "http://127.0.0.1:8080"
    healthy = run_health_checks(
        backend_url=f"{base_url}/api/health",
        frontend_url=f"{base_url}/",
        database_path=representative_database,
        gcode_directory=storage,
    )
    assert health_main(
        [
            "--backend-url",
            f"{base_url}/api/health",
            "--frontend-url",
            f"{base_url}/",
            "--database",
            str(representative_database),
            "--gcode-directory",
            str(storage),
        ]
    ) == 0
    assert all(check.healthy for check in healthy)

    def unreachable_urlopen(request: object, timeout: int) -> Response:
        raise URLError("unreachable")

    monkeypatch.setattr("app.operations.health.urlopen", unreachable_urlopen)
    unhealthy = run_health_checks(
        backend_url="http://127.0.0.1:1/api/health",
        frontend_url=f"{base_url}/",
        database_path=representative_database,
        gcode_directory=storage,
    )
    assert unhealthy[0].name == "Backend"
    assert not unhealthy[0].healthy
    assert health_main(
        [
            "--backend-url",
            "http://127.0.0.1:1/api/health",
            "--frontend-url",
            "http://127.0.0.1:1/",
            "--database",
            str(representative_database),
            "--gcode-directory",
            str(storage),
        ]
    ) == 1


def test_update_rejects_dirty_tree_and_records_previous_revision(
    representative_database: Path, tmp_path: Path
) -> None:
    repository = tmp_path / "checkout"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Ops Test")
    _git(repository, "config", "user.email", "ops@example.invalid")
    tracked = repository / "tracked.txt"
    tracked.write_text("clean\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-m", "fixture")
    preflight = inspect_update_checkout(repository)
    assert len(preflight.previous_revision) == 40
    assert preflight.free_bytes > 0

    backup = create_backup(representative_database, tmp_path / "update-backups")
    record = record_update_state(
        tmp_path / "update-backups",
        previous_revision=preflight.previous_revision,
        target_revision="a" * 40,
        backup=backup,
    )
    payload = json.loads(record.read_text(encoding="utf-8"))
    assert payload["previous_revision"] == preflight.previous_revision
    assert payload["verified_backup"] == str(backup.database_path)

    tracked.write_text("dirty\n", encoding="utf-8")
    with pytest.raises(OperationsError, match="working tree is dirty"):
        inspect_update_checkout(repository)


def test_update_and_rollback_artifacts_require_safe_database_path() -> None:
    updater = (BACKEND_ROOT / "app/scripts/update_production.py").read_text(encoding="utf-8")
    assert updater.index("create_backup(") < updater.index('"git", "merge"')
    assert updater.index("create_backup(") < updater.index('"upgrade", "head"')
    assert "downgrade" not in updater

    runbook = (REPOSITORY_ROOT / "docs/operations/production-runbook.md").read_text(
        encoding="utf-8"
    )
    rollback = runbook[runbook.index("## 17. Rollback") : runbook.index("## 18.")]
    assert "alembic downgrade" in rollback
    assert "pre-update" in rollback.lower()


def test_deployment_artifacts_preserve_network_and_identity_boundaries() -> None:
    backend_unit = (
        REPOSITORY_ROOT / "deploy/systemd/filament-command-center.service"
    ).read_text(encoding="utf-8")
    web_unit = (
        REPOSITORY_ROOT / "deploy/systemd/filament-command-center-web.service"
    ).read_text(encoding="utf-8")
    caddyfile = (REPOSITORY_ROOT / "deploy/proxy/Caddyfile").read_text(encoding="utf-8")
    environment = (
        REPOSITORY_ROOT / "deploy/env/production.env.example"
    ).read_text(encoding="utf-8")

    assert "--host 127.0.0.1" in backend_unit
    assert "Restart=on-failure" in backend_unit
    assert "RestartSec=5s" in backend_unit
    assert "User=root" not in backend_unit + web_unit
    assert "@api path /api /api/*" in caddyfile
    assert caddyfile.index("handle @api") < caddyfile.index("try_files")
    assert "frontend/dist" in caddyfile
    assert "/home/jeankarax" not in backend_unit + web_unit + caddyfile + environment
    assert "password=" not in environment.lower()


def test_runbook_references_tracked_operational_artifacts() -> None:
    expected = [
        "docs/operations/production-runbook.md",
        "deploy/env/production.env.example",
        "deploy/proxy/Caddyfile",
        "deploy/systemd/filament-command-center.service",
        "deploy/systemd/filament-command-center-web.service",
        "deploy/systemd/filament-command-center-backup.service",
        "deploy/systemd/filament-command-center-backup.timer",
        "backend/app/scripts/backup_database.py",
        "backend/app/scripts/restore_database.py",
        "backend/app/scripts/check_database.py",
        "backend/app/scripts/check_health.py",
        "backend/app/scripts/update_production.py",
        "frontend/playwright.production.config.ts",
    ]
    assert all((REPOSITORY_ROOT / path).is_file() for path in expected)


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
