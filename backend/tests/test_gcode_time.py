import asyncio
from io import BytesIO
import json
import math
from pathlib import Path
from typing import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from app.api.gcode_uploads import get_gcode_upload_service
from app.main import app
from app.services.gcode_parser import GCodeParseService
from app.services.gcode_time_service import (
    GCodeCommandTimeEstimator,
    GCodeTimeService,
    parse_duration_seconds,
)
from app.services.gcode_upload_service import GCodeUploadService


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5423", 5423),
        ("1h 30m 23s", 5423),
        ("1h 30m", 5400),
        ("30m 23s", 1823),
        ("01:30:23", 5423),
        ("30:23", 1823),
    ],
)
def test_duration_parser_accepts_explicit_formats(raw: str, expected: int) -> None:
    assert parse_duration_seconds(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [None, "", "-1", "NaN", "infinity", "tomorrow", "01:75:00", "999999999999"],
)
def test_duration_parser_rejects_invalid_values(raw: str | None) -> None:
    assert parse_duration_seconds(raw) is None


def analyze(*lines: str):
    return GCodeCommandTimeEstimator().analyze_lines(lines)


def test_linear_motion_uses_persistent_feedrate_and_xyz_distance() -> None:
    result = analyze("G21", "G90", "G1 F600", "G1 X3 Y4", "G1 X6 Y8")

    assert result.motion_time_seconds == 1
    assert result.unestimated_motion_count == 0


def test_feedrate_changes_only_subsequent_movements() -> None:
    result = analyze("G1 F600", "G1 X10", "G1 F1200", "G1 X20")

    assert result.motion_time_seconds == 1.5


def test_relative_positioning_uses_deltas() -> None:
    result = analyze("G91", "G1 F600", "G1 X10", "G1 X10")

    assert result.motion_time_seconds == 2


def test_inch_coordinates_and_feedrate_are_converted_together() -> None:
    result = analyze("G20", "G90", "G1 F60", "G1 X1")

    assert result.motion_time_seconds == 1


@pytest.mark.parametrize(
    ("mode", "moves", "expected"),
    [
        ("M82", ("G1 E10 F600", "G1 E20"), 2),
        ("M83", ("G1 E10 F600", "G1 E10"), 2),
    ],
)
def test_extrusion_only_moves_use_extruder_mode(
    mode: str,
    moves: tuple[str, str],
    expected: int,
) -> None:
    result = analyze(mode, *moves)

    assert result.motion_time_seconds == expected


def test_g92_changes_logical_position_without_adding_time() -> None:
    result = analyze("M82", "G92 E100", "G1 E110 F600")

    assert result.motion_time_seconds == 1


def test_xyz_and_extrusion_move_uses_only_spatial_distance() -> None:
    result = analyze("M83", "G1 X10 E100 F600")

    assert result.motion_time_seconds == 1


@pytest.mark.parametrize(("command", "expected"), [("G4 P5000", 5), ("G4 S5", 5)])
def test_dwell_is_included(command: str, expected: int) -> None:
    result = analyze(command)

    assert result.dwell_time_seconds == expected
    assert result.estimated_time_seconds == expected


def test_motion_without_feedrate_is_not_fabricated() -> None:
    result = analyze("G1 X10")

    assert result.estimated_time_seconds is None
    assert result.unestimated_motion_count == 1
    assert result.is_complete is False
    assert "missing_feedrate" in result.warnings


def test_partial_kinematic_result_retains_only_known_time() -> None:
    result = analyze("G1 X10", "G1 F600", "G1 X20")

    assert result.estimated_time_seconds == 1
    assert result.is_complete is False
    assert "incomplete_kinematic_estimate" in result.warnings


def test_waits_pauses_and_tool_changes_add_warnings_not_arbitrary_time() -> None:
    result = analyze("M109 S210", "M190 S60", "M0", "M1", "M25", "T1")

    assert result.estimated_time_seconds is None
    assert result.motion_time_seconds == 0
    assert result.dwell_time_seconds == 0
    assert result.warnings.count("temperature_waits_not_modeled") == 1
    assert result.warnings.count("user_pause_not_modeled") == 1
    assert result.warnings.count("tool_change_overhead_not_modeled") == 1


