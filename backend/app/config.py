import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = PROJECT_ROOT / "data"

DEFAULT_GCODE_UPLOAD_DIRECTORY = DATA_DIRECTORY / "uploads" / "gcode"
DEFAULT_PRINT_JOB_MEDIA_DIRECTORY = DATA_DIRECTORY / "print-jobs"
DEFAULT_GCODE_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
DEFAULT_GCODE_UPLOAD_RETENTION_DAYS = 30
DEFAULT_GCODE_UPLOAD_MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_GCODE_UPLOAD_TEMP_STALE_SECONDS = 60 * 60
DEFAULT_GCODE_UPLOAD_CLEANUP_ENABLED = True
DEFAULT_GCODE_UPLOAD_RETENTION_ENABLED = True
GCODE_UPLOAD_CHUNK_BYTES = 1024 * 1024


def get_print_job_media_directory() -> Path:
    configured = os.getenv("PRINT_JOB_MEDIA_DIRECTORY")
    return Path(configured).expanduser() if configured else DEFAULT_PRINT_JOB_MEDIA_DIRECTORY


def get_gcode_upload_directory() -> Path:
    configured = os.getenv("GCODE_UPLOAD_DIRECTORY")
    return Path(configured).expanduser() if configured else DEFAULT_GCODE_UPLOAD_DIRECTORY


def get_gcode_max_upload_bytes() -> int:
    return _positive_int("GCODE_MAX_UPLOAD_BYTES", DEFAULT_GCODE_MAX_UPLOAD_BYTES)


def get_gcode_upload_retention_days() -> int:
    return _non_negative_int(
        "GCODE_UPLOAD_RETENTION_DAYS",
        DEFAULT_GCODE_UPLOAD_RETENTION_DAYS,
    )


def get_gcode_upload_max_total_bytes() -> int:
    return _positive_int(
        "GCODE_UPLOAD_MAX_TOTAL_BYTES",
        DEFAULT_GCODE_UPLOAD_MAX_TOTAL_BYTES,
    )


def get_gcode_upload_temp_stale_seconds() -> int:
    return _positive_int(
        "GCODE_UPLOAD_TEMP_STALE_SECONDS",
        DEFAULT_GCODE_UPLOAD_TEMP_STALE_SECONDS,
    )


def get_gcode_upload_cleanup_enabled() -> bool:
    return _boolean(
        "GCODE_UPLOAD_CLEANUP_ENABLED",
        DEFAULT_GCODE_UPLOAD_CLEANUP_ENABLED,
    )


def get_gcode_upload_retention_enabled() -> bool:
    return _boolean(
        "GCODE_UPLOAD_RETENTION_ENABLED",
        DEFAULT_GCODE_UPLOAD_RETENTION_ENABLED,
    )


def _positive_int(name: str, default: int) -> int:
    value = _integer(name, default)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value


def _non_negative_int(name: str, default: int) -> int:
    value = _integer(name, default)
    if value < 0:
        raise ValueError(f"{name} must be zero or greater.")
    return value


def _integer(name: str, default: int) -> int:
    configured = os.getenv(name)
    if configured is None:
        return default

    try:
        value = int(configured)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error
    return value


def _boolean(name: str, default: bool) -> bool:
    configured = os.getenv(name)
    if configured is None:
        return default
    normalized = configured.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean.")
