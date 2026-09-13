from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
import os
from pathlib import Path
import stat
from uuid import UUID

from app.config import (
    get_gcode_upload_max_total_bytes,
    get_gcode_upload_retention_days,
    get_gcode_upload_retention_enabled,
    get_gcode_upload_temp_stale_seconds,
    get_gcode_upload_directory,
)
from app.schemas.gcode_upload import GCodeUploadRead
from app.services.gcode_upload_activity import active_upload_ids, storage_lock


logger = logging.getLogger(__name__)

_SUFFIXES = (
    (".parse.json.uploading", "parse_temp"),
    (".time.json.uploading", "time_temp"),
    (".json.uploading", "metadata_temp"),
    (".uploading", "upload_temp"),
    (".parse.json", "parse_cache"),
    (".time.json", "time_cache"),
    (".gcode", "raw"),
    (".json", "metadata"),
)
_TEMP_KINDS = frozenset({"parse_temp", "time_temp", "metadata_temp", "upload_temp"})
_DERIVED_KINDS = frozenset({"parse_cache", "time_cache", "parse_temp", "time_temp"})
_MAX_METADATA_BYTES = 64 * 1024
_DELETE_ORDER = {
    "parse_cache": 0,
    "time_cache": 0,
    "parse_temp": 0,
    "time_temp": 0,
    "metadata_temp": 1,
    "metadata": 2,
    "upload_temp": 3,
    "raw": 4,
}


@dataclass(frozen=True)
class ManagedFile:
    upload_id: UUID
    kind: str
    path: Path
    size_bytes: int
    modified_at: datetime
    is_symlink: bool


@dataclass(frozen=True)
class GCodeStorageStatus:
    used_bytes: int
    quota_bytes: int
    available_bytes: int
    upload_count: int
    expired_count: int
    over_quota: bool
    unknown_files: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass
class GCodeCleanupResult:
    scanned_uploads: int = 0
    expired_uploads: int = 0
    orphan_files: int = 0
    temp_files: int = 0
    deleted_uploads: int = 0
    deleted_orphans: int = 0
    deleted_temp_files: int = 0
    bytes_reclaimed: int = 0
    reclaimable_bytes: int = 0
    used_bytes: int = 0
    quota_bytes: int = 0
    over_quota: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _StorageScan:
    entries: dict[UUID, list[ManagedFile]]
    used_bytes: int
    unknown_files: list[str]
    errors: list[str]


