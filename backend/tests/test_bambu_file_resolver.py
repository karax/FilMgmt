from datetime import UTC, datetime, timedelta

from app.integrations.bambu.file_resolver import (
    BambuFileResolutionStatus,
    resolve_print_file,
)
from app.integrations.bambu.ftps_client import BambuRemoteFile


def remote(path: str, modified_at: datetime | None = None) -> BambuRemoteFile:
    return BambuRemoteFile(path=path, name=path.rsplit("/", 1)[-1], modified_at=modified_at)


def test_exact_gcode_stem_resolution_and_plate_hint() -> None:
    result = resolve_print_file(
        (remote("/cache/robot_head_plate_2.3mf"), remote("/cache/other.3mf")),
        gcode_file="/data/robot_head_plate_2.gcode",
        print_name="Robot Head",
        started_at=None,
    )

    assert result.status is BambuFileResolutionStatus.EXACT
    assert result.selected and result.selected.path == "/cache/robot_head_plate_2.3mf"
    assert result.plate_hint == 2


def test_normalized_print_name_is_high_confidence() -> None:
    result = resolve_print_file(
        (remote("/cache/Desk Robot Head.3mf"),),
        gcode_file=None,
        print_name="desk_robot_head",
        started_at=None,
    )

    assert result.status is BambuFileResolutionStatus.HIGH_CONFIDENCE


def test_multiple_plausible_files_are_ambiguous_without_strong_time_evidence() -> None:
    result = resolve_print_file(
        (remote("/cache/Cube.3mf"), remote("/model/Cube.3mf")),
        gcode_file="Cube.gcode",
        print_name="Cube",
        started_at=datetime(2026, 10, 5, tzinfo=UTC),
    )

    assert result.status is BambuFileResolutionStatus.AMBIGUOUS
    assert result.selected is None


def test_file_time_can_conservatively_disambiguate_same_name() -> None:
    started = datetime(2026, 10, 5, 20, tzinfo=UTC)
    result = resolve_print_file(
        (
            remote("/cache/Cube.3mf", started + timedelta(minutes=1)),
            remote("/model/Cube.3mf", started - timedelta(days=2)),
        ),
        gcode_file="Cube.gcode",
        print_name=None,
        started_at=started,
    )

    assert result.status is BambuFileResolutionStatus.HIGH_CONFIDENCE
    assert result.selected and result.selected.path == "/cache/Cube.3mf"


def test_missing_file_is_not_guessed_from_time_alone() -> None:
    result = resolve_print_file(
        (remote("/cache/Unrelated.3mf", datetime.now(UTC)),),
        gcode_file="Wanted.gcode",
        print_name="Wanted",
        started_at=datetime.now(UTC),
    )

    assert result.status is BambuFileResolutionStatus.NOT_FOUND
    assert result.selected is None
