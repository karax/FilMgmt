from dataclasses import replace
from datetime import UTC, datetime

from app.integrations.bambu.lifecycle import BambuPrintLifecycleDetector
from app.integrations.bambu.models import (
    BambuConnectionState,
    BambuLifecycleEventType,
    BambuPrinterState,
    BambuPrintState,
)


NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def state(
    print_state: BambuPrintState,
    *,
    progress: int | None = None,
) -> BambuPrinterState:
    return BambuPrinterState(
        connection_state=BambuConnectionState.CONNECTED,
        serial="01P00TESTSERIAL",
        print_state=print_state,
        raw_print_state=print_state.value,
        current_print="Calibration Cube",
        progress_percent=progress,
        last_update_at=NOW,
    )


def event_types(events) -> list[BambuLifecycleEventType]:
    return [event.event_type for event in events]


def test_print_lifecycle_transitions_and_progress_are_detected() -> None:
    detector = BambuPrintLifecycleDetector()

    assert detector.observe(state(BambuPrintState.IDLE)) == ()
    assert detector.observe(state(BambuPrintState.PREPARING)) == ()
    assert event_types(detector.observe(state(BambuPrintState.PRINTING, progress=1))) == [
        BambuLifecycleEventType.PRINT_STARTED,
        BambuLifecycleEventType.PRINT_PROGRESS,
    ]
    assert event_types(detector.observe(state(BambuPrintState.PRINTING, progress=2))) == [
        BambuLifecycleEventType.PRINT_PROGRESS,
    ]
    assert event_types(detector.observe(state(BambuPrintState.PAUSED, progress=2))) == [
        BambuLifecycleEventType.PRINT_PAUSED,
    ]
    assert event_types(detector.observe(state(BambuPrintState.PRINTING, progress=2))) == [
        BambuLifecycleEventType.PRINT_RESUMED,
    ]
    assert event_types(detector.observe(state(BambuPrintState.FINISHED, progress=100))) == [
        BambuLifecycleEventType.PRINT_FINISHED,
    ]


def test_repeated_identical_states_do_not_emit_duplicate_events() -> None:
    detector = BambuPrintLifecycleDetector()
    printing = state(BambuPrintState.PRINTING, progress=42)

    assert detector.observe(printing)
    assert detector.observe(printing) == ()
    assert detector.observe(replace(printing, last_update_at=datetime.now(UTC))) == ()


def test_start_event_distinguishes_live_transition_from_recovery() -> None:
    live = BambuPrintLifecycleDetector()
    live.observe(state(BambuPrintState.PREPARING))
    live_event = live.observe(state(BambuPrintState.PRINTING, progress=1))[0]
    assert live_event.event_type is BambuLifecycleEventType.PRINT_STARTED
    assert live_event.start_observed is True

    recovered = BambuPrintLifecycleDetector()
    recovered_event = recovered.observe(state(BambuPrintState.PRINTING, progress=42))[0]
    assert recovered_event.event_type is BambuLifecycleEventType.PRINT_STARTED
    assert recovered_event.start_observed is False


def test_failed_and_cancelled_active_prints_emit_abort_event() -> None:
    for terminal_state in (BambuPrintState.FAILED, BambuPrintState.CANCELLED):
        detector = BambuPrintLifecycleDetector()
        detector.observe(state(BambuPrintState.PRINTING, progress=50))

        events = detector.observe(state(terminal_state, progress=50))

        assert event_types(events) == [
            BambuLifecycleEventType.PRINT_ABORTED_OR_FAILED,
        ]


def test_active_print_returning_directly_to_idle_emits_abort_event() -> None:
    detector = BambuPrintLifecycleDetector()
    detector.observe(state(BambuPrintState.PRINTING, progress=50))

    events = detector.observe(state(BambuPrintState.IDLE, progress=50))

    assert event_types(events) == [
        BambuLifecycleEventType.PRINT_ABORTED_OR_FAILED,
    ]
