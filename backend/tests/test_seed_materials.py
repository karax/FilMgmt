from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import Location, Manufacturer, Material, Spool
from app.scripts.seed_materials import (
    MATERIAL_SEED,
    MaterialSeedDefinition,
    seed_materials,
    validate_material_catalog,
)


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    factory = create_session_factory(engine)
    Base.metadata.create_all(engine)
    try:
        with factory() as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_catalog_is_valid_and_covers_required_technical_profiles() -> None:
    validate_material_catalog()
    names = {entry.name for entry in MATERIAL_SEED}
    required = {
        "PLA", "PLA+", "PLA-CF", "PLA-GF", "PLA Lightweight/Foaming",
        "PETG", "PETG-CF", "PETG-GF", "PETG FR/V0", "PETG ESD",
        "PCTG", "PCTG-CF", "ABS", "ABS-GF", "ABS ESD", "ABS FR/V0",
        "ASA", "ASA-CF", "TPU 60A", "TPU 85A", "TPU 95A", "TPU 98A",
        "PA6", "PA11", "PA12", "PA6-CF", "PA12-CF", "PAHT-CF", "PPA-CF",
        "PC", "PC-CF", "PC-ABS", "PC-PBT", "PP", "PP-CF", "PP-GF",
        "PPS", "PPS-CF", "PEEK", "PEKK", "PEI 9085", "PEI 1010", "PVDF",
        "PVC", "PVA", "BVOH", "PVB", "HIPS",
    }
    assert required <= names
    assert len(names) == len(MATERIAL_SEED)
    assert {entry.category for entry in MATERIAL_SEED} == {entry.category.upper() for entry in MATERIAL_SEED}


@pytest.mark.parametrize(
    "catalog",
    [
        (MaterialSeedDefinition("", "PLA"),),
        (MaterialSeedDefinition("PLA", "PLA"), MaterialSeedDefinition("pla", "PLA")),
        (MaterialSeedDefinition("PLA", "pla"),),
        (MaterialSeedDefinition("PLA", "PLA", default_nozzle_temp_min=501),),
        (MaterialSeedDefinition("PLA", "PLA", density_g_cm3=Decimal("0")),),
    ],
)
def test_catalog_validation_rejects_invalid_names_categories_and_defaults(
    catalog: tuple[MaterialSeedDefinition, ...],
) -> None:
    with pytest.raises(ValueError):
        validate_material_catalog(catalog)


def test_seed_populates_and_is_idempotent(db_session: Session) -> None:
    first = seed_materials(db_session)
    second = seed_materials(db_session)

    assert len(first.inserted) == len(MATERIAL_SEED)
    assert len(db_session.scalars(select(Material)).all()) == len(MATERIAL_SEED)
    assert second.inserted == ()
    assert len(second.existing) == len(MATERIAL_SEED)


def test_seed_preserves_custom_values_and_only_fills_null_defaults(db_session: Session) -> None:
    pla = Material(name="PLA", category="PLA", default_nozzle_temp_min=205)
    pa = Material(name="PA", category="PA")
    pa_custom = Material(name="PA6", category="PA", notes="User-maintained note")
    db_session.add_all([pla, pa, pa_custom])
    db_session.commit()

    result = seed_materials(db_session)

    assert pla.default_nozzle_temp_min == 205
    assert pa.notes == "Hygroscopic; drying is often recommended."
    assert pa_custom.notes == "User-maintained note"
    assert "PA" in result.defaults_updated
    # The custom nozzle minimum is preserved while the other missing
    # technical defaults are safely enriched.
    assert "PLA" in result.defaults_updated


def test_seed_preserves_existing_spool_relations(db_session: Session) -> None:
    material = Material(name="PLA", category="PLA")
    manufacturer = Manufacturer(name="eSUN")
    location = Location(name="Rack A")
    db_session.add_all([material, manufacturer, location])
    db_session.flush()
    spool = Spool(
        code="FIL-0001", manufacturer_id=manufacturer.id, material_id=material.id,
        location_id=location.id, color_name="Black",
        initial_filament_weight_g=Decimal("1000"), current_filament_weight_g=Decimal("1000"),
    )
    db_session.add(spool)
    db_session.commit()

    seed_materials(db_session)

    persisted = db_session.get(Spool, spool.id)
    assert persisted is not None
    assert persisted.material_id == material.id
