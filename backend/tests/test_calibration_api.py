from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory, get_db
from app.main import app
from app.models import (
    CalibrationEventType,
    Manufacturer,
    Material,
    PrintJob,
    PrintJobCaptureMode,
    PrintJobEnrichmentStatus,
    PrintJobFilamentReconciliation,
    PrintJobFilamentUsage,
    PrintJobReconciliationStatus,
    PrintJobStatus,
    Spool,
    SpoolCalibration,
    SpoolStatus,
    TareMeasurement,
    WeightHistory,
    WeightSource,
)


@pytest.fixture
def calibration_env(tmp_path: Path) -> Iterator[tuple[TestClient, sessionmaker[Session], str]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'calibration.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db:
        manufacturer = Manufacturer(name="eSUN")
        material = Material(name="PETG", category="PETG")
        db.add_all([manufacturer, material])
        db.flush()
        db.add(Spool(code="FIL-0020", manufacturer_id=manufacturer.id, material_id=material.id, color_name="White", initial_filament_weight_g=Decimal("1000.000"), current_filament_weight_g=Decimal("684.200"), status=SpoolStatus.OPEN))
        db.commit()

    def override() -> Iterator[Session]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    try:
        yield client, factory, "FIL-0020"
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()


def _preview(client: TestClient, code: str, **changes):
    payload = {"measured_total_g": "631.000", "tare_g": "224.000", "tare_source": "MEASURED", **changes}
    return client.post(f"/api/spools/{code}/calibrations/preview", json=payload)


def _confirm(client: TestClient, code: str, key: str, **changes):
    payload = {"measured_total_g": "631.000", "tare_g": "224.000", "tare_source": "MEASURED", "expected_current_remaining_g": "684.200", "idempotency_key": key, **changes}
    return client.post(f"/api/spools/{code}/calibrations", json=payload)


def test_routes_formula_precision_and_preview_is_read_only(calibration_env) -> None:
    client, factory, code = calibration_env
    assert {"/api/spools/{code}/calibrations/preview", "/api/spools/{code}/calibrations", "/api/spools/{code}/calibrations/{calibration_id}/undo", "/api/tare-profiles"} <= {route.path for route in app.routes}
    response = _preview(client, code, measured_total_g="637.123", tare_g="224.001")
    assert response.status_code == 200
    assert Decimal(response.json()["calculated_filament_g"]) == Decimal("413.122")
    assert Decimal(response.json()["adjustment_g"]) == Decimal("-271.078")
    assert response.json()["tare_confidence"] == "HIGH"
    with factory() as db:
        assert db.scalar(select(Spool).where(Spool.code == code)).current_filament_weight_g == Decimal("684.200")
        assert not list(db.scalars(select(WeightHistory)).all())
        assert not list(db.scalars(select(SpoolCalibration)).all())


@pytest.mark.parametrize("payload", [
    {"measured_total_g": "-1", "tare_g": "0", "tare_source": "MANUAL"},
    {"measured_total_g": "10", "tare_g": "-1", "tare_source": "MANUAL"},
    {"measured_total_g": "100", "tare_g": "101", "tare_source": "MANUAL"},
    {"measured_total_g": "100"},
])
def test_invalid_calibration_inputs_are_explicit(calibration_env, payload) -> None:
    client, _, code = calibration_env
    assert client.post(f"/api/spools/{code}/calibrations/preview", json=payload).status_code == 422


def test_confirm_creates_scale_history_and_signed_negative_ledger(calibration_env) -> None:
    client, factory, code = calibration_env
    response = _confirm(client, code, "calibration-negative-0001", note="Initial physical calibration")
    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["previous_remaining_g"]) == Decimal("684.200")
    assert Decimal(body["new_remaining_g"]) == Decimal("407.000")
    assert Decimal(body["adjustment_g"]) == Decimal("-277.200")
    with factory() as db:
        assert db.scalar(select(Spool).where(Spool.code == code)).current_filament_weight_g == Decimal("407.000")
        history = db.scalar(select(WeightHistory))
        assert history.weight_g == Decimal("407.000") and history.source is WeightSource.SCALE


