from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Material
from app.schemas.gcode_parse import GCodeParseResult, GCodeToolSummary
from app.schemas.gcode_weight import (
    GCodeToolWeightResult,
    GCodeWeightRequest,
    GCodeWeightResult,
    GCodeWeightToolRequest,
)
from app.services.gcode_parser import GCodeParseService

PI = Decimal("3.1415926535897932384626433832795028841971693993751")
RESULT_QUANTUM = Decimal("0.001")
MAX_FILAMENT_DIAMETER_MM = Decimal("20")
MAX_DENSITY_G_CM3 = Decimal("10")


class GCodeWeightInvalidToolError(Exception):
    pass


class GCodeWeightMaterialNotFoundError(Exception):
    def __init__(self, material_id: int) -> None:
        self.material_id = material_id
        super().__init__(f"Material {material_id} was not found.")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(RESULT_QUANTUM, rounding=ROUND_HALF_UP)


def _linear_volume_mm3(length_mm: Decimal, diameter_mm: Decimal) -> Decimal:
    radius_mm = diameter_mm / Decimal("2")
    return length_mm * PI * radius_mm * radius_mm


def _weight_g(volume_mm3: Decimal, density_g_cm3: Decimal) -> Decimal:
    return volume_mm3 * density_g_cm3 / Decimal("1000")


class GCodeWeightService:
    """Estimate per-tool mass from the bounded TASK-043 parse summary."""

    def __init__(self, db: Session, parse_service: GCodeParseService) -> None:
        self.db = db
        self.parse_service = parse_service

    def calculate_upload(
        self,
        upload_id: str | UUID,
        request: GCodeWeightRequest,
    ) -> GCodeWeightResult:
        summary = self.parse_service.parse_upload(upload_id)
        configurations = {item.tool: item for item in request.tools}
        parsed_tools = {item.tool for item in summary.tools}
        unknown_tools = sorted(set(configurations) - parsed_tools)
        if unknown_tools:
            joined = ", ".join(f"T{tool}" for tool in unknown_tools)
            raise GCodeWeightInvalidToolError(
                f"The requested tools are not present in the G-code: {joined}."
            )

        material_ids = {
            item.material_id for item in request.tools if item.material_id is not None
        }
        materials: dict[int, Material] = {}
        for material_id in material_ids:
            material = self.db.get(Material, material_id)
            if material is None:
                raise GCodeWeightMaterialNotFoundError(material_id)
            materials[material_id] = material

        diameter_metadata, diameter_metadata_invalid = _metadata_values(
            summary,
            ("filament_diameter_mm", "filament_diameter"),
            maximum=MAX_FILAMENT_DIAMETER_MM,
        )
        density_metadata, density_metadata_invalid = _metadata_values(
            summary,
            ("filament_density",),
            maximum=MAX_DENSITY_G_CM3,
        )

        results = [
            self._calculate_tool(
                tool,
                configurations.get(tool.tool),
                materials,
                diameter_metadata,
                density_metadata,
            )
            for tool in summary.tools
        ]
        known_weight = sum(
            (item.estimated_weight_g for item in results if item.estimated_weight_g is not None),
            Decimal("0"),
        )
        is_complete = all(item.estimated_weight_g is not None for item in results)
        warnings = _deduplicate(
            warning for item in results for warning in item.warnings
        )
        if diameter_metadata_invalid or density_metadata_invalid:
            warnings.append("metadata_value_invalid")
        if not is_complete:
            warnings.append("incomplete_weight_estimate")

        return GCodeWeightResult(
            upload_id=summary.upload_id,
            parser_version=summary.parser_version,
            tools=results,
            total_estimated_weight_g=_quantize(known_weight) if is_complete else None,
            known_estimated_weight_g=_quantize(known_weight),
            is_complete=is_complete,
            warnings=warnings,
        )

    @staticmethod
    def _calculate_tool(
        tool: GCodeToolSummary,
        configuration: GCodeWeightToolRequest | None,
        materials: dict[int, Material],
        diameter_metadata: list[Decimal],
        density_metadata: list[Decimal],
    ) -> GCodeToolWeightResult:
        with localcontext() as context:
            context.prec = 36
            length = _decimal_or_none(tool.extrusion_length_mm)
            provided_volume = _decimal_or_none(tool.extrusion_volume_mm3)
            extrusion_mode = _extrusion_mode(length, provided_volume)
            warnings: list[str] = []

            material = (
                materials.get(configuration.material_id)
                if configuration is not None and configuration.material_id is not None
                else None
            )
            density, density_source = _resolve_density(
                tool.tool,
                material,
                density_metadata,
            )
            diameter, diameter_source = _resolve_diameter(
                tool.tool,
                configuration,
                diameter_metadata,
            )

            if extrusion_mode == "none":
                calculated_volume = Decimal("0")
                estimated_weight = Decimal("0")
            else:
                calculated_volume = provided_volume or Decimal("0")
                if length is not None:
                    if diameter is None:
                        warnings.append("missing_filament_diameter")
                    else:
                        calculated_volume += _linear_volume_mm3(length, diameter)
                if density is None:
                    warnings.append("missing_density")
                estimated_weight = (
                    _quantize(_weight_g(calculated_volume, density))
                    if density is not None
                    and not (length is not None and diameter is None)
                    else None
                )

            if extrusion_mode == "mixed":
                warnings.append("mixed_extrusion_modes")

            return GCodeToolWeightResult(
                tool=tool.tool,
                material_id=material.id if material is not None else None,
                material_name=material.name if material is not None else None,
                extrusion_mode=extrusion_mode,
                extrusion_length_mm=_quantize(length) if length is not None else None,
                extrusion_volume_mm3=(
                    _quantize(provided_volume) if provided_volume is not None else None
                ),
                calculated_volume_mm3=_quantize(calculated_volume),
                filament_diameter_mm=diameter,
                diameter_source=diameter_source,
                density_g_cm3=density,
                density_source=density_source,
                estimated_weight_g=estimated_weight,
                warnings=_deduplicate(warnings),
            )


