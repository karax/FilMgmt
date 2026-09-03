from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import re
from typing import BinaryIO
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.gcode_parse import GCodeParseResult
from app.schemas.gcode_time import GCodeTimeResult
from app.services.gcode_parser import (
    GCODE_READ_CHUNK_BYTES,
    MAX_GCODE_LINE_BYTES,
    GCodeParseService,
    parse_gcode_line,
)
from app.services.gcode_upload_service import GCodeUploadService

TIME_ESTIMATOR_VERSION = 1
MAX_TIME_CACHE_BYTES = 64 * 1024
MAX_DURATION_SECONDS = 10 * 365 * 24 * 60 * 60

_DECIMAL_RE = re.compile(r"^(?:\d+(?:\.\d*)?|\.\d+)$")
_DURATION_UNITS_RE = re.compile(
    r"^\s*(?:(?P<days>\d+(?:\.\d+)?)\s*d\s*)?"
    r"(?:(?P<hours>\d+(?:\.\d+)?)\s*h\s*)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)\s*m\s*)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)\s*s\s*)?$",
    re.IGNORECASE,
)
_METADATA_RE = re.compile(r"^\s*([^:=]+?)\s*[:=]\s*(.*?)\s*$")
_MODE_TIME_KEY_RE = re.compile(
    r"^estimated print(?:ing)? time \([a-z0-9 _-]+\)$",
    re.IGNORECASE,
)
_TIME_KEY_PRIORITY = {
    "total estimated time": 0,
    "estimated printing time (normal mode)": 1,
    "estimated print time (normal mode)": 2,
    "estimated printing time (default mode)": 3,
    "estimated print time (default mode)": 4,
    "estimated printing time": 10,
    "estimated print time": 11,
    "time": 20,
    "print_time": 30,
    "print time": 31,
}


class GCodeTimeStorageError(Exception):
    pass


class _TimeCacheEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_estimator_version: int
    upload_id: UUID
    filename: str
    source_size_bytes: int
    result: GCodeTimeResult


@dataclass(frozen=True)
class _SlicerCandidate:
    key: str
    seconds: float
    priority: int
    order: int


@dataclass(frozen=True)
class _KinematicAnalysis:
    estimated_time_seconds: float | None
    motion_time_seconds: float
    dwell_time_seconds: float
    is_complete: bool
    unestimated_motion_count: int
    warnings: list[str]
    slicer_candidates: list[_SlicerCandidate]


