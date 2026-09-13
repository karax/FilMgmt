from collections.abc import Iterable
from dataclasses import dataclass, field
import logging
import math
import os
from pathlib import Path
import re
from typing import BinaryIO
from uuid import UUID

from app.schemas.gcode_parse import GCodeParseResult, GCodeToolSummary
from app.services.gcode_upload_service import GCodeUploadService
from app.services.gcode_upload_activity import storage_lock


logger = logging.getLogger(__name__)

PARSER_VERSION = 1
MAX_GCODE_LINE_BYTES = 64 * 1024
GCODE_READ_CHUNK_BYTES = 64 * 1024
MAX_METADATA_KEYS = 64
MAX_METADATA_KEY_LENGTH = 64
MAX_METADATA_VALUE_LENGTH = 256
MAX_COMMAND_COUNT_KEYS = 256
MAX_COMMAND_NAME_LENGTH = 64
MAX_TEMPERATURE_TARGETS = 32
MAX_TOOLS = 32
MAX_PARSE_CACHE_BYTES = 1024 * 1024

_NUMBER_PATTERN = r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?"
_PARAMETER_NUMBER_PATTERN = (
    r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))"
    r"(?:[eE][+-]\d+)?"
)
_LINE_NUMBER_RE = re.compile(r"^\s*N[+-]?\d+\s*", re.IGNORECASE)
_STANDARD_COMMAND_RE = re.compile(
    rf"^\s*(?P<letter>[GMT])\s*(?P<number>{_NUMBER_PATTERN})",
    re.IGNORECASE,
)
_VENDOR_COMMAND_RE = re.compile(
    r"^\s*(?P<command>[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)\b",
    re.IGNORECASE,
)
_PARAMETER_RE = re.compile(
    rf"(?P<letter>[A-Za-z])\s*(?P<number>{_PARAMETER_NUMBER_PATTERN})",
)
_CHECKSUM_RE = re.compile(r"\s*\*[+-]?\d+\s*$")
_PARENTHESIS_COMMENT_RE = re.compile(r"\(([^()]*)\)")
_METADATA_RE = re.compile(r"^\s*([^:=]+?)\s*[:=]\s*(.*?)\s*$")
_METADATA_KEY_RE = re.compile(r"^[A-Za-z0-9_. -]+$")
_THUMBNAIL_MARKER_RE = re.compile(
    r"^\s*(?:thumbnail(?:_[A-Za-z0-9]+)?|preview|image)\s+(begin|end)\b",
    re.IGNORECASE,
)

_SUPPORTED_COMMANDS = {
    "G0",
    "G1",
    "G2",
    "G3",
    "G20",
    "G21",
    "G90",
    "G91",
    "G92",
    "M82",
    "M83",
    "M104",
    "M109",
    "M140",
    "M190",
    "M200",
}
_EXTRUSION_COMMANDS = {"G0", "G1", "G2", "G3"}
_NOZZLE_TEMPERATURE_COMMANDS = {"M104", "M109"}
_BED_TEMPERATURE_COMMANDS = {"M140", "M190"}


class GCodeParseError(Exception):
    """Base exception for controlled G-code parsing failures."""


class GCodeBinaryFileError(GCodeParseError):
    pass


class GCodeParseStorageError(GCodeParseError):
    pass


@dataclass(frozen=True)
class ParsedGCodeLine:
    command: str | None
    parameters: dict[str, float]
    comment: str | None
    malformed: bool = False


@dataclass
class _ToolState:
    tool: int
    volumetric_enabled: bool = False
    linear_e_position_mm: float = 0.0
    volume_e_position_mm3: float = 0.0
    linear_retraction_debt_mm: float = 0.0
    volume_retraction_debt_mm3: float = 0.0
    extrusion_length_mm: float = 0.0
    extrusion_volume_mm3: float = 0.0
    linear_seen: bool = False
    volume_seen: bool = False


