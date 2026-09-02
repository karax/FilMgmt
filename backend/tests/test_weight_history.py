from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import (
    Manufacturer,
    Material,
    Spool,
    SpoolStatus,
    WeightHistory,
    WeightSource,
)
from app.schemas import SpoolCreate, WeightHistoryCreate, WeightHistoryRead
from app.services import add_spool_with_generated_code

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_database_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    try:
        with session_factory() as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def spool(db_session: Session) -> Spool:
    manufacturer = Manufacturer(name="eSUN")
    material = Material(name="PLA+", category="PLA")
    db_session.add_all([manufacturer, material])
    db_session.flush()

    payload = SpoolCreate(
        manufacturer_id=manufacturer.id,
        material_id=material.id,
        color_name="Black",
        initial_filament_weight_g=1000,
        current_filament_weight_g=742,
    )
    result = Spool(**payload.model_dump())
    add_spool_with_generated_code(db_session, result)
    db_session.commit()
    return result


def add_history(
    db_session: Session,
    spool: Spool,
    weight_g: Decimal | int,
    source: WeightSource = WeightSource.MANUAL,
    **values: object,
) -> WeightHistory:
    history = WeightHistory(
        spool_id=spool.id,
        weight_g=Decimal(weight_g),
        source=source,
        **values,
    )
    db_session.add(history)
    db_session.flush()
    return history


def create_another_spool(db_session: Session, spool: Spool) -> Spool:
    payload = SpoolCreate(
        manufacturer_id=spool.manufacturer_id,
        material_id=spool.material_id,
        color_name="Orange",
        initial_filament_weight_g=500,
    )
    result = Spool(**payload.model_dump())
    add_spool_with_generated_code(db_session, result)
    db_session.flush()
    return result


def test_weight_history_can_be_created(
    db_session: Session,
    spool: Spool,
) -> None:
    history = add_history(
        db_session,
        spool,
        742,
        notes="Pesagem manual.",
    )
    db_session.commit()
    db_session.refresh(history)

    assert history.id is not None
    assert history.spool_id == spool.id
    assert history.weight_g == Decimal("742.000")
    assert history.source is WeightSource.MANUAL
    assert history.notes == "Pesagem manual."
    assert history.created_at is not None


def test_weight_history_references_its_spool(
    db_session: Session,
    spool: Spool,
) -> None:
    history = add_history(db_session, spool, 742)
    db_session.commit()

    assert history.spool is spool
    assert history.spool.code == spool.code


def test_spool_exposes_history_in_chronological_order(
    db_session: Session,
    spool: Spool,
) -> None:
    first_at = datetime(2026, 8, 29, 9, tzinfo=UTC)
    add_history(
        db_session,
        spool,
        742,
        created_at=first_at + timedelta(hours=2),
    )
    add_history(db_session, spool, 1000, created_at=first_at)
    add_history(
        db_session,
        spool,
        850,
        WeightSource.PRINT,
        created_at=first_at + timedelta(hours=1),
    )
    db_session.commit()
    db_session.expire(spool, ["weight_history"])

    assert [entry.weight_g for entry in spool.weight_history] == [
        Decimal("1000.000"),
        Decimal("850.000"),
        Decimal("742.000"),
    ]
    assert all(entry.spool_id == spool.id for entry in spool.weight_history)


def test_zero_weight_is_valid(db_session: Session, spool: Spool) -> None:
    history = add_history(db_session, spool, 0)
    db_session.commit()

    assert history.weight_g == Decimal("0.000")
    assert WeightHistoryCreate(weight_g=0, source="MANUAL").weight_g == 0


def test_negative_weight_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        WeightHistoryCreate(weight_g=-1, source="MANUAL")


