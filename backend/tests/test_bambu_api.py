from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.bambu import get_bambu_integration
from app.integrations.bambu.config import BambuMqttSettings
from app.integrations.bambu.models import BambuConnectionState
from app.integrations.bambu.parser import BambuReportParser
from app.integrations.bambu.service import BambuIntegration
from app.main import app


FULL_REPORT = (Path(__file__).parent / "fixtures" / "bambu_report_full.json").read_bytes()


@pytest.fixture
def configured_integration() -> BambuIntegration:
    return BambuIntegration(
        BambuMqttSettings(
            host="192.0.2.10",
            serial="01P00TESTSERIAL",
            access_code="never-return-this-secret",
        ),
    )


@pytest.fixture
def bambu_client(configured_integration: BambuIntegration) -> Iterator[TestClient]:
    app.dependency_overrides[get_bambu_integration] = lambda: configured_integration
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_bambu_integration, None)


def test_bambu_status_is_read_only_normalized_diagnostic(
    bambu_client: TestClient,
) -> None:
    response = bambu_client.get("/api/integrations/bambu/status")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "connected": False,
        "connection_state": "DISCONNECTED",
        "missing_configuration": [],
        "configuration_error": None,
        "serial": "01P00TESTSERIAL",
        "last_update_at": None,
        "state": "UNKNOWN",
        "raw_state": None,
        "progress": None,
        "current_layer": None,
        "total_layers": None,
        "remaining_time_minutes": None,
        "current_print": None,
        "gcode_file": None,
        "project_name": None,
        "project_id": None,
        "profile_id": None,
        "task_id": None,
        "subtask_id": None,
        "current_tray": None,
        "ams": [],
        "external_tray": None,
        "active_print_job_id": None,
        "ftps_configured": False,
        "ftps_reachable": None,
        "last_ftps_success_at": None,
        "last_ftps_error_code": None,
    }


def test_credentials_are_not_returned_by_diagnostic_representation(
    bambu_client: TestClient,
    configured_integration: BambuIntegration,
) -> None:
    response = bambu_client.get("/api/integrations/bambu/status")
    serialized_diagnostic = repr(configured_integration.diagnostic())

    assert "never-return-this-secret" not in response.text
    assert "access_code" not in response.text
    assert "never-return-this-secret" not in serialized_diagnostic
    assert "access_code" not in serialized_diagnostic


def test_bambu_status_returns_current_normalized_print_and_ams_state(
    bambu_client: TestClient,
    configured_integration: BambuIntegration,
) -> None:
    configured_integration.state_store.set_connection(BambuConnectionState.CONNECTED)
    configured_integration.state_store.merge(BambuReportParser().parse(FULL_REPORT))

    payload = bambu_client.get("/api/integrations/bambu/status").json()

    assert payload["connected"] is True
    assert payload["state"] == "PRINTING"
    assert payload["raw_state"] == "RUNNING"
    assert payload["current_print"] == "Calibration Cube"
    assert payload["project_name"] == "Calibration Project"
    assert payload["progress"] == 42
    assert payload["current_layer"] == 71
    assert payload["total_layers"] == 166
    assert payload["current_tray"] == "1"
    assert payload["last_update_at"].endswith("Z")
    assert payload["ams"][0]["unit_id"] == "0"
    assert payload["ams"][0]["trays"][0]["material_type"] == "PLA"
    assert payload["ams"][0]["trays"][0]["tag_uid"] == "AABBCCDDEEFF0011"
    assert payload["external_tray"]["tray_id"] == "254"


def test_bambu_status_endpoint_is_registered_in_openapi(
    bambu_client: TestClient,
) -> None:
    paths = bambu_client.get("/openapi.json").json()["paths"]

    assert list(paths["/api/integrations/bambu/status"]) == ["get"]