def test_m220_speed_factor_changes_subsequent_timing() -> None:
    result = analyze("G1 F600", "M220 S50", "G1 X10")

    assert result.motion_time_seconds == 2


def test_xy_arcs_use_directional_arc_length() -> None:
    clockwise = analyze("G92 X10 Y0", "G1 F600", "G2 X0 Y10 I-10 J0")
    counterclockwise = analyze("G92 X10 Y0", "G1 F600", "G3 X0 Y10 I-10 J0")

    assert counterclockwise.motion_time_seconds == pytest.approx(math.pi / 2, abs=1e-6)
    assert clockwise.motion_time_seconds == pytest.approx(3 * math.pi / 2, abs=1e-6)
    assert clockwise.motion_time_seconds > counterclockwise.motion_time_seconds


def test_invalid_arc_falls_back_to_chord_with_explicit_warning() -> None:
    result = analyze("G1 F600", "G2 X10 R1")

    assert result.motion_time_seconds == 1
    assert "arc_duration_approximated" in result.warnings


async def persist(service: GCodeUploadService, contents: bytes, name: str = "time.gcode"):
    return await service.persist_upload(UploadFile(filename=name, file=BytesIO(contents)))


def make_service(tmp_path: Path, contents: bytes, *, estimator=None):
    upload_service = GCodeUploadService(tmp_path / "gcode", 1024 * 1024, 32)
    metadata = asyncio.run(persist(upload_service, contents))
    parse_service = GCodeParseService(upload_service=upload_service)
    service = GCodeTimeService(
        parse_service=parse_service,
        upload_service=upload_service,
        estimator=estimator,
    )
    return service, upload_service, metadata


def test_slicer_time_formats_and_source_precedence(tmp_path: Path) -> None:
    service, _, metadata = make_service(
        tmp_path,
        b";TIME:5423\n; estimated printing time = 1h 31m\nG1 X10 F600\n",
    )

    result = service.estimate_upload(metadata.upload_id)

    assert result.estimated_time_seconds == 5460
    assert result.source == "slicer_metadata"
    assert result.slicer_time_key == "estimated printing time"
    assert result.kinematic_estimated_time_seconds == 1
    assert result.is_heuristic is False
    assert result.warnings == ["multiple_slicer_time_estimates"]


def test_normal_mode_beats_silent_generic_and_time_metadata(tmp_path: Path) -> None:
    service, _, metadata = make_service(
        tmp_path,
        (
            b";TIME:5000\n"
            b"; estimated printing time = 1h 20m\n"
            b"; estimated printing time (silent mode) = 2h\n"
            b"; estimated printing time (normal mode) = 1h 30m 23s\n"
        ),
    )

    result = service.estimate_upload(metadata.upload_id)

    assert result.estimated_time_seconds == 5423
    assert result.slicer_time_key == "estimated printing time (normal mode)"
    assert result.warnings == ["multiple_slicer_time_estimates"]


def test_invalid_slicer_value_falls_back_without_crashing(tmp_path: Path) -> None:
    service, _, metadata = make_service(tmp_path, b";TIME:not-a-duration\nG1 X10 F600\n")

    result = service.estimate_upload(metadata.upload_id)

    assert result.source == "command_kinematics"
    assert result.estimated_time_seconds == 1
    assert result.is_heuristic is True
    assert "acceleration_not_modeled" in result.warnings


def test_no_metadata_or_timed_commands_preserves_null(tmp_path: Path) -> None:
    service, _, metadata = make_service(tmp_path, b"M104 S210\n")

    result = service.estimate_upload(metadata.upload_id)

    assert result.estimated_time_seconds is None
    assert result.source is None
    assert result.is_complete is False


class CountingEstimator(GCodeCommandTimeEstimator):
    def __init__(self) -> None:
        self.calls = 0

    def analyze_path(self, path: Path, *, metadata=None):
        self.calls += 1
        return super().analyze_path(path, metadata=metadata)


