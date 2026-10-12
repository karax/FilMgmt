from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory, get_db
from app.main import app
from app.models import (
    CalibrationEventType,
    FilamentReconciliationEventType,
    Manufacturer,
    Material,
    PrintJob,
    PrintJobEnrichmentStatus,
    PrintJobFilamentReconciliation,
    PrintJobFilamentUsage,
    PrintJobReconciliationStatus,
    PrintJobStatus,
    Spool,
    SpoolCalibration,
    SpoolStatus,
    TareConfidence,
    TareSource,
    WeightHistory,
    WeightSource,
)


CUSTOM_RANGE = (
    "range=custom&from=2026-10-01&to=2026-10-31&timezone=Europe%2FLisbon"
)


@dataclass(frozen=True)
class AnalyticsEnvironment:
    client: TestClient
    factory: sessionmaker[Session]
    spool_ids: dict[str, int]


@pytest.fixture
def analytics_environment(tmp_path: Path) -> Iterator[AnalyticsEnvironment]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'analytics.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db:
        spool_ids = _seed_analytics_fixture(db)

    def override() -> Iterator[Session]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    try:
        yield AnalyticsEnvironment(client, factory, spool_ids)
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()


def _seed_analytics_fixture(db: Session) -> dict[str, int]:
    esun = Manufacturer(name="eSUN")
    bambu = Manufacturer(name="Bambu Lab")
    unknown_brand = Manufacturer(name="")
    pla = Material(name="PLA", category="PLA")
    petg = Material(name="PETG", category="PETG")
    db.add_all([esun, bambu, unknown_brand, pla, petg])
    db.flush()

    spools = {
        "a": Spool(
            code="FIL-A",
            display_name="Black PLA A",
            manufacturer_id=esun.id,
            material_id=pla.id,
            color_name="Black",
            initial_filament_weight_g=Decimal("1000"),
            current_filament_weight_g=Decimal("700"),
            purchase_price=Decimal("20"),
            currency="EUR",
            store_name="3DJake",
            purchase_date=date(2026, 10, 1),
            status=SpoolStatus.OPEN,
        ),
        "a2": Spool(
            code="FIL-A2",
            display_name="Black PLA A2",
            manufacturer_id=esun.id,
            material_id=pla.id,
            color_name="Black",
            initial_filament_weight_g=Decimal("1000"),
            current_filament_weight_g=Decimal("500"),
            purchase_price=Decimal("22"),
            currency="GBP",
            store_name="Amazon",
            purchase_date=date(2026, 10, 2),
            status=SpoolStatus.OPEN,
        ),
        "b": Spool(
            code="FIL-B",
            display_name="White PETG",
            manufacturer_id=bambu.id,
            material_id=petg.id,
            color_name="White",
            initial_filament_weight_g=Decimal("1000"),
            current_filament_weight_g=Decimal("800"),
            purchase_price=Decimal("25"),
            currency="EUR",
            store_name="3DJake",
            purchase_date=date(2026, 9, 15),
            status=SpoolStatus.OPEN,
        ),
        "c": Spool(
            code="FIL-C",
            display_name="Unknown PLA",
            manufacturer_id=unknown_brand.id,
            material_id=pla.id,
            color_name="Natural",
            initial_filament_weight_g=Decimal("1000"),
            current_filament_weight_g=Decimal("900"),
            purchase_price=None,
            currency="EUR",
            store_name=None,
            purchase_date=date(2026, 10, 3),
            status=SpoolStatus.SEALED,
        ),
        "empty": Spool(
            code="FIL-EMPTY",
            manufacturer_id=esun.id,
            material_id=pla.id,
            color_name="Blue",
            initial_filament_weight_g=Decimal("1000"),
            current_filament_weight_g=Decimal("0"),
            currency="EUR",
            status=SpoolStatus.EMPTY,
        ),
        "archived": Spool(
            code="FIL-ARCHIVED",
            manufacturer_id=esun.id,
            material_id=pla.id,
            color_name="Red",
            initial_filament_weight_g=Decimal("1000"),
            current_filament_weight_g=Decimal("100"),
            currency="EUR",
            status=SpoolStatus.ARCHIVED,
            archived_at=datetime(2026, 9, 1, tzinfo=UTC),
        ),
    }
    db.add_all(spools.values())
    db.flush()

    def job(
        name: str,
        status: PrintJobStatus,
        started_at: datetime | None,
        duration_seconds: int | None,
        *,
        slicer_seconds: int | None = None,
    ) -> PrintJob:
        item = PrintJob(
            name=name,
            status=status,
            started_at=started_at,
            finished_at=(started_at.replace(hour=min(started_at.hour + 1, 23)) if started_at else None),
            duration_seconds=duration_seconds,
            slicer_estimated_duration_seconds=slicer_seconds,
            capture_mode="LIVE",
            enrichment_status=PrintJobEnrichmentStatus.ENRICHED,
            reconciliation_status=PrintJobReconciliationStatus.PENDING,
        )
        db.add(item)
        db.flush()
        return item

    def usage(item: PrintJob, position: int, material: str, estimated: str) -> PrintJobFilamentUsage:
        row = PrintJobFilamentUsage(
            print_job_id=item.id,
            position=position,
            material_type=material,
            used_g=Decimal(estimated),
        )
        db.add(row)
        db.flush()
        return row

    def consume(item: PrintJob, row: PrintJobFilamentUsage, spool: Spool, amount: str, created_day: int = 10):
        event = PrintJobFilamentReconciliation(
            print_job_id=item.id,
            filament_usage_id=row.id,
            spool_id=spool.id,
            event_type=FilamentReconciliationEventType.CONSUMPTION,
            amount_g=Decimal(amount),
            sliced_estimated_g=row.used_g,
            remaining_before_g=spool.current_filament_weight_g + Decimal(amount),
            remaining_after_g=spool.current_filament_weight_g,
            created_at=datetime(2026, 10, created_day, 20, tzinfo=UTC),
        )
        db.add(event)
        db.flush()
        return event

    j1 = job("Partial multi material", PrintJobStatus.COMPLETED, datetime(2026, 10, 1, 22, 30, tzinfo=UTC), 3600)
    consume(j1, usage(j1, 0, "PLA", "230.510"), spools["a"], "100")
    usage(j1, 1, "PETG", "150")
    j1.reconciliation_status = PrintJobReconciliationStatus.PARTIALLY_RECONCILED

    j2 = job("Failed reversed", PrintJobStatus.FAILED, datetime(2026, 10, 2, 9, tzinfo=UTC), 1200)
    u2 = usage(j2, 0, "PETG", "50")
    old = consume(j2, u2, spools["b"], "50")
    old.reversed_at = datetime(2026, 10, 11, 20, tzinfo=UTC)
    db.add(PrintJobFilamentReconciliation(
        print_job_id=j2.id,
        filament_usage_id=u2.id,
        spool_id=spools["b"].id,
        event_type=FilamentReconciliationEventType.REVERSAL,
        amount_g=Decimal("50"),
        sliced_estimated_g=Decimal("50"),
        reversed_event_id=old.id,
        created_at=datetime(2026, 10, 11, 20, tzinfo=UTC),
    ))

    j3 = job("Cancelled manual", PrintJobStatus.CANCELLED, datetime(2026, 10, 3, 12, tzinfo=UTC), None, slicer_seconds=9999)
    consume(j3, usage(j3, 0, "PETG", "80"), spools["b"], "30")

    j4 = job("Second identical spool", PrintJobStatus.SUCCESS, datetime(2026, 10, 10, 12, tzinfo=UTC), 1800)
    consume(j4, usage(j4, 0, "PLA", "40"), spools["a2"], "40")

    j5 = job("Timezone boundary", PrintJobStatus.COMPLETED, datetime(2026, 9, 30, 23, 30, tzinfo=UTC), 600)
    consume(j5, usage(j5, 0, "PLA", "20"), spools["c"], "20", created_day=12)

    j6 = job("Explicitly skipped", PrintJobStatus.COMPLETED, datetime(2026, 10, 5, 12, tzinfo=UTC), 300)
    u6 = usage(j6, 0, "PLA", "400")
    db.add(PrintJobFilamentReconciliation(
        print_job_id=j6.id,
        filament_usage_id=u6.id,
        spool_id=None,
        event_type=FilamentReconciliationEventType.SKIP,
        amount_g=Decimal("0"),
        reason="Do not deduct",
        created_at=datetime(2026, 10, 12, 20, tzinfo=UTC),
    ))
    j6.reconciliation_status = PrintJobReconciliationStatus.NOT_APPLICABLE

    j7 = job("Re-reconciled once", PrintJobStatus.COMPLETED, datetime(2026, 10, 6, 12, tzinfo=UTC), 100)
    u7 = usage(j7, 0, "PLA", "10")
    original = consume(j7, u7, spools["a"], "10")
    original.reversed_at = datetime(2026, 10, 11, 20, tzinfo=UTC)
    db.add(PrintJobFilamentReconciliation(
        print_job_id=j7.id,
        filament_usage_id=u7.id,
        spool_id=spools["a"].id,
        event_type=FilamentReconciliationEventType.REVERSAL,
        amount_g=Decimal("10"),
        sliced_estimated_g=Decimal("10"),
        reversed_event_id=original.id,
        created_at=datetime(2026, 10, 11, 20, tzinfo=UTC),
    ))
    consume(j7, u7, spools["a2"], "12", created_day=12)

    printing = job("Still printing estimate", PrintJobStatus.PRINTING, datetime(2026, 10, 7, 12, tzinfo=UTC), None, slicer_seconds=7200)
    usage(printing, 0, "PLA", "999")

    unknown = job("Unknown terminal", PrintJobStatus.UNKNOWN_TERMINAL, datetime(2026, 10, 8, 12, tzinfo=UTC), 50)
    unknown.enrichment_status = None

    db.add(SpoolCalibration(
        spool_id=spools["a"].id,
        event_type=CalibrationEventType.PHYSICAL_CALIBRATION,
        measured_total_g=Decimal("900"),
        tare_g_used=Decimal("200"),
        calculated_filament_g=Decimal("700"),
        previous_remaining_g=Decimal("1287"),
        adjustment_g=Decimal("-587"),
        new_remaining_g=Decimal("700"),
        tare_source_used=TareSource.MEASURED,
        tare_confidence_used=TareConfidence.HIGH,
        idempotency_key="analytics-calibration",
        effective_at=datetime(2026, 10, 9, tzinfo=UTC),
    ))
    db.add(WeightHistory(
        spool_id=spools["a"].id,
        weight_g=Decimal("700"),
        source=WeightSource.SCALE,
        notes="Physical calibration -587 g",
    ))
    db.commit()
    return {name: spool.id for name, spool in spools.items()}


