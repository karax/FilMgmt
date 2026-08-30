from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import Location, Manufacturer, Material, Spool
from app.scripts.seed_manufacturers import MANUFACTURER_SEED, seed_manufacturers


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def manufacturers(session: Session) -> list[Manufacturer]:
    return list(session.scalars(select(Manufacturer).order_by(Manufacturer.id)).all())


def test_seed_populates_all_expected_manufacturers_in_an_empty_database(
    db_session: Session,
) -> None:
    result = seed_manufacturers(db_session)

    assert len(result.inserted) == len(MANUFACTURER_SEED)
    assert result.existing == ()
    assert result.websites_updated == ()
    assert [(manufacturer.name, manufacturer.website) for manufacturer in manufacturers(db_session)] == list(MANUFACTURER_SEED)


def test_seed_is_idempotent_and_matches_existing_names_case_insensitively(
    db_session: Session,
) -> None:
    db_session.add(Manufacturer(name="ESUN", website="https://custom.example"))
    db_session.commit()

    first = seed_manufacturers(db_session)
    second = seed_manufacturers(db_session)

    assert len(manufacturers(db_session)) == len(MANUFACTURER_SEED)
    assert "ESUN" in first.existing
    assert second.inserted == ()
    assert len(second.existing) == len(MANUFACTURER_SEED)
    assert db_session.scalar(select(Manufacturer.website).where(Manufacturer.name == "ESUN")) == "https://custom.example"


def test_seed_preserves_custom_website_and_fills_a_missing_one(
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            Manufacturer(name="Prusament", website="https://custom.example"),
            Manufacturer(name="Polymaker"),
        ]
    )
    db_session.commit()

    result = seed_manufacturers(db_session)

    websites = {manufacturer.name: manufacturer.website for manufacturer in manufacturers(db_session)}
    assert websites["Prusament"] == "https://custom.example"
    assert websites["Polymaker"] == "https://polymaker.com"
    assert result.websites_updated == ("Polymaker",)


def test_seed_preserves_existing_spool_relationships(db_session: Session) -> None:
    manufacturer = Manufacturer(name="eSUN", website="https://custom.example")
    material = Material(name="PLA", category="PLA")
    location = Location(name="Rack A")
    db_session.add_all([manufacturer, material, location])
    db_session.flush()
    spool = Spool(
        code="FIL-0001",
        manufacturer_id=manufacturer.id,
        material_id=material.id,
        location_id=location.id,
        color_name="Black",
        initial_filament_weight_g=Decimal("1000"),
        current_filament_weight_g=Decimal("1000"),
    )
    db_session.add(spool)
    db_session.commit()

    seed_manufacturers(db_session)

    persisted_spool = db_session.get(Spool, spool.id)
    assert persisted_spool is not None
    assert persisted_spool.manufacturer_id == manufacturer.id
    assert db_session.get(Manufacturer, manufacturer.id).website == "https://custom.example"  # type: ignore[union-attr]
