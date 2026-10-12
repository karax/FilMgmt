from datetime import UTC, datetime

from app.integrations.bambu.models import (
    BambuLifecycleEvent,
    BambuLifecycleEventType,
    BambuPrinterState,
    BambuPrintState,
)


_ACTIVE_STATES = {
    BambuPrintState.PREPARING,
    BambuPrintState.PRINTING,
    BambuPrintState.PAUSED,
}
_FAILED_STATES = {BambuPrintState.FAILED, BambuPrintState.CANCELLED}


class BambuPrintLifecycleDetector:
    """Derive de-duplicated lifecycle events from normalized snapshots."""

    def __init__(self) -> None:
        self._previous: BambuPrinterState | None = None

    def observe(
        self,
        current: BambuPrinterState,
        *,
        occurred_at: datetime | None = None,
    ) -> tuple[BambuLifecycleEvent, ...]:
        now = occurred_at or current.last_update_at or datetime.now(UTC)
        previous = self._previous
        events: list[BambuLifecycleEvent] = []

        transition = self._transition_event(previous, current)
        if transition is not None:
            event_type, start_observed = transition
            events.append(
                self._event(
                    event_type,
                    current,
                    now,
                    start_observed=start_observed,
                )
            )

        if (
            current.print_state in _ACTIVE_STATES
            and current.progress_percent is not None
            and (previous is None or current.progress_percent != previous.progress_percent)
        ):
            events.append(
                self._event(BambuLifecycleEventType.PRINT_PROGRESS, current, now),
            )

        self._previous = current
        return tuple(events)

    def _transition_event(
        self,
        previous: BambuPrinterState | None,
        current: BambuPrinterState,
    ) -> tuple[BambuLifecycleEventType, bool | None] | None:
        previous_state = previous.print_state if previous else BambuPrintState.UNKNOWN
        current_state = current.print_state

        if current_state is BambuPrintState.PRINTING:
            if previous_state is BambuPrintState.PAUSED:
                return (BambuLifecycleEventType.PRINT_RESUMED, None)
            if previous_state is not BambuPrintState.PRINTING:
                return (
                    BambuLifecycleEventType.PRINT_STARTED,
                    previous is not None
                    and previous_state
                    in {BambuPrintState.IDLE, BambuPrintState.PREPARING},
                )
        if (
            current_state is BambuPrintState.PAUSED
            and previous_state is not BambuPrintState.PAUSED
        ):
            return (BambuLifecycleEventType.PRINT_PAUSED, None)
        if (
            current_state is BambuPrintState.FINISHED
            and previous_state in _ACTIVE_STATES
        ):
            return (BambuLifecycleEventType.PRINT_FINISHED, None)
        if current_state in _FAILED_STATES and previous_state in _ACTIVE_STATES:
            return (BambuLifecycleEventType.PRINT_ABORTED_OR_FAILED, None)
        if (
            current_state is BambuPrintState.IDLE
            and previous_state in _ACTIVE_STATES
        ):
            return (BambuLifecycleEventType.PRINT_ABORTED_OR_FAILED, None)
        return None

    def _event(
        self,
        event_type: BambuLifecycleEventType,
        state: BambuPrinterState,
        occurred_at: datetime,
        *,
        start_observed: bool | None = None,
    ) -> BambuLifecycleEvent:
        return BambuLifecycleEvent(
            event_type=event_type,
            occurred_at=occurred_at,
            print_state=state.print_state,
            raw_print_state=state.raw_print_state,
            current_print=state.current_print,
            progress_percent=state.progress_percent,
            start_observed=start_observed,
        )
