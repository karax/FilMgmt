from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import (
    create_database_engine,
    create_session_factory,
    get_db,
)
from app.main import app
from app.models import Manufacturer, Material, Spool, WeightHistory


@dataclass(frozen=True)
class ApiEnvironment:
    client: TestClient
    session_factory: sessionmaker[Session]
    engine: Engine
    manufacturer_id: int
    material_id: int


@pytest.fixture
def api_environment(tmp_path: Path) -> Iterator[ApiEnvironment]:
    database_path = tmp_path / "spool-api.db"
    engine = create_database_engine(
        f"sqlite+pysqlite:///{database_path.as_posix()}"
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        manufacturer = Manufacturer(name="eSUN")
        material = Material(name="PLA+", category="PLA")
        session.add_all([manufacturer, material])
        session.commit()
        manufacturer_id = manufacturer.id
        material_id = material.id

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield ApiEnvironment(
                client=client,
                session_factory=session_factory,
                engine=engine,
                manufacturer_id=manufacturer_id,
                material_id=material_id,
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def valid_spool_payload(
    environment: ApiEnvironment,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "manufacturer_id": environment.manufacturer_id,
        "material_id": environment.material_id,
        "product_name": "PLA+ HS",
        "color_name": "Black",
        "color_hex": "#000000",
        "diameter_mm": 1.75,
        "initial_filament_weight_g": 1000,
        "current_filament_weight_g": 800,
        "empty_spool_weight_g": 244,
        "purchase_price": 21.99,
        "currency": "EUR",
        "status": "OPEN",
        "needs_drying": False,
    }
    payload.update(overrides)
    return payload


def create_spool(
    environment: ApiEnvironment,
    **overrides: object,
) -> dict[str, object]:
    response = environment.client.post(
        "/api/spools",
        json=valid_spool_payload(environment, **overrides),
    )
    assert response.status_code == 201
    return response.json()


def test_list_spools_is_empty(api_environment: ApiEnvironment) -> None:
    response = api_environment.client.get("/api/spools")

    assert response.status_code == 200
    assert response.json() == []


def test_spool_openapi_exposes_optional_names(api_environment: ApiEnvironment) -> None:
    response = api_environment.client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    for schema_name in ("SpoolCreate", "SpoolUpdate", "SpoolRead"):
        assert "display_name" in schemas[schema_name]["properties"]
        assert "store_name" in schemas[schema_name]["properties"]
        assert "location_id" not in schemas[schema_name]["properties"]


def test_create_basic_spool_with_automatic_code(
    api_environment: ApiEnvironment,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(api_environment),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["code"] == f"FIL-{body['id']:04d}"
    assert re.fullmatch(r"FIL-[0-9]{4,}", body["code"])
    assert body["manufacturer_id"] == api_environment.manufacturer_id
    assert body["material_id"] == api_environment.material_id
    assert body["remaining_percent"] == 80.0


def test_current_weight_defaults_to_initial_weight(
    api_environment: ApiEnvironment,
) -> None:
    payload = valid_spool_payload(api_environment)
    payload.pop("current_filament_weight_g")

    response = api_environment.client.post("/api/spools", json=payload)

    assert response.status_code == 201
    assert Decimal(response.json()["current_filament_weight_g"]) == Decimal(
        "1000.000"
    )
    assert response.json()["remaining_percent"] == 100.0


def test_create_recalculates_automatically_managed_status(
    api_environment: ApiEnvironment,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(
            api_environment,
            current_filament_weight_g=150,
            status="OPEN",
        ),
    )

    assert response.status_code == 201
    assert response.json()["remaining_percent"] == 15.0
    assert response.json()["status"] == "LOW"


@pytest.mark.parametrize("status", ["SEALED", "IN_USE", "NEEDS_DRYING"])
def test_create_preserves_special_status_with_positive_weight(
    api_environment: ApiEnvironment,
    status: str,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(
            api_environment,
            current_filament_weight_g=100,
            status=status,
            needs_drying=status == "NEEDS_DRYING",
        ),
    )

    assert response.status_code == 201
    assert response.json()["status"] == status


def test_create_rejects_unknown_manufacturer(
    api_environment: ApiEnvironment,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(api_environment, manufacturer_id=999_999),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Manufacturer not found."}


def test_create_rejects_unknown_material(api_environment: ApiEnvironment) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(api_environment, material_id=999_999),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Material not found."}


def test_create_rejects_current_weight_above_initial(
    api_environment: ApiEnvironment,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(
            api_environment,
            initial_filament_weight_g=1000,
            current_filament_weight_g=1200,
        ),
    )

    assert response.status_code == 422


def test_create_accepts_maximum_filament_weights(
    api_environment: ApiEnvironment,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(
            api_environment,
            initial_filament_weight_g=2000,
            current_filament_weight_g=2000,
        ),
    )

    assert response.status_code == 201
    assert Decimal(response.json()["initial_filament_weight_g"]) == 2000
    assert Decimal(response.json()["current_filament_weight_g"]) == 2000


@pytest.mark.parametrize("initial_weight", [2000.01, 2500])
def test_create_rejects_initial_filament_weight_above_limit(
    api_environment: ApiEnvironment,
    initial_weight: float,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(
            api_environment,
            initial_filament_weight_g=initial_weight,
        ),
    )

    assert response.status_code == 422
    issue = response.json()["detail"][0]
    assert issue["loc"] == ["body", "initial_filament_weight_g"]
    assert "Filament weight cannot exceed 2000 g." in issue["msg"]


def test_create_rejects_current_filament_weight_above_limit(
    api_environment: ApiEnvironment,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(
            api_environment,
            initial_filament_weight_g=2000,
            current_filament_weight_g=2000.01,
        ),
    )

    assert response.status_code == 422
    issue = response.json()["detail"][0]
    assert issue["loc"] == ["body", "current_filament_weight_g"]
    assert "Filament weight cannot exceed 2000 g." in issue["msg"]


@pytest.mark.parametrize("purchase_price", [None, 0, 100])
def test_create_accepts_purchase_price_at_or_below_limit(
    api_environment: ApiEnvironment,
    purchase_price: float | None,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(
            api_environment,
            purchase_price=purchase_price,
        ),
    )

    assert response.status_code == 201
    actual = response.json()["purchase_price"]
    if purchase_price is None:
        assert actual is None
    else:
        assert Decimal(actual) == Decimal(str(purchase_price))


@pytest.mark.parametrize("purchase_price", [-1, 100.01, 150])
def test_create_rejects_purchase_price_outside_range(
    api_environment: ApiEnvironment,
    purchase_price: float,
) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(
            api_environment,
            purchase_price=purchase_price,
        ),
    )

    assert response.status_code == 422
    issue = response.json()["detail"][0]
    assert issue["loc"] == ["body", "purchase_price"]
    if purchase_price > 100:
        assert "Purchase price cannot exceed 100." in issue["msg"]


def test_create_rejects_invalid_color(api_environment: ApiEnvironment) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(api_environment, color_hex="black"),
    )

    assert response.status_code == 422


def test_response_serializes_all_relationships(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.get(f"/api/spools/{spool['code']}")

    assert response.status_code == 200
    body = response.json()
    assert body["manufacturer"]["name"] == "eSUN"
    assert body["material"]["name"] == "PLA+"
    assert body["remaining_percent"] == 80.0


def test_existing_price_above_new_write_limit_remains_readable(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)
    with api_environment.session_factory() as session:
        persisted = session.get(Spool, spool["id"])
        assert persisted is not None
        persisted.purchase_price = Decimal("1000000")
        session.commit()

    response = api_environment.client.get(f"/api/spools/{spool['code']}")

    assert response.status_code == 200
    assert Decimal(response.json()["purchase_price"]) == Decimal("1000000")


def test_get_spool_by_code_is_case_insensitive(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.get(
        f"/api/spools/{str(spool['code']).lower()}"
    )

    assert response.status_code == 200
    assert response.json()["code"] == spool["code"]


def test_get_unknown_spool_returns_not_found(
    api_environment: ApiEnvironment,
) -> None:
    response = api_environment.client.get("/api/spools/FIL-999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Spool not found."}


def test_update_color_name_preserves_code(api_environment: ApiEnvironment) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"color_name": "Galaxy Purple"},
    )

    assert response.status_code == 200
    assert response.json()["color_name"] == "Galaxy Purple"
    assert response.json()["code"] == spool["code"]


def test_create_normalizes_optional_display_name(api_environment: ApiEnvironment) -> None:
    created = create_spool(
        api_environment,
        display_name="  PLA Preto Principal  ",
    )
    unnamed = create_spool(api_environment, display_name="   ")

    assert created["display_name"] == "PLA Preto Principal"
    assert unnamed["display_name"] is None


def test_create_and_read_optional_store_name(
    api_environment: ApiEnvironment,
) -> None:
    purchased = create_spool(api_environment, store_name="  Filament World  ")
    unspecified = create_spool(api_environment)

    response = api_environment.client.get(
        f"/api/spools/{purchased['code']}"
    )

    assert purchased["store_name"] == "Filament World"
    assert unspecified["store_name"] is None
    assert response.status_code == 200
    assert response.json()["store_name"] == "Filament World"


def test_patch_updates_and_clears_store_name(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    updated = api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"store_name": "  Local Filaments  "},
    )
    cleared = api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"store_name": "   "},
    )

    assert updated.status_code == 200
    assert updated.json()["store_name"] == "Local Filaments"
    assert cleared.status_code == 200
    assert cleared.json()["store_name"] is None


