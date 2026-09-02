from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import Manufacturer, Material, Spool, SpoolStatus
from app.schemas import SpoolCreate, SpoolRead, SpoolUpdate
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
def catalog_records(
    db_session: Session,
) -> tuple[Manufacturer, Material]:
    manufacturer = Manufacturer(name="eSUN")
    material = Material(name="PLA+", category="PLA")
    db_session.add_all([manufacturer, material])
    db_session.commit()
    return manufacturer, material


def create_spool(
    db_session: Session,
    catalog_records: tuple[Manufacturer, Material],
    **overrides: object,
) -> Spool:
    manufacturer, material = catalog_records
    values: dict[str, object] = {
        "manufacturer_id": manufacturer.id,
        "material_id": material.id,
        "product_name": "PLA+ HS",
        "color_name": "Black",
        "color_hex": "#000000",
        "initial_filament_weight_g": 1000,
        "empty_spool_weight_g": 244,
        "purchase_price": Decimal("21.99"),
    }
    values.update(overrides)
    payload = SpoolCreate(**values)
    spool = Spool(**payload.model_dump())
    add_spool_with_generated_code(db_session, spool)
    return spool


def test_spool_can_be_created_with_relationships(
    db_session: Session,
    catalog_records: tuple[Manufacturer, Material],
) -> None:
    manufacturer, material = catalog_records
    spool = create_spool(db_session, catalog_records)
    db_session.commit()
    db_session.refresh(spool)

    assert spool.id is not None
    assert spool.manufacturer == manufacturer
    assert spool.material == material
    assert spool.current_filament_weight_g == Decimal("1000.000")
    assert spool.status is SpoolStatus.SEALED
    assert spool.created_at is not None
    assert spool.updated_at is not None
    assert spool.archived_at is None


def test_spool_codes_are_generated_from_unique_ids(
    db_session: Session,
    catalog_records: tuple[Manufacturer, Material],
) -> None:
    first = create_spool(db_session, catalog_records)
    second = create_spool(db_session, catalog_records, color_name="Orange")
    db_session.commit()

    assert first.code == f"FIL-{first.id:04d}"
    assert second.code == f"FIL-{second.id:04d}"
    assert first.code != second.code


def test_archived_spool_code_is_not_reused(
    db_session: Session,
    catalog_records: tuple[Manufacturer, Material],
) -> None:
    archived = create_spool(db_session, catalog_records)
    archived.archived_at = datetime.now(UTC)
    archived.status = SpoolStatus.ARCHIVED
    db_session.commit()

    active = create_spool(db_session, catalog_records, color_name="White")
    db_session.commit()

    assert active.code != archived.code


def test_physically_deleted_spool_id_is_not_reused_on_sqlite(
    db_session: Session,
    catalog_records: tuple[Manufacturer, Material],
) -> None:
    deleted = create_spool(db_session, catalog_records)
    db_session.commit()
    deleted_id = deleted.id
    db_session.delete(deleted)
    db_session.commit()

    replacement = create_spool(db_session, catalog_records, color_name="White")
    db_session.commit()

    assert replacement.id > deleted_id
    assert replacement.code != f"FIL-{deleted_id:04d}"


