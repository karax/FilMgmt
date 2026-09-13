import argparse
import os
from pathlib import Path

from app.config import get_gcode_upload_directory
from app.operations.database import OperationsError, database_path_from_url
from app.operations.health import HealthCheck, run_health_checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check production application health.")
    parser.add_argument(
        "--backend-url",
        default=os.getenv("FCC_BACKEND_HEALTH_URL", "http://127.0.0.1:8000/api/health"),
    )
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("FCC_FRONTEND_URL", "http://127.0.0.1:8080/"),
    )
    parser.add_argument("--database", type=Path)
    parser.add_argument("--gcode-directory", type=Path)
    args = parser.parse_args(argv)
    try:
        database = args.database or database_path_from_url()
    except OperationsError as error:
        checks = [HealthCheck("Database", False, str(error))]
    else:
        checks = run_health_checks(
            backend_url=args.backend_url,
            frontend_url=args.frontend_url,
            database_path=database,
            gcode_directory=args.gcode_directory or get_gcode_upload_directory(),
        )

    for check in checks:
        state = "OK" if check.healthy else "FAILED"
        print(f"{check.name}: {state} ({check.detail})")
    healthy = all(check.healthy for check in checks)
    print(f"\nOverall: {'HEALTHY' if healthy else 'UNHEALTHY'}")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
