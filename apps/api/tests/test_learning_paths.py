from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from ownyourcode.modules.authentication.service import resolve_internal_user
from ownyourcode.modules.learning_paths.schemas import (
    LearningPathCreateRequest,
    ModuleActivityAttemptRequest,
)
from ownyourcode.modules.learning_paths.service import (
    LearningPathActivityUnavailableError,
    LearningPathNotFoundError,
    LearningPathService,
)
from ownyourcode.modules.learning_workspaces.models import (
    ProjectInspectionSnapshot,
    ProjectLearningProgress,
)
from ownyourcode.modules.learning_workspaces.schemas import (
    INSPECTION_SNAPSHOT_CONTRACT_VERSION,
    StoredInspectionSnapshotPayload,
    canonical_request_hash,
)
from ownyourcode.modules.lessons.evidence import build_evidence_catalog
from ownyourcode.modules.projects.repository import ProjectRepository
from ownyourcode.modules.projects.schemas import ProjectCreateRequest
from ownyourcode.modules.projects.service import ProjectService
from ownyourcode.modules.repositories.schemas import (
    DetectedLanguage,
    DetectedTechnology,
    ImportantFile,
    InspectedPaths,
    RepositoryInspectionResponse,
    RepositoryMetadata,
)


def _inspection() -> RepositoryInspectionResponse:
    return RepositoryInspectionResponse(
        repository=RepositoryMetadata(
            name="persisted-path",
            full_name="acme/persisted-path",
            description="A bounded persisted learning-path fixture.",
            default_branch="main",
            primary_language="Python",
            html_url="https://github.com/acme/persisted-path",
        ),
        languages=[DetectedLanguage(name="Python", bytes=1200)],
        technologies=[
            DetectedTechnology(key="fastapi", label="FastAPI", evidence=["pyproject.toml"]),
            DetectedTechnology(key="react", label="React", evidence=["package.json"]),
            DetectedTechnology(key="docker", label="Docker", evidence=["Dockerfile"]),
        ],
        paths=InspectedPaths(inspected_count=3, returned=["pyproject.toml", "package.json", "Dockerfile"], truncated=False),
        important_files=[
            ImportantFile(path="pyproject.toml", kind="manifest"),
            ImportantFile(path="package.json", kind="manifest"),
            ImportantFile(path="Dockerfile", kind="container"),
        ],
        limitations=["Inspection is bounded and does not review all source files."],
    )


def _project_with_snapshot(test_session_factory, subject: str = "path-owner") -> tuple[UUID, UUID]:  # type: ignore[no-untyped-def]
    with test_session_factory() as session:
        user = resolve_internal_user(session, subject)
        project = ProjectService(ProjectRepository()).create(
            session,
            user.id,
            ProjectCreateRequest.model_validate(
                {
                    "name": "Path fixture",
                    "description": "A persisted Existing Repository path fixture.",
                    "mode": "existing_repository",
                    "repository_url": "https://github.com/acme/persisted-path",
                }
            ),
        )
        inspection = _inspection()
        payload = StoredInspectionSnapshotPayload(
            inspection=inspection,
            evidence_catalog=build_evidence_catalog(inspection),
        )
        snapshot = ProjectInspectionSnapshot(
            id=uuid4(),
            project_id=project.project.id,
            version=1,
            canonical_repository_url=inspection.repository.html_url,
            evidence_fingerprint=canonical_request_hash(payload.model_dump(mode="json")),
            contract_version=INSPECTION_SNAPSHOT_CONTRACT_VERSION,
            payload=payload.model_dump(mode="json"),
        )
        session.add(snapshot)
        session.flush()
        session.add(
            ProjectLearningProgress(
                id=uuid4(), project_id=project.project.id, active_snapshot_id=snapshot.id
            )
        )
        session.commit()
        return user.id, project.project.id


def _create_path(test_session_factory, owner_id: UUID, project_id: UUID):  # type: ignore[no-untyped-def]
    with test_session_factory() as session:
        response = LearningPathService().create_path(
            session,
            owner_id,
            project_id,
            LearningPathCreateRequest(learner_level="junior", learning_goal="Trace the confirmed application boundaries."),
            "path-create-one",
        )
        session.rollback()
        return response


def _submit(test_session_factory, owner_id: UUID, project_id: UUID, module, activity, *, key: str, selected_choice_id: str | None = None, ordered_step_ids: list[str] | None = None, source_code: str | None = None):  # type: ignore[no-untyped-def]
    with test_session_factory() as session:
        response = LearningPathService().submit_attempt(
            session,
            owner_id,
            project_id,
            module.id,
            activity.id,
            ModuleActivityAttemptRequest(
                context_id=activity.context_id,
                selected_choice_id=selected_choice_id,
                ordered_step_ids=ordered_step_ids,
                source_code=source_code,
            ),
            key,
        )
        session.rollback()
        return response