@pytest.mark.parametrize(("current", "measured", "adjustment"), [("352.000", "585.000", "9.000"), ("407.000", "631.000", "0.000")])
def test_positive_and_zero_adjustments(calibration_env, current, measured, adjustment) -> None:
    client, factory, code = calibration_env
    with factory() as db:
        db.scalar(select(Spool).where(Spool.code == code)).current_filament_weight_g = Decimal(current)
        db.commit()
    response = _confirm(client, code, f"calibration-{current}", measured_total_g=measured, expected_current_remaining_g=current)
    assert response.status_code == 201
    assert Decimal(response.json()["adjustment_g"]) == Decimal(adjustment)


def test_confirmation_is_idempotent_and_stale_preview_requires_review(calibration_env) -> None:
    client, factory, code = calibration_env
    first = _confirm(client, code, "retry-safe-calibration")
    second = _confirm(client, code, "retry-safe-calibration")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    with factory() as db:
        assert len(list(db.scalars(select(SpoolCalibration)).all())) == 1
        assert len(list(db.scalars(select(WeightHistory)).all())) == 1
    stale = _confirm(client, code, "new-calibration-after-change", measured_total_g="600.000", expected_current_remaining_g="684.200")
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_calibration_preview"
    assert Decimal(stale.json()["detail"]["preview"]["current_remaining_g"]) == Decimal("407.000")


def test_undo_restores_exact_balance_and_keeps_audit(calibration_env) -> None:
    client, factory, code = calibration_env
    calibration = _confirm(client, code, "undo-calibration-0001").json()
    url = f"/api/spools/{code}/calibrations/{calibration['id']}/undo"
    response = client.post(url, json={"reason": "Incorrect tare entered"})
    assert response.status_code == 200
    assert Decimal(response.json()["new_remaining_g"]) == Decimal("684.200")
    assert client.post(url, json={"reason": "Retry"}).status_code == 200
    with factory() as db:
        assert db.scalar(select(Spool).where(Spool.code == code)).current_filament_weight_g == Decimal("684.200")
        events = list(db.scalars(select(SpoolCalibration).order_by(SpoolCalibration.id)).all())
        assert [event.event_type for event in events] == [CalibrationEventType.PHYSICAL_CALIBRATION, CalibrationEventType.REVERSAL]
        assert [row.source for row in db.scalars(select(WeightHistory).order_by(WeightHistory.id)).all()] == [WeightSource.SCALE, WeightSource.CORRECTION]


def test_undo_rejects_overwriting_later_inventory_activity(calibration_env) -> None:
    client, factory, code = calibration_env
    calibration = _confirm(client, code, "ordered-undo-calibration").json()
    with factory() as db:
        db.scalar(select(Spool).where(Spool.code == code)).current_filament_weight_g = Decimal("400.000")
        db.commit()
    assert client.post(f"/api/spools/{code}/calibrations/{calibration['id']}/undo", json={"reason": "Too late"}).status_code == 409


def test_recalibration_keeps_history_and_only_applies_drift(calibration_env) -> None:
    client, _, code = calibration_env
    first = _confirm(client, code, "initial-calibration-0001").json()
    second = _confirm(client, code, "recalibration-0002", measured_total_g="566.500", expected_current_remaining_g="407.000").json()
    history = client.get(f"/api/spools/{code}/calibrations").json()
    assert len(history) == 2
    assert Decimal(first["adjustment_g"]) == Decimal("-277.200")
    assert Decimal(second["adjustment_g"]) == Decimal("-64.500")


