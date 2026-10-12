from decimal import Decimal
from pathlib import Path
import zipfile

import pytest

from app.integrations.bambu import three_mf
from app.integrations.bambu.three_mf import (
    Bambu3mfAmbiguousPlateError,
    Bambu3mfArchiveTooLargeError,
    Bambu3mfError,
    Bambu3mfMalformedMetadataError,
    Bambu3mfParser,
    Bambu3mfUnsafeArchiveError,
)


FIXTURES = Path(__file__).parent / "fixtures" / "bambu_3mf"
PNG = b"\x89PNG\r\n\x1a\n" + b"sanitized-png-fixture"


def make_archive(
    path: Path,
    *,
    slice_info: bytes | None = None,
    model_settings: bytes | None = None,
    thumbnail: bool = True,
    extra: dict[str, bytes] | None = None,
) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if slice_info is not None:
            archive.writestr("Metadata/slice_info.config", slice_info)
        if model_settings is not None:
            archive.writestr("Metadata/model_settings.config", model_settings)
        if thumbnail:
            archive.writestr("Metadata/plate_7.png", PNG)
        for name, contents in (extra or {}).items():
            archive.writestr(name, contents)
    return path


def real_fixture_archive(tmp_path: Path, **overrides) -> Path:
    options = {
        "slice_info": (FIXTURES / "slice_info.config").read_bytes(),
        "model_settings": (FIXTURES / "model_settings.config").read_bytes(),
    }
    options.update(overrides)
    return make_archive(tmp_path / "fixture.3mf", **options)


def test_sanitized_real_archive_parses_plate_thumbnail_duration_and_filament(tmp_path: Path) -> None:
    parsed = Bambu3mfParser().parse(real_fixture_archive(tmp_path))

    assert parsed.plate_index == 7
    assert parsed.plate_name == "Sanitized printed plate"
    assert parsed.plate_selection_confidence == "EXACT"
    assert parsed.slicer_estimated_duration_seconds == 22557
    assert parsed.thumbnail_member == "Metadata/plate_7.png"
    assert parsed.thumbnail_bytes == PNG
    assert len(parsed.filaments) == 1
    usage = parsed.filaments[0]
    assert usage.source_filament_id == "4"
    assert usage.material_type == "PETG"
    assert usage.color == "#FFFFFF"
    assert usage.used_g == Decimal("230.51")
    assert usage.used_m == Decimal("75.46")
    assert usage.tray_info_idx == "GFG99"
    assert usage.used_for_object is True
    assert usage.used_for_support is False
    assert usage.nozzle_diameter == Decimal("0.40")


def test_namespace_unknown_elements_and_multiple_filaments_are_tolerated(tmp_path: Path) -> None:
    xml = b'''<ns:config xmlns:ns="urn:test"><ns:plate future="yes">
      <ns:metadata key="index" value="2"/><ns:metadata key="prediction" value="120"/>
      <ns:future-element value="ignored"/>
      <ns:filament id="1" type="PLA" color="#000000" used_g="74.2" used_m="24.7" tray_info_idx="GFA00"/>
      <ns:filament id="2" type="PLA" color="#FFFFFF" used_g="8.7" used_m="2.9" tray_info_idx="GFA01"/>
    </ns:plate></ns:config>'''
    parsed = Bambu3mfParser().parse(make_archive(tmp_path / "multi.3mf", slice_info=xml, thumbnail=False))

    assert [usage.used_g for usage in parsed.filaments] == [Decimal("74.2"), Decimal("8.7")]
    assert [usage.used_m for usage in parsed.filaments] == [Decimal("24.7"), Decimal("2.9")]
    assert parsed.thumbnail_bytes is None


