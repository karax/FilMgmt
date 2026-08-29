from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import ManufacturerCreate, ManufacturerRead, ManufacturerUpdate
from app.services.manufacturer_service import (
    ManufacturerInUseError,
    ManufacturerNameConflictError,
    ManufacturerNotFoundError,
    ManufacturerService,
)

router = APIRouter(prefix="/manufacturers", tags=["Manufacturers"])

DbSession = Annotated[Session, Depends(get_db)]

NOT_FOUND_DETAIL = "Manufacturer not found."
NAME_CONFLICT_DETAIL = "Manufacturer with this name already exists."
IN_USE_DETAIL = "Manufacturer is in use and cannot be deleted."


@router.get("", response_model=list[ManufacturerRead], status_code=status.HTTP_200_OK)
def list_manufacturers(db: DbSession) -> list[ManufacturerRead]:
    manufacturers = ManufacturerService(db).list_manufacturers()
    return [ManufacturerRead.model_validate(item) for item in manufacturers]


@router.post(
    "",
    response_model=ManufacturerRead,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"description": NAME_CONFLICT_DETAIL}},
)
def create_manufacturer(
    payload: ManufacturerCreate,
    db: DbSession,
) -> ManufacturerRead:
    try:
        manufacturer = ManufacturerService(db).create_manufacturer(payload)
    except ManufacturerNameConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=NAME_CONFLICT_DETAIL,
        ) from error
    return ManufacturerRead.model_validate(manufacturer)


@router.get(
    "/{manufacturer_id}",
    response_model=ManufacturerRead,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_404_NOT_FOUND: {"description": NOT_FOUND_DETAIL}},
)
def get_manufacturer(manufacturer_id: int, db: DbSession) -> ManufacturerRead:
    try:
        manufacturer = ManufacturerService(db).get_manufacturer(manufacturer_id)
    except ManufacturerNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from error
    return ManufacturerRead.model_validate(manufacturer)


@router.put(
    "/{manufacturer_id}",
    response_model=ManufacturerRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": NOT_FOUND_DETAIL},
        status.HTTP_409_CONFLICT: {"description": NAME_CONFLICT_DETAIL},
    },
)
def update_manufacturer(
    manufacturer_id: int,
    payload: ManufacturerUpdate,
    db: DbSession,
) -> ManufacturerRead:
    try:
        manufacturer = ManufacturerService(db).update_manufacturer(
            manufacturer_id,
            payload,
        )
    except ManufacturerNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from error
    except ManufacturerNameConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=NAME_CONFLICT_DETAIL,
        ) from error
    return ManufacturerRead.model_validate(manufacturer)


@router.delete(
    "/{manufacturer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": NOT_FOUND_DETAIL},
        status.HTTP_409_CONFLICT: {"description": IN_USE_DETAIL},
    },
)
def delete_manufacturer(manufacturer_id: int, db: DbSession) -> Response:
    try:
        ManufacturerService(db).delete_manufacturer(manufacturer_id)
    except ManufacturerNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from error
    except ManufacturerInUseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=IN_USE_DETAIL,
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