def test_learning_path_freezes_three_modules_and_excludes_private_answers(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory)
    created = _create_path(test_session_factory, owner_id, project_id)

    assert created.mode == "multi_module"
    assert [module.module_key for module in created.modules] == [
        "repository-orientation.v1",
        "architecture-boundaries.v1",
        "validation-failure-paths.v1",
    ]
    assert [module.state for module in created.modules] == ["available", "locked", "locked"]
    assert created.persisted is True
    assert [item.id for item in created.evidence_catalog][:2] == ["repository:name", "repository:default-branch"]
    public_payload = created.model_dump_json()
    assert "expected_choice_id" not in public_payload
    assert "expected_order" not in public_payload
    assert "evaluator_key" not in public_payload

    with test_session_factory() as session:
        restored = LearningPathService().get_path(session, owner_id, project_id)
        assert restored.resume_module_id == created.modules[0].id
        assert restored.modules[0].activities[0].context_id == created.modules[0].activities[0].context_id


def test_learning_path_unlocks_sequentially_and_requires_remediation_after_wrong_evidence(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory)
    created = _create_path(test_session_factory, owner_id, project_id)
    orientation, architecture, validation = created.modules
    orientation_activity = orientation.activities[0]

    failed = _submit(
        test_session_factory,
        owner_id,
        project_id,
        orientation,
        orientation_activity,
        key="orientation-wrong",
        selected_choice_id=orientation_activity.choices[-1].id,
    )
    assert failed.passed is False
    assert failed.module.state == "remediation_required"
    remediation = failed.module.remediation_activities[0]
    assert remediation.id == "evidence-reading-remediation.v1"

    with pytest.raises(LearningPathActivityUnavailableError):
        _submit(
            test_session_factory,
            owner_id,
            project_id,
            orientation,
            orientation_activity,
            key="orientation-blocked",
            selected_choice_id=orientation_activity.choices[0].id,
        )

    remediated = _submit(
        test_session_factory,
        owner_id,
        project_id,
        failed.module,
        remediation,
        key="orientation-remediation",
        selected_choice_id=remediation.choices[0].id,
    )
    assert remediated.passed is True
    assert remediated.module.state == "in_progress"

    completed_orientation = _submit(
        test_session_factory,
        owner_id,
        project_id,
        remediated.module,
        orientation_activity,
        key="orientation-correct",
        selected_choice_id=orientation_activity.choices[0].id,
    )
    assert completed_orientation.module.state == "demonstrated"
    assert completed_orientation.summary.modules_demonstrated == 1

    with test_session_factory() as session:
        refreshed = LearningPathService().get_path(session, owner_id, project_id)
        assert refreshed.modules[1].state == "available"
        assert refreshed.modules[2].state == "locked"

    architecture_activity = refreshed.modules[1].activities[0]
    completed_architecture = _submit(
        test_session_factory,
        owner_id,
        project_id,
        refreshed.modules[1],
        architecture_activity,
        key="architecture-correct",
        ordered_step_ids=["activity:browser", "activity:api", "activity:response"],
    )
    assert completed_architecture.module.state == "demonstrated"

    with test_session_factory() as session:
        refreshed = LearningPathService().get_path(session, owner_id, project_id)
        assert refreshed.modules[2].state == "available"
    health = refreshed.modules[2].activities[0]
    completed_validation = _submit(
        test_session_factory,
        owner_id,
        project_id,
        refreshed.modules[2],
        health,
        key="health-correct",
        source_code='def healthz():\n    return {"status": "ok", "service": "ownyourcode-api"}\n',
    )
    assert completed_validation.passed is True
    assert completed_validation.summary.modules_demonstrated == 3
    assert completed_validation.summary.practical_gates_passed == 2


def test_learning_path_is_owner_scoped(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory)
    _create_path(test_session_factory, owner_id, project_id)
    with test_session_factory() as session:
        other = resolve_internal_user(session, "other-path-owner")
        session.commit()
    with test_session_factory() as session:
        with pytest.raises(LearningPathNotFoundError):
            LearningPathService().get_path(session, other.id, project_id)


def test_learning_path_routes_are_authenticated_and_do_not_project_private_answers(
    test_session_factory, authenticated_client
) -> None:  # type: ignore[no-untyped-def]
    _, project_id = _project_with_snapshot(test_session_factory, subject="user_alice")

    response = authenticated_client.post(
        f"/api/v1/projects/{project_id}/learning-path",
        headers={"Authorization": "Bearer alice-token", "Idempotency-Key": "path-http-one"},
        json={"learner_level": "beginner", "learning_goal": "Understand the stored evidence."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted"] is True
    assert payload["modules"][0]["state"] == "available"
    assert "expected_choice_id" not in response.text
    assert "evaluator_key" not in response.text