def test_spool_code_is_unique_in_database(
    db_session: Session,
    catalog_records: tuple[Manufacturer, Material],
) -> None:
    first = create_spool(db_session, catalog_records)
    db_session.commit()

    duplicate = Spool(
        code=first.code,
        manufacturer_id=first.manufacturer_id,
        material_id=first.material_id,
        color_name="Duplicate",
        diameter_mm=Decimal("1.75"),
        initial_filament_weight_g=Decimal("1000"),
        current_filament_weight_g=Decimal("1000"),
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


@pytest.mark.parametrize("initial_weight", [0, -1])
def test_initial_filament_weight_must_be_positive(initial_weight: int) -> None:
    with pytest.raises(ValidationError):
        SpoolCreate(
            manufacturer_id=1,
            material_id=1,
            color_name="Black",
            initial_filament_weight_g=initial_weight,
        )


def test_current_weight_cannot_exceed_initial_weight() -> None:
    with pytest.raises(ValidationError):
        SpoolCreate(
            manufacturer_id=1,
            material_id=1,
            color_name="Black",
            initial_filament_weight_g=1000,
            current_filament_weight_g=1100,
        )


def test_current_weight_can_be_zero() -> None:
    payload = SpoolCreate(
        manufacturer_id=1,
        material_id=1,
        color_name="Black",
        initial_filament_weight_g=1000,
        current_filament_weight_g=0,
    )

    assert payload.current_filament_weight_g == Decimal("0")


def test_current_weight_defaults_to_initial_weight() -> None:
    payload = SpoolCreate(
        manufacturer_id=1,
        material_id=1,
        color_name="Black",
        initial_filament_weight_g=750,
    )

    assert payload.current_filament_weight_g == Decimal("750")


@pytest.mark.parametrize(
    ("initial_weight", "current_weight", "expected"),
    [
        (1000, 1000, 100.0),
        (1000, 500, 50.0),
        (1000, 0, 0.0),
        (1000, 742, 74.2),
        (750, 375, 50.0),
        (250, 50, 20.0),
        (1000, 333, 33.3),
    ],
)
def test_remaining_percent_is_derived_from_current_and_initial_weight(
    initial_weight: int,
    current_weight: int,
    expected: float,
) -> None:
    spool = Spool(
        initial_filament_weight_g=initial_weight,
        current_filament_weight_g=current_weight,
    )

    assert spool.remaining_percent == expected


def test_remaining_percent_is_dynamic_and_safe_for_legacy_zero_initial() -> None:
    spool = Spool(
        initial_filament_weight_g=1000,
        current_filament_weight_g=1000,
    )
    assert spool.remaining_percent == 100.0

    spool.current_filament_weight_g = Decimal("500")
    assert spool.remaining_percent == 50.0

    legacy_spool = Spool(
        initial_filament_weight_g=0,
        current_filament_weight_g=0,
    )
    assert legacy_spool.remaining_percent == 0.0


def test_empty_spool_weight_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        SpoolCreate(
            manufacturer_id=1,
            material_id=1,
            color_name="Black",
            initial_filament_weight_g=1000,
            empty_spool_weight_g=-1,
        )


def test_purchase_price_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        SpoolCreate(
            manufacturer_id=1,
            material_id=1,
            color_name="Black",
            initial_filament_weight_g=1000,
            purchase_price=-10,
        )


def test_color_hex_is_accepted_and_normalized() -> None:
    payload = SpoolCreate(
        manufacturer_id=1,
        material_id=1,
        color_name="Orange",
        color_hex="#ff6600",
        initial_filament_weight_g=1000,
    )

    assert payload.color_hex == "#FF6600"


@pytest.mark.parametrize("color_hex", ["orange", "#FFF"])
def test_invalid_color_hex_is_rejected(color_hex: str) -> None:
    with pytest.raises(ValidationError):
        SpoolCreate(
            manufacturer_id=1,
            material_id=1,
            color_name="Orange",
            color_hex=color_hex,
            initial_filament_weight_g=1000,
        )


def test_currency_is_normalized_to_uppercase() -> None:
    payload = SpoolCreate(
        manufacturer_id=1,
        material_id=1,
        color_name="Black",
        initial_filament_weight_g=1000,
        currency="eur",
    )

    assert payload.currency == "EUR"


def test_store_name_is_optional_and_trimmed() -> None:
    named = SpoolCreate(
        manufacturer_id=1,
        material_id=1,
        color_name="Black",
        initial_filament_weight_g=1000,
        store_name="  Filament World  ",
    )
    unnamed = SpoolCreate(
        manufacturer_id=1,
        material_id=1,
        color_name="Black",
        initial_filament_weight_g=1000,
    )

    assert named.store_name == "Filament World"
    assert unnamed.store_name is None


def test_inverted_temperature_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SpoolCreate(
            manufacturer_id=1,
            material_id=1,
            color_name="Black",
            initial_filament_weight_g=1000,
            nozzle_temp_min=250,
            nozzle_temp_max=200,
        )


def test_invalid_foreign_key_is_rejected_by_sqlite(
    db_session: Session,
    catalog_records: tuple[Manufacturer, Material],
) -> None:
    with pytest.raises(IntegrityError):
        create_spool(db_session, catalog_records, manufacturer_id=999_999)

    db_session.rollback()


def test_spool_orm_object_can_be_converted_to_read_schema(
    db_session: Session,
    catalog_records: tuple[Manufacturer, Material],
) -> None:
    spool = create_spool(
        db_session,
        catalog_records,
        current_filament_weight_g=742,
        status=SpoolStatus.OPEN,
    )
    db_session.commit()
    db_session.refresh(spool)

    result = SpoolRead.model_validate(spool)

    assert result.id == spool.id
    assert result.code == spool.code
    assert result.current_filament_weight_g == Decimal("742.000")
    assert result.remaining_percent == 74.2
    assert result.manufacturer.name == "eSUN"
    assert result.material.name == "PLA+"
    assert result.created_at.tzinfo is UTC
    assert result.updated_at.tzinfo is UTC
    assert result.model_dump(mode="json")["status"] == "OPEN"


def test_spool_create_and_update_protect_system_fields() -> None:
    with pytest.raises(ValidationError):
        SpoolCreate(
            manufacturer_id=1,
            material_id=1,
            color_name="Black",
            initial_filament_weight_g=1000,
            code="FIL-9999",
        )

    with pytest.raises(ValidationError):
        SpoolCreate(
            manufacturer_id=1,
            material_id=1,
            color_name="Black",
            initial_filament_weight_g=1000,
            remaining_percent=50,
        )

    with pytest.raises(ValidationError):
        SpoolUpdate(current_filament_weight_g=500)

    with pytest.raises(ValidationError):
        SpoolUpdate(remaining_percent=50)

    with pytest.raises(ValidationError):
        SpoolUpdate(id=1)
