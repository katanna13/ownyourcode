from fastapi.testclient import TestClient

from ownyourcode.main import app


def test_healthz_reports_api_liveness_without_database_access() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok",
                                "service": "ownyourcode-api"}
