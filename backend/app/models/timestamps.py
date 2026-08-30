from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def normalize_utc(value: datetime) -> datetime:
    """Treat SQLite's timezone-naive round-trips as UTC timestamps."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
