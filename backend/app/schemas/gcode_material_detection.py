from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


MaterialDetectionSource = Literal["slicer_metadata", "temperature_heuristic"]
MaterialDetectionConfidence = Literal["HIGH", "MEDIUM", "LOW", "NONE"]


class GCodeMaterialCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: int = Field(gt=0)
    material_name: str


class GCodeMaterialEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata_key: str | None = Field(default=None, max_length=64)
    nozzle_temperatures_c: list[float]
    bed_temperatures_c: list[float]


class GCodeToolMaterialDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: int = Field(ge=0)
    material_id: int | None = Field(default=None, gt=0)
    material_name: str | None
    raw_material_label: str | None = Field(default=None, max_length=256)
    source: MaterialDetectionSource | None
    confidence: MaterialDetectionConfidence
    evidence: GCodeMaterialEvidence
    candidates: list[GCodeMaterialCandidate]
    warnings: list[str]


class GCodeMaterialDetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    parser_version: int = Field(ge=1)
    tools: list[GCodeToolMaterialDetection]
    is_complete: bool
    warnings: list[str]
