from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


FILAMENT_COST_PRECISION = Decimal("0.000001")
MATERIAL_COST_PRECISION = Decimal("0.0001")


class InvalidPrintCostDataError(Exception):
    """Raised when legacy spool data cannot safely produce a cost snapshot."""


@dataclass(frozen=True)
class PrintMaterialCost:
    filament_cost_per_g: Decimal | None
    material_cost: Decimal | None
    currency: str | None


def calculate_print_material_cost(
    purchase_price: Decimal | None,
    initial_weight_g: Decimal,
    actual_weight_g: Decimal | None,
    currency: str,
) -> PrintMaterialCost:
    """Return an immutable material-cost snapshot using Decimal arithmetic."""
    if actual_weight_g is None or purchase_price is None:
        return PrintMaterialCost(None, None, None)
    if initial_weight_g <= 0:
        raise InvalidPrintCostDataError
    per_gram = (purchase_price / initial_weight_g).quantize(
        FILAMENT_COST_PRECISION,
        rounding=ROUND_HALF_UP,
    )
    material_cost = (actual_weight_g * per_gram).quantize(
        MATERIAL_COST_PRECISION,
        rounding=ROUND_HALF_UP,
    )
    return PrintMaterialCost(per_gram, material_cost, currency)
