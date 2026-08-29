from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.timestamps import utc_now


class Material(Base):
    """A generic type of 3D-printing filament material."""

    __tablename__ = "materials"
    __table_args__ = (
        UniqueConstraint("name", name="uq_materials_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    default_nozzle_temp_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    default_nozzle_temp_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    default_bed_temp_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    default_bed_temp_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    density_g_cm3: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 3),
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
