from dataclasses import fields, replace
from datetime import UTC, datetime
from threading import RLock

from app.integrations.bambu.models import (
    BambuAmsTray,
    BambuAmsUnit,
    BambuAmsUnitPatch,
    BambuConnectionState,
    BambuPrinterState,
    BambuStatePatch,
    BambuTrayPatch,
)


_STATE_PATCH_FIELDS = {
    field.name
    for field in fields(BambuPrinterState)
    if field.name not in {"connection_state", "serial", "ams_units", "external_tray", "last_update_at"}
}
_UNIT_PATCH_FIELDS = {"humidity", "temperature_c"}
_TRAY_PATCH_FIELDS = {
    field.name for field in fields(BambuAmsTray) if field.name != "tray_id"
}


class BambuStateStore:
    """Thread-safe in-memory state assembled from partial report messages."""

    def __init__(self, serial: str | None, *, configured: bool) -> None:
        initial_connection = (
            BambuConnectionState.DISCONNECTED
            if configured
            else BambuConnectionState.DISABLED
        )
        self._state = BambuPrinterState(
            connection_state=initial_connection,
            serial=serial,
        )
        self._lock = RLock()

    def snapshot(self) -> BambuPrinterState:
        with self._lock:
            return self._state

    def set_connection(self, state: BambuConnectionState) -> BambuPrinterState:
        with self._lock:
            self._state = replace(self._state, connection_state=state)
            return self._state

    def merge(
        self,
        patch: BambuStatePatch,
        *,
        received_at: datetime | None = None,
    ) -> BambuPrinterState:
        timestamp = received_at or datetime.now(UTC)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        else:
            timestamp = timestamp.astimezone(UTC)

        with self._lock:
            scalar_updates = {
                name: value
                for name, value in patch.values.items()
                if name in _STATE_PATCH_FIELDS
            }
            ams_units = self._merge_units(self._state.ams_units, patch.ams_units)
            external_tray = self._state.external_tray
            if patch.external_tray is not None:
                external_tray = self._merge_tray(external_tray, patch.external_tray)

            self._state = replace(
                self._state,
                **scalar_updates,
                ams_units=ams_units,
                external_tray=external_tray,
                last_update_at=timestamp,
            )
            return self._state

    def _merge_units(
        self,
        current: tuple[BambuAmsUnit, ...],
        patches: tuple[BambuAmsUnitPatch, ...],
    ) -> tuple[BambuAmsUnit, ...]:
        if not patches:
            return current
        units = {unit.unit_id: unit for unit in current}
        for patch in patches:
            unit = units.get(patch.unit_id, BambuAmsUnit(unit_id=patch.unit_id))
            unit_updates = {
                name: value
                for name, value in patch.values.items()
                if name in _UNIT_PATCH_FIELDS
            }
            trays = self._merge_trays(unit.trays, patch.trays)
            units[patch.unit_id] = replace(unit, **unit_updates, trays=trays)
        return tuple(units[key] for key in sorted(units, key=_identifier_sort_key))

    def _merge_trays(
        self,
        current: tuple[BambuAmsTray, ...],
        patches: tuple[BambuTrayPatch, ...],
    ) -> tuple[BambuAmsTray, ...]:
        if not patches:
            return current
        trays = {tray.tray_id: tray for tray in current}
        for patch in patches:
            trays[patch.tray_id] = self._merge_tray(trays.get(patch.tray_id), patch)
        return tuple(trays[key] for key in sorted(trays, key=_identifier_sort_key))

    def _merge_tray(
        self,
        current: BambuAmsTray | None,
        patch: BambuTrayPatch,
    ) -> BambuAmsTray:
        tray = current or BambuAmsTray(tray_id=patch.tray_id)
        updates = {
            name: value
            for name, value in patch.values.items()
            if name in _TRAY_PATCH_FIELDS
        }
        return replace(tray, **updates)


def _identifier_sort_key(value: str) -> tuple[int, int | str]:
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)
