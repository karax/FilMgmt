from collections.abc import Iterator
from datetime import UTC
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import Material
from app.schemas import MaterialCreate, MaterialRead, MaterialUpdate

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


def test_material_pla_can_be_created(db_session: Session) -> None:
    payload = MaterialCreate(
        name="PLA",
        category="PLA",
        default_nozzle_temp_min=190,
        default_nozzle_temp_max=220,
        default_bed_temp_min=0,
        default_bed_temp_max=60,
        density_g_cm3=1.24,
    )
    material = Material(**payload.model_dump())

    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    assert material.id is not None
    assert material.name == "PLA"
    assert material.category == "PLA"
    assert material.density_g_cm3 == Decimal("1.240")
    assert material.created_at is not None
    assert material.updated_at is not None


def test_material_optional_fields_can_be_omitted(db_session: Session) -> None:
    payload = MaterialCreate(name="Experimental", category="OTHER")
    material = Material(**payload.model_dump())

    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    assert material.default_nozzle_temp_min is None
    assert material.default_nozzle_temp_max is None
    assert material.default_bed_temp_min is None
    assert material.default_bed_temp_max is None
    assert material.density_g_cm3 is None
    assert material.notes is None


def test_material_name_is_unique(db_session: Session) -> None:
    db_session.add(Material(name="PLA", category="PLA"))
    db_session.commit()
    db_session.add(Material(name="PLA", category="PLA"))

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


@pytest.mark.parametrize("temperature", [-10, 501])
def test_material_temperature_must_be_in_supported_range(
    temperature: int,
) -> None:
    with pytest.raises(ValidationError):
        MaterialCreate(
            name="Broken",
            category="OTHER",
            default_nozzle_temp_min=temperature,
        )


def test_material_nozzle_minimum_cannot_exceed_maximum() -> None:
    with pytest.raises(ValidationError):
        MaterialCreate(
            name="Broken",
            category="OTHER",
            default_nozzle_temp_min=250,
            default_nozzle_temp_max=200,
        )


def test_material_bed_minimum_cannot_exceed_maximum() -> None:
    with pytest.raises(ValidationError):
        MaterialCreate(
            name="Broken",
            category="OTHER",
            default_bed_temp_min=100,
            default_bed_temp_max=60,
        )


@pytest.mark.parametrize("density", [Decimal("-1.24"), Decimal("10.001")])
def test_material_density_must_be_positive_and_reasonable(
    density: Decimal,
) -> None:
    with pytest.raises(ValidationError):
        MaterialCreate(
            name="Broken",
            category="OTHER",
            density_g_cm3=density,
        )


def test_material_category_is_normalized_to_uppercase() -> None:
    payload = MaterialCreate(name="Silk PLA", category="  pla  ")

    assert payload.category == "PLA"


@pytest.mark.parametrize("name", ["", "    "])
def test_material_name_cannot_be_empty(name: str) -> None:
    with pytest.raises(ValidationError):
        MaterialCreate(name=name, category="OTHER")


def test_material_orm_object_can_be_converted_to_read_schema(
    db_session: Session,
) -> None:
    material = Material(
        name="PETG",
        category="PETG",
        default_nozzle_temp_min=230,
        default_nozzle_temp_max=250,
        density_g_cm3=Decimal("1.270"),
        notes="Durable general-purpose material.",
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    result = MaterialRead.model_validate(material)

    assert result.id == material.id
    assert result.name == "PETG"
    assert result.category == "PETG"
    assert result.density_g_cm3 == Decimal("1.270")
    assert result.created_at.tzinfo is UTC
    assert result.updated_at.tzinfo is UTC
    assert result.model_dump(mode="json")["created_at"].endswith("Z")


def test_material_update_is_partial_protected_and_validated() -> None:
    assert MaterialUpdate(notes="New note").model_dump(exclude_unset=True) == {
        "notes": "New note"
    }

    with pytest.raises(ValidationError):
        MaterialUpdate(id=1)

    with pytest.raises(ValidationError):
        MaterialUpdate(
            default_nozzle_temp_min=250,
            default_nozzle_temp_max=200,
        )


def test_material_updated_at_changes_on_update(db_session: Session) -> None:
    material = Material(name="TPU", category="TPU")
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    original_updated_at = material.updated_at

    material.notes = "Flexible material."
    db_session.commit()
    db_session.refresh(material)

    assert material.updated_at > original_updated_at
