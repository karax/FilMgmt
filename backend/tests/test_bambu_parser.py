from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.integrations.bambu.models import BambuPrintState
from app.integrations.bambu.parser import BambuReportParseError, BambuReportParser, normalize_print_state
from app.integrations.bambu.state_store import BambuStateStore


FIXTURES = Path(__file__).parent / "fixtures"
FULL_REPORT = (FIXTURES / "bambu_report_full.json").read_bytes()
DELTA_REPORT = (FIXTURES / "bambu_report_delta.json").read_bytes()


def test_mqtt_report_json_is_parsed_into_normalized_fields() -> None:
    patch = BambuReportParser().parse(FULL_REPORT)

    assert patch.values == {
        "raw_print_state": "RUNNING",
        "print_state": BambuPrintState.PRINTING,
        "current_print": "Calibration Cube",
        "gcode_file": "/data/Metadata/calibration_cube.gcode",
        "project_name": "Calibration Project",
        "project_id": "project-12",
        "profile_id": "profile-34",
        "task_id": "task-56",
        "subtask_id": "subtask-78",
        "progress_percent": 42,
        "current_layer": 71,
        "total_layers": 166,
        "remaining_time_minutes": 38,
        "current_tray": "1",
    }


def test_unknown_json_properties_do_not_break_parsing() -> None:
    patch = BambuReportParser().parse(
        '{"print":{"gcode_state":"NEW_FIRMWARE_STATE","new_value":42},'
        '"another_new_value":true}',
    )

    assert patch.values["raw_print_state"] == "NEW_FIRMWARE_STATE"
    assert patch.values["print_state"] is BambuPrintState.UNKNOWN


@pytest.mark.parametrize(
    ("raw_state", "normalized"),
    [
        ("IDLE", BambuPrintState.IDLE),
        ("PREPARE", BambuPrintState.PREPARING),
        ("RUNNING", BambuPrintState.PRINTING),
        ("PAUSE", BambuPrintState.PAUSED),
        ("FINISH", BambuPrintState.FINISHED),
        ("FAILED", BambuPrintState.FAILED),
        ("CANCELLED", BambuPrintState.CANCELLED),
    ],
)
def test_observed_lifecycle_state_strings_are_normalized(
    raw_state: str,
    normalized: BambuPrintState,
) -> None:
    assert normalize_print_state(raw_state) is normalized


def test_ams_units_trays_and_external_spool_are_parsed() -> None:
    patch = BambuReportParser().parse(FULL_REPORT)

    assert len(patch.ams_units) == 1
    unit = patch.ams_units[0]
    assert unit.unit_id == "0"
    assert unit.values == {"humidity": 3, "temperature_c": 24.5}
    assert len(unit.trays) == 2
    assert unit.trays[0].values == {
        "material_type": "PLA",
        "color": "FF0000FF",
        "profile_id": "GFA00",
        "setting_id": "GFSA00_01",
        "brand": "Bambu PLA Basic",
        "tag_uid": "AABBCCDDEEFF0011",
        "tray_uuid": "tray-uuid-0",
        "remaining_percent": 87,
        "nozzle_temp_min": 190,
        "nozzle_temp_max": 240,
    }
    assert patch.external_tray is not None
    assert patch.external_tray.tray_id == "254"
    assert patch.external_tray.values["material_type"] == "PLA"


def test_partial_reports_are_deep_merged_without_erasing_missing_fields() -> None:
    parser = BambuReportParser()
    store = BambuStateStore("01P00TESTSERIAL", configured=True)
    first_timestamp = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
    second_timestamp = datetime(2026, 10, 5, 10, 1, tzinfo=UTC)

    store.merge(parser.parse(FULL_REPORT), received_at=first_timestamp)
    state = store.merge(parser.parse(DELTA_REPORT), received_at=second_timestamp)

    assert state.print_state is BambuPrintState.PRINTING
    assert state.current_print == "Calibration Cube"
    assert state.gcode_file == "/data/Metadata/calibration_cube.gcode"
    assert state.project_name == "Calibration Project"
    assert state.progress_percent == 43
    assert state.current_layer == 72
    assert state.total_layers == 166
    assert state.remaining_time_minutes == 38
    assert state.last_update_at == second_timestamp
    assert len(state.ams_units) == 1
    assert len(state.ams_units[0].trays) == 2
    first_tray, second_tray = state.ams_units[0].trays
    assert first_tray.tag_uid == "AABBCCDDEEFF0011"
    assert second_tray.material_type == "PETG"
    assert second_tray.color == "0000FFFF"
    assert second_tray.remaining_percent == 64
    assert state.external_tray is not None
    assert state.external_tray.material_type == "PLA"


def test_field_explicitly_reported_as_null_can_be_cleared() -> None:
    parser = BambuReportParser()
    store = BambuStateStore("01P00TESTSERIAL", configured=True)
    store.merge(parser.parse(FULL_REPORT))

    state = store.merge(parser.parse('{"print":{"subtask_name":null}}'))

    assert state.current_print is None
    assert state.gcode_file == "/data/Metadata/calibration_cube.gcode"


@pytest.mark.parametrize("payload", [b"not-json", b"[]", b'{"print":[]}'])
def test_malformed_reports_are_rejected(payload: bytes) -> None:
    with pytest.raises(BambuReportParseError):
        BambuReportParser().parse(payload)
