from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from uuid import uuid4

from app.config import get_print_job_media_directory


_THUMBNAIL_NAME = re.compile(r"thumbnail-[0-9a-f]{16}\.png")


class PrintJobMediaError(Exception):
    pass


@dataclass(frozen=True)
class StoredThumbnail:
    file_name: str
    path: Path


class PrintJobMediaService:
    def __init__(self, storage_directory: Path | None = None) -> None:
        self.storage_directory = storage_directory or get_print_job_media_directory()

    def store_thumbnail(self, print_job_id: int, contents: bytes) -> StoredThumbnail:
        if print_job_id <= 0 or not contents.startswith(b"\x89PNG\r\n\x1a\n"):
            raise PrintJobMediaError("Invalid print thumbnail.")
        digest = hashlib.sha256(contents).hexdigest()[:16]
        file_name = f"thumbnail-{digest}.png"
        directory = self.storage_directory / str(print_job_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / file_name
        if destination.is_file() and not destination.is_symlink():
            return StoredThumbnail(file_name, destination)
        temporary = directory / f".{file_name}.{uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as output:
                output.write(contents)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise PrintJobMediaError("Could not store print thumbnail.") from error
        return StoredThumbnail(file_name, destination)

    def resolve_thumbnail(self, print_job_id: int, file_name: str) -> Path:
        if print_job_id <= 0 or not _THUMBNAIL_NAME.fullmatch(file_name):
            raise PrintJobMediaError("Invalid print thumbnail reference.")
        path = self.storage_directory / str(print_job_id) / file_name
        if not path.is_file() or path.is_symlink():
            raise PrintJobMediaError("Print thumbnail not found.")
        return path

    def remove_thumbnail(self, print_job_id: int, file_name: str | None) -> None:
        if file_name is None or not _THUMBNAIL_NAME.fullmatch(file_name):
            return
        try:
            (self.storage_directory / str(print_job_id) / file_name).unlink(missing_ok=True)
        except OSError:
            return
