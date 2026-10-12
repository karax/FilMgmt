from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import PurePosixPath
import re
import unicodedata

from app.integrations.bambu.ftps_client import BambuRemoteFile


class BambuFileResolutionStatus(StrEnum):
    EXACT = "EXACT"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class BambuFileResolution:
    status: BambuFileResolutionStatus
    selected: BambuRemoteFile | None
    candidates: tuple[BambuRemoteFile, ...] = ()
    plate_hint: int | None = None


def resolve_print_file(
    files: tuple[BambuRemoteFile, ...],
    *,
    gcode_file: str | None,
    print_name: str | None,
    started_at: datetime | None,
) -> BambuFileResolution:
    plate_hint = _plate_hint(gcode_file) or _plate_hint(print_name)
    if gcode_file:
        direct_path = _safe_posix(gcode_file)
        direct = tuple(item for item in files if direct_path and item.path.casefold() == direct_path.casefold())
        if len(direct) == 1:
            return BambuFileResolution(BambuFileResolutionStatus.EXACT, direct[0], direct, plate_hint)

    expected: list[tuple[str, bool]] = []
    if gcode_file:
        basename = PurePosixPath(gcode_file.replace("\\", "/")).name
        if not re.fullmatch(r"plate_\d+\.gcode", basename, flags=re.IGNORECASE):
            expected.append((_stem(basename), True))
    if print_name:
        expected.append((_stem(print_name), False))

    exact: dict[str, BambuRemoteFile] = {}
    normalized: dict[str, BambuRemoteFile] = {}
    for expected_stem, from_gcode in expected:
        if not expected_stem:
            continue
        for item in files:
            remote_stem = _stem(item.name)
            if remote_stem.casefold() == expected_stem.casefold():
                (exact if from_gcode else normalized)[item.path] = item
            elif _normalized(remote_stem) == _normalized(expected_stem):
                normalized[item.path] = item

    if len(exact) == 1:
        selected = next(iter(exact.values()))
        return BambuFileResolution(BambuFileResolutionStatus.EXACT, selected, (selected,), plate_hint or _plate_hint(selected.name))
    candidates = tuple(exact.values()) if exact else tuple(normalized.values())
    if len(candidates) == 1:
        selected = candidates[0]
        return BambuFileResolution(BambuFileResolutionStatus.HIGH_CONFIDENCE, selected, candidates, plate_hint or _plate_hint(selected.name))
    if len(candidates) > 1:
        selected = _nearest_unambiguous(candidates, started_at)
        if selected is not None:
            return BambuFileResolution(BambuFileResolutionStatus.HIGH_CONFIDENCE, selected, candidates, plate_hint or _plate_hint(selected.name))
        return BambuFileResolution(BambuFileResolutionStatus.AMBIGUOUS, None, candidates, plate_hint)
    return BambuFileResolution(BambuFileResolutionStatus.NOT_FOUND, None, (), plate_hint)


def _stem(value: str) -> str:
    result = value.strip()
    lower = result.casefold()
    for suffix in (".gcode.3mf", ".gcode", ".3mf"):
        if lower.endswith(suffix):
            return result[: -len(suffix)]
    return result


def _normalized(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _safe_posix(value: str) -> str | None:
    normalized = value.replace("\\", "/")
    if "\r" in normalized or "\n" in normalized:
        return None
    path = PurePosixPath(normalized)
    if not path.is_absolute() or ".." in path.parts:
        return None
    return str(path)


def _plate_hint(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(?:^|[_\-\s])plate[_\-\s]?(\d+)(?:\D|$)", value, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _nearest_unambiguous(
    candidates: tuple[BambuRemoteFile, ...],
    started_at: datetime | None,
) -> BambuRemoteFile | None:
    if started_at is None or any(candidate.modified_at is None for candidate in candidates):
        return None
    reference = started_at if started_at.tzinfo else started_at.replace(tzinfo=UTC)
    ranked = sorted(
        ((abs((candidate.modified_at - reference).total_seconds()), candidate) for candidate in candidates if candidate.modified_at),
        key=lambda item: item[0],
    )
    if not ranked or ranked[0][0] > timedelta(hours=24).total_seconds():
        return None
    if len(ranked) > 1 and ranked[1][0] - ranked[0][0] < timedelta(minutes=30).total_seconds():
        return None
    return ranked[0][1]
