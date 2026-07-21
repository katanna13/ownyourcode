from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from ownyourcode.modules.authentication.service import resolve_internal_user
from ownyourcode.modules.projects.models import Project
from ownyourcode.modules.projects.repository import ProjectRepository
from ownyourcode.modules.projects.schemas import ProjectCreateRequest
from ownyourcode.modules.projects.service import ProjectService


ALICE_HEADERS = {"Authorization": "Bearer alice-token"}
BOB_HEADERS = {"Authorization": "Bearer bob-token"}


def repository_payload() -> dict[str, object]:
    return {
        "name": "  Learning API  ",
        "description": "  Learn the architecture of a public FastAPI project.  ",
        "mode": "existing_repository",
        "repository_url": "https://github.com/example/learning-api/",
    }


def idea_payload() -> dict[str, object]:
    return {
        "name": "Study planner",
        "description": "Learn how a study-planning product could be designed safely.",
        "mode": "new_idea",
        "idea_brief": {
            "problem": "Learners need a focused way to plan their weekly study sessions.",
            "intended_user": "Independent learners",
            "first_outcome": "Create a practical plan for the next study session.",
            "constraints": ["Keep the first release small"],
        },
    }


def create_project(
    client: TestClient, headers: dict[str, str], payload: dict[str, object]
) -> dict[str, object]:
    response = client.post("/api/v1/projects", headers=headers, json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def test_creates_canonical_repository_and_bounded_new_idea_projects(
    authenticated_client: TestClient,
) -> None:
    repository_project = create_project(
        authenticated_client, ALICE_HEADERS, repository_payload()
    )
    idea_project = create_project(authenticated_client, ALICE_HEADERS, idea_payload())

    assert repository_project["name"] == "Learning API"
    assert repository_project["source"]["repository_url"] == (
        "https://github.com/example/learning-api"
    )
    assert repository_project["source"]["idea_brief"] is None
    assert idea_project["source"]["repository_url"] is None
    assert idea_project["source"]["idea_brief"]["intended_user"] == "Independent learners"
    assert "progress" not in repository_project


@pytest.mark.parametrize(
    "payload",
    [
        {
            **repository_payload(),
            "idea_brief": {
                "problem": "This extra brief should be rejected for a repository project.",
                "intended_user": "Learners",
                "first_outcome": "Understand the project safely.",
            },
        },
        {"name": "Idea", "description": "A valid enough description for testing.", "mode": "new_idea"},
        {
            **idea_payload(),
            "repository_url": "https://github.com/example/not-allowed",
        },
        {
            **idea_payload(),
            "idea_brief": {
                **idea_payload()["idea_brief"],  # type: ignore[arg-type]
                "unexpected": "field",
            },
        },
    ],
)
def test_rejects_invalid_source_mode_combinations(
    authenticated_client: TestClient, payload: dict[str, object]
) -> None:
    response = authenticated_client.post(
        "/api/v1/projects", headers=ALICE_HEADERS, json=payload
    )
    assert response.status_code == 422


def test_list_is_owned_paginated_and_has_no_fake_progress(
    authenticated_client: TestClient,
) -> None:
    alice_one = create_project(authenticated_client, ALICE_HEADERS, repository_payload())
    alice_two = create_project(authenticated_client, ALICE_HEADERS, idea_payload())
    create_project(authenticated_client, BOB_HEADERS, repository_payload())

    response = authenticated_client.get("/api/v1/projects?limit=1", headers=ALICE_HEADERS)
    assert response.status_code == 200
    first_page = response.json()
    assert len(first_page["items"]) == 1
    assert first_page["next_cursor"]
    assert "progress" not in first_page["items"][0]

    second_response = authenticated_client.get(
        f"/api/v1/projects?limit=1&cursor={first_page['next_cursor']}",
        headers=ALICE_HEADERS,
    )
    assert second_response.status_code == 200
    returned_ids = {first_page["items"][0]["id"], second_response.json()["items"][0]["id"]}
    assert returned_ids == {alice_one["id"], alice_two["id"]}
    assert (
        authenticated_client.get("/api/v1/projects?limit=51", headers=ALICE_HEADERS).status_code
        == 422
    )
    assert (
        authenticated_client.get(
            "/api/v1/projects?cursor=not-a-cursor", headers=ALICE_HEADERS
        ).status_code
        == 422
    )


def test_equal_activity_timestamps_have_stable_cursor_ordering(
    authenticated_client: TestClient, test_session_factory
) -> None:  # type: ignore[no-untyped-def]
    created = [
        create_project(authenticated_client, ALICE_HEADERS, repository_payload())
        for _ in range(3)
    ]
    timestamp = datetime(2026, 7, 16, tzinfo=timezone.utc)
    with test_session_factory.begin() as session:
        session.execute(update(Project).values(last_activity_at=timestamp))

    first = authenticated_client.get("/api/v1/projects?limit=1", headers=ALICE_HEADERS)
    second = authenticated_client.get(
        f"/api/v1/projects?limit=1&cursor={first.json()['next_cursor']}",
        headers=ALICE_HEADERS,
    )
    third = authenticated_client.get(
        f"/api/v1/projects?limit=1&cursor={second.json()['next_cursor']}",
        headers=ALICE_HEADERS,
    )
    ids = [first.json()["items"][0]["id"], second.json()["items"][0]["id"], third.json()["items"][0]["id"]]
    assert len(set(ids)) == 3
    assert set(ids) == {project["id"] for project in created}


def test_cross_user_read_update_archive_and_source_access_are_indistinguishable(
    authenticated_client: TestClient,
) -> None:
    project = create_project(authenticated_client, ALICE_HEADERS, repository_payload())
    project_id = project["id"]
    responses = [
        authenticated_client.get(f"/api/v1/projects/{project_id}", headers=BOB_HEADERS),
        authenticated_client.patch(
            f"/api/v1/projects/{project_id}",
            headers=BOB_HEADERS,
            json={"name": "Not allowed"},
        ),
        authenticated_client.delete(f"/api/v1/projects/{project_id}", headers=BOB_HEADERS),
    ]
    missing = authenticated_client.get(
        f"/api/v1/projects/{uuid4()}", headers=BOB_HEADERS
    )
    assert all(response.status_code == 404 for response in responses)
    assert all(response.json() == {"detail": "Project not found."} for response in responses)
    assert missing.json() == {"detail": "Project not found."}
    assert authenticated_client.get(f"/api/v1/projects/{project_id}", headers=ALICE_HEADERS).status_code == 200


def test_patch_and_archive_are_truthful_and_archived_projects_are_hidden(
    authenticated_client: TestClient,
) -> None:
    project = create_project(authenticated_client, ALICE_HEADERS, idea_payload())
    project_id = project["id"]
    patched = authenticated_client.patch(
        f"/api/v1/projects/{project_id}",
        headers=ALICE_HEADERS,
        json={"name": "Updated study planner"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Updated study planner"
    assert patched.json()["last_activity_at"] != project["last_activity_at"]
    assert authenticated_client.delete(
        f"/api/v1/projects/{project_id}", headers=ALICE_HEADERS
    ).status_code == 204
    assert authenticated_client.get(f"/api/v1/projects/{project_id}", headers=ALICE_HEADERS).status_code == 404
    assert authenticated_client.get("/api/v1/projects", headers=ALICE_HEADERS).json()["items"] == []


def test_project_and_source_creation_roll_back_together_on_failure(
    test_session_factory,
) -> None:  # type: ignore[no-untyped-def]
    class FailingSourceRepository(ProjectRepository):
        def add_source(self, session, source):  # type: ignore[no-untyped-def]
            raise RuntimeError("simulated source failure")

    with test_session_factory() as session:
        owner = resolve_internal_user(session, "rollback_user")
        service = ProjectService(repository=FailingSourceRepository())
        with pytest.raises(RuntimeError, match="simulated source failure"):
            service.create(
                session,
                owner.id,
                ProjectCreateRequest.model_validate(repository_payload()),
            )
    with test_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Project)) == 0