def test_display_names_can_repeat_and_be_updated_or_cleared(
    api_environment: ApiEnvironment,
) -> None:
    first = create_spool(api_environment, display_name="PLA Preto")
    second = create_spool(api_environment, display_name="PLA Preto")

    changed = api_environment.client.patch(
        f"/api/spools/{first['code']}",
        json={"display_name": "PLA Preto Reserva"},
    )
    cleared = api_environment.client.patch(
        f"/api/spools/{second['code']}",
        json={"display_name": None},
    )

    assert changed.status_code == 200
    assert changed.json()["display_name"] == "PLA Preto Reserva"
    assert changed.json()["code"] == first["code"]
    assert cleared.status_code == 200
    assert cleared.json()["display_name"] is None


def test_patch_updates_spool_without_exposing_read_only_fields(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"color_name": "Galaxy Purple"},
    )

    assert response.status_code == 200
    assert response.json()["color_name"] == "Galaxy Purple"
    assert response.json()["current_filament_weight_g"] == spool["current_filament_weight_g"]


@pytest.mark.parametrize(
    ("field", "detail"),
    [
        ("manufacturer_id", "Manufacturer not found."),
        ("material_id", "Material not found."),
    ],
)
def test_update_rejects_unknown_catalog_reference(
    api_environment: ApiEnvironment,
    field: str,
    detail: str,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={field: 999_999},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": detail}


def test_update_rejects_initial_weight_below_persisted_current(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(
        api_environment,
        initial_filament_weight_g=1000,
        current_filament_weight_g=800,
    )

    response = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"initial_filament_weight_g": 500},
    )

    assert response.status_code == 422
    persisted = api_environment.client.get(f"/api/spools/{spool['code']}")
    assert Decimal(persisted.json()["initial_filament_weight_g"]) == Decimal(
        "1000.000"
    )
    assert Decimal(persisted.json()["current_filament_weight_g"]) == Decimal(
        "800.000"
    )


