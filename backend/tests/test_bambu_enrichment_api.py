from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.prints import get_print_job_media_service
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory, get_db
from app.integrations.bambu.config import BambuFtpsSettings
from app.main import app
from app.models import (
    PrintJob,
    PrintJobCaptureMode,
    PrintJobEnrichmentStatus,
    PrintJobFilamentUsage,
    PrintJobStatus,
)
from app.services.print_job_media_service import PrintJobMediaService


PNG = b"\x89PNG\r\n\x1a\n" + b"api-thumbnail"


@pytest.fixture
def environment(tmp_path: Path) -> Iterator[tuple[TestClient, object, int, PrintJobMediaService]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    media = PrintJobMediaService(tmp_path / "media")
    with factory() as db:
        job = PrintJob(
            name="Enriched Print",
            status=PrintJobStatus.COMPLETED,
            printer_serial="SERIAL",
            capture_mode=PrintJobCaptureMode.LIVE,
            enrichment_status=PrintJobEnrichmentStatus.ENRICHED,
            enrichment_attempts=1,
            metadata_source="P1S_FTPS_3MF",
            source_file_name="Enriched Print.3mf",
            source_file_match="EXACT",
            metadata_parser_version="1",
            enriched_at=datetime(2026, 10, 5, 21, tzinfo=UTC),
            selected_plate_index=1,
            selected_plate_name="Main plate",
            plate_selection_confidence="EXACT",
            slicer_estimated_duration_seconds=11820,
            filament_usages=[
                PrintJobFilamentUsage(
                    position=0,
                    plate_index=1,
                    source_filament_id="1",
                    material_type="PLA",
                    color="#000000",
                    used_g=Decimal("74.2"),
                    used_m=Decimal("24.7"),
                    tray_info_idx="GFA00",
                ),
                PrintJobFilamentUsage(
                    position=1,
                    plate_index=1,
                    source_filament_id="2",
                    material_type="PLA",
                    color="#FFFFFF",
                    used_g=Decimal("8.7"),
                    used_m=Decimal("2.9"),
                    tray_info_idx="GFA01",
                ),
            ],
        )
        db.add(job)
        db.commit()
        stored = media.store_thumbnail(job.id, PNG)
        job.thumbnail_file_name = stored.file_name
        db.commit()
        job_id = job.id

    def database_dependency():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database_dependency
    app.dependency_overrides[get_print_job_media_service] = lambda: media
    with TestClient(app) as client:
        yield client, factory, job_id, media
    app.dependency_overrides.clear()
    engine.dispose()


def test_history_and_detail_api_expose_estimated_metadata_without_paths_or_secrets(environment) -> None:
    client, _, job_id, _ = environment

    listed = client.get("/api/prints").json()[0]
    detail = client.get(f"/api/prints/{job_id}").json()

    for payload in (listed, detail):
        assert payload["enrichment_status"] == "ENRICHED"
        assert Decimal(str(payload["estimated_filament_g"])) == Decimal("82.9")
        assert Decimal(str(payload["estimated_filament_m"])) == Decimal("27.6")
        assert payload["slicer_estimated_duration_seconds"] == 11820
        assert payload["filament_count"] == 2
        assert payload["thumbnail_url"] == f"/api/prints/{job_id}/thumbnail"
        assert len(payload["filaments"]) == 2
        assert "thumbnail_file_name" not in payload
        assert "access_code" not in str(payload)


def test_thumbnail_route_serves_only_valid_internal_reference(environment) -> None:
    client, factory, job_id, _ = environment
    response = client.get(f"/api/prints/{job_id}/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == PNG

    with factory() as db:
        db.get(PrintJob, job_id).thumbnail_file_name = "../../etc/passwd"
        db.commit()
    assert client.get(f"/api/prints/{job_id}/thumbnail").status_code == 404


def test_historical_enrichment_can_be_queued_without_generic_ftps_access(environment) -> None:
    client, _, job_id, _ = environment

    class FakeIntegration:
        ftps_settings = BambuFtpsSettings(host="printer", access_code="secret")
        requested: list[tuple[int, bool]] = []
        def request_enrichment(self, print_job_id: int, force: bool = False):
            self.requested.append((print_job_id, force))
            return True

    fake = FakeIntegration()
    app.state.bambu_integration = fake
    response = client.post(f"/api/prints/{job_id}/enrichment")

    assert response.status_code == 202
    assert response.json() == {"print_job_id": job_id, "status": "ACCEPTED"}
    assert fake.requested == [(job_id, True)]
    paths = client.get("/openapi.json").json()["paths"]
    assert not any("ftps" in path.casefold() for path in paths)
