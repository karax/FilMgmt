from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import errno
import logging
import os
from pathlib import Path
from typing import Iterator
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.config import (
    GCODE_UPLOAD_CHUNK_BYTES,
    get_gcode_max_upload_bytes,
    get_gcode_upload_cleanup_enabled,
    get_gcode_upload_max_total_bytes,
    get_gcode_upload_directory,
)
from app.schemas.gcode_upload import GCodeUploadRead
from app.services.gcode_upload_activity import active_upload, storage_lock
from app.services.gcode_upload_cleanup_service import GCodeUploadCleanupService


logger = logging.getLogger(__name__)


class GCodeUploadError(Exception):
    """Base exception for controlled G-code upload failures."""


class GCodeInvalidExtensionError(GCodeUploadError):
    pass


class GCodeEmptyFileError(GCodeUploadError):
    pass


class GCodeUploadTooLargeError(GCodeUploadError):
    pass


class GCodeStorageQuotaExceededError(GCodeUploadError):
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
        max_total_bytes: int | None = None,
        cleanup_enabled: bool | None = None,
        cleanup_service: GCodeUploadCleanupService | None = None,
    ) -> None:
        self.storage_directory = storage_directory or get_gcode_upload_directory()
        self.max_upload_bytes = (
            get_gcode_max_upload_bytes()
            if max_upload_bytes is None
            else max_upload_bytes
        )
        self.chunk_size = chunk_size
        self.max_total_bytes = (
            get_gcode_upload_max_total_bytes()
            if max_total_bytes is None
            else max_total_bytes
        )
        self.cleanup_enabled = (
            get_gcode_upload_cleanup_enabled()
            if cleanup_enabled is None
            else cleanup_enabled
        )
        self.cleanup_service = cleanup_service or GCodeUploadCleanupService(
            storage_directory=self.storage_directory,
            max_total_bytes=self.max_total_bytes,
        )
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes must be greater than zero.")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")
        if self.max_total_bytes <= 0:
            raise ValueError("max_total_bytes must be greater than zero.")

    async def persist_upload(self, upload: UploadFile) -> GCodeUploadRead:
        upload_id = uuid4()
        temporary_path = self._data_path(upload_id, suffix=".uploading")
        final_path = self._data_path(upload_id)
        metadata_temporary_path = self._metadata_path(upload_id, temporary=True)
        metadata_path = self._metadata_path(upload_id)
        committed = False

        with self.active_operation(upload_id):
            try:
                self._validate_filename(upload.filename)
                self.storage_directory.mkdir(parents=True, exist_ok=True)
                if upload.size is not None and upload.size > self.max_upload_bytes:
                    raise GCodeUploadTooLargeError("The G-code file exceeds the upload size limit.")
                self._cleanup_before_upload()
                self._ensure_declared_size_fits(upload.size)
                size_bytes = await self._stream_to_temporary_file(upload, temporary_path)
                if size_bytes == 0:
                    raise GCodeEmptyFileError("The uploaded G-code file is empty.")

                metadata = GCodeUploadRead(
                    upload_id=upload_id,
                    filename=upload.filename or "",
                    size_bytes=size_bytes,
                    created_at=datetime.now(UTC),
                    status="UPLOADED",
                )
                metadata_contents = metadata.model_dump_json(indent=2)
                with storage_lock(self.storage_directory):
                    self._ensure_bytes_fit(len(metadata_contents.encode("utf-8")))
                    os.replace(temporary_path, final_path)
                    self._write_metadata(
                        metadata_contents,
                        metadata_temporary_path,
                        metadata_path,
                    )
                committed = True
                return metadata
            except GCodeUploadError:
                raise
            except OSError as error:
                if error.errno in {errno.ENOSPC, errno.EDQUOT}:
                    logger.warning("G-code storage filesystem is full")
                    raise GCodeStorageQuotaExceededError(
                        "G-code storage has reached its configured limit.",
                    ) from error
                raise GCodeUploadStorageError("Could not persist the G-code upload.") from error
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
        with self.active_operation(parsed_id):
            data_path = self._data_path(parsed_id)
            metadata_path = self._metadata_path(parsed_id)
            data_exists = data_path.is_file() and not data_path.is_symlink()
            metadata_exists = metadata_path.is_file() and not metadata_path.is_symlink()
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

    @contextmanager
    def active_operation(self, upload_id: str | UUID) -> Iterator[None]:
        parsed_id = self._parse_upload_id(upload_id)
        with active_upload(self.storage_directory, parsed_id):
            yield

    def delete_upload(self, upload_id: str | UUID) -> None:
        parsed_id = self._parse_upload_id(upload_id)
        with storage_lock(self.storage_directory):
            self._remove_if_present(self.storage_directory / f"{parsed_id}.parse.json")
            self._remove_if_present(self.storage_directory / f"{parsed_id}.parse.json.uploading")
            self._remove_if_present(self.storage_directory / f"{parsed_id}.time.json")
            self._remove_if_present(self.storage_directory / f"{parsed_id}.time.json.uploading")
            self._remove_if_present(self._metadata_path(parsed_id, temporary=True))
            self._remove_if_present(self._metadata_path(parsed_id))
            self._remove_if_present(self._data_path(parsed_id, suffix=".uploading"))
            self._remove_if_present(self._data_path(parsed_id))

    async def _stream_to_temporary_file(self, upload: UploadFile, path: Path) -> int:
        size_bytes = 0
        with path.open("xb", buffering=0) as destination:
            while chunk := await upload.read(self.chunk_size):
                size_bytes += len(chunk)
                if size_bytes > self.max_upload_bytes:
                    raise GCodeUploadTooLargeError("The G-code file exceeds the upload size limit.")
                with storage_lock(self.storage_directory):
                    self._ensure_bytes_fit(len(chunk))
                    destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        return size_bytes

    def _write_metadata(self, contents: str, temporary_path: Path, final_path: Path) -> None:
        with temporary_path.open("x", encoding="utf-8") as destination:
            destination.write(contents)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, final_path)

    def _cleanup_before_upload(self) -> None:
        if not self.cleanup_enabled:
            return
        result = self.cleanup_service.cleanup()
        if result.errors:
            logger.warning("G-code pre-upload cleanup completed with %d error(s)", len(result.errors))

    def _ensure_declared_size_fits(self, declared_size: int | None) -> None:
        if declared_size is None or declared_size <= 0:
            return
        used_bytes, errors = self.cleanup_service.storage_usage()
        if errors:
            raise GCodeUploadStorageError("Could not inspect G-code storage usage.")
        if used_bytes + declared_size > self.max_total_bytes:
            self._raise_quota_exceeded(used_bytes)

    def _ensure_bytes_fit(self, additional_bytes: int) -> None:
        if self.storage_bytes_fit(additional_bytes):
            return
        used_bytes, _ = self.cleanup_service.storage_usage()
        self._raise_quota_exceeded(used_bytes)

    def storage_bytes_fit(self, additional_bytes: int) -> bool:
        """Check capacity while the caller holds the shared storage lock."""
        if additional_bytes < 0:
            raise ValueError("additional_bytes must be zero or greater.")
        used_bytes, errors = self.cleanup_service.storage_usage()
        if errors:
            raise GCodeUploadStorageError("Could not inspect G-code storage usage.")
        return used_bytes + additional_bytes <= self.max_total_bytes

    def _raise_quota_exceeded(self, used_bytes: int) -> None:
        logger.warning(
            "G-code storage quota exceeded: used_bytes=%d quota_bytes=%d",
            used_bytes,
            self.max_total_bytes,
        )
        raise GCodeStorageQuotaExceededError(
            "G-code storage has reached its configured limit.",
        )

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
        except OSError as error:
            logger.warning("Could not remove G-code storage artifact %s: %s", path.name, error)
