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
    Numeric,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.spool import Spool


class WeightSource(StrEnum):
    """Origin of a spool weight measurement."""

    MANUAL = "MANUAL"
    PRINT = "PRINT"
    SCALE = "SCALE"
    IMPORT = "IMPORT"
    CORRECTION = "CORRECTION"


class WeightHistory(Base):
    """Append-only record of a spool's remaining filament weight."""

    __tablename__ = "weight_history"
    __table_args__ = (
        CheckConstraint(
            "weight_g >= 0",
            name="ck_weight_history_weight_non_negative",
        ),
        CheckConstraint(
            "source IN ('MANUAL', 'PRINT', 'SCALE', 'IMPORT', 'CORRECTION')",
            name="ck_weight_history_source",
        ),
        Index(
            "ix_weight_history_spool_id_created_at",
            "spool_id",
            "created_at",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    spool_id: Mapped[int] = mapped_column(
        ForeignKey("spools.id", ondelete="CASCADE"),
        nullable=False,
    )
    weight_g: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    source: Mapped[WeightSource] = mapped_column(
        Enum(
            WeightSource,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            length=10,
            name="weight_source",
        ),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    spool: Mapped["Spool"] = relationship(back_populates="weight_history")
