from collections.abc import Iterator
from datetime import UTC

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import Manufacturer
from app.schemas import ManufacturerCreate, ManufacturerRead, ManufacturerUpdate

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


def test_manufacturer_can_be_created(db_session: Session) -> None:
    payload = ManufacturerCreate(
        name="  eSUN  ",
        website="https://www.esun3d.com",
    )
    manufacturer = Manufacturer(
        name=payload.name,
        website=str(payload.website) if payload.website else None,
    )

    db_session.add(manufacturer)
    db_session.commit()
    db_session.refresh(manufacturer)

    assert manufacturer.id is not None
    assert manufacturer.name == "eSUN"
    assert manufacturer.created_at is not None
    assert manufacturer.updated_at is not None


def test_manufacturer_website_is_optional(db_session: Session) -> None:
    payload = ManufacturerCreate(name="Generic")
    manufacturer = Manufacturer(name=payload.name)

    db_session.add(manufacturer)
    db_session.commit()
    db_session.refresh(manufacturer)

    assert manufacturer.website is None


def test_manufacturer_name_is_unique(db_session: Session) -> None:
    db_session.add(Manufacturer(name="eSUN"))
    db_session.commit()
    db_session.add(Manufacturer(name="eSUN"))

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_manufacturer_name_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        ManufacturerCreate(name="")


def test_manufacturer_name_cannot_contain_only_spaces() -> None:
    with pytest.raises(ValidationError):
        ManufacturerCreate(name="    ")


def test_manufacturer_website_must_be_a_valid_http_url() -> None:
    with pytest.raises(ValidationError):
        ManufacturerCreate(name="Invalid URL", website="not-a-valid-url")


def test_manufacturer_orm_object_can_be_converted_to_read_schema(
    db_session: Session,
) -> None:
    manufacturer = Manufacturer(
        name="Polymaker",
        website="https://polymaker.com",
    )
    db_session.add(manufacturer)
    db_session.commit()
    db_session.refresh(manufacturer)

    result = ManufacturerRead.model_validate(manufacturer)

    assert result.id == manufacturer.id
    assert result.name == "Polymaker"
    assert str(result.website) == "https://polymaker.com/"
    assert result.created_at.tzinfo is UTC
    assert result.updated_at.tzinfo is UTC
    assert result.created_at.replace(tzinfo=None) == manufacturer.created_at.replace(
        tzinfo=None
    )
    assert result.updated_at.replace(tzinfo=None) == manufacturer.updated_at.replace(
        tzinfo=None
    )
    assert result.model_dump(mode="json")["created_at"].endswith("Z")


def test_manufacturer_update_fields_are_optional_and_protected() -> None:
    assert ManufacturerUpdate().model_dump(exclude_unset=True) == {}

    with pytest.raises(ValidationError):
        ManufacturerUpdate(id=1)


def test_updated_at_changes_when_manufacturer_is_updated(
    db_session: Session,
) -> None:
    manufacturer = Manufacturer(name="SUNLU")
    db_session.add(manufacturer)
    db_session.commit()
    db_session.refresh(manufacturer)
    original_updated_at = manufacturer.updated_at

    manufacturer.name = "SUNLU Filament"
    db_session.commit()
    db_session.refresh(manufacturer)

    assert manufacturer.updated_at > original_updated_at
