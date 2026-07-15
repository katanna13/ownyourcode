from fastapi.testclient import TestClient

from ownyourcode.main import app


def test_preview_accepts_and_normalizes_a_new_idea() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/projects/preview",
            json={
                "name": "  Study   Planner  ",
                "description": "  A focused planner for weekly study sessions.  ",
                "mode": "new_idea",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "validated": True,
        "persisted": False,
        "message": "Project details validated. Nothing was saved.",
        "project": {
            "name": "Study Planner",
            "description": "A focused planner for weekly study sessions.",
            "mode": "new_idea",
            "repository_url": None,
        },
    }


def test_preview_accepts_and_normalizes_a_repository_url() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/projects/preview",
            json={
                "name": "Learning API",
                "description": "A FastAPI project I want to understand deeply.",
                "mode": "existing_repository",
                "repository_url": " https://github.com/example/learning-api/ ",
            },
        )

    assert response.status_code == 200
    assert response.json()["project"]["repository_url"] == (
        "https://github.com/example/learning-api"
    )


def test_preview_requires_a_repository_url_for_repository_mode() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/projects/preview",
            json={
                "name": "Learning API",
                "description": "A FastAPI project I want to understand deeply.",
                "mode": "existing_repository",
            },
        )

    assert response.status_code == 422
    messages = [issue.get("msg", "") for issue in response.json()["detail"]]
    assert any("repository_url is required" in message for message in messages)


def test_preview_rejects_malformed_input() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/projects/preview",
            json={
                "name": " ",
                "description": 42,
                "mode": "unsupported_mode",
                "repository_url": "not-a-url",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_preview_cors_preflight_allows_the_frontend_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/projects/preview",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
