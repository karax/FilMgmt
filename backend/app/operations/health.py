from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HealthCheck:
    name: str
    healthy: bool
    detail: str


def run_health_checks(
    *,
    backend_url: str,
    frontend_url: str,
    database_path: Path,
    gcode_directory: Path,
) -> list[HealthCheck]:
    return [
        _check_backend(backend_url),
        _check_frontend(frontend_url),
        _check_database(database_path),
        _check_storage(gcode_directory),
    ]


def _check_backend(url: str) -> HealthCheck:
    try:
        response = _request(url, accept="application/json")
        payload = json.loads(response.decode("utf-8"))
        if payload != {"status": "ok"}:
            return HealthCheck("Backend", False, "unexpected health response")
        return HealthCheck("Backend", True, url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
        return HealthCheck("Backend", False, str(error))


def _check_frontend(url: str) -> HealthCheck:
    try:
        body = _request(url, accept="text/html").decode("utf-8", errors="replace")
        if "<html" not in body.lower() and "<!doctype html" not in body.lower():
            return HealthCheck("Frontend", False, "entrypoint did not return HTML")
        return HealthCheck("Frontend", True, url)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        return HealthCheck("Frontend", False, str(error))


def _check_database(path: Path) -> HealthCheck:
    path = path.expanduser().resolve()
    if not path.is_file():
        return HealthCheck("Database", False, f"missing: {path}")
    if not os.access(path, os.R_OK | os.W_OK) or not os.access(path.parent, os.W_OK):
        return HealthCheck("Database", False, f"not readable/writable: {path}")
    try:
        connection = sqlite3.connect(path, timeout=5)
        try:
            connection.execute("SELECT 1").fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        return HealthCheck("Database", False, str(error))
    return HealthCheck("Database", True, str(path))


def _check_storage(path: Path) -> HealthCheck:
    path = path.expanduser().resolve()
    if not path.is_dir():
        return HealthCheck("G-code storage", False, f"missing: {path}")
    if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
        return HealthCheck("G-code storage", False, f"not accessible: {path}")
    return HealthCheck("G-code storage", True, str(path))


def _request(url: str, *, accept: str) -> bytes:
    request = Request(url, headers={"Accept": accept, "User-Agent": "fcc-health/1"})
    with urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise OSError(f"HTTP {response.status}")
        return response.read(1024 * 1024)