def _get(environment: AnalyticsEnvironment, path: str, query: str = CUSTOM_RANGE):
    separator = "&" if "?" in path else "?"
    response = environment.client.get(f"{path}{separator}{query}")
    assert response.status_code == 200, response.text
    return response.json()


def test_confirmed_consumption_uses_only_active_confirmed_lines(analytics_environment):
    body = _get(analytics_environment, "/api/analytics/dashboard")
    consumption = body["consumption"]
    assert Decimal(consumption["confirmed_g"]) == Decimal("202.000")
    assert Decimal(consumption["confirmed_kg"]) == Decimal("0.202")
    assert Decimal(consumption["confirmed_g_with_known_cost"]) == Decimal("182.000")
    assert Decimal(consumption["cost_coverage_percentage"]) == Decimal("90.10")
    assert {row["currency"]: Decimal(row["amount"]) for row in consumption["estimated_costs"]} == {
        "EUR": Decimal("2.75"),
        "GBP": Decimal("1.14"),
    }
    assert body["reconciliation"] == {
        "pending_print_count": 2,
        "pending_filament_usage_count": 2,
    }


@pytest.mark.parametrize(
    ("bucket", "expected"),
    [
        ("day", {"2026-10-01": Decimal("120"), "2026-10-03": Decimal("30"), "2026-10-06": Decimal("12"), "2026-10-10": Decimal("40")}),
        ("week", {"2026-09-28": Decimal("150"), "2026-10-05": Decimal("52")}),
        ("month", {"2026-10": Decimal("202")}),
    ],
)
def test_consumption_bucketing_uses_print_date_and_requested_timezone(analytics_environment, bucket, expected):
    body = _get(
        analytics_environment,
        "/api/analytics/consumption-over-time",
        f"{CUSTOM_RANGE}&bucket={bucket}",
    )
    actual = {row["period"]: Decimal(row["consumption_g"]) for row in body["points"]}
    assert actual == expected
    assert Decimal(body["unbucketed_consumption_g"]) == 0


