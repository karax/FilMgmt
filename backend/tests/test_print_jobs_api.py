from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory, get_db
from app.main import app
from app.models import Location, Manufacturer, Material, PrintJob, PrintJobStatus, Spool, SpoolStatus, WeightHistory
from app.schemas import SpoolCreate
from app.services import add_spool_with_generated_code


@dataclass(frozen=True)
class ApiEnvironment:
    client: TestClient
    session_factory: sessionmaker[Session]
    spool_id: int


@pytest.fixture
def api_environment(tmp_path: Path) -> Iterator[ApiEnvironment]:
    engine = create_database_engine(f"sqlite+pysqlite:///{(tmp_path / 'prints-api.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        manufacturer, material, location = Manufacturer(name="eSUN"), Material(name="PLA+", category="PLA"), Location(name="Rack A")
        session.add_all([manufacturer, material, location])
        session.flush()
        spool = Spool(**SpoolCreate(manufacturer_id=manufacturer.id, material_id=material.id, location_id=location.id, color_name="Black", initial_filament_weight_g=1000).model_dump())
        add_spool_with_generated_code(session, spool)
        session.commit()
        spool_id = spool.id

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield ApiEnvironment(client, factory, spool_id)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def payload(environment: ApiEnvironment, **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {"name": "Phone Stand", "spool_id": environment.spool_id}
    value.update(overrides)
    return value


def create(environment: ApiEnvironment, **overrides: object) -> dict[str, object]:
    response = environment.client.post("/api/prints", json=payload(environment, **overrides))
    assert response.status_code == 201
    return response.json()


def test_list_is_empty(api_environment: ApiEnvironment) -> None:
    assert api_environment.client.get("/api/prints").json() == []


def test_create_minimal_and_complete_planned_job(api_environment: ApiEnvironment) -> None:
    body = create(api_environment, name="  Cyberpunk Pi Case  ", estimated_weight_g=237.4, estimated_time_minutes=402, printer_name="Ender 3 V3 SE", notes="0.2 mm")
    assert body["name"] == "Cyberpunk Pi Case"
    assert body["status"] == "PLANNED"
    assert body["actual_weight_g"] is None and body["actual_time_minutes"] is None
    assert body["printer_name"] == "Ender 3 V3 SE"


@pytest.mark.parametrize("extra", [{"status": "SUCCESS"}, {"actual_weight_g": 2}, {"started_at": "2026-01-01T00:00:00Z"}, {"material_cost": 1.23}])
def test_create_rejects_operational_fields(api_environment: ApiEnvironment, extra: dict[str, object]) -> None:
    assert api_environment.client.post("/api/prints", json=payload(api_environment, **extra)).status_code == 422


def test_create_validates_spool_existence_and_archival(api_environment: ApiEnvironment) -> None:
    assert api_environment.client.post("/api/prints", json=payload(api_environment, spool_id=99999)).status_code == 404
    with api_environment.session_factory() as session:
        spool = session.get(Spool, api_environment.spool_id)
        assert spool is not None
        spool.status = SpoolStatus.ARCHIVED
        session.commit()
    response = api_environment.client.post("/api/prints", json=payload(api_environment))
    assert response.status_code == 409
    assert response.json()["detail"] == "Archived spool cannot be used for a print job."


def test_list_filters_and_deterministic_order(api_environment: ApiEnvironment) -> None:
    first = create(api_environment, name="First")
    second = create(api_environment, name="Second")
    with api_environment.session_factory() as session:
        item = session.get(PrintJob, first["id"])
        assert item is not None
        item.status = PrintJobStatus.SUCCESS
        session.commit()
    listed = api_environment.client.get("/api/prints").json()
    assert [item["id"] for item in listed] == [second["id"], first["id"]]
    assert [item["id"] for item in api_environment.client.get("/api/prints", params={"status": "SUCCESS", "spool_id": api_environment.spool_id}).json()] == [first["id"]]
    assert api_environment.client.get("/api/prints", params={"spool_id": 99999}).json() == []
    assert api_environment.client.get("/api/prints", params={"status": "NOT_A_STATUS"}).status_code == 422


def test_get_and_patch_planned_job(api_environment: ApiEnvironment) -> None:
    created = create(api_environment, estimated_weight_g=100)
    assert api_environment.client.get(f"/api/prints/{created['id']}").json()["estimated_weight_g"] == "100.000"
    updated = api_environment.client.patch(f"/api/prints/{created['id']}", json={"name": "Pi Case V2", "estimated_weight_g": 125, "printer_name": "Bambu Lab A1"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Pi Case V2"
    assert Decimal(updated.json()["estimated_weight_g"]) == Decimal("125")
    assert updated.json()["printer_name"] == "Bambu Lab A1"


def test_patch_validates_spool_and_lifecycle(api_environment: ApiEnvironment) -> None:
    created = create(api_environment)
    endpoint = f"/api/prints/{created['id']}"
    assert api_environment.client.patch(endpoint, json={"spool_id": 99999}).status_code == 404
    assert api_environment.client.patch(endpoint, json={"status": "SUCCESS"}).status_code == 422
    assert api_environment.client.patch(endpoint, json={"material_cost": 1.23}).status_code == 422
    assert api_environment.client.patch(endpoint, json={"name": "   "}).status_code == 422
    with api_environment.session_factory() as session:
        item = session.get(PrintJob, created["id"])
        assert item is not None
        item.status = PrintJobStatus.PRINTING
        session.commit()
    assert api_environment.client.patch(endpoint, json={"name": "Not allowed"}).status_code == 409
    assert api_environment.client.get("/api/prints/99999").status_code == 404


def test_start_planned_job_updates_operational_state_without_weight_changes(api_environment: ApiEnvironment) -> None:
    created = create(api_environment, estimated_weight_g=237)
    with api_environment.session_factory() as session:
        spool = session.get(Spool, api_environment.spool_id)
        assert spool is not None
        before_weight = spool.current_filament_weight_g
        before_percent = spool.remaining_percent
        history_count = len(session.query(WeightHistory).all())
    response = api_environment.client.post(f"/api/prints/{created['id']}/start")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PRINTING"
    assert body["started_at"] is not None
    assert body["finished_at"] is None
    assert body["actual_weight_g"] is None
    with api_environment.session_factory() as session:
        spool = session.get(Spool, api_environment.spool_id)
        assert spool is not None
        assert spool.status is SpoolStatus.IN_USE
        assert spool.opened_at == spool.last_used_at
        assert spool.current_filament_weight_g == before_weight
        assert spool.remaining_percent == before_percent
        assert len(session.query(WeightHistory).all()) == history_count
    assert api_environment.client.patch(f"/api/prints/{created['id']}", json={"name": "Blocked"}).status_code == 409
    assert [item["id"] for item in api_environment.client.get("/api/prints", params={"status": "PRINTING"}).json()] == [created["id"]]


def test_start_preserves_existing_opened_at_and_allows_low(api_environment: ApiEnvironment) -> None:
    created = create(api_environment)
    with api_environment.session_factory() as session:
        spool = session.get(Spool, api_environment.spool_id)
        assert spool is not None
        original_opened_at = spool.created_at
        spool.opened_at = original_opened_at
        spool.status = SpoolStatus.LOW
        session.commit()
    response = api_environment.client.post(f"/api/prints/{created['id']}/start")
    assert response.status_code == 200
    with api_environment.session_factory() as session:
        spool = session.get(Spool, api_environment.spool_id)
        assert spool is not None
        assert spool.status is SpoolStatus.IN_USE
        assert spool.opened_at == original_opened_at
        assert spool.last_used_at is not None


@pytest.mark.parametrize(
    ("spool_status", "job_status", "expected_detail"),
    [
        (SpoolStatus.EMPTY, PrintJobStatus.PLANNED, "Empty spool cannot be used for printing."),
        (SpoolStatus.ARCHIVED, PrintJobStatus.PLANNED, "Archived spool cannot be used for printing."),
        (SpoolStatus.IN_USE, PrintJobStatus.PLANNED, "Spool is already in use."),
        (SpoolStatus.OPEN, PrintJobStatus.SUCCESS, "Only planned print jobs can be started."),
        (SpoolStatus.OPEN, PrintJobStatus.FAILED, "Only planned print jobs can be started."),
        (SpoolStatus.OPEN, PrintJobStatus.CANCELLED, "Only planned print jobs can be started."),
    ],
)
def test_start_rejects_invalid_lifecycle_states(api_environment: ApiEnvironment, spool_status: SpoolStatus, job_status: PrintJobStatus, expected_detail: str) -> None:
    created = create(api_environment)
    with api_environment.session_factory() as session:
        spool = session.get(Spool, api_environment.spool_id)
        job = session.get(PrintJob, created["id"])
        assert spool is not None and job is not None
        spool.status = spool_status
        job.status = job_status
        session.commit()
    response = api_environment.client.post(f"/api/prints/{created['id']}/start")
    assert response.status_code == 409
    assert response.json()["detail"] == expected_detail


def test_start_rejects_second_job_using_same_spool(api_environment: ApiEnvironment) -> None:
    first = create(api_environment, name="Active")
    second = create(api_environment, name="Queued")
    with api_environment.session_factory() as session:
        active = session.get(PrintJob, first["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert active is not None and spool is not None
        active.status = PrintJobStatus.PRINTING
        spool.status = SpoolStatus.OPEN
        session.commit()
    response = api_environment.client.post(f"/api/prints/{second['id']}/start")
    assert response.status_code == 409
    assert response.json()["detail"] == "Another print job is already using this spool."
    assert api_environment.client.post("/api/prints/99999/start").status_code == 404


def test_finish_updates_job_and_releases_spool_without_consuming_weight(
    api_environment: ApiEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = create(api_environment, estimated_weight_g=237)
    started_at = datetime(2026, 8, 30, 14, 0, tzinfo=UTC)
    finished_at = started_at + timedelta(hours=6, minutes=58)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, started_at
        spool.status = SpoolStatus.IN_USE
        before_weight = spool.current_filament_weight_g
        history_count = len(session.query(WeightHistory).all())
        session.commit()
    monkeypatch.setattr("app.services.print_job_service.utc_now", lambda: finished_at)
    response = api_environment.client.post(f"/api/prints/{created['id']}/finish", json={"actual_weight_g": 249.2})
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
    assert response.json()["actual_time_minutes"] == 418
    assert Decimal(response.json()["actual_weight_g"]) == Decimal("249.2")
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        assert job.started_at is not None and job.finished_at is not None
        assert job.started_at.replace(tzinfo=UTC) == started_at
        assert job.finished_at.replace(tzinfo=UTC) == finished_at
        assert spool.status is SpoolStatus.OPEN
        assert spool.last_used_at is not None
        assert spool.last_used_at.replace(tzinfo=UTC) == finished_at
        assert spool.current_filament_weight_g == before_weight - Decimal("249.2")
        assert spool.remaining_percent == 75.1
        history = session.query(WeightHistory).all()
        assert len(history) == history_count + 1
        assert history[-1].weight_g == Decimal("750.8")
        assert history[-1].source.value == "PRINT"
        assert f"Print job #{created['id']}" in (history[-1].notes or "")
    assert api_environment.client.patch(f"/api/prints/{created['id']}", json={"name": "Blocked"}).status_code == 409
    assert [item["id"] for item in api_environment.client.get("/api/prints", params={"status": "SUCCESS"}).json()] == [created["id"]]
    assert api_environment.client.get("/api/prints", params={"status": "PRINTING"}).json() == []


def test_finish_persists_immutable_material_cost_snapshot(
    api_environment: ApiEnvironment,
) -> None:
    created = create(api_environment)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, datetime.now(UTC) - timedelta(minutes=1)
        spool.status = SpoolStatus.IN_USE
        spool.purchase_price = Decimal("20")
        spool.currency = "USD"
        spool.current_filament_weight_g = Decimal("500")
        session.commit()

    response = api_environment.client.post(
        f"/api/prints/{created['id']}/finish",
        json={"actual_weight_g": 100},
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["filament_cost_per_g"]) == Decimal("0.020000")
    assert Decimal(body["material_cost"]) == Decimal("2.0000")
    assert body["material_cost_currency"] == "USD"

    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        assert job.filament_cost_per_g == Decimal("0.020000")
        assert job.material_cost == Decimal("2.0000")
        assert job.material_cost_currency == "USD"
        assert spool.current_filament_weight_g == Decimal("400")
        spool.purchase_price = Decimal("30")
        spool.currency = "EUR"
        spool.initial_filament_weight_g = Decimal("2000")
        session.commit()

    persisted = api_environment.client.get(f"/api/prints/{created['id']}").json()
    assert Decimal(persisted["filament_cost_per_g"]) == Decimal("0.020000")
    assert Decimal(persisted["material_cost"]) == Decimal("2.0000")
    assert persisted["material_cost_currency"] == "USD"


@pytest.mark.parametrize(("weight", "expected_status"), [(100, SpoolStatus.LOW), (0, SpoolStatus.EMPTY)])
def test_finish_recalculates_inventory_status(api_environment: ApiEnvironment, weight: int, expected_status: SpoolStatus) -> None:
    created = create(api_environment)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, datetime.now(UTC) - timedelta(minutes=1)
        spool.status, spool.current_filament_weight_g, spool.needs_drying = SpoolStatus.IN_USE, weight, True
        session.commit()
    response = api_environment.client.post(f"/api/prints/{created['id']}/finish")
    assert response.status_code == 200
    with api_environment.session_factory() as session:
        spool = session.get(Spool, api_environment.spool_id)
        assert spool is not None
        assert spool.status is expected_status
        assert spool.needs_drying is True


def test_finish_consumption_covers_low_empty_zero_and_missing_values(api_environment: ApiEnvironment) -> None:
    created = create(api_environment)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, datetime.now(UTC) - timedelta(minutes=1)
        spool.status, spool.current_filament_weight_g = SpoolStatus.IN_USE, Decimal("350")
        session.commit()
    assert api_environment.client.post(f"/api/prints/{created['id']}/finish", json={"actual_weight_g": 170}).status_code == 200
    with api_environment.session_factory() as session:
        spool = session.get(Spool, api_environment.spool_id)
        assert spool is not None
        assert spool.current_filament_weight_g == Decimal("180")
        assert spool.status is SpoolStatus.LOW

    next_job = create(api_environment)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, next_job["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, datetime.now(UTC) - timedelta(minutes=1)
        spool.status, spool.current_filament_weight_g = SpoolStatus.IN_USE, Decimal("100")
        history_count = len(session.query(WeightHistory).all())
        session.commit()
    assert api_environment.client.post(f"/api/prints/{next_job['id']}/finish", json={"actual_weight_g": 100}).status_code == 200
    with api_environment.session_factory() as session:
        spool = session.get(Spool, api_environment.spool_id)
        assert spool is not None
        assert spool.current_filament_weight_g == Decimal("0") and spool.status is SpoolStatus.EMPTY
        assert len(session.query(WeightHistory).all()) == history_count + 1


@pytest.mark.parametrize("payload", [None, {"actual_weight_g": 0}])
def test_finish_without_effective_consumption_does_not_create_history(api_environment: ApiEnvironment, payload: dict[str, object] | None) -> None:
    created = create(api_environment, estimated_weight_g=500)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, datetime.now(UTC) - timedelta(minutes=1)
        spool.status = SpoolStatus.IN_USE
        spool.purchase_price = Decimal("21.99")
        before_weight = spool.current_filament_weight_g
        history_count = len(session.query(WeightHistory).all())
        session.commit()
    response = api_environment.client.post(f"/api/prints/{created['id']}/finish", json=payload)
    assert response.status_code == 200
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        assert spool.current_filament_weight_g == before_weight
        assert len(session.query(WeightHistory).all()) == history_count
        assert job.actual_weight_g == (Decimal("0") if payload else None)
        if payload:
            assert job.filament_cost_per_g == Decimal("0.021990")
            assert job.material_cost == Decimal("0.0000")
            assert job.material_cost_currency == "EUR"
        else:
            assert job.filament_cost_per_g is None
            assert job.material_cost is None
            assert job.material_cost_currency is None


def test_finish_without_purchase_price_leaves_cost_snapshot_empty(
    api_environment: ApiEnvironment,
) -> None:
    created = create(api_environment)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, datetime.now(UTC) - timedelta(minutes=1)
        spool.status = SpoolStatus.IN_USE
        spool.purchase_price = None
        session.commit()

    assert api_environment.client.post(
        f"/api/prints/{created['id']}/finish",
        json={"actual_weight_g": 10},
    ).status_code == 200
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        assert job is not None
        assert job.filament_cost_per_g is None
        assert job.material_cost is None
        assert job.material_cost_currency is None


def test_finish_rolls_back_when_cost_snapshot_cannot_be_calculated(
    api_environment: ApiEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = create(api_environment)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, datetime.now(UTC) - timedelta(minutes=1)
        spool.status = SpoolStatus.IN_USE
        spool.purchase_price = Decimal("20")
        history_count = len(session.query(WeightHistory).all())
        session.commit()

    from app.services.print_cost_service import InvalidPrintCostDataError

    def fail_cost_calculation(*_args: object, **_kwargs: object) -> object:
        raise InvalidPrintCostDataError

    monkeypatch.setattr(
        "app.services.print_job_service.calculate_print_material_cost",
        fail_cost_calculation,
    )
    response = api_environment.client.post(
        f"/api/prints/{created['id']}/finish",
        json={"actual_weight_g": 100},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Spool data cannot be used to calculate material cost."
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        assert job.status is PrintJobStatus.PRINTING
        assert job.material_cost is None
        assert spool.status is SpoolStatus.IN_USE
        assert spool.current_filament_weight_g == Decimal("1000")
        assert len(session.query(WeightHistory).all()) == history_count


def test_finish_rejects_consumption_above_available_weight_atomically(api_environment: ApiEnvironment) -> None:
    created = create(api_environment)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, datetime.now(UTC) - timedelta(minutes=1)
        spool.status, spool.current_filament_weight_g = SpoolStatus.IN_USE, Decimal("100")
        history_count = len(session.query(WeightHistory).all())
        session.commit()
    response = api_environment.client.post(f"/api/prints/{created['id']}/finish", json={"actual_weight_g": 101})
    assert response.status_code == 409
    assert response.json()["detail"] == "Print consumption exceeds available spool weight."
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        assert job.status is PrintJobStatus.PRINTING
        assert spool.status is SpoolStatus.IN_USE and spool.current_filament_weight_g == Decimal("100")
        assert len(session.query(WeightHistory).all()) == history_count


def test_finish_rejects_invalid_states_and_allows_new_start_after_success(api_environment: ApiEnvironment) -> None:
    created = create(api_environment)
    endpoint = f"/api/prints/{created['id']}/finish"
    assert api_environment.client.post(endpoint).status_code == 409


def test_finish_uses_total_seconds_and_releases_partial_index(
    api_environment: ApiEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = create(api_environment, name="Long print")
    started_at = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    finished_at = started_at + timedelta(hours=30)
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, first["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, started_at
        spool.status = SpoolStatus.IN_USE
        session.commit()
    monkeypatch.setattr("app.services.print_job_service.utc_now", lambda: finished_at)
    assert api_environment.client.post(f"/api/prints/{first['id']}/finish").json()["actual_time_minutes"] == 1800
    second = create(api_environment, name="Next print")
    assert api_environment.client.post(f"/api/prints/{second['id']}/start").status_code == 200


def test_finish_rejects_negative_weight_and_missing_job(api_environment: ApiEnvironment) -> None:
    created = create(api_environment)
    endpoint = f"/api/prints/{created['id']}/finish"
    assert api_environment.client.post(endpoint, json={"actual_weight_g": -1}).status_code == 422
    assert api_environment.client.post(endpoint, json={"actual_weight_g": 1, "material_cost": 0.01}).status_code == 422
    assert api_environment.client.post("/api/prints/99999/finish").status_code == 404
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.status, job.started_at = PrintJobStatus.PRINTING, None
        spool.status = SpoolStatus.IN_USE
        session.commit()
    assert api_environment.client.post(endpoint).json()["detail"] == "Printing job has no start time."
    with api_environment.session_factory() as session:
        job = session.get(PrintJob, created["id"])
        spool = session.get(Spool, api_environment.spool_id)
        assert job is not None and spool is not None
        job.started_at = datetime.now(UTC) - timedelta(minutes=1)
        spool.status, spool.archived_at = SpoolStatus.ARCHIVED, datetime.now(UTC)
        session.commit()
    assert api_environment.client.post(endpoint).status_code == 409
