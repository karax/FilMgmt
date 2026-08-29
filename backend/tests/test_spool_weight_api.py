from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import (
    create_database_engine,
    create_session_factory,
    get_db,
)
from app.main import app
from app.models import (
    Location,
    Manufacturer,
    Material,
    Spool,
    SpoolStatus,
    WeightHistory,
    WeightSource,
)


@dataclass(frozen=True)
class WeightApiEnvironment:
    client: TestClient
    session_factory: sessionmaker[Session]
    engine: Engine
    manufacturer_id: int
    material_id: int
    location_id: int


@pytest.fixture
def weight_api_environment(tmp_path: Path) -> Iterator[WeightApiEnvironment]:
    database_path = tmp_path / "spool-weight-api.db"
    engine = create_database_engine(
        f"sqlite+pysqlite:///{database_path.as_posix()}"
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        manufacturer = Manufacturer(name="eSUN")
        material = Material(name="PLA+", category="PLA")
        location = Location(name="Dry Box")
        session.add_all([manufacturer, material, location])
        session.commit()
        manufacturer_id = manufacturer.id
        material_id = material.id
        location_id = location.id

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield WeightApiEnvironment(
                client=client,
                session_factory=session_factory,
                engine=engine,
                manufacturer_id=manufacturer_id,
                material_id=material_id,
                location_id=location_id,
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_spool(
    environment: WeightApiEnvironment,
    *,
    initial_weight: int = 1000,
    current_weight: int = 1000,
) -> dict[str, object]:
    response = environment.client.post(
        "/api/spools",
        json={
            "manufacturer_id": environment.manufacturer_id,
            "material_id": environment.material_id,
            "location_id": environment.location_id,
            "color_name": "Black",
            "initial_filament_weight_g": initial_weight,
            "current_filament_weight_g": current_weight,
            "status": "OPEN",
        },
    )
    assert response.status_code == 201
    return response.json()


def get_persisted_spool(
    environment: WeightApiEnvironment,
    code: object,
) -> Spool:
    with environment.session_factory() as session:
        spool = session.scalar(select(Spool).where(Spool.code == code))
        assert spool is not None
        session.expunge(spool)
        return spool


def get_history(
    environment: WeightApiEnvironment,
    spool_id: object,
) -> list[WeightHistory]:
    with environment.session_factory() as session:
        histories = list(
            session.scalars(
                select(WeightHistory)
                .where(WeightHistory.spool_id == spool_id)
                .order_by(WeightHistory.id.asc())
            ).all()
        )
        session.expunge_all()
        return histories


def test_manual_weight_update_returns_updated_spool(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 742, "source": "MANUAL"},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["current_filament_weight_g"]) == Decimal(
        "742.000"
    )
    assert response.json()["remaining_percent"] == 74.2
    assert response.json()["status"] == "OPEN"
    assert response.json()["code"] == spool["code"]
    assert get_persisted_spool(
        weight_api_environment,
        spool["code"],
    ).current_filament_weight_g == Decimal("742.000")


def test_weight_update_creates_history(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 742, "source": "MANUAL"},
    )

    assert response.status_code == 200
    histories = get_history(weight_api_environment, spool["id"])
    assert len(histories) == 1
    assert histories[0].spool_id == spool["id"]
    assert histories[0].weight_g == Decimal("742.000")
    assert histories[0].source is WeightSource.MANUAL


def test_history_insert_failure_rolls_back_weight_update(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    def fail_history_insert(
        _connection: object,
        _cursor: object,
        statement: str,
        parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if statement.lstrip().upper().startswith("INSERT INTO WEIGHT_HISTORY"):
            raise IntegrityError(statement, parameters, RuntimeError("forced"))

    event.listen(
        weight_api_environment.engine,
        "before_cursor_execute",
        fail_history_insert,
    )
    try:
        response = weight_api_environment.client.post(
            f"/api/spools/{spool['code']}/weight",
            json={"weight_g": 180, "source": "MANUAL"},
        )
    finally:
        event.remove(
            weight_api_environment.engine,
            "before_cursor_execute",
            fail_history_insert,
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Spool operation conflicts with current data."
    }
    assert get_persisted_spool(
        weight_api_environment,
        spool["code"],
    ).current_filament_weight_g == Decimal("1000.000")
    assert get_persisted_spool(
        weight_api_environment,
        spool["code"],
    ).status is SpoolStatus.OPEN
    assert get_history(weight_api_environment, spool["id"]) == []


def test_negative_weight_is_rejected_without_changes(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": -1, "source": "MANUAL"},
    )

    assert response.status_code == 422
    assert get_persisted_spool(
        weight_api_environment,
        spool["code"],
    ).current_filament_weight_g == Decimal("1000.000")
    assert get_history(weight_api_environment, spool["id"]) == []


def test_weight_above_initial_is_rejected_without_changes(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 1200, "source": "MANUAL"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Weight cannot exceed the spool's initial filament weight."
    }
    assert get_persisted_spool(
        weight_api_environment,
        spool["code"],
    ).current_filament_weight_g == Decimal("1000.000")
    assert get_history(weight_api_environment, spool["id"]) == []


def test_zero_weight_is_allowed_and_recorded(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 0, "source": "MANUAL"},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["current_filament_weight_g"]) == 0
    assert get_history(weight_api_environment, spool["id"])[0].weight_g == 0
    assert response.json()["remaining_percent"] == 0.0
    assert response.json()["status"] == "EMPTY"


def test_weight_update_transitions_open_to_low(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment, current_weight=500)

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 180, "source": "MANUAL"},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["current_filament_weight_g"]) == Decimal(
        "180.000"
    )
    assert response.json()["remaining_percent"] == 18.0
    assert response.json()["status"] == "LOW"