def test_patch_accepts_consistent_initial_weight_below_limit(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(
        api_environment,
        initial_filament_weight_g=2000,
        current_filament_weight_g=1000,
    )

    response = api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"initial_filament_weight_g": 1999},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["initial_filament_weight_g"]) == 1999


def test_patch_rejects_initial_weight_above_limit(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"initial_filament_weight_g": 2001},
    )

    assert response.status_code == 422
    issue = response.json()["detail"][0]
    assert issue["loc"] == ["body", "initial_filament_weight_g"]
    assert "Filament weight cannot exceed 2000 g." in issue["msg"]


def test_patch_accepts_purchase_price_below_limit(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"purchase_price": 99.99},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["purchase_price"]) == Decimal("99.99")


def test_patch_rejects_purchase_price_above_limit(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"purchase_price": 101},
    )

    assert response.status_code == 422
    issue = response.json()["detail"][0]
    assert issue["loc"] == ["body", "purchase_price"]
    assert "Purchase price cannot exceed 100." in issue["msg"]


def test_update_initial_weight_recalculates_managed_status(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(
        api_environment,
        initial_filament_weight_g=1000,
        current_filament_weight_g=250,
        status="OPEN",
    )
    assert spool["status"] == "OPEN"

    response = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"initial_filament_weight_g": 1250},
    )

    assert response.status_code == 200
    assert response.json()["remaining_percent"] == 20.0
    assert response.json()["status"] == "LOW"


def test_partial_update_validates_persisted_temperature_range(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(
        api_environment,
        nozzle_temp_min=190,
        nozzle_temp_max=220,
    )

    response = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"nozzle_temp_min": 230},
    )

    assert response.status_code == 422
    persisted = api_environment.client.get(f"/api/spools/{spool['code']}")
    assert persisted.json()["nozzle_temp_min"] == 190
    assert persisted.json()["nozzle_temp_max"] == 220


