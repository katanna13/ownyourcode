from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ownyourcode.modules.assessments.schemas import ExplainBackEvaluation
from ownyourcode.modules.learning_workspaces.models import (
    LearningActivityKind,
    LearningOperationState,
    ProjectLearningContentVersion,
)
from ownyourcode.modules.learning_workspaces.repository import LearningWorkspaceRepository
from ownyourcode.modules.learning_workspaces.schemas import (
    WorkspaceAssessmentAttemptRequest,
    WorkspaceContentGenerateRequest,
    WorkspaceLabAttemptRequest,
    WorkspaceOralDefenseAttemptRequest,
)
from ownyourcode.modules.learning_workspaces.service import (
    PersistedLearningWorkspaceService,
    WorkspaceOperationConflictError,
)
from ownyourcode.modules.lessons.schemas import (
    ArchitectureOrientationLessonDraft,
    ArchitectureWalkthroughStep,
    LessonConcept,
)
from ownyourcode.modules.projects.schemas import ProjectCreateRequest
from ownyourcode.modules.projects.repository import ProjectRepository
from ownyourcode.modules.projects.service import ProjectService
from ownyourcode.modules.repositories.schemas import (
    DetectedLanguage,
    DetectedTechnology,
    ImportantFile,
    InspectedPaths,
    RepositoryInspectionResponse,
    RepositoryMetadata,
)


def repository_payload() -> dict[str, object]:
    return {
        "name": "Saved learning API",
        "description": "Persist one bounded Existing Repository learning workspace.",
        "mode": "existing_repository",
        "repository_url": "https://github.com/acme/saved-learning-api",
    }


def inspection(*, description: str = "A bounded public FastAPI repository.") -> RepositoryInspectionResponse:
    return RepositoryInspectionResponse(
        repository=RepositoryMetadata(
            name="saved-learning-api",
            full_name="acme/saved-learning-api",
            description=description,
            default_branch="main",
            primary_language="Python",
            html_url="https://github.com/acme/saved-learning-api",
        ),
        languages=[DetectedLanguage(name="Python", bytes=4000)],
        technologies=[
            DetectedTechnology(key="fastapi", label="FastAPI", evidence=["pyproject.toml: dependency fastapi"]),
            DetectedTechnology(key="react", label="React", evidence=["package.json: dependency react"]),
            DetectedTechnology(key="docker", label="Docker", evidence=["Dockerfile"]),
        ],
        paths=InspectedPaths(inspected_count=3, returned=["pyproject.toml", "package.json", "Dockerfile"], truncated=False),
        important_files=[
            ImportantFile(path="pyproject.toml", kind="manifest"),
            ImportantFile(path="package.json", kind="manifest"),
            ImportantFile(path="Dockerfile", kind="container"),
        ],
        limitations=["Inspection is a bounded deterministic orientation, not a full source review."],
    )


def lesson() -> ArchitectureOrientationLessonDraft:
    return ArchitectureOrientationLessonDraft(
        title="Understand the saved learning API",
        learning_objective="Identify confirmed API, frontend, and container boundaries from bounded evidence.",
        repository_summary="The saved repository has deterministic Python, FastAPI, React, and Docker evidence.",
        repository_summary_evidence_ids=["repository:name"],
        concepts=[
            LessonConcept(
                title="FastAPI boundary",
                explanation="FastAPI is confirmed from a declared dependency in the bounded evidence catalog.",
                why_it_matters="The framework evidence gives a safe starting point for reasoning about requests and routes.",
                evidence_ids=["technology:fastapi"],
                reflection_question="Which confirmed manifest would you inspect before assuming route structure?",
            ),
            LessonConcept(
                title="React boundary",
                explanation="React is confirmed from deterministic package evidence rather than inferred from a language alone.",
                why_it_matters="A confirmed frontend framework helps distinguish the browser boundary from the API boundary.",
                evidence_ids=["technology:react"],
                reflection_question="Which evidence distinguishes the frontend framework from a generic runtime?",
            ),
        ],
        architecture_walkthrough=[
            ArchitectureWalkthroughStep(
                step="Start from the deterministic repository metadata before drawing conclusions about the implementation.",
                evidence_ids=["repository:default-branch"],
            ),
            ArchitectureWalkthroughStep(
                step="Use the declared framework and container evidence to identify likely boundaries without claiming a full source review.",
                evidence_ids=["technology:fastapi", "technology:docker"],
            ),
        ],
        knowledge_check_questions=[
            "Which evidence confirms the backend framework?",
            "Why should bounded inspection limits remain explicit?",
        ],
        limitations_and_open_questions=["This orientation is limited to bounded inspection evidence."],
    )


