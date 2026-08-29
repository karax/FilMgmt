from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    HttpUrl,
    StringConstraints,
    UrlConstraints,
    field_validator,
)

from app.schemas.common import UtcDatetime

ManufacturerName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=150),
]
ManufacturerWebsite = Annotated[
    HttpUrl,
    UrlConstraints(max_length=500, allowed_schemes=["http", "https"]),
]


class ManufacturerBase(BaseModel):
    """Fields shared by manufacturer creation and representation."""

    model_config = ConfigDict(extra="forbid")

    name: ManufacturerName
    website: ManufacturerWebsite | None = None


class ManufacturerCreate(ManufacturerBase):
    """Payload accepted when creating a manufacturer."""


class ManufacturerUpdate(BaseModel):
    """Editable manufacturer fields for partial updates."""

    model_config = ConfigDict(extra="forbid")

    name: ManufacturerName | None = None
    website: ManufacturerWebsite | None = None

    @field_validator("name")
    @classmethod
    def name_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return value


class ManufacturerRead(ManufacturerBase):
    """Manufacturer representation returned to clients."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    created_at: UtcDatetime
    updated_at: UtcDatetime
