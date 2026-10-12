import pytest

from app.integrations.bambu.config import (
    DEFAULT_BAMBU_FTPS_PORT,
    DEFAULT_BAMBU_MQTT_PORT,
    BambuFtpsSettings,
    BambuMqttSettings,
    load_bambu_ftps_settings,
    load_bambu_mqtt_settings,
)


BAMBU_VARIABLES = (
    "BAMBU_HOST",
    "BAMBU_PORT",
    "BAMBU_SERIAL",
    "BAMBU_ACCESS_CODE",
    "BAMBU_MQTT_TLS",
    "BAMBU_DEBUG_PAYLOADS",
    "BAMBU_FTPS_PORT",
)


def clear_bambu_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in BAMBU_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_bambu_configuration_defaults_to_disabled_tls_port_8883(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_bambu_environment(monkeypatch)

    settings = load_bambu_mqtt_settings()

    assert settings.configured is False
    assert settings.port == DEFAULT_BAMBU_MQTT_PORT
    assert settings.tls_enabled is True
    assert settings.debug_payloads is False
    assert settings.missing_variables == (
        "BAMBU_HOST",
        "BAMBU_SERIAL",
        "BAMBU_ACCESS_CODE",
    )


def test_complete_bambu_configuration_uses_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_bambu_environment(monkeypatch)
    monkeypatch.setenv("BAMBU_HOST", "192.0.2.10")
    monkeypatch.setenv("BAMBU_PORT", "1883")
    monkeypatch.setenv("BAMBU_SERIAL", "01P00TESTSERIAL")
    monkeypatch.setenv("BAMBU_ACCESS_CODE", "test-secret")
    monkeypatch.setenv("BAMBU_MQTT_TLS", "false")
    monkeypatch.setenv("BAMBU_DEBUG_PAYLOADS", "true")

    settings = load_bambu_mqtt_settings()

    assert settings.configured is True
    assert settings.port == 1883
    assert settings.tls_enabled is False
    assert settings.debug_payloads is True
    assert settings.report_topic == "device/01P00TESTSERIAL/report"


@pytest.mark.parametrize(
    ("name", "value", "expected_error"),
    [
        ("BAMBU_PORT", "not-a-port", "BAMBU_PORT"),
        ("BAMBU_PORT", "70000", "BAMBU_PORT"),
        ("BAMBU_MQTT_TLS", "sometimes", "BAMBU_MQTT_TLS"),
        ("BAMBU_DEBUG_PAYLOADS", "sometimes", "BAMBU_DEBUG_PAYLOADS"),
    ],
)
def test_invalid_bambu_configuration_disables_integration_without_raising(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    expected_error: str,
) -> None:
    clear_bambu_environment(monkeypatch)
    monkeypatch.setenv("BAMBU_HOST", "192.0.2.10")
    monkeypatch.setenv("BAMBU_SERIAL", "01P00TESTSERIAL")
    monkeypatch.setenv("BAMBU_ACCESS_CODE", "test-secret")
    monkeypatch.setenv(name, value)

    settings = load_bambu_mqtt_settings()

    assert settings.configured is False
    assert settings.configuration_error is not None
    assert expected_error in settings.configuration_error
    assert value not in settings.configuration_error


def test_access_code_is_redacted_from_settings_representation() -> None:
    settings = BambuMqttSettings(
        host="192.0.2.10",
        serial="01P00TESTSERIAL",
        access_code="do-not-print-this",
    )

    assert "do-not-print-this" not in repr(settings)


def test_ftps_reuses_host_and_access_code_with_dedicated_port(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_bambu_environment(monkeypatch)
    monkeypatch.setenv("BAMBU_HOST", "192.0.2.10")
    monkeypatch.setenv("BAMBU_ACCESS_CODE", "ftps-secret")
    monkeypatch.setenv("BAMBU_FTPS_PORT", "1990")

    settings = load_bambu_ftps_settings()

    assert settings.configured is True
    assert settings.port == 1990
    assert settings.username == "bblp"
    assert "ftps-secret" not in repr(settings)


def test_invalid_ftps_port_disables_only_ftps(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_bambu_environment(monkeypatch)
    monkeypatch.setenv("BAMBU_HOST", "192.0.2.10")
    monkeypatch.setenv("BAMBU_ACCESS_CODE", "ftps-secret")
    monkeypatch.setenv("BAMBU_FTPS_PORT", "invalid")

    settings = load_bambu_ftps_settings()

    assert settings.configured is False
    assert settings.port == DEFAULT_BAMBU_FTPS_PORT
    assert settings.configuration_error and "BAMBU_FTPS_PORT" in settings.configuration_error
    assert "ftps-secret" not in settings.configuration_error
