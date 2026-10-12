from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.reconciliation import (
    ReconciliationConfirmRequest,
    ReconciliationConfirmResult,
    ReconciliationJobRead,
    ReconciliationQueueRead,
    ReconciliationUndoRequest,
)
from app.services.reconciliation_service import (
    ReconciliationConflictError,
    ReconciliationCheckpointAcknowledgementRequiredError,
    ReconciliationInsufficientWeightError,
    ReconciliationInvalidSpoolError,
    ReconciliationManualReasonRequiredError,
    ReconciliationNotFoundError,
    ReconciliationService,
)


router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/pending", response_model=ReconciliationQueueRead)
def list_pending_reconciliation(db: DbSession) -> ReconciliationQueueRead:
    return ReconciliationService(db).list_pending()


@router.post("/confirm", response_model=ReconciliationConfirmResult)
def confirm_reconciliation(
    payload: ReconciliationConfirmRequest,
    db: DbSession,
) -> ReconciliationConfirmResult:
    try:
        return ReconciliationService(db).confirm(payload)
    except ReconciliationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Filament usage not found.") from error
    except ReconciliationInvalidSpoolError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "spool_unavailable",
                "message": "The selected spool is unavailable.",
                "spool_id": error.spool_id,
            },
        ) from error
    except ReconciliationInsufficientWeightError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "insufficient_weight",
                "message": "Consumption exceeds the selected spool's remaining weight.",
                "spool_id": error.spool_id,
            },
        ) from error
    except ReconciliationManualReasonRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "manual_reason_required",
                "message": "Explain manual consumption for an incomplete or adjusted print.",
            },
        ) from error
    except ReconciliationCheckpointAcknowledgementRequiredError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "physical_checkpoint_acknowledgement_required",
                "message": (
                    "This print predates the selected spool's latest physical calibration; "
                    "its consumption may already be represented by that checkpoint."
                ),
                "spool_id": error.spool_id,
                "calibration_at": error.calibration_at.isoformat(),
            },
        ) from error
    except ReconciliationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "reconciliation_conflict",
                "message": "Reconciliation changed or could not be applied atomically.",
            },
        ) from error


@router.post(
    "/usages/{filament_usage_id}/undo",
    response_model=ReconciliationJobRead,
)
def undo_reconciliation(
    filament_usage_id: int,
    payload: ReconciliationUndoRequest,
    db: DbSession,
) -> ReconciliationJobRead:
    try:
        return ReconciliationService(db).undo(filament_usage_id, payload)
    except ReconciliationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Filament usage not found.") from error
    except ReconciliationConflictError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "reversal_conflict",
                "message": "The reconciliation could not be reversed safely.",
            },
        ) from error
