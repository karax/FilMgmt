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
from app.models import Manufacturer, Material, Spool
from app.services import add_spool_with_generated_code


@pytest.fixture
def api_environment(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_path = tmp_path / "manufacturer-api.db"
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


def create_manufacturer(
    client: TestClient,
    name: str,
    website: str | None = None,
) -> dict[str, object]:
    payload: dict[str, str] = {"name": name}
    if website is not None:
        payload["website"] = website

    response = client.post("/api/manufacturers", json=payload)
    assert response.status_code == 201
    return response.json()


def test_list_manufacturers_is_empty(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.get("/api/manufacturers")

    assert response.status_code == 200
    assert response.json() == []


def test_create_manufacturer(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment

    response = client.post(
        "/api/manufacturers",
        json={"name": "eSUN", "website": "https://www.esun3d.com"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "eSUN"
    assert body["website"] == "https://www.esun3d.com/"
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")
    with session_factory() as session:
        assert session.get(Manufacturer, body["id"]).name == "eSUN"


def test_create_manufacturer_without_website(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.post("/api/manufacturers", json={"name": "Generic"})

    assert response.status_code == 201
    assert response.json()["website"] is None


def test_create_manufacturer_rejects_invalid_payload(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    blank_name = client.post("/api/manufacturers", json={"name": "   "})
    extra_field = client.post(
        "/api/manufacturers",
        json={"name": "eSUN", "admin": True},
    )

    assert blank_name.status_code == 422
    assert extra_field.status_code == 422


def test_create_duplicate_manufacturer_returns_conflict(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    create_manufacturer(client, "eSUN")

    response = client.post("/api/manufacturers", json={"name": "eSUN"})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Manufacturer with this name already exists."
    }


def test_list_manufacturers_is_sorted_by_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    for name in ("SUNLU", "eSUN", "Polymaker"):
        create_manufacturer(client, name)

    response = client.get("/api/manufacturers")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == [
        "eSUN",
        "Polymaker",
        "SUNLU",
    ]


def test_get_manufacturer_by_id(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_manufacturer(client, "Polymaker")

    response = client.get(f"/api/manufacturers/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_manufacturer_returns_not_found(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.get("/api/manufacturers/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Manufacturer not found."}


def test_update_manufacturer_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    created = create_manufacturer(client, "Generic")

    response = client.put(
        f"/api/manufacturers/{created['id']}",
        json={"name": "Generic Filaments"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Generic Filaments"
    with session_factory() as session:
        manufacturer = session.get(Manufacturer, created["id"])
        assert manufacturer is not None
        assert manufacturer.name == "Generic Filaments"


def test_update_only_website_preserves_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_manufacturer(client, "Generic")

    response = client.put(
        f"/api/manufacturers/{created['id']}",
        json={"website": "https://generic.example"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Generic"
    assert response.json()["website"] == "https://generic.example/"


def test_update_to_duplicate_name_returns_conflict(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    create_manufacturer(client, "eSUN")
    polymaker = create_manufacturer(client, "Polymaker")

    response = client.put(
        f"/api/manufacturers/{polymaker['id']}",
        json={"name": "eSUN"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Manufacturer with this name already exists."
    }
    persisted = client.get(f"/api/manufacturers/{polymaker['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["name"] == "Polymaker"


def test_update_rejects_protected_or_null_name(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_manufacturer(client, "Generic")
    url = f"/api/manufacturers/{created['id']}"

    protected_field = client.put(url, json={"id": 999})
    null_name = client.put(url, json={"name": None})

    assert protected_field.status_code == 422
    assert null_name.status_code == 422


def test_update_unknown_manufacturer_returns_not_found(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.put(
        "/api/manufacturers/999999",
        json={"name": "Unknown"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Manufacturer not found."}


def test_delete_unused_manufacturer(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment
    created = create_manufacturer(client, "Unused")

    response = client.delete(f"/api/manufacturers/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    missing = client.get(f"/api/manufacturers/{created['id']}")
    assert missing.status_code == 404


def test_delete_manufacturer_in_use_returns_conflict_and_preserves_spool(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    created = create_manufacturer(client, "In Use")

    with session_factory() as session:
        material = Material(name="PLA", category="PLA")
        session.add(material)
        session.flush()
        spool = Spool(
            manufacturer_id=created["id"],
            material_id=material.id,
            color_name="Black",
            initial_filament_weight_g=1000,
            current_filament_weight_g=1000,
        )
        add_spool_with_generated_code(session, spool)
        session.commit()
        spool_id = spool.id

    response = client.delete(f"/api/manufacturers/{created['id']}")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Manufacturer is in use and cannot be deleted."
    }
    with session_factory() as session:
        assert session.get(Manufacturer, created["id"]) is not None
        assert session.get(Spool, spool_id) is not None


def test_delete_unknown_manufacturer_returns_not_found(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_environment

    response = client.delete("/api/manufacturers/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Manufacturer not found."}


def test_created_manufacturer_persists_across_requests_and_sessions(
    api_environment: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_environment
    created = create_manufacturer(client, "Persistent")

    list_response = client.get("/api/manufacturers")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [created["id"]]
    with session_factory() as session:
        persisted = session.scalar(
            select(Manufacturer).where(Manufacturer.id == created["id"])
        )
        assert persisted is not None
        assert persisted.name == "Persistent"