def test_archive_sets_status_and_timestamp(api_environment: ApiEnvironment) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.post(
        f"/api/spools/{spool['code']}/archive"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"
    assert response.json()["archived_at"].endswith("Z")


def test_archived_spool_is_hidden_from_list_but_available_by_code(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)
    archive = api_environment.client.post(
        f"/api/spools/{spool['code']}/archive"
    )
    assert archive.status_code == 200

    listed = api_environment.client.get("/api/spools")
    fetched = api_environment.client.get(f"/api/spools/{spool['code']}")

    assert listed.status_code == 200
    assert listed.json() == []
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "ARCHIVED"


def test_archive_is_idempotent_and_preserves_timestamp(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    first = api_environment.client.post(f"/api/spools/{spool['code']}/archive")
    second = api_environment.client.post(f"/api/spools/{spool['code']}/archive")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["archived_at"] == first.json()["archived_at"]


def test_archive_unknown_spool_returns_not_found(
    api_environment: ApiEnvironment,
) -> None:
    response = api_environment.client.post("/api/spools/FIL-999999/archive")

    assert response.status_code == 404
    assert response.json() == {"detail": "Spool not found."}


def test_archive_in_use_spool_returns_conflict(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment, status="IN_USE")

    response = api_environment.client.post(f"/api/spools/{spool['code']}/archive")

    assert response.status_code == 409
    assert response.json() == {"detail": "Spool in use cannot be archived."}
    assert api_environment.client.get(f"/api/spools/{spool['code']}").json()["status"] == "IN_USE"


def test_delete_active_spool_requires_archive(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.delete(f"/api/spools/{spool['code']}")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Spool must be archived before deletion."
    }
    assert api_environment.client.get(
        f"/api/spools/{spool['code']}"
    ).status_code == 200


def test_delete_archived_spool(api_environment: ApiEnvironment) -> None:
    spool = create_spool(api_environment)
    archive = api_environment.client.post(
        f"/api/spools/{spool['code']}/archive"
    )
    assert archive.status_code == 200

    response = api_environment.client.delete(f"/api/spools/{spool['code']}")

    assert response.status_code == 204
    assert response.content == b""
    assert api_environment.client.get(
        f"/api/spools/{spool['code']}"
    ).status_code == 404


def test_delete_unknown_spool_returns_not_found(
    api_environment: ApiEnvironment,
) -> None:
    response = api_environment.client.delete("/api/spools/FIL-999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Spool not found."}


def test_list_spools_is_ordered_by_code(api_environment: ApiEnvironment) -> None:
    created = [
        create_spool(api_environment, color_name=color)
        for color in ("Black", "Orange", "White")
    ]

    response = api_environment.client.get("/api/spools")

    assert response.status_code == 200
    assert [item["code"] for item in response.json()] == sorted(
        item["code"] for item in created
    )


def test_list_eager_loads_relationships_in_one_query(
    api_environment: ApiEnvironment,
) -> None:
    create_spool(api_environment)
    statements: list[str] = []

    def record_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        statements.append(statement)

    event.listen(api_environment.engine, "before_cursor_execute", record_statement)
    try:
        response = api_environment.client.get("/api/spools")
    finally:
        event.remove(
            api_environment.engine,
            "before_cursor_execute",
            record_statement,
        )

    assert response.status_code == 200
    assert response.json()[0]["manufacturer"]["name"] == "eSUN"
    assert len(statements) == 1


def test_create_and_update_reject_protected_fields(
    api_environment: ApiEnvironment,
) -> None:
    create_response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(api_environment, code="FIL-9999"),
    )
    create_percent = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(api_environment, remaining_percent=20),
    )
    spool = create_spool(api_environment)
    update_code = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"code": "FIL-9999"},
    )
    update_archive_timestamp = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"archived_at": "2026-01-01T00:00:00Z"},
    )
    update_percent = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"remaining_percent": 20},
    )
    update_status = api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"status": "EMPTY"},
    )
    update_operational_time = api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"last_used_at": "2026-01-01T00:00:00Z"},
    )

    assert create_response.status_code == 422
    assert create_percent.status_code == 422
    assert update_code.status_code == 422
    assert update_archive_timestamp.status_code == 422
    assert update_percent.status_code == 422
    assert update_status.status_code == 422
    assert update_operational_time.status_code == 422


def test_update_rejects_null_for_required_fields(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"current_filament_weight_g": None},
    )

    assert response.status_code == 422


def test_currency_and_color_are_normalized(api_environment: ApiEnvironment) -> None:
    response = api_environment.client.post(
        "/api/spools",
        json=valid_spool_payload(
            api_environment,
            currency="eur",
            color_hex="#ff6600",
        ),
    )

    assert response.status_code == 201
    assert response.json()["currency"] == "EUR"
    assert response.json()["color_hex"] == "#FF6600"


