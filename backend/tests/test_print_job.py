from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import Location, Manufacturer, Material, PrintJob, PrintJobStatus, Spool
from app.schemas import PrintJobCreate, PrintJobRead, SpoolCreate
from app.services import add_spool_with_generated_code


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def spool(db_session: Session) -> Spool:
    manufacturer = Manufacturer(name="eSUN")
    material = Material(name="PLA+", category="PLA")
    location = Location(name="Rack A")
    db_session.add_all([manufacturer, material, location])
    db_session.flush()
    payload = SpoolCreate(manufacturer_id=manufacturer.id, material_id=material.id, location_id=location.id, color_name="Black", initial_filament_weight_g=1000)
    value = Spool(**payload.model_dump())
    add_spool_with_generated_code(db_session, value)
    db_session.commit()
    return value


def test_print_job_defaults_to_planned_and_relates_to_spool(db_session: Session, spool: Spool) -> None:
    payload = PrintJobCreate(name="  Phone Stand  ", spool_id=spool.id, estimated_weight_g=Decimal("237.4"), estimated_time_minutes=402, printer_name="  Ender 3 V3 SE  ")
    job = PrintJob(**payload.model_dump())
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.name == "Phone Stand"
    assert job.printer_name == "Ender 3 V3 SE"
    assert job.status is PrintJobStatus.PLANNED
    assert job.spool == spool
    assert job in spool.print_jobs
    assert job.created_at is not None and job.updated_at is not None


@pytest.mark.parametrize("name", ["", "   "])
def test_print_job_rejects_blank_name(name: str) -> None:
    with pytest.raises(ValidationError):
        PrintJobCreate(name=name, spool_id=1)


@pytest.mark.parametrize(("field", "value"), [("estimated_weight_g", 0), ("estimated_weight_g", -1), ("estimated_time_minutes", 0), ("estimated_time_minutes", -1)])
def test_create_values_must_be_positive(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        PrintJobCreate(name="Phone Stand", spool_id=1, **{field: value})


@pytest.mark.parametrize("status", list(PrintJobStatus))
def test_print_job_status_values(status: PrintJobStatus) -> None:
    assert status.value in {"PLANNED", "PRINTING", "SUCCESS", "FAILED", "CANCELLED"}


def test_multiple_jobs_and_foreign_key_restriction(db_session: Session, spool: Spool) -> None:
    jobs = [PrintJob(name=f"Job {number}", spool_id=spool.id) for number in range(3)]
    db_session.add_all(jobs)
    db_session.commit()
    assert len(spool.print_jobs) == 3

    db_session.delete(spool)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_only_one_printing_job_is_allowed_per_spool(
    db_session: Session,
    spool: Spool,
) -> None:
    db_session.add(PrintJob(name="Active", spool_id=spool.id, status=PrintJobStatus.PRINTING))
    db_session.commit()
    db_session.add(PrintJob(name="Second active", spool_id=spool.id, status=PrintJobStatus.PRINTING))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add_all(
        [
            PrintJob(name="Planned", spool_id=spool.id, status=PrintJobStatus.PLANNED),
            PrintJob(name="Success", spool_id=spool.id, status=PrintJobStatus.SUCCESS),
            PrintJob(name="Failed", spool_id=spool.id, status=PrintJobStatus.FAILED),
            PrintJob(name="Cancelled", spool_id=spool.id, status=PrintJobStatus.CANCELLED),
        ]
    )
    db_session.commit()


def test_database_rejects_missing_spool(db_session: Session) -> None:
    db_session.add(PrintJob(name="Missing spool", spool_id=999999))
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize(("field", "value"), [("actual_weight_g", -1), ("actual_time_minutes", -1)])
def test_database_rejects_negative_actual_values(
    db_session: Session,
    spool: Spool,
    field: str,
    value: int,
) -> None:
    db_session.add(PrintJob(name="Invalid actual", spool_id=spool.id, **{field: value}))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_read_schema_validates_internal_values_and_serializes(db_session: Session, spool: Spool) -> None:
    started_at = datetime.now(UTC)
    job = PrintJob(name="Pi Case", spool_id=spool.id, actual_weight_g=Decimal("0"), actual_time_minutes=0, started_at=started_at, finished_at=started_at + timedelta(minutes=1))
    db_session.add(job)
    db_session.commit()
    read = PrintJobRead.model_validate(job)
    assert read.name == "Pi Case"
    assert read.actual_weight_g == Decimal("0")


def test_read_schema_rejects_invalid_temporal_order() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        PrintJobRead(id=1, name="Invalid dates", spool_id=1, status=PrintJobStatus.PLANNED, estimated_weight_g=None, actual_weight_g=None, estimated_time_minutes=None, actual_time_minutes=None, filament_cost_per_g=None, material_cost=None, material_cost_currency=None, printer_name=None, started_at=now, finished_at=now - timedelta(seconds=1), notes=None, created_at=now, updated_at=now)
