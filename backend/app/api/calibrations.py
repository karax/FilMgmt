from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.calibration import (
    CalibrationConfirmRequest,
    CalibrationPreviewRead,
    CalibrationPreviewRequest,
    CalibrationRead,
    CalibrationUndoRequest,
    EmptySpoolMeasurementCreate,
    EmptySpoolMeasurementRead,
)
from app.services.calibration_service import (
    CalibrationConflictError,
    CalibrationNotFoundError,
    CalibrationService,
    CalibrationStalePreviewError,
    CalibrationValidationError,
    TareProfileNotFoundError,
)


router = APIRouter(prefix="/spools/{code}", tags=["Spool calibration"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/calibrations/preview", response_model=CalibrationPreviewRead)
def preview_calibration(
    code: str, payload: CalibrationPreviewRequest, db: DbSession
) -> CalibrationPreviewRead:
    try:
        return CalibrationService(db).preview(code, payload)
    except CalibrationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Spool not found.") from error
    except TareProfileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Tare profile not found.") from error
    except CalibrationConflictError as error:
        raise HTTPException(status_code=409, detail="Spool cannot be calibrated.") from error
    except CalibrationValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_calibration", "message": error.message},
        ) from error


@router.post(
    "/calibrations", response_model=CalibrationRead, status_code=status.HTTP_201_CREATED
)
def confirm_calibration(
    code: str, payload: CalibrationConfirmRequest, db: DbSession
) -> CalibrationRead:
    try:
        return CalibrationService(db).confirm(code, payload)
    except CalibrationStalePreviewError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_calibration_preview",
                "message": "Inventory changed after the preview. Review the updated adjustment.",
                "preview": error.preview.model_dump(mode="json"),
            },
        ) from error
    except CalibrationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Spool not found.") from error
    except TareProfileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Tare profile not found.") from error
    except CalibrationValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_calibration", "message": error.message},
        ) from error
    except CalibrationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calibration_conflict",
                "message": "Calibration could not be applied atomically.",
            },
        ) from error


@router.get("/calibrations", response_model=list[CalibrationRead])
def list_calibrations(code: str, db: DbSession) -> list[CalibrationRead]:
    try:
        return CalibrationService(db).list_calibrations(code)
    except CalibrationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Spool not found.") from error


@router.post("/calibrations/{calibration_id}/undo", response_model=CalibrationRead)
def undo_calibration(
    code: str,
    calibration_id: int,
    payload: CalibrationUndoRequest,
    db: DbSession,
) -> CalibrationRead:
    try:
        return CalibrationService(db).undo(code, calibration_id, payload)
    except CalibrationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Calibration not found.") from error
    except CalibrationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calibration_reversal_conflict",
                "message": "Undo would overwrite later inventory activity.",
            },
        ) from error


@router.post(
    "/empty-spool-measurements",
    response_model=EmptySpoolMeasurementRead,
    status_code=status.HTTP_201_CREATED,
)
def record_empty_spool_measurement(
    code: str, payload: EmptySpoolMeasurementCreate, db: DbSession
) -> EmptySpoolMeasurementRead:
    try:
        return CalibrationService(db).record_empty_spool(code, payload)
    except CalibrationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Spool not found.") from error
    except TareProfileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Tare profile not found.") from error
    except CalibrationConflictError as error:
        raise HTTPException(status_code=409, detail="Measurement could not be saved.") from error
