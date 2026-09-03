from dataclasses import dataclass
import math
import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Material
from app.schemas.gcode_material_detection import (
    GCodeMaterialCandidate,
    GCodeMaterialDetectionResult,
    GCodeMaterialEvidence,
    GCodeToolMaterialDetection,
)
from app.schemas.gcode_parse import GCodeParseResult, GCodeToolSummary
from app.services.gcode_parser import GCodeParseService
from app.services.material_service import MaterialService

MAX_MATERIAL_CANDIDATES = 3
_PRIMARY_METADATA_KEYS = (
    "filament_type",
    "material_type",
    "filament_material",
    "material",
)
_PROFILE_METADATA_KEY = "filament_settings_id"
_LABEL_SEPARATOR_RE = re.compile(r"[;,]")


@dataclass(frozen=True)
class _ExplicitLabel:
    raw: str
    metadata_key: str
    from_profile: bool


@dataclass(frozen=True)
class _RankedMaterial:
    material: Material
    matched_dimensions: int
    center_distance: float


class GCodeMaterialDetectionService:
    """Detect per-tool material from a parse summary and the live catalog."""

    def __init__(self, db: Session, parse_service: GCodeParseService) -> None:
        self.db = db
        self.parse_service = parse_service

    def detect_upload(self, upload_id: str | UUID) -> GCodeMaterialDetectionResult:
        summary = self.parse_service.parse_upload(upload_id)
        materials = MaterialService(self.db).list_materials()
        labels, label_warnings = _explicit_labels(summary)
        nozzle_temperatures = _usable_temperatures(summary.nozzle_temperatures_c)
        bed_temperatures = _usable_temperatures(summary.bed_temperatures_c)
        evidence_temperatures = GCodeMaterialEvidence(
            metadata_key=None,
            nozzle_temperatures_c=nozzle_temperatures,
            bed_temperatures_c=bed_temperatures,
        )
        active_tools = {tool.tool for tool in summary.tools if _tool_extrudes(tool)}
        global_temperature_is_ambiguous = len(active_tools) > 1

        results: list[GCodeToolMaterialDetection] = []
        for tool in summary.tools:
            explicit = labels.get(tool.tool)
            if explicit is not None:
                result = _detect_explicit(
                    tool.tool,
                    explicit,
                    materials,
                    nozzle_temperatures,
                    bed_temperatures,
                )
            elif tool.tool not in active_tools:
                result = _unknown_detection(tool.tool, evidence_temperatures)
            elif global_temperature_is_ambiguous:
                result = _unknown_detection(
                    tool.tool,
                    evidence_temperatures,
                    warning="multi_tool_temperature_ambiguous",
                )
            else:
                result = _detect_temperature(
                    tool.tool,
                    materials,
                    nozzle_temperatures,
                    bed_temperatures,
                )
            results.append(result)

        warnings = list(label_warnings)
        warnings.extend(warning for result in results for warning in result.warnings)
        active_results = [result for result in results if result.tool in active_tools]
        is_complete = all(_is_sufficient_detection(result) for result in active_results)
        return GCodeMaterialDetectionResult(
            upload_id=summary.upload_id,
            parser_version=summary.parser_version,
            tools=results,
            is_complete=is_complete,
            warnings=list(dict.fromkeys(warnings)),
        )


