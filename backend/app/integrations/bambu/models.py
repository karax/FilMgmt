from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class BambuConnectionState(StrEnum):
    DISABLED = "DISABLED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


class BambuPrintState(StrEnum):
    UNKNOWN = "UNKNOWN"
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    PRINTING = "PRINTING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BambuLifecycleEventType(StrEnum):
    PRINT_STARTED = "PRINT_STARTED"
    PRINT_PROGRESS = "PRINT_PROGRESS"
    PRINT_PAUSED = "PRINT_PAUSED"
    PRINT_RESUMED = "PRINT_RESUMED"
    PRINT_FINISHED = "PRINT_FINISHED"
    PRINT_ABORTED_OR_FAILED = "PRINT_ABORTED_OR_FAILED"


@dataclass(frozen=True)
class BambuAmsTray:
    tray_id: str
    material_type: str | None = None
    color: str | None = None
    profile_id: str | None = None
    setting_id: str | None = None
    brand: str | None = None
    tag_uid: str | None = None
    tray_uuid: str | None = None
    remaining_percent: int | None = None
    nozzle_temp_min: int | None = None
    nozzle_temp_max: int | None = None


@dataclass(frozen=True)
class BambuAmsUnit:
    unit_id: str
    humidity: int | None = None
    temperature_c: float | None = None
    trays: tuple[BambuAmsTray, ...] = ()


@dataclass(frozen=True)
class BambuPrinterState:
    connection_state: BambuConnectionState
    serial: str | None
    print_state: BambuPrintState = BambuPrintState.UNKNOWN
    raw_print_state: str | None = None
    current_print: str | None = None
    gcode_file: str | None = None
    project_name: str | None = None
    project_id: str | None = None
    profile_id: str | None = None
    task_id: str | None = None
    subtask_id: str | None = None
    progress_percent: int | None = None
    current_layer: int | None = None
    total_layers: int | None = None
    remaining_time_minutes: int | None = None
    current_tray: str | None = None
    ams_units: tuple[BambuAmsUnit, ...] = ()
    external_tray: BambuAmsTray | None = None
    last_update_at: datetime | None = None


@dataclass(frozen=True)
class BambuTrayPatch:
    tray_id: str
    values: dict[str, object | None] = field(default_factory=dict)


@dataclass(frozen=True)
class BambuAmsUnitPatch:
    unit_id: str
    values: dict[str, object | None] = field(default_factory=dict)
    trays: tuple[BambuTrayPatch, ...] = ()


@dataclass(frozen=True)
class BambuStatePatch:
    values: dict[str, object | None] = field(default_factory=dict)
    ams_units: tuple[BambuAmsUnitPatch, ...] = ()
    external_tray: BambuTrayPatch | None = None


@dataclass(frozen=True)
class BambuLifecycleEvent:
    event_type: BambuLifecycleEventType
    occurred_at: datetime
    print_state: BambuPrintState
    raw_print_state: str | None
    current_print: str | None
    progress_percent: int | None
    start_observed: bool | None = None