def parse_gcode_line(line: str) -> ParsedGCodeLine:
    """Parse one textual G-code line without applying file-level semantics."""
    if "\x00" in line:
        raise GCodeBinaryFileError("G-code contains NUL bytes.")

    raw = line.rstrip("\r\n")
    code, semicolon, semicolon_comment = raw.partition(";")
    parenthesis_comments = _PARENTHESIS_COMMENT_RE.findall(code)
    stripped_code = _PARENTHESIS_COMMENT_RE.sub(" ", code)
    unmatched_parenthesis = stripped_code.count("(") > 0 or stripped_code.count(")") > 0

    if semicolon:
        comment = semicolon_comment.strip()
    elif parenthesis_comments:
        comment = " ".join(part.strip() for part in parenthesis_comments if part.strip()) or None
    else:
        comment = None

    stripped_code = _CHECKSUM_RE.sub("", stripped_code)
    stripped_code = _LINE_NUMBER_RE.sub("", stripped_code, count=1)
    if not stripped_code.strip():
        return ParsedGCodeLine(None, {}, comment, unmatched_parenthesis)

    standard_match = _STANDARD_COMMAND_RE.match(stripped_code)
    if standard_match:
        if not math.isfinite(float(standard_match.group("number"))):
            return ParsedGCodeLine(None, {}, comment, True)
        command = _normalize_standard_command(
            standard_match.group("letter"),
            standard_match.group("number"),
        )
        remainder = stripped_code[standard_match.end():]
        parameters, malformed_parameters = _parse_parameters(remainder)
        return ParsedGCodeLine(
            command,
            parameters,
            comment,
            unmatched_parenthesis or malformed_parameters,
        )

    vendor_match = _VENDOR_COMMAND_RE.match(stripped_code)
    if vendor_match:
        return ParsedGCodeLine(
            vendor_match.group("command").upper(),
            {},
            comment,
            unmatched_parenthesis,
        )

    return ParsedGCodeLine(None, {}, comment, True)


class GenericGCodeParser:
    """Build a bounded summary while consuming G-code exactly once."""

    def parse_path(
        self,
        path: Path,
        *,
        upload_id: UUID,
        filename: str,
    ) -> GCodeParseResult:
        try:
            accumulator = _ParseAccumulator(
                upload_id=upload_id,
                filename=filename,
                source_size_bytes=path.stat().st_size,
            )
            with path.open("rb") as source:
                for raw_line, oversized in _iter_bounded_binary_lines(source):
                    try:
                        line = raw_line.decode("utf-8")
                    except UnicodeDecodeError:
                        line = raw_line.decode("utf-8", errors="replace")
                        accumulator.add_warning("encoding_replacement_detected")
                    accumulator.consume(line, oversized=oversized)
        except GCodeParseError:
            raise
        except OSError as error:
            raise GCodeParseStorageError("Could not read the uploaded G-code file.") from error
        return accumulator.result()

    def parse_lines(
        self,
        lines: Iterable[str],
        *,
        upload_id: UUID,
        filename: str,
        source_size_bytes: int = 0,
    ) -> GCodeParseResult:
        accumulator = _ParseAccumulator(
            upload_id=upload_id,
            filename=filename,
            source_size_bytes=source_size_bytes,
        )
        for line in lines:
            accumulator.consume(line)
        return accumulator.result()


class GCodeParseService:
    """Resolve immutable uploads, reuse versioned summaries, and cache atomically."""

    def __init__(
        self,
        upload_service: GCodeUploadService | None = None,
        parser: GenericGCodeParser | None = None,
    ) -> None:
        self.upload_service = upload_service or GCodeUploadService()
        self.parser = parser or GenericGCodeParser()

    def parse_upload(self, upload_id: str | UUID) -> GCodeParseResult:
        with self.upload_service.active_operation(upload_id):
            resolved = self.upload_service.resolve_upload(upload_id)
            cache_path = self.cache_path_for(resolved.path)
            cached = self._read_cache(cache_path)
            if cached is not None and self._cache_matches_upload(cached, resolved.metadata):
                return cached

            result = self.parser.parse_path(
                resolved.path,
                upload_id=resolved.metadata.upload_id,
                filename=resolved.metadata.filename,
            )
            self._write_cache(cache_path, result)
            return result

    @staticmethod
    def cache_path_for(upload_path: Path) -> Path:
        return upload_path.with_suffix(".parse.json")

    @staticmethod
    def _cache_matches_upload(result: GCodeParseResult, metadata: object) -> bool:
        upload_id = getattr(metadata, "upload_id", None)
        filename = getattr(metadata, "filename", None)
        size_bytes = getattr(metadata, "size_bytes", None)
        return (
            result.parser_version == PARSER_VERSION
            and result.upload_id == upload_id
            and result.filename == filename
            and result.source_size_bytes == size_bytes
        )

    @staticmethod
    def _read_cache(path: Path) -> GCodeParseResult | None:
        if not path.is_file() or path.is_symlink():
            return None
        try:
            if path.stat().st_size > MAX_PARSE_CACHE_BYTES:
                return None
            result = GCodeParseResult.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return result if result.parser_version == PARSER_VERSION else None

    def _write_cache(self, path: Path, result: GCodeParseResult) -> None:
        temporary_path = path.with_suffix(".json.uploading")
        contents = result.model_dump_json(indent=2)
        try:
            with storage_lock(path.parent):
                temporary_path.unlink(missing_ok=True)
                if not self.upload_service.storage_bytes_fit(len(contents.encode("utf-8"))):
                    logger.warning("Skipped G-code parse cache because storage quota is full")
                    return
                with temporary_path.open("x", encoding="utf-8") as destination:
                    destination.write(contents)
                    destination.flush()
                    os.fsync(destination.fileno())
                os.replace(temporary_path, path)
        except OSError as error:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise GCodeParseStorageError("Could not cache the G-code parse summary.") from error