def test_multiple_slice_plates_use_the_only_plate_with_embedded_gcode(tmp_path: Path) -> None:
    slice_xml = b'''<config><plate><metadata key="index" value="1"/><filament id="1" used_g="1"/></plate>
      <plate><metadata key="index" value="2"/><filament id="2" used_g="2"/></plate></config>'''
    model_xml = b'''<config><plate><metadata key="plater_id" value="1"/><metadata key="gcode_file" value=""/></plate>
      <plate><metadata key="plater_id" value="2"/><metadata key="gcode_file" value="Metadata/plate_2.gcode"/></plate></config>'''
    parsed = Bambu3mfParser().parse(make_archive(tmp_path / "plates.3mf", slice_info=slice_xml, model_settings=model_xml, thumbnail=False))

    assert parsed.plate_index == 2
    assert parsed.filaments[0].used_g == Decimal("2")
    assert parsed.plate_selection_confidence == "HIGH_CONFIDENCE"


def test_ambiguous_multiple_plates_are_not_summed(tmp_path: Path) -> None:
    xml = b'''<config><plate><metadata key="index" value="1"/><filament id="1" used_g="10"/></plate>
      <plate><metadata key="index" value="2"/><filament id="2" used_g="20"/></plate></config>'''
    with pytest.raises(Bambu3mfAmbiguousPlateError):
        Bambu3mfParser().parse(make_archive(tmp_path / "ambiguous.3mf", slice_info=xml, thumbnail=False))


def test_plate_hint_selects_one_of_multiple_plates(tmp_path: Path) -> None:
    xml = b'''<config><plate><metadata key="index" value="1"/><filament id="1" used_g="10"/></plate>
      <plate><metadata key="index" value="2"/><filament id="2" used_g="20"/></plate></config>'''
    parsed = Bambu3mfParser().parse(make_archive(tmp_path / "hint.3mf", slice_info=xml, thumbnail=False), plate_hint=2)
    assert parsed.plate_index == 2
    assert parsed.filaments[0].used_g == Decimal("20")


def test_filament_sequence_selects_the_only_active_plate(tmp_path: Path) -> None:
    xml = b'''<config><plate><metadata key="index" value="1"/><filament id="1" used_g="10"/></plate>
      <plate><metadata key="index" value="2"/><filament id="2" used_g="20"/></plate></config>'''
    parsed = Bambu3mfParser().parse(make_archive(
        tmp_path / "sequence.3mf",
        slice_info=xml,
        thumbnail=False,
        extra={"Metadata/filament_sequence.json": b'{"plate_2":{"sequence":[2]}}'},
    ))

    assert parsed.plate_index == 2
    assert parsed.plate_selection_confidence == "HIGH_CONFIDENCE"
    assert parsed.filaments[0].used_g == Decimal("20")


def test_zip_traversal_malformed_zip_and_malformed_xml_are_rejected(tmp_path: Path) -> None:
    unsafe = make_archive(
        tmp_path / "unsafe.3mf",
        slice_info=(FIXTURES / "slice_info.config").read_bytes(),
        extra={"../escape.png": PNG},
    )
    with pytest.raises(Bambu3mfUnsafeArchiveError):
        Bambu3mfParser().parse(unsafe)

    malformed_zip = tmp_path / "bad.3mf"
    malformed_zip.write_bytes(b"not a zip")
    with pytest.raises(Bambu3mfError):
        Bambu3mfParser().parse(malformed_zip)

    malformed_xml = make_archive(tmp_path / "bad-xml.3mf", slice_info=b"<config><plate>", thumbnail=False)
    with pytest.raises(Bambu3mfMalformedMetadataError):
        Bambu3mfParser().parse(malformed_xml)


def test_oversized_member_is_rejected_without_decompression(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(three_mf, "MAX_MEMBER_UNCOMPRESSED_BYTES", 10)
    archive = make_archive(tmp_path / "large.3mf", slice_info=b"x" * 11, thumbnail=False)
    with pytest.raises(Bambu3mfArchiveTooLargeError):
        Bambu3mfParser().parse(archive)
