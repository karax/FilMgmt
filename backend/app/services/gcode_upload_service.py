from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.config import (
    GCODE_UPLOAD_CHUNK_BYTES,
    get_gcode_max_upload_bytes,
    get_gcode_upload_directory,
)
from app.schemas.gcode_upload import GCodeUploadRead


class GCodeUploadError(Exception):
    """Base exception for controlled G-code upload failures."""


class GCodeInvalidExtensionError(GCodeUploadError):
    pass


class GCodeEmptyFileError(GCodeUploadError):
    pass


class GCodeUploadTooLargeError(GCodeUploadError):
    pass


class GCodeInvalidUploadIdError(GCodeUploadError):
    pass


class GCodeUploadNotFoundError(GCodeUploadError):
    pass


class GCodeUploadStorageError(GCodeUploadError):
    pass


@dataclass(frozen=True)
class ResolvedGCodeUpload:
    metadata: GCodeUploadRead
    path: Path


class GCodeUploadService:
    def __init__(
        self,
        storage_directory: Path | None = None,
        max_upload_bytes: int | None = None,
        chunk_size: int = GCODE_UPLOAD_CHUNK_BYTES,
    ) -> None:
        self.storage_directory = storage_directory or get_gcode_upload_directory()
        self.max_upload_bytes = (
            get_gcode_max_upload_bytes()
            if max_upload_bytes is None
            else max_upload_bytes
        )
        self.chunk_size = chunk_size
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes must be greater than zero.")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")

    async def persist_upload(self, upload: UploadFile) -> GCodeUploadRead:
        upload_id = uuid4()
        temporary_path = self._data_path(upload_id, suffix=".uploading")
        final_path = self._data_path(upload_id)
        metadata_temporary_path = self._metadata_path(upload_id, temporary=True)
        metadata_path = self._metadata_path(upload_id)
        committed = False

        try:
            self._validate_filename(upload.filename)
            self.storage_directory.mkdir(parents=True, exist_ok=True)
            size_bytes = await self._stream_to_temporary_file(upload, temporary_path)
            if size_bytes == 0:
                raise GCodeEmptyFileError("The uploaded G-code file is empty.")

            os.replace(temporary_path, final_path)
            metadata = GCodeUploadRead(
                upload_id=upload_id,
                filename=upload.filename or "",
                size_bytes=size_bytes,
                created_at=datetime.now(UTC),
                status="UPLOADED",
            )
            self._write_metadata(metadata, metadata_temporary_path, metadata_path)
            committed = True
            return metadata
        except GCodeUploadError:
            raise
        except Exception as error:
            raise GCodeUploadStorageError("Could not persist the G-code upload.") from error
        finally:
            try:
                await upload.close()
            finally:
                if not committed:
                    self._remove_if_present(temporary_path)
                    self._remove_if_present(metadata_temporary_path)
                    self._remove_if_present(final_path)
                    self._remove_if_present(metadata_path)

    def resolve_upload(self, upload_id: str | UUID) -> ResolvedGCodeUpload:
        parsed_id = self._parse_upload_id(upload_id)
        data_path = self._data_path(parsed_id)
        metadata_path = self._metadata_path(parsed_id)
        data_exists = data_path.is_file()
        metadata_exists = metadata_path.is_file()
        if not data_exists and not metadata_exists:
            raise GCodeUploadNotFoundError("G-code upload not found.")
        if not data_exists or not metadata_exists:
            raise GCodeUploadStorageError("Stored G-code upload is incomplete.")

        try:
            metadata = GCodeUploadRead.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        except Exception as error:
            raise GCodeUploadStorageError("Stored G-code upload metadata is invalid.") from error
        if metadata.upload_id != parsed_id:
            raise GCodeUploadStorageError("Stored G-code upload metadata does not match its file.")
        return ResolvedGCodeUpload(metadata=metadata, path=data_path)

    def delete_upload(self, upload_id: str | UUID) -> None:
        parsed_id = self._parse_upload_id(upload_id)
        self._remove_if_present(self._data_path(parsed_id))
        self._remove_if_present(self._metadata_path(parsed_id))
        self._remove_if_present(self.storage_directory / f"{parsed_id}.parse.json")
        self._remove_if_present(self.storage_directory / f"{parsed_id}.parse.json.uploading")
        self._remove_if_present(self.storage_directory / f"{parsed_id}.time.json")
        self._remove_if_present(self.storage_directory / f"{parsed_id}.time.json.uploading")

    async def _stream_to_temporary_file(self, upload: UploadFile, path: Path) -> int:
        size_bytes = 0
        with path.open("xb") as destination:
            while chunk := await upload.read(self.chunk_size):
                size_bytes += len(chunk)
                if size_bytes > self.max_upload_bytes:
                    raise GCodeUploadTooLargeError("The G-code file exceeds the upload size limit.")
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        return size_bytes

    def _write_metadata(self, metadata: GCodeUploadRead, temporary_path: Path, final_path: Path) -> None:
        with temporary_path.open("x", encoding="utf-8") as destination:
            destination.write(metadata.model_dump_json(indent=2))
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, final_path)

    @staticmethod
    def _validate_filename(filename: str | None) -> None:
        if not filename or not filename.lower().endswith(".gcode"):
            raise GCodeInvalidExtensionError("Only .gcode files are accepted.")

    @staticmethod
    def _parse_upload_id(upload_id: str | UUID) -> UUID:
        try:
            return upload_id if isinstance(upload_id, UUID) else UUID(upload_id)
        except (TypeError, ValueError, AttributeError) as error:
            raise GCodeInvalidUploadIdError("Invalid G-code upload ID.") from error

    def _data_path(self, upload_id: UUID, suffix: str = ".gcode") -> Path:
        return self.storage_directory / f"{upload_id}{suffix}"

    def _metadata_path(self, upload_id: UUID, temporary: bool = False) -> Path:
        suffix = ".json.uploading" if temporary else ".json"
        return self.storage_directory / f"{upload_id}{suffix}"

    @staticmethod
    def _remove_if_present(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
