import asyncio
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from app.api.gcode_uploads import get_gcode_upload_service
from app.config import (
    DEFAULT_GCODE_UPLOAD_CLEANUP_ENABLED,
    DEFAULT_GCODE_UPLOAD_MAX_TOTAL_BYTES,
    DEFAULT_GCODE_UPLOAD_RETENTION_DAYS,
    DEFAULT_GCODE_UPLOAD_RETENTION_ENABLED,
    DEFAULT_GCODE_UPLOAD_TEMP_STALE_SECONDS,
    get_gcode_max_upload_bytes,
    get_gcode_upload_cleanup_enabled,
    get_gcode_upload_directory,
    get_gcode_upload_max_total_bytes,
    get_gcode_upload_retention_days,
    get_gcode_upload_retention_enabled,
    get_gcode_upload_temp_stale_seconds,
)
from app.main import app
from app.services.gcode_upload_service import (
    GCodeInvalidUploadIdError,
    GCodeStorageQuotaExceededError,
    GCodeUploadService,
    GCodeUploadStorageError,
)

MAX_TEST_UPLOAD_BYTES = 16


@dataclass(frozen=True)
class GCodeApiEnvironment:
    client: TestClient
    service: GCodeUploadService
    storage_directory: Path


@pytest.fixture
def gcode_api_environment(tmp_path: Path) -> Iterator[GCodeApiEnvironment]:
    storage_directory = tmp_path / "uploads" / "gcode"
    service = GCodeUploadService(
        storage_directory=storage_directory,
        max_upload_bytes=MAX_TEST_UPLOAD_BYTES,
        chunk_size=4,
    )
    app.dependency_overrides[get_gcode_upload_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield GCodeApiEnvironment(client, service, storage_directory)
    finally:
        app.dependency_overrides.pop(get_gcode_upload_service, None)


def upload_file(
    environment: GCodeApiEnvironment,
    filename: str,
    contents: bytes,
):
    return environment.client.post(
        "/api/gcode/uploads",
        files={"file": (filename, contents, "application/octet-stream")},
    )


def test_valid_upload_returns_metadata_and_persists_file(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    contents = b"G1 X1 Y2\n"

    response = upload_file(gcode_api_environment, "benchy.gcode", contents)

    assert response.status_code == 201
    payload = response.json()
    assert UUID(payload["upload_id"])
    assert payload["filename"] == "benchy.gcode"
    assert payload["size_bytes"] == len(contents)
    assert payload["created_at"].endswith("Z")
    assert payload["status"] == "UPLOADED"

    resolved = gcode_api_environment.service.resolve_upload(payload["upload_id"])
    assert resolved.metadata.model_dump(mode="json") == payload
    assert resolved.path.read_bytes() == contents
    assert resolved.path.name == f'{payload["upload_id"]}.gcode'


def test_upload_ids_are_unique(gcode_api_environment: GCodeApiEnvironment) -> None:
    first = upload_file(gcode_api_environment, "first.gcode", b"G1\n").json()
    second = upload_file(gcode_api_environment, "second.gcode", b"G2\n").json()

    assert first["upload_id"] != second["upload_id"]


@pytest.mark.parametrize("filename", ["model.stl", "model.txt"])
def test_invalid_extensions_are_rejected(
    gcode_api_environment: GCodeApiEnvironment,
    filename: str,
) -> None:
    response = upload_file(gcode_api_environment, filename, b"not gcode")

    assert response.status_code == 400
    assert response.json() == {"detail": "Only .gcode files are accepted."}
    assert not gcode_api_environment.storage_directory.exists()


def test_uppercase_gcode_extension_is_accepted(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    response = upload_file(gcode_api_environment, "MODEL.GCODE", b"G1\n")

    assert response.status_code == 201
    assert response.json()["filename"] == "MODEL.GCODE"


def test_empty_file_is_rejected_without_storage_artifacts(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    response = upload_file(gcode_api_environment, "empty.gcode", b"")

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded G-code file is empty."}
    assert list(gcode_api_environment.storage_directory.iterdir()) == []


def test_file_exactly_at_size_limit_is_accepted(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    response = upload_file(
        gcode_api_environment,
        "limit.gcode",
        b"G" * MAX_TEST_UPLOAD_BYTES,
    )

    assert response.status_code == 201
    assert response.json()["size_bytes"] == MAX_TEST_UPLOAD_BYTES


def test_oversized_file_is_rejected_and_partial_file_is_removed(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    response = upload_file(
        gcode_api_environment,
        "large.gcode",
        b"G" * (MAX_TEST_UPLOAD_BYTES + 1),
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "The G-code file exceeds the upload size limit.",
    }
    assert list(gcode_api_environment.storage_directory.iterdir()) == []


def test_client_filename_cannot_control_physical_path(
    gcode_api_environment: GCodeApiEnvironment,
    tmp_path: Path,
) -> None:
    response = upload_file(gcode_api_environment, "../../evil.gcode", b"G1\n")

    assert response.status_code == 201
    payload = response.json()
    assert payload["filename"] == "../../evil.gcode"
    resolved = gcode_api_environment.service.resolve_upload(payload["upload_id"])
    assert resolved.path.parent == gcode_api_environment.storage_directory
    assert not (tmp_path / "evil.gcode").exists()


def test_missing_multipart_file_returns_validation_error(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    response = gcode_api_environment.client.post("/api/gcode/uploads")

    assert response.status_code == 422


def test_get_metadata_returns_upload_without_file_contents(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    created = upload_file(gcode_api_environment, "metadata.gcode", b"G1\n").json()

    response = gcode_api_environment.client.get(
        f'/api/gcode/uploads/{created["upload_id"]}',
    )

    assert response.status_code == 200
    assert response.json() == created
    assert "contents" not in response.json()


def test_get_metadata_returns_404_for_unknown_upload(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    response = gcode_api_environment.client.get(f"/api/gcode/uploads/{uuid4()}")

    assert response.status_code == 404


def test_invalid_upload_id_is_rejected_without_path_resolution(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    with pytest.raises(GCodeInvalidUploadIdError):
        gcode_api_environment.service.resolve_upload("../../foo")

    response = gcode_api_environment.client.get("/api/gcode/uploads/not-a-uuid")
    assert response.status_code == 400


def test_service_reads_upload_in_bounded_chunks(tmp_path: Path) -> None:
    contents = b"G1 X10 Y10\n"
    source = TrackingBytesIO(contents)
    upload = UploadFile(file=source, filename="streamed.gcode")
    service = GCodeUploadService(
        storage_directory=tmp_path / "streamed",
        max_upload_bytes=100,
        chunk_size=4,
    )

    metadata = asyncio.run(service.persist_upload(upload))

    assert metadata.size_bytes == len(contents)
    assert source.read_sizes
    assert all(size == 4 for size in source.read_sizes)


def test_read_error_removes_temporary_and_committed_artifacts(tmp_path: Path) -> None:
    upload = UploadFile(file=ExplodingBytesIO(b"G1 X10"), filename="broken.gcode")
    storage_directory = tmp_path / "broken"
    service = GCodeUploadService(
        storage_directory=storage_directory,
        max_upload_bytes=100,
        chunk_size=3,
    )

    with pytest.raises(GCodeUploadStorageError):
        asyncio.run(service.persist_upload(upload))

    assert list(storage_directory.iterdir()) == []


def test_openapi_registers_upload_and_metadata_endpoints(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    paths = gcode_api_environment.client.get("/openapi.json").json()["paths"]

    assert "post" in paths["/api/gcode/uploads"]
    assert "get" in paths["/api/gcode/uploads/{upload_id}"]
    assert "post" in paths["/api/gcode/uploads/{upload_id}/parse"]
    request_body = paths["/api/gcode/uploads"]["post"]["requestBody"]
    assert "multipart/form-data" in request_body["content"]


def test_upload_storage_and_limit_can_be_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured_directory = tmp_path / "configured-uploads"
    monkeypatch.setenv("GCODE_UPLOAD_DIRECTORY", str(configured_directory))
    monkeypatch.setenv("GCODE_MAX_UPLOAD_BYTES", "2048")

    assert get_gcode_upload_directory() == configured_directory
    assert get_gcode_max_upload_bytes() == 2048


def test_gcode_storage_lifecycle_defaults_load(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "GCODE_UPLOAD_RETENTION_DAYS",
        "GCODE_UPLOAD_MAX_TOTAL_BYTES",
        "GCODE_UPLOAD_TEMP_STALE_SECONDS",
        "GCODE_UPLOAD_CLEANUP_ENABLED",
        "GCODE_UPLOAD_RETENTION_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)

    assert get_gcode_upload_retention_days() == DEFAULT_GCODE_UPLOAD_RETENTION_DAYS
    assert get_gcode_upload_max_total_bytes() == DEFAULT_GCODE_UPLOAD_MAX_TOTAL_BYTES
    assert get_gcode_upload_temp_stale_seconds() == DEFAULT_GCODE_UPLOAD_TEMP_STALE_SECONDS
    assert get_gcode_upload_cleanup_enabled() is DEFAULT_GCODE_UPLOAD_CLEANUP_ENABLED
    assert get_gcode_upload_retention_enabled() is DEFAULT_GCODE_UPLOAD_RETENTION_ENABLED


@pytest.mark.parametrize(
    ("name", "value", "getter"),
    [
        ("GCODE_UPLOAD_RETENTION_DAYS", "-1", get_gcode_upload_retention_days),
        ("GCODE_UPLOAD_MAX_TOTAL_BYTES", "0", get_gcode_upload_max_total_bytes),
        ("GCODE_UPLOAD_TEMP_STALE_SECONDS", "0", get_gcode_upload_temp_stale_seconds),
        ("GCODE_UPLOAD_CLEANUP_ENABLED", "sometimes", get_gcode_upload_cleanup_enabled),
        ("GCODE_UPLOAD_RETENTION_ENABLED", "sometimes", get_gcode_upload_retention_enabled),
    ],
)
def test_invalid_gcode_storage_lifecycle_config_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    getter,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        getter()


def test_upload_with_sufficient_global_quota_succeeds(tmp_path: Path) -> None:
    storage = tmp_path / "quota-ok"
    service = GCodeUploadService(
        storage_directory=storage,
        max_upload_bytes=1024,
        max_total_bytes=1024,
        chunk_size=2,
    )

    metadata = asyncio.run(
        service.persist_upload(
            UploadFile(file=BytesIO(b"G1 X1\n"), filename="fits.gcode"),
        ),
    )

    assert service.resolve_upload(metadata.upload_id).path.read_bytes() == b"G1 X1\n"


def test_global_quota_rejection_is_structured_and_leaves_no_partial_file(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    existing = upload_file(gcode_api_environment, "existing.gcode", b"G1\n").json()
    used = sum(path.stat().st_size for path in gcode_api_environment.storage_directory.iterdir())
    quota_service = GCodeUploadService(
        storage_directory=gcode_api_environment.storage_directory,
        max_upload_bytes=MAX_TEST_UPLOAD_BYTES,
        max_total_bytes=used + 1,
        cleanup_enabled=True,
        chunk_size=4,
    )
    app.dependency_overrides[get_gcode_upload_service] = lambda: quota_service

    response = upload_file(gcode_api_environment, "blocked.gcode", b"G2\n")

    assert response.status_code == 507
    assert response.json() == {
        "detail": {
            "code": "gcode_storage_quota_exceeded",
            "message": "G-code storage has reached its configured limit.",
        },
    }
    assert {path.name for path in gcode_api_environment.storage_directory.iterdir()} == {
        f'{existing["upload_id"]}.gcode',
        f'{existing["upload_id"]}.json',
    }


def test_pre_upload_cleanup_reclaims_expired_upload_before_quota_check(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    expired = upload_file(gcode_api_environment, "expired.gcode", b"G1\n").json()
    metadata_path = gcode_api_environment.storage_directory / f'{expired["upload_id"]}.json'
    payload = metadata_path.read_text(encoding="utf-8").replace(
        expired["created_at"],
        "2020-01-01T00:00:00Z",
    )
    metadata_path.write_text(payload, encoding="utf-8")
    (gcode_api_environment.storage_directory / f'{expired["upload_id"]}.parse.json').write_bytes(
        b"x" * 512,
    )
    used = sum(path.stat().st_size for path in gcode_api_environment.storage_directory.iterdir())
    quota_service = GCodeUploadService(
        storage_directory=gcode_api_environment.storage_directory,
        max_upload_bytes=MAX_TEST_UPLOAD_BYTES,
        max_total_bytes=used,
        cleanup_enabled=True,
        chunk_size=4,
    )
    app.dependency_overrides[get_gcode_upload_service] = lambda: quota_service

    response = upload_file(gcode_api_environment, "replacement.gcode", b"G2\n")

    assert response.status_code == 201
    assert response.json()["upload_id"] != expired["upload_id"]
    assert not (gcode_api_environment.storage_directory / f'{expired["upload_id"]}.gcode').exists()


def test_full_quota_does_not_evict_recent_upload(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    recent = upload_file(gcode_api_environment, "recent.gcode", b"G1\n").json()
    used = sum(path.stat().st_size for path in gcode_api_environment.storage_directory.iterdir())
    quota_service = GCodeUploadService(
        storage_directory=gcode_api_environment.storage_directory,
        max_upload_bytes=MAX_TEST_UPLOAD_BYTES,
        max_total_bytes=used + 1,
        cleanup_enabled=True,
        chunk_size=4,
    )
    app.dependency_overrides[get_gcode_upload_service] = lambda: quota_service

    response = upload_file(gcode_api_environment, "new.gcode", b"G2\n")

    assert response.status_code == 507
    assert (gcode_api_environment.storage_directory / f'{recent["upload_id"]}.gcode').is_file()


def test_disabling_automatic_cleanup_preserves_expired_upload(tmp_path: Path) -> None:
    storage = tmp_path / "cleanup-disabled"
    original = GCodeUploadService(
        storage_directory=storage,
        max_upload_bytes=1024,
        max_total_bytes=4096,
        cleanup_enabled=False,
    )
    expired = asyncio.run(
        original.persist_upload(
            UploadFile(file=BytesIO(b"G1\n"), filename="expired.gcode"),
        ),
    )
    metadata_path = storage / f"{expired.upload_id}.json"
    metadata_path.write_text(
        metadata_path.read_text(encoding="utf-8").replace(
            expired.created_at.isoformat().replace("+00:00", "Z"),
            "2020-01-01T00:00:00Z",
        ),
        encoding="utf-8",
    )
    service = GCodeUploadService(
        storage_directory=storage,
        max_upload_bytes=1024,
        max_total_bytes=4096,
        cleanup_enabled=False,
    )

    asyncio.run(
        service.persist_upload(
            UploadFile(file=BytesIO(b"G2\n"), filename="new.gcode"),
        ),
    )

    assert (storage / f"{expired.upload_id}.gcode").is_file()


def test_streaming_quota_failure_removes_temporary_file(tmp_path: Path) -> None:
    storage = tmp_path / "stream-quota"
    service = GCodeUploadService(
        storage_directory=storage,
        max_upload_bytes=100,
        max_total_bytes=5,
        cleanup_enabled=False,
        chunk_size=4,
    )

    with pytest.raises(GCodeStorageQuotaExceededError):
        asyncio.run(
            service.persist_upload(
                UploadFile(file=BytesIO(b"123456"), filename="stream.gcode"),
            ),
        )

    assert list(storage.iterdir()) == []


def test_parse_endpoint_returns_versioned_summary_and_reuses_cache(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    created = upload_file(gcode_api_environment, "parse.gcode", b"M83\nG1 E2\n").json()
    path = f'/api/gcode/uploads/{created["upload_id"]}/parse'

    first = gcode_api_environment.client.post(path)
    second = gcode_api_environment.client.post(path)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["parser_version"] == 1
    assert first.json()["upload_id"] == created["upload_id"]
    assert first.json()["total_extrusion_length_mm"] == 2.0
    assert first.json()["tools"] == [
        {
            "tool": 0,
            "extrusion_length_mm": 2.0,
            "extrusion_volume_mm3": None,
        },
    ]
    cache = gcode_api_environment.storage_directory / f'{created["upload_id"]}.parse.json'
    assert cache.is_file()


def test_parse_endpoint_handles_invalid_and_missing_upload_ids(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    invalid = gcode_api_environment.client.post("/api/gcode/uploads/not-a-uuid/parse")
    missing = gcode_api_environment.client.post(f"/api/gcode/uploads/{uuid4()}/parse")

    assert invalid.status_code == 400
    assert missing.status_code == 404


def test_parse_endpoint_rejects_binary_upload(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    created = upload_file(gcode_api_environment, "binary.gcode", b"G1\x00X1").json()

    response = gcode_api_environment.client.post(
        f'/api/gcode/uploads/{created["upload_id"]}/parse',
    )

    assert response.status_code == 422
    assert "binary data" in response.json()["detail"]


def test_parse_endpoint_reports_missing_physical_file_without_traceback(
    gcode_api_environment: GCodeApiEnvironment,
) -> None:
    created = upload_file(gcode_api_environment, "missing.gcode", b"G1\n").json()
    resolved = gcode_api_environment.service.resolve_upload(created["upload_id"])
    resolved.path.unlink()

    response = gcode_api_environment.client.post(
        f'/api/gcode/uploads/{created["upload_id"]}/parse',
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Could not read or cache the G-code parse result.",
    }


class TrackingBytesIO(BytesIO):
    def __init__(self, initial_bytes: bytes) -> None:
        super().__init__(initial_bytes)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)


class ExplodingBytesIO(BytesIO):
    def __init__(self, initial_bytes: bytes) -> None:
        super().__init__(initial_bytes)
        self.read_count = 0

    def read(self, size: int = -1) -> bytes:
        self.read_count += 1
        if self.read_count > 1:
            raise OSError("simulated storage read failure")
        return super().read(size)
