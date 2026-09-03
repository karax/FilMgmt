from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GCodeTimeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_estimator_version: Literal[1]
    upload_id: UUID
    parser_version: int = Field(ge=1)
    estimated_time_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    source: Literal["slicer_metadata", "command_kinematics"] | None
    slicer_estimated_time_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    slicer_time_key: str | None = Field(default=None, max_length=64)
    kinematic_estimated_time_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    motion_time_seconds: float = Field(ge=0, allow_inf_nan=False)
    dwell_time_seconds: float = Field(ge=0, allow_inf_nan=False)
    kinematic_is_complete: bool
    unestimated_motion_count: int = Field(ge=0)
    is_heuristic: bool
    is_complete: bool
    warnings: list[str]
