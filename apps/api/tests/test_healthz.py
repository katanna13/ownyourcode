from fastapi.testclient import TestClient

from ownyourcode.main import app


def test_healthz_reports_api_liveness_without_database_access() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok",
                                "service": "ownyourcode-api"}


def test_workspace_content_preflight_allows_authenticated_idempotent_post() -> None:
    """CORS handles preflight before the protected route or database access."""
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/projects/00000000-0000-0000-0000-000000000000/workspace/content",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization, content-type, idempotency-key",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    allowed_headers = {
        value.strip().lower()
        for value in response.headers["access-control-allow-headers"].split(",")
    }
    assert {"authorization", "content-type", "idempotency-key"} <= allowed_headers
    allowed_methods = {
        value.strip().upper()
        for value in response.headers["access-control-allow-methods"].split(",")
    }
    assert {"GET", "POST", "PATCH", "DELETE"} <= allowed_methods
