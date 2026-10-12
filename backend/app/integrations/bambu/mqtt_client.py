from __future__ import annotations

from collections.abc import Callable
import logging
import ssl

import paho.mqtt.client as mqtt

from app.integrations.bambu.config import BambuMqttSettings
from app.integrations.bambu.models import BambuConnectionState


logger = logging.getLogger(__name__)

ConnectionHandler = Callable[[BambuConnectionState], None]
PayloadHandler = Callable[[bytes], None]


class BambuMqttClient:
    """Passive MQTT subscriber for one Bambu report topic.

    This adapter intentionally exposes no publish method. It cannot send printer
    commands or status requests.
    """

    def __init__(
        self,
        settings: BambuMqttSettings,
        *,
        on_connection: ConnectionHandler,
        on_payload: PayloadHandler,
    ) -> None:
        if not settings.configured:
            raise ValueError("Bambu MQTT client requires complete configuration.")
        self._settings = settings
        self._on_connection = on_connection
        self._on_payload = on_payload
        self._started = False
        self._stopping = False
        self._has_connected = False

        client_id = f"fcc-{(settings.serial or '')[-12:]}"
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            reconnect_on_failure=True,
        )
        self._client.username_pw_set("bblp", settings.access_code)
        self._client.reconnect_delay_set(min_delay=2, max_delay=60)
        if settings.tls_enabled:
            self._client.tls_set_context(_local_printer_tls_context())

        self._client.on_connect = self._handle_connect
        self._client.on_connect_fail = self._handle_connect_fail
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message
        self._client.on_subscribe = self._handle_subscribe

    def start(self) -> None:
        if self._started:
            return
        self._stopping = False
        self._on_connection(BambuConnectionState.CONNECTING)
        logger.info(
            "Bambu MQTT connection attempt host=%s port=%d serial=%s tls=%s",
            self._settings.host,
            self._settings.port,
            self._settings.serial,
            self._settings.tls_enabled,
        )
        self._client.connect_async(
            self._settings.host or "",
            port=self._settings.port,
            keepalive=60,
        )
        result = self._client.loop_start()
        if result != mqtt.MQTT_ERR_SUCCESS:
            self._on_connection(BambuConnectionState.DISCONNECTED)
            raise RuntimeError("Could not start the Bambu MQTT network loop.")
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._stopping = True
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()
            self._started = False
            self._on_connection(BambuConnectionState.DISCONNECTED)

    def _handle_connect(
        self,
        client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            self._on_connection(BambuConnectionState.DISCONNECTED)
            logger.warning(
                "Bambu MQTT connection rejected serial=%s reason=%s",
                self._settings.serial,
                reason_code,
            )
            return

        self._on_connection(BambuConnectionState.CONNECTED)
        connection_label = "reconnected" if self._has_connected else "connected"
        self._has_connected = True
        logger.info(
            "Bambu MQTT %s serial=%s",
            connection_label,
            self._settings.serial,
        )

        result, _message_id = client.subscribe(self._settings.report_topic, qos=0)
        if result != mqtt.MQTT_ERR_SUCCESS:
            logger.error(
                "Bambu MQTT subscription request failed serial=%s result=%s",
                self._settings.serial,
                result,
            )

    def _handle_connect_fail(self, _client: mqtt.Client, _userdata: object) -> None:
        self._on_connection(BambuConnectionState.DISCONNECTED)
        logger.warning(
            "Bambu MQTT connection failed serial=%s; reconnect backoff is active",
            self._settings.serial,
        )

    def _handle_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        self._on_connection(BambuConnectionState.DISCONNECTED)
        if self._stopping:
            logger.info("Bambu MQTT disconnected serial=%s", self._settings.serial)
        else:
            logger.warning(
                "Bambu MQTT disconnected serial=%s reason=%s; reconnect backoff is active",
                self._settings.serial,
                reason_code,
            )

    def _handle_message(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        logger.debug(
            "Bambu MQTT report received serial=%s bytes=%d",
            self._settings.serial,
            len(message.payload),
        )
        self._on_payload(bytes(message.payload))

    def _handle_subscribe(
        self,
        _client: mqtt.Client,
        _userdata: object,
        message_id: int,
        reason_codes: list[mqtt.ReasonCode],
        _properties: mqtt.Properties | None,
    ) -> None:
        if any(reason_code.is_failure for reason_code in reason_codes):
            logger.error(
                "Bambu MQTT subscription rejected serial=%s message_id=%d",
                self._settings.serial,
                message_id,
            )
            return
        logger.info(
            "Bambu MQTT subscribed serial=%s topic=%s",
            self._settings.serial,
            self._settings.report_topic,
        )


def _local_printer_tls_context() -> ssl.SSLContext:
    """Build a TLS context used only by the local printer MQTT socket.

    P1S firmware presents a self-signed certificate that cannot be verified
    against the system trust store. Encryption stays enabled, while certificate
    and hostname verification are disabled only on this dedicated context.
    """

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context
