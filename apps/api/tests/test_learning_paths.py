from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from ownyourcode.modules.authentication.service import resolve_internal_user
from ownyourcode.modules.learning_paths.continuous_openai import (
    ContinuousLearningProviderError,
    ContinuousLearningStructuredOutputError,
)
from ownyourcode.modules.learning_paths.router import get_continuous_learning_service
from ownyourcode.modules.learning_paths.continuous_schemas import (
    ContinuousLessonAttemptRequest,
    ContinuousLessonDraft,
    ContinuousTextEvaluation,
    DraftChoiceActivity,
    DraftTextActivity,
)
from ownyourcode.modules.learning_paths.continuous_service import (
    ContinuousLearningService,
    ContinuousLearningUnavailableError,
)
from ownyourcode.modules.learning_paths.schemas import (
    LearningPathCreateRequest,
    ModuleActivityAttemptRequest,
)
from ownyourcode.modules.learning_paths.service import (
    LearningPathActivityUnavailableError,
    LearningPathContextStaleError,
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


def _complete_path(test_session_factory, owner_id: UUID, project_id: UUID):  # type: ignore[no-untyped-def]
    path = _create_path(test_session_factory, owner_id, project_id)
    orientation = path.modules[0]
    _submit(
        test_session_factory,
        owner_id,
        project_id,
        orientation,
        orientation.activities[0],
        key="complete-orientation",
        selected_choice_id=orientation.activities[0].choices[0].id,
    )
    with test_session_factory() as session:
        path = LearningPathService().get_path(session, owner_id, project_id)
    architecture = path.modules[1]
    _submit(
        test_session_factory,
        owner_id,
        project_id,
        architecture,
        architecture.activities[0],
        key="complete-architecture",
        ordered_step_ids=["activity:browser", "activity:api", "activity:response"],
    )
    with test_session_factory() as session:
        path = LearningPathService().get_path(session, owner_id, project_id)
    validation = path.modules[2]
    _submit(
        test_session_factory,
        owner_id,
        project_id,
        validation,
        validation.activities[0],
        key="complete-validation",
        source_code='def healthz():\n    return {"status": "ok", "service": "ownyourcode-api"}\n',
    )
    with test_session_factory() as session:
        return LearningPathService().get_path(session, owner_id, project_id)


class FakeContinuousClient:
    def __init__(self) -> None:
        self.generation_contexts: list[dict[str, object]] = []
        self.evaluation_contexts: list[dict[str, object]] = []
        self.duplicate_once = False
        self.invalid_structured = False
        self.safe_content_provider_error = False

    def ensure_configured(self) -> None:
        return None

    def generate(self, context: dict[str, object]) -> ContinuousLessonDraft:
        self.generation_contexts.append(context)
        if self.safe_content_provider_error:
            raise ContinuousLearningProviderError()
        if self.invalid_structured:
            raise ContinuousLearningStructuredOutputError()
        activity_type = context["required_activity_type"]
        evidence = context["confirmed_evidence_catalog"]
        assert isinstance(evidence, list) and evidence
        evidence_ids = [str(item["id"]) for item in evidence if isinstance(item, dict)]
        if self.duplicate_once and len(self.generation_contexts) > 1 and "rejected_duplicate_candidate" not in context:
            history = context["recent_continuous_lesson_summaries"]
            assert isinstance(history, list) and history and isinstance(history[-1], dict)
            title = "Confirmed evidence"
            focus = str(history[-1]["focus"])
        else:
            title = f"Lesson {len(self.generation_contexts)} about confirmed evidence"
            focus = f"Use confirmed evidence in a bounded learning frame {len(self.generation_contexts)}."
        if activity_type == "test_interpretation":
            activity = DraftChoiceActivity(
                activity_type="test_interpretation",
                prompt="Which interpretation is supported by the displayed deterministic teaching result?",
                choices=["The bounded check supports this result.", "The entire repository was executed."],
                correct_choice_index=0,
                reference_answer="The bounded check supports this result.",
                why_correct="The deterministic result supports only the displayed bounded teaching claim.",
            )
        else:
            activity = DraftTextActivity(
                activity_type=activity_type,
                prompt="Explain how one confirmed evidence item supports a bounded repository claim.",
                reference_answer="A strong answer names confirmed evidence, limits the claim, and separates illustrative behavior from inspected facts.",
                why_correct="It connects a bounded claim to confirmed evidence without inventing uninspected behavior.",
                evaluation_rubric=["Connect one claim to evidence.", "State one inspection limitation."],
            )
        return ContinuousLessonDraft(
            title=title,
            focus=focus,
            objective="Practice making one bounded claim from confirmed repository evidence.",
            explanation="The saved inspection confirms a limited evidence catalog. Use those facts as anchors and label teaching examples as illustrative.",
            project_connection="This practice uses the project snapshot while avoiding claims about source files that were not inspected.",
            confirmed_evidence_ids=evidence_ids[:2],
            illustrative_example="For example, trace a hypothetical request while clearly labeling the flow as illustrative.",
            unknown_or_uninspected=["The bounded inspection does not prove every runtime path or source-level behavior."],
            suggested_next_focus="Try the same evidence through a different activity format or a deeper limitation.",
            activity=activity,
        )

    def evaluate(self, context: dict[str, object]) -> ContinuousTextEvaluation:
        self.evaluation_contexts.append(context)
        evidence = context["confirmed_evidence"]
        assert isinstance(evidence, list) and evidence
        return ContinuousTextEvaluation(
            points=2,
            feedback="The answer connects a repository claim to confirmed evidence and states a useful boundary.",
            evidence_ids=[str(evidence[0]["id"])],
        )


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
    assert "expected_answer" not in public_payload
    assert created.modules[0].attempt_reviews == []

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
    assert failed.review.your_answer.endswith(f"({orientation_activity.choices[-1].id})")
    assert failed.review.expected_answer.endswith(f"({orientation_activity.choices[0].id})")
    assert any(item.expected for item in failed.review.option_feedback)
    assert any("weaker or unrelated" in item.explanation for item in failed.review.option_feedback if not item.expected)
    assert failed.module.attempt_reviews[0].attempt_id == failed.attempt_id
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

    with test_session_factory() as session:
        LearningPathService().view_module(session, owner_id, project_id, orientation.id)
        session.rollback()
    with test_session_factory() as session:
        refreshed = LearningPathService().get_path(session, owner_id, project_id)
        assert refreshed.resume_module_id == architecture.id

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
    assert "Browser boundary" in completed_architecture.review.expected_answer
    assert len(completed_architecture.review.transition_explanations) == 2
    assert "illustrative" in completed_architecture.review.project_teaching

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
    assert completed_validation.review.example_solution == 'def healthz():\n    return {"status": "ok", "service": "ownyourcode-api"}\n'
    assert "without executing learner code" in completed_validation.review.project_teaching
    assert completed_validation.summary.modules_demonstrated == 3
    assert completed_validation.summary.practical_gates_passed == 2

    with test_session_factory() as session:
        LearningPathService().view_module(session, owner_id, project_id, architecture.id)
        session.rollback()
    with test_session_factory() as session:
        completed_path = LearningPathService().get_path(session, owner_id, project_id)
        assert completed_path.resume_module_id == architecture.id
        reviewed_architecture = next(item for item in completed_path.modules if item.id == architecture.id)
        assert reviewed_architecture.attempt_reviews[0].expected_answer == completed_architecture.review.expected_answer


def test_learning_path_is_owner_scoped(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory)
    _create_path(test_session_factory, owner_id, project_id)
    with test_session_factory() as session:
        other = resolve_internal_user(session, "other-path-owner")
        session.commit()
    with test_session_factory() as session:
        with pytest.raises(LearningPathNotFoundError):
            LearningPathService().get_path(session, other.id, project_id)


def test_changed_saved_inspection_marks_the_old_path_stale_without_rewriting_it(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory)
    original = _create_path(test_session_factory, owner_id, project_id)
    with test_session_factory() as session:
        progress = session.query(ProjectLearningProgress).filter_by(project_id=project_id).one()
        old_snapshot = session.get(ProjectInspectionSnapshot, progress.active_snapshot_id)
        assert old_snapshot is not None
        replacement = ProjectInspectionSnapshot(
            id=uuid4(),
            project_id=project_id,
            version=2,
            canonical_repository_url=old_snapshot.canonical_repository_url,
            evidence_fingerprint="d" * 64,
            contract_version=old_snapshot.contract_version,
            payload=old_snapshot.payload,
        )
        session.add(replacement)
        session.flush()
        progress.active_snapshot_id = replacement.id
        session.commit()

    with test_session_factory() as session:
        stale = LearningPathService().get_path(session, owner_id, project_id)
        assert stale.stale is True
        assert stale.path_id == original.path_id
        assert stale.modules == []

    with test_session_factory() as session:
        refreshed = LearningPathService().create_path(
            session,
            owner_id,
            project_id,
            LearningPathCreateRequest(learner_level="junior"),
            "path-create-after-reinspection",
        )
        assert refreshed.path_version == 2
        assert refreshed.stale is False


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

    viewed = authenticated_client.patch(
        f"/api/v1/projects/{project_id}/learning-path/modules/{payload['modules'][0]['id']}/view",
        headers={"Authorization": "Bearer alice-token"},
    )
    assert viewed.status_code == 200
    assert viewed.json()["id"] == payload["modules"][0]["id"]


def test_continuous_learning_requires_completion_and_persists_one_lesson_and_attempt(
    test_session_factory,
) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory, subject="continuous-owner")
    _create_path(test_session_factory, owner_id, project_id)
    client = FakeContinuousClient()
    service = ContinuousLearningService(client=client)

    with test_session_factory() as session:
        with pytest.raises(ContinuousLearningUnavailableError):
            service.generate_lesson(session, owner_id, project_id, "continuous-before-complete")

    completed = _complete_path(test_session_factory, owner_id, project_id)
    assert all(module.state == "demonstrated" for module in completed.modules)

    with test_session_factory() as session:
        generated = service.generate_lesson(session, owner_id, project_id, "continuous-generate-one")
    assert generated.available is True
    assert len(generated.lessons) == 1
    lesson = generated.lessons[0]
    assert lesson.sequence == 1
    assert lesson.completed is False
    assert lesson.review is None
    assert set(lesson.confirmed_evidence_ids).issubset({item.id for item in generated.evidence_catalog})
    public_json = lesson.model_dump_json()
    assert "reference_answer" not in public_json
    assert "expected_choice_id" not in public_json
    assert "evaluator_key" not in public_json
    assert "evaluation_rubric" not in public_json

    with test_session_factory() as session:
        attempted = service.submit_attempt(
            session,
            owner_id,
            project_id,
            lesson.id,
            ContinuousLessonAttemptRequest(
                context_id=lesson.activity.context_id,
                answer_text="Confirmed FastAPI evidence supports a bounded API claim, while exact runtime behavior remains uninspected.",
            ),
            "continuous-attempt-one",
        )
    assert attempted.lesson.completed is True
    assert attempted.lesson.review is not None
    assert attempted.lesson.review.earned_points == 2
    assert "strong answer" in attempted.lesson.review.expected_answer
    assert len(client.evaluation_contexts) == 1

    with test_session_factory() as session:
        restored = service.list_lessons(session, owner_id, project_id)
    assert restored.lessons[0].review == attempted.lesson.review

    with test_session_factory() as session:
        replayed = service.generate_lesson(session, owner_id, project_id, "continuous-generate-one")
    assert len(replayed.lessons) == 1
    assert len(client.generation_contexts) == 1


