"""Transactional PrintJob enrichment from read-only P1S FTPS metadata."""

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.integrations.bambu.file_resolver import (
    BambuFileResolutionStatus,
    resolve_print_file,
)
from app.integrations.bambu.ftps_client import (
    BambuFtpsClient,
    BambuFtpsError,
    BambuFtpsFileNotFoundError,
    BambuRemoteFile,
)
from app.integrations.bambu.three_mf import (
    PARSER_VERSION,
    Bambu3mfAmbiguousPlateError,
    Bambu3mfError,
    Bambu3mfParser,
    BambuParsed3mf,
)
from app.models import (
    PrintJob,
    PrintJobEnrichmentStatus,
    PrintJobFilamentReconciliation,
    PrintJobFilamentUsage,
    PrintJobStatus,
)
from app.models.timestamps import utc_now
from app.services.print_job_media_service import (
    PrintJobMediaError,
    PrintJobMediaService,
)


logger = logging.getLogger(__name__)
_ACTIVE_STATUSES = {PrintJobStatus.PRINTING, PrintJobStatus.PAUSED}


@dataclass(frozen=True)
class BambuFtpsHealthSnapshot:
    reachable: bool | None
    last_success_at: datetime | None
    last_error_code: str | None


class BambuFtpsHealthTracker:
    def __init__(self) -> None:
        self._lock = RLock()
        self._reachable: bool | None = None
        self._last_success_at: datetime | None = None
        self._last_error_code: str | None = None

    def success(self) -> None:
        with self._lock:
            self._reachable = True
            self._last_success_at = utc_now()
            self._last_error_code = None

    def failure(self, error_code: str) -> None:
        with self._lock:
            self._reachable = False
            self._last_error_code = error_code

    def snapshot(self) -> BambuFtpsHealthSnapshot:
        with self._lock:
            return BambuFtpsHealthSnapshot(
                reachable=self._reachable,
                last_success_at=self._last_success_at,
                last_error_code=self._last_error_code,
            )


@dataclass(frozen=True)
class EnrichmentOutcome:
    status: PrintJobEnrichmentStatus
    attempts: int
    retryable: bool = False


@dataclass(frozen=True)
class _JobSnapshot:
    id: int
    name: str | None
    gcode_file: str | None
    started_at: datetime | None
    status: PrintJobStatus
    attempts: int


