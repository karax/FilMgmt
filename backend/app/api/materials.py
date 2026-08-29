from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import MaterialCreate, MaterialRead, MaterialUpdate
from app.services.material_service import (
    MaterialInUseError,
    MaterialNameConflictError,
    MaterialNotFoundError,
    MaterialService,
)

router = APIRouter(prefix="/materials", tags=["Materials"])

DbSession = Annotated[Session, Depends(get_db)]

NOT_FOUND_DETAIL = "Material not found."
NAME_CONFLICT_DETAIL = "Material with this name already exists."
IN_USE_DETAIL = "Material is in use and cannot be deleted."


@router.get("", response_model=list[MaterialRead], status_code=status.HTTP_200_OK)
def list_materials(db: DbSession) -> list[MaterialRead]:
    materials = MaterialService(db).list_materials()
    return [MaterialRead.model_validate(item) for item in materials]


@router.post(
    "",
    response_model=MaterialRead,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"description": NAME_CONFLICT_DETAIL}},
)
def create_material(payload: MaterialCreate, db: DbSession) -> MaterialRead:
    try:
        material = MaterialService(db).create_material(payload)
    except MaterialNameConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=NAME_CONFLICT_DETAIL,
        ) from error
    return MaterialRead.model_validate(material)


@router.get(
    "/{material_id}",
    response_model=MaterialRead,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_404_NOT_FOUND: {"description": NOT_FOUND_DETAIL}},
)
def get_material(material_id: int, db: DbSession) -> MaterialRead:
    try:
        material = MaterialService(db).get_material(material_id)
    except MaterialNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from error
    return MaterialRead.model_validate(material)


@router.put(
    "/{material_id}",
    response_model=MaterialRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": NOT_FOUND_DETAIL},
        status.HTTP_409_CONFLICT: {"description": NAME_CONFLICT_DETAIL},
    },
)
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: DbSession,
) -> MaterialRead:
    try:
        material = MaterialService(db).update_material(material_id, payload)
    except MaterialNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from error
    except MaterialNameConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=NAME_CONFLICT_DETAIL,
        ) from error
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
    return MaterialRead.model_validate(material)


@router.delete(
    "/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": NOT_FOUND_DETAIL},
        status.HTTP_409_CONFLICT: {"description": IN_USE_DETAIL},
    },
)
def delete_material(material_id: int, db: DbSession) -> Response:
    try:
        MaterialService(db).delete_material(material_id)
    except MaterialNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from error
    except MaterialInUseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=IN_USE_DETAIL,
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
