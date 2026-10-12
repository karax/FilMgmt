import ssl

import paho.mqtt.client as mqtt
import pytest

from app.integrations.bambu.config import BambuMqttSettings
from app.integrations.bambu.models import BambuConnectionState
from app.integrations.bambu.mqtt_client import BambuMqttClient


class FakeReasonCode:
    def __init__(self, *, failure: bool = False) -> None:
        self.is_failure = failure

    def __str__(self) -> str:
        return "fake-reason"


class FakePahoClient:
    def __init__(self) -> None:
        self.creation_options = None
        self.username = None
        self.password = None
        self.reconnect_delays = None
        self.tls_context = None
        self.connect_options = None
        self.subscriptions: list[tuple[str, int]] = []
        self.loop_started = False
        self.disconnected = False
        self.on_connect = None
        self.on_connect_fail = None
        self.on_disconnect = None
        self.on_message = None
        self.on_subscribe = None

    def username_pw_set(self, username: str, password: str | None) -> None:
        self.username = username
        self.password = password

    def reconnect_delay_set(self, min_delay: int, max_delay: int) -> None:
        self.reconnect_delays = (min_delay, max_delay)

    def tls_set_context(self, context: ssl.SSLContext) -> None:
        self.tls_context = context

    def connect_async(self, host: str, *, port: int, keepalive: int) -> None:
        self.connect_options = (host, port, keepalive)

    def loop_start(self):
        self.loop_started = True
        return mqtt.MQTT_ERR_SUCCESS

    def subscribe(self, topic: str, qos: int):
        self.subscriptions.append((topic, qos))
        return mqtt.MQTT_ERR_SUCCESS, len(self.subscriptions)

    def disconnect(self) -> None:
        self.disconnected = True

    def loop_stop(self) -> None:
        self.loop_started = False


@pytest.fixture
def fake_paho_client(monkeypatch: pytest.MonkeyPatch) -> FakePahoClient:
    fake = FakePahoClient()

    def factory(**options):
        fake.creation_options = options
        return fake

    monkeypatch.setattr(mqtt, "Client", factory)
    return fake


def test_mqtt_client_uses_scoped_tls_credentials_backoff_and_async_connect(
    fake_paho_client: FakePahoClient,
) -> None:
    connection_states: list[BambuConnectionState] = []
    settings = BambuMqttSettings(
        host="192.0.2.10",
        serial="01P00TESTSERIAL",
        access_code="test-secret",
    )
    client = BambuMqttClient(
        settings,
        on_connection=connection_states.append,
        on_payload=lambda _payload: None,
    )

    client.start()

    assert fake_paho_client.username == "bblp"
    assert fake_paho_client.password == "test-secret"
    assert fake_paho_client.reconnect_delays == (2, 60)
    assert fake_paho_client.connect_options == ("192.0.2.10", 8883, 60)
    assert fake_paho_client.tls_context is not None
    assert fake_paho_client.tls_context.verify_mode is ssl.CERT_NONE
    assert fake_paho_client.tls_context.check_hostname is False
    assert connection_states == [BambuConnectionState.CONNECTING]
    assert not hasattr(client, "publish")


def test_each_successful_connect_resubscribes_to_exact_report_topic(
    fake_paho_client: FakePahoClient,
) -> None:
    connection_states: list[BambuConnectionState] = []
    client = BambuMqttClient(
        BambuMqttSettings(
            host="192.0.2.10",
            serial="01P00TESTSERIAL",
            access_code="test-secret",
        ),
        on_connection=connection_states.append,
        on_payload=lambda _payload: None,
    )

    client._handle_connect(
        fake_paho_client,
        None,
        None,
        FakeReasonCode(),
        None,
    )
    client._handle_connect(
        fake_paho_client,
        None,
        None,
        FakeReasonCode(),
        None,
    )

    assert fake_paho_client.subscriptions == [
        ("device/01P00TESTSERIAL/report", 0),
        ("device/01P00TESTSERIAL/report", 0),
    ]
    assert connection_states == [
        BambuConnectionState.CONNECTED,
        BambuConnectionState.CONNECTED,
    ]