class FakeInspectionService:
    def __init__(self) -> None:
        self.calls = 0
        self.urls: list[str] = []
        self._lock = Lock()
        self.response = inspection()

    def inspect_url(self, repository_url: str) -> RepositoryInspectionResponse:
        with self._lock:
            self.calls += 1
            self.urls.append(repository_url)
            return self.response


class SequentialInspectionService(FakeInspectionService):
    def inspect_url(self, repository_url: str) -> RepositoryInspectionResponse:
        with self._lock:
            self.calls += 1
            self.urls.append(repository_url)
            return inspection(description=f"Bounded inspection snapshot {self.calls}.")


class FailingInspectionService(FakeInspectionService):
    def inspect_url(self, repository_url: str) -> RepositoryInspectionResponse:
        raise RuntimeError("upstream failure")


class FakeLessonClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request, catalog):  # type: ignore[no-untyped-def]
        self.calls += 1
        return lesson()


class FakeAssessmentClient:
    def ensure_configured(self) -> None:
        return None

    def evaluate(self, **_: object) -> ExplainBackEvaluation:
        return ExplainBackEvaluation(
            earned_points=2,
            feedback="The explanation is grounded in the selected confirmed evidence.",
        )


class FakeOralDefenseClient:
    def ensure_configured(self) -> None:
        return None

    def evaluate(self, **_: object):  # type: ignore[no-untyped-def]
        raise AssertionError("The oral-defense provider is not needed by this focused persistence test.")


def service(inspector: FakeInspectionService) -> PersistedLearningWorkspaceService:
    return PersistedLearningWorkspaceService(
        repository=LearningWorkspaceRepository(),
        inspection_service=inspector,  # type: ignore[arg-type]
        lesson_client=FakeLessonClient(),  # type: ignore[arg-type]
        assessment_client=FakeAssessmentClient(),  # type: ignore[arg-type]
        oral_defense_client=FakeOralDefenseClient(),  # type: ignore[arg-type]
    )


def saved_project(test_session_factory) -> tuple[UUID, UUID]:  # type: ignore[no-untyped-def]
    with test_session_factory() as session:
        from ownyourcode.modules.authentication.service import resolve_internal_user

        user = resolve_internal_user(session, "workspace-owner")
        project = ProjectService(ProjectRepository()).create(
            session, user.id, ProjectCreateRequest.model_validate(repository_payload())
        )
        session.commit()
        return user.id, project.project.id


def test_saved_workspace_reuses_unchanged_snapshot_freezes_public_definition_and_resumes_assessment(
    test_session_factory,
) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = saved_project(test_session_factory)
    inspector = FakeInspectionService()
    persisted = service(inspector)
    with test_session_factory() as session:
        first = persisted.inspect(session, owner_id, project_id)
        second = persisted.inspect(session, owner_id, project_id)
        assert first.snapshot.version == 1
        assert first.progress.unlocked_stages == ["inspect", "learn"]
        assert first.progress.last_viewed_stage == "inspect"
        assert second.reused is True
        assert second.snapshot.version == 1
        assert second.progress.unlocked_stages == ["inspect", "learn"]
        session.rollback()

        created = persisted.generate_content(
            session,
            owner_id,
            project_id,
            WorkspaceContentGenerateRequest(learner_level="junior", learning_goal="  Learn   the  saved stack. "),
            "content-one",
        )
        session.rollback()
        replay = persisted.generate_content(
            session,
            owner_id,
            project_id,
            WorkspaceContentGenerateRequest(learner_level="junior", learning_goal="Learn the saved stack."),
            "content-one",
        )
        assert created.content.id == replay.content.id
        assert created.content.learning_goal == "Learn the saved stack."

        prepared = persisted.prepare_activity(session, owner_id, project_id, LearningActivityKind.ASSESSMENT)
        assert "assessment_private_definition" not in str(prepared.definition)
        questions = prepared.definition["questions"]
        multiple = next(question for question in questions if question["type"] == "multiple_choice")
        evidence = next(question for question in questions if question["type"] == "evidence_selection")
        explain = next(question for question in questions if question["type"] == "explain_back")
        session.rollback()
        answer = persisted.submit_assessment(
            session,
            owner_id,
            project_id,
            WorkspaceAssessmentAttemptRequest.model_validate({
                "assessment_context_id": prepared.definition["assessment_context_id"],
                "answers": {
                    "multiple_choice": {"question_id": multiple["id"], "selected_option_id": multiple["options"][0]["id"]},
                    "evidence_selection": {"question_id": evidence["id"], "selected_evidence_id": evidence["evidence_choices"][0]["id"]},
                    "explain_back": {"question_id": explain["id"], "answer_text": "The FastAPI evidence is a confirmed dependency and the inspection has explicit limits.", "evidence_ids": [explain["evidence_choices"][0]["id"]]},
                },
            }),
            "assessment-one",
        )
        assert answer.progress.last_viewed_stage == "lab"
        restored = persisted.get_workspace(session, owner_id, project_id)
        assert restored.active_content is not None
        assert restored.progress.summary.assessment_points is not None
        assert "assessment_private_definition" not in restored.model_dump_json()
    assert inspector.calls == 2
    assert inspector.urls == ["https://github.com/acme/saved-learning-api"] * 2


