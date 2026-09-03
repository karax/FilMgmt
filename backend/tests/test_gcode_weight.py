from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.gcode_uploads import get_gcode_upload_service
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory, get_db
from app.main import app
from app.models import Material
from app.schemas.gcode_parse import GCodeParseResult, GCodeToolSummary
from app.schemas.gcode_weight import GCodeWeightRequest, GCodeWeightToolRequest
from app.services.gcode_upload_service import GCodeUploadService
from app.services.gcode_weight_service import (
    GCodeWeightInvalidToolError,
    GCodeWeightService,
)


class StubParseService:
    def __init__(self, result: GCodeParseResult) -> None:
        self.result = result
        self.calls = 0

    def parse_upload(self, _upload_id: str | UUID) -> GCodeParseResult:
        self.calls += 1
        return self.result


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'weight.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def parse_result(
    *tools: GCodeToolSummary,
    metadata: dict[str, str] | None = None,
    upload_id: UUID | None = None,
) -> GCodeParseResult:
    return GCodeParseResult(
        parser_version=1,
        upload_id=upload_id or uuid4(),
        filename="weight.gcode",
        source_size_bytes=10,
        line_count=1,
        blank_line_count=0,
        comment_line_count=0,
        command_line_count=1,
        unknown_line_count=0,
        malformed_line_count=0,
        command_counts={"G1": 1},
        units="mm",
        xyz_positioning="absolute",
        extrusion_mode="relative",
        current_tool=tools[-1].tool if tools else 0,
        tools=list(tools),
        total_extrusion_length_mm=None,
        total_extrusion_volume_mm3=None,
        nozzle_temperatures_c=[],
        bed_temperatures_c=[],
        metadata=metadata or {},
        warnings=[],
    )


def calculate(
    db: Session,
    summary: GCodeParseResult,
    request: GCodeWeightRequest,
):
    parser = StubParseService(summary)
    result = GCodeWeightService(db, parser).calculate_upload(summary.upload_id, request)
    assert parser.calls == 1
    return result


def material(db: Session, name: str, density: Decimal | None) -> Material:
    item = Material(name=name, category="TEST", density_g_cm3=density)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_linear_formula_uses_circular_area_and_decimal_precision(db_session: Session) -> None:
    pla = material(db_session, "PLA", Decimal("1.240"))
    summary = parse_result(GCodeToolSummary(tool=0, extrusion_length_mm=1000, extrusion_volume_mm3=None))

    result = calculate(
        db_session,
        summary,
        GCodeWeightRequest(tools=[GCodeWeightToolRequest(tool=0, material_id=pla.id, filament_diameter_mm=Decimal("1.75"))]),
    )

    assert result.tools[0].estimated_weight_g == Decimal("2.983")
    assert result.tools[0].calculated_volume_mm3 == Decimal("2405.282")
    assert result.tools[0].density_source == "material"
    assert result.tools[0].diameter_source == "request"
    assert result.total_estimated_weight_g == Decimal("2.983")
    assert result.is_complete is True


def test_length_scales_linearly_and_diameter_scales_quadratically(db_session: Session) -> None:
    pla = material(db_session, "PLA", Decimal("1.240"))
    request = lambda diameter: GCodeWeightRequest(tools=[GCodeWeightToolRequest(tool=0, material_id=pla.id, filament_diameter_mm=Decimal(diameter))])
    one = calculate(db_session, parse_result(GCodeToolSummary(tool=0, extrusion_length_mm=1000, extrusion_volume_mm3=None)), request("1.75"))
    two = calculate(db_session, parse_result(GCodeToolSummary(tool=0, extrusion_length_mm=2000, extrusion_volume_mm3=None)), request("1.75"))
    double_diameter = calculate(db_session, parse_result(GCodeToolSummary(tool=0, extrusion_length_mm=1000, extrusion_volume_mm3=None)), request("3.50"))

    assert two.tools[0].estimated_weight_g == Decimal("5.965")
    assert double_diameter.tools[0].estimated_weight_g == Decimal("11.930")


def test_volumetric_extrusion_uses_volume_directly_without_diameter(db_session: Session) -> None:
    summary = parse_result(
        GCodeToolSummary(tool=0, extrusion_length_mm=None, extrusion_volume_mm3=1000),
        metadata={"filament_density": "1.24"},
    )

    result = calculate(db_session, summary, GCodeWeightRequest())

    tool = result.tools[0]
    assert tool.extrusion_mode == "volumetric"
    assert tool.filament_diameter_mm is None
    assert tool.density_source == "gcode_metadata"
    assert tool.estimated_weight_g == Decimal("1.240")


