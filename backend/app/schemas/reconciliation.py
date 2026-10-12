from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.print_job import (
    FilamentReconciliationEventType,
    PrintJobReconciliationStatus,
    PrintJobStatus,
)
from app.schemas.common import UtcDatetime


PositiveId = Annotated[int, Field(gt=0)]
ReconciliationWeight = Annotated[
    Decimal, Field(gt=0, max_digits=12, decimal_places=3)
]
OptionalReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class CandidateConfidence(StrEnum):
    EXACT = "EXACT"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    AMBIGUOUS = "AMBIGUOUS"


class ReconciliationAction(StrEnum):
    DEDUCT = "DEDUCT"
    SKIP = "SKIP"


class ReconciliationCandidateReason(BaseModel):
    code: str
    detail: str


class ReconciliationSpoolCandidate(BaseModel):
    id: int
    code: str
    display_name: str | None
    product_name: str | None
    manufacturer_name: str
    material_name: str
    color_name: str
    color_hex: str | None
    current_filament_weight_g: Decimal
    purchase_price: Decimal | None
    currency: str
    confidence: CandidateConfidence
    reasons: list[ReconciliationCandidateReason]
    sufficient_remaining: bool
    latest_physical_calibration_at: UtcDatetime | None


class ReconciliationSpoolOption(BaseModel):
    id: int
    code: str
    display_name: str | None
    manufacturer_name: str
    material_name: str
    color_name: str
    color_hex: str | None
    current_filament_weight_g: Decimal
    latest_physical_calibration_at: UtcDatetime | None


class ReconciliationResolutionRead(BaseModel):
    id: int
    event_type: FilamentReconciliationEventType
    spool_id: int | None
    spool_code: str | None
    amount_g: Decimal
    sliced_estimated_g: Decimal | None
    remaining_before_g: Decimal | None
    remaining_after_g: Decimal | None
    manual_override: bool
    reason: str | None
    created_at: UtcDatetime


class ReconciliationUsageRead(BaseModel):
    id: int
    position: int
    material_type: str | None
    color: str | None
    used_g: Decimal | None
    progress_estimated_g: Decimal | None
    used_m: Decimal | None
    tray_info_idx: str | None
    ams_tray: str | None
    ams_brand: str | None
    candidates: list[ReconciliationSpoolCandidate]
    recommended_spool_id: int | None
    unambiguous: bool
    requires_manual_consumption: bool
    resolution: ReconciliationResolutionRead | None


class ReconciliationJobRead(BaseModel):
    id: int
    name: str | None
    gcode_file: str | None
    status: PrintJobStatus
    reconciliation_status: PrintJobReconciliationStatus
    started_at: UtcDatetime | None
    finished_at: UtcDatetime | None
    duration_seconds: int | None
    actual_time_minutes: int | None
    final_progress: int | None
    selected_plate_index: int | None
    selected_plate_name: str | None
    thumbnail_url: str | None
    filament_count: int
    estimated_filament_g: Decimal | None
    filaments: list[ReconciliationUsageRead]


class ReconciliationQueueRead(BaseModel):
    jobs: list[ReconciliationJobRead]
    recently_reconciled_jobs: list[ReconciliationJobRead]
    available_spools: list[ReconciliationSpoolOption]
    pending_job_count: int
    ready_job_count: int
    needs_review_job_count: int
    estimated_pending_g: Decimal


class ReconciliationConfirmItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filament_usage_id: PositiveId
    action: ReconciliationAction
    spool_id: PositiveId | None = None
    consumption_g: ReconciliationWeight | None = None
    reason: OptionalReason | None = None
    checkpoint_acknowledged: bool = False

    @model_validator(mode="after")
    def validate_action_shape(self):
        if self.action is ReconciliationAction.DEDUCT:
            if self.spool_id is None or self.consumption_g is None:
                raise ValueError("deduction requires spool_id and consumption_g")
        elif self.spool_id is not None or self.consumption_g is not None:
            raise ValueError("skip cannot include spool_id or consumption_g")
        return self


class ReconciliationConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReconciliationConfirmItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_usages(self):
        ids = [item.filament_usage_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate filament_usage_id")
        return self


class ReconciliationConfirmResult(BaseModel):
    reconciled_usage_ids: list[int]
    print_jobs: list[ReconciliationJobRead]


class ReconciliationUndoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: OptionalReason
