from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def normalize_timestamp_to_utc(value: datetime) -> datetime:
    """Represent database timestamps consistently as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(normalize_timestamp_to_utc)]
