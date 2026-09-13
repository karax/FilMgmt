import argparse

from app.services.gcode_upload_cleanup_service import GCodeUploadCleanupService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean managed G-code upload storage.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report eligible files and reclaimable space without deleting anything.",
    )
    args = parser.parse_args(argv)

    result = GCodeUploadCleanupService().cleanup(dry_run=args.dry_run)
    print("G-code cleanup")
    print(f"uploads scanned: {result.scanned_uploads}")
    print(f"expired uploads: {result.expired_uploads}")
    print(f"orphan files: {result.orphan_files}")
    print(f"temp files: {result.temp_files}")
    print(f"reclaimable: {_format_bytes(result.reclaimable_bytes)}")
    print(f"used after cleanup: {_format_bytes(result.used_bytes)}")
    print(f"quota: {_format_bytes(result.quota_bytes)}")
    print(f"over quota: {'yes' if result.over_quota else 'no'}")
    if args.dry_run:
        print("dry run: no files deleted")
    else:
        print(
            "deleted: "
            f"{result.deleted_uploads} uploads, "
            f"{result.deleted_orphans} orphan files, "
            f"{result.deleted_temp_files} temp files",
        )
        print(f"reclaimed: {_format_bytes(result.bytes_reclaimed)}")
    for warning in result.warnings:
        print(f"warning: {warning}")
    for error in result.errors:
        print(f"error: {error}")
    return 1 if result.errors else 0


def _format_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{value} B"


if __name__ == "__main__":
    raise SystemExit(main())