def test_generic_weight_update_is_rejected_for_task_017(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    response = api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"current_filament_weight_g": 742},
    )

    assert response.status_code == 422
    with api_environment.session_factory() as session:
        persisted = session.scalar(
            select(Spool).where(Spool.code == spool["code"])
        )
        assert persisted is not None
        assert persisted.current_filament_weight_g == Decimal("800.000")
        assert session.scalars(select(WeightHistory)).all() == []


def test_create_archived_spool_sets_timestamp_and_hides_it(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment, status="ARCHIVED")

    assert spool["status"] == "ARCHIVED"
    assert spool["archived_at"] is not None
    assert api_environment.client.get("/api/spools").json() == []


def test_created_spool_persists_across_requests_and_sessions(
    api_environment: ApiEnvironment,
) -> None:
    spool = create_spool(api_environment)

    fetched = api_environment.client.get(f"/api/spools/{spool['code']}")

    assert fetched.status_code == 200
    with api_environment.session_factory() as session:
        persisted = session.scalar(
            select(Spool).where(Spool.code == spool["code"])
        )
        assert persisted is not None
        assert persisted.code == spool["code"]


@dataclass(frozen=True)
class FilterDataset:
    spools: dict[str, dict[str, object]]
    manufacturer_ids: dict[str, int]
    material_ids: dict[str, int]


@pytest.fixture
def filter_dataset(api_environment: ApiEnvironment) -> FilterDataset:
    with api_environment.session_factory() as session:
        sunlu = Manufacturer(name="SUNLU")
        polymaker = Manufacturer(name="Polymaker")
        petg = Material(name="PETG", category="PETG")
        tpu = Material(name="TPU", category="TPU")
        session.add_all([sunlu, polymaker, petg, tpu])
        session.commit()
        manufacturer_ids = {
            "esun": api_environment.manufacturer_id,
            "sunlu": sunlu.id,
            "polymaker": polymaker.id,
        }
        material_ids = {
            "pla": api_environment.material_id,
            "petg": petg.id,
            "tpu": tpu.id,
        }

    spools = {
        "esun_pla": create_spool(
            api_environment,
            manufacturer_id=manufacturer_ids["esun"],
            material_id=material_ids["pla"],
            color_name="Black",
            initial_filament_weight_g=1000,
            current_filament_weight_g=800,
            status="OPEN",
            needs_drying=False,
        ),
        "sunlu_pla": create_spool(
            api_environment,
            manufacturer_id=manufacturer_ids["sunlu"],
            material_id=material_ids["pla"],
            color_name="Orange",
            initial_filament_weight_g=1000,
            current_filament_weight_g=150,
            status="OPEN",
            needs_drying=False,
        ),
        "polymaker_petg": create_spool(
            api_environment,
            manufacturer_id=manufacturer_ids["polymaker"],
            material_id=material_ids["petg"],
            color_name="White",
            initial_filament_weight_g=1000,
            current_filament_weight_g=1000,
            status="SEALED",
            needs_drying=False,
        ),
        "esun_tpu": create_spool(
            api_environment,
            manufacturer_id=manufacturer_ids["esun"],
            material_id=material_ids["tpu"],
            color_name="Blue",
            initial_filament_weight_g=500,
            current_filament_weight_g=300,
            status="NEEDS_DRYING",
            needs_drying=True,
        ),
    }
    return FilterDataset(
        spools=spools,
        manufacturer_ids=manufacturer_ids,
        material_ids=material_ids,
    )


def response_codes(response: Response) -> list[str]:
    assert response.status_code == 200
    return [item["code"] for item in response.json()]


def expected_codes(
    dataset: FilterDataset,
    *keys: str,
) -> list[str]:
    return sorted(str(dataset.spools[key]["code"]) for key in keys)


def test_filters_no_parameters_preserve_default_list(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get("/api/spools")

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "esun_pla",
        "sunlu_pla",
        "polymaker_petg",
        "esun_tpu",
    )


def test_filter_by_manufacturer_id(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"manufacturer_id": filter_dataset.manufacturer_ids["esun"]},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "esun_pla",
        "esun_tpu",
    )


def test_filter_by_material_id(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"material_id": filter_dataset.material_ids["pla"]},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "esun_pla",
        "sunlu_pla",
    )


def test_filter_by_status(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"status": "OPEN"},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "esun_pla",
    )


def test_filter_by_automatically_assigned_low_status(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"status": "LOW"},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "sunlu_pla",
    )


def test_filter_rejects_invalid_status(api_environment: ApiEnvironment) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"status": "BROKEN"},
    )

    assert response.status_code == 422


def test_filter_by_needs_drying_true(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"needs_drying": "true"},
    )

    assert response_codes(response) == expected_codes(filter_dataset, "esun_tpu")


def test_filter_by_needs_drying_false(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"needs_drying": "false"},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "esun_pla",
        "sunlu_pla",
        "polymaker_petg",
    )