def _explicit_labels(
    summary: GCodeParseResult,
) -> tuple[dict[int, _ExplicitLabel], list[str]]:
    tools = sorted(tool.tool for tool in summary.tools)
    labels: dict[int, _ExplicitLabel] = {}
    warnings: list[str] = []

    for base_key in (*_PRIMARY_METADATA_KEYS, _PROFILE_METADATA_KEY):
        from_profile = base_key == _PROFILE_METADATA_KEY
        for tool in tools:
            indexed_key = f"{base_key}_{tool}"
            raw = summary.metadata.get(indexed_key)
            if raw is None:
                continue
            values = _split_labels(raw)
            if len(values) != 1:
                warnings.append("ambiguous_material")
                continue
            _assign_label(
                labels,
                tool,
                _ExplicitLabel(values[0], indexed_key, from_profile),
                warnings,
            )

        raw = summary.metadata.get(base_key)
        if raw is None:
            continue
        values = _split_labels(raw)
        assignments: dict[int, str] = {}
        if len(values) == 1 and len(tools) == 1:
            assignments[tools[0]] = values[0]
        elif (
            len(values) == len(tools)
            and tools == list(range(len(tools)))
        ):
            assignments = {tool: values[tool] for tool in tools}
        else:
            warnings.append("ambiguous_material")
        for tool, value in assignments.items():
            _assign_label(
                labels,
                tool,
                _ExplicitLabel(value, base_key, from_profile),
                warnings,
            )

    return labels, list(dict.fromkeys(warnings))


def _assign_label(
    labels: dict[int, _ExplicitLabel],
    tool: int,
    label: _ExplicitLabel,
    warnings: list[str],
) -> None:
    existing = labels.get(tool)
    if existing is None:
        labels[tool] = label
    elif _normalize_label(existing.raw) != _normalize_label(label.raw):
        warnings.append("ambiguous_material")


def _split_labels(raw: str) -> list[str]:
    return [value.strip() for value in _LABEL_SEPARATOR_RE.split(raw) if value.strip()]


def _detect_explicit(
    tool: int,
    explicit: _ExplicitLabel,
    materials: list[Material],
    nozzle_temperatures: list[float],
    bed_temperatures: list[float],
) -> GCodeToolMaterialDetection:
    exact_matches = [
        material
        for material in materials
        if _normalize_label(material.name) == _normalize_label(explicit.raw)
    ]
    matched = exact_matches[0] if len(exact_matches) == 1 else None
    confidence = "HIGH"
    warnings: list[str] = []

    if matched is None and explicit.from_profile:
        matched = _profile_material_match(explicit.raw, materials)
        if matched is not None:
            confidence = "MEDIUM"
    if matched is None:
        warnings.append("explicit_material_not_in_catalog")
    elif _temperature_conflicts(matched, nozzle_temperatures, bed_temperatures):
        warnings.append("temperature_metadata_mismatch")

    return GCodeToolMaterialDetection(
        tool=tool,
        material_id=matched.id if matched is not None else None,
        material_name=matched.name if matched is not None else None,
        raw_material_label=explicit.raw,
        source="slicer_metadata",
        confidence=confidence,
        evidence=GCodeMaterialEvidence(
            metadata_key=explicit.metadata_key,
            nozzle_temperatures_c=nozzle_temperatures,
            bed_temperatures_c=bed_temperatures,
        ),
        candidates=[],
        warnings=warnings,
    )


def _profile_material_match(raw: str, materials: list[Material]) -> Material | None:
    normalized_raw = _normalize_label(raw)
    matches: list[Material] = []
    for material in materials:
        normalized_name = _normalize_label(material.name)
        pattern = rf"(?<![a-z0-9+\-]){re.escape(normalized_name)}(?![a-z0-9+\-])"
        if re.search(pattern, normalized_raw):
            matches.append(material)
    if not matches:
        return None
    longest = max(len(_normalize_label(material.name)) for material in matches)
    longest_matches = [
        material for material in matches if len(_normalize_label(material.name)) == longest
    ]
    return longest_matches[0] if len(longest_matches) == 1 else None