def test_zero_extrusion_is_known_zero_and_not_null(db_session: Session) -> None:
    summary = parse_result(GCodeToolSummary(tool=0, extrusion_length_mm=0, extrusion_volume_mm3=None))
    result = calculate(
        db_session,
        summary,
        GCodeWeightRequest(tools=[GCodeWeightToolRequest(tool=0, filament_diameter_mm=Decimal("1.75"))]),
    )

    assert result.tools[0].estimated_weight_g is None
    assert "missing_density" in result.tools[0].warnings

    no_extrusion = calculate(
        db_session,
        parse_result(GCodeToolSummary(tool=0, extrusion_length_mm=None, extrusion_volume_mm3=None)),
        GCodeWeightRequest(),
    )
    assert no_extrusion.tools[0].estimated_weight_g == Decimal("0")


def test_missing_inputs_produce_partial_result_without_false_total(db_session: Session) -> None:
    pla = material(db_session, "PLA", Decimal("1.240"))
    summary = parse_result(
        GCodeToolSummary(tool=0, extrusion_length_mm=1000, extrusion_volume_mm3=None),
        GCodeToolSummary(tool=1, extrusion_length_mm=1000, extrusion_volume_mm3=None),
    )
    result = calculate(
        db_session,
        summary,
        GCodeWeightRequest(tools=[GCodeWeightToolRequest(tool=0, material_id=pla.id, filament_diameter_mm=Decimal("1.75"))]),
    )

    assert result.tools[0].estimated_weight_g == Decimal("2.983")
    assert result.tools[1].estimated_weight_g is None
    assert set(result.tools[1].warnings) == {"missing_density", "missing_filament_diameter"}
    assert result.known_estimated_weight_g == Decimal("2.983")
    assert result.total_estimated_weight_g is None
    assert result.is_complete is False
    assert "incomplete_weight_estimate" in result.warnings


def test_metadata_is_per_tool_and_material_density_has_priority(db_session: Session) -> None:
    custom = material(db_session, "Custom", Decimal("1.500"))
    summary = parse_result(
        GCodeToolSummary(tool=0, extrusion_length_mm=1000, extrusion_volume_mm3=None),
        GCodeToolSummary(tool=1, extrusion_length_mm=1000, extrusion_volume_mm3=None),
        metadata={"filament_diameter": "1.75,2.85", "filament_density": "1.24,1.10"},
    )
    result = calculate(
        db_session,
        summary,
        GCodeWeightRequest(tools=[GCodeWeightToolRequest(tool=1, material_id=custom.id)]),
    )

    assert result.tools[0].diameter_source == "gcode_metadata"
    assert result.tools[0].density_source == "gcode_metadata"
    assert result.tools[1].filament_diameter_mm == Decimal("2.85")
    assert result.tools[1].density_g_cm3 == Decimal("1.500")
    assert result.tools[1].density_source == "material"
    assert result.total_estimated_weight_g is not None


def test_selected_material_without_density_does_not_fall_back_or_invent_weight(db_session: Session) -> None:
    unknown = material(db_session, "Unknown", None)
    summary = parse_result(
        GCodeToolSummary(tool=0, extrusion_length_mm=1000, extrusion_volume_mm3=None),
        metadata={"filament_density": "1.24", "filament_diameter": "1.75"},
    )
    result = calculate(
        db_session,
        summary,
        GCodeWeightRequest(tools=[GCodeWeightToolRequest(tool=0, material_id=unknown.id)]),
    )

    assert result.tools[0].density_g_cm3 is None
    assert result.tools[0].density_source == "not_available"
    assert result.tools[0].estimated_weight_g is None
    assert "missing_density" in result.tools[0].warnings


def test_invalid_physical_metadata_is_ignored_with_a_bounded_warning(db_session: Session) -> None:
    summary = parse_result(
        GCodeToolSummary(tool=0, extrusion_length_mm=1000, extrusion_volume_mm3=None),
        metadata={"filament_density": "NaN", "filament_diameter": "500"},
    )
    result = calculate(db_session, summary, GCodeWeightRequest())

    assert result.tools[0].estimated_weight_g is None
    assert result.warnings.count("metadata_value_invalid") == 1