def test_filter_by_minimum_weight(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"min_weight_g": 800},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "esun_pla",
        "polymaker_petg",
    )


def test_filter_by_maximum_weight(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"max_weight_g": 300},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "sunlu_pla",
        "esun_tpu",
    )


def test_filter_by_weight_range(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"min_weight_g": 200, "max_weight_g": 800},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "esun_pla",
        "esun_tpu",
    )


@pytest.mark.parametrize(
    "params",
    [
        {"min_weight_g": -1},
        {"max_weight_g": -1},
        {"min_weight_g": 800, "max_weight_g": 200},
    ],
)
def test_filter_rejects_invalid_weight_range(
    api_environment: ApiEnvironment,
    params: dict[str, int],
) -> None:
    response = api_environment.client.get("/api/spools", params=params)

    assert response.status_code == 422


def test_filter_by_maximum_remaining_percent(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"max_remaining_percent": 20},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "sunlu_pla",
    )
    assert response.json()[0]["remaining_percent"] == 15.0


def test_filter_by_minimum_remaining_percent(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"min_remaining_percent": 80},
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "esun_pla",
        "polymaker_petg",
    )


def test_filter_by_remaining_percent_range(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"min_remaining_percent": 20, "max_remaining_percent": 60},
    )

    assert response_codes(response) == expected_codes(filter_dataset, "esun_tpu")


@pytest.mark.parametrize(
    "params",
    [
        {"min_remaining_percent": -1},
        {"max_remaining_percent": 101},
        {"min_remaining_percent": 80, "max_remaining_percent": 20},
    ],
)
def test_filter_rejects_invalid_remaining_percent_range(
    api_environment: ApiEnvironment,
    params: dict[str, int],
) -> None:
    response = api_environment.client.get("/api/spools", params=params)

    assert response.status_code == 422


def test_filters_are_combined_with_and(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={
            "manufacturer_id": filter_dataset.manufacturer_ids["esun"],
            "material_id": filter_dataset.material_ids["pla"],
            "status": "OPEN",
            "needs_drying": "false",
            "max_remaining_percent": 90,
        },
    )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "esun_pla",
    )


