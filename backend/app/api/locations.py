from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import LocationCreate, LocationRead, LocationUpdate
from app.services.location_service import (
    LocationInUseError,
    LocationNameConflictError,
    LocationNotFoundError,
    LocationService,
)

router = APIRouter(prefix="/locations", tags=["Locations"])

DbSession = Annotated[Session, Depends(get_db)]

NOT_FOUND_DETAIL = "Location not found."
NAME_CONFLICT_DETAIL = "Location with this name already exists."
IN_USE_DETAIL = "Location is in use and cannot be deleted."


@router.get("", response_model=list[LocationRead], status_code=status.HTTP_200_OK)
def list_locations(db: DbSession) -> list[LocationRead]:
    locations = LocationService(db).list_locations()
    return [LocationRead.model_validate(item) for item in locations]


@router.post(
    "",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"description": NAME_CONFLICT_DETAIL}},
)
def create_location(payload: LocationCreate, db: DbSession) -> LocationRead:
    try:
        location = LocationService(db).create_location(payload)
    except LocationNameConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=NAME_CONFLICT_DETAIL,
        ) from error
    return LocationRead.model_validate(location)


@router.get(
    "/{location_id}",
    response_model=LocationRead,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_404_NOT_FOUND: {"description": NOT_FOUND_DETAIL}},
)
def get_location(location_id: int, db: DbSession) -> LocationRead:
    try:
        location = LocationService(db).get_location(location_id)
    except LocationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from error
    return LocationRead.model_validate(location)


@router.put(
    "/{location_id}",
    response_model=LocationRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": NOT_FOUND_DETAIL},
        status.HTTP_409_CONFLICT: {"description": NAME_CONFLICT_DETAIL},
    },
)
def update_location(
    location_id: int,
    payload: LocationUpdate,
    db: DbSession,
) -> LocationRead:
    try:
        location = LocationService(db).update_location(location_id, payload)
    except LocationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from error
    except LocationNameConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=NAME_CONFLICT_DETAIL,
        ) from error
    return LocationRead.model_validate(location)


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": NOT_FOUND_DETAIL},
        status.HTTP_409_CONFLICT: {"description": IN_USE_DETAIL},
    },
)
def delete_location(location_id: int, db: DbSession) -> Response:
    try:
        LocationService(db).delete_location(location_id)
    except LocationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from error
    except LocationInUseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=IN_USE_DETAIL,
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
