from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import shutil
import zipfile

from sqlalchemy import func, select

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.integrations.bambu.config import BambuFtpsSettings, BambuMqttSettings
from app.integrations.bambu.enrichment import BambuPrintJobEnrichmentService
from app.integrations.bambu.ftps_client import BambuFtpsError, BambuRemoteFile
from app.integrations.bambu.service import BambuIntegration
from app.models import (
    Manufacturer,
    Material,
    PrintJob,
    PrintJobCaptureMode,
    PrintJobEnrichmentStatus,
    PrintJobFilamentUsage,
    PrintJobStatus,
    Spool,
    SpoolStatus,
    WeightHistory,
)
from app.services.print_job_media_service import PrintJobMediaService
from app.schemas.reconciliation import ReconciliationConfirmRequest
from app.services.reconciliation_service import ReconciliationService


FIXTURES = Path(__file__).parent / "fixtures" / "bambu_3mf"
PNG = b"\x89PNG\r\n\x1a\n" + b"thumbnail"


def archive_fixture(path: Path) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Metadata/slice_info.config", (FIXTURES / "slice_info.config").read_bytes())
        archive.writestr("Metadata/model_settings.config", (FIXTURES / "model_settings.config").read_bytes())
        archive.writestr("Metadata/plate_7.png", PNG)
    return path


class FakeFtpsClient:
    def __init__(self, archive: Path) -> None:
        self.archive = archive
        self.remote = BambuRemoteFile("/cache/Sanitized Print.3mf", "Sanitized Print.3mf")

    def list_print_files(self):
        return (self.remote,)

    def stat_file(self, remote):
        return BambuRemoteFile(remote.path, remote.name, self.archive.stat().st_size, datetime(2026, 10, 5, 20, tzinfo=UTC))

    def download(self, remote, destination):
        shutil.copyfile(self.archive, destination)
        return destination.stat().st_size


class BrokenFtpsClient(FakeFtpsClient):
    def list_print_files(self):
        raise BambuFtpsError("CONNECTION_FAILED")