def parse_duration_seconds(value: str | None) -> float | None:
    """Parse an explicit duration without interpreting arbitrary text as time."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None

    if _DECIMAL_RE.fullmatch(normalized):
        return _valid_duration(float(normalized))

    if ":" in normalized:
        parts = normalized.split(":")
        if len(parts) not in {2, 3} or any(not part.isdigit() for part in parts):
            return None
        numbers = [int(part) for part in parts]
        if len(numbers) == 2:
            minutes, seconds = numbers
            if seconds >= 60:
                return None
            return _valid_duration(minutes * 60 + seconds)
        hours, minutes, seconds = numbers
        if minutes >= 60 or seconds >= 60:
            return None
        return _valid_duration(hours * 3600 + minutes * 60 + seconds)

    match = _DURATION_UNITS_RE.fullmatch(normalized)
    if match is None or not any(match.groupdict().values()):
        return None
    seconds = (
        float(match.group("days") or 0) * 86400
        + float(match.group("hours") or 0) * 3600
        + float(match.group("minutes") or 0) * 60
        + float(match.group("seconds") or 0)
    )
    return _valid_duration(seconds)


def _valid_duration(value: float) -> float | None:
    if not math.isfinite(value) or value < 0 or value > MAX_DURATION_SECONDS:
        return None
    return _normalized_seconds(value)


def _metadata_candidate(key: str, value: str, order: int) -> _SlicerCandidate | None:
    normalized_key = " ".join(key.lower().split())
    priority = _TIME_KEY_PRIORITY.get(normalized_key)
    if priority is None:
        if not _MODE_TIME_KEY_RE.fullmatch(normalized_key):
            return None
        priority = 40

    if normalized_key == "time":
        normalized_value = value.strip()
        seconds = (
            _valid_duration(float(normalized_value))
            if _DECIMAL_RE.fullmatch(normalized_value)
            else None
        )
    else:
        seconds = parse_duration_seconds(value)
    if seconds is None:
        return None
    return _SlicerCandidate(normalized_key, seconds, priority, order)


def _select_slicer_candidate(
    candidates: Iterable[_SlicerCandidate],
) -> tuple[_SlicerCandidate | None, bool]:
    unique: dict[tuple[str, float], _SlicerCandidate] = {}
    for candidate in candidates:
        unique[(candidate.key, candidate.seconds)] = candidate
    values = list(unique.values())
    if not values:
        return None, False
    selected = min(values, key=lambda item: (item.priority, item.key, -item.order))
    conflicting = len({item.seconds for item in values}) > 1
    return selected, conflicting


class GCodeCommandTimeEstimator:
    """Idealized constant-feed timing for a streaming sequence of commands."""

    def analyze_path(
        self,
        path: Path,
        *,
        metadata: dict[str, str] | None = None,
    ) -> _KinematicAnalysis:
        try:
            with path.open("rb") as source:
                return self._analyze_binary_lines(source, metadata=metadata)
        except OSError as error:
            raise GCodeTimeStorageError("Could not read the G-code for time analysis.") from error

    def analyze_lines(
        self,
        lines: Iterable[str],
        *,
        metadata: dict[str, str] | None = None,
    ) -> _KinematicAnalysis:
        accumulator = _TimeAccumulator()
        accumulator.add_metadata(metadata or {})
        for line in lines:
            accumulator.consume(line)
        return accumulator.result()

    def _analyze_binary_lines(
        self,
        source: BinaryIO,
        *,
        metadata: dict[str, str] | None,
    ) -> _KinematicAnalysis:
        accumulator = _TimeAccumulator()
        accumulator.add_metadata(metadata or {})
        for raw_line, oversized in _iter_bounded_binary_lines(source):
            if oversized:
                accumulator.mark_unestimated_line()
                continue
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                line = raw_line.decode("utf-8", errors="replace")
                accumulator.add_warning("encoding_replacement_detected")
            accumulator.consume(line)
        return accumulator.result()


@dataclass
class _TimeAccumulator:
    units_to_mm: float = 1.0
    xyz_absolute: bool = True
    e_absolute: bool = True
    plane: str = "G17"
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    current_tool: int = 0
    e_positions_mm: dict[int, float] = field(default_factory=dict)
    feedrate_mm_per_min: float | None = None
    speed_factor: float = 1.0
    volumetric_extrusion: bool = False
    motion_time_seconds: float = 0.0
    dwell_time_seconds: float = 0.0
    estimated_component_count: int = 0
    unestimated_motion_count: int = 0
    warnings: list[str] = field(default_factory=list)
    _warning_set: set[str] = field(default_factory=set)
    slicer_candidates: list[_SlicerCandidate] = field(default_factory=list)
    _metadata_order: int = 0

    def add_warning(self, warning: str) -> None:
        if warning not in self._warning_set:
            self._warning_set.add(warning)
            self.warnings.append(warning)

    def add_metadata(self, metadata: dict[str, str]) -> None:
        for key, value in metadata.items():
            self._add_metadata_value(key, value)

    def mark_unestimated_line(self) -> None:
        self.unestimated_motion_count += 1
        self.add_warning("oversized_line_ignored")

    def consume(self, line: str) -> None:
        parsed = parse_gcode_line(line)
        if parsed.comment:
            match = _METADATA_RE.match(parsed.comment)
            if match:
                self._add_metadata_value(match.group(1), match.group(2))
        command = parsed.command
        if command is None:
            return
        parameters = parsed.parameters

        if command == "G20":
            self.units_to_mm = 25.4
        elif command == "G21":
            self.units_to_mm = 1.0
        elif command == "G90":
            self.xyz_absolute = True
        elif command == "G91":
            self.xyz_absolute = False
        elif command == "M82":
            self.e_absolute = True
        elif command == "M83":
            self.e_absolute = False
        elif command in {"G17", "G18", "G19"}:
            self.plane = command
        elif command == "G92":
            self._set_logical_position(parameters)
        elif command in {"G0", "G1", "G2", "G3"}:
            self._consume_motion(command, parameters)
        elif command == "G4":
            self._consume_dwell(parameters)
        elif command in {"M0", "M1", "M25"}:
            self.add_warning("user_pause_not_modeled")
        elif command in {"M109", "M190"}:
            self.add_warning("temperature_waits_not_modeled")
        elif command == "M220":
            self._set_speed_factor(parameters)
        elif command == "M200":
            diameter = parameters.get("D")
            if diameter is not None and diameter >= 0:
                self.volumetric_extrusion = diameter > 0
        elif command.startswith("T") and command[1:].isdigit():
            tool = int(command[1:])
            if tool != self.current_tool:
                self.add_warning("tool_change_overhead_not_modeled")
            self.current_tool = tool

    def _add_metadata_value(self, key: str, value: str) -> None:
        self._metadata_order += 1
        candidate = _metadata_candidate(key, value, self._metadata_order)
        if candidate is not None:
            self.slicer_candidates.append(candidate)

    def _set_logical_position(self, parameters: dict[str, float]) -> None:
        if "X" in parameters:
            self.x_mm = parameters["X"] * self.units_to_mm
        if "Y" in parameters:
            self.y_mm = parameters["Y"] * self.units_to_mm
        if "Z" in parameters:
            self.z_mm = parameters["Z"] * self.units_to_mm
        if "E" in parameters:
            self.e_positions_mm[self.current_tool] = parameters["E"] * self.units_to_mm

    def _consume_motion(self, command: str, parameters: dict[str, float]) -> None:
        if "F" in parameters:
            requested_feedrate = parameters["F"] * self.units_to_mm
            if requested_feedrate > 0:
                self.feedrate_mm_per_min = requested_feedrate
            else:
                self.add_warning("invalid_feedrate")

        start = (self.x_mm, self.y_mm, self.z_mm)
        end = self._target_xyz(parameters)
        dx, dy, dz = (end[index] - start[index] for index in range(3))
        e_delta = self._extrusion_delta(parameters)
        self.x_mm, self.y_mm, self.z_mm = end

        if command in {"G2", "G3"}:
            xyz_distance, approximated = _arc_distance_mm(
                command,
                self.plane,
                start,
                end,
                parameters,
                self.units_to_mm,
            )
            if approximated:
                self.add_warning("arc_duration_approximated")
        else:
            xyz_distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if xyz_distance > 0:
            distance = xyz_distance
        elif abs(e_delta) > 0:
            if self.volumetric_extrusion:
                self._mark_unestimated_motion("volumetric_e_only_not_estimated")
                return
            distance = abs(e_delta)
        else:
            return

        effective_feedrate = (
            self.feedrate_mm_per_min * self.speed_factor
            if self.feedrate_mm_per_min is not None
            else None
        )
        if effective_feedrate is None or effective_feedrate <= 0:
            self._mark_unestimated_motion("missing_feedrate")
            return
        self.motion_time_seconds += distance / effective_feedrate * 60
        self.estimated_component_count += 1

    def _target_xyz(self, parameters: dict[str, float]) -> tuple[float, float, float]:
        current = (self.x_mm, self.y_mm, self.z_mm)
        targets = []
        for index, axis in enumerate(("X", "Y", "Z")):
            if axis not in parameters:
                targets.append(current[index])
            elif self.xyz_absolute:
                targets.append(parameters[axis] * self.units_to_mm)
            else:
                targets.append(current[index] + parameters[axis] * self.units_to_mm)
        return targets[0], targets[1], targets[2]

    def _extrusion_delta(self, parameters: dict[str, float]) -> float:
        if "E" not in parameters:
            return 0.0
        current = self.e_positions_mm.get(self.current_tool, 0.0)
        commanded = parameters["E"] * self.units_to_mm
        if self.e_absolute:
            delta = commanded - current
            self.e_positions_mm[self.current_tool] = commanded
            return delta
        self.e_positions_mm[self.current_tool] = current + commanded
        return commanded

    def _consume_dwell(self, parameters: dict[str, float]) -> None:
        seconds = max(parameters.get("S", 0.0), 0.0)
        seconds += max(parameters.get("P", 0.0), 0.0) / 1000
        if seconds > 0:
            self.dwell_time_seconds += seconds
            self.estimated_component_count += 1

    def _set_speed_factor(self, parameters: dict[str, float]) -> None:
        factor = parameters.get("S")
        if factor is None:
            return
        if factor <= 0:
            self.add_warning("invalid_speed_factor")
            return
        self.speed_factor = factor / 100

    def _mark_unestimated_motion(self, warning: str) -> None:
        self.unestimated_motion_count += 1
        self.add_warning(warning)

    def result(self) -> _KinematicAnalysis:
        total = self.motion_time_seconds + self.dwell_time_seconds
        available = self.estimated_component_count > 0
        warnings = list(self.warnings)
        if available:
            warnings.insert(0, "acceleration_not_modeled")
        if self.unestimated_motion_count:
            warnings.append("incomplete_kinematic_estimate")
        return _KinematicAnalysis(
            estimated_time_seconds=_normalized_seconds(total) if available else None,
            motion_time_seconds=_normalized_seconds(self.motion_time_seconds),
            dwell_time_seconds=_normalized_seconds(self.dwell_time_seconds),
            is_complete=self.unestimated_motion_count == 0,
            unestimated_motion_count=self.unestimated_motion_count,
            warnings=list(dict.fromkeys(warnings)),
            slicer_candidates=self.slicer_candidates,
        )


class GCodeTimeService:
    """Select slicer metadata over a cached, streaming kinematic fallback."""

    def __init__(
        self,
        parse_service: GCodeParseService,
        upload_service: GCodeUploadService | None = None,
        estimator: GCodeCommandTimeEstimator | None = None,
    ) -> None:
        self.parse_service = parse_service
        self.upload_service = upload_service or parse_service.upload_service
        self.estimator = estimator or GCodeCommandTimeEstimator()

    def estimate_upload(self, upload_id: str | UUID) -> GCodeTimeResult:
        resolved = self.upload_service.resolve_upload(upload_id)
        cache_path = self.cache_path_for(resolved.path)
        cached = self._read_cache(cache_path)
        if cached is not None and self._cache_matches_upload(cached, resolved.metadata):
            return cached.result

        summary = self.parse_service.parse_upload(upload_id)
        analysis = self.estimator.analyze_path(resolved.path, metadata=summary.metadata)
        slicer, conflicting = _select_slicer_candidate(analysis.slicer_candidates)
        if slicer is not None:
            source = "slicer_metadata"
            estimated = slicer.seconds
            is_heuristic = False
            is_complete = True
            warnings = ["multiple_slicer_time_estimates"] if conflicting else []
        elif analysis.estimated_time_seconds is not None:
            source = "command_kinematics"
            estimated = analysis.estimated_time_seconds
            is_heuristic = True
            is_complete = analysis.is_complete
            warnings = analysis.warnings
        else:
            source = None
            estimated = None
            is_heuristic = False
            is_complete = False
            warnings = analysis.warnings

        result = GCodeTimeResult(
            time_estimator_version=TIME_ESTIMATOR_VERSION,
            upload_id=summary.upload_id,
            parser_version=summary.parser_version,
            estimated_time_seconds=estimated,
            source=source,
            slicer_estimated_time_seconds=slicer.seconds if slicer is not None else None,
            slicer_time_key=slicer.key if slicer is not None else None,
            kinematic_estimated_time_seconds=analysis.estimated_time_seconds,
            motion_time_seconds=analysis.motion_time_seconds,
            dwell_time_seconds=analysis.dwell_time_seconds,
            kinematic_is_complete=analysis.is_complete,
            unestimated_motion_count=analysis.unestimated_motion_count,
            is_heuristic=is_heuristic,
            is_complete=is_complete,
            warnings=warnings,
        )
        envelope = _TimeCacheEnvelope(
            time_estimator_version=TIME_ESTIMATOR_VERSION,
            upload_id=resolved.metadata.upload_id,
            filename=resolved.metadata.filename,
            source_size_bytes=resolved.metadata.size_bytes,
            result=result,
        )
        self._write_cache(cache_path, envelope)
        return result

    @staticmethod
    def cache_path_for(upload_path: Path) -> Path:
        return upload_path.with_suffix(".time.json")

    @staticmethod
    def _cache_matches_upload(envelope: _TimeCacheEnvelope, metadata: object) -> bool:
        return (
            envelope.time_estimator_version == TIME_ESTIMATOR_VERSION
            and envelope.result.time_estimator_version == TIME_ESTIMATOR_VERSION
            and envelope.upload_id == getattr(metadata, "upload_id", None)
            and envelope.filename == getattr(metadata, "filename", None)
            and envelope.source_size_bytes == getattr(metadata, "size_bytes", None)
        )

    @staticmethod
    def _read_cache(path: Path) -> _TimeCacheEnvelope | None:
        if not path.is_file():
            return None
        try:
            if path.stat().st_size > MAX_TIME_CACHE_BYTES:
                return None
            envelope = _TimeCacheEnvelope.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return envelope if envelope.time_estimator_version == TIME_ESTIMATOR_VERSION else None

    @staticmethod
    def _write_cache(path: Path, envelope: _TimeCacheEnvelope) -> None:
        temporary_path = path.with_suffix(".json.uploading")
        try:
            with temporary_path.open("w", encoding="utf-8") as destination:
                destination.write(envelope.model_dump_json(indent=2))
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise GCodeTimeStorageError("Could not cache the G-code time result.") from error


def _arc_distance_mm(
    command: str,
    plane: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    parameters: dict[str, float],
    unit_scale: float,
) -> tuple[float, bool]:
    chord_3d = math.dist(start, end)
    if plane != "G17":
        return chord_3d, True

    sx, sy, sz = start
    ex, ey, ez = end
    if "I" in parameters or "J" in parameters:
        cx = sx + parameters.get("I", 0.0) * unit_scale
        cy = sy + parameters.get("J", 0.0) * unit_scale
        radius = math.hypot(sx - cx, sy - cy)
        end_radius = math.hypot(ex - cx, ey - cy)
        if radius <= 0 or not math.isclose(radius, end_radius, rel_tol=0.01, abs_tol=0.01):
            return chord_3d, True
        start_angle = math.atan2(sy - cy, sx - cx)
        end_angle = math.atan2(ey - cy, ex - cx)
        sweep = (
            (start_angle - end_angle) % (2 * math.pi)
            if command == "G2"
            else (end_angle - start_angle) % (2 * math.pi)
        )
        if math.isclose(sweep, 0.0, abs_tol=1e-12):
            sweep = 2 * math.pi
    elif "R" in parameters:
        radius_parameter = parameters["R"] * unit_scale
        radius = abs(radius_parameter)
        chord = math.hypot(ex - sx, ey - sy)
        if radius <= 0 or chord <= 0 or chord > 2 * radius:
            return chord_3d, True
        sweep = 2 * math.asin(min(1.0, chord / (2 * radius)))
        if radius_parameter < 0:
            sweep = 2 * math.pi - sweep
    else:
        return chord_3d, True

    planar_length = radius * sweep
    return math.hypot(planar_length, ez - sz), False


def _iter_bounded_binary_lines(source: BinaryIO) -> Iterator[tuple[bytes, bool]]:
    while True:
        raw_line = source.readline(MAX_GCODE_LINE_BYTES + 1)
        if not raw_line:
            return
        oversized = len(raw_line) > MAX_GCODE_LINE_BYTES
        if oversized and not raw_line.endswith(b"\n"):
            while True:
                remainder = source.readline(GCODE_READ_CHUNK_BYTES)
                if not remainder or remainder.endswith(b"\n"):
                    break
        yield raw_line[:MAX_GCODE_LINE_BYTES], oversized


def _normalized_seconds(value: float) -> float:
    rounded = round(value, 6)
    return 0.0 if rounded == 0 else rounded