def test_negative_weight_is_rejected_by_database(
    db_session: Session,
    spool: Spool,
) -> None:
    db_session.add(
        WeightHistory(
            spool_id=spool.id,
            weight_g=Decimal("-1"),
            source=WeightSource.MANUAL,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


@pytest.mark.parametrize("source", list(WeightSource))
def test_all_weight_sources_are_valid(source: WeightSource) -> None:
    payload = WeightHistoryCreate(weight_g=500, source=source)

    assert payload.source is source
    assert payload.model_dump(mode="json")["source"] == source.value


def test_weight_source_is_persisted_as_text(
    db_session: Session,
    spool: Spool,
) -> None:
    history = add_history(db_session, spool, 600, WeightSource.SCALE)
    db_session.commit()

    persisted_source = db_session.execute(
        text("SELECT source FROM weight_history WHERE id = :history_id"),
        {"history_id": history.id},
    ).scalar_one()

    assert persisted_source == "SCALE"


def test_unknown_weight_source_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        WeightHistoryCreate(weight_g=500, source="UNKNOWN")


def test_weight_history_orm_object_converts_to_read_schema(
    db_session: Session,
    spool: Spool,
) -> None:
    history = add_history(
        db_session,
        spool,
        608,
        WeightSource.SCALE,
        notes="Balança digital.",
    )
    db_session.commit()
    db_session.refresh(history)

    result = WeightHistoryRead.model_validate(history)

    assert result.id == history.id
    assert result.spool_id == spool.id
    assert result.weight_g == Decimal("608.000")
    assert result.source is WeightSource.SCALE
    assert result.created_at.tzinfo is UTC


def test_invalid_spool_foreign_key_is_rejected(
    db_session: Session,
) -> None:
    db_session.add(
        WeightHistory(
            spool_id=999_999,
            weight_g=Decimal("500"),
            source=WeightSource.IMPORT,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_histories_remain_isolated_between_spools(
    db_session: Session,
    spool: Spool,
) -> None:
    second_spool = create_another_spool(db_session, spool)
    first_history = add_history(db_session, spool, 742)
    second_history = add_history(
        db_session,
        second_spool,
        500,
        WeightSource.IMPORT,
    )
    db_session.commit()
    db_session.expire_all()

    assert [entry.id for entry in spool.weight_history] == [first_history.id]
    assert [entry.id for entry in second_spool.weight_history] == [
        second_history.id
    ]


@pytest.mark.parametrize("protected_field", ["id", "spool_id", "created_at"])
def test_create_schema_rejects_history_managed_fields(
    protected_field: str,
) -> None:
    values: dict[str, object] = {
        "weight_g": 742,
        "source": "MANUAL",
        protected_field: 1,
    }
    if protected_field == "created_at":
        values[protected_field] = datetime.now(UTC)

    with pytest.raises(ValidationError):
        WeightHistoryCreate(**values)


def test_creating_history_does_not_change_current_spool_weight(
    db_session: Session,
    spool: Spool,
) -> None:
    add_history(db_session, spool, 600, WeightSource.CORRECTION)
    db_session.commit()
    db_session.refresh(spool)

    assert spool.current_filament_weight_g == Decimal("742.000")


def test_spool_creation_does_not_create_initial_history(
    db_session: Session,
    spool: Spool,
) -> None:
    histories = db_session.scalars(
        select(WeightHistory).where(WeightHistory.spool_id == spool.id)
    ).all()

    assert histories == []


def test_archiving_spool_preserves_history(
    db_session: Session,
    spool: Spool,
) -> None:
    history = add_history(db_session, spool, 742)
    db_session.commit()
    history_id = history.id

    spool.status = SpoolStatus.ARCHIVED
    spool.archived_at = datetime.now(UTC)
    db_session.commit()

    assert db_session.get(WeightHistory, history_id) is not None


def test_physical_spool_delete_cascades_to_history(
    db_session: Session,
    spool: Spool,
) -> None:
    history = add_history(db_session, spool, 742)
    spool.status = SpoolStatus.ARCHIVED
    spool.archived_at = datetime.now(UTC)
    db_session.commit()
    history_id = history.id

    db_session.delete(spool)
    db_session.commit()

    persisted_count = db_session.execute(
        text("SELECT COUNT(*) FROM weight_history WHERE id = :history_id"),
        {"history_id": history_id},
    ).scalar_one()
    db_session.expunge_all()

    assert persisted_count == 0
    assert db_session.get(WeightHistory, history_id) is None