@dataclass
class _ParseAccumulator:
    upload_id: UUID
    filename: str
    source_size_bytes: int
    line_count: int = 0
    blank_line_count: int = 0
    comment_line_count: int = 0
    command_line_count: int = 0
    unknown_line_count: int = 0
    malformed_line_count: int = 0
    command_counts: dict[str, int] = field(default_factory=dict)
    units: str = "mm"
    xyz_positioning: str = "absolute"
    extrusion_mode: str = "absolute"
    current_tool: int = 0
    tools: dict[int, _ToolState] = field(default_factory=dict)
    nozzle_temperatures_c: list[float] = field(default_factory=list)
    bed_temperatures_c: list[float] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    _warning_set: set[str] = field(default_factory=set)
    _units_seen: set[str] = field(default_factory=set)
    _extrusion_domains_seen: set[str] = field(default_factory=set)
    _inside_thumbnail: bool = False

    def consume(self, line: str, *, oversized: bool = False) -> None:
        self.line_count += 1
        if "\x00" in line:
            raise GCodeBinaryFileError("G-code contains NUL bytes.")

        if oversized:
            if self._inside_thumbnail:
                self.comment_line_count += 1
                return
            self.malformed_line_count += 1
            self.add_warning("malformed_lines_present")
            self.add_warning("oversized_line_ignored")
            return

        parsed = parse_gcode_line(line)
        if parsed.command is None:
            if parsed.comment is not None:
                self.comment_line_count += 1
                self._consume_comment(parsed.comment)
            elif line.strip():
                self.malformed_line_count += 1
                self.add_warning("malformed_lines_present")
            else:
                self.blank_line_count += 1
            if parsed.malformed and parsed.comment is not None:
                self.malformed_line_count += 1
                self.add_warning("malformed_lines_present")
            return

        self.command_line_count += 1
        if parsed.malformed:
            self.malformed_line_count += 1
            self.add_warning("malformed_lines_present")
        self._count_command(parsed.command)
        if not _is_supported_command(parsed.command):
            self.unknown_line_count += 1
            return

        self._apply_command(parsed.command, parsed.parameters)
        if parsed.comment is not None and not self._inside_thumbnail:
            self._consume_metadata(parsed.comment)

    def add_warning(self, warning: str) -> None:
        if warning in self._warning_set:
            return
        self._warning_set.add(warning)
        self.warnings.append(warning)

    def result(self) -> GCodeParseResult:
        tool_summaries = [
            GCodeToolSummary(
                tool=tool.tool,
                extrusion_length_mm=(
                    _normalized_float(tool.extrusion_length_mm)
                    if tool.linear_seen
                    else None
                ),
                extrusion_volume_mm3=(
                    _normalized_float(tool.extrusion_volume_mm3)
                    if tool.volume_seen
                    else None
                ),
            )
            for tool in sorted(self.tools.values(), key=lambda item: item.tool)
        ]
        linear_values = [
            tool.extrusion_length_mm for tool in self.tools.values() if tool.linear_seen
        ]
        volume_values = [
            tool.extrusion_volume_mm3 for tool in self.tools.values() if tool.volume_seen
        ]
        return GCodeParseResult(
            parser_version=PARSER_VERSION,
            upload_id=self.upload_id,
            filename=self.filename,
            source_size_bytes=self.source_size_bytes,
            line_count=self.line_count,
            blank_line_count=self.blank_line_count,
            comment_line_count=self.comment_line_count,
            command_line_count=self.command_line_count,
            unknown_line_count=self.unknown_line_count,
            malformed_line_count=self.malformed_line_count,
            command_counts=self.command_counts,
            units=self.units,
            xyz_positioning=self.xyz_positioning,
            extrusion_mode=self.extrusion_mode,
            current_tool=self.current_tool,
            tools=tool_summaries,
            total_extrusion_length_mm=(
                _normalized_float(sum(linear_values)) if linear_values else None
            ),
            total_extrusion_volume_mm3=(
                _normalized_float(sum(volume_values)) if volume_values else None
            ),
            nozzle_temperatures_c=self.nozzle_temperatures_c,
            bed_temperatures_c=self.bed_temperatures_c,
            metadata=self.metadata,
            warnings=self.warnings,
        )

    def _consume_comment(self, comment: str) -> None:
        marker = _THUMBNAIL_MARKER_RE.match(comment)
        if marker:
            self._inside_thumbnail = marker.group(1).lower() == "begin"
            return
        if not self._inside_thumbnail:
            self._consume_metadata(comment)

    def _consume_metadata(self, comment: str) -> None:
        match = _METADATA_RE.match(comment)
        if not match:
            return
        raw_key = " ".join(match.group(1).split())
        if not raw_key or not _METADATA_KEY_RE.fullmatch(raw_key):
            return
        key = raw_key.lower()
        value = match.group(2).strip()
        truncated = False
        if len(key) > MAX_METADATA_KEY_LENGTH:
            key = key[:MAX_METADATA_KEY_LENGTH]
            truncated = True
        if len(value) > MAX_METADATA_VALUE_LENGTH:
            value = value[:MAX_METADATA_VALUE_LENGTH]
            truncated = True
        if key not in self.metadata and len(self.metadata) >= MAX_METADATA_KEYS:
            self.add_warning("metadata_truncated")
            return
        self.metadata[key] = value
        if truncated:
            self.add_warning("metadata_truncated")

    def _count_command(self, command: str) -> None:
        bounded_command = command[:MAX_COMMAND_NAME_LENGTH]
        if bounded_command != command:
            self.add_warning("command_counts_truncated")
        if bounded_command in self.command_counts:
            self.command_counts[bounded_command] += 1
            return
        if len(self.command_counts) >= MAX_COMMAND_COUNT_KEYS:
            self.add_warning("command_counts_truncated")
            return
        self.command_counts[bounded_command] = 1

    def _apply_command(self, command: str, parameters: dict[str, float]) -> None:
        if command == "G20":
            self.units = "in"
            self._units_seen.add("in")
            self._warn_for_mixed_units()
            return
        if command == "G21":
            self.units = "mm"
            self._units_seen.add("mm")
            self._warn_for_mixed_units()
            return
        if command == "G90":
            self.xyz_positioning = "absolute"
            return
        if command == "G91":
            self.xyz_positioning = "relative"
            return
        if command == "M82":
            self.extrusion_mode = "absolute"
            return
        if command == "M83":
            self.extrusion_mode = "relative"
            return
        if command.startswith("T"):
            self._select_tool(int(command[1:]))
            return
        if command == "M200":
            self._apply_m200(parameters)
            return
        if command == "G92" and "E" in parameters:
            tool = self._current_tool_state()
            if tool is not None:
                self._mark_domain(tool)
                if tool.volumetric_enabled:
                    tool.volume_e_position_mm3 = parameters["E"]
                else:
                    tool.linear_e_position_mm = self._linear_to_mm(parameters["E"])
            return
        if command in _EXTRUSION_COMMANDS and "E" in parameters:
            self._units_seen.add(self.units)
            self._warn_for_mixed_units()
            tool = self._current_tool_state()
            if tool is not None:
                self._apply_extrusion(tool, parameters["E"])
            return
        if command in _NOZZLE_TEMPERATURE_COMMANDS:
            self._capture_temperatures(parameters, self.nozzle_temperatures_c)
            return
        if command in _BED_TEMPERATURE_COMMANDS:
            self._capture_temperatures(parameters, self.bed_temperatures_c)

    def _apply_m200(self, parameters: dict[str, float]) -> None:
        target_tool = int(parameters.get("T", self.current_tool))
        tool = self._tool_state(target_tool)
        if tool is None:
            return
        diameter = parameters.get("D")
        if diameter is None:
            self.add_warning("ambiguous_volumetric_extrusion_command")
            return
        if diameter > 0:
            tool.volumetric_enabled = True
            self.add_warning("volumetric_extrusion_detected")
        elif diameter == 0:
            tool.volumetric_enabled = False
        else:
            self.add_warning("malformed_lines_present")

    def _apply_extrusion(self, tool: _ToolState, commanded_e: float) -> None:
        self._mark_domain(tool)
        if tool.volumetric_enabled:
            delta = self._extrusion_delta(commanded_e, tool.volume_e_position_mm3)
            tool.volume_e_position_mm3 = (
                commanded_e
                if self.extrusion_mode == "absolute"
                else tool.volume_e_position_mm3 + commanded_e
            )
            consumed, debt = _consume_extrusion_delta(
                delta,
                tool.volume_retraction_debt_mm3,
            )
            tool.volume_retraction_debt_mm3 = debt
            tool.extrusion_volume_mm3 += consumed
            return

        value_mm = self._linear_to_mm(commanded_e)
        delta = self._extrusion_delta(value_mm, tool.linear_e_position_mm)
        tool.linear_e_position_mm = (
            value_mm
            if self.extrusion_mode == "absolute"
            else tool.linear_e_position_mm + value_mm
        )
        consumed, debt = _consume_extrusion_delta(delta, tool.linear_retraction_debt_mm)
        tool.linear_retraction_debt_mm = debt
        tool.extrusion_length_mm += consumed

    def _mark_domain(self, tool: _ToolState) -> None:
        if tool.volumetric_enabled:
            tool.volume_seen = True
            self._extrusion_domains_seen.add("volume")
        else:
            tool.linear_seen = True
            self._extrusion_domains_seen.add("linear")
        if len(self._extrusion_domains_seen) > 1:
            self.add_warning("mixed_extrusion_modes_detected")

    def _extrusion_delta(self, value: float, current_position: float) -> float:
        return value - current_position if self.extrusion_mode == "absolute" else value

    def _linear_to_mm(self, value: float) -> float:
        return value * 25.4 if self.units == "in" else value

    def _select_tool(self, tool_number: int) -> None:
        self.current_tool = tool_number
        self._tool_state(tool_number)

    def _current_tool_state(self) -> _ToolState | None:
        return self._tool_state(self.current_tool)

    def _tool_state(self, tool_number: int) -> _ToolState | None:
        if tool_number in self.tools:
            return self.tools[tool_number]
        if len(self.tools) >= MAX_TOOLS:
            self.add_warning("tools_truncated")
            return None
        state = _ToolState(tool=tool_number)
        self.tools[tool_number] = state
        return state

    def _capture_temperatures(
        self,
        parameters: dict[str, float],
        target: list[float],
    ) -> None:
        for key in ("S", "R"):
            value = parameters.get(key)
            if value is None or value in target:
                continue
            if len(target) >= MAX_TEMPERATURE_TARGETS:
                self.add_warning("temperature_targets_truncated")
                return
            target.append(_normalized_float(value))

    def _warn_for_mixed_units(self) -> None:
        if len(self._units_seen) > 1:
            self.add_warning("mixed_units_detected")


