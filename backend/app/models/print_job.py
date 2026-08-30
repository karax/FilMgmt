from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.spool import Spool


class PrintJobStatus(StrEnum):
    PLANNED = "PLANNED"
    PRINTING = "PRINTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PrintJob(Base):
    """A single 3D print associated with the filament spool it uses."""

    __tablename__ = "print_jobs"
    __table_args__ = (
        CheckConstraint("estimated_weight_g IS NULL OR estimated_weight_g > 0", name="ck_print_jobs_estimated_weight_positive"),
        CheckConstraint("trim(name) <> ''", name="ck_print_jobs_name_not_blank"),
        CheckConstraint("actual_weight_g IS NULL OR actual_weight_g >= 0", name="ck_print_jobs_actual_weight_non_negative"),
        CheckConstraint("estimated_time_minutes IS NULL OR estimated_time_minutes > 0", name="ck_print_jobs_estimated_time_positive"),
        CheckConstraint("actual_time_minutes IS NULL OR actual_time_minutes >= 0", name="ck_print_jobs_actual_time_non_negative"),
        CheckConstraint("finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at", name="ck_print_jobs_timestamp_order"),
        CheckConstraint("status IN ('PLANNED', 'PRINTING', 'SUCCESS', 'FAILED', 'CANCELLED')", name="ck_print_jobs_status"),
        Index(
            "uq_print_jobs_one_printing_per_spool",
            "spool_id",
            unique=True,
            sqlite_where=text("status = 'PRINTING'"),
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    spool_id: Mapped[int] = mapped_column(ForeignKey("spools.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[PrintJobStatus] = mapped_column(
        Enum(PrintJobStatus, native_enum=False, create_constraint=False, validate_strings=True, length=20, name="print_job_status"),
        default=PrintJobStatus.PLANNED,
        server_default=PrintJobStatus.PLANNED.value,
        nullable=False,
        index=True,
    )
    estimated_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    actual_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    estimated_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filament_cost_per_g: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
    )
    material_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )
    material_cost_currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )
    printer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now, nullable=False)

    spool: Mapped["Spool"] = relationship(back_populates="print_jobs")
