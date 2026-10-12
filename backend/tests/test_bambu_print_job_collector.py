from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.integrations.bambu.lifecycle import BambuPrintLifecycleDetector
from app.integrations.bambu.models import (
    BambuAmsTray,
    BambuAmsUnit,
    BambuConnectionState,
    BambuPrinterState,
    BambuPrintState,
)
from app.integrations.bambu.print_job_collector import BambuPrintJobCollector
from app.models import (
    Manufacturer,
    Material,
    PrintJob,
    PrintJobCaptureMode,
    PrintJobReconciliationStatus,
    PrintJobStatus,
    Spool,
)


START = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
def database(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'history.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    yield factory
    engine.dispose()


def printer_state(
    print_state: BambuPrintState,
    *,
    at: datetime = START,
    progress: int | None = None,
    layer: int | None = None,
    task_id: str | None = "task-56",
    subtask_id: str | None = "subtask-78",
    ams_material: str = "PLA",
    ams_color: str = "FF0000FF",
) -> BambuPrinterState:
    tray = BambuAmsTray(
        tray_id="0",
        material_type=ams_material,
        color=ams_color,
        profile_id="GFA00",
        setting_id="GFSA00_01",
        brand="Bambu PLA Basic",
        tag_uid="AABBCCDDEEFF0011",
        tray_uuid="tray-uuid-0",
        remaining_percent=87,
    )
    return BambuPrinterState(
        connection_state=BambuConnectionState.CONNECTED,
        serial="01P00TESTSERIAL",
        print_state=print_state,
        raw_print_state=print_state.value,
        current_print="Calibration Cube",
        gcode_file="/data/Metadata/calibration_cube.gcode",
        project_name="Calibration Project",
        project_id="project-12",
        profile_id="profile-34",
        task_id=task_id,
        subtask_id=subtask_id,
        progress_percent=progress,
        current_layer=layer,
        total_layers=166,
        remaining_time_minutes=38,
        current_tray="0",
        ams_units=(BambuAmsUnit(unit_id="0", humidity=3, temperature_c=24.5, trays=(tray,)),),
        last_update_at=at,
    )


def observe(
    collector: BambuPrintJobCollector,
    detector: BambuPrintLifecycleDetector,
    state: BambuPrinterState,
) -> None:
    collector.collect(state, detector.observe(state, occurred_at=state.last_update_at))


def all_jobs(factory) -> list[PrintJob]:
    with factory() as db:
        return list(
            db.scalars(
                select(PrintJob)
                .options(selectinload(PrintJob.spool_links))
                .order_by(PrintJob.id)
            ).all()
        )


def test_live_lifecycle_updates_one_job_and_freezes_ams_snapshot(database) -> None:
    collector = BambuPrintJobCollector(database)
    detector = BambuPrintLifecycleDetector()
    observe(collector, detector, printer_state(BambuPrintState.IDLE))
    started = printer_state(BambuPrintState.PRINTING, progress=1, layer=1, at=START + timedelta(seconds=10))

    observe(collector, detector, started)
    observe(collector, detector, started)

    jobs = all_jobs(database)
    assert len(jobs) == 1
    job_id = jobs[0].id
    assert jobs[0].capture_mode is PrintJobCaptureMode.LIVE
    assert jobs[0].started_at is not None
    assert jobs[0].finished_at is None
    assert jobs[0].start_progress == 1
    assert jobs[0].start_layer == 1
    assert jobs[0].ams_snapshot["current_tray"] == "0"
    assert jobs[0].ams_snapshot["ams_units"][0]["trays"][0]["material_type"] == "PLA"

    changed_ams = printer_state(
        BambuPrintState.PRINTING,
        progress=42,
        layer=71,
        at=START + timedelta(minutes=10),
        ams_material="PETG",
        ams_color="0000FFFF",
    )
    observe(collector, detector, changed_ams)
    observe(
        collector,
        detector,
        replace(changed_ams, print_state=BambuPrintState.PAUSED, raw_print_state="PAUSE"),
    )
    paused = all_jobs(database)[0]
    assert paused.id == job_id
    assert paused.status is PrintJobStatus.PAUSED
    assert paused.finished_at is None
    assert paused.final_progress == 42
    assert paused.final_layer == 71
    assert paused.ams_snapshot["ams_units"][0]["trays"][0]["material_type"] == "PLA"

    resumed = replace(
        changed_ams,
        print_state=BambuPrintState.PRINTING,
        raw_print_state="RUNNING",
        last_update_at=START + timedelta(minutes=11),
    )
    observe(collector, detector, resumed)
    assert all_jobs(database)[0].status is PrintJobStatus.PRINTING

    finished = replace(
        resumed,
        print_state=BambuPrintState.FINISHED,
        raw_print_state="FINISH",
        progress_percent=100,
        current_layer=166,
        remaining_time_minutes=0,
        last_update_at=START + timedelta(minutes=20),
    )
    observe(collector, detector, finished)
    observe(collector, detector, finished)

    completed = all_jobs(database)
    assert len(completed) == 1
    assert completed[0].id == job_id
    assert completed[0].status is PrintJobStatus.COMPLETED
    assert completed[0].finished_at is not None
    assert completed[0].final_progress == 100
    assert completed[0].final_layer == 166
    assert completed[0].duration_seconds == 1190
    assert completed[0].reconciliation_status is PrintJobReconciliationStatus.PENDING
    assert completed[0].spool_links == []
    assert collector.active_print_job_id is None


@pytest.mark.parametrize(
    ("printer_status", "job_status", "reconciliation"),
    [
        (BambuPrintState.CANCELLED, PrintJobStatus.CANCELLED, PrintJobReconciliationStatus.NEEDS_REVIEW),
        (BambuPrintState.FAILED, PrintJobStatus.FAILED, PrintJobReconciliationStatus.NEEDS_REVIEW),
        (BambuPrintState.IDLE, PrintJobStatus.UNKNOWN_TERMINAL, PrintJobReconciliationStatus.NEEDS_REVIEW),
    ],
)
def test_terminal_outcomes_are_mapped_without_guessing(
    database,
    printer_status,
    job_status,
    reconciliation,
) -> None:
    collector = BambuPrintJobCollector(database)
    detector = BambuPrintLifecycleDetector()
    observe(collector, detector, printer_state(BambuPrintState.IDLE))
    observe(collector, detector, printer_state(BambuPrintState.PRINTING, progress=10))
    observe(
        collector,
        detector,
        printer_state(
            printer_status,
            progress=10,
            at=START + timedelta(minutes=1),
        ),
    )

    job = all_jobs(database)[0]
    assert job.status is job_status
    assert job.finished_at is not None
    assert job.reconciliation_status is reconciliation


def test_terminal_partial_report_preserves_known_file_metadata(database) -> None:
    collector = BambuPrintJobCollector(database)
    detector = BambuPrintLifecycleDetector()
    observe(collector, detector, printer_state(BambuPrintState.IDLE))
    observe(collector, detector, printer_state(BambuPrintState.PRINTING, progress=10))

    terminal = replace(
        printer_state(
            BambuPrintState.FINISHED,
            progress=100,
            at=START + timedelta(minutes=20),
        ),
        current_print="",
        gcode_file="",
    )
    observe(collector, detector, terminal)

    job = all_jobs(database)[0]
    assert job.name == "Calibration Cube"
    assert job.gcode_file == "/data/Metadata/calibration_cube.gcode"


def test_mid_print_recovery_does_not_invent_start_time(database) -> None:
    collector = BambuPrintJobCollector(database)
    detector = BambuPrintLifecycleDetector()

    observe(
        collector,
        detector,
        printer_state(BambuPrintState.PRINTING, progress=52, layer=80),
    )

    job = all_jobs(database)[0]
    assert job.capture_mode is PrintJobCaptureMode.RECOVERED
    assert job.started_at is None
    assert job.start_progress == 52
    assert job.start_layer == 80
    assert job.finished_at is None


def test_restart_reuses_active_job_and_completed_history_survives(database) -> None:
    first_collector = BambuPrintJobCollector(database)
    first_detector = BambuPrintLifecycleDetector()
    observe(first_collector, first_detector, printer_state(BambuPrintState.IDLE))
    observe(first_collector, first_detector, printer_state(BambuPrintState.PRINTING, progress=5))
    original = all_jobs(database)[0]

    restarted_collector = BambuPrintJobCollector(database)
    restarted_detector = BambuPrintLifecycleDetector()
    observe(
        restarted_collector,
        restarted_detector,
        printer_state(BambuPrintState.PRINTING, progress=20, at=START + timedelta(minutes=5)),
    )
    after_restart = all_jobs(database)
    assert len(after_restart) == 1
    assert after_restart[0].id == original.id
    assert after_restart[0].capture_mode is PrintJobCaptureMode.LIVE
    assert after_restart[0].final_progress == 20

    observe(
        restarted_collector,
        restarted_detector,
        printer_state(BambuPrintState.FINISHED, progress=100, layer=166, at=START + timedelta(minutes=9)),
    )
    third_collector = BambuPrintJobCollector(database)
    third_detector = BambuPrintLifecycleDetector()
    observe(
        third_collector,
        third_detector,
        printer_state(BambuPrintState.FINISHED, progress=100, layer=166, at=START + timedelta(minutes=10)),
    )
    history = all_jobs(database)
    assert len(history) == 1
    assert history[0].status is PrintJobStatus.COMPLETED


def test_new_identity_closes_stale_active_job_conservatively(database) -> None:
    first = BambuPrintJobCollector(database)
    detector = BambuPrintLifecycleDetector()
    observe(first, detector, printer_state(BambuPrintState.IDLE))
    observe(first, detector, printer_state(BambuPrintState.PRINTING, progress=25))

    restarted = BambuPrintJobCollector(database)
    observe(
        restarted,
        BambuPrintLifecycleDetector(),
        printer_state(
            BambuPrintState.PRINTING,
            progress=3,
            task_id="task-new",
            subtask_id="subtask-new",
            at=START + timedelta(days=1),
        ),
    )

    old_job, new_job = all_jobs(database)
    assert old_job.status is PrintJobStatus.UNKNOWN_TERMINAL
    assert old_job.task_id == "task-56"
    assert old_job.reconciliation_status is PrintJobReconciliationStatus.NEEDS_REVIEW
    assert new_job.status is PrintJobStatus.PRINTING
    assert new_job.capture_mode is PrintJobCaptureMode.RECOVERED
    assert new_job.task_id == "task-new"


def test_late_partial_identity_fields_enrich_same_job(database) -> None:
    collector = BambuPrintJobCollector(database)
    detector = BambuPrintLifecycleDetector()
    observe(collector, detector, printer_state(BambuPrintState.IDLE, task_id=None, subtask_id=None))
    observe(
        collector,
        detector,
        printer_state(BambuPrintState.PRINTING, progress=1, task_id="task-56", subtask_id=None),
    )
    original_id = all_jobs(database)[0].id
    observe(
        collector,
        detector,
        printer_state(BambuPrintState.PRINTING, progress=2, task_id="task-56", subtask_id="subtask-78"),
    )

    jobs = all_jobs(database)
    assert len(jobs) == 1
    assert jobs[0].id == original_id
    assert jobs[0].subtask_id == "subtask-78"
    assert jobs[0].bambu_identity_key == "task=task-56|subtask=subtask-78"


def test_progress_only_report_can_update_persisted_active_job_after_restart(database) -> None:
    first = BambuPrintJobCollector(database)
    detector = BambuPrintLifecycleDetector()
    observe(first, detector, printer_state(BambuPrintState.IDLE))
    observe(first, detector, printer_state(BambuPrintState.PRINTING, progress=5))

    restarted = BambuPrintJobCollector(database)
    progress_only = printer_state(
        BambuPrintState.UNKNOWN,
        progress=8,
        layer=12,
        at=START + timedelta(minutes=2),
    )
    observe(restarted, BambuPrintLifecycleDetector(), progress_only)

    job = all_jobs(database)[0]
    assert job.status is PrintJobStatus.PRINTING
    assert job.final_progress == 8
    assert job.final_layer == 12


def test_active_bambu_job_database_constraint_prevents_duplicates(database) -> None:
    with database() as db:
        db.add_all(
            [
                PrintJob(
                    name="A",
                    status=PrintJobStatus.PRINTING,
                    printer_serial="01P00TESTSERIAL",
                    capture_mode=PrintJobCaptureMode.LIVE,
                ),
                PrintJob(
                    name="B",
                    status=PrintJobStatus.PAUSED,
                    printer_serial="01P00TESTSERIAL",
                    capture_mode=PrintJobCaptureMode.RECOVERED,
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_automatic_collection_never_changes_spool_inventory(database) -> None:
    with database() as db:
        manufacturer = Manufacturer(name="eSUN")
        material = Material(name="PLA", category="PLA")
        db.add_all([manufacturer, material])
        db.flush()
        spool = Spool(
            code="FIL-0001",
            manufacturer_id=manufacturer.id,
            material_id=material.id,
            color_name="Black",
            initial_filament_weight_g=1000,
            current_filament_weight_g=750,
        )
        db.add(spool)
        db.commit()
        spool_id = spool.id

    collector = BambuPrintJobCollector(database)
    detector = BambuPrintLifecycleDetector()
    observe(collector, detector, printer_state(BambuPrintState.IDLE))
    observe(collector, detector, printer_state(BambuPrintState.PRINTING, progress=1))
    observe(collector, detector, printer_state(BambuPrintState.FINISHED, progress=100))

    with database() as db:
        spool = db.get(Spool, spool_id)
        assert spool.current_filament_weight_g == 750
        assert db.scalar(select(PrintJob)).spool_links == []
