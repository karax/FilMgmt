from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.spool import MAX_SPOOL_FILAMENT_WEIGHT_G
from app.models.weight_history import WeightSource
from app.schemas.common import UtcDatetime

WeightHistoryWeight = Annotated[
    Decimal,
    Field(ge=0, max_digits=10, decimal_places=3),
]


class WeightHistoryBase(BaseModel):
    """Fields accepted for a new immutable weight event."""

    model_config = ConfigDict(extra="forbid")

    weight_g: WeightHistoryWeight
    source: WeightSource
    notes: str | None = None


class WeightHistoryCreate(WeightHistoryBase):
    """Payload for a future spool-scoped weight recording operation."""

    @field_validator("weight_g")
    @classmethod
    def filament_weight_cannot_exceed_limit(cls, value: Decimal) -> Decimal:
        if value > MAX_SPOOL_FILAMENT_WEIGHT_G:
            raise ValueError("Filament weight cannot exceed 2000 g.")
        return value


class WeightHistoryRead(WeightHistoryBase):
    """Persisted weight event serialized from SQLAlchemy attributes."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    spool_id: int
    created_at: UtcDatetime
