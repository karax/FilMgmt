from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.integrations.bambu.service import BambuIntegration
from app.schemas.bambu import (
    BambuAmsTrayRead,
    BambuAmsUnitRead,
    BambuStatusRead,
)


router = APIRouter(prefix="/integrations/bambu", tags=["Integrations"])


def get_bambu_integration(request: Request) -> BambuIntegration:
    return request.app.state.bambu_integration


BambuService = Annotated[BambuIntegration, Depends(get_bambu_integration)]


@router.get("/status", response_model=BambuStatusRead)
def get_bambu_status(service: BambuService) -> BambuStatusRead:
    diagnostic = service.diagnostic()
    state = diagnostic.state
    return BambuStatusRead(
        configured=diagnostic.configured,
        connected=diagnostic.connected,
        connection_state=state.connection_state,
        missing_configuration=list(diagnostic.missing_configuration),
        configuration_error=diagnostic.configuration_error,
        serial=state.serial,
        last_update_at=state.last_update_at,
        state=state.print_state,
        raw_state=state.raw_print_state,
        progress=state.progress_percent,
        current_layer=state.current_layer,
        total_layers=state.total_layers,
        remaining_time_minutes=state.remaining_time_minutes,
        current_print=state.current_print,
        gcode_file=state.gcode_file,
        project_name=state.project_name,
        project_id=state.project_id,
        profile_id=state.profile_id,
        task_id=state.task_id,
        subtask_id=state.subtask_id,
        current_tray=state.current_tray,
        ams=[BambuAmsUnitRead.model_validate(unit) for unit in state.ams_units],
        external_tray=(
            BambuAmsTrayRead.model_validate(state.external_tray)
            if state.external_tray is not None
            else None
        ),
        active_print_job_id=diagnostic.active_print_job_id,
        ftps_configured=diagnostic.ftps_configured,
        ftps_reachable=diagnostic.ftps_reachable,
        last_ftps_success_at=diagnostic.last_ftps_success_at,
        last_ftps_error_code=diagnostic.last_ftps_error_code,
    )
