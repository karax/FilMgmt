from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import PrintJobCreate, PrintJobFilterParams, PrintJobFinishRequest, PrintJobRead, PrintJobUpdate
from app.services.print_job_service import (
    PrintJobArchivedSpoolError,
    PrintJobDataConflictError,
    PrintJobNotFoundError,
    PrintJobNotPlannedError,
    PrintJobActiveSpoolJobError,
    PrintJobSpoolInUseError,
    PrintJobStartArchivedSpoolError,
    PrintJobStartEmptySpoolError,
    PrintJobFinishArchivedSpoolError,
    PrintJobConsumptionExceedsWeightError,
    PrintJobInvalidCostDataError,
    PrintJobInvalidFinishTimeError,
    PrintJobMissingStartTimeError,
    PrintJobNotPrintingError,
    PrintJobService,
    PrintJobSpoolNotFoundError,
)

router = APIRouter(prefix="/prints", tags=["Prints"])
DbSession = Annotated[Session, Depends(get_db)]
PrintFilters = Annotated[PrintJobFilterParams, Query()]


@router.get("", response_model=list[PrintJobRead])
def list_print_jobs(db: DbSession, filters: PrintFilters) -> list[PrintJobRead]:
    return [PrintJobRead.model_validate(item) for item in PrintJobService(db).list_print_jobs(filters)]


@router.post("", response_model=PrintJobRead, status_code=status.HTTP_201_CREATED)
def create_print_job(payload: PrintJobCreate, db: DbSession) -> PrintJobRead:
    try:
        print_job = PrintJobService(db).create_print_job(payload)
    except PrintJobSpoolNotFoundError as error:
        raise _save_error(404, "spool_not_found", "The selected spool was not found.", error.spool_id) from error
    except PrintJobArchivedSpoolError as error:
        raise _save_error(409, "spool_archived", "Select a spool that is not archived.", error.spool_id) from error
    except PrintJobDataConflictError as error:
        raise _save_error(409, "print_data_conflict", "Review the print and selected spools, then try again.") from error
    return PrintJobRead.model_validate(print_job)


@router.post("/{print_job_id}/start", response_model=PrintJobRead)
def start_print_job(print_job_id: int, db: DbSession) -> PrintJobRead:
    try:
        print_job = PrintJobService(db).start_print_job(print_job_id)
    except PrintJobNotFoundError as error:
        raise _not_found("Print job not found.") from error
    except PrintJobSpoolNotFoundError as error:
        raise _not_found("Spool not found.") from error
    except PrintJobStartArchivedSpoolError as error:
        raise _conflict("Archived spool cannot be used for printing.") from error
    except PrintJobStartEmptySpoolError as error:
        raise _conflict("Empty spool cannot be used for printing.") from error
    except PrintJobSpoolInUseError as error:
        raise _conflict("Spool is already in use.") from error
    except PrintJobActiveSpoolJobError as error:
        raise _conflict("Another print job is already using this spool.") from error
    except PrintJobNotPlannedError as error:
        raise _conflict("Only planned print jobs can be started.") from error
    except PrintJobDataConflictError as error:
        raise _conflict("Print job operation conflicts with current data.") from error
    return PrintJobRead.model_validate(print_job)


@router.post("/{print_job_id}/finish", response_model=PrintJobRead)
def finish_print_job(
    print_job_id: int,
    db: DbSession,
    payload: PrintJobFinishRequest | None = None,
) -> PrintJobRead:
    try:
        print_job = PrintJobService(db).finish_print_job(
            print_job_id,
            payload or PrintJobFinishRequest(),
        )
    except PrintJobNotFoundError as error:
        raise _not_found("Print job not found.") from error
    except PrintJobSpoolNotFoundError as error:
        raise _not_found("Spool not found.") from error
    except PrintJobNotPrintingError as error:
        raise _conflict("Only printing jobs can be finished.") from error
    except PrintJobMissingStartTimeError as error:
        raise _conflict("Printing job has no start time.") from error
    except PrintJobInvalidFinishTimeError as error:
        raise _conflict("Finish time cannot be before start time.") from error
    except PrintJobFinishArchivedSpoolError as error:
        raise _conflict("Archived spool cannot be used for finishing.") from error
    except PrintJobConsumptionExceedsWeightError as error:
        raise _conflict("Print consumption exceeds available spool weight.") from error
    except PrintJobInvalidCostDataError as error:
        raise _conflict("Spool data cannot be used to calculate material cost.") from error
    except PrintJobDataConflictError as error:
        raise _conflict("Print job operation conflicts with current data.") from error
    return PrintJobRead.model_validate(print_job)


@router.get("/{print_job_id}", response_model=PrintJobRead)
def get_print_job(print_job_id: int, db: DbSession) -> PrintJobRead:
    try:
        return PrintJobRead.model_validate(PrintJobService(db).get_print_job(print_job_id))
    except PrintJobNotFoundError as error:
        raise _not_found("Print job not found.") from error


@router.patch("/{print_job_id}", response_model=PrintJobRead)
def update_print_job(print_job_id: int, payload: PrintJobUpdate, db: DbSession) -> PrintJobRead:
    try:
        print_job = PrintJobService(db).update_print_job(print_job_id, payload)
    except PrintJobNotFoundError as error:
        raise _save_error(404, "print_not_found", "This print no longer exists. Return to the print list.") from error
    except PrintJobSpoolNotFoundError as error:
        raise _save_error(404, "spool_not_found", "The selected spool was not found.", error.spool_id) from error
    except PrintJobArchivedSpoolError as error:
        raise _save_error(409, "spool_archived", "Select a spool that is not archived.", error.spool_id) from error
    except PrintJobNotPlannedError as error:
        raise _save_error(409, "print_not_planned", "This print can no longer be edited. Return to the print list.") from error
    except PrintJobDataConflictError as error:
        raise _save_error(409, "print_data_conflict", "Review the print and selected spools, then try again.") from error
    return PrintJobRead.model_validate(print_job)


def _save_error(status_code: int, code: str, message: str, spool_id: int | None = None) -> HTTPException:
    detail: dict[str, str | int] = {"code": code, "message": message}
    if spool_id is not None:
        detail["spool_id"] = spool_id
    return HTTPException(status_code=status_code, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