def test_rankings_keep_physical_spools_separate_and_group_canonical_dimensions(analytics_environment):
    spools = _get(analytics_environment, "/api/analytics/top-spools")
    assert [(row["code"], Decimal(row["consumption_g"])) for row in spools] == [
        ("FIL-A", Decimal("100")),
        ("FIL-A2", Decimal("52")),
        ("FIL-B", Decimal("30")),
        ("FIL-C", Decimal("20")),
    ]
    assert spools[1]["print_count"] == 2
    materials = _get(analytics_environment, "/api/analytics/consumption-by-material")
    assert {row["name"]: Decimal(row["consumption_g"]) for row in materials} == {
        "PLA": Decimal("172"),
        "PETG": Decimal("30"),
    }
    brands = _get(analytics_environment, "/api/analytics/consumption-by-brand")
    assert {row["name"]: Decimal(row["consumption_g"]) for row in brands} == {
        "eSUN": Decimal("152"),
        "Bambu Lab": Decimal("30"),
        "Unknown": Decimal("20"),
    }


def test_current_inventory_is_not_filtered_by_date_and_excludes_empty_archived(analytics_environment):
    dashboard = _get(
        analytics_environment,
        "/api/analytics/dashboard",
        "range=custom&from=1999-01-01&to=1999-01-02",
    )
    assert dashboard["inventory"] == {
        "active_spool_count": 4,
        "current_remaining_g": "2900.000",
        "empty_spool_count": 1,
        "archived_spool_count": 1,
    }
    inventory = _get(
        analytics_environment,
        "/api/analytics/inventory-by-material",
        "range=custom&from=1999-01-01&to=1999-01-02",
    )
    assert {row["material"]: Decimal(row["remaining_g"]) for row in inventory} == {
        "PLA": Decimal("2100"),
        "PETG": Decimal("800"),
    }


