from dataclasses import dataclass, field
import os


DEFAULT_BAMBU_MQTT_PORT = 8883
DEFAULT_BAMBU_MQTT_TLS = True
DEFAULT_BAMBU_FTPS_PORT = 990
DEFAULT_BAMBU_FTPS_TIMEOUT_SECONDS = 12
DEFAULT_BAMBU_FTPS_MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
BAMBU_FTPS_USERNAME = "bblp"


@dataclass(frozen=True)
class BambuMqttSettings:
    """Configuration for one local Bambu printer.

    The access code is deliberately omitted from ``repr`` so routine debugging
    cannot accidentally print the credential.
    """

    host: str | None
    serial: str | None
    access_code: str | None = field(repr=False)
    port: int = DEFAULT_BAMBU_MQTT_PORT
    tls_enabled: bool = DEFAULT_BAMBU_MQTT_TLS
    debug_payloads: bool = False
    configuration_error: str | None = None

    @property
    def configured(self) -> bool:
        return (
            self.configuration_error is None
            and bool(self.host)
            and bool(self.serial)
            and bool(self.access_code)
        )

    @property
    def missing_variables(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.host:
            missing.append("BAMBU_HOST")
        if not self.serial:
            missing.append("BAMBU_SERIAL")
        if not self.access_code:
            missing.append("BAMBU_ACCESS_CODE")
        return tuple(missing)

    @property
    def report_topic(self) -> str:
        if not self.serial:
            raise RuntimeError("BAMBU_SERIAL is required to build the report topic.")
        return f"device/{self.serial}/report"


@dataclass(frozen=True)
class BambuFtpsSettings:
    """Read-only LAN FTPS settings, with the credential excluded from repr."""

    host: str | None
    access_code: str | None = field(repr=False)
    port: int = DEFAULT_BAMBU_FTPS_PORT
    username: str = BAMBU_FTPS_USERNAME
    timeout_seconds: int = DEFAULT_BAMBU_FTPS_TIMEOUT_SECONDS
    max_download_bytes: int = DEFAULT_BAMBU_FTPS_MAX_DOWNLOAD_BYTES
    configuration_error: str | None = None

    @property
    def configured(self) -> bool:
        return self.configuration_error is None and bool(self.host) and bool(self.access_code)

    @property
    def missing_variables(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.host:
            missing.append("BAMBU_HOST")
        if not self.access_code:
            missing.append("BAMBU_ACCESS_CODE")
        return tuple(missing)


def load_bambu_mqtt_settings() -> BambuMqttSettings:
    host = _optional_value("BAMBU_HOST")
    serial = _optional_value("BAMBU_SERIAL")
    access_code = _optional_value("BAMBU_ACCESS_CODE")
    port, port_error = _mqtt_port()
    tls_enabled, tls_error = _mqtt_tls()
    debug_payloads, debug_error = _boolean_setting(
        "BAMBU_DEBUG_PAYLOADS",
        default=False,
    )
    return BambuMqttSettings(
        host=host,
        serial=serial,
        access_code=access_code,
        port=port,
        tls_enabled=tls_enabled,
        debug_payloads=debug_payloads,
        configuration_error=port_error or tls_error or debug_error,
    )


def load_bambu_ftps_settings() -> BambuFtpsSettings:
    port, port_error = _port_setting("BAMBU_FTPS_PORT", DEFAULT_BAMBU_FTPS_PORT)
    return BambuFtpsSettings(
        host=_optional_value("BAMBU_HOST"),
        access_code=_optional_value("BAMBU_ACCESS_CODE"),
        port=port,
        configuration_error=port_error,
    )


def _optional_value(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _mqtt_port() -> tuple[int, str | None]:
    return _port_setting("BAMBU_PORT", DEFAULT_BAMBU_MQTT_PORT)


def _port_setting(name: str, default: int) -> tuple[int, str | None]:
    configured = _optional_value(name)
    if configured is None:
        return default, None
    try:
        port = int(configured)
    except ValueError:
        return default, f"{name} must be an integer from 1 to 65535."
    if not 1 <= port <= 65535:
        return default, f"{name} must be an integer from 1 to 65535."
    return port, None


def _mqtt_tls() -> tuple[bool, str | None]:
    return _boolean_setting("BAMBU_MQTT_TLS", default=DEFAULT_BAMBU_MQTT_TLS)


def _boolean_setting(name: str, *, default: bool) -> tuple[bool, str | None]:
    configured = _optional_value(name)
    if configured is None:
        return default, None
    normalized = configured.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True, None
    if normalized in {"0", "false", "no", "off"}:
        return False, None
    return default, f"{name} must be a boolean."
