from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.models.print_job import PrintJobStatus
from app.schemas.common import UtcDatetime

PrintJobName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PrintJobOptionalName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PrintJobId = Annotated[int, Field(gt=0)]
EstimatedWeight = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=3)]
ActualWeight = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=3)]
EstimatedMinutes = Annotated[int, Field(gt=0)]
ActualMinutes = Annotated[int, Field(ge=0)]
FilamentCostPerG = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=6)]
MaterialCost = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=4)]
MaterialCostCurrency = Annotated[str, StringConstraints(min_length=3, max_length=3)]


class PrintJobCreate(BaseModel):
    """Initial payload; lifecycle fields are controlled by later workflows."""

    model_config = ConfigDict(extra="forbid")

    name: PrintJobName
    spool_id: PrintJobId
    estimated_weight_g: EstimatedWeight | None = None
    estimated_time_minutes: EstimatedMinutes | None = None
    printer_name: PrintJobOptionalName | None = None
    notes: str | None = None


class PrintJobUpdate(BaseModel):
    """Planning-only fields that may be changed before a print starts."""

    model_config = ConfigDict(extra="forbid")

    name: PrintJobName | None = None
    spool_id: PrintJobId | None = None
    estimated_weight_g: EstimatedWeight | None = None
    estimated_time_minutes: EstimatedMinutes | None = None
    printer_name: PrintJobOptionalName | None = None
    notes: str | None = None

    @field_validator("name", "spool_id")
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class PrintJobFilterParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PrintJobStatus | None = None
    spool_id: PrintJobId | None = None


class PrintJobFinishRequest(BaseModel):
    """Optional measured consumption recorded when a successful print ends."""

    model_config = ConfigDict(extra="forbid")

    actual_weight_g: ActualWeight | None = None


class PrintJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: PrintJobName
    spool_id: PrintJobId
    status: PrintJobStatus
    estimated_weight_g: EstimatedWeight | None
    actual_weight_g: ActualWeight | None
    estimated_time_minutes: EstimatedMinutes | None
    actual_time_minutes: ActualMinutes | None
    filament_cost_per_g: FilamentCostPerG | None
    material_cost: MaterialCost | None
    material_cost_currency: MaterialCostCurrency | None
    printer_name: PrintJobOptionalName | None
    started_at: UtcDatetime | None
    finished_at: UtcDatetime | None
    notes: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> Self:
        if self.started_at and self.finished_at and self.finished_at < self.started_at:
            raise ValueError("finished_at cannot be before started_at")
        return self
