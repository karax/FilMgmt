from decimal import Decimal

from app.models import Spool, SpoolStatus

LOW_SPOOL_PERCENT = Decimal("20.0")
LOW_SPOOL_WEIGHT_G = Decimal("200.0")

_PRESERVED_POSITIVE_WEIGHT_STATUSES = frozenset(
    {
        SpoolStatus.SEALED,
        SpoolStatus.IN_USE,
        SpoolStatus.NEEDS_DRYING,
    }
)


def determine_inventory_status(spool: Spool) -> SpoolStatus:
    """Determine the inventory status without mutating or persisting the spool."""
    if spool.status is SpoolStatus.ARCHIVED or spool.archived_at is not None:
        return SpoolStatus.ARCHIVED

    current_weight = Decimal(str(spool.current_filament_weight_g))
    if current_weight == 0:
        return SpoolStatus.EMPTY

    if spool.status in _PRESERVED_POSITIVE_WEIGHT_STATUSES:
        return spool.status

    initial_weight = Decimal(str(spool.initial_filament_weight_g))
    remaining_percent = current_weight / initial_weight * Decimal("100")
    if (
        remaining_percent <= LOW_SPOOL_PERCENT
        or current_weight <= LOW_SPOOL_WEIGHT_G
    ):
        return SpoolStatus.LOW

    return SpoolStatus.OPEN


def update_inventory_status(spool: Spool) -> SpoolStatus:
    """Apply the centrally determined status without committing the session."""
    spool.status = determine_inventory_status(spool)
    return spool.status


def release_spool_from_use(spool: Spool) -> SpoolStatus:
    """Remove transient print usage and recalculate the inventory status."""
    if spool.status is SpoolStatus.IN_USE:
        spool.status = (
            SpoolStatus.NEEDS_DRYING
            if spool.needs_drying
            else SpoolStatus.OPEN
        )
    return update_inventory_status(spool)
