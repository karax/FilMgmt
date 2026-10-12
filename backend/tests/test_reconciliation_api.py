from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.models import (
    FilamentReconciliationEventType,
    Manufacturer,
    Material,
    PrintJob,
    PrintJobCaptureMode,
    PrintJobEnrichmentStatus,
    PrintJobFilamentReconciliation,
    PrintJobFilamentUsage,
    PrintJobReconciliationStatus,
    PrintJobStatus,
    Spool,
    SpoolStatus,
    WeightHistory,
    WeightSource,
)
from app.schemas.reconciliation import ReconciliationConfirmRequest, ReconciliationUndoRequest
from app.services.reconciliation_service import (
    ReconciliationInsufficientWeightError,
    ReconciliationManualReasonRequiredError,
    ReconciliationService,
)
from app.main import app


def _snapshot(color: str = "000000FF") -> dict[str, object]:
    return {
        "captured_at": "2026-10-05T10:00:00+00:00",
        "current_tray": "1",
        "ams_units": [
            {
                "unit_id": "0",
                "trays": [
                    {
                        "tray_id": "1",
                        "material_type": "PLA+",
                        "color": color,
                        "profile_id": "GFL99",
                        "setting_id": "GFSA99",
                        "brand": "eSUN",
                        "tag_uid": None,
                        "tray_uuid": "tray-1",
                    }
                ],
            }
        ],
        "external_tray": None,
    }


def test_reconciliation_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}
    assert {
        "/api/reconciliation/pending",
        "/api/reconciliation/confirm",
        "/api/reconciliation/usages/{filament_usage_id}/undo",
    } <= paths


@pytest.fixture
def reconciliation_env(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path}/reconciliation.db")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db:
        manufacturer = Manufacturer(name="eSUN")
        pla = Material(name="PLA+", category="PLA")
        petg = Material(name="PETG", category="PETG")
        db.add_all([manufacturer, pla, petg])
        db.flush()
        spools = [
            Spool(
                code="FIL-0017",
                manufacturer_id=manufacturer.id,
                material_id=pla.id,
                color_name="Black",
                color_hex="#000000",
                initial_filament_weight_g=Decimal("1000"),
                current_filament_weight_g=Decimal("423"),
                status=SpoolStatus.OPEN,
            ),
            Spool(
                code="FIL-0031",
                manufacturer_id=manufacturer.id,
                material_id=pla.id,
                color_name="Black",
                color_hex="#000000",
                initial_filament_weight_g=Decimal("1000"),
                current_filament_weight_g=Decimal("812"),
                status=SpoolStatus.OPEN,
            ),
            Spool(
                code="FIL-0042",
                manufacturer_id=manufacturer.id,
                material_id=petg.id,
                color_name="White",
                color_hex="#FFFFFF",
                initial_filament_weight_g=Decimal("1000"),
                current_filament_weight_g=Decimal("100"),
                status=SpoolStatus.OPEN,
            ),
        ]
        db.add_all(spools)
        db.commit()
        spool_ids = [spool.id for spool in spools]

    yield factory, spool_ids
    engine.dispose()


def _pending(factory) -> dict[str, object]:
    with factory() as db:
        return ReconciliationService(db).list_pending().model_dump(mode="json")


def _confirm(factory, payload: dict[str, object]) -> dict[str, object]:
    with factory() as db:
        return ReconciliationService(db).confirm(
            ReconciliationConfirmRequest.model_validate(payload)
        ).model_dump(mode="json")


def _undo(factory, usage_id: int, reason: str) -> dict[str, object]:
    with factory() as db:
        return ReconciliationService(db).undo(
            usage_id, ReconciliationUndoRequest(reason=reason)
        ).model_dump(mode="json")


def _job(
    factory,
    *,
    status: PrintJobStatus = PrintJobStatus.COMPLETED,
    usages: tuple[tuple[str, str, str], ...] = (("PLA+", "000000FF", "74.200"),),
    hours_ago: int = 0,
    name: str = "Desk Robot Head",
) -> tuple[int, list[int]]:
    finished = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    with factory() as db:
        job = PrintJob(
            name=name,
            status=status,
            capture_mode=PrintJobCaptureMode.LIVE,
            enrichment_status=PrintJobEnrichmentStatus.ENRICHED,
            reconciliation_status=(
                PrintJobReconciliationStatus.NEEDS_REVIEW
                if status in {PrintJobStatus.FAILED, PrintJobStatus.CANCELLED}
                else PrintJobReconciliationStatus.PENDING
            ),
            started_at=finished - timedelta(hours=3),
            finished_at=finished,
            duration_seconds=10800,
            final_progress=100 if status is PrintJobStatus.COMPLETED else 37,
            selected_plate_index=2,
            thumbnail_file_name="thumbnail.png",
            ams_snapshot=_snapshot(),
        )
        db.add(job)
        db.flush()
        rows = [
            PrintJobFilamentUsage(
                print_job_id=job.id,
                position=position,
                plate_index=2,
                source_filament_id=str(position + 1),
                material_type=material,
                color=color,
                used_g=Decimal(grams),
                tray_info_idx="GFL99",
            )
            for position, (material, color, grams) in enumerate(usages)
        ]
        db.add_all(rows)
        db.commit()
        return job.id, [row.id for row in rows]


