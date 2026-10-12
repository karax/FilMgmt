import logging

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.integrations.bambu.config import BambuMqttSettings
from app.integrations.bambu.service import BambuIntegration


def test_debug_capture_is_opt_in_sanitized_and_deduplicated(tmp_path, caplog) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'debug.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    integration = BambuIntegration(
        BambuMqttSettings(
            host="192.0.2.10",
            serial="01P00TESTSERIAL",
            access_code="never-log-this-access-code",
            debug_payloads=True,
        ),
        session_factory=factory,
    )
    payload = b'{"print":{"gcode_state":"IDLE","mc_percent":0,"unrelated_secret":"never-log-this-payload-value"}}'

    with caplog.at_level(logging.DEBUG, logger="app.integrations.bambu.service"):
        integration._handle_payload(payload)
        integration._handle_payload(payload)

    capture_messages = [
        record.getMessage()
        for record in caplog.records
        if "sanitized normalized report" in record.getMessage()
    ]
    assert len(capture_messages) == 1
    assert '"raw_print_state": "IDLE"' in capture_messages[0]
    assert "never-log-this-access-code" not in caplog.text
    assert "never-log-this-payload-value" not in caplog.text
    assert "unrelated_secret" not in caplog.text
    engine.dispose()


def test_debug_capture_is_off_by_default(tmp_path, caplog) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'debug-off.db'}")
    Base.metadata.create_all(engine)
    integration = BambuIntegration(
        BambuMqttSettings(
            host="192.0.2.10",
            serial="01P00TESTSERIAL",
            access_code="secret",
        ),
        session_factory=create_session_factory(engine),
    )

    with caplog.at_level(logging.DEBUG, logger="app.integrations.bambu.service"):
        integration._handle_payload(b'{"print":{"gcode_state":"IDLE"}}')

    assert "sanitized normalized report" not in caplog.text
    engine.dispose()