def test_weight_correction_transitions_low_back_to_open(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment, current_weight=180)
    assert spool["status"] == "LOW"

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 600, "source": "CORRECTION"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "OPEN"
    assert response.json()["remaining_percent"] == 60.0
    histories = get_history(weight_api_environment, spool["id"])
    assert [history.weight_g for history in histories] == [Decimal("600.000")]
    assert histories[0].source is WeightSource.CORRECTION


@pytest.mark.parametrize(
    ("corrected_weight", "expected_status"),
    [(150, "LOW"), (700, "OPEN")],
)
def test_weight_correction_transitions_empty_to_managed_status(
    weight_api_environment: WeightApiEnvironment,
    corrected_weight: int,
    expected_status: str,
) -> None:
    spool = create_spool(weight_api_environment, current_weight=0)
    assert spool["status"] == "EMPTY"

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": corrected_weight, "source": "CORRECTION"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == expected_status


def test_status_filters_reflect_automatic_weight_transitions(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    low_spool = create_spool(weight_api_environment, current_weight=500)
    empty_spool = create_spool(weight_api_environment, current_weight=500)

    low_response = weight_api_environment.client.post(
        f"/api/spools/{low_spool['code']}/weight",
        json={"weight_g": 180, "source": "MANUAL"},
    )
    empty_response = weight_api_environment.client.post(
        f"/api/spools/{empty_spool['code']}/weight",
        json={"weight_g": 0, "source": "MANUAL"},
    )

    assert low_response.status_code == 200
    assert empty_response.status_code == 200
    listed_low = weight_api_environment.client.get(
        "/api/spools", params={"status": "LOW"}
    )
    listed_empty = weight_api_environment.client.get(
        "/api/spools", params={"status": "EMPTY"}
    )
    assert [item["code"] for item in listed_low.json()] == [low_spool["code"]]
    assert [item["code"] for item in listed_empty.json()] == [
        empty_spool["code"]
    ]


def test_unknown_spool_returns_not_found(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    response = weight_api_environment.client.post(
        "/api/spools/FIL-9999/weight",
        json={"weight_g": 742, "source": "MANUAL"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Spool not found."}


def test_archived_spool_rejects_weight_update(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)
    archive = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/archive"
    )
    assert archive.status_code == 200

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 742, "source": "MANUAL"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Archived spool cannot be updated."
    }
    assert get_persisted_spool(
        weight_api_environment,
        spool["code"],
    ).current_filament_weight_g == Decimal("1000.000")
    assert get_history(weight_api_environment, spool["id"]) == []


def test_unknown_source_is_rejected(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 742, "source": "UNKNOWN"},
    )

    assert response.status_code == 422
    assert get_history(weight_api_environment, spool["id"]) == []


@pytest.mark.parametrize("source", ["SCALE", "PRINT"])
def test_automated_weight_sources_are_recorded(
    weight_api_environment: WeightApiEnvironment,
    source: str,
) -> None:
    spool = create_spool(weight_api_environment)

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 742, "source": source},
    )

    assert response.status_code == 200
    history = get_history(weight_api_environment, spool["id"])[0]
    assert history.source.value == source


def test_weight_notes_are_preserved(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)
    notes = "Pesagem depois da impressão."

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={"weight_g": 742, "source": "MANUAL", "notes": notes},
    )

    assert response.status_code == 200
    assert get_history(weight_api_environment, spool["id"])[0].notes == notes


def test_same_weight_creates_a_new_measurement_event(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(
        weight_api_environment,
        current_weight=742,
    )

    for _ in range(2):
        response = weight_api_environment.client.post(
            f"/api/spools/{spool['code']}/weight",
            json={"weight_g": 742, "source": "SCALE"},
        )
        assert response.status_code == 200

    histories = get_history(weight_api_environment, spool["id"])
    assert [history.weight_g for history in histories] == [
        Decimal("742.000"),
        Decimal("742.000"),
    ]


def test_multiple_measurements_update_current_and_append_history(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    for weight in (900, 742, 500):
        response = weight_api_environment.client.post(
            f"/api/spools/{spool['code']}/weight",
            json={"weight_g": weight, "source": "MANUAL"},
        )
        assert response.status_code == 200

    assert get_persisted_spool(
        weight_api_environment,
        spool["code"],
    ).current_filament_weight_g == Decimal("500.000")
    assert [
        history.weight_g
        for history in get_history(weight_api_environment, spool["id"])
    ] == [Decimal("900.000"), Decimal("742.000"), Decimal("500.000")]


def test_generic_spool_update_cannot_change_current_weight(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    response = weight_api_environment.client.put(
        f"/api/spools/{spool['code']}",
        json={"current_filament_weight_g": 742},
    )

    assert response.status_code == 422
    assert get_persisted_spool(
        weight_api_environment,
        spool["code"],
    ).current_filament_weight_g == Decimal("1000.000")
    assert get_history(weight_api_environment, spool["id"]) == []


def test_weight_payload_cannot_select_another_spool(
    weight_api_environment: WeightApiEnvironment,
) -> None:
    spool = create_spool(weight_api_environment)

    response = weight_api_environment.client.post(
        f"/api/spools/{spool['code']}/weight",
        json={
            "weight_g": 742,
            "source": "MANUAL",
            "spool_id": 999_999,
        },
    )

    assert response.status_code == 422
    assert get_persisted_spool(
        weight_api_environment,
        spool["code"],
    ).current_filament_weight_g == Decimal("1000.000")
    assert get_history(weight_api_environment, spool["id"]) == []
