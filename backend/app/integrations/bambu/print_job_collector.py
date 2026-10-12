"""Persist normalized Bambu print lifecycle without touching inventory."""

from collections.abc import Sequence
from datetime import datetime
import logging
from threading import RLock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.integrations.bambu.models import (
    BambuAmsTray,
    BambuLifecycleEvent,
    BambuLifecycleEventType,
    BambuPrinterState,
    BambuPrintState,
)
from app.models import (
    PrintJob,
    PrintJobCaptureMode,
    PrintJobEnrichmentStatus,
    PrintJobReconciliationStatus,
    PrintJobStatus,
)
from app.models.timestamps import normalize_utc


logger = logging.getLogger(__name__)

_ACTIVE_JOB_STATUSES = {PrintJobStatus.PRINTING, PrintJobStatus.PAUSED}
_ACTIVE_PRINTER_STATES = {BambuPrintState.PRINTING, BambuPrintState.PAUSED}
class BambuPrintJobCollector:
    """Create and update Bambu-owned PrintJobs using a fresh session per callback.

    Stable task/subtask identifiers are retained as the run identity when either
    exists. If neither exists, the one-active-job-per-printer database invariant
    provides in-flight de-duplication without pretending that a filename is a
    unique print run.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._lock = RLock()
        self._active_print_job_id: int | None = None
        self._last_print_job_id: int | None = None

    @property
    def active_print_job_id(self) -> int | None:
        with self._lock:
            return self._active_print_job_id

    @property
    def last_print_job_id(self) -> int | None:
        with self._lock:
            return self._last_print_job_id

    def collect(
        self,
        state: BambuPrinterState,
        events: Sequence[BambuLifecycleEvent],
    ) -> int | None:
        if state.serial is None or state.last_update_at is None:
            return self.active_print_job_id

        with self._lock:
            try:
                with self._session_factory() as db:
                    active = self._active_job(db, state.serial)
                    if (
                        active is not None
                        and state.print_state in _ACTIVE_PRINTER_STATES
                        and _identity_conflicts(active, state)
                    ):
                        self._close_stale_active(active, state.last_update_at)
                        active = None

                    start_event = next(
                        (
                            event
                            for event in events
                            if event.event_type is BambuLifecycleEventType.PRINT_STARTED
                        ),
                        None,
                    )
                    if active is None and state.print_state in _ACTIVE_PRINTER_STATES:
                        capture_mode = (
                            PrintJobCaptureMode.LIVE
                            if start_event is not None and start_event.start_observed is True
                            else PrintJobCaptureMode.RECOVERED
                        )
                        active = self._create_job(
                            state,
                            capture_mode,
                            start_event.occurred_at if start_event is not None else state.last_update_at,
                        )
                        db.add(active)
                        db.flush()

                    if active is not None:
                        self._reconcile_active(active, state, events)

                    db.commit()
                    self._last_print_job_id = active.id if active is not None else None
                    self._active_print_job_id = (
                        active.id
                        if active is not None and active.status in _ACTIVE_JOB_STATUSES
                        else None
                    )
                    return self._active_print_job_id
            except IntegrityError:
                logger.warning(
                    "Bambu PrintJob write conflicted with another active collector serial=%s",
                    state.serial,
                )
                with self._session_factory() as db:
                    active = self._active_job(db, state.serial)
                    self._active_print_job_id = active.id if active is not None else None
                return self._active_print_job_id

    def _active_job(self, db: Session, serial: str) -> PrintJob | None:
        return db.scalar(
            select(PrintJob)
            .where(
                PrintJob.printer_serial == serial,
                PrintJob.capture_mode.is_not(None),
                PrintJob.status.in_(_ACTIVE_JOB_STATUSES),
            )
            .order_by(PrintJob.created_at.desc(), PrintJob.id.desc())
            .limit(1)
        )

    def _create_job(
        self,
        state: BambuPrinterState,
        capture_mode: PrintJobCaptureMode,
        observed_at: datetime,
    ) -> PrintJob:
        observed_at = normalize_utc(observed_at)
        started_at = observed_at if capture_mode is PrintJobCaptureMode.LIVE else None
        return PrintJob(
            name=state.current_print,
            status=(
                PrintJobStatus.PAUSED
                if state.print_state is BambuPrintState.PAUSED
                else PrintJobStatus.PRINTING
            ),
            printer_serial=state.serial,
            bambu_identity_key=bambu_print_identity(state),
            task_id=state.task_id,
            subtask_id=state.subtask_id,
            project_id=state.project_id,
            profile_id=state.profile_id,
            gcode_file=state.gcode_file,
            started_at=started_at,
            last_seen_at=observed_at,
            raw_bambu_state=state.raw_print_state,
            start_progress=state.progress_percent,
            final_progress=state.progress_percent,
            start_layer=state.current_layer,
            final_layer=state.current_layer,
            total_layers=state.total_layers,
            remaining_time_minutes=state.remaining_time_minutes,
            capture_mode=capture_mode,
            ams_snapshot=ams_snapshot(state, observed_at),
            enrichment_status=PrintJobEnrichmentStatus.PENDING,
        )

    def _reconcile_active(
        self,
        job: PrintJob,
        state: BambuPrinterState,
        events: Sequence[BambuLifecycleEvent],
    ) -> None:
        observed_at = normalize_utc(state.last_update_at)  # type: ignore[arg-type]
        has_lifecycle_event = bool(events)
        metadata_changed = self._update_metadata(job, state)

        if state.print_state is BambuPrintState.PRINTING:
            job.status = PrintJobStatus.PRINTING
        elif state.print_state is BambuPrintState.PAUSED:
            job.status = PrintJobStatus.PAUSED
        elif state.print_state is BambuPrintState.FINISHED:
            self._finish(job, state, PrintJobStatus.COMPLETED, observed_at)
            return
        elif state.print_state is BambuPrintState.FAILED:
            self._finish(job, state, PrintJobStatus.FAILED, observed_at)
            return
        elif state.print_state is BambuPrintState.CANCELLED:
            self._finish(job, state, PrintJobStatus.CANCELLED, observed_at)
            return
        elif state.print_state is BambuPrintState.IDLE:
            self._finish(job, state, PrintJobStatus.UNKNOWN_TERMINAL, observed_at)
            return

        progress_event = any(
            event.event_type is BambuLifecycleEventType.PRINT_PROGRESS
            for event in events
        )
        recovered_progress = (
            state.print_state is BambuPrintState.UNKNOWN
            and state.progress_percent is not None
            and state.progress_percent != job.final_progress
        )
        if progress_event or recovered_progress or has_lifecycle_event:
            self._update_progress(job, state)
            job.raw_bambu_state = state.raw_print_state
            job.last_seen_at = observed_at
        elif metadata_changed:
            job.last_seen_at = observed_at

    def _update_metadata(self, job: PrintJob, state: BambuPrinterState) -> bool:
        changed = False
        values = {
            "name": state.current_print,
            "task_id": state.task_id,
            "subtask_id": state.subtask_id,
            "project_id": state.project_id,
            "profile_id": state.profile_id,
            "gcode_file": state.gcode_file,
            "bambu_identity_key": bambu_print_identity(state),
        }
        for field_name, value in values.items():
            # Terminal/partial P1S reports can send empty strings after having
            # supplied useful metadata earlier in the run.  Treat those as
            # absent values so the final report cannot erase the filename or
            # name needed by FTPS enrichment.
            if (
                value is not None
                and (not isinstance(value, str) or bool(value.strip()))
                and getattr(job, field_name) != value
            ):
                setattr(job, field_name, value)
                changed = True
        return changed

    def _update_progress(self, job: PrintJob, state: BambuPrinterState) -> None:
        if state.progress_percent is not None:
            job.final_progress = state.progress_percent
        if state.current_layer is not None:
            job.final_layer = state.current_layer
        if state.total_layers is not None:
            job.total_layers = state.total_layers
        if state.remaining_time_minutes is not None:
            job.remaining_time_minutes = state.remaining_time_minutes

    def _finish(
        self,
        job: PrintJob,
        state: BambuPrinterState,
        status: PrintJobStatus,
        observed_at: datetime,
    ) -> None:
        observed_at = normalize_utc(observed_at)
        self._update_metadata(job, state)
        self._update_progress(job, state)
        job.status = status
        job.finished_at = observed_at
        job.last_seen_at = observed_at
        job.raw_bambu_state = state.raw_print_state
        job.reconciliation_status = (
            PrintJobReconciliationStatus.NEEDS_REVIEW
            if status
            in {
                PrintJobStatus.FAILED,
                PrintJobStatus.CANCELLED,
                PrintJobStatus.UNKNOWN_TERMINAL,
            }
            else PrintJobReconciliationStatus.PENDING
        )
        if job.started_at is not None:
            job.duration_seconds = max(
                0,
                int((observed_at - normalize_utc(job.started_at)).total_seconds()),
            )

    def _close_stale_active(self, job: PrintJob, observed_at: datetime) -> None:
        """Close an unmatched pre-restart job without copying the new run into it."""

        job.status = PrintJobStatus.UNKNOWN_TERMINAL
        job.finished_at = normalize_utc(observed_at)
        job.reconciliation_status = PrintJobReconciliationStatus.NEEDS_REVIEW


def bambu_print_identity(state: BambuPrinterState) -> str | None:
    """Return a stable run identity only when Bambu task identifiers exist."""

    if state.task_id is None and state.subtask_id is None:
        return None
    return f"task={state.task_id or ''}|subtask={state.subtask_id or ''}"


def _identity_conflicts(job: PrintJob, state: BambuPrinterState) -> bool:
    """Compare only identifier components known on both partial snapshots."""

    return (
        job.task_id is not None
        and state.task_id is not None
        and job.task_id != state.task_id
    ) or (
        job.subtask_id is not None
        and state.subtask_id is not None
        and job.subtask_id != state.subtask_id
    )


def ams_snapshot(state: BambuPrinterState, captured_at: datetime) -> dict[str, object]:
    """Detach the normalized AMS state into a JSON-safe historical value."""

    return {
        "captured_at": normalize_utc(captured_at).isoformat(),
        "current_tray": state.current_tray,
        "ams_units": [
            {
                "unit_id": unit.unit_id,
                "humidity": unit.humidity,
                "temperature_c": unit.temperature_c,
                "trays": [_tray_snapshot(tray) for tray in unit.trays],
            }
            for unit in state.ams_units
        ],
        "external_tray": (
            _tray_snapshot(state.external_tray)
            if state.external_tray is not None
            else None
        ),
    }


def _tray_snapshot(tray: BambuAmsTray) -> dict[str, object]:
    return {
        "tray_id": tray.tray_id,
        "material_type": tray.material_type,
        "color": tray.color,
        "profile_id": tray.profile_id,
        "setting_id": tray.setting_id,
        "brand": tray.brand,
        "tag_uid": tray.tag_uid,
        "tray_uuid": tray.tray_uuid,
        "remaining_percent": tray.remaining_percent,
        "nozzle_temp_min": tray.nozzle_temp_min,
        "nozzle_temp_max": tray.nozzle_temp_max,
    }
