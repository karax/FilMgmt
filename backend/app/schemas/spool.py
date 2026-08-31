from datetime import date
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.spool import SpoolStatus
from app.schemas.common import UtcDatetime
from app.schemas.location import LocationRead
from app.schemas.manufacturer import ManufacturerRead
from app.schemas.material import MaterialRead, validate_temperature_range

SpoolId = Annotated[int, Field(gt=0)]
SpoolProductName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
SpoolDisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=150),
]
SpoolColorName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
SpoolColorHex = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    ),
]
SpoolDiameter = Annotated[
    Decimal,
    Field(gt=0, ge=Decimal("0.5"), le=Decimal("5"), max_digits=4, decimal_places=2),
]
SpoolInitialWeight = Annotated[
    Decimal,
    Field(gt=0, max_digits=10, decimal_places=3),
]
SpoolWeight = Annotated[
    Decimal,
    Field(ge=0, max_digits=10, decimal_places=3),
]
SpoolPrice = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=2),
]
SpoolCurrency = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    ),
]
SpoolTemperature = Annotated[int, Field(ge=0, le=500)]
SpoolRemainingPercent = Annotated[Decimal, Field(ge=0, le=100)]
SpoolSearch = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=200),
    Field(
        description=(
            "Search spools by code, product name, color, manufacturer, "
            "material, or location."
        )
    ),
]


def validate_weight_range(
    initial_weight: Decimal | None,
    current_weight: Decimal | None,
) -> None:
    """Reject current weight above initial weight when both are available."""
    if (
        initial_weight is not None
        and current_weight is not None
        and current_weight > initial_weight
    ):
        raise ValueError("current filament weight cannot exceed initial weight")


def validate_filter_range(
    minimum: Decimal | None,
    maximum: Decimal | None,
    label: str,
) -> None:
    """Reject an inverted optional filter range."""
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError(f"minimum {label} cannot exceed maximum {label}")


class SpoolFilterParams(BaseModel):
    """Optional SQL filters accepted by the spool list endpoint."""

    model_config = ConfigDict(extra="forbid")

    manufacturer_id: SpoolId | None = None
    material_id: SpoolId | None = None
    location_id: SpoolId | None = None
    status: SpoolStatus | None = None
    needs_drying: bool | None = None
    min_weight_g: SpoolWeight | None = None
    max_weight_g: SpoolWeight | None = None
    min_remaining_percent: SpoolRemainingPercent | None = None
    max_remaining_percent: SpoolRemainingPercent | None = None
    include_archived: bool = False
    search: SpoolSearch | None = None

    @field_validator("search")
    @classmethod
    def empty_search_is_ignored(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        validate_filter_range(
            self.min_weight_g,
            self.max_weight_g,
            "weight",
        )
        validate_filter_range(
            self.min_remaining_percent,
            self.max_remaining_percent,
            "remaining percent",
        )
        return self


class SpoolBase(BaseModel):
    """Editable physical and commercial attributes shared by spool schemas."""

    model_config = ConfigDict(extra="forbid")

    manufacturer_id: SpoolId
    material_id: SpoolId
    location_id: SpoolId | None = None
    display_name: SpoolDisplayName | None = None
    product_name: SpoolProductName | None = None
    color_name: SpoolColorName
    color_hex: SpoolColorHex | None = None
    diameter_mm: SpoolDiameter = Decimal("1.75")
    initial_filament_weight_g: SpoolInitialWeight
    current_filament_weight_g: SpoolWeight
    empty_spool_weight_g: SpoolWeight | None = None
    purchase_price: SpoolPrice | None = None
    currency: SpoolCurrency = "EUR"
    purchase_date: date | None = None
    nozzle_temp_min: SpoolTemperature | None = None
    nozzle_temp_max: SpoolTemperature | None = None
    bed_temp_min: SpoolTemperature | None = None
    bed_temp_max: SpoolTemperature | None = None
    status: SpoolStatus = SpoolStatus.SEALED
    needs_drying: bool = False
    last_dried_at: UtcDatetime | None = None
    notes: str | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        validate_weight_range(
            self.initial_filament_weight_g,
            self.current_filament_weight_g,
        )
        validate_temperature_range(
            self.nozzle_temp_min,
            self.nozzle_temp_max,
            "nozzle temperature",
        )
        validate_temperature_range(
            self.bed_temp_min,
            self.bed_temp_max,
            "bed temperature",
        )
        return self


class SpoolCreate(SpoolBase):
    """Payload accepted when creating a spool; its code is server-generated."""

    current_filament_weight_g: SpoolWeight | None = None

    @model_validator(mode="after")
    def default_and_validate_current_weight(self) -> Self:
        if self.current_filament_weight_g is None:
            self.current_filament_weight_g = self.initial_filament_weight_g
        validate_weight_range(
            self.initial_filament_weight_g,
            self.current_filament_weight_g,
        )
        return self


class SpoolUpdate(BaseModel):
    """Editable fields excluding weight measurements.

    Current weight changes use POST /api/spools/{code}/weight so the persisted
    state and its WeightHistory event remain atomic. The service still validates
    the merged persisted state when initial weight or one side of a temperature
    range is supplied.
    """

    model_config = ConfigDict(extra="forbid")

    manufacturer_id: SpoolId | None = None
    material_id: SpoolId | None = None
    location_id: SpoolId | None = None
    display_name: SpoolDisplayName | None = None
    product_name: SpoolProductName | None = None
    color_name: SpoolColorName | None = None
    color_hex: SpoolColorHex | None = None
    diameter_mm: SpoolDiameter | None = None
    initial_filament_weight_g: SpoolInitialWeight | None = None
    empty_spool_weight_g: SpoolWeight | None = None
    purchase_price: SpoolPrice | None = None
    currency: SpoolCurrency | None = None
    purchase_date: date | None = None
    opened_at: UtcDatetime | None = None
    last_used_at: UtcDatetime | None = None
    nozzle_temp_min: SpoolTemperature | None = None
    nozzle_temp_max: SpoolTemperature | None = None
    bed_temp_min: SpoolTemperature | None = None
    bed_temp_max: SpoolTemperature | None = None
    needs_drying: bool | None = None
    last_dried_at: UtcDatetime | None = None
    notes: str | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "manufacturer_id",
        "material_id",
        "color_name",
        "diameter_mm",
        "initial_filament_weight_g",
        "currency",
        "needs_drying",
    )
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        validate_temperature_range(
            self.nozzle_temp_min,
            self.nozzle_temp_max,
            "nozzle temperature",
        )
        validate_temperature_range(
            self.bed_temp_min,
            self.bed_temp_max,
            "bed temperature",
        )
        return self


class SpoolRead(SpoolBase):
    """Complete spool representation including its related catalog records."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    code: str
    manufacturer: ManufacturerRead
    material: MaterialRead
    location: LocationRead | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
    archived_at: UtcDatetime | None
    remaining_percent: float = Field(ge=0, le=100)
