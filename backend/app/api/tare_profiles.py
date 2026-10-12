from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.calibration import TareProfileCreate, TareProfileRead, TareProfileUpdate
from app.services.calibration_service import (
    TareProfileConflictError,
    TareProfileNotFoundError,
    TareProfileService,
)


router = APIRouter(prefix="/tare-profiles", tags=["Tare profiles"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[TareProfileRead])
def list_tare_profiles(
    db: DbSession, include_archived: Annotated[bool, Query()] = False
) -> list[TareProfileRead]:
    return TareProfileService(db).list(include_archived)


@router.post("", response_model=TareProfileRead, status_code=status.HTTP_201_CREATED)
def create_tare_profile(payload: TareProfileCreate, db: DbSession) -> TareProfileRead:
    try:
        return TareProfileService(db).create(payload)
    except TareProfileConflictError as error:
        raise HTTPException(status_code=409, detail="Tare profile name already exists.") from error


@router.patch("/{profile_id}", response_model=TareProfileRead)
def update_tare_profile(
    profile_id: int, payload: TareProfileUpdate, db: DbSession
) -> TareProfileRead:
    try:
        return TareProfileService(db).update(profile_id, payload)
    except TareProfileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Tare profile not found.") from error
    except TareProfileConflictError as error:
        raise HTTPException(status_code=409, detail="Tare profile could not be updated.") from error


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tare_profile(profile_id: int, db: DbSession) -> Response:
    try:
        TareProfileService(db).delete(profile_id)
    except TareProfileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Tare profile not found.") from error
    except TareProfileConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="Used tare profiles must be archived instead of deleted.",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