class BambuPrintJobEnrichmentService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        ftps_client: BambuFtpsClient,
        *,
        parser: Bambu3mfParser | None = None,
        media_service: PrintJobMediaService | None = None,
        health: BambuFtpsHealthTracker | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._ftps_client = ftps_client
        self._parser = parser or Bambu3mfParser()
        self._media_service = media_service or PrintJobMediaService()
        self.health = health or BambuFtpsHealthTracker()

    def enrich(self, print_job_id: int, *, force: bool = False) -> EnrichmentOutcome:
        snapshot = self._begin(print_job_id, force=force)
        if snapshot is None:
            with self._session_factory() as db:
                job = db.get(PrintJob, print_job_id)
                status = job.enrichment_status if job and job.enrichment_status else PrintJobEnrichmentStatus.FAILED
                attempts = job.enrichment_attempts if job else 0
            return EnrichmentOutcome(status=status, attempts=attempts)

        try:
            files = self._ftps_client.list_print_files()
            self.health.success()
            resolution = resolve_print_file(
                files,
                gcode_file=snapshot.gcode_file,
                print_name=snapshot.name,
                started_at=snapshot.started_at,
            )
            if resolution.status is BambuFileResolutionStatus.AMBIGUOUS and len(resolution.candidates) <= 10:
                candidates = tuple(self._safe_stat(candidate) for candidate in resolution.candidates)
                resolution = resolve_print_file(
                    candidates,
                    gcode_file=snapshot.gcode_file,
                    print_name=snapshot.name,
                    started_at=snapshot.started_at,
                )
            if resolution.status is BambuFileResolutionStatus.NOT_FOUND:
                retryable = snapshot.status in _ACTIVE_STATUSES
                self._record_failure(
                    snapshot.id,
                    PrintJobEnrichmentStatus.FILE_NOT_FOUND,
                    "SOURCE_FILE_NOT_FOUND",
                )
                return EnrichmentOutcome(PrintJobEnrichmentStatus.FILE_NOT_FOUND, snapshot.attempts, retryable)
            if resolution.status is BambuFileResolutionStatus.AMBIGUOUS or resolution.selected is None:
                self._record_failure(
                    snapshot.id,
                    PrintJobEnrichmentStatus.AMBIGUOUS,
                    "SOURCE_FILE_AMBIGUOUS",
                )
                return EnrichmentOutcome(PrintJobEnrichmentStatus.AMBIGUOUS, snapshot.attempts)

            remote_file = self._ftps_client.stat_file(resolution.selected)
            with TemporaryDirectory(prefix="bambu-ftps-") as temporary_directory:
                archive_path = Path(temporary_directory) / "source.3mf"
                self._ftps_client.download(remote_file, archive_path)
                self.health.success()
                parsed = self._parser.parse(archive_path, plate_hint=resolution.plate_hint)
            self._persist(snapshot.id, remote_file, resolution.status, parsed)
            return EnrichmentOutcome(PrintJobEnrichmentStatus.ENRICHED, snapshot.attempts)
        except BambuFtpsFileNotFoundError as error:
            self.health.failure(error.error_code)
            retryable = snapshot.status in _ACTIVE_STATUSES
            self._record_failure(snapshot.id, PrintJobEnrichmentStatus.FILE_NOT_FOUND, error.error_code)
            return EnrichmentOutcome(PrintJobEnrichmentStatus.FILE_NOT_FOUND, snapshot.attempts, retryable)
        except BambuFtpsError as error:
            self.health.failure(error.error_code)
            self._record_failure(snapshot.id, PrintJobEnrichmentStatus.RETRYABLE, error.error_code)
            return EnrichmentOutcome(PrintJobEnrichmentStatus.RETRYABLE, snapshot.attempts, True)
        except Bambu3mfAmbiguousPlateError as error:
            self._record_failure(snapshot.id, PrintJobEnrichmentStatus.AMBIGUOUS, error.error_code)
            return EnrichmentOutcome(PrintJobEnrichmentStatus.AMBIGUOUS, snapshot.attempts)
        except Bambu3mfError as error:
            self._record_failure(snapshot.id, PrintJobEnrichmentStatus.FAILED, error.error_code)
            return EnrichmentOutcome(PrintJobEnrichmentStatus.FAILED, snapshot.attempts)
        except (PrintJobMediaError, SQLAlchemyError):
            self._record_failure(snapshot.id, PrintJobEnrichmentStatus.FAILED, "PERSISTENCE_FAILED")
            return EnrichmentOutcome(PrintJobEnrichmentStatus.FAILED, snapshot.attempts)

    def _begin(self, print_job_id: int, *, force: bool) -> _JobSnapshot | None:
        with self._session_factory() as db:
            job = db.get(PrintJob, print_job_id)
            if job is None or job.capture_mode is None:
                return None
            has_reconciliation_history = db.scalar(
                select(PrintJobFilamentReconciliation.id)
                .join(
                    PrintJobFilamentUsage,
                    PrintJobFilamentUsage.id
                    == PrintJobFilamentReconciliation.filament_usage_id,
                )
                .where(PrintJobFilamentUsage.print_job_id == print_job_id)
                .limit(1)
            )
            if has_reconciliation_history is not None:
                # Wave 4 audit rows intentionally RESTRICT deletion of the
                # normalized usage they explain. A forced re-enrichment must
                # not replace those source rows after inventory was changed.
                return None
            if job.enrichment_status is PrintJobEnrichmentStatus.ENRICHED and not force:
                return None
            job.enrichment_status = PrintJobEnrichmentStatus.IN_PROGRESS
            job.enrichment_attempts += 1
            job.last_enrichment_attempt_at = utc_now()
            job.enrichment_error_code = None
            db.commit()
            return _JobSnapshot(
                id=job.id,
                name=job.name,
                gcode_file=job.gcode_file,
                started_at=job.started_at,
                status=job.status,
                attempts=job.enrichment_attempts,
            )

    def _safe_stat(self, candidate: BambuRemoteFile) -> BambuRemoteFile:
        try:
            return self._ftps_client.stat_file(candidate)
        except BambuFtpsError:
            return candidate

    def _persist(
        self,
        print_job_id: int,
        remote_file: BambuRemoteFile,
        match_status: BambuFileResolutionStatus,
        parsed: BambuParsed3mf,
    ) -> None:
        stored_thumbnail = (
            self._media_service.store_thumbnail(print_job_id, parsed.thumbnail_bytes)
            if parsed.thumbnail_bytes is not None
            else None
        )
        new_thumbnail_name = stored_thumbnail.file_name if stored_thumbnail else None
        old_thumbnail_name: str | None = None
        try:
            with self._session_factory() as db:
                job = db.scalar(
                    select(PrintJob)
                    .where(PrintJob.id == print_job_id)
                    .options(selectinload(PrintJob.filament_usages))
                )
                if job is None:
                    raise SQLAlchemyError("PrintJob disappeared during enrichment")
                old_thumbnail_name = job.thumbnail_file_name
                job.filament_usages.clear()
                db.flush()
                job.filament_usages.extend(
                    PrintJobFilamentUsage(
                        position=position,
                        plate_index=parsed.plate_index,
                        source_filament_id=usage.source_filament_id,
                        material_type=usage.material_type,
                        color=usage.color,
                        used_g=usage.used_g,
                        used_m=usage.used_m,
                        tray_info_idx=usage.tray_info_idx,
                        used_for_object=usage.used_for_object,
                        used_for_support=usage.used_for_support,
                        nozzle_diameter=usage.nozzle_diameter,
                        group_id=usage.group_id,
                    )
                    for position, usage in enumerate(parsed.filaments)
                )
                job.enrichment_status = PrintJobEnrichmentStatus.ENRICHED
                job.enrichment_error_code = None
                job.metadata_source = "P1S_FTPS_3MF"
                job.source_file_name = remote_file.name
                job.source_file_match = match_status.value
                job.source_file_modified_at = remote_file.modified_at
                job.metadata_parser_version = PARSER_VERSION
                job.enriched_at = utc_now()
                job.thumbnail_file_name = new_thumbnail_name
                job.selected_plate_index = parsed.plate_index
                job.selected_plate_name = parsed.plate_name
                job.plate_selection_confidence = parsed.plate_selection_confidence
                job.slicer_estimated_duration_seconds = parsed.slicer_estimated_duration_seconds
                db.commit()
        except Exception:
            if new_thumbnail_name and new_thumbnail_name != old_thumbnail_name:
                self._media_service.remove_thumbnail(print_job_id, new_thumbnail_name)
            raise
        if old_thumbnail_name and old_thumbnail_name != new_thumbnail_name:
            self._media_service.remove_thumbnail(print_job_id, old_thumbnail_name)

    def _record_failure(
        self,
        print_job_id: int,
        status: PrintJobEnrichmentStatus,
        error_code: str,
    ) -> None:
        try:
            with self._session_factory() as db:
                job = db.get(PrintJob, print_job_id)
                if job is None:
                    return
                job.enrichment_status = status
                job.enrichment_error_code = error_code
                db.commit()
        except SQLAlchemyError:
            logger.error(
                "Bambu enrichment status persistence failed print_job_id=%s error_code=%s",
                print_job_id,
                error_code,
            )