def test_idempotency_key_conflict_and_cross_owner_workspace_are_safe(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = saved_project(test_session_factory)
    persisted = service(FakeInspectionService())
    with test_session_factory() as session:
        persisted.inspect(session, owner_id, project_id)
        persisted.generate_content(session, owner_id, project_id, WorkspaceContentGenerateRequest(learner_level="beginner"), "same-key")
        session.rollback()
        with pytest.raises(WorkspaceOperationConflictError):
            persisted.generate_content(session, owner_id, project_id, WorkspaceContentGenerateRequest(learner_level="intermediate"), "same-key")
        with pytest.raises(Exception) as error:
            persisted.get_workspace(session, uuid4(), project_id)
        assert type(error.value).__name__ == "WorkspaceNotFoundError"


def test_project_lock_serializes_concurrent_snapshot_versions(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = saved_project(test_session_factory)
    persisted = service(SequentialInspectionService())

    def inspect_once(_: int) -> int:
        with test_session_factory() as session:
            return persisted.inspect(session, owner_id, project_id).snapshot.version

    with ThreadPoolExecutor(max_workers=4) as executor:
        versions = list(executor.map(inspect_once, range(4)))
    assert sorted(versions) == [1, 2, 3, 4]


def test_composite_content_snapshot_foreign_key_rejects_cross_project_reference(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    first_owner, first_project = saved_project(test_session_factory)
    with test_session_factory() as session:
        from ownyourcode.modules.authentication.service import resolve_internal_user

        second_owner = resolve_internal_user(session, "second-workspace-owner")
        second_project = ProjectService(ProjectRepository()).create(
            session,
            second_owner.id,
            ProjectCreateRequest.model_validate({
                **repository_payload(),
                "name": "Second saved learning API",
                "repository_url": "https://github.com/acme/second-api",
            }),
        )
        session.commit()

    persisted = service(FakeInspectionService())
    with test_session_factory() as session:
        first_snapshot = persisted.inspect(session, first_owner, first_project).snapshot
        second_snapshot = persisted.inspect(session, second_owner.id, second_project.project.id).snapshot
        session.rollback()
        with pytest.raises(IntegrityError):
            with session.begin():
                session.add(ProjectLearningContentVersion(
                    id=uuid4(), project_id=first_project, inspection_snapshot_id=UUID(str(second_snapshot.id)), version=99,
                    activity_kind=LearningActivityKind.LESSON_GENERATION, idempotency_key="cross-project", request_hash="a" * 64,
                    state=LearningOperationState.PENDING, contract_version="saved-existing-repository-workspace.v1",
                ))
                session.flush()
        assert first_snapshot.id != second_snapshot.id


def test_saved_attempt_contracts_bound_and_safely_normalize_submissions() -> None:
    context_id = "a" * 64
    lab = WorkspaceLabAttemptRequest(lab_context_id=context_id, source_code="def healthz():\r\n\treturn {'status': 'ok'}\r")
    assert lab.source_code == "def healthz():\n\treturn {'status': 'ok'}\n"
    with pytest.raises(ValueError):
        WorkspaceLabAttemptRequest(lab_context_id=context_id, source_code="x\x00")
    with pytest.raises(ValueError):
        WorkspaceOralDefenseAttemptRequest(
            oral_defense_context_id=context_id,
            question_id="architecture-boundaries.question.v1",
            answer_text=" " * 39 + "x",
        )


def test_failed_inspection_keeps_learn_locked(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = saved_project(test_session_factory)
    persisted = service(FailingInspectionService())
    with test_session_factory() as session:
        with pytest.raises(RuntimeError, match="upstream failure"):
            persisted.inspect(session, owner_id, project_id)
        restored = persisted.get_workspace(session, owner_id, project_id)
        assert restored.active_snapshot is None
        assert restored.progress.unlocked_stages == ["inspect"]
        assert restored.progress.last_viewed_stage == "inspect"
