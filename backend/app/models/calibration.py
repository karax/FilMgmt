from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.spool import Spool


class TareSource(StrEnum):
    MEASURED = "MEASURED"
    KNOWN = "KNOWN"
    ESTIMATED = "ESTIMATED"
    MANUAL = "MANUAL"


class TareConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CalibrationEventType(StrEnum):
    PHYSICAL_CALIBRATION = "PHYSICAL_CALIBRATION"
    REVERSAL = "REVERSAL"


class TareProfile(Base):
    """Reusable description of one physical empty-spool design."""

    __tablename__ = "tare_profiles"
    __table_args__ = (
        CheckConstraint("trim(name) <> ''", name="ck_tare_profiles_name_not_blank"),
        CheckConstraint("tare_g >= 0", name="ck_tare_profiles_tare_non_negative"),
        CheckConstraint(
            "source IN ('MEASURED', 'KNOWN', 'ESTIMATED', 'MANUAL')",
            name="ck_tare_profiles_source",
        ),
        CheckConstraint(
            "confidence IN ('HIGH', 'MEDIUM', 'LOW')",
            name="ck_tare_profiles_confidence",
        ),
        CheckConstraint(
            "measured_sample_count >= 0",
            name="ck_tare_profiles_sample_count_non_negative",
        ),
        CheckConstraint(
            "measured_min_g IS NULL OR measured_min_g >= 0",
            name="ck_tare_profiles_min_non_negative",
        ),
        CheckConstraint(
            "measured_max_g IS NULL OR measured_max_g >= 0",
            name="ck_tare_profiles_max_non_negative",
        ),
        UniqueConstraint("name", name="uq_tare_profiles_name"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(150), nullable=True)
    spool_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tare_g: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    source: Mapped[TareSource] = mapped_column(
        Enum(TareSource, native_enum=False, create_constraint=False, length=20),
        nullable=False,
    )
    confidence: Mapped[TareConfidence] = mapped_column(
        Enum(TareConfidence, native_enum=False, create_constraint=False, length=10),
        nullable=False,
    )
    measured_sample_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    measured_min_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    measured_max_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(),
        onupdate=utc_now, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    calibrations: Mapped[list["SpoolCalibration"]] = relationship(
        back_populates="tare_profile", passive_deletes="all"
    )
    measurements: Mapped[list["TareMeasurement"]] = relationship(
        back_populates="tare_profile", passive_deletes="all"
    )


class TareMeasurement(Base):
    """One physical empty-spool observation used as reusable tare evidence."""

    __tablename__ = "tare_measurements"
    __table_args__ = (
        CheckConstraint("measured_tare_g >= 0", name="ck_tare_measurements_non_negative"),
        Index("ix_tare_measurements_profile_created", "tare_profile_id", "created_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    spool_id: Mapped[int] = mapped_column(
        ForeignKey("spools.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tare_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("tare_profiles.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    measured_tare_g: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    contributes_to_profile: Mapped[bool] = mapped_column(
        default=False, server_default="0", nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )

    spool: Mapped["Spool"] = relationship(back_populates="tare_measurements")
    tare_profile: Mapped["TareProfile | None"] = relationship(back_populates="measurements")


class SpoolCalibration(Base):
    """Append-only physical-balance checkpoint and its optional reversal."""

    __tablename__ = "spool_calibrations"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('PHYSICAL_CALIBRATION', 'REVERSAL')",
            name="ck_spool_calibrations_event_type",
        ),
        CheckConstraint("measured_total_g IS NULL OR measured_total_g >= 0", name="ck_spool_calibrations_total_non_negative"),
        CheckConstraint("tare_g_used IS NULL OR tare_g_used >= 0", name="ck_spool_calibrations_tare_non_negative"),
        CheckConstraint("calculated_filament_g IS NULL OR calculated_filament_g >= 0", name="ck_spool_calibrations_filament_non_negative"),
        CheckConstraint("previous_remaining_g >= 0", name="ck_spool_calibrations_before_non_negative"),
        CheckConstraint("new_remaining_g >= 0", name="ck_spool_calibrations_after_non_negative"),
        CheckConstraint(
            "tare_source_used IS NULL OR tare_source_used IN ('MEASURED', 'KNOWN', 'ESTIMATED', 'MANUAL')",
            name="ck_spool_calibrations_tare_source",
        ),
        CheckConstraint(
            "tare_confidence_used IS NULL OR tare_confidence_used IN ('HIGH', 'MEDIUM', 'LOW')",
            name="ck_spool_calibrations_tare_confidence",
        ),
        CheckConstraint(
            "(event_type = 'PHYSICAL_CALIBRATION' AND measured_total_g IS NOT NULL "
            "AND tare_g_used IS NOT NULL AND calculated_filament_g IS NOT NULL "
            "AND tare_source_used IS NOT NULL AND tare_confidence_used IS NOT NULL "
            "AND idempotency_key IS NOT NULL AND reversed_calibration_id IS NULL) "
            "OR (event_type = 'REVERSAL' AND reversed_calibration_id IS NOT NULL)",
            name="ck_spool_calibrations_event_shape",
        ),
        UniqueConstraint("idempotency_key", name="uq_spool_calibrations_idempotency"),
        UniqueConstraint("reversed_calibration_id", name="uq_spool_calibrations_reversed"),
        Index("ix_spool_calibrations_spool_effective", "spool_id", "effective_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    spool_id: Mapped[int] = mapped_column(
        ForeignKey("spools.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[CalibrationEventType] = mapped_column(
        Enum(CalibrationEventType, native_enum=False, create_constraint=False, length=30),
        nullable=False,
    )
    measured_total_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    tare_g_used: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    calculated_filament_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    previous_remaining_g: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    adjustment_g: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    new_remaining_g: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    tare_source_used: Mapped[TareSource | None] = mapped_column(
        Enum(TareSource, native_enum=False, create_constraint=False, length=20)
    )
    tare_confidence_used: Mapped[TareConfidence | None] = mapped_column(
        Enum(TareConfidence, native_enum=False, create_constraint=False, length=10)
    )
    tare_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("tare_profiles.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    reversed_calibration_id: Mapped[int | None] = mapped_column(
        ForeignKey("spool_calibrations.id", ondelete="RESTRICT"), nullable=True
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )

    spool: Mapped["Spool"] = relationship(back_populates="calibrations")
    tare_profile: Mapped["TareProfile | None"] = relationship(back_populates="calibrations")
    reversed_calibration: Mapped["SpoolCalibration | None"] = relationship(
        remote_side="SpoolCalibration.id", foreign_keys=[reversed_calibration_id]
    )
