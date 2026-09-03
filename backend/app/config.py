import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = PROJECT_ROOT / "data"

DEFAULT_GCODE_UPLOAD_DIRECTORY = DATA_DIRECTORY / "uploads" / "gcode"
DEFAULT_GCODE_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
GCODE_UPLOAD_CHUNK_BYTES = 1024 * 1024


def get_gcode_upload_directory() -> Path:
    configured = os.getenv("GCODE_UPLOAD_DIRECTORY")
    return Path(configured).expanduser() if configured else DEFAULT_GCODE_UPLOAD_DIRECTORY


def get_gcode_max_upload_bytes() -> int:
    configured = os.getenv("GCODE_MAX_UPLOAD_BYTES")
    if configured is None:
        return DEFAULT_GCODE_MAX_UPLOAD_BYTES

    try:
        value = int(configured)
    except ValueError as error:
        raise ValueError("GCODE_MAX_UPLOAD_BYTES must be an integer.") from error
    if value <= 0:
        raise ValueError("GCODE_MAX_UPLOAD_BYTES must be greater than zero.")
    return value
