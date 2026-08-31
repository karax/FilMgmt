from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
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
        CheckConstraint("trim(name) <> ''", name="ck_print_jobs_name_not_blank"),
        CheckConstraint("estimated_time_minutes IS NULL OR estimated_time_minutes > 0", name="ck_print_jobs_estimated_time_positive"),
        CheckConstraint("actual_time_minutes IS NULL OR actual_time_minutes >= 0", name="ck_print_jobs_actual_time_non_negative"),
        CheckConstraint("finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at", name="ck_print_jobs_timestamp_order"),
        CheckConstraint("status IN ('PLANNED', 'PRINTING', 'SUCCESS', 'FAILED', 'CANCELLED')", name="ck_print_jobs_status"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now, nullable=False)

    spool_links: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job", order_by="PrintJobSpool.position", cascade="all, delete-orphan")
    spool_locks: Mapped[list["PrintSpoolLock"]] = relationship(back_populates="print_job", passive_deletes="all")

    def _total(self, field: str) -> Decimal | None:
        values = [getattr(link, field) for link in self.spool_links]
        return sum(values, Decimal("0")) if values and all(value is not None for value in values) else None

    @property
    def total_estimated_weight_g(self) -> Decimal | None:
        return self._total("estimated_weight_g")

    @property
    def total_actual_weight_g(self) -> Decimal | None:
        return self._total("actual_weight_g")


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
