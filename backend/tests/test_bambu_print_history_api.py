from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory, get_db
from app.main import app
from app.models import (
    PrintJob,
    PrintJobCaptureMode,
    PrintJobReconciliationStatus,
    PrintJobStatus,
)


def test_print_history_api_lists_newest_first_filters_and_returns_details(tmp_path) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    now = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
    with factory() as db:
        older = PrintJob(
            name=None,
            status=PrintJobStatus.FAILED,
            printer_serial="SERIAL-OTHER",
            task_id="task-old",
            started_at=now - timedelta(days=2),
            finished_at=now - timedelta(days=2, hours=-1),
            last_seen_at=now - timedelta(days=2, hours=-1),
            final_progress=20,
            capture_mode=PrintJobCaptureMode.LIVE,
            reconciliation_status=PrintJobReconciliationStatus.PENDING,
            ams_snapshot={"current_tray": "0", "ams_units": []},
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        )
        newer = PrintJob(
            name="desk_robot_head",
            status=PrintJobStatus.COMPLETED,
            printer_serial="01P00TESTSERIAL",
            task_id="task-56",
            subtask_id="subtask-78",
            project_id="project-12",
            profile_id="profile-34",
            gcode_file="/data/Metadata/desk_robot_head.gcode",
            started_at=now,
            finished_at=now + timedelta(hours=1),
            last_seen_at=now + timedelta(hours=1),
            raw_bambu_state="FINISH",
            start_progress=1,
            final_progress=100,
            start_layer=1,
            final_layer=928,
            total_layers=928,
            duration_seconds=3600,
            remaining_time_minutes=0,
            capture_mode=PrintJobCaptureMode.LIVE,
            reconciliation_status=PrintJobReconciliationStatus.PENDING,
            ams_snapshot={
                "current_tray": "1",
                "ams_units": [
                    {
                        "unit_id": "0",
                        "trays": [
                            {
                                "tray_id": "1",
                                "material_type": "PLA",
                                "color": "000000FF",
                            }
                        ],
                    }
                ],
            },
            created_at=now,
            updated_at=now + timedelta(hours=1),
        )
        db.add_all([older, newer])
        db.commit()
        newer_id = newer.id

    def database_dependency():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database_dependency
    client = TestClient(app)
    try:
        response = client.get("/api/prints")
        assert response.status_code == 200
        assert [job["name"] for job in response.json()] == ["desk_robot_head", None]

        filtered = client.get(
            "/api/prints",
            params={
                "printer_serial": "01P00TESTSERIAL",
                "status": "COMPLETED",
                "started_after": (now - timedelta(minutes=1)).isoformat(),
                "started_before": (now + timedelta(minutes=1)).isoformat(),
            },
        )
        assert filtered.status_code == 200
        assert [job["id"] for job in filtered.json()] == [newer_id]

        detail = client.get(f"/api/prints/{newer_id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["printer_serial"] == "01P00TESTSERIAL"
        assert body["task_id"] == "task-56"
        assert body["status"] == "COMPLETED"
        assert body["final_progress"] == 100
        assert body["capture_mode"] == "LIVE"
        assert body["reconciliation_status"] == "PENDING"
        assert body["ams_snapshot"]["ams_units"][0]["trays"][0]["color"] == "000000FF"
        assert body["spools"] == []
        assert "bambu_identity_key" not in body
        assert "access_code" not in detail.text
        assert "never-return-this-secret" not in detail.text

        manual_finish = client.post(f"/api/prints/{newer_id}/finish", json={})
        assert manual_finish.status_code == 409
        assert manual_finish.json()["detail"] == "Printer-managed jobs are updated automatically."
    finally:
        app.dependency_overrides.clear()
        client.close()
        engine.dispose()
