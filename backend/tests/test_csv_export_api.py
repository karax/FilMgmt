from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
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
    PrintJobFilamentReconciliation,
    Spool,
    SpoolCalibration,
    WeightHistory,
)
from app.services.analytics_service import AnalyticsDateRange, AnalyticsFilters, AnalyticsService
from app.services.csv_export_service import (
    DATASET_DEFINITIONS,
    CsvExportService,
    ExportDataset,
    ExportScope,
)
from app.schemas.analytics import AnalyticsBucket, AnalyticsRangePreset
from tests.test_analytics_api import _seed_analytics_fixture


CUSTOM_RANGE = "range=custom&from=2026-10-01&to=2026-10-31&timezone=Europe%2FLisbon"


@dataclass(frozen=True)
class ExportEnvironment:
    client: TestClient
    factory: sessionmaker[Session]
    spool_ids: dict[str, int]


@pytest.fixture
def export_environment(tmp_path: Path) -> Iterator[ExportEnvironment]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'export.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db:
        spool_ids = _seed_analytics_fixture(db)
        active = db.scalar(
            select(PrintJobFilamentReconciliation)
            .where(
                PrintJobFilamentReconciliation.event_type
                == FilamentReconciliationEventType.CONSUMPTION,
                PrintJobFilamentReconciliation.reversed_at.is_(None),
            )
            .order_by(PrintJobFilamentReconciliation.id)
        )
        assert active is not None
        active.amount_g = Decimal("230.510")
        active.sliced_estimated_g = Decimal("230.510")

        calibration = db.scalar(
            select(SpoolCalibration).where(
                SpoolCalibration.event_type == CalibrationEventType.PHYSICAL_CALIBRATION
            )
        )
        assert calibration is not None
        reversed_at = datetime(2026, 10, 10, 8, tzinfo=UTC)
        calibration.reversed_at = reversed_at
        db.add(SpoolCalibration(
            spool_id=calibration.spool_id,
            event_type=CalibrationEventType.REVERSAL,
            previous_remaining_g=calibration.new_remaining_g,
            adjustment_g=calibration.previous_remaining_g - calibration.new_remaining_g,
            new_remaining_g=calibration.previous_remaining_g,
            note="Undo calibration",
            reversed_calibration_id=calibration.id,
            effective_at=reversed_at,
            created_at=reversed_at,
        ))

        archived = db.get(Spool, spool_ids["archived"])
        assert archived is not None
        archived.display_name = '=HYPERLINK("https://example.invalid")'
        archived.product_name = "+SUM(1,2)"
        archived.color_name = "-cmd"
        archived.store_name = 'Filamentos Pró, "São João"'
        archived.notes = "@danger\nsecond line"
        db.commit()

    def override() -> Iterator[Session]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    try:
        yield ExportEnvironment(client, factory, spool_ids)
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()


def _response(environment: ExportEnvironment, dataset: str, query: str = CUSTOM_RANGE):
    return environment.client.get(f"/api/analytics/export?dataset={dataset}&{query}")


def _rows(response) -> tuple[list[str], list[dict[str, str]]]:
    text = response.content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    return list(reader.fieldnames or []), list(reader)


def test_valid_export_has_csv_headers_bom_and_safe_filename(export_environment):
    response = _response(export_environment, "spools")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="spool-inventory-custom-'
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content.startswith(b"\xef\xbb\xbf")


def test_unknown_dataset_and_invalid_analytics_scope_are_rejected(export_environment):
    assert _response(export_environment, "sqlite_master").status_code == 422
    assert _response(
        export_environment,
        "consumption_over_time",
        f"{CUSTOM_RANGE}&scope=all",
    ).status_code == 422


@pytest.mark.parametrize("dataset", list(ExportDataset))
def test_every_allowlisted_dataset_exports_stable_headers(export_environment, dataset):
    response = _response(export_environment, dataset.value)
    assert response.status_code == 200, response.text
    headers, _ = _rows(response)
    assert headers == [column.name for column in DATASET_DEFINITIONS[dataset].columns]


def test_spool_export_handles_utf8_quoting_newlines_formula_injection_and_missing_values(export_environment):
    response = _response(export_environment, "spools", "range=all_time&timezone=Europe%2FLisbon&scope=all")
    headers, rows = _rows(response)
    assert headers[0:4] == ["spool_id", "code", "display_name", "product_name"]
    row = next(item for item in rows if item["code"] == "FIL-ARCHIVED")
    assert row["display_name"].startswith("'=HYPERLINK")
    assert row["product_name"] == "'+SUM(1,2)"
    assert row["color_name"] == "'-cmd"
    assert row["notes"] == "'@danger\nsecond line"
    assert row["purchase_store"] == 'Filamentos Pró, "São João"'
    missing = next(item for item in rows if item["code"] == "FIL-C")
    assert missing["purchase_price"] == ""
    assert missing["purchase_store"] == ""