def test_filter_with_unknown_foreign_key_returns_empty_list(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"manufacturer_id": 999_999},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_archived_spools_remain_hidden_by_default(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    archived = filter_dataset.spools["sunlu_pla"]
    response = api_environment.client.post(
        f"/api/spools/{archived['code']}/archive"
    )
    assert response.status_code == 200

    listed = api_environment.client.get("/api/spools")

    assert response_codes(listed) == expected_codes(
        filter_dataset,
        "esun_pla",
        "polymaker_petg",
        "esun_tpu",
    )


def test_include_archived_returns_active_and_archived_spools(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    archived = filter_dataset.spools["sunlu_pla"]
    response = api_environment.client.post(
        f"/api/spools/{archived['code']}/archive"
    )
    assert response.status_code == 200

    listed = api_environment.client.get(
        "/api/spools",
        params={"include_archived": "true"},
    )

    assert response_codes(listed) == expected_codes(
        filter_dataset,
        "esun_pla",
        "sunlu_pla",
        "polymaker_petg",
        "esun_tpu",
    )


def test_archived_status_implies_explicit_archive_intent(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    archived = filter_dataset.spools["sunlu_pla"]
    response = api_environment.client.post(
        f"/api/spools/{archived['code']}/archive"
    )
    assert response.status_code == 200

    listed = api_environment.client.get(
        "/api/spools",
        params={"status": "ARCHIVED"},
    )

    assert response_codes(listed) == expected_codes(
        filter_dataset,
        "sunlu_pla",
    )


def test_filtered_response_keeps_relationships_loaded(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"material_id": filter_dataset.material_ids["petg"]},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    body = response.json()[0]
    assert body["manufacturer"]["name"] == "Polymaker"
    assert body["material"]["name"] == "PETG"


def test_remaining_percent_filter_is_executed_in_single_sql_query(
    api_environment: ApiEnvironment,
    filter_dataset: FilterDataset,
) -> None:
    statements: list[str] = []

    def record_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        statements.append(statement)

    event.listen(api_environment.engine, "before_cursor_execute", record_statement)
    try:
        response = api_environment.client.get(
            "/api/spools",
            params={"max_remaining_percent": 20},
        )
    finally:
        event.remove(
            api_environment.engine,
            "before_cursor_execute",
            record_statement,
        )

    assert response_codes(response) == expected_codes(
        filter_dataset,
        "sunlu_pla",
    )
    assert len(statements) == 1
    assert "spools.current_filament_weight_g *" in statements[0]
    assert "spools.initial_filament_weight_g" in statements[0]


@dataclass(frozen=True)
class SearchDataset:
    spools: dict[str, dict[str, object]]
    manufacturer_ids: dict[str, int]
    material_ids: dict[str, int]


@pytest.fixture
def search_dataset(api_environment: ApiEnvironment) -> SearchDataset:
    with api_environment.session_factory() as session:
        polymaker = Manufacturer(name="Polymaker")
        sunlu = Manufacturer(name="SUNLU")
        petg = Material(name="PETG", category="PETG")
        tpu = Material(name="TPU", category="TPU")
        session.add_all([polymaker, sunlu, petg, tpu])
        session.commit()
        manufacturer_ids = {
            "esun": api_environment.manufacturer_id,
            "polymaker": polymaker.id,
            "sunlu": sunlu.id,
        }
        material_ids = {
            "pla": api_environment.material_id,
            "petg": petg.id,
            "tpu": tpu.id,
        }

    spools = {
        "esun_pla": create_spool(
            api_environment,
            manufacturer_id=manufacturer_ids["esun"],
            material_id=material_ids["pla"],
            product_name="PLA+ High Speed",
            color_name="Black",
            initial_filament_weight_g=1000,
            current_filament_weight_g=180,
            status="OPEN",
            needs_drying=False,
        ),
        "polymaker_petg": create_spool(
            api_environment,
            manufacturer_id=manufacturer_ids["polymaker"],
            material_id=material_ids["petg"],
            product_name="PolyLite PETG",
            color_name="Orange",
            initial_filament_weight_g=1000,
            current_filament_weight_g=600,
            status="OPEN",
            needs_drying=False,
        ),
        "sunlu_tpu": create_spool(
            api_environment,
            manufacturer_id=manufacturer_ids["sunlu"],
            material_id=material_ids["tpu"],
            product_name="Flexible TPU",
            color_name="Galaxy Black",
            initial_filament_weight_g=500,
            current_filament_weight_g=100,
            status="NEEDS_DRYING",
            needs_drying=True,
        ),
    }
    return SearchDataset(
        spools=spools,
        manufacturer_ids=manufacturer_ids,
        material_ids=material_ids,
    )


def test_search_by_full_code(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    spool = search_dataset.spools["esun_pla"]

    response = api_environment.client.get(
        "/api/spools",
        params={"search": spool["code"]},
    )

    assert response_codes(response) == [spool["code"]]


def test_search_by_partial_code(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    spool = search_dataset.spools["esun_pla"]
    partial_code = str(spool["code"]).removeprefix("FIL-")

    response = api_environment.client.get(
        "/api/spools",
        params={"search": partial_code},
    )

    assert response_codes(response) == [spool["code"]]


def test_search_code_is_case_insensitive(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    spool = search_dataset.spools["esun_pla"]

    response = api_environment.client.get(
        "/api/spools",
        params={"search": str(spool["code"]).lower()},
    )

    assert response_codes(response) == [spool["code"]]


def test_search_by_color_returns_all_partial_matches(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "black"},
    )

    assert response_codes(response) == expected_codes(
        search_dataset,
        "esun_pla",
        "sunlu_tpu",
    )


def test_search_by_partial_color(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "galaxy"},
    )

    assert response_codes(response) == expected_codes(search_dataset, "sunlu_tpu")


def test_search_by_product_name(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "High Speed"},
    )

    assert response_codes(response) == expected_codes(search_dataset, "esun_pla")


def test_search_by_partial_product_name(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "lite"},
    )

    assert response_codes(response) == expected_codes(
        search_dataset,
        "polymaker_petg",
    )


@pytest.mark.parametrize("search", ["principal", "PRETO PRINCIPAL"])
def test_search_by_display_name_is_case_insensitive(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
    search: str,
) -> None:
    spool = search_dataset.spools["esun_pla"]
    api_environment.client.patch(
        f"/api/spools/{spool['code']}",
        json={"display_name": "PLA Preto Principal"},
    )

    response = api_environment.client.get("/api/spools", params={"search": search})

    assert response_codes(response) == [spool["code"]]


def test_search_by_manufacturer_name(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "Polymaker"},
    )

    assert response_codes(response) == expected_codes(
        search_dataset,
        "polymaker_petg",
    )


def test_search_by_partial_manufacturer_is_case_insensitive(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "poly"},
    )

    assert response_codes(response) == expected_codes(
        search_dataset,
        "polymaker_petg",
    )


def test_search_by_material_name(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "TPU"},
    )

    assert response_codes(response) == expected_codes(search_dataset, "sunlu_tpu")


