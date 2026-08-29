from collections.abc import Iterator
from datetime import UTC

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import Location
from app.schemas import LocationCreate, LocationRead, LocationUpdate

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


def test_location_can_be_created(db_session: Session) -> None:
    payload = LocationCreate(
        name="Rack A / Slot 1",
        description="First position in the main rack.",
    )
    location = Location(**payload.model_dump())

    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)

    assert location.id is not None
    assert location.name == "Rack A / Slot 1"
    assert location.created_at is not None
    assert location.updated_at is not None


def test_location_description_is_optional(db_session: Session) -> None:
    payload = LocationCreate(name="Dry Box")
    location = Location(**payload.model_dump())

    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)

    assert location.description is None


def test_location_name_is_unique(db_session: Session) -> None:
    db_session.add(Location(name="Dry Box"))
    db_session.commit()
    db_session.add(Location(name="Dry Box"))

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_location_name_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        LocationCreate(name="")


def test_location_name_cannot_contain_only_spaces() -> None:
    with pytest.raises(ValidationError):
        LocationCreate(name="   ")


def test_location_name_strips_surrounding_whitespace() -> None:
    payload = LocationCreate(name="  Rack A / Slot 1  ")

    assert payload.name == "Rack A / Slot 1"


def test_location_orm_object_can_be_converted_to_read_schema(
    db_session: Session,
) -> None:
    location = Location(
        name="Cabinet",
        description="Closed storage beside the printer.",
    )
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)

    result = LocationRead.model_validate(location)

    assert result.id == location.id
    assert result.name == "Cabinet"
    assert result.description == "Closed storage beside the printer."
    assert result.created_at.tzinfo is UTC
    assert result.updated_at.tzinfo is UTC
    assert result.model_dump(mode="json")["created_at"].endswith("Z")


def test_location_update_fields_are_optional_and_protected() -> None:
    assert LocationUpdate(description="Updated rack.").model_dump(
        exclude_unset=True
    ) == {"description": "Updated rack."}

    with pytest.raises(ValidationError):
        LocationUpdate(id=1)


def test_location_updated_at_changes_on_update(db_session: Session) -> None:
    location = Location(name="Printer")
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    original_updated_at = location.updated_at

    location.description = "Currently mounted on the printer."
    db_session.commit()
    db_session.refresh(location)

    assert location.updated_at > original_updated_at