def test_queue_keeps_identical_physical_spools_ambiguous(reconciliation_env):
    factory, _ = reconciliation_env
    job_id, _ = _job(factory)

    body = _pending(factory)
    assert body["pending_job_count"] == 1
    assert body["needs_review_job_count"] == 1
    job = body["jobs"][0]
    assert job["id"] == job_id
    assert job["thumbnail_url"] == f"/api/prints/{job_id}/thumbnail"
    line = job["filaments"][0]
    assert line["recommended_spool_id"] is None
    assert line["unambiguous"] is False
    assert {candidate["code"] for candidate in line["candidates"]} == {
        "FIL-0017",
        "FIL-0031",
    }
    assert {candidate["confidence"] for candidate in line["candidates"]} == {
        "AMBIGUOUS"
    }


def test_confirm_is_atomic_idempotent_and_partial_status_is_derived(reconciliation_env):
    factory, spool_ids = reconciliation_env
    job_id, usage_ids = _job(
        factory,
        usages=(("PLA+", "000000FF", "74.200"), ("PETG", "FFFFFFFF", "8.700")),
    )
    payload = {
        "items": [
            {
                "filament_usage_id": usage_ids[0],
                "action": "DEDUCT",
                "spool_id": spool_ids[0],
                "consumption_g": 74.2,
            }
        ]
    }
    first = _confirm(factory, payload)
    assert first["print_jobs"][0]["reconciliation_status"] == "PARTIALLY_RECONCILED"

    complete = _confirm(
        factory,
        {
            "items": [
                {
                    "filament_usage_id": usage_ids[1],
                    "action": "SKIP",
                    "reason": "Externally supplied sample",
                }
            ]
        },
    )
    assert complete["print_jobs"][0]["reconciliation_status"] == "RECONCILED"

    _confirm(factory, payload)
    with factory() as db:
        assert db.get(Spool, spool_ids[0]).current_filament_weight_g == Decimal("348.800")
        assert db.get(PrintJob, job_id).reconciliation_status is PrintJobReconciliationStatus.RECONCILED
        events = list(db.scalars(select(PrintJobFilamentReconciliation)).all())
        assert len(events) == 2
        assert {event.event_type for event in events} == {
            FilamentReconciliationEventType.CONSUMPTION,
            FilamentReconciliationEventType.SKIP,
        }
        print_weights = list(
            db.scalars(select(WeightHistory).where(WeightHistory.source == WeightSource.PRINT)).all()
        )
        assert len(print_weights) == 1
        assert print_weights[0].notes == f"P1S reconciliation: print #{job_id}, usage #{usage_ids[0]}"


def test_multi_line_insufficient_weight_rolls_back_every_line(reconciliation_env):
    factory, spool_ids = reconciliation_env
    _, usage_ids = _job(
        factory,
        usages=(("PLA+", "000000FF", "20.000"), ("PETG", "FFFFFFFF", "230.510")),
    )
    with pytest.raises(ReconciliationInsufficientWeightError):
        _confirm(factory, {
            "items": [
                {
                    "filament_usage_id": usage_ids[0],
                    "action": "DEDUCT",
                    "spool_id": spool_ids[0],
                    "consumption_g": 20,
                },
                {
                    "filament_usage_id": usage_ids[1],
                    "action": "DEDUCT",
                    "spool_id": spool_ids[2],
                    "consumption_g": 230.510,
                },
            ]
        })
    with factory() as db:
        assert db.get(Spool, spool_ids[0]).current_filament_weight_g == Decimal("423")
        assert db.get(Spool, spool_ids[2]).current_filament_weight_g == Decimal("100")
        assert not list(db.scalars(select(PrintJobFilamentReconciliation)).all())
        assert not list(db.scalars(select(WeightHistory)).all())


