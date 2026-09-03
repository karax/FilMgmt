from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.gcode_uploads import get_gcode_parse_service, get_gcode_upload_service
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory, get_db
from app.main import app
from app.models import Material
from app.schemas.gcode_parse import GCodeParseResult, GCodeToolSummary
from app.services.gcode_material_detection_service import (
    MAX_MATERIAL_CANDIDATES,
    GCodeMaterialDetectionService,
)
from app.services.gcode_upload_service import GCodeUploadService


class StubParseService:
    def __init__(self, result: GCodeParseResult) -> None:
        self.result = result
        self.calls = 0

    def parse_upload(self, _upload_id):
        self.calls += 1
        return self.result


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'materials.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def material(
    db: Session,
    name: str,
    *,
    nozzle: tuple[int, int] | None = None,
    bed: tuple[int, int] | None = None,
) -> Material:
    item = Material(
        name=name,
        category=name,
        default_nozzle_temp_min=nozzle[0] if nozzle else None,
        default_nozzle_temp_max=nozzle[1] if nozzle else None,
        default_bed_temp_min=bed[0] if bed else None,
        default_bed_temp_max=bed[1] if bed else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def summary(
    *tools: GCodeToolSummary,
    metadata: dict[str, str] | None = None,
    nozzle: list[float] | None = None,
    bed: list[float] | None = None,
) -> GCodeParseResult:
    return GCodeParseResult(
        parser_version=1,
        upload_id=uuid4(),
        filename="material.gcode",
        source_size_bytes=100,
        line_count=5,
        blank_line_count=0,
        comment_line_count=1,
        command_line_count=4,
        unknown_line_count=0,
        malformed_line_count=0,
        command_counts={"G1": 1},
        units="mm",
        xyz_positioning="absolute",
        extrusion_mode="relative",
        current_tool=tools[-1].tool if tools else 0,
        tools=list(tools),
        total_extrusion_length_mm=sum(
            tool.extrusion_length_mm or 0 for tool in tools
        ),
        total_extrusion_volume_mm3=None,
        nozzle_temperatures_c=nozzle or [],
        bed_temperatures_c=bed or [],
        metadata=metadata or {},
        warnings=[],
    )


def tool(number: int, extrusion: float = 100) -> GCodeToolSummary:
    return GCodeToolSummary(
        tool=number,
        extrusion_length_mm=extrusion,
        extrusion_volume_mm3=None,
    )


def detect(db: Session, parsed: GCodeParseResult):
    parser = StubParseService(parsed)
    result = GCodeMaterialDetectionService(db, parser).detect_upload(parsed.upload_id)
    assert parser.calls == 1
    return result


@pytest.mark.parametrize(
    ("raw", "catalog_name"),
    [("PLA", "PLA"), ("  petg  ", "PETG")],
)
def test_explicit_metadata_matches_catalog_case_and_whitespace(
    db_session: Session,
    raw: str,
    catalog_name: str,
) -> None:
    expected = material(db_session, catalog_name)

    result = detect(db_session, summary(tool(0), metadata={"filament_type": raw}))
    detected = result.tools[0]

    assert detected.material_id == expected.id
    assert detected.material_name == catalog_name
    assert detected.raw_material_label == raw.strip()
    assert detected.confidence == "HIGH"
    assert detected.source == "slicer_metadata"
    assert detected.evidence.metadata_key == "filament_type"
    assert result.is_complete is True


def test_composite_and_plus_names_are_not_collapsed_to_base_material(
    db_session: Session,
) -> None:
    pla = material(db_session, "PLA")
    pla_plus = material(db_session, "PLA+")
    petg = material(db_session, "PETG")

    plus = detect(db_session, summary(tool(0), metadata={"material": "PLA+"})).tools[0]
    composite = detect(
        db_session,
        summary(tool(0), metadata={"material_type": "PETG-CF"}),
    ).tools[0]

    assert plus.material_id == pla_plus.id
    assert plus.material_id != pla.id
    assert composite.material_id is None
    assert composite.raw_material_label == "PETG-CF"
    assert composite.confidence == "HIGH"
    assert composite.material_id != petg.id
    assert composite.warnings == ["explicit_material_not_in_catalog"]


def test_unknown_explicit_material_preserves_label_without_creating_catalog_row(
    db_session: Session,
) -> None:
    material(db_session, "PLA")
    before = db_session.scalar(select(func.count()).select_from(Material))

    result = detect(
        db_session,
        summary(tool(0), metadata={"filament_material": "SuperPLA Xtreme"}),
    )

    assert result.tools[0].raw_material_label == "SuperPLA Xtreme"
    assert result.tools[0].material_id is None
    assert result.tools[0].confidence == "HIGH"
    assert db_session.scalar(select(func.count()).select_from(Material)) == before


def test_filament_settings_id_uses_only_an_unambiguous_catalog_token(
    db_session: Session,
) -> None:
    pla = material(db_session, "PLA")
    material(db_session, "PETG")

    detected = detect(
        db_session,
        summary(
            tool(0),
            metadata={"filament_settings_id": "Bambu PLA Basic @BBL X1C"},
        ),
    ).tools[0]

    assert detected.material_id == pla.id
    assert detected.raw_material_label == "Bambu PLA Basic @BBL X1C"
    assert detected.confidence == "MEDIUM"


def test_multi_tool_metadata_list_maps_only_when_indices_are_unambiguous(
    db_session: Session,
) -> None:
    pla = material(db_session, "PLA")
    petg = material(db_session, "PETG")

    result = detect(
        db_session,
        summary(tool(0), tool(1), metadata={"filament_type": "PLA;PETG"}),
    )

    assert [(item.tool, item.material_id) for item in result.tools] == [
        (0, pla.id),
        (1, petg.id),
    ]
    assert result.is_complete is True


def test_incompatible_list_count_does_not_guess(db_session: Session) -> None:
    material(db_session, "PLA")
    result = detect(
        db_session,
        summary(tool(0), tool(1), metadata={"filament_type": "PLA"}),
    )

    assert all(item.material_id is None for item in result.tools)
    assert result.is_complete is False
    assert "ambiguous_material" in result.warnings


def test_non_contiguous_tools_require_explicit_indexed_metadata(
    db_session: Session,
) -> None:
    pla = material(db_session, "PLA")
    petg = material(db_session, "PETG")

    indexed = detect(
        db_session,
        summary(
            tool(0),
            tool(2),
            metadata={"filament_type_0": "PLA", "filament_type_2": "PETG"},
        ),
    )
    ambiguous = detect(
        db_session,
        summary(tool(0), tool(2), metadata={"filament_type": "PLA,PETG"}),
    )

    assert [(item.tool, item.material_id) for item in indexed.tools] == [
        (0, pla.id),
        (2, petg.id),
    ]
    assert all(item.material_id is None for item in ambiguous.tools)
    assert "ambiguous_material" in ambiguous.warnings


def test_unique_nozzle_and_bed_range_match_is_medium_heuristic(
    db_session: Session,
) -> None:
    pla = material(db_session, "PLA", nozzle=(190, 220), bed=(50, 65))
    material(db_session, "ABS", nozzle=(230, 260), bed=(90, 110))

    detected = detect(
        db_session,
        summary(tool(0), nozzle=[210, 0], bed=[60, 0]),
    ).tools[0]

    assert detected.material_id == pla.id
    assert detected.material_name == "PLA"
    assert detected.confidence == "MEDIUM"
    assert detected.source == "temperature_heuristic"
    assert detected.evidence.nozzle_temperatures_c == [210]
    assert detected.evidence.bed_temperatures_c == [60]


def test_ambiguous_temperatures_return_bounded_candidates_without_selection(
    db_session: Session,
) -> None:
    for name in ["PLA", "PLA+", "PLA Pro", "PLA Tough", "Generic PLA"]:
        material(db_session, name, nozzle=(190, 220), bed=(50, 65))

    detected = detect(
        db_session,
        summary(tool(0), nozzle=[210], bed=[60]),
    ).tools[0]

    assert detected.material_id is None
    assert detected.confidence == "LOW"
    assert detected.source == "temperature_heuristic"
    assert len(detected.candidates) == MAX_MATERIAL_CANDIDATES
    assert {candidate.material_name for candidate in detected.candidates} <= {
        "PLA", "PLA+", "PLA Pro", "PLA Tough", "Generic PLA"
    }
    assert detected.warnings == ["ambiguous_material"]


@pytest.mark.parametrize(
    ("nozzle", "bed"),
    [([210], []), ([], [60])],
)
def test_single_temperature_dimension_never_exceeds_low_confidence(
    db_session: Session,
    nozzle: list[float],
    bed: list[float],
) -> None:
    material(db_session, "PLA", nozzle=(190, 220), bed=(50, 65))

    detected = detect(
        db_session,
        summary(tool(0), nozzle=nozzle, bed=bed),
    ).tools[0]

    assert detected.confidence == "LOW"
    assert detected.material_id is None
    assert [candidate.material_name for candidate in detected.candidates] == ["PLA"]


def test_missing_temperature_data_and_missing_ranges_do_not_invent_match(
    db_session: Session,
) -> None:
    material(db_session, "No ranges")
    no_data = detect(db_session, summary(tool(0))).tools[0]
    no_ranges = detect(
        db_session,
        summary(tool(0), nozzle=[210], bed=[60]),
    ).tools[0]

    assert no_data.confidence == "NONE"
    assert no_ranges.confidence == "NONE"
    assert no_data.material_id is None
    assert no_ranges.material_id is None
    assert "insufficient_temperature_data" in no_data.warnings
    assert "insufficient_temperature_data" in no_ranges.warnings


def test_global_temperatures_are_not_assigned_across_active_multi_tool_file(
    db_session: Session,
) -> None:
    material(db_session, "PLA", nozzle=(190, 220), bed=(50, 65))

    result = detect(
        db_session,
        summary(tool(0), tool(1), nozzle=[210], bed=[60]),
    )

    assert all(item.confidence == "NONE" for item in result.tools)
    assert all(item.material_id is None for item in result.tools)
    assert "multi_tool_temperature_ambiguous" in result.warnings


def test_explicit_metadata_wins_over_temperature_conflict(db_session: Session) -> None:
    petg = material(db_session, "PETG", nozzle=(230, 250), bed=(70, 90))
    material(db_session, "PLA", nozzle=(190, 220), bed=(50, 65))

    detected = detect(
        db_session,
        summary(
            tool(0),
            metadata={"filament_type": "PETG"},
            nozzle=[205],
            bed=[60],
        ),
    ).tools[0]

    assert detected.material_id == petg.id
    assert detected.source == "slicer_metadata"
    assert detected.confidence == "HIGH"
    assert "temperature_metadata_mismatch" in detected.warnings


def test_zero_extrusion_setup_tool_does_not_make_result_incomplete(
    db_session: Session,
) -> None:
    material(db_session, "PLA")

    result = detect(
        db_session,
        summary(
            tool(0),
            tool(1, extrusion=0),
            metadata={"filament_type_0": "PLA"},
        ),
    )

    assert result.tools[0].confidence == "HIGH"
    assert result.tools[1].confidence == "NONE"
    assert result.is_complete is True


@pytest.fixture
def material_detection_api(
    db_session: Session,
    tmp_path: Path,
) -> Iterator[tuple[TestClient, GCodeUploadService]]:
    upload_service = GCodeUploadService(tmp_path / "gcode", 4096, 32)
    app.dependency_overrides[get_gcode_upload_service] = lambda: upload_service
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            yield client, upload_service
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_gcode_upload_service, None)


