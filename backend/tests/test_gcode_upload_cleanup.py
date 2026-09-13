import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from starlette.datastructures import UploadFile

from app.scripts.cleanup_gcode_uploads import main as cleanup_main
from app.schemas.gcode_upload import GCodeUploadRead
from app.services.gcode_upload_cleanup_service import GCodeUploadCleanupService
from app.services.gcode_upload_service import GCodeUploadService


NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


def store_upload(
    storage: Path,
    *,
    created_at: datetime,
    contents: bytes = b"G1 X1\n",
    filename: str = "fixture.gcode",
) -> tuple[GCodeUploadService, GCodeUploadRead]:
    service = GCodeUploadService(
        storage_directory=storage,
        max_upload_bytes=1024,
        max_total_bytes=1024 * 1024,
        cleanup_enabled=False,
        chunk_size=4,
    )
    metadata = asyncio.run(
        service.persist_upload(UploadFile(file=BytesIO(contents), filename=filename)),
    )
    metadata = metadata.model_copy(update={"created_at": created_at})
    (storage / f"{metadata.upload_id}.json").write_text(
        metadata.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return service, metadata


def cleanup_service(storage: Path, **overrides) -> GCodeUploadCleanupService:
    return GCodeUploadCleanupService(
        storage_directory=storage,
        retention_days=overrides.pop("retention_days", 30),
        max_total_bytes=overrides.pop("max_total_bytes", 1024 * 1024),
        temp_stale_seconds=overrides.pop("temp_stale_seconds", 3600),
        **overrides,
    )


def test_expired_upload_removes_raw_metadata_parse_and_time_as_one_unit(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    _, metadata = store_upload(storage, created_at=NOW - timedelta(days=31))
    prefix = storage / str(metadata.upload_id)
    parse_cache = Path(f"{prefix}.parse.json")
    time_cache = Path(f"{prefix}.time.json")
    parse_cache.write_text("parse", encoding="utf-8")
    time_cache.write_text("time", encoding="utf-8")

    result = cleanup_service(storage).cleanup(now=NOW)

    assert result.expired_uploads == 1
    assert result.deleted_uploads == 1
    assert result.bytes_reclaimed > len(b"G1 X1\n")
    assert list(storage.iterdir()) == []


def test_recent_upload_is_not_removed(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    _, metadata = store_upload(storage, created_at=NOW - timedelta(days=29))

    result = cleanup_service(storage).cleanup(now=NOW)

    assert result.expired_uploads == 0
    assert result.deleted_uploads == 0
    assert (storage / f"{metadata.upload_id}.gcode").is_file()


def test_retention_flag_disables_expired_upload_deletion(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    _, metadata = store_upload(storage, created_at=NOW - timedelta(days=365))

    result = cleanup_service(storage, retention_enabled=False).cleanup(now=NOW)

    assert result.expired_uploads == 0
    assert (storage / f"{metadata.upload_id}.gcode").is_file()


def test_upload_exactly_at_retention_boundary_is_expired(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    _, metadata = store_upload(storage, created_at=NOW - timedelta(days=30))

    result = cleanup_service(storage).cleanup(now=NOW)

    assert result.expired_uploads == 1
    assert not (storage / f"{metadata.upload_id}.gcode").exists()


def test_orphan_cache_is_removed_but_unknown_file_is_ignored(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    storage.mkdir(parents=True)
    orphan = storage / f"{uuid4()}.parse.json"
    unknown = storage / "operator-notes.txt"
    orphan.write_text("cache", encoding="utf-8")
    unknown.write_text("keep", encoding="utf-8")

    result = cleanup_service(storage).cleanup(now=NOW)

    assert result.deleted_orphans == 1
    assert not orphan.exists()
    assert unknown.read_text(encoding="utf-8") == "keep"
    assert result.warnings == ["Ignored unknown G-code storage entry: operator-notes.txt"]
    assert result.used_bytes == len(b"keep")


@pytest.mark.parametrize("suffix", [".gcode", ".json"])
def test_incomplete_raw_or_metadata_sidecar_is_removed_as_orphan(
    tmp_path: Path,
    suffix: str,
) -> None:
    storage = tmp_path / "gcode"
    storage.mkdir(parents=True)
    orphan = storage / f"{uuid4()}{suffix}"
    orphan.write_text("orphan", encoding="utf-8")

    result = cleanup_service(storage).cleanup(now=NOW)

    assert result.deleted_orphans == 1
    assert not orphan.exists()


def test_stale_temp_is_removed_and_recent_temp_is_preserved(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    storage.mkdir(parents=True)
    stale = storage / f"{uuid4()}.uploading"
    recent = storage / f"{uuid4()}.parse.json.uploading"
    stale.write_bytes(b"stale")
    recent.write_bytes(b"recent")
    old_timestamp = (NOW - timedelta(hours=2)).timestamp()
    os.utime(stale, (old_timestamp, old_timestamp))
    recent_timestamp = (NOW - timedelta(minutes=30)).timestamp()
    os.utime(recent, (recent_timestamp, recent_timestamp))

    result = cleanup_service(storage).cleanup(now=NOW)

    assert result.deleted_temp_files == 1
    assert not stale.exists()
    assert recent.exists()


def test_cleanup_is_idempotent(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    store_upload(storage, created_at=NOW - timedelta(days=31))
    service = cleanup_service(storage)

    first = service.cleanup(now=NOW)
    second = service.cleanup(now=NOW)

    assert first.deleted_uploads == 1
    assert second.deleted_uploads == 0
    assert second.deleted_orphans == 0
    assert second.deleted_temp_files == 0
    assert second.bytes_reclaimed == 0


def test_cleanup_cli_executes_and_deletes_eligible_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage = tmp_path / "gcode"
    _, metadata = store_upload(storage, created_at=NOW - timedelta(days=3650))
    monkeypatch.setenv("GCODE_UPLOAD_DIRECTORY", str(storage))
    monkeypatch.setenv("GCODE_UPLOAD_RETENTION_DAYS", "30")
    monkeypatch.setenv("GCODE_UPLOAD_MAX_TOTAL_BYTES", str(1024 * 1024))
    monkeypatch.setenv("GCODE_UPLOAD_TEMP_STALE_SECONDS", "3600")

    exit_code = cleanup_main([])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "G-code cleanup" in output
    assert "expired uploads: 1" in output
    assert "deleted: 1 uploads" in output
    assert not (storage / f"{metadata.upload_id}.gcode").exists()


def test_cleanup_cli_dry_run_reports_reclaimable_bytes_without_deleting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage = tmp_path / "gcode"
    _, metadata = store_upload(storage, created_at=NOW - timedelta(days=3650))
    monkeypatch.setenv("GCODE_UPLOAD_DIRECTORY", str(storage))
    monkeypatch.setenv("GCODE_UPLOAD_RETENTION_DAYS", "30")
    monkeypatch.setenv("GCODE_UPLOAD_MAX_TOTAL_BYTES", str(1024 * 1024))
    monkeypatch.setenv("GCODE_UPLOAD_TEMP_STALE_SECONDS", "3600")

    exit_code = cleanup_main(["--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "reclaimable: " in output
    assert "reclaimable: 0 B" not in output
    assert "dry run: no files deleted" in output
    assert (storage / f"{metadata.upload_id}.gcode").is_file()


def test_active_upload_is_not_removed(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    upload_service, metadata = store_upload(storage, created_at=NOW - timedelta(days=31))

    with upload_service.active_operation(metadata.upload_id):
        result = cleanup_service(storage).cleanup(now=NOW)
        assert result.deleted_uploads == 0
        assert (storage / f"{metadata.upload_id}.gcode").is_file()

    assert cleanup_service(storage).cleanup(now=NOW).deleted_uploads == 1


def test_original_filename_path_traversal_cannot_delete_outside_storage(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    outside = tmp_path / "outside.gcode"
    outside.write_bytes(b"keep")
    store_upload(
        storage,
        created_at=NOW - timedelta(days=31),
        filename="../../outside.gcode",
    )

    result = cleanup_service(storage).cleanup(now=NOW)

    assert result.deleted_uploads == 1
    assert outside.read_bytes() == b"keep"


def test_known_symlink_is_unlinked_without_touching_external_target(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    _, metadata = store_upload(storage, created_at=NOW - timedelta(days=1))
    outside = tmp_path / "external-cache.json"
    outside.write_text("keep", encoding="utf-8")
    cache_link = storage / f"{metadata.upload_id}.parse.json"
    cache_link.symlink_to(outside)

    result = cleanup_service(storage).cleanup(now=NOW)

    assert result.deleted_orphans == 1
    assert not cache_link.exists()
    assert outside.read_text(encoding="utf-8") == "keep"
    assert (storage / f"{metadata.upload_id}.gcode").is_file()


def test_partial_delete_failure_is_reported_and_keeps_upload_resolvable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = tmp_path / "gcode"
    upload_service, metadata = store_upload(storage, created_at=NOW - timedelta(days=31))
    cache = storage / f"{metadata.upload_id}.parse.json"
    cache.write_text("cache", encoding="utf-8")
    real_unlink = Path.unlink

    def fail_cache_unlink(path: Path, *args, **kwargs):
        if path == cache:
            raise PermissionError("simulated permission failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_cache_unlink)

    result = cleanup_service(storage).cleanup(now=NOW)

    assert result.deleted_uploads == 0
    assert any("simulated permission failure" in error for error in result.errors)
    assert upload_service.resolve_upload(metadata.upload_id).path.is_file()


def test_storage_usage_counts_known_files_without_reading_them(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    _, metadata = store_upload(storage, created_at=NOW - timedelta(days=1), contents=b"123456")
    parse_cache = storage / f"{metadata.upload_id}.parse.json"
    parse_cache.write_bytes(b"1234")
    unknown = storage / "README"
    unknown.write_bytes(b"not managed")
    expected = sum(
        path.lstat().st_size
        for path in storage.iterdir()
    )

    status = cleanup_service(storage).inspect_storage(now=NOW)

    assert status.used_bytes == expected
    assert status.upload_count == 1
    assert status.unknown_files == ("README",)


def test_dry_run_reports_reclaimable_bytes_without_removing_files(tmp_path: Path) -> None:
    storage = tmp_path / "gcode"
    _, metadata = store_upload(storage, created_at=NOW - timedelta(days=31))

    result = cleanup_service(storage).cleanup(dry_run=True, now=NOW)

    assert result.expired_uploads == 1
    assert result.reclaimable_bytes > 0
    assert result.bytes_reclaimed == 0
    assert result.deleted_uploads == 0
    assert (storage / f"{metadata.upload_id}.gcode").is_file()
