from dataclasses import dataclass
from datetime import datetime
import json
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import SessionLocal

from app.integrations.bambu.config import (
    BambuFtpsSettings,
    BambuMqttSettings,
    load_bambu_ftps_settings,
    load_bambu_mqtt_settings,
)
from app.integrations.bambu.enrichment import BambuPrintJobEnrichmentService
from app.integrations.bambu.enrichment_worker import BambuEnrichmentWorker
from app.integrations.bambu.ftps_client import BambuFtpsClient
from app.integrations.bambu.lifecycle import BambuPrintLifecycleDetector
from app.integrations.bambu.models import (
    BambuConnectionState,
    BambuPrinterState,
    BambuStatePatch,
)
from app.integrations.bambu.mqtt_client import BambuMqttClient
from app.integrations.bambu.parser import BambuReportParseError, BambuReportParser
from app.integrations.bambu.print_job_collector import BambuPrintJobCollector
from app.integrations.bambu.state_store import BambuStateStore


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BambuDiagnostic:
    configured: bool
    connected: bool
    missing_configuration: tuple[str, ...]
    configuration_error: str | None
    state: BambuPrinterState
    active_print_job_id: int | None
    ftps_configured: bool
    ftps_reachable: bool | None
    last_ftps_success_at: datetime | None
    last_ftps_error_code: str | None


class BambuIntegration:
    """Coordinate Bambu MQTT input, normalized state, and lifecycle events."""

    def __init__(
        self,
        settings: BambuMqttSettings | None = None,
        *,
        session_factory: sessionmaker[Session] = SessionLocal,
        ftps_settings: BambuFtpsSettings | None = None,
        enrichment_worker: BambuEnrichmentWorker | None = None,
    ) -> None:
        self.settings = settings or load_bambu_mqtt_settings()
        self.state_store = BambuStateStore(
            self.settings.serial,
            configured=self.settings.configured,
        )
        self._parser = BambuReportParser()
        self._lifecycle_detector = BambuPrintLifecycleDetector()
        self._print_job_collector = BambuPrintJobCollector(session_factory)
        self.ftps_settings = ftps_settings or load_bambu_ftps_settings()
        self._enrichment_service = BambuPrintJobEnrichmentService(
            session_factory,
            BambuFtpsClient(self.ftps_settings),
        )
        self._enrichment_worker = enrichment_worker or BambuEnrichmentWorker(
            self._enrichment_service,
        )
        self._mqtt_client: BambuMqttClient | None = None
        self._debug_payload_fingerprints: set[str] = set()
        self._last_enrichment_signature: tuple[int, str | None, str | None] | None = None

    def start(self) -> None:
        if self.ftps_settings.configured:
            self._enrichment_worker.start()
        if not self.settings.configured:
            if self.settings.configuration_error:
                logger.error(
                    "Bambu integration disabled: %s",
                    self.settings.configuration_error,
                )
            else:
                logger.info(
                    "Bambu integration not configured missing=%s",
                    ",".join(self.settings.missing_variables),
                )
            return

        try:
            self._mqtt_client = BambuMqttClient(
                self.settings,
                on_connection=self._handle_connection,
                on_payload=self._handle_payload,
            )
            self._mqtt_client.start()
        except Exception as error:
            self._mqtt_client = None
            self.state_store.set_connection(BambuConnectionState.DISCONNECTED)
            logger.error(
                "Bambu MQTT collector could not start serial=%s error_type=%s",
                self.settings.serial,
                type(error).__name__,
            )

    def stop(self) -> None:
        if self._mqtt_client is not None:
            self._mqtt_client.stop()
            self._mqtt_client = None
        self._enrichment_worker.stop()

    def diagnostic(self) -> BambuDiagnostic:
        state = self.state_store.snapshot()
        ftps_health = self._enrichment_service.health.snapshot()
        return BambuDiagnostic(
            configured=self.settings.configured,
            connected=state.connection_state is BambuConnectionState.CONNECTED,
            missing_configuration=self.settings.missing_variables,
            configuration_error=self.settings.configuration_error,
            state=state,
            active_print_job_id=self._print_job_collector.active_print_job_id,
            ftps_configured=self.ftps_settings.configured,
            ftps_reachable=ftps_health.reachable,
            last_ftps_success_at=ftps_health.last_success_at,
            last_ftps_error_code=ftps_health.last_error_code,
        )

    def request_enrichment(self, print_job_id: int, *, force: bool = False) -> bool:
        if not self.ftps_settings.configured:
            return False
        return self._enrichment_worker.schedule(print_job_id, force=force)

    def _handle_connection(self, connection_state: BambuConnectionState) -> None:
        self.state_store.set_connection(connection_state)

    def _handle_payload(self, payload: bytes) -> None:
        try:
            patch = self._parser.parse(payload)
        except BambuReportParseError as error:
            logger.warning(
                "Bambu MQTT report parsing failed serial=%s error=%s",
                self.settings.serial,
                error,
            )
            return

        state = self.state_store.merge(patch)
        events = self._lifecycle_detector.observe(state)
        self._log_sanitized_debug_patch(patch)
        for event in events:
            logger.info(
                "Bambu lifecycle event=%s serial=%s state=%s raw_state=%s progress=%s current_print=%s",
                event.event_type,
                self.settings.serial,
                event.print_state,
                event.raw_print_state,
                event.progress_percent,
                event.current_print,
            )
        try:
            self._print_job_collector.collect(state, events)
            print_job_id = self._print_job_collector.last_print_job_id
            if print_job_id is not None:
                signature = (print_job_id, state.gcode_file, state.current_print)
                if events or signature != self._last_enrichment_signature:
                    self._enrichment_worker.schedule(print_job_id)
                    self._last_enrichment_signature = signature
        except SQLAlchemyError as error:
            logger.error(
                "Bambu PrintJob persistence failed serial=%s error_type=%s",
                self.settings.serial,
                type(error).__name__,
            )
        except Exception as error:
            logger.error(
                "Bambu enrichment scheduling failed serial=%s error_type=%s",
                self.settings.serial,
                type(error).__name__,
            )

    def _log_sanitized_debug_patch(self, patch: BambuStatePatch) -> None:
        if not self.settings.debug_payloads or not logger.isEnabledFor(logging.DEBUG):
            return
        document = {
            "values": patch.values,
            "ams_units": [
                {
                    "unit_id": unit.unit_id,
                    "values": unit.values,
                    "trays": [
                        {"tray_id": tray.tray_id, "values": tray.values}
                        for tray in unit.trays
                    ],
                }
                for unit in patch.ams_units
            ],
            "external_tray": (
                {
                    "tray_id": patch.external_tray.tray_id,
                    "values": patch.external_tray.values,
                }
                if patch.external_tray is not None
                else None
            ),
        }
        serialized = json.dumps(document, default=str, sort_keys=True)
        if serialized in self._debug_payload_fingerprints:
            return
        if len(self._debug_payload_fingerprints) >= 200:
            return
        self._debug_payload_fingerprints.add(serialized)
        logger.debug(
            "Bambu sanitized normalized report serial=%s payload=%s",
            self.settings.serial,
            serialized,
        )