def test_print_history_is_machine_readable_and_does_not_substitute_missing_duration(export_environment):
    _, rows = _rows(_response(export_environment, "prints"))
    cancelled = next(row for row in rows if row["name"] == "Cancelled manual")
    assert cancelled["actual_duration_seconds"] == ""
    assert cancelled["slicer_estimated_duration_seconds"] == "9999"
    dated = next(row for row in rows if row["started_at"])
    assert dated["started_at"].endswith("+00:00")
    assert " g" not in dated["estimated_filament_g"]


def test_filament_usage_keeps_estimates_pending_and_skipped_separate(export_environment):
    _, rows = _rows(_response(export_environment, "filament_usage"))
    partial = [row for row in rows if row["print_name"] == "Partial multi material"]
    assert [row["reconciliation_status"] for row in partial] == ["CONFIRMED", "PENDING"]
    assert partial[0]["confirmed_consumption_g"] == "230.510"
    assert partial[1]["confirmed_consumption_g"] == ""
    skipped = next(row for row in rows if row["print_name"] == "Explicitly skipped")
    assert skipped["reconciliation_status"] == "SKIPPED"
    assert skipped["estimated_used_g"] == "400.000"
    assert skipped["confirmed_consumption_g"] == ""


def test_confirmed_consumption_exports_only_active_events_once_with_print_date_and_cost(export_environment):
    _, rows = _rows(_response(export_environment, "confirmed_consumption"))
    partial = [row for row in rows if row["print_name"] == "Partial multi material"]
    assert len(partial) == 1
    assert partial[0]["confirmed_consumption_g"] == "230.510"
    assert partial[0]["effective_print_date"].startswith("2026-10-01T22:30:00")
    assert partial[0]["reconciliation_date"].startswith("2026-10-10T20:00:00")
    assert partial[0]["purchase_unit_cost_per_g"] == "0.020000"
    assert partial[0]["estimated_material_cost"] == "4.610200"
    assert not any(row["print_name"] == "Failed reversed" for row in rows)
    rereconciled = [row for row in rows if row["print_name"] == "Re-reconciled once"]
    assert len(rereconciled) == 1
    assert rereconciled[0]["spool_code"] == "FIL-A2"
    assert rereconciled[0]["confirmed_consumption_g"] == "12.000"
    assert not any(row["print_name"] == "Explicitly skipped" for row in rows)


def test_purchase_export_uses_nominal_weight_and_keeps_currency_separate(export_environment):
    _, rows = _rows(_response(export_environment, "purchases"))
    a = next(row for row in rows if row["spool_code"] == "FIL-A")
    assert a["nominal_weight_g"] == "1000.000"
    assert a["price"] == "20.00"
    assert a["currency"] == "EUR"
    assert a["cost_per_g"] == "0.020000"
    assert a["cost_per_kg"] == "20.00"
    currencies = {row["currency"] for row in rows}
    assert {"EUR", "GBP"} <= currencies


def test_ledger_retains_reversals_calibrations_and_legitimate_negative_numbers(export_environment):
    _, rows = _rows(_response(export_environment, "ledger"))
    event_types = {row["event_type"] for row in rows}
    assert "PRINT_CONSUMPTION" in event_types
    assert "PRINT_CONSUMPTION_REVERSAL" in event_types
    assert "PHYSICAL_CALIBRATION" in event_types
    assert "CALIBRATION_REVERSAL" in event_types
    calibration = next(row for row in rows if row["event_type"] == "PHYSICAL_CALIBRATION")
    assert calibration["amount_g"] == "-587.000"
    assert not calibration["amount_g"].startswith("'")


def test_calibration_export_preserves_historical_tare_and_is_not_consumption(export_environment):
    _, calibrations = _rows(_response(export_environment, "calibrations"))
    physical = next(row for row in calibrations if row["event_type"] == "PHYSICAL_CALIBRATION")
    reversal = next(row for row in calibrations if row["event_type"] == "REVERSAL")
    assert physical["tare_g"] == "200.000"
    assert physical["physical_filament_g"] == "700.000"
    assert reversal["reversal_of_calibration_id"] == physical["calibration_id"]
    _, consumption = _rows(_response(export_environment, "confirmed_consumption"))
    assert all(row["confirmed_consumption_g"] != "587.000" for row in consumption)


