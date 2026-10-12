from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from app.models.print_job import (
    FilamentReconciliationEventType,
    PrintJobCaptureMode,
    PrintJobEnrichmentStatus,
    PrintJobReconciliationStatus,
    PrintJobStatus,
)
from app.schemas.common import UtcDatetime

PrintJobName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PrintJobId = Annotated[int, Field(gt=0)]
EstimatedWeight = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=3)]
ActualWeight = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=3)]
EstimatedUsage = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=3)]

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


class PrintJobFilamentUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    plate_index: int | None
    source_filament_id: str | None
    material_type: str | None
    color: str | None
    used_g: EstimatedUsage | None
    used_m: EstimatedUsage | None
    tray_info_idx: str | None
    used_for_object: bool | None
    used_for_support: bool | None
    nozzle_diameter: Decimal | None
    group_id: str | None
    reconciliation_event_type: FilamentReconciliationEventType | None
    confirmed_spool_id: int | None
    confirmed_spool_code: str | None
    reconciled_consumption_g: EstimatedUsage | None
    created_at: UtcDatetime
    updated_at: UtcDatetime

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
    status: PrintJobStatus | None = None
    spool_id: PrintJobId | None = None
    printer_serial: str | None = None
    started_after: UtcDatetime | None = None
    started_before: UtcDatetime | None = None

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
    id: int; name: str | None; status: PrintJobStatus; spools: list[PrintJobSpoolRead] = Field(validation_alias='spool_links')
    total_estimated_weight_g: EstimatedWeight | None; total_actual_weight_g: ActualWeight | None
    estimated_time_minutes: int | None; actual_time_minutes: int | None; printer_name: str | None
    started_at: UtcDatetime | None; finished_at: UtcDatetime | None; notes: str | None
    printer_serial: str | None
    task_id: str | None
    subtask_id: str | None
    project_id: str | None
    profile_id: str | None
    gcode_file: str | None
    last_seen_at: UtcDatetime | None
    raw_bambu_state: str | None
    start_progress: int | None
    final_progress: int | None
    start_layer: int | None
    final_layer: int | None
    total_layers: int | None
    duration_seconds: int | None
    remaining_time_minutes: int | None
    capture_mode: PrintJobCaptureMode | None
    reconciliation_status: PrintJobReconciliationStatus | None
    ams_snapshot: dict[str, object] | None
    enrichment_status: PrintJobEnrichmentStatus | None
    enrichment_attempts: int
    last_enrichment_attempt_at: UtcDatetime | None
    enrichment_error_code: str | None
    metadata_source: str | None
    source_file_name: str | None
    source_file_match: str | None
    source_file_modified_at: UtcDatetime | None
    metadata_parser_version: str | None
    enriched_at: UtcDatetime | None
    thumbnail_url: str | None
    selected_plate_index: int | None
    selected_plate_name: str | None
    plate_selection_confidence: str | None
    slicer_estimated_duration_seconds: int | None
    estimated_filament_g: EstimatedUsage | None
    estimated_filament_m: EstimatedUsage | None
    filament_count: int
    filaments: list[PrintJobFilamentUsageRead] = Field(validation_alias='filament_usages')
    created_at: UtcDatetime
    updated_at: UtcDatetime


class PrintJobEnrichmentAccepted(BaseModel):
    print_job_id: int
    status: str