def test_continuous_learning_uses_history_retries_a_duplicate_once_and_dispatches_deterministically(
    test_session_factory,
) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory, subject="continuous-history-owner")
    _complete_path(test_session_factory, owner_id, project_id)
    client = FakeContinuousClient()
    service = ContinuousLearningService(client=client)

    with test_session_factory() as session:
        first = service.generate_lesson(session, owner_id, project_id, "continuous-history-one")
    first_lesson = first.lessons[0]
    with test_session_factory() as session:
        service.submit_attempt(
            session,
            owner_id,
            project_id,
            first_lesson.id,
            ContinuousLessonAttemptRequest(
                context_id=first_lesson.activity.context_id,
                answer_text="The confirmed framework evidence supports one bounded architecture claim and does not prove uninspected routes.",
            ),
            "continuous-history-attempt-one",
        )

    client.duplicate_once = True
    with test_session_factory() as session:
        second = service.generate_lesson(session, owner_id, project_id, "continuous-history-two")
    assert len(second.lessons) == 2
    assert len(client.generation_contexts) == 3
    second_first_context = client.generation_contexts[1]
    assert second_first_context["recent_continuous_lesson_summaries"]
    assert second_first_context["recent_learner_results"]
    assert "rejected_duplicate_candidate" in client.generation_contexts[2]

    second_lesson = second.lessons[1]
    assert second_lesson.activity_type == "test_interpretation"
    correct_choice = next(
        choice for choice in second_lesson.activity.choices
        if choice.label == "The bounded check supports this result."
    )
    evaluation_calls_before = len(client.evaluation_contexts)
    with test_session_factory() as session:
        evaluated = service.submit_attempt(
            session,
            owner_id,
            project_id,
            second_lesson.id,
            ContinuousLessonAttemptRequest(
                context_id=second_lesson.activity.context_id,
                selected_choice_id=correct_choice.id,
            ),
            "continuous-history-attempt-two",
        )
    assert evaluated.lesson.completed is True
    assert evaluated.lesson.review is not None
    assert evaluated.lesson.review.passed is True
    assert len(client.evaluation_contexts) == evaluation_calls_before