def _resolve_density(
    tool: int,
    material: Material | None,
    metadata_values: list[Decimal],
) -> tuple[Decimal | None, Literal["material", "gcode_metadata", "not_available"]]:
    if material is not None:
        if material.density_g_cm3 is not None:
            return Decimal(str(material.density_g_cm3)), "material"
        return None, "not_available"
    metadata = _metadata_for_tool(metadata_values, tool)
    return (metadata, "gcode_metadata") if metadata is not None else (None, "not_available")


def _resolve_diameter(
    tool: int,
    configuration: GCodeWeightToolRequest | None,
    metadata_values: list[Decimal],
) -> tuple[Decimal | None, Literal["request", "gcode_metadata", "not_available"]]:
    if configuration is not None and configuration.filament_diameter_mm is not None:
        return configuration.filament_diameter_mm, "request"
    metadata = _metadata_for_tool(metadata_values, tool)
    return (metadata, "gcode_metadata") if metadata is not None else (None, "not_available")


def _metadata_values(
    summary: GCodeParseResult,
    keys: tuple[str, ...],
    *,
    maximum: Decimal,
) -> tuple[list[Decimal], bool]:
    raw = next((summary.metadata[key] for key in keys if key in summary.metadata), None)
    if raw is None:
        return [], False
    values: list[Decimal] = []
    for part in raw.split(","):
        try:
            value = Decimal(part.strip())
        except InvalidOperation:
            return [], True
        if not value.is_finite() or value <= 0 or value > maximum:
            return [], True
        values.append(value)
    return values, False


def _metadata_for_tool(values: list[Decimal], tool: int) -> Decimal | None:
    if len(values) == 1:
        return values[0]
    return values[tool] if 0 <= tool < len(values) else None


def _decimal_or_none(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _extrusion_mode(
    length: Decimal | None,
    volume: Decimal | None,
) -> Literal["linear", "volumetric", "mixed", "none"]:
    if length is not None and volume is not None:
        return "mixed"
    if length is not None:
        return "linear"
    if volume is not None:
        return "volumetric"
    return "none"


def _deduplicate(values) -> list[str]:
    return list(dict.fromkeys(values))
