from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


FilamentDiameter = Decimal


class GCodeWeightToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: int = Field(ge=0)
    material_id: int | None = Field(default=None, gt=0)
    filament_diameter_mm: FilamentDiameter | None = Field(
        default=None,
        gt=0,
        le=Decimal("20"),
        allow_inf_nan=False,
    )


class GCodeWeightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tools: list[GCodeWeightToolRequest] = Field(default_factory=list)

    @model_validator(mode="after")
    def tools_must_be_unique(self) -> Self:
        tool_numbers = [item.tool for item in self.tools]
        if len(tool_numbers) != len(set(tool_numbers)):
            raise ValueError("Each tool may be configured only once.")
        return self


class GCodeToolWeightResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: int = Field(ge=0)
    material_id: int | None
    material_name: str | None
    extrusion_mode: Literal["linear", "volumetric", "mixed", "none"]
    extrusion_length_mm: Decimal | None
    extrusion_volume_mm3: Decimal | None
    calculated_volume_mm3: Decimal
    filament_diameter_mm: Decimal | None
    diameter_source: Literal["request", "gcode_metadata", "not_available"]
    density_g_cm3: Decimal | None
    density_source: Literal["material", "gcode_metadata", "not_available"]
    estimated_weight_g: Decimal | None
    warnings: list[str]


class GCodeWeightResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    parser_version: int = Field(ge=1)
    tools: list[GCodeToolWeightResult]
    total_estimated_weight_g: Decimal | None
    known_estimated_weight_g: Decimal
    is_complete: bool
    warnings: list[str]
