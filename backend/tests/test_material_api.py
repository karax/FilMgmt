from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import (
    create_database_engine,
    create_session_factory,
    get_db,
)
from app.main import app
from app.models import Manufacturer, Material, Spool
from app.services import add_spool_with_generated_code


@pytest.fixture
def api_environment(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "material-api.db"
    engine = create_database_engine(
        f"sqlite+pysqlite:///{database_path.as_posix()}"
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, session_factory
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_material(
    client: TestClient,
    name: str,
    category: str = "OTHER",
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {"name": name, "category": category} | extra
    response = client.post("/api/materials", json=payload)
    assert response.status_code == 201
    return response.json()


def test_list_materials_is_empty(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.get("/api/materials")

    assert response.status_code == 200
    assert response.json() == []


def test_create_complete_material(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    payload = {
        "name": "PLA",
        "category": "PLA",
        "default_nozzle_temp_min": 190,
        "default_nozzle_temp_max": 220,
        "default_bed_temp_min": 0,
        "default_bed_temp_max": 60,
        "density_g_cm3": 1.24,
        "notes": "Material de uso geral.",
    }

    response = client.post("/api/materials", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "PLA"
    assert body["category"] == "PLA"
    assert body["default_nozzle_temp_min"] == 190
    assert body["default_nozzle_temp_max"] == 220
    assert Decimal(body["density_g_cm3"]) == Decimal("1.240")
    assert body["notes"] == "Material de uso geral."
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")
    with session_factory() as session:
        material = session.get(Material, body["id"])
        assert material is not None
        assert material.density_g_cm3 == Decimal("1.240")


def test_create_minimal_material(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.post(
        "/api/materials",
        json={"name": "Experimental", "category": "OTHER"},
    )

    assert response.status_code == 201
    assert response.json()["density_g_cm3"] is None
    assert response.json()["notes"] is None


def test_create_duplicate_material_returns_conflict(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    create_material(client, "PLA", "PLA")

    response = client.post(
        "/api/materials",
        json={"name": "PLA", "category": "PLA"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Material with this name already exists."
    }


def test_create_material_rejects_inverted_temperature_range(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.post(
        "/api/materials",
        json={
            "name": "Broken",
            "category": "OTHER",
            "default_nozzle_temp_min": 250,
            "default_nozzle_temp_max": 200,
        },
    )

    assert response.status_code == 422


def test_create_material_rejects_invalid_density(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.post(
        "/api/materials",
        json={"name": "Broken", "category": "OTHER", "density_g_cm3": -1},
    )

    assert response.status_code == 422


def test_create_material_rejects_extra_fields(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.post(
        "/api/materials",
        json={"name": "PLA", "category": "PLA", "hacked": True},
    )

    assert response.status_code == 422


def test_list_materials_is_sorted_by_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    for name in ("TPU", "PLA", "PETG"):
        create_material(client, name, name)

    response = client.get("/api/materials")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["PETG", "PLA", "TPU"]


def test_get_material_by_id(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_material(client, "PETG", "PETG")

    response = client.get(f"/api/materials/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_material_returns_not_found(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.get("/api/materials/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Material not found."}


def test_update_material_partially_and_preserve_other_fields(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    created = create_material(
        client,
        "PLA",
        "PLA",
        default_nozzle_temp_min=190,
        default_nozzle_temp_max=220,
        default_bed_temp_min=0,
        default_bed_temp_max=60,
        density_g_cm3=1.24,
        notes="General purpose.",
    )

    response = client.put(
        f"/api/materials/{created['id']}",
        json={
            "default_nozzle_temp_min": 200,
            "default_nozzle_temp_max": 230,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["default_nozzle_temp_min"] == 200
    assert body["default_nozzle_temp_max"] == 230
    assert body["name"] == "PLA"
    assert body["category"] == "PLA"
    assert body["default_bed_temp_min"] == 0
    assert body["default_bed_temp_max"] == 60
    assert Decimal(body["density_g_cm3"]) == Decimal("1.240")
    assert body["notes"] == "General purpose."
    with session_factory() as session:
        material = session.get(Material, created["id"])
        assert material is not None
        assert material.default_nozzle_temp_min == 200


def test_partial_update_validates_result_against_persisted_range(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_material(
        client,
        "PLA",
        "PLA",
        default_nozzle_temp_min=190,
        default_nozzle_temp_max=220,
    )

    response = client.put(
        f"/api/materials/{created['id']}",
        json={"default_nozzle_temp_min": 230},
    )

    assert response.status_code == 422
    persisted = client.get(f"/api/materials/{created['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["default_nozzle_temp_min"] == 190
    assert persisted.json()["default_nozzle_temp_max"] == 220


def test_update_to_duplicate_name_returns_conflict(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    create_material(client, "PLA", "PLA")
    petg = create_material(client, "PETG", "PETG")

    response = client.put(
        f"/api/materials/{petg['id']}",
        json={"name": "PLA"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Material with this name already exists."
    }
    persisted = client.get(f"/api/materials/{petg['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["name"] == "PETG"


def test_category_is_normalized_in_response_and_database(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment

    response = client.post(
        "/api/materials",
        json={"name": "Silk PLA", "category": "  pla  "},
    )

    assert response.status_code == 201
    assert response.json()["category"] == "PLA"
    with session_factory() as session:
        material = session.get(Material, response.json()["id"])
        assert material is not None
        assert material.category == "PLA"


def test_update_rejects_protected_and_null_required_fields(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_material(client, "PLA", "PLA")
    url = f"/api/materials/{created['id']}"

    protected_field = client.put(url, json={"id": 999})
    null_name = client.put(url, json={"name": None})
    null_category = client.put(url, json={"category": None})

    assert protected_field.status_code == 422
    assert null_name.status_code == 422
    assert null_category.status_code == 422


def test_update_unknown_material_returns_not_found(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.put(
        "/api/materials/999999",
        json={"notes": "Unknown"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Material not found."}


def test_delete_unused_material(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_material(client, "Unused")

    response = client.delete(f"/api/materials/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    missing = client.get(f"/api/materials/{created['id']}")
    assert missing.status_code == 404


def test_delete_material_in_use_returns_conflict_and_preserves_spool(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    created = create_material(client, "PLA", "PLA")

    with session_factory() as session:
        manufacturer = Manufacturer(name="eSUN")
        session.add(manufacturer)
        session.flush()
        spool = Spool(
            manufacturer_id=manufacturer.id,
            material_id=created["id"],
            color_name="Black",
            initial_filament_weight_g=1000,
            current_filament_weight_g=1000,
        )
        add_spool_with_generated_code(session, spool)
        session.commit()
        spool_id = spool.id

    response = client.delete(f"/api/materials/{created['id']}")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Material is in use and cannot be deleted."
    }
    with session_factory() as session:
        assert session.get(Material, created["id"]) is not None
        assert session.get(Spool, spool_id) is not None


def test_delete_unknown_material_returns_not_found(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.delete("/api/materials/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Material not found."}


def test_created_material_persists_across_requests_and_sessions(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    created = create_material(client, "Persistent")

    list_response = client.get("/api/materials")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [created["id"]]
    with session_factory() as session:
        persisted = session.scalar(
            select(Material).where(Material.id == created["id"])
        )
        assert persisted is not None
        assert persisted.name == "Persistent"
