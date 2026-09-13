from collections import defaultdict
from contextlib import contextmanager
import os
from pathlib import Path
from threading import RLock
from typing import Iterator
from uuid import UUID


_registry_lock = RLock()
_storage_locks: dict[Path, RLock] = {}
_active_uploads: dict[tuple[Path, UUID], int] = defaultdict(int)


def storage_key(storage_directory: Path) -> Path:
    return Path(os.path.abspath(storage_directory))


def storage_lock(storage_directory: Path) -> RLock:
    key = storage_key(storage_directory)
    with _registry_lock:
        return _storage_locks.setdefault(key, RLock())


@contextmanager
def active_upload(storage_directory: Path, upload_id: UUID) -> Iterator[None]:
    key = storage_key(storage_directory)
    lock = storage_lock(storage_directory)
    with lock:
        _active_uploads[(key, upload_id)] += 1
    try:
        yield
    finally:
        with lock:
            registry_key = (key, upload_id)
            _active_uploads[registry_key] -= 1
            if _active_uploads[registry_key] == 0:
                _active_uploads.pop(registry_key, None)


def active_upload_ids(storage_directory: Path) -> frozenset[UUID]:
    key = storage_key(storage_directory)
    lock = storage_lock(storage_directory)
    with lock:
        return frozenset(
            upload_id
            for (storage, upload_id), count in _active_uploads.items()
            if storage == key and count > 0
        )
