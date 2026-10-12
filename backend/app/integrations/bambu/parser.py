import json
from collections.abc import Callable, Mapping
from typing import Any

from app.integrations.bambu.models import (
    BambuAmsUnitPatch,
    BambuPrintState,
    BambuStatePatch,
    BambuTrayPatch,
)


class BambuReportParseError(ValueError):
    """Raised when an MQTT report is not a usable Bambu JSON object."""


_PRINT_STATE_MAP = {
    "IDLE": BambuPrintState.IDLE,
    "READY": BambuPrintState.IDLE,
    "PREPARE": BambuPrintState.PREPARING,
    "PREPARING": BambuPrintState.PREPARING,
    "INIT": BambuPrintState.PREPARING,
    "INITING": BambuPrintState.PREPARING,
    "SLICING": BambuPrintState.PREPARING,
    "RUNNING": BambuPrintState.PRINTING,
    "PRINTING": BambuPrintState.PRINTING,
    "PAUSE": BambuPrintState.PAUSED,
    "PAUSED": BambuPrintState.PAUSED,
    "FINISH": BambuPrintState.FINISHED,
    "FINISHED": BambuPrintState.FINISHED,
    "COMPLETED": BambuPrintState.FINISHED,
    "FAILED": BambuPrintState.FAILED,
    "FAILURE": BambuPrintState.FAILED,
    "ERROR": BambuPrintState.FAILED,
    "CANCEL": BambuPrintState.CANCELLED,
    "CANCELLED": BambuPrintState.CANCELLED,
    "CANCELED": BambuPrintState.CANCELLED,
    "ABORT": BambuPrintState.CANCELLED,
    "ABORTED": BambuPrintState.CANCELLED,
}

_PRINT_FIELDS: tuple[tuple[str, str, Callable[[object], object | None]], ...] = (
    ("subtask_name", "current_print", lambda value: _as_string(value)),
    ("gcode_file", "gcode_file", lambda value: _as_string(value)),
    ("project_name", "project_name", lambda value: _as_string(value)),
    ("project_id", "project_id", lambda value: _as_string(value)),
    ("profile_id", "profile_id", lambda value: _as_string(value)),
    ("task_id", "task_id", lambda value: _as_string(value)),
    ("subtask_id", "subtask_id", lambda value: _as_string(value)),
    ("mc_percent", "progress_percent", lambda value: _as_int(value)),
    ("layer_num", "current_layer", lambda value: _as_int(value)),
    ("total_layer_num", "total_layers", lambda value: _as_int(value)),
    ("mc_remaining_time", "remaining_time_minutes", lambda value: _as_int(value)),
    ("tray_now", "current_tray", lambda value: _as_string(value)),
)

_TRAY_FIELDS: tuple[tuple[str, str, Callable[[object], object | None]], ...] = (
    ("tray_type", "material_type", lambda value: _as_string(value)),
    ("tray_color", "color", lambda value: _as_string(value)),
    ("tray_info_idx", "profile_id", lambda value: _as_string(value)),
    ("setting_id", "setting_id", lambda value: _as_string(value)),
    ("tray_sub_brands", "brand", lambda value: _as_string(value)),
    ("tag_uid", "tag_uid", lambda value: _as_string(value)),
    ("tray_uuid", "tray_uuid", lambda value: _as_string(value)),
    ("remain", "remaining_percent", lambda value: _as_int(value)),
    ("nozzle_temp_min", "nozzle_temp_min", lambda value: _as_int(value)),
    ("nozzle_temp_max", "nozzle_temp_max", lambda value: _as_int(value)),
)


class BambuReportParser:
    """Translate protocol-specific report JSON into a normalized delta."""

    def parse(self, payload: bytes | str) -> BambuStatePatch:
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BambuReportParseError("Bambu report is not valid JSON.") from error

        if not isinstance(document, dict):
            raise BambuReportParseError("Bambu report must be a JSON object.")

        print_report = document.get("print")
        if print_report is None:
            return BambuStatePatch()
        if not isinstance(print_report, dict):
            raise BambuReportParseError("Bambu report 'print' field must be an object.")

        values: dict[str, object | None] = {}
        if "gcode_state" in print_report:
            raw_state = _as_string(print_report["gcode_state"])
            values["raw_print_state"] = raw_state
            values["print_state"] = normalize_print_state(raw_state)

        _copy_known_fields(print_report, values, _PRINT_FIELDS)

        ams_units: tuple[BambuAmsUnitPatch, ...] = ()
        ams_report = print_report.get("ams")
        if isinstance(ams_report, dict):
            if "tray_now" in ams_report and "current_tray" not in values:
                values["current_tray"] = _as_string(ams_report["tray_now"])
            ams_units = _parse_ams_units(ams_report.get("ams"))

        external_tray = None
        if "vt_tray" in print_report and isinstance(print_report["vt_tray"], dict):
            external_tray = _parse_tray(print_report["vt_tray"])

        return BambuStatePatch(
            values=values,
            ams_units=ams_units,
            external_tray=external_tray,
        )


def normalize_print_state(raw_state: str | None) -> BambuPrintState:
    if raw_state is None:
        return BambuPrintState.UNKNOWN
    return _PRINT_STATE_MAP.get(raw_state.strip().upper(), BambuPrintState.UNKNOWN)


def _parse_ams_units(value: object) -> tuple[BambuAmsUnitPatch, ...]:
    if not isinstance(value, list):
        return ()

    units: list[BambuAmsUnitPatch] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        unit_id = _as_string(item.get("id"))
        if unit_id is None:
            continue
        unit_values: dict[str, object | None] = {}
        if "humidity" in item:
            unit_values["humidity"] = _as_int(item["humidity"])
        if "temp" in item:
            unit_values["temperature_c"] = _as_float(item["temp"])
        trays = _parse_trays(item.get("tray"))
        units.append(
            BambuAmsUnitPatch(
                unit_id=unit_id,
                values=unit_values,
                trays=trays,
            ),
        )
    return tuple(units)


def _parse_trays(value: object) -> tuple[BambuTrayPatch, ...]:
    if not isinstance(value, list):
        return ()
    trays = [_parse_tray(item) for item in value if isinstance(item, dict)]
    return tuple(tray for tray in trays if tray is not None)


def _parse_tray(value: Mapping[str, Any]) -> BambuTrayPatch | None:
    tray_id = _as_string(value.get("id"))
    if tray_id is None:
        return None
    values: dict[str, object | None] = {}
    _copy_known_fields(value, values, _TRAY_FIELDS)
    return BambuTrayPatch(tray_id=tray_id, values=values)


def _copy_known_fields(
    source: Mapping[str, Any],
    target: dict[str, object | None],
    fields: tuple[tuple[str, str, Callable[[object], object | None]], ...],
) -> None:
    for source_name, target_name, converter in fields:
        if source_name in source:
            target[target_name] = converter(source[source_name])


def _as_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _as_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if not converted.is_integer():
        return None
    return int(converted)


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