def test_search_strips_surrounding_whitespace(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "  black  "},
    )

    assert response_codes(response) == expected_codes(
        search_dataset,
        "esun_pla",
        "sunlu_tpu",
    )


@pytest.mark.parametrize("search", ["", "   "])
def test_empty_search_is_equivalent_to_no_search(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
    search: str,
) -> None:
    unfiltered = api_environment.client.get("/api/spools")
    searched = api_environment.client.get(
        "/api/spools",
        params={"search": search},
    )

    assert searched.status_code == 200
    assert searched.json() == unfiltered.json()


def test_search_without_results_returns_empty_list(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "nonexistent-value"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_search_combines_with_material_filter_using_and(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={
            "search": "black",
            "material_id": search_dataset.material_ids["pla"],
        },
    )

    assert response_codes(response) == expected_codes(search_dataset, "esun_pla")


def test_search_combines_with_status_filter_using_and(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "eSUN", "status": "LOW"},
    )

    assert response_codes(response) == expected_codes(search_dataset, "esun_pla")


def test_search_combines_with_multiple_structured_filters(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={
            "search": "black",
            "manufacturer_id": search_dataset.manufacturer_ids["esun"],
            "status": "LOW",
            "max_remaining_percent": 30,
        },
    )

    assert response_codes(response) == expected_codes(search_dataset, "esun_pla")


def test_search_hides_archived_matches_by_default_and_can_include_them(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    archived = search_dataset.spools["sunlu_tpu"]
    archive_response = api_environment.client.post(
        f"/api/spools/{archived['code']}/archive"
    )
    assert archive_response.status_code == 200

    default_search = api_environment.client.get(
        "/api/spools",
        params={"search": "black"},
    )
    archived_search = api_environment.client.get(
        "/api/spools",
        params={"search": "black", "include_archived": "true"},
    )

    assert response_codes(default_search) == expected_codes(
        search_dataset,
        "esun_pla",
    )
    assert response_codes(archived_search) == expected_codes(
        search_dataset,
        "esun_pla",
        "sunlu_tpu",
    )


def test_search_combines_with_explicit_archived_status(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    archived = search_dataset.spools["sunlu_tpu"]
    archive_response = api_environment.client.post(
        f"/api/spools/{archived['code']}/archive"
    )
    assert archive_response.status_code == 200

    response = api_environment.client.get(
        "/api/spools",
        params={"search": "galaxy", "status": "ARCHIVED"},
    )

    assert response_codes(response) == expected_codes(search_dataset, "sunlu_tpu")


def test_search_does_not_duplicate_spool_matching_multiple_fields(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    with api_environment.session_factory() as session:
        manufacturer = Manufacturer(name="PLA Brand")
        material = Material(name="PLA Search", category="PLA")
        session.add_all([manufacturer, material])
        session.commit()
        manufacturer_id = manufacturer.id
        material_id = material.id

    multi_match = create_spool(
        api_environment,
        manufacturer_id=manufacturer_id,
        material_id=material_id,
        product_name="PLA Special",
        color_name="PLA Black",
    )

    response = api_environment.client.get(
        "/api/spools",
        params={"search": "PLA"},
    )

    codes = response_codes(response)
    assert codes.count(multi_match["code"]) == 1


def test_search_response_keeps_relationships_serialized(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    response = api_environment.client.get(
        "/api/spools",
        params={"search": "Polymaker"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    body = response.json()[0]
    assert body["manufacturer"]["name"] == "Polymaker"
    assert body["material"]["name"] == "PETG"


def test_search_escapes_like_wildcards(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    literal_percent = create_spool(
        api_environment,
        product_name="100% Recycled",
        color_name="Green",
    )

    response = api_environment.client.get(
        "/api/spools",
        params={"search": "%"},
    )

    assert response_codes(response) == [literal_percent["code"]]


def test_search_is_parameterized_and_executes_in_one_query(
    api_environment: ApiEnvironment,
    search_dataset: SearchDataset,
) -> None:
    statements: list[str] = []
    bound_parameters: list[object] = []

    def record_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        statements.append(statement)
        bound_parameters.append(parameters)

    event.listen(api_environment.engine, "before_cursor_execute", record_statement)
    try:
        response = api_environment.client.get(
            "/api/spools",
            params={"search": "black"},
        )
    finally:
        event.remove(
            api_environment.engine,
            "before_cursor_execute",
            record_statement,
        )

    assert response.status_code == 200
    assert len(statements) == 1
    assert "EXISTS" in statements[0]
    assert "black" not in statements[0].lower()
    assert "%black%" in bound_parameters[0]