def test_purchase_rankings_use_purchase_date_unknown_store_and_keep_currencies_separate(analytics_environment):
    body = _get(analytics_environment, "/api/analytics/purchases-by-store")
    assert {(row["store"], row["currency"], Decimal(row["amount"])) for row in body["by_spend"]} == {
        ("3DJake", "EUR", Decimal("20")),
        ("Amazon", "GBP", Decimal("22")),
    }
    assert {row["store"]: row["spool_count"] for row in body["by_spool_count"]} == {
        "3DJake": 1,
        "Amazon": 1,
        "Unknown": 1,
    }
    series = _get(
        analytics_environment,
        "/api/analytics/purchase-spend-over-time",
        f"{CUSTOM_RANGE}&bucket=month",
    )
    assert {(row["period"], row["currency"], Decimal(row["amount"])) for row in series["points"]} == {
        ("2026-10", "EUR", Decimal("20")),
        ("2026-10", "GBP", Decimal("22")),
    }


def test_print_outcomes_success_rate_duration_and_completed_series(analytics_environment):
    body = _get(
        analytics_environment,
        "/api/analytics/print-activity",
        f"{CUSTOM_RANGE}&bucket=month",
    )
    assert body["outcomes"] == {
        "completed": 5,
        "failed": 1,
        "cancelled": 1,
        "unknown_terminal": 1,
        "success_rate_percentage": "71.43",
    }
    assert body["activity"] == {
        "actual_printing_seconds": 7650,
        "actual_printing_hours": "2.13",
        "jobs_with_actual_duration": 7,
        "total_terminal_jobs": 8,
        "duration_coverage_percentage": "87.50",
    }
    assert body["completed_prints_by_period"] == [{"period": "2026-10", "count": 5}]
    assert body["printing_seconds_by_period"] == [{"period": "2026-10", "count": 7650}]


