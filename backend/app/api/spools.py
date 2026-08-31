from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    SpoolCreate,
    SpoolFilterParams,
    SpoolRead,
    SpoolUpdate,
    WeightHistoryCreate,
)
from app.services.spool_service import (
    SpoolArchivedUpdateError,
    SpoolDataConflictError,
    SpoolInUseArchiveError,
    SpoolLocationNotFoundError,
    SpoolManufacturerNotFoundError,
    SpoolMaterialNotFoundError,
    SpoolMustBeArchivedError,
    SpoolNotFoundError,
    SpoolService,
    SpoolWeightExceedsInitialError,
)

router = APIRouter(prefix="/spools", tags=["Spools"])

DbSession = Annotated[Session, Depends(get_db)]
SpoolFilters = Annotated[SpoolFilterParams, Query()]

SPOOL_NOT_FOUND_DETAIL = "Spool not found."
MANUFACTURER_NOT_FOUND_DETAIL = "Manufacturer not found."
MATERIAL_NOT_FOUND_DETAIL = "Material not found."
LOCATION_NOT_FOUND_DETAIL = "Location not found."
MUST_ARCHIVE_DETAIL = "Spool must be archived before deletion."
DATA_CONFLICT_DETAIL = "Spool operation conflicts with current data."
SPOOL_IN_USE_ARCHIVE_DETAIL = "Spool in use cannot be archived."
ARCHIVED_UPDATE_DETAIL = "Archived spool cannot be updated."
WEIGHT_EXCEEDS_INITIAL_DETAIL = (
    "Weight cannot exceed the spool's initial filament weight."
)


@router.get("", response_model=list[SpoolRead], status_code=status.HTTP_200_OK)
def list_spools(db: DbSession, filters: SpoolFilters) -> list[SpoolRead]:
    spools = SpoolService(db).list_spools(filters)
    return [SpoolRead.model_validate(item) for item in spools]


@router.post(
    "",
    response_model=SpoolRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Related catalog record not found."
        },
        status.HTTP_409_CONFLICT: {"description": DATA_CONFLICT_DETAIL},
    },
)
def create_spool(payload: SpoolCreate, db: DbSession) -> SpoolRead:
    try:
        spool = SpoolService(db).create_spool(payload)
    except SpoolManufacturerNotFoundError as error:
        raise _not_found(MANUFACTURER_NOT_FOUND_DETAIL) from error
    except SpoolMaterialNotFoundError as error:
        raise _not_found(MATERIAL_NOT_FOUND_DETAIL) from error
    except SpoolLocationNotFoundError as error:
        raise _not_found(LOCATION_NOT_FOUND_DETAIL) from error
    except SpoolDataConflictError as error:
        raise _conflict(DATA_CONFLICT_DETAIL) from error
    return SpoolRead.model_validate(spool)


@router.get(
    "/{code}",
    response_model=SpoolRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": SPOOL_NOT_FOUND_DETAIL}
    },
)
def get_spool(code: str, db: DbSession) -> SpoolRead:
    try:
        spool = SpoolService(db).get_spool_by_code(code)
    except SpoolNotFoundError as error:
        raise _not_found(SPOOL_NOT_FOUND_DETAIL) from error
    return SpoolRead.model_validate(spool)


@router.patch(
    "/{code}",
    response_model=SpoolRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Spool or related catalog record not found."
        },
        status.HTTP_409_CONFLICT: {"description": DATA_CONFLICT_DETAIL},
    },
)
def update_spool(
    code: str,
    payload: SpoolUpdate,
    db: DbSession,
) -> SpoolRead:
    try:
        spool = SpoolService(db).update_spool(code, payload)
    except SpoolNotFoundError as error:
        raise _not_found(SPOOL_NOT_FOUND_DETAIL) from error
    except SpoolManufacturerNotFoundError as error:
        raise _not_found(MANUFACTURER_NOT_FOUND_DETAIL) from error
    except SpoolMaterialNotFoundError as error:
        raise _not_found(MATERIAL_NOT_FOUND_DETAIL) from error
    except SpoolLocationNotFoundError as error:
        raise _not_found(LOCATION_NOT_FOUND_DETAIL) from error
    except SpoolDataConflictError as error:
        raise _conflict(DATA_CONFLICT_DETAIL) from error
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
    return SpoolRead.model_validate(spool)


@router.put("/{code}", response_model=SpoolRead, include_in_schema=False)
def update_spool_legacy(
    code: str,
    payload: SpoolUpdate,
    db: DbSession,
) -> SpoolRead:
    """Temporary backwards compatibility for the original update route."""
    return update_spool(code, payload, db)


@router.post(
    "/{code}/weight",
    response_model=SpoolRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": SPOOL_NOT_FOUND_DETAIL},
        status.HTTP_409_CONFLICT: {"description": ARCHIVED_UPDATE_DETAIL},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Invalid weight measurement."
        },
    },
)
def update_spool_weight(
    code: str,
    payload: WeightHistoryCreate,
    db: DbSession,
) -> SpoolRead:
    try:
        spool = SpoolService(db).update_weight(code, payload)
    except SpoolNotFoundError as error:
        raise _not_found(SPOOL_NOT_FOUND_DETAIL) from error
    except SpoolArchivedUpdateError as error:
        raise _conflict(ARCHIVED_UPDATE_DETAIL) from error
    except SpoolWeightExceedsInitialError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=WEIGHT_EXCEEDS_INITIAL_DETAIL,
        ) from error
    except SpoolDataConflictError as error:
        raise _conflict(DATA_CONFLICT_DETAIL) from error
    return SpoolRead.model_validate(spool)


@router.post(
    "/{code}/archive",
    response_model=SpoolRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": SPOOL_NOT_FOUND_DETAIL},
        status.HTTP_409_CONFLICT: {"description": DATA_CONFLICT_DETAIL},
    },
)
def archive_spool(code: str, db: DbSession) -> SpoolRead:
    try:
        spool = SpoolService(db).archive_spool(code)
    except SpoolNotFoundError as error:
        raise _not_found(SPOOL_NOT_FOUND_DETAIL) from error
    except SpoolInUseArchiveError as error:
        raise _conflict(SPOOL_IN_USE_ARCHIVE_DETAIL) from error
    except SpoolDataConflictError as error:
        raise _conflict(DATA_CONFLICT_DETAIL) from error
    return SpoolRead.model_validate(spool)


@router.delete(
    "/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": SPOOL_NOT_FOUND_DETAIL},
        status.HTTP_409_CONFLICT: {"description": MUST_ARCHIVE_DETAIL},
    },
)
def delete_spool(code: str, db: DbSession) -> Response:
    try:
        SpoolService(db).delete_spool(code)
    except SpoolNotFoundError as error:
        raise _not_found(SPOOL_NOT_FOUND_DETAIL) from error
    except SpoolMustBeArchivedError as error:
        raise _conflict(MUST_ARCHIVE_DETAIL) from error
    except SpoolDataConflictError as error:
        raise _conflict(DATA_CONFLICT_DETAIL) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
