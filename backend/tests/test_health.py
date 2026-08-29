from fastapi.testclient import TestClient

from app.main import app


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_local_vite_origin_is_allowed_for_frontend_reads() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/spools",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )


def test_unknown_origin_is_not_allowed() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/health",
            headers={"Origin": "https://example.com"},
        )

    assert "access-control-allow-origin" not in response.headers
