from decimal import Decimal

import pytest

from app.services.print_cost_service import (
    InvalidPrintCostDataError,
    calculate_print_material_cost,
)


def test_calculates_cost_snapshot_with_decimal_precision() -> None:
    result = calculate_print_material_cost(Decimal("21.99"), Decimal("1000"), Decimal("249"), "EUR")
    assert result.filament_cost_per_g == Decimal("0.021990")
    assert result.material_cost == Decimal("5.4755")
    assert result.currency == "EUR"


def test_calculates_cost_for_large_spool_and_zero_cases() -> None:
    result = calculate_print_material_cost(Decimal("29.99"), Decimal("2500"), Decimal("300"), "USD")
    assert result.filament_cost_per_g == Decimal("0.011996")
    assert result.material_cost == Decimal("3.5988")
    free = calculate_print_material_cost(Decimal("0"), Decimal("1000"), Decimal("249"), "GBP")
    assert free.filament_cost_per_g == Decimal("0.000000")
    assert free.material_cost == Decimal("0.0000") and free.currency == "GBP"
    zero = calculate_print_material_cost(Decimal("21.99"), Decimal("1000"), Decimal("0"), "EUR")
    assert zero.filament_cost_per_g == Decimal("0.021990")
    assert zero.material_cost == Decimal("0.0000")


@pytest.mark.parametrize(("price", "actual"), [(None, Decimal("20")), (Decimal("20"), None)])
def test_returns_no_snapshot_when_price_or_actual_is_unknown(price: Decimal | None, actual: Decimal | None) -> None:
    assert calculate_print_material_cost(price, Decimal("1000"), actual, "EUR").material_cost is None


def test_rejects_invalid_legacy_initial_weight() -> None:
    with pytest.raises(InvalidPrintCostDataError):
        calculate_print_material_cost(Decimal("20"), Decimal("0"), Decimal("1"), "EUR")
