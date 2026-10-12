from pydantic import BaseModel, ConfigDict

from app.integrations.bambu.models import BambuConnectionState, BambuPrintState
from app.schemas.common import UtcDatetime


class BambuAmsTrayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    tray_id: str
    material_type: str | None
    color: str | None
    profile_id: str | None
    setting_id: str | None
    brand: str | None
    tag_uid: str | None
    tray_uuid: str | None
    remaining_percent: int | None
    nozzle_temp_min: int | None
    nozzle_temp_max: int | None


class BambuAmsUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    unit_id: str
    humidity: int | None
    temperature_c: float | None
    trays: list[BambuAmsTrayRead]


class BambuStatusRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    connected: bool
    connection_state: BambuConnectionState
    missing_configuration: list[str]
    configuration_error: str | None
    serial: str | None
    last_update_at: UtcDatetime | None
    state: BambuPrintState
    raw_state: str | None
    progress: int | None
    current_layer: int | None
    total_layers: int | None
    remaining_time_minutes: int | None
    current_print: str | None
    gcode_file: str | None
    project_name: str | None
    project_id: str | None
    profile_id: str | None
    task_id: str | None
    subtask_id: str | None
    current_tray: str | None
    ams: list[BambuAmsUnitRead]
    external_tray: BambuAmsTrayRead | None
    active_print_job_id: int | None
    ftps_configured: bool
    ftps_reachable: bool | None
    last_ftps_success_at: UtcDatetime | None
    last_ftps_error_code: str | None
