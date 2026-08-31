from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from app.models.print_job import PrintJobStatus
from app.schemas.common import UtcDatetime

PrintJobName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PrintJobId = Annotated[int, Field(gt=0)]
EstimatedWeight = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=3)]
ActualWeight = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=3)]

class PrintJobSpoolCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    spool_id: PrintJobId
    estimated_weight_g: EstimatedWeight | None = None

class PrintJobSpoolUpdate(PrintJobSpoolCreate): pass

class PrintJobSpoolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; spool_id: PrintJobId; position: int; estimated_weight_g: EstimatedWeight | None; actual_weight_g: ActualWeight | None
    filament_cost_per_g: Decimal | None; material_cost: Decimal | None; material_cost_currency: str | None
    created_at: UtcDatetime; updated_at: UtcDatetime

class PrintJobCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: PrintJobName
    spools: list[PrintJobSpoolCreate] = Field(min_length=1)
    estimated_time_minutes: Annotated[int, Field(gt=0)] | None = None
    printer_name: PrintJobName | None = None
    notes: str | None = None
    @model_validator(mode='after')
    def unique_spools(self) -> Self:
        if len({s.spool_id for s in self.spools}) != len(self.spools): raise ValueError('duplicate spool_id')
        return self

class PrintJobUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: PrintJobName | None = None
    spools: list[PrintJobSpoolUpdate] | None = Field(default=None, min_length=1)
    estimated_time_minutes: Annotated[int, Field(gt=0)] | None = None
    printer_name: PrintJobName | None = None
    notes: str | None = None
    @model_validator(mode='after')
    def unique_spools(self) -> Self:
        if self.spools is not None and len({s.spool_id for s in self.spools}) != len(self.spools): raise ValueError('duplicate spool_id')
        return self

class PrintJobFilterParams(BaseModel):
    status: PrintJobStatus | None = None; spool_id: PrintJobId | None = None

class PrintJobSpoolConsumption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    spool_id: PrintJobId; actual_weight_g: ActualWeight

class PrintJobFinishRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consumptions: list[PrintJobSpoolConsumption] = Field(default_factory=list)
    @model_validator(mode='after')
    def unique_spools(self) -> Self:
        if len({s.spool_id for s in self.consumptions}) != len(self.consumptions): raise ValueError('duplicate spool_id')
        return self

class PrintJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: PrintJobName; status: PrintJobStatus; spools: list[PrintJobSpoolRead] = Field(validation_alias='spool_links')
    total_estimated_weight_g: EstimatedWeight | None; total_actual_weight_g: ActualWeight | None
    estimated_time_minutes: int | None; actual_time_minutes: int | None; printer_name: str | None
    started_at: UtcDatetime | None; finished_at: UtcDatetime | None; notes: str | None; created_at: UtcDatetime; updated_at: UtcDatetime