def test_linear_and_volumetric_tools_use_their_own_formula(db_session: Session) -> None:
    pla = material(db_session, "PLA", Decimal("1.240"))
    summary = parse_result(
        GCodeToolSummary(tool=0, extrusion_length_mm=1000, extrusion_volume_mm3=None),
        GCodeToolSummary(tool=1, extrusion_length_mm=None, extrusion_volume_mm3=1000),
    )
    result = calculate(
        db_session,
        summary,
        GCodeWeightRequest(tools=[
            GCodeWeightToolRequest(tool=0, material_id=pla.id, filament_diameter_mm=Decimal("1.75")),
            GCodeWeightToolRequest(tool=1, material_id=pla.id),
        ]),
    )

    assert result.tools[0].estimated_weight_g == Decimal("2.983")
    assert result.tools[1].estimated_weight_g == Decimal("1.240")
    assert result.total_estimated_weight_g == Decimal("4.223")


def test_unknown_tool_and_invalid_diameter_are_rejected(db_session: Session) -> None:
    summary = parse_result(GCodeToolSummary(tool=0, extrusion_length_mm=1, extrusion_volume_mm3=None))
    with pytest.raises(GCodeWeightInvalidToolError):
        calculate(db_session, summary, GCodeWeightRequest(tools=[GCodeWeightToolRequest(tool=8, filament_diameter_mm=Decimal("1.75"))]))
    with pytest.raises(ValidationError):
        GCodeWeightToolRequest(tool=0, filament_diameter_mm=Decimal("0"))
    with pytest.raises(ValidationError):
        GCodeWeightToolRequest(tool=0, filament_diameter_mm=Decimal("NaN"))
    with pytest.raises(ValidationError):
        GCodeWeightToolRequest(tool=0, filament_diameter_mm=Decimal("500"))


def test_weight_endpoint_reuses_parse_summary_and_exposes_openapi(
    db_session: Session,
    tmp_path: Path,
) -> None:
    upload_service = GCodeUploadService(
        storage_directory=tmp_path / "gcode",
        max_upload_bytes=1024,
        chunk_size=16,
    )
    pla = material(db_session, "API PLA", Decimal("1.240"))
    app.dependency_overrides[get_gcode_upload_service] = lambda: upload_service
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/gcode/uploads",
                files={"file": ("api.gcode", b"M83\nG1 E1000\n", "text/plain")},
            ).json()
            parse_response = client.post(f'/api/gcode/uploads/{created["upload_id"]}/parse')
            upload_path = upload_service.resolve_upload(created["upload_id"]).path
            original_mtime = upload_path.stat().st_mtime_ns

            response = client.post(
                f'/api/gcode/uploads/{created["upload_id"]}/weight',
                json={"tools": [{"tool": 0, "material_id": pla.id, "filament_diameter_mm": "1.75"}]},
            )

            assert parse_response.status_code == 200
            assert response.status_code == 200
            assert response.json()["total_estimated_weight_g"] == "2.983"
            assert upload_path.stat().st_mtime_ns == original_mtime
            assert upload_path.with_suffix(".parse.json").is_file()
            paths = client.get("/openapi.json").json()["paths"]
            assert "post" in paths["/api/gcode/uploads/{upload_id}/weight"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_gcode_upload_service, None)


def test_weight_endpoint_reports_missing_upload_material_and_invalid_tool(
    db_session: Session,
    tmp_path: Path,
) -> None:
    upload_service = GCodeUploadService(tmp_path / "gcode", 1024, 16)
    app.dependency_overrides[get_gcode_upload_service] = lambda: upload_service
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            missing = client.post(f"/api/gcode/uploads/{uuid4()}/weight", json={"tools": []})
            created = client.post(
                "/api/gcode/uploads",
                files={"file": ("api.gcode", b"M83\nG1 E1\n", "text/plain")},
            ).json()
            base = f'/api/gcode/uploads/{created["upload_id"]}/weight'
            missing_material = client.post(base, json={"tools": [{"tool": 0, "material_id": 99999, "filament_diameter_mm": 1.75}]})
            invalid_tool = client.post(base, json={"tools": [{"tool": 8, "filament_diameter_mm": 1.75}]})

            assert missing.status_code == 404
            assert missing_material.status_code == 404
            assert invalid_tool.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_gcode_upload_service, None)