def _detect_temperature(
    tool: int,
    materials: list[Material],
    nozzle_temperatures: list[float],
    bed_temperatures: list[float],
) -> GCodeToolMaterialDetection:
    evidence = GCodeMaterialEvidence(
        metadata_key=None,
        nozzle_temperatures_c=nozzle_temperatures,
        bed_temperatures_c=bed_temperatures,
    )
    if not nozzle_temperatures and not bed_temperatures:
        return _unknown_detection(
            tool,
            evidence,
            warning="insufficient_temperature_data",
        )

    nozzle = max(nozzle_temperatures) if nozzle_temperatures else None
    bed = max(bed_temperatures) if bed_temperatures else None
    ranked = [
        match
        for material in materials
        if (match := _rank_temperature_match(material, nozzle, bed)) is not None
    ]
    ranked.sort(
        key=lambda item: (
            -item.matched_dimensions,
            item.center_distance,
            item.material.name.casefold(),
            item.material.id,
        )
    )
    if not ranked:
        return _unknown_detection(
            tool,
            evidence,
            warning="insufficient_temperature_data",
        )

    top_dimensions = ranked[0].matched_dimensions
    top_matches = [item for item in ranked if item.matched_dimensions == top_dimensions]
    if nozzle is not None and bed is not None and top_dimensions == 2 and len(top_matches) == 1:
        material = top_matches[0].material
        return GCodeToolMaterialDetection(
            tool=tool,
            material_id=material.id,
            material_name=material.name,
            raw_material_label=None,
            source="temperature_heuristic",
            confidence="MEDIUM",
            evidence=evidence,
            candidates=[],
            warnings=[],
        )

    candidates = [
        GCodeMaterialCandidate(
            material_id=item.material.id,
            material_name=item.material.name,
        )
        for item in ranked[:MAX_MATERIAL_CANDIDATES]
    ]
    return GCodeToolMaterialDetection(
        tool=tool,
        material_id=None,
        material_name=None,
        raw_material_label=None,
        source="temperature_heuristic",
        confidence="LOW",
        evidence=evidence,
        candidates=candidates,
        warnings=["ambiguous_material"],
    )


def _rank_temperature_match(
    material: Material,
    nozzle: float | None,
    bed: float | None,
) -> _RankedMaterial | None:
    matched_dimensions = 0
    center_distance = 0.0
    for observed, minimum, maximum in (
        (nozzle, material.default_nozzle_temp_min, material.default_nozzle_temp_max),
        (bed, material.default_bed_temp_min, material.default_bed_temp_max),
    ):
        if observed is None:
            continue
        if minimum is None or maximum is None:
            continue
        if observed < minimum or observed > maximum:
            return None
        matched_dimensions += 1
        center_distance += abs(observed - ((minimum + maximum) / 2))
    if matched_dimensions == 0:
        return None
    return _RankedMaterial(material, matched_dimensions, center_distance)


def _temperature_conflicts(
    material: Material,
    nozzle_temperatures: list[float],
    bed_temperatures: list[float],
) -> bool:
    for observed, minimum, maximum in (
        (
            max(nozzle_temperatures) if nozzle_temperatures else None,
            material.default_nozzle_temp_min,
            material.default_nozzle_temp_max,
        ),
        (
            max(bed_temperatures) if bed_temperatures else None,
            material.default_bed_temp_min,
            material.default_bed_temp_max,
        ),
    ):
        if observed is not None and minimum is not None and maximum is not None:
            if observed < minimum or observed > maximum:
                return True
    return False


def _unknown_detection(
    tool: int,
    evidence: GCodeMaterialEvidence,
    *,
    warning: str | None = None,
) -> GCodeToolMaterialDetection:
    return GCodeToolMaterialDetection(
        tool=tool,
        material_id=None,
        material_name=None,
        raw_material_label=None,
        source=None,
        confidence="NONE",
        evidence=evidence,
        candidates=[],
        warnings=[warning] if warning else [],
    )


def _tool_extrudes(tool: GCodeToolSummary) -> bool:
    return (
        tool.extrusion_length_mm is not None and tool.extrusion_length_mm > 0
    ) or (
        tool.extrusion_volume_mm3 is not None and tool.extrusion_volume_mm3 > 0
    )


def _is_sufficient_detection(result: GCodeToolMaterialDetection) -> bool:
    if result.confidence == "HIGH":
        return result.raw_material_label is not None
    return result.confidence == "MEDIUM" and result.material_id is not None


def _usable_temperatures(values: list[float]) -> list[float]:
    return [value for value in values if math.isfinite(value) and 0 < value <= 500]


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().casefold().split())
