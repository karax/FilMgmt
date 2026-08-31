from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
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
    from app.models.print_job import PrintJobSpool, PrintSpoolLock
    from app.models.weight_history import WeightHistory


class SpoolStatus(StrEnum):
    """Lifecycle states currently supported for a physical spool."""

    SEALED = "SEALED"
    OPEN = "OPEN"
    IN_USE = "IN_USE"
    LOW = "LOW"
    EMPTY = "EMPTY"
    NEEDS_DRYING = "NEEDS_DRYING"
    ARCHIVED = "ARCHIVED"


class Spool(Base):
    """An individual physical roll of filament."""

    __tablename__ = "spools"
    __table_args__ = (
        UniqueConstraint("code", name="uq_spools_code"),
        CheckConstraint(
            "diameter_mm >= 0.5 AND diameter_mm <= 5",
            name="ck_spools_diameter_range",
        ),
        CheckConstraint(
            "initial_filament_weight_g > 0",
            name="ck_spools_initial_weight_positive",
        ),
        CheckConstraint(
            "current_filament_weight_g >= 0",
            name="ck_spools_current_weight_non_negative",
        ),
        CheckConstraint(
            "current_filament_weight_g <= initial_filament_weight_g",
            name="ck_spools_current_weight_not_above_initial",
        ),
        CheckConstraint(
            "empty_spool_weight_g IS NULL OR empty_spool_weight_g >= 0",
            name="ck_spools_empty_weight_non_negative",
        ),
        CheckConstraint(
            "purchase_price IS NULL OR purchase_price >= 0",
            name="ck_spools_purchase_price_non_negative",
        ),
        CheckConstraint(
            "nozzle_temp_min IS NULL OR nozzle_temp_min BETWEEN 0 AND 500",
            name="ck_spools_nozzle_temp_min_range",
        ),
        CheckConstraint(
            "nozzle_temp_max IS NULL OR nozzle_temp_max BETWEEN 0 AND 500",
            name="ck_spools_nozzle_temp_max_range",
        ),
        CheckConstraint(
            "nozzle_temp_min IS NULL OR nozzle_temp_max IS NULL "
            "OR nozzle_temp_min <= nozzle_temp_max",
            name="ck_spools_nozzle_temp_order",
        ),
        CheckConstraint(
            "bed_temp_min IS NULL OR bed_temp_min BETWEEN 0 AND 500",
            name="ck_spools_bed_temp_min_range",
        ),
        CheckConstraint(
            "bed_temp_max IS NULL OR bed_temp_max BETWEEN 0 AND 500",
            name="ck_spools_bed_temp_max_range",
        ),
        CheckConstraint(
            "bed_temp_min IS NULL OR bed_temp_max IS NULL "
            "OR bed_temp_min <= bed_temp_max",
            name="ck_spools_bed_temp_order",
        ),
        CheckConstraint(
            "status IN ('SEALED', 'OPEN', 'IN_USE', 'LOW', 'EMPTY', "
            "'NEEDS_DRYING', 'ARCHIVED')",
            name="ck_spools_status",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    manufacturer_id: Mapped[int] = mapped_column(
        ForeignKey("manufacturers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    display_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    color_name: Mapped[str] = mapped_column(String(100), nullable=False)
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    diameter_mm: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        default=Decimal("1.75"),
        server_default="1.75",
        nullable=False,
    )

    initial_filament_weight_g: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
    )
    current_filament_weight_g: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
    )
    empty_spool_weight_g: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )

    purchase_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="EUR",
        server_default="EUR",
        nullable=False,
    )
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    nozzle_temp_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nozzle_temp_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bed_temp_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bed_temp_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[SpoolStatus] = mapped_column(
        Enum(
            SpoolStatus,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            length=20,
            name="spool_status",
        ),
        default=SpoolStatus.SEALED,
        server_default=SpoolStatus.SEALED.value,
        nullable=False,
        index=True,
    )
    needs_drying: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        nullable=False,
    )
    last_dried_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    manufacturer: Mapped["Manufacturer"] = relationship()
    material: Mapped["Material"] = relationship()
    location: Mapped["Location | None"] = relationship()
    weight_history: Mapped[list["WeightHistory"]] = relationship(
        back_populates="spool",
        order_by="WeightHistory.created_at",
        passive_deletes="all",
    )
    print_job_links: Mapped[list["PrintJobSpool"]] = relationship(
        back_populates="spool",
        passive_deletes="all",
    )
    print_spool_locks: Mapped[list["PrintSpoolLock"]] = relationship(
        back_populates="spool",
        passive_deletes="all",
    )

    @property
    def remaining_percent(self) -> float:
        """Return the current filament percentage without persisting it."""
        initial_weight = self.initial_filament_weight_g
        current_weight = self.current_filament_weight_g
        if initial_weight is None or initial_weight <= 0 or current_weight is None:
            return 0.0

        initial_decimal = Decimal(str(initial_weight))
        current_decimal = Decimal(str(current_weight))
        percentage = current_decimal / initial_decimal * Decimal("100")
        return float(percentage.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