def test_incomplete_print_requires_explained_manual_amount(reconciliation_env):
    factory, spool_ids = reconciliation_env
    job_id, usage_ids = _job(factory, status=PrintJobStatus.CANCELLED)
    queue = _pending(factory)
    assert queue["jobs"][0]["reconciliation_status"] == "NEEDS_REVIEW"
    usage = queue["jobs"][0]["filaments"][0]
    assert usage["requires_manual_consumption"] is True
    assert usage["used_g"] == "74.200"
    assert usage["progress_estimated_g"] == "27.454"
    assert queue["estimated_pending_g"] == "27.454"

    with pytest.raises(ReconciliationManualReasonRequiredError):
        _confirm(factory, {
            "items": [
                {
                    "filament_usage_id": usage_ids[0],
                    "action": "DEDUCT",
                    "spool_id": spool_ids[0],
                    "consumption_g": 17,
                }
            ]
        })

    _confirm(
        factory,
        {
            "items": [
                {
                    "filament_usage_id": usage_ids[0],
                    "action": "DEDUCT",
                    "spool_id": spool_ids[0],
                    "consumption_g": 17,
                    "reason": "Cancelled after the base layers",
                }
            ]
        },
    )
    with factory() as db:
        job = db.get(PrintJob, job_id)
        event = db.scalar(select(PrintJobFilamentReconciliation))
        assert job.reconciliation_status is PrintJobReconciliationStatus.RECONCILED
        assert event.manual_override is True
        assert event.sliced_estimated_g == Decimal("74.200")
        assert event.amount_g == Decimal("17.000")


def test_explicit_skip_marks_wholly_skipped_print_not_applicable(reconciliation_env):
    factory, spool_ids = reconciliation_env
    job_id, usage_ids = _job(factory, name="Externally supplied material")

    result = _confirm(
        factory,
        {
            "items": [
                {
                    "filament_usage_id": usage_ids[0],
                    "action": "SKIP",
                    "reason": "Material was supplied outside inventory",
                }
            ]
        },
    )

    assert result["print_jobs"][0]["reconciliation_status"] == "NOT_APPLICABLE"
    queue = _pending(factory)
    assert queue["pending_job_count"] == 0
    assert queue["recently_reconciled_jobs"][0]["id"] == job_id
    with factory() as db:
        assert db.get(PrintJob, job_id).reconciliation_status is PrintJobReconciliationStatus.NOT_APPLICABLE
        assert db.get(Spool, spool_ids[0]).current_filament_weight_g == Decimal("423")
        assert db.scalar(select(PrintJobFilamentReconciliation)).event_type is FilamentReconciliationEventType.SKIP
        assert not list(db.scalars(select(WeightHistory)).all())


def test_undo_adds_reversal_and_restores_stock_without_deleting_audit(reconciliation_env):
    factory, spool_ids = reconciliation_env
    job_id, usage_ids = _job(factory)
    _confirm(
        factory,
        {
            "items": [
                {
                    "filament_usage_id": usage_ids[0],
                    "action": "DEDUCT",
                    "spool_id": spool_ids[0],
                    "consumption_g": 74.2,
                }
            ]
        },
    )

    undone = _undo(factory, usage_ids[0], "Wrong physical spool selected")
    assert undone["reconciliation_status"] == "PENDING"
    _undo(factory, usage_ids[0], "Double click")

    with factory() as db:
        assert db.get(Spool, spool_ids[0]).current_filament_weight_g == Decimal("423.000")
        assert db.get(PrintJob, job_id).reconciliation_status is PrintJobReconciliationStatus.PENDING
        events = list(
            db.scalars(select(PrintJobFilamentReconciliation).order_by(PrintJobFilamentReconciliation.id)).all()
        )
        assert [event.event_type for event in events] == [
            FilamentReconciliationEventType.CONSUMPTION,
            FilamentReconciliationEventType.REVERSAL,
        ]
        assert events[0].reversed_at is not None
        assert events[1].reversed_event_id == events[0].id
        assert [row.source for row in db.scalars(select(WeightHistory).order_by(WeightHistory.id)).all()] == [
            WeightSource.PRINT,
            WeightSource.CORRECTION,
        ]


def test_same_ams_fingerprint_promotes_previous_confirmation(reconciliation_env):
    factory, spool_ids = reconciliation_env
    _, prior_usage_ids = _job(factory, hours_ago=4, name="Earlier print")
    current_job_id, _ = _job(factory, name="Current print")
    _confirm(
        factory,
        {
            "items": [
                {
                    "filament_usage_id": prior_usage_ids[0],
                    "action": "DEDUCT",
                    "spool_id": spool_ids[0],
                    "consumption_g": 74.2,
                }
            ]
        },
    )

    queue = _pending(factory)
    current = next(job for job in queue["jobs"] if job["id"] == current_job_id)
    line = current["filaments"][0]
    assert line["recommended_spool_id"] == spool_ids[0]
    assert line["unambiguous"] is True
    candidate = line["candidates"][0]
    assert candidate["confidence"] == "HIGH"
    assert "SAME_AMS_TRAY_HISTORY" in {reason["code"] for reason in candidate["reasons"]}
