from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.spool import Spool


class PrintJobStatus(StrEnum):
    PLANNED = "PLANNED"
    PRINTING = "PRINTING"
    PAUSED = "PAUSED"
    SUCCESS = "SUCCESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN_TERMINAL = "UNKNOWN_TERMINAL"


class PrintJobCaptureMode(StrEnum):
    LIVE = "LIVE"
    RECOVERED = "RECOVERED"


class PrintJobReconciliationStatus(StrEnum):
    PENDING = "PENDING"
    PARTIALLY_RECONCILED = "PARTIALLY_RECONCILED"
    RECONCILED = "RECONCILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FilamentReconciliationEventType(StrEnum):
    CONSUMPTION = "CONSUMPTION"
    SKIP = "SKIP"
    REVERSAL = "REVERSAL"


class PrintJobEnrichmentStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    ENRICHED = "ENRICHED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    RETRYABLE = "RETRYABLE"
    FAILED = "FAILED"


class PrintJob(Base):
    """A manual inventory print or a read-only printer-observed print."""

    __tablename__ = "print_jobs"
    __table_args__ = (
        CheckConstraint("name IS NULL OR trim(name) <> ''", name="ck_print_jobs_name_not_blank"),
        CheckConstraint("estimated_time_minutes IS NULL OR estimated_time_minutes > 0", name="ck_print_jobs_estimated_time_positive"),
        CheckConstraint("actual_time_minutes IS NULL OR actual_time_minutes >= 0", name="ck_print_jobs_actual_time_non_negative"),
        CheckConstraint("finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at", name="ck_print_jobs_timestamp_order"),
        CheckConstraint("status IN ('PLANNED', 'PRINTING', 'PAUSED', 'SUCCESS', 'COMPLETED', 'FAILED', 'CANCELLED', 'UNKNOWN_TERMINAL')", name="ck_print_jobs_status"),
        CheckConstraint("start_progress IS NULL OR start_progress BETWEEN 0 AND 100", name="ck_print_jobs_start_progress_range"),
        CheckConstraint("final_progress IS NULL OR final_progress BETWEEN 0 AND 100", name="ck_print_jobs_final_progress_range"),
        CheckConstraint("start_layer IS NULL OR start_layer >= 0", name="ck_print_jobs_start_layer_non_negative"),
        CheckConstraint("final_layer IS NULL OR final_layer >= 0", name="ck_print_jobs_final_layer_non_negative"),
        CheckConstraint("total_layers IS NULL OR total_layers >= 0", name="ck_print_jobs_total_layers_non_negative"),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ck_print_jobs_duration_non_negative"),
        CheckConstraint("remaining_time_minutes IS NULL OR remaining_time_minutes >= 0", name="ck_print_jobs_remaining_time_non_negative"),
        CheckConstraint("enrichment_attempts >= 0", name="ck_print_jobs_enrichment_attempts_non_negative"),
        CheckConstraint("enrichment_status IS NULL OR enrichment_status IN ('PENDING', 'IN_PROGRESS', 'ENRICHED', 'FILE_NOT_FOUND', 'AMBIGUOUS', 'RETRYABLE', 'FAILED')", name="ck_print_jobs_enrichment_status"),
        CheckConstraint(
            "reconciliation_status IS NULL OR reconciliation_status IN "
            "('PENDING', 'PARTIALLY_RECONCILED', 'RECONCILED', "
            "'NEEDS_REVIEW', 'NOT_APPLICABLE')",
            name="ck_print_jobs_reconciliation_status",
        ),
        CheckConstraint("slicer_estimated_duration_seconds IS NULL OR slicer_estimated_duration_seconds >= 0", name="ck_print_jobs_slicer_duration_non_negative"),
        Index(
            "uq_print_jobs_one_active_bambu_printer",
            "printer_serial",
            unique=True,
            sqlite_where=text(
                "printer_serial IS NOT NULL AND capture_mode IS NOT NULL "
                "AND status IN ('PRINTING', 'PAUSED')"
            ),
        ),
        Index("ix_print_jobs_started_at", "started_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[PrintJobStatus] = mapped_column(
        Enum(PrintJobStatus, native_enum=False, create_constraint=False, validate_strings=True, length=20, name="print_job_status"),
        default=PrintJobStatus.PLANNED,
        server_default=PrintJobStatus.PLANNED.value,
        nullable=False,
        index=True,
    )
    estimated_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    printer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    printer_serial: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    bambu_identity_key: Mapped[str | None] = mapped_column(String(700), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subtask_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gcode_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_bambu_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_layer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_layer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_layers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capture_mode: Mapped[PrintJobCaptureMode | None] = mapped_column(
        Enum(PrintJobCaptureMode, native_enum=False, create_constraint=False, validate_strings=True, length=20, name="print_job_capture_mode"),
        nullable=True,
    )
    reconciliation_status: Mapped[PrintJobReconciliationStatus | None] = mapped_column(
        Enum(PrintJobReconciliationStatus, native_enum=False, create_constraint=False, validate_strings=True, length=20, name="print_job_reconciliation_status"),
        nullable=True,
        index=True,
    )
    ams_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    enrichment_status: Mapped[PrintJobEnrichmentStatus | None] = mapped_column(
        Enum(PrintJobEnrichmentStatus, native_enum=False, create_constraint=False, validate_strings=True, length=20, name="print_job_enrichment_status"),
        nullable=True,
        index=True,
    )
    enrichment_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_enrichment_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrichment_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_file_match: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_file_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_parser_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    thumbnail_file_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    selected_plate_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_plate_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    plate_selection_confidence: Mapped[str | None] = mapped_column(String(30), nullable=True)
    slicer_estimated_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now, nullable=False)

    spool_links: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job", order_by="PrintJobSpool.position", cascade="all, delete-orphan")
    spool_locks: Mapped[list["PrintSpoolLock"]] = relationship(back_populates="print_job", passive_deletes="all")
    filament_usages: Mapped[list["PrintJobFilamentUsage"]] = relationship(
        back_populates="print_job",
        order_by="PrintJobFilamentUsage.position",
        cascade="all, delete-orphan",
    )
    reconciliation_events: Mapped[list["PrintJobFilamentReconciliation"]] = relationship(
        back_populates="print_job",
        passive_deletes="all",
    )

    def _total(self, field: str) -> Decimal | None:
        values = [getattr(link, field) for link in self.spool_links]
        return sum(values, Decimal("0")) if values and all(value is not None for value in values) else None

    @property
    def total_estimated_weight_g(self) -> Decimal | None:
        return self._total("estimated_weight_g")

    @property
    def total_actual_weight_g(self) -> Decimal | None:
        return self._total("actual_weight_g")

    @property
    def estimated_filament_g(self) -> Decimal | None:
        values = [usage.used_g for usage in self.filament_usages]
        return sum(values, Decimal("0")) if values and all(value is not None for value in values) else None

    @property
    def estimated_filament_m(self) -> Decimal | None:
        values = [usage.used_m for usage in self.filament_usages]
        return sum(values, Decimal("0")) if values and all(value is not None for value in values) else None

    @property
    def filament_count(self) -> int:
        return len(self.filament_usages)

    @property
    def thumbnail_url(self) -> str | None:
        if self.thumbnail_file_name is None or self.id is None:
            return None
        return f"/api/prints/{self.id}/thumbnail"


class PrintJobFilamentUsage(Base):
    """Immutable slicer estimate; physical spool resolution lives in its ledger."""

    __tablename__ = "print_job_filament_usages"
    __table_args__ = (
        UniqueConstraint("print_job_id", "position", name="uq_print_job_filament_usages_job_position"),
        CheckConstraint("position >= 0", name="ck_print_job_filament_usages_position_non_negative"),
        CheckConstraint("used_g IS NULL OR used_g >= 0", name="ck_print_job_filament_usages_used_g_non_negative"),
        CheckConstraint("used_m IS NULL OR used_m >= 0", name="ck_print_job_filament_usages_used_m_non_negative"),
        CheckConstraint("nozzle_diameter IS NULL OR nozzle_diameter > 0", name="ck_print_job_filament_usages_nozzle_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    print_job_id: Mapped[int] = mapped_column(ForeignKey("print_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    plate_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_filament_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    material_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    used_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    used_m: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    tray_info_idx: Mapped[str | None] = mapped_column(String(100), nullable=True)
    used_for_object: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    used_for_support: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    nozzle_diameter: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    group_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now, nullable=False)

    print_job: Mapped["PrintJob"] = relationship(back_populates="filament_usages")
    reconciliation_events: Mapped[list["PrintJobFilamentReconciliation"]] = relationship(
        back_populates="filament_usage",
        order_by="PrintJobFilamentReconciliation.created_at",
        passive_deletes="all",
    )

    @property
    def current_reconciliation(self) -> "PrintJobFilamentReconciliation | None":
        return next(
            (
                event
                for event in reversed(self.reconciliation_events)
                if event.event_type
                in {
                    FilamentReconciliationEventType.CONSUMPTION,
                    FilamentReconciliationEventType.SKIP,
                }
                and event.reversed_at is None
            ),
            None,
        )

    @property
    def reconciliation_event_type(self) -> FilamentReconciliationEventType | None:
        event = self.current_reconciliation
        return event.event_type if event is not None else None

    @property
    def confirmed_spool_id(self) -> int | None:
        event = self.current_reconciliation
        return event.spool_id if event is not None else None

    @property
    def confirmed_spool_code(self) -> str | None:
        event = self.current_reconciliation
        return event.spool.code if event is not None and event.spool is not None else None

    @property
    def reconciled_consumption_g(self) -> Decimal | None:
        event = self.current_reconciliation
        return event.amount_g if event is not None else None


class PrintJobFilamentReconciliation(Base):
    """Append-only audit event for resolving one sliced filament usage."""

    __tablename__ = "print_job_filament_reconciliations"
    __table_args__ = (
        CheckConstraint("amount_g >= 0", name="ck_filament_reconciliation_amount_non_negative"),
        CheckConstraint(
            "event_type IN ('CONSUMPTION', 'SKIP', 'REVERSAL')",
            name="ck_filament_reconciliation_event_type",
        ),
        CheckConstraint(
            "(event_type = 'CONSUMPTION' AND spool_id IS NOT NULL AND amount_g > 0 "
            "AND remaining_before_g IS NOT NULL AND remaining_after_g IS NOT NULL) "
            "OR (event_type = 'SKIP' AND spool_id IS NULL AND amount_g = 0 "
            "AND remaining_before_g IS NULL AND remaining_after_g IS NULL) "
            "OR (event_type = 'REVERSAL' AND reversed_event_id IS NOT NULL)",
            name="ck_filament_reconciliation_event_shape",
        ),
        Index(
            "uq_active_filament_reconciliation",
            "filament_usage_id",
            unique=True,
            sqlite_where=text(
                "event_type IN ('CONSUMPTION', 'SKIP') AND reversed_at IS NULL"
            ),
        ),
        Index(
            "ix_reconciliation_active_consumption_job_spool",
            "print_job_id",
            "spool_id",
            sqlite_where=text("event_type = 'CONSUMPTION' AND reversed_at IS NULL"),
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    print_job_id: Mapped[int] = mapped_column(
        ForeignKey("print_jobs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    filament_usage_id: Mapped[int] = mapped_column(
        ForeignKey("print_job_filament_usages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    spool_id: Mapped[int | None] = mapped_column(
        ForeignKey("spools.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    event_type: Mapped[FilamentReconciliationEventType] = mapped_column(
        Enum(
            FilamentReconciliationEventType,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            length=20,
            name="filament_reconciliation_event_type",
        ),
        nullable=False,
    )
    amount_g: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    sliced_estimated_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    remaining_before_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    remaining_after_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    manual_override: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("print_job_filament_reconciliations.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )

    print_job: Mapped["PrintJob"] = relationship(back_populates="reconciliation_events")
    filament_usage: Mapped["PrintJobFilamentUsage"] = relationship(
        back_populates="reconciliation_events"
    )
    spool: Mapped["Spool | None"] = relationship(back_populates="reconciliation_events")
    reversed_event: Mapped["PrintJobFilamentReconciliation | None"] = relationship(
        remote_side="PrintJobFilamentReconciliation.id",
        foreign_keys=[reversed_event_id],
    )


class PrintJobSpool(Base):
    __tablename__ = "print_job_spools"
    __table_args__ = (UniqueConstraint("print_job_id", "spool_id", name="uq_print_job_spools_print_job_spool"), CheckConstraint("position >= 0", name="ck_print_job_spools_position_non_negative"), CheckConstraint("estimated_weight_g IS NULL OR estimated_weight_g > 0", name="ck_print_job_spools_estimated_weight_positive"), CheckConstraint("actual_weight_g IS NULL OR actual_weight_g >= 0", name="ck_print_job_spools_actual_weight_non_negative"))
    id: Mapped[int] = mapped_column(primary_key=True)
    print_job_id: Mapped[int] = mapped_column(ForeignKey("print_jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    spool_id: Mapped[int] = mapped_column(ForeignKey("spools.id", ondelete="RESTRICT"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    actual_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    filament_cost_per_g: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    material_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    material_cost_currency: Mapped[str | None] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now, nullable=False)
    print_job: Mapped["PrintJob"] = relationship(back_populates="spool_links")
    spool: Mapped["Spool"] = relationship(back_populates="print_job_links")


class PrintSpoolLock(Base):
    __tablename__ = "print_spool_locks"
    spool_id: Mapped[int] = mapped_column(ForeignKey("spools.id", ondelete="RESTRICT"), primary_key=True)
    print_job_id: Mapped[int] = mapped_column(ForeignKey("print_jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False)
    print_job: Mapped["PrintJob"] = relationship(back_populates="spool_locks")
    spool: Mapped["Spool"] = relationship(back_populates="print_spool_locks")