def database(tmp_path: Path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'enrichment.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db:
        manufacturer = Manufacturer(name="Inventory Brand")
        material = Material(name="PLA", category="PLA")
        db.add_all([manufacturer, material])
        db.flush()
        spool = Spool(
            code="FIL-3001",
            manufacturer_id=manufacturer.id,
            material_id=material.id,
            color_name="Black",
            initial_filament_weight_g=Decimal("1000"),
            current_filament_weight_g=Decimal("654.321"),
            status=SpoolStatus.OPEN,
        )
        job = PrintJob(
            name="Sanitized Print",
            status=PrintJobStatus.COMPLETED,
            printer_serial="SERIAL",
            capture_mode=PrintJobCaptureMode.LIVE,
            enrichment_status=PrintJobEnrichmentStatus.PENDING,
            gcode_file="Sanitized Print.gcode",
        )
        db.add_all([spool, job])
        db.commit()
        return engine, factory, job.id, spool.id


def test_enrichment_persists_normalized_usage_thumbnail_and_aggregates_idempotently(tmp_path: Path) -> None:
    engine, factory, job_id, spool_id = database(tmp_path)
    archive = archive_fixture(tmp_path / "source.3mf")
    media = PrintJobMediaService(tmp_path / "media")
    service = BambuPrintJobEnrichmentService(factory, FakeFtpsClient(archive), media_service=media)

    first = service.enrich(job_id)
    second = service.enrich(job_id, force=True)

    assert first.status is PrintJobEnrichmentStatus.ENRICHED
    assert second.status is PrintJobEnrichmentStatus.ENRICHED
    with factory() as db:
        job = db.scalar(select(PrintJob).where(PrintJob.id == job_id).options())
        assert job is not None
        usages = list(db.scalars(select(PrintJobFilamentUsage).where(PrintJobFilamentUsage.print_job_id == job_id)))
        assert len(usages) == 1
        assert usages[0].material_type == "PETG"
        assert usages[0].used_g == Decimal("230.510")
        assert usages[0].used_m == Decimal("75.460")
        assert usages[0].tray_info_idx == "GFG99"
        assert job.enrichment_attempts == 2
        assert job.source_file_match == "EXACT"
        assert job.selected_plate_index == 7
        assert job.slicer_estimated_duration_seconds == 22557
        assert job.thumbnail_file_name and media.resolve_thumbnail(job_id, job.thumbnail_file_name).read_bytes() == PNG
        assert db.get(Spool, spool_id).current_filament_weight_g == Decimal("654.321")
        assert db.scalar(select(func.count()).select_from(WeightHistory)) == 0
    engine.dispose()


def test_ftps_failure_is_retryable_and_does_not_modify_inventory_or_create_usage(tmp_path: Path) -> None:
    engine, factory, job_id, spool_id = database(tmp_path)
    archive = archive_fixture(tmp_path / "source.3mf")
    service = BambuPrintJobEnrichmentService(factory, BrokenFtpsClient(archive), media_service=PrintJobMediaService(tmp_path / "media"))

    outcome = service.enrich(job_id)

    assert outcome.status is PrintJobEnrichmentStatus.RETRYABLE
    assert outcome.retryable is True
    with factory() as db:
        job = db.get(PrintJob, job_id)
        assert job.enrichment_error_code == "CONNECTION_FAILED"
        assert db.scalar(select(func.count()).select_from(PrintJobFilamentUsage)) == 0
        assert db.get(Spool, spool_id).current_filament_weight_g == Decimal("654.321")
        assert db.scalar(select(func.count()).select_from(WeightHistory)) == 0
    engine.dispose()


def test_enriched_metadata_survives_new_service_and_session(tmp_path: Path) -> None:
    engine, factory, job_id, _ = database(tmp_path)
    archive = archive_fixture(tmp_path / "source.3mf")
    media = PrintJobMediaService(tmp_path / "media")
    BambuPrintJobEnrichmentService(factory, FakeFtpsClient(archive), media_service=media).enrich(job_id)

    restarted_factory = create_session_factory(engine)
    with restarted_factory() as db:
        job = db.scalar(select(PrintJob).where(PrintJob.id == job_id).options())
        assert job and job.enrichment_status is PrintJobEnrichmentStatus.ENRICHED
        assert db.scalar(select(func.count()).select_from(PrintJobFilamentUsage)) == 1
        assert job.thumbnail_file_name and media.resolve_thumbnail(job_id, job.thumbnail_file_name).is_file()
    engine.dispose()


def test_force_enrichment_does_not_replace_usage_after_inventory_reconciliation(tmp_path: Path) -> None:
    engine, factory, job_id, spool_id = database(tmp_path)
    archive = archive_fixture(tmp_path / "source.3mf")
    media = PrintJobMediaService(tmp_path / "media")
    service = BambuPrintJobEnrichmentService(factory, FakeFtpsClient(archive), media_service=media)
    service.enrich(job_id)
    with factory() as db:
        usage_id = db.scalar(
            select(PrintJobFilamentUsage.id).where(
                PrintJobFilamentUsage.print_job_id == job_id
            )
        )
        ReconciliationService(db).confirm(
            ReconciliationConfirmRequest.model_validate(
                {
                    "items": [
                        {
                            "filament_usage_id": usage_id,
                            "action": "DEDUCT",
                            "spool_id": spool_id,
                            "consumption_g": "230.510",
                        }
                    ]
                }
            )
        )

    outcome = service.enrich(job_id, force=True)

    assert outcome.status is PrintJobEnrichmentStatus.ENRICHED
    with factory() as db:
        job = db.get(PrintJob, job_id)
        usages = list(
            db.scalars(
                select(PrintJobFilamentUsage).where(
                    PrintJobFilamentUsage.print_job_id == job_id
                )
            )
        )
        assert job.enrichment_attempts == 1
        assert len(usages) == 1
        assert usages[0].id == usage_id
        assert db.get(Spool, spool_id).current_filament_weight_g == Decimal("423.811")
    engine.dispose()


def test_enrichment_scheduling_failure_does_not_rollback_mqtt_print_capture(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'mqtt.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    class FailingWorker:
        def start(self): pass
        def stop(self): pass
        def schedule(self, print_job_id, force=False): raise RuntimeError("worker unavailable")

    integration = BambuIntegration(
        BambuMqttSettings(host="printer", serial="SERIAL", access_code="secret"),
        session_factory=factory,
        ftps_settings=BambuFtpsSettings(host="printer", access_code="secret"),
        enrichment_worker=FailingWorker(),
    )
    integration._handle_payload(
        b'{"print":{"gcode_state":"RUNNING","subtask_name":"Safe Capture","gcode_file":"Safe Capture.gcode","mc_percent":1}}'
    )

    with factory() as db:
        job = db.scalar(select(PrintJob))
        assert job and job.name == "Safe Capture"
        assert job.status is PrintJobStatus.PRINTING
        assert job.enrichment_status is PrintJobEnrichmentStatus.PENDING
    engine.dispose()
