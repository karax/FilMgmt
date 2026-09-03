from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GCodeToolSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: int = Field(ge=0)
    extrusion_length_mm: float | None
    extrusion_volume_mm3: float | None


class GCodeParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parser_version: Literal[1]
    upload_id: UUID
    filename: str
    source_size_bytes: int = Field(ge=0)
    line_count: int = Field(ge=0)
    blank_line_count: int = Field(ge=0)
    comment_line_count: int = Field(ge=0)
    command_line_count: int = Field(ge=0)
    unknown_line_count: int = Field(ge=0)
    malformed_line_count: int = Field(ge=0)
    command_counts: dict[str, int]
    units: Literal["mm", "in"]
    xyz_positioning: Literal["absolute", "relative"]
    extrusion_mode: Literal["absolute", "relative"]
    current_tool: int = Field(ge=0)
    tools: list[GCodeToolSummary]
    total_extrusion_length_mm: float | None
    total_extrusion_volume_mm3: float | None
    nozzle_temperatures_c: list[float]
    bed_temperatures_c: list[float]
    metadata: dict[str, str]
    warnings: list[str]