def test_material_detection_endpoint_reuses_parse_and_is_in_openapi(
    material_detection_api,
    db_session: Session,
) -> None:
    client, upload_service = material_detection_api
    pla = material(db_session, "API PLA")
    created = client.post(
        "/api/gcode/uploads",
        files={
            "file": (
                "api.gcode",
                b"; filament_type = API PLA\nM83\nG1 E10 F600\n",
                "text/plain",
            )
        },
    ).json()
    parse_response = client.post(f'/api/gcode/uploads/{created["upload_id"]}/parse')
    upload_path = upload_service.resolve_upload(created["upload_id"]).path
    original_mtime = upload_path.stat().st_mtime_ns

    response = client.post(
        f'/api/gcode/uploads/{created["upload_id"]}/material-detection'
    )

    assert parse_response.status_code == 200
    assert response.status_code == 200
    assert response.json()["tools"][0]["material_id"] == pla.id
    assert upload_path.stat().st_mtime_ns == original_mtime
    assert upload_path.with_suffix(".parse.json").is_file()
    assert not upload_path.with_suffix(".material-detection.json").exists()
    paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/api/gcode/uploads/{upload_id}/material-detection"]


def test_material_detection_endpoint_handles_missing_and_invalid_upload_ids(
    material_detection_api,
) -> None:
    client, _ = material_detection_api

    missing = client.post(
        f"/api/gcode/uploads/{uuid4()}/material-detection"
    )
    invalid = client.post("/api/gcode/uploads/not-a-uuid/material-detection")

    assert missing.status_code == 404
    assert invalid.status_code == 400


def test_endpoint_can_consume_an_existing_summary_without_opening_gcode(
    db_session: Session,
) -> None:
    pla = material(db_session, "PLA")
    parsed = summary(tool(0), metadata={"filament_type": "PLA"})
    parser = StubParseService(parsed)
    app.dependency_overrides[get_gcode_parse_service] = lambda: parser
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/gcode/uploads/{parsed.upload_id}/material-detection"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_gcode_parse_service, None)

    assert response.status_code == 200
    assert response.json()["tools"][0]["material_id"] == pla.id
    assert parser.calls == 1
