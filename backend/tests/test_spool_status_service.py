from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models import Spool, SpoolStatus
from app.services.spool_status_service import (
    LOW_SPOOL_PERCENT,
    LOW_SPOOL_WEIGHT_G,
    determine_inventory_status,
    update_inventory_status,
)


def spool_with_inventory(
    *,
    initial: int | Decimal = 1000,
    current: int | Decimal,
    status: SpoolStatus = SpoolStatus.OPEN,
    needs_drying: bool = False,
) -> Spool:
    return Spool(
        initial_filament_weight_g=Decimal(str(initial)),
        current_filament_weight_g=Decimal(str(current)),
        status=status,
        needs_drying=needs_drying,
    )


def test_low_thresholds_are_centralized_decimal_constants() -> None:
    assert LOW_SPOOL_PERCENT == Decimal("20.0")
    assert LOW_SPOOL_WEIGHT_G == Decimal("200.0")


@pytest.mark.parametrize(
    ("initial", "current", "expected"),
    [
        (1000, 800, SpoolStatus.OPEN),
        (1000, 190, SpoolStatus.LOW),
        (5000, 200, SpoolStatus.LOW),
        (1000, 200, SpoolStatus.LOW),
        (1000, 201, SpoolStatus.OPEN),
        (1000, 0, SpoolStatus.EMPTY),
        (2500, 300, SpoolStatus.LOW),
        (5000, 180, SpoolStatus.LOW),
    ],
)
def test_inventory_status_uses_inclusive_weight_and_percent_thresholds(
    initial: int,
    current: int,
    expected: SpoolStatus,
) -> None:
    spool = spool_with_inventory(initial=initial, current=current)

    assert determine_inventory_status(spool) is expected
    assert spool.status is SpoolStatus.OPEN


def test_empty_has_priority_over_needs_drying() -> None:
    spool = spool_with_inventory(
        current=0,
        status=SpoolStatus.NEEDS_DRYING,
        needs_drying=True,
    )

    assert determine_inventory_status(spool) is SpoolStatus.EMPTY


def test_archived_status_is_preserved_at_low_weight() -> None:
    spool = spool_with_inventory(current=10, status=SpoolStatus.ARCHIVED)

    assert determine_inventory_status(spool) is SpoolStatus.ARCHIVED


def test_archived_timestamp_also_protects_status() -> None:
    spool = spool_with_inventory(current=10)
    spool.archived_at = datetime.now(UTC)

    assert determine_inventory_status(spool) is SpoolStatus.ARCHIVED


@pytest.mark.parametrize(
    "status",
    [SpoolStatus.SEALED, SpoolStatus.IN_USE, SpoolStatus.NEEDS_DRYING],
)
def test_special_status_is_preserved_for_positive_weight(
    status: SpoolStatus,
) -> None:
    spool = spool_with_inventory(current=100, status=status)

    assert determine_inventory_status(spool) is status


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        (SpoolStatus.LOW, 600, SpoolStatus.OPEN),
        (SpoolStatus.EMPTY, 150, SpoolStatus.LOW),
        (SpoolStatus.EMPTY, 700, SpoolStatus.OPEN),
    ],
)
def test_managed_statuses_are_recalculated_after_correction(
    previous: SpoolStatus,
    current: int,
    expected: SpoolStatus,
) -> None:
    spool = spool_with_inventory(current=current, status=previous)

    assert update_inventory_status(spool) is expected
    assert spool.status is expected
