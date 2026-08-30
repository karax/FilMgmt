"""Populate the configured database with a curated initial manufacturer list."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Manufacturer


MANUFACTURER_SEED: tuple[tuple[str, str], ...] = (
    ("Prusament", "https://prusament.com"),
    ("Polymaker", "https://polymaker.com"),
    ("eSUN", "https://www.esun3d.com"),
    ("SUNLU", "https://www.sunlu.com"),
    ("Bambu Lab", "https://bambulab.com"),
    ("Fiberlogy", "https://fiberlogy.com"),
    ("Fillamentum", "https://fillamentum.com"),
    ("FormFutura", "https://formfutura.com"),
    ("Extrudr", "https://www.extrudr.com"),
    ("Spectrum Filaments", "https://spectrumfilaments.com"),
    ("colorFabb", "https://colorfabb.com"),
    ("AzureFilm", "https://azurefilm.com"),
    ("Devil Design", "https://devildesign.com"),
    ("ROSA3D", "https://rosa3d.pl"),
    ("Recreus", "https://recreus.com"),
    ("add:north", "https://addnorth.com"),
    ("Filament-PM", "https://www.filament-pm.com"),
    ("Eryone", "https://eryone3d.com"),
    ("3DJake", "https://www.3djake.com"),
    ("Nobufil", "https://nobufil.com"),
)


@dataclass(frozen=True)
class ManufacturerSeedResult:
    """A human-readable summary of one idempotent seed execution."""

    inserted: tuple[str, ...]
    existing: tuple[str, ...]
    websites_updated: tuple[str, ...]


def seed_manufacturers(session: Session) -> ManufacturerSeedResult:
    """Insert absent manufacturers without overwriting user-managed websites."""
    existing_by_name: dict[str, list[Manufacturer]] = {}
    for manufacturer in session.scalars(select(Manufacturer)).all():
        existing_by_name.setdefault(manufacturer.name.casefold(), []).append(manufacturer)

    inserted: list[str] = []
    existing: list[str] = []
    websites_updated: list[str] = []

    try:
        for name, website in MANUFACTURER_SEED:
            matches = existing_by_name.get(name.casefold(), [])
            if not matches:
                manufacturer = Manufacturer(name=name, website=website)
                session.add(manufacturer)
                existing_by_name[name.casefold()] = [manufacturer]
                inserted.append(name)
                continue

            # Prefer an existing user-provided website when case variants exist.
            manufacturer = next(
                (candidate for candidate in matches if candidate.website is not None),
                matches[0],
            )
            existing.append(manufacturer.name)
            if manufacturer.website is None:
                manufacturer.website = website
                websites_updated.append(manufacturer.name)

        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise

    return ManufacturerSeedResult(
        inserted=tuple(inserted),
        existing=tuple(existing),
        websites_updated=tuple(websites_updated),
    )


def _print_group(prefix: str, heading: str, names: tuple[str, ...]) -> None:
    if not names:
        return
    print(f"{heading}:")
    for name in names:
        print(f"  {prefix} {name}")


def main() -> None:
    """Run the manufacturer seed against the application's configured database."""
    with SessionLocal() as session:
        result = seed_manufacturers(session)
        total_manufacturers = len(session.scalars(select(Manufacturer)).all())

    print("Filament Command Center — Manufacturer Seed")
    _print_group("+", "Added", result.inserted)
    _print_group("=", "Already existing", result.existing)
    _print_group("~", "Updated missing website", result.websites_updated)
    print("Summary:")
    print(f"  inserted: {len(result.inserted)}")
    print(f"  existing: {len(result.existing)}")
    print(f"  websites updated: {len(result.websites_updated)}")
    print(f"  total manufacturers: {total_manufacturers}")


if __name__ == "__main__":
    main()