def test_tare_profile_snapshot_and_empty_spool_learning(calibration_env) -> None:
    client, factory, code = calibration_env
    profile_response = client.post("/api/tare-profiles", json={"name": "eSUN plastic spool A", "manufacturer": "eSUN", "spool_type": "plastic type A", "tare_g": "224.000", "source": "KNOWN"})
    assert profile_response.status_code == 201
    profile = profile_response.json()
    calibration = client.post(f"/api/spools/{code}/calibrations", json={"measured_total_g": "637.000", "tare_profile_id": profile["id"], "expected_current_remaining_g": "684.200", "idempotency_key": "profile-calibration-0001"})
    assert calibration.status_code == 201
    assert client.patch(f"/api/tare-profiles/{profile['id']}", json={"tare_g": "223.700"}).status_code == 200
    assert Decimal(client.get(f"/api/spools/{code}/calibrations").json()[0]["tare_g_used"]) == Decimal("224.000")
    measured = client.post(f"/api/spools/{code}/empty-spool-measurements", json={"measured_tare_g": "221.700", "tare_profile_id": profile["id"], "contribute_to_profile": True, "note": "Spool fully empty"})
    assert measured.status_code == 201
    refreshed = client.get("/api/tare-profiles").json()[0]
    assert Decimal(refreshed["tare_g"]) == Decimal("221.700")
    assert refreshed["source"] == "MEASURED" and refreshed["measured_sample_count"] == 1
    with factory() as db:
        assert db.scalar(select(Spool).where(Spool.code == code)).empty_spool_weight_g == Decimal("221.700")
        assert db.scalar(select(TareMeasurement)).contributes_to_profile is True


def test_estimated_source_and_pending_print_warning(calibration_env) -> None:
    client, factory, code = calibration_env
    with factory() as db:
        job = PrintJob(name="Pending PETG print", status=PrintJobStatus.COMPLETED, capture_mode=PrintJobCaptureMode.LIVE, enrichment_status=PrintJobEnrichmentStatus.ENRICHED, reconciliation_status=PrintJobReconciliationStatus.PENDING, started_at=datetime.now(timezone.utc) - timedelta(hours=2), finished_at=datetime.now(timezone.utc) - timedelta(hours=1))
        db.add(job); db.flush()
        db.add(PrintJobFilamentUsage(print_job_id=job.id, position=0, material_type="PETG", used_g=Decimal("12.500")))
        db.commit(); job_id = job.id
    preview = _preview(client, code, tare_source="ESTIMATED", tare_confidence="LOW")
    assert preview.status_code == 200 and preview.json()["is_estimated"] is True
    assert preview.json()["unreconciled_prints"][0]["print_job_id"] == job_id
    event = _confirm(client, code, "estimated-calibration-0001", tare_source="ESTIMATED", tare_confidence="LOW")
    assert event.status_code == 201 and event.json()["tare_source_used"] == "ESTIMATED"


def test_historical_print_after_checkpoint_requires_acknowledgement(calibration_env) -> None:
    client, factory, code = calibration_env
    assert _confirm(client, code, "checkpoint-calibration-0001").status_code == 201
    with factory() as db:
        spool = db.scalar(select(Spool).where(Spool.code == code))
        printed = datetime.now(timezone.utc) - timedelta(days=1)
        job = PrintJob(name="Historical print", status=PrintJobStatus.COMPLETED, capture_mode=PrintJobCaptureMode.LIVE, enrichment_status=PrintJobEnrichmentStatus.ENRICHED, reconciliation_status=PrintJobReconciliationStatus.PENDING, started_at=printed - timedelta(hours=1), finished_at=printed)
        db.add(job); db.flush()
        usage = PrintJobFilamentUsage(print_job_id=job.id, position=0, material_type="PETG", color="FFFFFFFF", used_g=Decimal("10.000"))
        db.add(usage); db.commit(); spool_id, usage_id = spool.id, usage.id
    queue = client.get("/api/reconciliation/pending").json()
    assert next(row for row in queue["available_spools"] if row["id"] == spool_id)["latest_physical_calibration_at"] is not None
    item = {"filament_usage_id": usage_id, "action": "DEDUCT", "spool_id": spool_id, "consumption_g": "10.000"}
    blocked = client.post("/api/reconciliation/confirm", json={"items": [item]})
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "physical_checkpoint_acknowledgement_required"
    item["checkpoint_acknowledged"] = True
    assert client.post("/api/reconciliation/confirm", json={"items": [item]}).status_code == 200
    with factory() as db:
        assert db.get(Spool, spool_id).current_filament_weight_g == Decimal("397.000")
        assert db.scalar(select(PrintJobFilamentReconciliation)).amount_g == Decimal("10.000")