def test_zero_denominator_and_empty_data_are_explicit(analytics_environment):
    body = _get(
        analytics_environment,
        "/api/analytics/dashboard",
        "range=custom&from=1999-01-01&to=1999-01-02&material=PETG",
    )
    assert body["printing"]["success_rate_percentage"] is None
    assert body["consumption"]["confirmed_g"] == "0.000"
    assert body["consumption"]["estimated_costs"] == []
    assert body["highlights"]["most_used_spool"] is None


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (f"{CUSTOM_RANGE}&material=PETG", Decimal("30")),
        (f"{CUSTOM_RANGE}&brand=eSUN", Decimal("152")),
        (f"{CUSTOM_RANGE}&store=Amazon", Decimal("52")),
    ],
)
def test_dimension_filters_compose(analytics_environment, query, expected):
    body = _get(analytics_environment, "/api/analytics/dashboard", query)
    assert Decimal(body["consumption"]["confirmed_g"]) == expected


def test_spool_filter_and_custom_date_range(analytics_environment):
    query = f"{CUSTOM_RANGE}&spool_id={analytics_environment.spool_ids['a2']}"
    body = _get(analytics_environment, "/api/analytics/dashboard", query)
    assert Decimal(body["consumption"]["confirmed_g"]) == Decimal("52")


def test_top_consuming_prints_uses_confirmed_consumption(analytics_environment):
    rows = _get(analytics_environment, "/api/analytics/top-consuming-prints")
    assert rows[0]["name"] == "Partial multi material"
    assert Decimal(rows[0]["consumption_g"]) == Decimal("100")
    assert all(row["name"] != "Still printing estimate" for row in rows)


def test_invalid_custom_ranges_and_timezone_are_rejected(analytics_environment):
    assert analytics_environment.client.get("/api/analytics/dashboard?range=custom").status_code == 422
    assert analytics_environment.client.get(
        "/api/analytics/dashboard?range=custom&from=2026-10-02&to=2026-10-01"
    ).status_code == 422
    assert analytics_environment.client.get(
        "/api/analytics/dashboard?range=last_30_days&timezone=Not%2FAZone"
    ).status_code == 422


def test_analytics_get_requests_create_zero_inventory_or_ledger_mutations(analytics_environment):
    with analytics_environment.factory() as db:
        before = {
            "reconciliation": db.scalar(select(func.count()).select_from(PrintJobFilamentReconciliation)),
            "weights": db.scalar(select(func.count()).select_from(WeightHistory)),
            "calibrations": db.scalar(select(func.count()).select_from(SpoolCalibration)),
            "remaining": list(db.execute(select(Spool.id, Spool.current_filament_weight_g).order_by(Spool.id)).all()),
        }
    for path in (
        "/api/analytics/dashboard",
        "/api/analytics/consumption-over-time",
        "/api/analytics/top-spools",
        "/api/analytics/consumption-by-material",
        "/api/analytics/consumption-by-brand",
        "/api/analytics/inventory-by-material",
        "/api/analytics/purchases-by-store",
        "/api/analytics/purchase-spend-over-time",
        "/api/analytics/print-activity",
        "/api/analytics/top-consuming-prints",
    ):
        _get(analytics_environment, path)
    with analytics_environment.factory() as db:
        after = {
            "reconciliation": db.scalar(select(func.count()).select_from(PrintJobFilamentReconciliation)),
            "weights": db.scalar(select(func.count()).select_from(WeightHistory)),
            "calibrations": db.scalar(select(func.count()).select_from(SpoolCalibration)),
            "remaining": list(db.execute(select(Spool.id, Spool.current_filament_weight_g).order_by(Spool.id)).all()),
        }
    assert after == before


def test_openapi_exposes_only_get_analytics_operations(analytics_environment):
    document = analytics_environment.client.get("/openapi.json").json()
    paths = {path: methods for path, methods in document["paths"].items() if path.startswith("/api/analytics/")}
    assert paths
    assert all(set(methods) == {"get"} for methods in paths.values())
    serialized = str(paths).lower()
    assert "bambu_access_code" not in serialized
    assert "password" not in serialized