def test_versioned_cache_is_reused_and_invalidated_atomically(tmp_path: Path) -> None:
    estimator = CountingEstimator()
    service, upload_service, metadata = make_service(
        tmp_path,
        b"G1 X10 F600\n",
        estimator=estimator,
    )

    first = service.estimate_upload(metadata.upload_id)
    second = service.estimate_upload(metadata.upload_id)
    cache_path = service.cache_path_for(upload_service.resolve_upload(metadata.upload_id).path)

    assert first == second
    assert estimator.calls == 1
    assert cache_path.is_file()
    assert not cache_path.with_suffix(".json.uploading").exists()
    assert "G1 X10" not in cache_path.read_text(encoding="utf-8")

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    cache["time_estimator_version"] = 0
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    service.estimate_upload(metadata.upload_id)
    assert estimator.calls == 2


def test_time_analysis_skips_sidecars_when_total_storage_quota_is_full(
    tmp_path: Path,
) -> None:
    _, original_upload_service, metadata = make_service(tmp_path, b"G1 F600 X10\n")
    upload_path = original_upload_service.resolve_upload(metadata.upload_id).path
    storage = upload_path.parent
    used_bytes = sum(path.lstat().st_size for path in storage.iterdir())
    quota_service = GCodeUploadService(
        storage_directory=storage,
        max_upload_bytes=1024,
        max_total_bytes=used_bytes,
        cleanup_enabled=False,
    )
    parse_service = GCodeParseService(upload_service=quota_service)
    service = GCodeTimeService(
        parse_service=parse_service,
        upload_service=quota_service,
    )

    result = service.estimate_upload(metadata.upload_id)

    assert result.estimated_time_seconds == 1
    assert not service.cache_path_for(upload_path).exists()
    assert not parse_service.cache_path_for(upload_path).exists()
    assert not list(storage.glob("*.uploading"))
    assert sum(path.lstat().st_size for path in storage.iterdir()) == used_bytes


def test_path_estimator_uses_readline_not_bulk_reads(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "stream.gcode"
    path.write_bytes(b"G1 X10 F600\nG1 X20\n")
    real_open = Path.open

    class ReadlineOnly:
        def __init__(self, data: bytes) -> None:
            self.data = BytesIO(data)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def readline(self, size: int = -1):
            return self.data.readline(size)

        def read(self, *_args, **_kwargs):
            raise AssertionError("bulk read is forbidden")

        def readlines(self, *_args, **_kwargs):
            raise AssertionError("readlines is forbidden")

    def guarded_open(target: Path, mode="r", *args, **kwargs):
        if target == path and mode == "rb":
            return ReadlineOnly(contents)
        return real_open(target, mode, *args, **kwargs)

    contents = path.read_bytes()
    monkeypatch.setattr(Path, "open", guarded_open)

    result = GCodeCommandTimeEstimator().analyze_path(path)

    assert result.motion_time_seconds == 2


@pytest.fixture
def time_api(tmp_path: Path) -> Iterator[tuple[TestClient, GCodeUploadService]]:
    upload_service = GCodeUploadService(tmp_path / "api-gcode", 4096, 32)
    app.dependency_overrides[get_gcode_upload_service] = lambda: upload_service
    try:
        with TestClient(app) as client:
            yield client, upload_service
    finally:
        app.dependency_overrides.pop(get_gcode_upload_service, None)


def test_time_endpoint_and_openapi(time_api) -> None:
    client, upload_service = time_api
    created = client.post(
        "/api/gcode/uploads",
        files={"file": ("api.gcode", b"; print_time = 90\nG1 X10 F600\n", "text/plain")},
    ).json()

    response = client.post(f'/api/gcode/uploads/{created["upload_id"]}/time')

    assert response.status_code == 200
    assert response.json()["estimated_time_seconds"] == 90
    assert response.json()["source"] == "slicer_metadata"
    upload_path = upload_service.resolve_upload(created["upload_id"]).path
    assert upload_path.with_suffix(".time.json").is_file()
    paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/api/gcode/uploads/{upload_id}/time"]


def test_time_endpoint_rejects_missing_and_invalid_upload_ids(time_api) -> None:
    client, _ = time_api

    missing = client.post(f"/api/gcode/uploads/{uuid4()}/time")
    invalid = client.post("/api/gcode/uploads/not-a-uuid/time")

    assert missing.status_code == 404
    assert invalid.status_code == 400
