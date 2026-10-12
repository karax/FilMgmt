from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.calibration import CalibrationEventType, TareConfidence, TareSource
from app.schemas.common import UtcDatetime


Weight = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=3)]
ProfileName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
IdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=64)]


class TareProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProfileName
    manufacturer: ProfileName | None = None
    spool_type: ProfileName | None = None
    description: OptionalText | None = None
    tare_g: Weight
    source: TareSource
    confidence: TareConfidence | None = None


class TareProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProfileName | None = None
    manufacturer: ProfileName | None = None
    spool_type: ProfileName | None = None
    description: OptionalText | None = None
    tare_g: Weight | None = None
    source: TareSource | None = None
    confidence: TareConfidence | None = None
    archived: bool | None = None


class TareProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: str
    manufacturer: str | None
    spool_type: str | None
    description: str | None
    tare_g: Decimal
    source: TareSource
    confidence: TareConfidence
    measured_sample_count: int
    measured_min_g: Decimal | None
    measured_max_g: Decimal | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
    archived_at: UtcDatetime | None


class CalibrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measured_total_g: Weight
    tare_profile_id: Annotated[int, Field(gt=0)] | None = None
    tare_g: Weight | None = None
    tare_source: TareSource | None = None
    tare_confidence: TareConfidence | None = None
    note: OptionalText | None = None

    @model_validator(mode="after")
    def validate_tare_selection(self) -> Self:
        if self.tare_profile_id is not None:
            if any(value is not None for value in (self.tare_g, self.tare_source, self.tare_confidence)):
                raise ValueError("profile tare cannot be combined with manual tare fields")
        elif self.tare_g is None or self.tare_source is None:
            raise ValueError("select a tare profile or provide tare_g and tare_source")
        return self


class CalibrationPreviewRequest(CalibrationInput):
    pass


class CalibrationConfirmRequest(CalibrationInput):
    idempotency_key: IdempotencyKey
    expected_current_remaining_g: Weight


class PendingPrintWarning(BaseModel):
    print_job_id: int
    name: str | None
    printed_at: UtcDatetime | None


class CalibrationPreviewRead(BaseModel):
    measured_total_g: Decimal
    tare_g: Decimal
    calculated_filament_g: Decimal
    current_remaining_g: Decimal
    adjustment_g: Decimal
    tare_source: TareSource
    tare_confidence: TareConfidence
    tare_profile_id: int | None
    is_estimated: bool
    unreconciled_prints: list[PendingPrintWarning]


class CalibrationRead(BaseModel):
    id: int
    spool_id: int
    event_type: CalibrationEventType
    measured_total_g: Decimal | None
    tare_g_used: Decimal | None
    calculated_filament_g: Decimal | None
    previous_remaining_g: Decimal
    adjustment_g: Decimal
    new_remaining_g: Decimal
    tare_source_used: TareSource | None
    tare_confidence_used: TareConfidence | None
    tare_profile_id: int | None
    tare_profile_name: str | None
    note: str | None
    reversed_calibration_id: int | None
    reversed_at: UtcDatetime | None
    effective_at: UtcDatetime
    created_at: UtcDatetime


class CalibrationUndoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: OptionalText


class EmptySpoolMeasurementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measured_tare_g: Weight
    tare_profile_id: Annotated[int, Field(gt=0)] | None = None
    contribute_to_profile: bool = False
    note: OptionalText | None = None

    @model_validator(mode="after")
    def contribution_requires_profile(self) -> Self:
        if self.contribute_to_profile and self.tare_profile_id is None:
            raise ValueError("contributing a measurement requires tare_profile_id")
        return self


class EmptySpoolMeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    spool_id: int
    tare_profile_id: int | None
    measured_tare_g: Decimal
    contributes_to_profile: bool
    note: str | None
    created_at: UtcDatetime
