from collections.abc import Iterator
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
from app.models import Location, Manufacturer, Material, Spool
from app.services import add_spool_with_generated_code


@pytest.fixture
def api_environment(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "location-api.db"
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


def create_location(
    client: TestClient,
    name: str,
    description: str | None = None,
) -> dict[str, object]:
    payload: dict[str, str] = {"name": name}
    if description is not None:
        payload["description"] = description

    response = client.post("/api/locations", json=payload)
    assert response.status_code == 201
    return response.json()


def test_list_locations_is_empty(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.get("/api/locations")

    assert response.status_code == 200
    assert response.json() == []


def test_create_complete_location(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment

    response = client.post(
        "/api/locations",
        json={
            "name": "Rack A / Slot 1",
            "description": "Primeiro slot.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "Rack A / Slot 1"
    assert body["description"] == "Primeiro slot."
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")
    with session_factory() as session:
        location = session.get(Location, body["id"])
        assert location is not None
        assert location.name == "Rack A / Slot 1"


def test_create_minimal_location(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.post("/api/locations", json={"name": "Dry Box"})

    assert response.status_code == 201
    assert response.json()["description"] is None


def test_create_duplicate_location_returns_conflict(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    create_location(client, "Dry Box")

    response = client.post("/api/locations", json={"name": "Dry Box"})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Location with this name already exists."
    }


def test_create_location_rejects_invalid_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.post("/api/locations", json={"name": "   "})

    assert response.status_code == 422


def test_create_location_rejects_extra_fields(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.post(
        "/api/locations",
        json={"name": "Dry Box", "hacked": True},
    )

    assert response.status_code == 422


def test_list_locations_is_sorted_by_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    for name in ("Shelf B", "Dry Box", "Rack A"):
        create_location(client, name)

    response = client.get("/api/locations")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == [
        "Dry Box",
        "Rack A",
        "Shelf B",
    ]


def test_get_location_by_id(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_location(client, "Dry Box")

    response = client.get(f"/api/locations/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_location_returns_not_found(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.get("/api/locations/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Location not found."}


def test_update_location_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    created = create_location(client, "Rack A")

    response = client.put(
        f"/api/locations/{created['id']}",
        json={"name": "Rack Principal"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Rack Principal"
    with session_factory() as session:
        location = session.get(Location, created["id"])
        assert location is not None
        assert location.name == "Rack Principal"


def test_update_only_description_preserves_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_location(client, "Rack A", "Descrição antiga.")

    response = client.put(
        f"/api/locations/{created['id']}",
        json={"description": "Rack principal ao lado da impressora."},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Rack A"
    assert response.json()["description"] == (
        "Rack principal ao lado da impressora."
    )


def test_update_to_duplicate_name_returns_conflict(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    create_location(client, "Dry Box")
    rack = create_location(client, "Rack A")

    response = client.put(
        f"/api/locations/{rack['id']}",
        json={"name": "Dry Box"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Location with this name already exists."
    }
    persisted = client.get(f"/api/locations/{rack['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["name"] == "Rack A"


def test_update_rejects_protected_or_null_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_location(client, "Dry Box")
    url = f"/api/locations/{created['id']}"

    protected_field = client.put(url, json={"id": 999})
    null_name = client.put(url, json={"name": None})

    assert protected_field.status_code == 422
    assert null_name.status_code == 422


def test_update_unknown_location_returns_not_found(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.put(
        "/api/locations/999999",
        json={"description": "Unknown"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Location not found."}


def test_delete_unused_location(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_location(client, "Unused")

    response = client.delete(f"/api/locations/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    missing = client.get(f"/api/locations/{created['id']}")
    assert missing.status_code == 404


def test_delete_location_in_use_returns_conflict_and_preserves_reference(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    created = create_location(client, "Rack A / Slot 1")

    with session_factory() as session:
        manufacturer = Manufacturer(name="eSUN")
        material = Material(name="PLA", category="PLA")
        session.add_all([manufacturer, material])
        session.flush()
        spool = Spool(
            manufacturer_id=manufacturer.id,
            material_id=material.id,
            location_id=created["id"],
            color_name="Black",
            initial_filament_weight_g=1000,
            current_filament_weight_g=1000,
        )
        add_spool_with_generated_code(session, spool)
        session.commit()
        spool_id = spool.id

    response = client.delete(f"/api/locations/{created['id']}")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Location is in use and cannot be deleted."
    }
    with session_factory() as session:
        persisted_spool = session.get(Spool, spool_id)
        assert session.get(Location, created["id"]) is not None
        assert persisted_spool is not None
        assert persisted_spool.location_id == created["id"]


def test_delete_unknown_location_returns_not_found(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.delete("/api/locations/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Location not found."}


def test_created_location_persists_across_requests_and_sessions(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    created = create_location(client, "Persistent")

    list_response = client.get("/api/locations")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [created["id"]]
    with session_factory() as session:
        persisted = session.scalar(
            select(Location).where(Location.id == created["id"])
        )
        assert persisted is not None
        assert persisted.name == "Persistent"