@pytest.mark.parametrize(
    ("filter_query", "dashboard_query"),
    [
        ("material=PETG", "material=PETG"),
        ("brand=eSUN", "brand=eSUN"),
        ("store=Amazon", "store=Amazon"),
    ],
)
def test_confirmed_consumption_filters_match_dashboard_totals(export_environment, filter_query, dashboard_query):
    _, rows = _rows(_response(export_environment, "confirmed_consumption", f"{CUSTOM_RANGE}&{filter_query}"))
    csv_total = sum((Decimal(row["confirmed_consumption_g"]) for row in rows), Decimal("0"))
    body = export_environment.client.get(f"/api/analytics/dashboard?{CUSTOM_RANGE}&{dashboard_query}").json()
    assert csv_total == Decimal(body["consumption"]["confirmed_g"])


def test_spool_filter_and_all_data_scope(export_environment):
    spool_id = export_environment.spool_ids["a2"]
    _, filtered = _rows(_response(export_environment, "confirmed_consumption", f"{CUSTOM_RANGE}&spool_id={spool_id}"))
    assert filtered and {row["spool_id"] for row in filtered} == {str(spool_id)}

    empty = _response(export_environment, "prints", "range=custom&from=1999-01-01&to=1999-01-02&timezone=UTC")
    _, empty_rows = _rows(empty)
    assert empty_rows == []
    all_data = _response(export_environment, "prints", "range=custom&from=1999-01-01&to=1999-01-02&timezone=UTC&scope=all")
    _, all_rows = _rows(all_data)
    assert all_rows


def test_bucket_and_chart_json_csv_semantic_parity(export_environment):
    csv_response = _response(export_environment, "consumption_over_time", f"{CUSTOM_RANGE}&bucket=week")
    _, csv_rows = _rows(csv_response)
    json_rows = export_environment.client.get(
        f"/api/analytics/consumption-over-time?{CUSTOM_RANGE}&bucket=week"
    ).json()["points"]
    assert csv_rows == json_rows

    _, top_csv = _rows(_response(export_environment, "top_spools"))
    top_json = export_environment.client.get(f"/api/analytics/top-spools?{CUSTOM_RANGE}").json()
    assert [(row["code"], row["consumption_g"]) for row in top_csv] == [
        (row["code"], row["consumption_g"]) for row in top_json
    ]

    _, store_csv = _rows(_response(export_environment, "purchases_by_store"))
    store_json = export_environment.client.get(f"/api/analytics/purchases-by-store?{CUSTOM_RANGE}").json()
    spend_csv = [(row["store"], row["currency"], row["amount"]) for row in store_csv if row["ranking_type"] == "spend"]
    spend_json = [(row["store"], row["currency"], row["amount"]) for row in store_json["by_spend"]]
    assert spend_csv == spend_json


def test_exports_contain_no_credentials_or_configuration_secrets(export_environment):
    combined = ""
    for dataset in (
        "spools", "prints", "filament_usage", "confirmed_consumption",
        "purchases", "ledger", "calibrations",
    ):
        combined += _response(export_environment, dataset, "range=all_time&timezone=UTC&scope=all").text
    lowered = combined.lower()
    for forbidden in ("bambu_access_code", "mqtt_password", "ftps_password", "database_url", "environment variable"):
        assert forbidden not in lowered


def test_export_requests_create_zero_mutations(export_environment):
    def snapshot() -> dict[str, object]:
        with export_environment.factory() as db:
            return {
                "reconciliation": db.scalar(select(func.count()).select_from(PrintJobFilamentReconciliation)),
                "weights": db.scalar(select(func.count()).select_from(WeightHistory)),
                "calibrations": db.scalar(select(func.count()).select_from(SpoolCalibration)),
                "remaining": list(db.execute(select(Spool.id, Spool.current_filament_weight_g).order_by(Spool.id)).all()),
            }

    before = snapshot()
    for dataset in ExportDataset:
        response = _response(export_environment, dataset.value)
        assert response.status_code == 200
    assert snapshot() == before


def test_csv_generator_begins_streaming_before_rows_are_consumed(export_environment):
    with export_environment.factory() as db:
        analytics = AnalyticsService(
            db,
            AnalyticsDateRange.resolve(
                AnalyticsRangePreset.ALL_TIME,
                None,
                None,
                "UTC",
                now=datetime(2026, 10, 12, tzinfo=UTC),
            ),
            AnalyticsFilters(),
        )
        export = CsvExportService(
            db,
            analytics,
            ExportDataset.LEDGER,
            ExportScope.ALL,
            AnalyticsBucket.DAY,
        ).build()
        stream = export.stream()
        assert next(stream) == b"\xef\xbb\xbf"
        assert next(stream).decode().startswith("event_domain,event_id,")
