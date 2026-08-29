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

from app.schemas.common import UtcDatetime

MaterialName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
MaterialCategory = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=1,
        max_length=50,
    ),
]
MaterialTemperature = Annotated[int, Field(ge=0, le=500)]
MaterialDensity = Annotated[
    Decimal,
    Field(gt=0, le=Decimal("10"), max_digits=5, decimal_places=3),
]


def validate_temperature_range(
    minimum: int | None,
    maximum: int | None,
    label: str,
) -> None:
    """Reject an inverted temperature range when both limits are present."""
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError(f"{label} minimum cannot exceed maximum")


class MaterialBase(BaseModel):
    """Fields shared by material creation and representation."""

    model_config = ConfigDict(extra="forbid")

    name: MaterialName
    category: MaterialCategory
    default_nozzle_temp_min: MaterialTemperature | None = None
    default_nozzle_temp_max: MaterialTemperature | None = None
    default_bed_temp_min: MaterialTemperature | None = None
    default_bed_temp_max: MaterialTemperature | None = None
    density_g_cm3: MaterialDensity | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_temperature_ranges(self) -> Self:
        validate_temperature_range(
            self.default_nozzle_temp_min,
            self.default_nozzle_temp_max,
            "nozzle temperature",
        )
        validate_temperature_range(
            self.default_bed_temp_min,
            self.default_bed_temp_max,
            "bed temperature",
        )
        return self


class MaterialCreate(MaterialBase):
    """Payload accepted when creating a material."""


class MaterialUpdate(BaseModel):
    """Editable material fields for partial updates."""

    model_config = ConfigDict(extra="forbid")

    name: MaterialName | None = None
    category: MaterialCategory | None = None
    default_nozzle_temp_min: MaterialTemperature | None = None
    default_nozzle_temp_max: MaterialTemperature | None = None
    default_bed_temp_min: MaterialTemperature | None = None
    default_bed_temp_max: MaterialTemperature | None = None
    density_g_cm3: MaterialDensity | None = None
    notes: str | None = None

    @field_validator("name", "category")
    @classmethod
    def required_fields_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("field cannot be null")
        return value

    @model_validator(mode="after")
    def validate_temperature_ranges(self) -> Self:
        validate_temperature_range(
            self.default_nozzle_temp_min,
            self.default_nozzle_temp_max,
            "nozzle temperature",
        )
        validate_temperature_range(
            self.default_bed_temp_min,
            self.default_bed_temp_max,
            "bed temperature",
        )
        return self


class MaterialRead(MaterialBase):
    """Material representation returned to clients."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    created_at: UtcDatetime
    updated_at: UtcDatetime