def test_continuous_learning_is_owner_scoped_and_rejects_stale_attempts_without_evaluation(
    test_session_factory,
) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory, subject="continuous-stale-owner")
    _complete_path(test_session_factory, owner_id, project_id)
    client = FakeContinuousClient()
    service = ContinuousLearningService(client=client)
    with test_session_factory() as session:
        generated = service.generate_lesson(session, owner_id, project_id, "continuous-stale-one")
    lesson = generated.lessons[0]

    with test_session_factory() as session:
        other = resolve_internal_user(session, "continuous-other-owner")
        session.commit()
    with test_session_factory() as session:
        with pytest.raises(LearningPathNotFoundError):
            service.list_lessons(session, other.id, project_id)

    with test_session_factory() as session:
        progress = session.query(ProjectLearningProgress).filter_by(project_id=project_id).one()
        prior = session.get(ProjectInspectionSnapshot, progress.active_snapshot_id)
        assert prior is not None
        replacement = ProjectInspectionSnapshot(
            id=uuid4(),
            project_id=project_id,
            version=2,
            canonical_repository_url=prior.canonical_repository_url,
            evidence_fingerprint="e" * 64,
            contract_version=prior.contract_version,
            payload=prior.payload,
        )
        session.add(replacement)
        session.flush()
        progress.active_snapshot_id = replacement.id
        session.commit()

    with test_session_factory() as session:
        with pytest.raises(LearningPathContextStaleError):
            service.submit_attempt(
                session,
                owner_id,
                project_id,
                lesson.id,
                ContinuousLessonAttemptRequest(
                    context_id=lesson.activity.context_id,
                    answer_text="This answer is long enough but must be rejected because the active inspection has changed.",
                ),
                "continuous-stale-attempt",
            )
    assert client.evaluation_contexts == []