class GCodeUploadCleanupService:
    """Inspect and remove only recognized files in the flat G-code storage root."""

    def __init__(
        self,
        storage_directory: Path | None = None,
        *,
        retention_days: int | None = None,
        max_total_bytes: int | None = None,
        temp_stale_seconds: int | None = None,
        retention_enabled: bool | None = None,
    ) -> None:
        self.storage_directory = storage_directory or get_gcode_upload_directory()
        self.retention_days = (
            get_gcode_upload_retention_days()
            if retention_days is None
            else retention_days
        )
        self.max_total_bytes = (
            get_gcode_upload_max_total_bytes()
            if max_total_bytes is None
            else max_total_bytes
        )
        self.temp_stale_seconds = (
            get_gcode_upload_temp_stale_seconds()
            if temp_stale_seconds is None
            else temp_stale_seconds
        )
        self.retention_enabled = (
            get_gcode_upload_retention_enabled()
            if retention_enabled is None
            else retention_enabled
        )
        if self.retention_days < 0:
            raise ValueError("retention_days must be zero or greater.")
        if self.max_total_bytes <= 0:
            raise ValueError("max_total_bytes must be greater than zero.")
        if self.temp_stale_seconds <= 0:
            raise ValueError("temp_stale_seconds must be greater than zero.")

    def inspect_storage(self, *, now: datetime | None = None) -> GCodeStorageStatus:
        current_time = _utc(now)
        with storage_lock(self.storage_directory):
            scan = self._scan()
            expired = self._expired_upload_ids(scan, current_time)
            upload_count = sum(
                1 for files in scan.entries.values() if self._complete_upload(files)
            )
        return GCodeStorageStatus(
            used_bytes=scan.used_bytes,
            quota_bytes=self.max_total_bytes,
            available_bytes=max(self.max_total_bytes - scan.used_bytes, 0),
            upload_count=upload_count,
            expired_count=len(expired),
            over_quota=scan.used_bytes > self.max_total_bytes,
            unknown_files=tuple(scan.unknown_files),
            errors=tuple(scan.errors),
        )

    def storage_usage(self) -> tuple[int, tuple[str, ...]]:
        """Return quota usage from directory entries without reading sidecars."""
        with storage_lock(self.storage_directory):
            scan = self._scan()
        return scan.used_bytes, tuple(scan.errors)

    def cleanup(
        self,
        *,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> GCodeCleanupResult:
        current_time = _utc(now)
        logger.info("G-code upload cleanup started%s", " (dry run)" if dry_run else "")
        with storage_lock(self.storage_directory):
            scan = self._scan()
            result = GCodeCleanupResult(
                scanned_uploads=len(scan.entries),
                used_bytes=scan.used_bytes,
                quota_bytes=self.max_total_bytes,
                errors=list(scan.errors),
                warnings=[f"Ignored unknown G-code storage entry: {name}" for name in scan.unknown_files],
            )
            active = active_upload_ids(self.storage_directory)
            cutoff = current_time - timedelta(days=self.retention_days)
            stale_cutoff = current_time - timedelta(seconds=self.temp_stale_seconds)

            for upload_id, files in scan.entries.items():
                if upload_id in active:
                    continue
                recent_temp = any(
                    item.kind in _TEMP_KINDS and item.modified_at > stale_cutoff
                    for item in files
                )
                if recent_temp:
                    continue

                complete = self._complete_upload(files)
                expired = False
                if complete and self.retention_enabled:
                    metadata = self._read_metadata(upload_id, files, result.errors)
                    if metadata is None:
                        continue
                    expired = metadata.created_at <= cutoff

                if expired:
                    result.expired_uploads += 1
                    result.reclaimable_bytes += sum(item.size_bytes for item in files)
                    if not dry_run:
                        reclaimed, complete_delete = self._delete_upload_unit(files, result.errors)
                        result.bytes_reclaimed += reclaimed
                        if complete_delete:
                            result.deleted_uploads += 1
                            logger.info("Deleted expired G-code upload %s", upload_id)
                    continue

                if not complete:
                    orphan_entries = [item for item in files if item.kind not in _TEMP_KINDS]
                    stale_temps = [item for item in files if item.kind in _TEMP_KINDS]
                    result.orphan_files += len(orphan_entries)
                    result.temp_files += len(stale_temps)
                    result.reclaimable_bytes += sum(item.size_bytes for item in files)
                    if not dry_run:
                        reclaimed, deleted = self._delete_entries(files, result.errors)
                        result.bytes_reclaimed += reclaimed
                        result.deleted_orphans += sum(
                            1 for item in deleted if item.kind not in _TEMP_KINDS
                        )
                        result.deleted_temp_files += sum(
                            1 for item in deleted if item.kind in _TEMP_KINDS
                        )
                    continue

                unsafe_sidecars = [
                    item
                    for item in files
                    if item.is_symlink and item.kind not in {"raw", "metadata"}
                ]
                stale_temps = [
                    item
                    for item in files
                    if item.kind in _TEMP_KINDS and item.modified_at <= stale_cutoff
                ]
                result.orphan_files += len(unsafe_sidecars)
                result.temp_files += len(stale_temps)
                planned = unsafe_sidecars + stale_temps
                result.reclaimable_bytes += sum(item.size_bytes for item in planned)
                if not dry_run and planned:
                    reclaimed, deleted = self._delete_entries(planned, result.errors)
                    result.bytes_reclaimed += reclaimed
                    result.deleted_orphans += sum(item in unsafe_sidecars for item in deleted)
                    result.deleted_temp_files += sum(item in stale_temps for item in deleted)

            final_scan = scan if dry_run else self._scan()
            result.used_bytes = final_scan.used_bytes
            result.errors.extend(error for error in final_scan.errors if error not in result.errors)
            result.over_quota = final_scan.used_bytes > self.max_total_bytes

        if scan.unknown_files:
            logger.warning(
                "G-code cleanup ignored %d unknown storage entr%s",
                len(scan.unknown_files),
                "y" if len(scan.unknown_files) == 1 else "ies",
            )
        for error in result.errors:
            logger.warning("G-code cleanup error: %s", error)
        logger.info(
            "G-code upload cleanup finished: deleted_uploads=%d deleted_orphans=%d "
            "deleted_temp_files=%d bytes_reclaimed=%d errors=%d",
            result.deleted_uploads,
            result.deleted_orphans,
            result.deleted_temp_files,
            result.bytes_reclaimed,
            len(result.errors),
        )
        return result

    def _scan(self) -> _StorageScan:
        entries: dict[UUID, list[ManagedFile]] = defaultdict(list)
        unknown_files: list[str] = []
        errors: list[str] = []
        used_bytes = 0
        if not self.storage_directory.exists():
            return _StorageScan(dict(entries), 0, unknown_files, errors)
        try:
            directory_entries = list(os.scandir(self.storage_directory))
        except OSError as error:
            return _StorageScan({}, 0, [], [f"Could not scan G-code storage: {error}"])

        for entry in directory_entries:
            try:
                file_stat = entry.stat(follow_symlinks=False)
            except OSError as error:
                errors.append(f"Could not inspect {entry.name}: {error}")
                continue
            is_symlink = stat.S_ISLNK(file_stat.st_mode)
            if not is_symlink and not stat.S_ISREG(file_stat.st_mode):
                unknown_files.append(entry.name)
                continue
            used_bytes += file_stat.st_size
            recognized = _recognized_name(entry.name)
            if recognized is None:
                unknown_files.append(entry.name)
                continue
            upload_id, kind = recognized
            item = ManagedFile(
                upload_id=upload_id,
                kind=kind,
                path=Path(entry.path),
                size_bytes=file_stat.st_size,
                modified_at=datetime.fromtimestamp(file_stat.st_mtime, UTC),
                is_symlink=is_symlink,
            )
            entries[upload_id].append(item)
        return _StorageScan(dict(entries), used_bytes, sorted(unknown_files), errors)

    def _expired_upload_ids(self, scan: _StorageScan, now: datetime) -> set[UUID]:
        if not self.retention_enabled:
            return set()
        cutoff = now - timedelta(days=self.retention_days)
        expired: set[UUID] = set()
        errors: list[str] = []
        active = active_upload_ids(self.storage_directory)
        for upload_id, files in scan.entries.items():
            if upload_id in active or not self._complete_upload(files):
                continue
            metadata = self._read_metadata(upload_id, files, errors)
            if metadata is not None and metadata.created_at <= cutoff:
                expired.add(upload_id)
        return expired

    @staticmethod
    def _complete_upload(files: list[ManagedFile]) -> bool:
        raw = next((item for item in files if item.kind == "raw"), None)
        metadata = next((item for item in files if item.kind == "metadata"), None)
        return bool(
            raw
            and metadata
            and not raw.is_symlink
            and not metadata.is_symlink
        )

    @staticmethod
    def _read_metadata(
        upload_id: UUID,
        files: list[ManagedFile],
        errors: list[str],
    ) -> GCodeUploadRead | None:
        metadata_file = next(item for item in files if item.kind == "metadata")
        try:
            if metadata_file.size_bytes > _MAX_METADATA_BYTES:
                raise ValueError("metadata sidecar exceeds the safe size limit")
            metadata = GCodeUploadRead.model_validate_json(
                metadata_file.path.read_text(encoding="utf-8"),
            )
        except Exception as error:
            errors.append(f"Invalid metadata for {upload_id}: {error}")
            return None
        if metadata.upload_id != upload_id:
            errors.append(f"Metadata ID mismatch for {upload_id}.")
            return None
        return metadata

    def _delete_upload_unit(
        self,
        files: list[ManagedFile],
        errors: list[str],
    ) -> tuple[int, bool]:
        reclaimed = 0
        for stage in (
            [item for item in files if item.kind in _DERIVED_KINDS],
            [item for item in files if item.kind == "metadata_temp"],
            [item for item in files if item.kind == "metadata"],
            [item for item in files if item.kind in {"upload_temp", "raw"}],
        ):
            stage_reclaimed, deleted = self._delete_entries(stage, errors)
            reclaimed += stage_reclaimed
            if len(deleted) != len(stage):
                return reclaimed, False
        return reclaimed, True

    def _delete_entries(
        self,
        files: list[ManagedFile],
        errors: list[str],
    ) -> tuple[int, list[ManagedFile]]:
        reclaimed = 0
        deleted: list[ManagedFile] = []
        for item in sorted(files, key=lambda value: _DELETE_ORDER[value.kind]):
            if not self._is_direct_child(item.path):
                errors.append(f"Refused to delete path outside G-code storage: {item.path.name}")
                continue
            try:
                current_stat = item.path.lstat()
                item.path.unlink()
            except FileNotFoundError:
                deleted.append(item)
                continue
            except OSError as error:
                errors.append(f"Could not delete {item.path.name}: {error}")
                continue
            reclaimed += current_stat.st_size
            deleted.append(item)
        return reclaimed, deleted

    def _is_direct_child(self, path: Path) -> bool:
        root = Path(os.path.abspath(self.storage_directory))
        candidate = Path(os.path.abspath(path))
        return candidate.parent == root and candidate.name not in {"", ".", ".."}


def _recognized_name(filename: str) -> tuple[UUID, str] | None:
    for suffix, kind in _SUFFIXES:
        if not filename.endswith(suffix):
            continue
        identifier = filename[: -len(suffix)]
        try:
            upload_id = UUID(identifier)
        except ValueError:
            return None
        if identifier != str(upload_id):
            return None
        return upload_id, kind
    return None


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware.")
    return current.astimezone(UTC)