def _parse_parameters(remainder: str) -> tuple[dict[str, float], bool]:
    parameters: dict[str, float] = {}
    malformed = False
    cursor = 0
    for match in _PARAMETER_RE.finditer(remainder):
        if remainder[cursor:match.start()].strip():
            malformed = True
        value = float(match.group("number"))
        if math.isfinite(value):
            parameters[match.group("letter").upper()] = value
        else:
            malformed = True
        cursor = match.end()
    if remainder[cursor:].strip():
        malformed = True
    return parameters, malformed


def _normalize_standard_command(letter: str, raw_number: str) -> str:
    value = float(raw_number)
    if value.is_integer():
        number = str(int(value))
    else:
        number = format(value, "g").upper()
    return f"{letter.upper()}{number}"


def _is_supported_command(command: str) -> bool:
    return command in _SUPPORTED_COMMANDS or (
        command.startswith("T") and command[1:].isdigit()
    )


def _consume_extrusion_delta(delta: float, debt: float) -> tuple[float, float]:
    if delta < 0:
        return 0.0, debt + abs(delta)
    cancelled_debt = min(delta, debt)
    return delta - cancelled_debt, debt - cancelled_debt


def _iter_bounded_binary_lines(source: BinaryIO) -> Iterable[tuple[bytes, bool]]:
    while True:
        raw_line = source.readline(MAX_GCODE_LINE_BYTES + 1)
        if not raw_line:
            return
        if b"\x00" in raw_line:
            raise GCodeBinaryFileError("G-code contains NUL bytes.")

        oversized = len(raw_line) > MAX_GCODE_LINE_BYTES
        if oversized and not raw_line.endswith(b"\n"):
            while True:
                remainder = source.readline(GCODE_READ_CHUNK_BYTES)
                if b"\x00" in remainder:
                    raise GCodeBinaryFileError("G-code contains NUL bytes.")
                if not remainder or remainder.endswith(b"\n"):
                    break
        yield raw_line[:MAX_GCODE_LINE_BYTES], oversized


def _normalized_float(value: float) -> float:
    rounded = round(value, 6)
    return 0.0 if rounded == 0 else rounded