def test_invalid_structured_generation_falls_back_to_a_usable_deterministic_lesson(
    test_session_factory,
) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory, subject="continuous-fallback-owner")
    _complete_path(test_session_factory, owner_id, project_id)
    client = FakeContinuousClient()
    client.invalid_structured = True
    service = ContinuousLearningService(client=client)

    with test_session_factory() as session:
        generated = service.generate_lesson(session, owner_id, project_id, "continuous-fallback-one")

    assert len(client.generation_contexts) == 2
    lesson = generated.lessons[0]
    assert lesson.activity_type == "test_interpretation"
    assert lesson.lesson_format == "interpret_deterministic_test_output"
    assert lesson.review is None
    assert "Illustrative teaching example:" in lesson.illustrative_example
    assert set(lesson.confirmed_evidence_ids).issubset({item.id for item in generated.evidence_catalog})
    assert "expected_answer" not in lesson.model_dump_json()
    correct = next(choice for choice in lesson.activity.choices if choice.label.startswith("The displayed catalog detail"))

    with test_session_factory() as session:
        attempted = service.submit_attempt(
            session,
            owner_id,
            project_id,
            lesson.id,
            ContinuousLessonAttemptRequest(
                context_id=lesson.activity.context_id,
                selected_choice_id=correct.id,
            ),
            "continuous-fallback-attempt",
        )

    assert attempted.lesson.completed is True
    assert attempted.lesson.review is not None
    assert attempted.lesson.review.passed is True
    assert attempted.lesson.review.expected_answer == correct.label


def test_safe_content_provider_502_path_returns_persisted_fallback_through_route(
    test_session_factory,
    authenticated_client,
) -> None:  # type: ignore[no-untyped-def]
    owner_id, project_id = _project_with_snapshot(test_session_factory, subject="user_alice")
    _complete_path(test_session_factory, owner_id, project_id)
    client = FakeContinuousClient()
    client.safe_content_provider_error = True
    service = ContinuousLearningService(client=client)
    authenticated_client.app.dependency_overrides[get_continuous_learning_service] = lambda: service
    try:
        generated = authenticated_client.post(
            f"/api/v1/projects/{project_id}/learning-path/continuous-lessons",
            headers={"Authorization": "Bearer alice-token", "Idempotency-Key": "continuous-provider-fallback"},
        )
        assert generated.status_code == 200
        payload = generated.json()
        assert payload["persisted"] is True
        assert len(client.generation_contexts) == 2
        lesson = payload["lessons"][0]
        assert lesson["activity_type"] == "test_interpretation"
        assert lesson["review"] is None
        assert "expected_answer" not in generated.text
        correct = next(
            choice for choice in lesson["activity"]["choices"]
            if choice["label"].startswith("The displayed catalog detail")
        )

        attempted = authenticated_client.post(
            f"/api/v1/projects/{project_id}/learning-path/continuous-lessons/{lesson['id']}/attempts",
            headers={"Authorization": "Bearer alice-token", "Idempotency-Key": "continuous-provider-fallback-attempt"},
            json={
                "context_id": lesson["activity"]["context_id"],
                "selected_choice_id": correct["id"],
                "ordered_step_ids": None,
                "source_code": None,
                "answer_text": None,
            },
        )
        assert attempted.status_code == 200
        assert attempted.json()["lesson"]["completed"] is True
        assert attempted.json()["lesson"]["review"]["expected_answer"] == correct["label"]
    finally:
        authenticated_client.app.dependency_overrides.pop(get_continuous_learning_service, None)
