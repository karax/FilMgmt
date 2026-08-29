from collections.abc import Iterator
import re

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import Manufacturer, Material, Spool
from app.schemas import SpoolCreate, SpoolUpdate
from app.services import add_spool_with_generated_code, format_spool_code

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
def catalog_ids(db_session: Session) -> tuple[int, int]:
    manufacturer = Manufacturer(name="Code Test Manufacturer")
    material = Material(name="Code Test PLA", category="PLA")
    db_session.add_all([manufacturer, material])
    db_session.commit()
    return manufacturer.id, material.id


def new_spool(manufacturer_id: int, material_id: int, color: str) -> Spool:
    payload = SpoolCreate(
        manufacturer_id=manufacturer_id,
        material_id=material_id,
        color_name=color,
        initial_filament_weight_g=1000,
    )
    return Spool(**payload.model_dump())


@pytest.mark.parametrize(
    ("spool_id", "expected"),
    [
        (1, "FIL-0001"),
        (9, "FIL-0009"),
        (42, "FIL-0042"),
        (9999, "FIL-9999"),
        (10000, "FIL-10000"),
    ],
)
def test_format_spool_code_uses_minimum_four_digit_width(
    spool_id: int,
    expected: str,
) -> None:
    assert format_spool_code(spool_id) == expected


@pytest.mark.parametrize("spool_id", [0, -1, -50])
def test_format_spool_code_rejects_non_positive_ids(spool_id: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        format_spool_code(spool_id)


def test_code_is_generated_automatically_from_database_id(
    db_session: Session,
    catalog_ids: tuple[int, int],
) -> None:
    spool = new_spool(*catalog_ids, color="Black")

    add_spool_with_generated_code(db_session, spool)
    db_session.commit()

    assert spool.id is not None
    assert spool.code == format_spool_code(spool.id)
    assert re.fullmatch(r"FIL-[0-9]{4,}", spool.code)


def test_consecutive_spools_receive_different_codes(
    db_session: Session,
    catalog_ids: tuple[int, int],
) -> None:
    first = new_spool(*catalog_ids, color="Black")
    second = new_spool(*catalog_ids, color="Orange")

    add_spool_with_generated_code(db_session, first)
    add_spool_with_generated_code(db_session, second)
    db_session.commit()

    assert first.code != second.code
    assert first.code == format_spool_code(first.id)
    assert second.code == format_spool_code(second.id)


def test_spool_schemas_reject_client_supplied_code() -> None:
    with pytest.raises(ValidationError):
        SpoolCreate(
            manufacturer_id=1,
            material_id=1,
            color_name="Black",
            initial_filament_weight_g=1000,
            code="HACK-123",
        )

    with pytest.raises(ValidationError):
        SpoolUpdate(code="FIL-9999")


def test_editing_spool_fields_does_not_change_code(
    db_session: Session,
    catalog_ids: tuple[int, int],
) -> None:
    spool = new_spool(*catalog_ids, color="Black")
    add_spool_with_generated_code(db_session, spool)
    db_session.commit()
    original_code = spool.code

    update = SpoolUpdate(color_name="Galaxy Purple")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(spool, field, value)
    db_session.commit()
    db_session.refresh(spool)

    assert spool.color_name == "Galaxy Purple"
    assert spool.code == original_code


def test_rollback_removes_spool_flushed_before_commit(
    db_session: Session,
    catalog_ids: tuple[int, int],
) -> None:
    spool = new_spool(*catalog_ids, color="Rollback Black")
    add_spool_with_generated_code(db_session, spool)
    flushed_id = spool.id

    assert db_session.get(Spool, flushed_id) is spool

    db_session.rollback()

    assert db_session.scalar(select(Spool).where(Spool.id == flushed_id)) is None
