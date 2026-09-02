from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Spool, WeightHistory, WeightSource
from app.models.spool import MAX_SPOOL_FILAMENT_WEIGHT_G
from app.services.spool_status_service import update_inventory_status


class SpoolWeightOutOfRangeError(Exception):
    """Raised when an absolute remaining weight is outside spool limits."""


def apply_spool_weight_update(
    db: Session,
    spool: Spool,
    weight_g: Decimal,
    source: WeightSource,
    notes: str | None = None,
) -> None:
    """Mutate spool weight and history in the caller's open transaction."""
    if (
        weight_g < 0
        or weight_g > MAX_SPOOL_FILAMENT_WEIGHT_G
        or weight_g > spool.initial_filament_weight_g
    ):
        raise SpoolWeightOutOfRangeError
    spool.current_filament_weight_g = weight_g
    update_inventory_status(spool)
    db.add(
        WeightHistory(
            spool_id=spool.id,
            weight_g=weight_g,
            source=source,
            notes=notes,
        )
    )
