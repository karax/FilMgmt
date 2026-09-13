from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.gcode_parse import GCodeParseResult
from app.schemas.gcode_material_detection import GCodeMaterialDetectionResult
from app.schemas.gcode_time import GCodeTimeResult
from app.schemas.gcode_upload import GCodeUploadRead
from app.schemas.gcode_weight import GCodeWeightRequest, GCodeWeightResult
from app.services.gcode_parser import (
    GCodeBinaryFileError,
    GCodeParseError,
    GCodeParseService,
    GCodeParseStorageError,
)
from app.services.gcode_material_detection_service import GCodeMaterialDetectionService
from app.services.gcode_upload_service import (
    GCodeEmptyFileError,
    GCodeInvalidExtensionError,
    GCodeInvalidUploadIdError,
    GCodeStorageQuotaExceededError,
    GCodeUploadNotFoundError,
    GCodeUploadService,
    GCodeUploadStorageError,
    GCodeUploadTooLargeError,
)
from app.services.gcode_time_service import GCodeTimeService, GCodeTimeStorageError
from app.services.gcode_weight_service import (
    GCodeWeightInvalidToolError,
    GCodeWeightMaterialNotFoundError,
    GCodeWeightService,
)

router = APIRouter(prefix="/gcode/uploads", tags=["G-code"])


def get_gcode_upload_service() -> GCodeUploadService:
    return GCodeUploadService()


UploadService = Annotated[GCodeUploadService, Depends(get_gcode_upload_service)]


def get_gcode_parse_service(service: UploadService) -> GCodeParseService:
    return GCodeParseService(upload_service=service)


ParseService = Annotated[GCodeParseService, Depends(get_gcode_parse_service)]
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=GCodeUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_gcode(
    file: Annotated[UploadFile, File(description="One .gcode file")],
    service: UploadService,
) -> GCodeUploadRead:
    try:
        return await service.persist_upload(file)
    except GCodeInvalidExtensionError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except GCodeEmptyFileError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except GCodeUploadTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(error),
        ) from error
    except GCodeStorageQuotaExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail={
                "code": "gcode_storage_quota_exceeded",
                "message": str(error),
            },
        ) from error
    except GCodeUploadStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store the G-code file.",
        ) from error


@router.get("/{upload_id}", response_model=GCodeUploadRead)
def get_gcode_upload(upload_id: str, service: UploadService) -> GCodeUploadRead:
    try:
        return service.resolve_upload(upload_id).metadata
    except GCodeInvalidUploadIdError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except GCodeUploadNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except GCodeUploadStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not read the G-code upload metadata.",
        ) from error


@router.post("/{upload_id}/parse", response_model=GCodeParseResult)
async def parse_gcode_upload(upload_id: str, service: ParseService) -> GCodeParseResult:
    try:
        return await run_in_threadpool(service.parse_upload, upload_id)
    except GCodeInvalidUploadIdError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except GCodeUploadNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except GCodeBinaryFileError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded file contains binary data and cannot be parsed as G-code.",
        ) from error
    except (GCodeUploadStorageError, GCodeParseStorageError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not read or cache the G-code parse result.",
        ) from error
    except GCodeParseError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse the uploaded G-code file.",
        ) from error


@router.post("/{upload_id}/weight", response_model=GCodeWeightResult)
async def estimate_gcode_weight(
    upload_id: str,
    payload: GCodeWeightRequest,
    service: ParseService,
    db: DbSession,
) -> GCodeWeightResult:
    try:
        weight_service = GCodeWeightService(db=db, parse_service=service)
        return await run_in_threadpool(weight_service.calculate_upload, upload_id, payload)
    except GCodeInvalidUploadIdError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except GCodeUploadNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except GCodeWeightMaterialNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except GCodeWeightInvalidToolError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (GCodeUploadStorageError, GCodeParseStorageError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not read or cache the G-code parse result.",
        ) from error
    except GCodeParseError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse the uploaded G-code file.",
        ) from error


@router.post("/{upload_id}/time", response_model=GCodeTimeResult)
async def estimate_gcode_time(upload_id: str, service: ParseService) -> GCodeTimeResult:
    try:
        time_service = GCodeTimeService(parse_service=service)
        return await run_in_threadpool(time_service.estimate_upload, upload_id)
    except GCodeInvalidUploadIdError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except GCodeUploadNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (GCodeUploadStorageError, GCodeParseStorageError, GCodeTimeStorageError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not read or cache the G-code time result.",
        ) from error
    except GCodeParseError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse the uploaded G-code file.",
        ) from error


@router.post(
    "/{upload_id}/material-detection",
    response_model=GCodeMaterialDetectionResult,
)
async def detect_gcode_materials(
    upload_id: str,
    service: ParseService,
    db: DbSession,
) -> GCodeMaterialDetectionResult:
    try:
        detection_service = GCodeMaterialDetectionService(db=db, parse_service=service)
        return await run_in_threadpool(detection_service.detect_upload, upload_id)
    except GCodeInvalidUploadIdError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except GCodeUploadNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (GCodeUploadStorageError, GCodeParseStorageError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not read the G-code material detection result.",
        ) from error
    except GCodeParseError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse the uploaded G-code file.",
        ) from error
