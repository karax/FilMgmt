"""Populate the configured database with a canonical technical material catalog."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Material


ABRASIVE_NOTE = "Abrasive composite; hardened nozzle generally recommended."
GLOW_NOTE = "Filled formulations may be abrasive."
HYGROSCOPIC_NOTE = "Hygroscopic; drying is often recommended."
HIGH_TEMPERATURE_NOTE = (
    "High-temperature engineering material requiring specialized hardware."
)


@dataclass(frozen=True)
class MaterialSeedDefinition:
    name: str
    category: str
    default_nozzle_temp_min: int | None = None
    default_nozzle_temp_max: int | None = None
    default_bed_temp_min: int | None = None
    default_bed_temp_max: int | None = None
    density_g_cm3: Decimal | None = None
    notes: str | None = None


def material(
    name: str,
    category: str,
    *,
    nozzle: tuple[int, int] | None = None,
    bed: tuple[int, int] | None = None,
    notes: str | None = None,
) -> MaterialSeedDefinition:
    """Keep catalog declarations concise while intentionally omitting uncertain defaults."""
    return MaterialSeedDefinition(
        name=name,
        category=category,
        default_nozzle_temp_min=nozzle[0] if nozzle else None,
        default_nozzle_temp_max=nozzle[1] if nozzle else None,
        default_bed_temp_min=bed[0] if bed else None,
        default_bed_temp_max=bed[1] if bed else None,
        notes=notes,
    )


MATERIAL_SEED: tuple[MaterialSeedDefinition, ...] = (
    # PLA
    material("PLA", "PLA", nozzle=(190, 220), bed=(45, 60)),
    material("PLA+", "PLA", nozzle=(190, 230), bed=(45, 60)),
    material("PLA Pro", "PLA"), material("PLA Tough", "PLA"),
    material("PLA Impact", "PLA"), material("PLA High Speed", "PLA"),
    material("PLA+ High Speed", "PLA"), material("HT-PLA", "PLA"),
    material("PLA Matte", "PLA"), material("PLA Silk", "PLA"),
    material("PLA High Gloss", "PLA"),
    material("PLA Glow in the Dark", "PLA", notes=GLOW_NOTE),
    material("PLA Wood", "PLA"), material("PLA Metal-Filled", "PLA", notes=ABRASIVE_NOTE),
    material("PLA Mineral/Stone", "PLA", notes=ABRASIVE_NOTE),
    material("PLA Lightweight/Foaming", "PLA"),
    material("PLA-CF", "PLA", notes=ABRASIVE_NOTE),
    material("PLA-GF", "PLA", notes=ABRASIVE_NOTE),
    material("PLA ESD/Conductive", "PLA"), material("PLA FR/V0", "PLA"),
    material("rPLA", "PLA"), material("PLA/PHA", "PLA"),
    material("PLA/PHB", "PLA"),
    # PETG
    material("PETG", "PETG", nozzle=(220, 250), bed=(70, 85)),
    material("PETG High Speed/HF", "PETG", nozzle=(220, 250), bed=(70, 85)),
    material("PETG Matte", "PETG"), material("PETG-CF", "PETG", notes=ABRASIVE_NOTE),
    material("PETG-GF", "PETG", notes=ABRASIVE_NOTE), material("PETG FR/V0", "PETG"),
    material("PETG ESD", "PETG"), material("PETG/PTFE", "PETG"),
    material("PETG HT", "PETG"), material("rPETG", "PETG"),
    material("PETG Magnetite-Filled", "PETG"),
    material("PETG Tungsten-Filled", "PETG"),
    # PET, PCTG and co-polyesters
    material("PET", "PET"), material("PET-CF", "PET", notes=ABRASIVE_NOTE),
    material("PET-GF", "PET", notes=ABRASIVE_NOTE), material("PET FR", "PET"),
    material("rPET", "PET"), material("PCTG", "PCTG"),
    material("PCTG-CF", "PCTG", notes=ABRASIVE_NOTE),
    material("PCTG-GF", "PCTG", notes=ABRASIVE_NOTE), material("rPCTG", "PCTG"),
    material("CPE", "CPE"), material("CPE-CF", "CPE", notes=ABRASIVE_NOTE),
    material("CoPE", "COPE"),
    # ABS and ASA
    material("ABS", "ABS", nozzle=(230, 260), bed=(90, 110)),
    material("ABS+", "ABS", nozzle=(230, 260), bed=(90, 110)), material("ABS-T", "ABS"),
    material("ABS High Speed", "ABS"), material("ABS-CF", "ABS", notes=ABRASIVE_NOTE),
    material("ABS-GF", "ABS", notes=ABRASIVE_NOTE), material("ABS FR/V0", "ABS"),
    material("ABS ESD", "ABS"), material("ABS Medical", "ABS"),
    material("ABS Aramid/Kevlar", "ABS", notes=ABRASIVE_NOTE), material("rABS", "ABS"),
    material("ASA", "ASA", nozzle=(240, 260), bed=(90, 110)), material("ASA High Speed", "ASA"),
    material("ASA-CF", "ASA", notes=ABRASIVE_NOTE),
    material("ASA-GF", "ASA", notes=ABRASIVE_NOTE),
    material("ASA Aramid/Kevlar", "ASA", notes=ABRASIVE_NOTE),
    material("ASA FR/V0", "ASA"), material("ASA Lightweight/Foaming", "ASA"),
    material("rASA", "ASA"),
    # Flexible materials
    material("TPU 60A", "TPU", nozzle=(210, 230), bed=(40, 60)), material("TPU 70A", "TPU", nozzle=(210, 230), bed=(40, 60)),
    material("TPU 82A", "TPU", nozzle=(210, 230), bed=(40, 60)), material("TPU 85A", "TPU", nozzle=(210, 230), bed=(40, 60)),
    material("TPU 87A", "TPU", nozzle=(210, 230), bed=(40, 60)), material("TPU 90A", "TPU", nozzle=(210, 230), bed=(40, 60)),
    material("TPU 92A", "TPU", nozzle=(210, 230), bed=(40, 60)), material("TPU 95A", "TPU", nozzle=(210, 230), bed=(40, 60)),
    material("TPU 98A", "TPU", nozzle=(210, 230), bed=(40, 60)), material("TPU 30D", "TPU"),
    material("TPU 40D", "TPU"), material("TPU 64D", "TPU"),
    material("TPU 75D-GF", "TPU", notes=ABRASIVE_NOTE), material("TPU 83D", "TPU"),
    material("TPU High Speed", "TPU"), material("TPU-CF", "TPU", notes=ABRASIVE_NOTE),
    material("TPU-ESD", "TPU"), material("TPU Lightweight/Foaming", "TPU"),
    material("rTPU", "TPU"), material("TPE 83A", "TPE"), material("TPE 88A", "TPE"),
    material("TPE 90A", "TPE"), material("TPE 96A", "TPE"), material("TPE 32D", "TPE"),
    material("PEBA 85A", "PEBA"), material("PEBA 90A", "PEBA"),
    material("PEBA Lightweight/Foaming", "PEBA"), material("TPC 30D", "TPC"),
    material("TPC 40D", "TPC"),
    # PA / nylon
    material("PA", "PA", notes=HYGROSCOPIC_NOTE), material("PA6", "PA", notes=HYGROSCOPIC_NOTE),
    material("PA11", "PA", notes=HYGROSCOPIC_NOTE), material("PA12", "PA", notes=HYGROSCOPIC_NOTE),
    material("PA612", "PA", notes=HYGROSCOPIC_NOTE), material("CoPA", "PA", notes=HYGROSCOPIC_NOTE),
    material("PA6-CF", "PA", notes=ABRASIVE_NOTE), material("PA6-GF", "PA", notes=ABRASIVE_NOTE),
    material("PA11-CF", "PA", notes=ABRASIVE_NOTE), material("PA12-CF", "PA", notes=ABRASIVE_NOTE),
    material("PA12-GF", "PA", notes=ABRASIVE_NOTE), material("PA612-CF", "PA", notes=ABRASIVE_NOTE),
    material("PA612-ESD", "PA", notes=HYGROSCOPIC_NOTE), material("PAHT-CF", "PA", notes=ABRASIVE_NOTE),
    material("PA Aramid", "PA", notes=ABRASIVE_NOTE), material("PA Metal Detectable", "PA"),
    material("rPA/Nylon", "PA", notes=HYGROSCOPIC_NOTE), material("PPA-CF", "PPA", notes=ABRASIVE_NOTE),
    # Polycarbonate and polyolefins
    material("PC", "PC"), material("PC-CF", "PC", notes=ABRASIVE_NOTE), material("PC FR", "PC"),
    material("PC-ABS", "PC"), material("PC-PBT", "PC"),
    material("PC-PBT-CF", "PC", notes=ABRASIVE_NOTE), material("PC-PBT-GF", "PC", notes=ABRASIVE_NOTE),
    material("PC-PTFE", "PC"), material("PP", "PP"),
    material("PP-CF", "PP", notes=ABRASIVE_NOTE), material("PP-GF", "PP", notes=ABRASIVE_NOTE),
    # High-temperature engineering polymers
    material("PPS", "PPS", notes=HIGH_TEMPERATURE_NOTE),
    material("PPS-CF", "PPS", notes=ABRASIVE_NOTE), material("PPS-GF", "PPS", notes=ABRASIVE_NOTE),
    material("PEEK", "PEEK", notes=HIGH_TEMPERATURE_NOTE),
    material("PEEK-CF", "PEEK", notes=HIGH_TEMPERATURE_NOTE),
    material("PEKK", "PEKK", notes=HIGH_TEMPERATURE_NOTE),
    material("PEI 9085", "PEI", notes=HIGH_TEMPERATURE_NOTE),
    material("PEI 1010", "PEI", notes=HIGH_TEMPERATURE_NOTE),
    material("ULTEM / PEI", "PEI", notes=HIGH_TEMPERATURE_NOTE),
    # Other technical and support materials
    material("PVDF", "PVDF"), material("PVC", "PVC"), material("PVB", "PVB"),
    material("PVA", "PVA", nozzle=(190, 220), bed=(45, 60)), material("PVA+", "PVA", nozzle=(190, 220), bed=(45, 60)), material("BVOH", "BVOH"),
    material("HIPS", "HIPS"), material("PHA", "PHA"), material("SBC", "SBC"),
    material("OBC/PE", "PE"), material("HDPE", "PE"),
    material("Water-Soluble Support", "SUPPORT"),
    material("Breakaway Support for PLA", "SUPPORT"),
    material("Support for PLA/PETG", "SUPPORT"), material("Support for PA/PET", "SUPPORT"),
    material("Support for ABS", "SUPPORT"),
)

_BRAND_TERMS = (
    "prusament", "polymaker", "esun", "sunlu", "bambu", "fiberlogy",
    "fillamentum", "formfutura", "extrudr", "spectrum", "colorfabb",
    "azurefilm", "devil design", "rosa3d", "recreus", "add:north",
    "filament-pm", "eryone", "3djake", "nobufil",
)
_OPTIONAL_DEFAULT_FIELDS = (
    "default_nozzle_temp_min", "default_nozzle_temp_max",
    "default_bed_temp_min", "default_bed_temp_max", "density_g_cm3", "notes",
)


def validate_material_catalog(
    catalog: tuple[MaterialSeedDefinition, ...] = MATERIAL_SEED,
) -> None:
    """Reject malformed, duplicate, or manufacturer-specific seed entries."""
    names: set[str] = set()
    for entry in catalog:
        normalized_name = entry.name.strip()
        if not normalized_name or normalized_name.casefold() in names:
            raise ValueError("Material seed names must be non-empty and unique.")
        names.add(normalized_name.casefold())
        if entry.category != entry.category.upper():
            raise ValueError(f"Material category must be uppercase: {entry.name}")
        if any(brand in normalized_name.casefold() for brand in _BRAND_TERMS):
            raise ValueError(f"Material seed must not include a manufacturer name: {entry.name}")
        for minimum, maximum, label in (
            (entry.default_nozzle_temp_min, entry.default_nozzle_temp_max, "nozzle"),
            (entry.default_bed_temp_min, entry.default_bed_temp_max, "bed"),
        ):
            if any(value is not None and not 0 <= value <= 500 for value in (minimum, maximum)):
                raise ValueError(f"Invalid {label} temperature: {entry.name}")
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"Inverted {label} temperature range: {entry.name}")
        if entry.density_g_cm3 is not None and not Decimal("0") < entry.density_g_cm3 <= Decimal("10"):
            raise ValueError(f"Invalid density: {entry.name}")


validate_material_catalog()


@dataclass(frozen=True)
class MaterialSeedResult:
    inserted: tuple[str, ...]
    existing: tuple[str, ...]
    defaults_updated: tuple[str, ...]


def seed_materials(session: Session) -> MaterialSeedResult:
    """Insert missing technical profiles and fill only absent canonical defaults."""
    existing_by_name: dict[str, list[Material]] = {}
    for existing in session.scalars(select(Material)).all():
        existing_by_name.setdefault(existing.name.casefold(), []).append(existing)

    inserted: list[str] = []
    existing: list[str] = []
    defaults_updated: list[str] = []
    try:
        for entry in MATERIAL_SEED:
            matches = existing_by_name.get(entry.name.casefold(), [])
            if not matches:
                created = Material(**entry.__dict__)
                session.add(created)
                existing_by_name[entry.name.casefold()] = [created]
                inserted.append(entry.name)
                continue

            # Do not reconcile case-variant legacy duplicates or change required fields.
            current = matches[0]
            existing.append(current.name)
            changed = False
            for field in _OPTIONAL_DEFAULT_FIELDS:
                seed_value = getattr(entry, field)
                if getattr(current, field) is None and seed_value is not None:
                    setattr(current, field, seed_value)
                    changed = True
            if changed:
                defaults_updated.append(current.name)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise

    return MaterialSeedResult(tuple(inserted), tuple(existing), tuple(defaults_updated))


def _print_group(prefix: str, heading: str, names: tuple[str, ...]) -> None:
    if names:
        print(f"{heading}:")
        for name in names:
            print(f"  {prefix} {name}")


def main() -> None:
    with SessionLocal() as session:
        result = seed_materials(session)
        total_materials = len(session.scalars(select(Material)).all())
    print("Filament Command Center — Material Seed")
    _print_group("+", "Added", result.inserted)
    _print_group("=", "Already existing", result.existing)
    _print_group("~", "Updated missing defaults", result.defaults_updated)
    print("Summary:")
    print(f"  inserted: {len(result.inserted)}")
    print(f"  existing: {len(result.existing)}")
    print(f"  defaults updated: {len(result.defaults_updated)}")
    print(f"  total materials: {total_materials}")


if __name__ == "__main__":
    main()
