"""Defensive metadata-only parser for Bambu print-ready 3MF archives."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET
import zipfile


PARSER_VERSION = "1"
MAX_ARCHIVE_ENTRIES = 2048
MAX_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_MEMBER_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_THUMBNAIL_BYTES = 10 * 1024 * 1024


class Bambu3mfError(Exception):
    error_code = "INVALID_3MF"


class Bambu3mfUnsafeArchiveError(Bambu3mfError):
    error_code = "UNSAFE_ARCHIVE"


class Bambu3mfArchiveTooLargeError(Bambu3mfError):
    error_code = "ARCHIVE_TOO_LARGE"


class Bambu3mfMalformedMetadataError(Bambu3mfError):
    error_code = "MALFORMED_METADATA"


class Bambu3mfMetadataMissingError(Bambu3mfError):
    error_code = "SLICE_INFO_MISSING"


class Bambu3mfAmbiguousPlateError(Bambu3mfError):
    error_code = "AMBIGUOUS_PLATE"


@dataclass(frozen=True)
class BambuParsedFilamentUsage:
    source_filament_id: str | None
    material_type: str | None
    color: str | None
    used_g: Decimal | None
    used_m: Decimal | None
    tray_info_idx: str | None
    used_for_object: bool | None
    used_for_support: bool | None
    nozzle_diameter: Decimal | None
    group_id: str | None


@dataclass(frozen=True)
class BambuParsed3mf:
    plate_index: int | None
    plate_name: str | None
    plate_selection_confidence: str
    slicer_estimated_duration_seconds: int | None
    filaments: tuple[BambuParsedFilamentUsage, ...]
    thumbnail_bytes: bytes | None
    thumbnail_member: str | None


@dataclass(frozen=True)
class _Plate:
    index: int | None
    metadata: dict[str, str]
    filaments: tuple[BambuParsedFilamentUsage, ...]


@dataclass(frozen=True)
class _ModelPlate:
    index: int | None
    name: str | None
    gcode_file: str | None
    thumbnail_file: str | None


class Bambu3mfParser:
    def parse(self, archive_path: Path, *, plate_hint: int | None = None) -> BambuParsed3mf:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                members = self._validate_archive(archive)
                slice_xml = self._read_member(archive, members, "Metadata/slice_info.config", MAX_METADATA_BYTES)
                if slice_xml is None:
                    raise Bambu3mfMetadataMissingError("slice_info.config is missing")
                slice_plates = _parse_slice_info(slice_xml)
                if not slice_plates:
                    raise Bambu3mfMalformedMetadataError("slice_info.config contains no plate")
                model_xml = self._read_member(archive, members, "Metadata/model_settings.config", MAX_METADATA_BYTES)
                model_plates = _parse_model_settings(model_xml) if model_xml is not None else ()
                sequence_json = self._read_member(archive, members, "Metadata/filament_sequence.json", MAX_METADATA_BYTES)
                selected, confidence = _select_plate(slice_plates, model_plates, sequence_json, plate_hint)
                model_plate = next((plate for plate in model_plates if plate.index == selected.index), None)
                thumbnail_member = _thumbnail_member(selected.index, model_plate, members)
                thumbnail = self._read_member(archive, members, thumbnail_member, MAX_THUMBNAIL_BYTES) if thumbnail_member else None
                if thumbnail is not None and not thumbnail.startswith(b"\x89PNG\r\n\x1a\n"):
                    thumbnail = None
                    thumbnail_member = None
                return BambuParsed3mf(
                    plate_index=selected.index,
                    plate_name=model_plate.name if model_plate else None,
                    plate_selection_confidence=confidence,
                    slicer_estimated_duration_seconds=_integer(selected.metadata.get("prediction")),
                    filaments=selected.filaments,
                    thumbnail_bytes=thumbnail,
                    thumbnail_member=thumbnail_member,
                )
        except Bambu3mfError:
            raise
        except (zipfile.BadZipFile, OSError) as error:
            raise Bambu3mfError("invalid 3MF archive") from error

    def _validate_archive(self, archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise Bambu3mfArchiveTooLargeError("too many archive entries")
        total_size = 0
        members: dict[str, zipfile.ZipInfo] = {}
        for entry in entries:
            name = entry.filename
            path = PurePosixPath(name)
            if "\x00" in name or "\\" in name or path.is_absolute() or ".." in path.parts:
                raise Bambu3mfUnsafeArchiveError("unsafe archive path")
            if entry.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
                raise Bambu3mfArchiveTooLargeError("archive member is too large")
            total_size += entry.file_size
            if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise Bambu3mfArchiveTooLargeError("archive expands beyond the safe limit")
            members[name] = entry
        return members

    @staticmethod
    def _read_member(
        archive: zipfile.ZipFile,
        members: dict[str, zipfile.ZipInfo],
        name: str,
        limit: int,
    ) -> bytes | None:
        entry = members.get(name)
        if entry is None:
            return None
        if entry.file_size > limit:
            raise Bambu3mfArchiveTooLargeError(f"{name} exceeds its safe limit")
        with archive.open(entry) as source:
            contents = source.read(limit + 1)
        if len(contents) > limit:
            raise Bambu3mfArchiveTooLargeError(f"{name} exceeds its safe limit")
        return contents


def _parse_slice_info(contents: bytes) -> tuple[_Plate, ...]:
    root = _xml_root(contents)
    plates: list[_Plate] = []
    for element in root.iter():
        if _local_name(element.tag) != "plate":
            continue
        metadata = {
            child.attrib.get("key", ""): child.attrib.get("value", "")
            for child in element
            if _local_name(child.tag) == "metadata" and child.attrib.get("key")
        }
        filaments = tuple(
            BambuParsedFilamentUsage(
                source_filament_id=child.attrib.get("id"),
                material_type=child.attrib.get("type"),
                color=child.attrib.get("color"),
                used_g=_decimal(child.attrib.get("used_g")),
                used_m=_decimal(child.attrib.get("used_m")),
                tray_info_idx=child.attrib.get("tray_info_idx"),
                used_for_object=_boolean(child.attrib.get("used_for_object")),
                used_for_support=_boolean(child.attrib.get("used_for_support")),
                nozzle_diameter=_decimal(child.attrib.get("nozzle_diameter")),
                group_id=child.attrib.get("group_id"),
            )
            for child in element
            if _local_name(child.tag) == "filament"
        )
        plates.append(_Plate(index=_integer(metadata.get("index")), metadata=metadata, filaments=filaments))
    return tuple(plates)


def _parse_model_settings(contents: bytes) -> tuple[_ModelPlate, ...]:
    root = _xml_root(contents)
    plates: list[_ModelPlate] = []
    for element in root.iter():
        if _local_name(element.tag) != "plate":
            continue
        metadata = {
            child.attrib.get("key", ""): child.attrib.get("value", "")
            for child in element
            if _local_name(child.tag) == "metadata" and child.attrib.get("key")
        }
        plates.append(
            _ModelPlate(
                index=_integer(metadata.get("plater_id") or metadata.get("index")),
                name=metadata.get("plater_name") or None,
                gcode_file=metadata.get("gcode_file") or None,
                thumbnail_file=metadata.get("thumbnail_file") or None,
            )
        )
    return tuple(plates)


def _select_plate(
    slice_plates: tuple[_Plate, ...],
    model_plates: tuple[_ModelPlate, ...],
    sequence_json: bytes | None,
    plate_hint: int | None,
) -> tuple[_Plate, str]:
    if len(slice_plates) == 1:
        return slice_plates[0], "EXACT"
    if plate_hint is not None:
        matches = [plate for plate in slice_plates if plate.index == plate_hint]
        if len(matches) == 1:
            return matches[0], "EXACT"
    gcode_indexes = {plate.index for plate in model_plates if plate.index is not None and plate.gcode_file}
    matches = [plate for plate in slice_plates if plate.index in gcode_indexes]
    if len(matches) == 1:
        return matches[0], "HIGH_CONFIDENCE"
    sequence_indexes = _active_sequence_indexes(sequence_json)
    matches = [plate for plate in slice_plates if plate.index in sequence_indexes]
    if len(matches) == 1:
        return matches[0], "HIGH_CONFIDENCE"
    raise Bambu3mfAmbiguousPlateError("printed plate cannot be determined")


def _active_sequence_indexes(contents: bytes | None) -> set[int]:
    if contents is None:
        return set()
    try:
        document = json.loads(contents)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return set()
    if not isinstance(document, dict):
        return set()
    result: set[int] = set()
    for key, value in document.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        match = re.fullmatch(r"plate_(\d+)", key)
        if match and any(value.get(field) for field in ("sequence", "nozzle_sequence", "optimal_assignment")):
            result.add(int(match.group(1)))
    return result


def _thumbnail_member(
    plate_index: int | None,
    model_plate: _ModelPlate | None,
    members: dict[str, zipfile.ZipInfo],
) -> str | None:
    candidates: list[str] = []
    if model_plate and model_plate.thumbnail_file:
        candidates.append(model_plate.thumbnail_file)
    if plate_index is not None:
        candidates.append(f"Metadata/plate_{plate_index}.png")
    candidates.append("Metadata/bbl_thumbnail.png")
    for candidate in candidates:
        path = PurePosixPath(candidate)
        if path.parts[:1] == ("Metadata",) and path.suffix.casefold() == ".png" and candidate in members:
            return candidate
    return None


def _xml_root(contents: bytes) -> ET.Element:
    lowered = contents[:4096].lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise Bambu3mfMalformedMetadataError("XML entities are not allowed")
    try:
        return ET.fromstring(contents)
    except ET.ParseError as error:
        raise Bambu3mfMalformedMetadataError("metadata XML is malformed") from error


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _decimal(value: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        result = Decimal(value.strip().replace(",", "."))
    except InvalidOperation:
        return None
    return result if result.is_finite() and result >= 0 else None


def _integer(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _boolean(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None
