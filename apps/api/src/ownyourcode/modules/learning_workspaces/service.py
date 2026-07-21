"""Persist and resume one bounded Existing Repository learning workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from ownyourcode.modules.assessments.definition import AssessmentDefinition
from ownyourcode.modules.assessments.openai_client import OpenAIAssessmentClient
from ownyourcode.modules.assessments.schemas import (
    AssessmentEvaluationRequest,
    AssessmentEvaluationResponse,
    AssessmentScore,
    DeterministicFeedback,
    EVIDENCE_SELECTION_QUESTION_ID,
    EvidenceSelectionQuestion,
    EXPLAIN_BACK_QUESTION_ID,
    ExplainBackFeedback,
    ExplainBackQuestion,
    MultipleChoiceQuestion,
    MULTIPLE_CHOICE_QUESTION_ID,
)
from ownyourcode.modules.labs.schemas import (
    FastAPIHealthCheckLabAvailableResponse,
    LabEvaluationRequest,
    LabEvaluationResponse,
)
from ownyourcode.modules.labs.verifier import verify_fastapi_health_check
from ownyourcode.modules.learning_workspaces.builders import build_frozen_workspace_definition
from ownyourcode.modules.learning_workspaces.models import (
    LearningActivityKind,
    LearningOperationState,
    ProjectInspectionSnapshot,
    ProjectLearningAttempt,
    ProjectLearningContentVersion,
    ProjectLearningProgress,
)
from ownyourcode.modules.learning_workspaces.repository import LearningWorkspaceRepository
from ownyourcode.modules.learning_workspaces.schemas import (
    INSPECTION_SNAPSHOT_CONTRACT_VERSION,
    MAX_STORED_WORKSPACE_DEFINITION_BYTES,
    WORKSPACE_DEFINITION_CONTRACT_VERSION,
    CurrentProjectLearningSummary,
    PersistedActivityPreparationResponse,
    PersistedAttemptResponse,
    PersistedContentResponse,
    PersistedInspectionResponse,
    ProjectWorkspaceResponse,
    SavedInspectionSnapshotResponse,
    SavedWorkspaceContentResponse,
    StoredInspectionSnapshotPayload,
    StoredWorkspaceDefinition,
    WorkspaceAssessmentAttemptRequest,
    WorkspaceContentGenerateRequest,
    WorkspaceLabAttemptRequest,
    WorkspaceOralDefenseAttemptRequest,
    WorkspaceProgressResponse,
    WorkspaceProgressUpdateRequest,
    WorkspaceSecurityAttemptRequest,
    canonical_request_hash,
    serialized_size,
)
from ownyourcode.modules.lessons.evidence import EvidenceCatalogError, build_evidence_catalog
from ownyourcode.modules.lessons.openai_client import OpenAILessonClient
from ownyourcode.modules.lessons.schemas import EvidenceCatalog, LessonGenerationRequest
from ownyourcode.modules.oral_defenses.definition import (
    OralDefenseDefinition,
    validate_model_evidence,
)
from ownyourcode.modules.oral_defenses.openai_client import OpenAIOralDefenseClient
from ownyourcode.modules.oral_defenses.schemas import (
    OralDefenseAvailableResponse,
    OralDefenseEvaluationRequest,
    OralDefenseEvaluationResponse,
    OralDefensePoints,
    OralDefenseRubricDimension,
)
from ownyourcode.modules.projects.models import Project, ProjectMode
from ownyourcode.modules.repositories.github_client import GitHubClientError
from ownyourcode.modules.repositories.schemas import RepositoryInspectionResponse
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService
from ownyourcode.modules.security_challenges.schemas import (
    FastAPICorsSecurityChallengeAvailableResponse,
    SecurityChallengeEvaluationRequest,
    SecurityChallengeEvaluationResponse,
)
from ownyourcode.modules.security_challenges.verifier import verify_fastapi_cors_fixture


class WorkspaceNotFoundError(Exception):
    pass


class ExistingRepositoryWorkspaceRequiredError(Exception):
    pass


class WorkspaceInspectionRequiredError(Exception):
    pass


class WorkspaceContentRequiredError(Exception):
    pass


class WorkspaceContextStaleError(Exception):
    pass


class WorkspaceActivityUnavailableError(Exception):
    pass


class WorkspaceOperationConflictError(Exception):
    pass


class WorkspaceOperationPreviouslyFailedError(Exception):
    pass


class StoredWorkspaceContractError(Exception):
    pass


class StoredWorkspaceSizeError(Exception):
    pass


class PersistedLearningWorkspaceService:
    """Coordinate stored definitions without changing public preview endpoints."""

    def __init__(
        self,
        *,
        repository: LearningWorkspaceRepository,
        inspection_service: PublicRepositoryInspectionService,
        lesson_client: OpenAILessonClient,
        assessment_client: OpenAIAssessmentClient,
        oral_defense_client: OpenAIOralDefenseClient,
    ) -> None:
        self._repository = repository
        self._inspection_service = inspection_service
        self._lesson_client = lesson_client
        self._assessment_client = assessment_client
        self._oral_defense_client = oral_defense_client

    def get_workspace(
        self, session: Session, owner_id: UUID, project_id: UUID
    ) -> ProjectWorkspaceResponse:
        owned = self._require_owned_project(session, owner_id, project_id)
        self._require_existing_repository(owned.project.mode)
        progress = self._repository.get_progress(session, project_id)
        snapshot = self._repository.get_snapshot(
            session, project_id, progress.active_snapshot_id if progress else None
        )
        content = self._repository.get_content(
            session, project_id, progress.active_content_version_id if progress else None
        )
        return ProjectWorkspaceResponse(
            active_snapshot=self._snapshot_response(snapshot) if snapshot else None,
            active_content=self._content_response(content, snapshot) if content and snapshot else None,
            progress=self._progress_response(session, project_id, progress, snapshot, content),
        )

    def inspect(
        self, session: Session, owner_id: UUID, project_id: UUID
    ) -> PersistedInspectionResponse:
        # The first read ends before GitHub I/O. The owned source is the only URL.
        owned = self._require_owned_project(session, owner_id, project_id)
        repository_url = self._require_existing_repository_source(owned.project.mode, owned.source.repository_url)
        session.rollback()

        inspection = self._inspection_service.inspect_url(repository_url)
        catalog = build_evidence_catalog(inspection)
        snapshot_payload = StoredInspectionSnapshotPayload(
            inspection=inspection,
            evidence_catalog=catalog,
        )
        fingerprint = canonical_request_hash(
            {
                "contract_version": INSPECTION_SNAPSHOT_CONTRACT_VERSION,
                "canonical_repository_url": inspection.repository.html_url,
                "payload": snapshot_payload.model_dump(mode="json"),
            }
        )
        if serialized_size(snapshot_payload) > MAX_STORED_WORKSPACE_DEFINITION_BYTES:
            raise StoredWorkspaceSizeError()

        # A short locked transaction serializes version allocation and activation.
        with session.begin():
            owned = self._require_owned_project(session, owner_id, project_id, lock=True)
            self._require_existing_repository(owned.project.mode)
            progress = self._repository.get_progress(session, project_id, lock=True)
            if progress is None:
                progress = ProjectLearningProgress(id=uuid4(), project_id=project_id)
                session.add(progress)
                session.flush()
            active = self._repository.get_snapshot(session, project_id, progress.active_snapshot_id)
            if active is not None and active.evidence_fingerprint == fingerprint:
                reused = True
                snapshot = active
            else:
                reused = False
                snapshot = ProjectInspectionSnapshot(
                    id=uuid4(),
                    project_id=project_id,
                    version=self._repository.next_snapshot_version(session, project_id),
                    canonical_repository_url=inspection.repository.html_url,
                    evidence_fingerprint=fingerprint,
                    contract_version=INSPECTION_SNAPSHOT_CONTRACT_VERSION,
                    payload=snapshot_payload.model_dump(mode="json"),
                )
                session.add(snapshot)
                session.flush()
                progress.active_snapshot_id = snapshot.id
                progress.active_content_version_id = None
                progress.assessment_attempt_id = None
                progress.verified_lab_attempt_id = None
                progress.security_challenge_attempt_id = None
                progress.oral_defense_attempt_id = None
                progress.last_viewed_stage = "inspect"
                self._touch_project(owned.project)

        return PersistedInspectionResponse(
            reused=reused,
            snapshot=self._snapshot_response(snapshot),
            progress=self._progress_response(session, project_id, progress, snapshot, None),
        )

    def generate_content(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
        request: WorkspaceContentGenerateRequest,
        idempotency_key: str,
    ) -> PersistedContentResponse:
        request_hash = canonical_request_hash(request.model_dump(mode="json"))
        stale_after_generation = False
        with session.begin():
            owned = self._require_owned_project(session, owner_id, project_id, lock=True)
            self._require_existing_repository(owned.project.mode)
            progress = self._repository.get_progress(session, project_id, lock=True)
            snapshot = self._repository.get_snapshot(
                session, project_id, progress.active_snapshot_id if progress else None
            )
            if progress is None or snapshot is None:
                raise WorkspaceInspectionRequiredError()
            existing = self._repository.find_content_idempotency(
                session, project_id, idempotency_key
            )
            if existing is not None:
                return self._replay_content_or_raise(session, project_id, progress, snapshot, existing, request_hash)
            content = ProjectLearningContentVersion(
                id=uuid4(),
                project_id=project_id,
                inspection_snapshot_id=snapshot.id,
                version=self._repository.next_content_version(session, project_id),
                activity_kind=LearningActivityKind.LESSON_GENERATION,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                state=LearningOperationState.PENDING,
                contract_version=WORKSPACE_DEFINITION_CONTRACT_VERSION,
            )
            session.add(content)
            session.flush()
            snapshot_payload = self._snapshot_payload(snapshot)

        try:
            generated_lesson = self._lesson_client.generate(
                LessonGenerationRequest(
                    repository_url=snapshot.canonical_repository_url,
                    learner_level=request.learner_level,
                    learning_goal=request.learning_goal,
                ),
                snapshot_payload.evidence_catalog,
            )
            definition = build_frozen_workspace_definition(
                inspection=snapshot_payload.inspection,
                catalog=snapshot_payload.evidence_catalog,
                source_inspection_fingerprint=snapshot.evidence_fingerprint,
                learner_level=request.learner_level,
                learning_goal=request.learning_goal,
                lesson=generated_lesson,
            )
            if serialized_size(definition) > MAX_STORED_WORKSPACE_DEFINITION_BYTES:
                raise StoredWorkspaceSizeError()
        except Exception:
            self._fail_content_operation(session, owner_id, project_id, content.id)
            raise

        with session.begin():
            owned = self._require_owned_project(session, owner_id, project_id, lock=True)
            progress = self._repository.get_progress(session, project_id, lock=True)
            stored = self._repository.get_content(session, project_id, content.id)
            if stored is None:
                raise WorkspaceNotFoundError()
            stored.definition_payload = definition.model_dump(mode="json")
            stored.content_fingerprint = canonical_request_hash(stored.definition_payload)
            stored.state = LearningOperationState.COMPLETED
            stored.completed_at = datetime.now(timezone.utc)
            if progress is None or progress.active_snapshot_id != stored.inspection_snapshot_id:
                # Save immutable historical content, but never activate it after a reinspection.
                stale_after_generation = True
            else:
                progress.active_content_version_id = stored.id
                progress.assessment_attempt_id = None
                progress.verified_lab_attempt_id = None
                progress.security_challenge_attempt_id = None
                progress.oral_defense_attempt_id = None
                progress.last_viewed_stage = "learn"
                self._touch_project(owned.project)

        if stale_after_generation:
            raise WorkspaceContextStaleError()

        return PersistedContentResponse(
            content=self._content_response(stored, snapshot),
            progress=self._progress_response(session, project_id, progress, snapshot, stored),
        )

    def prepare_activity(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
        activity_kind: LearningActivityKind,
    ) -> PersistedActivityPreparationResponse:
        self._require_owned_project(session, owner_id, project_id)
        progress, snapshot, content = self._active_workspace(session, project_id)
        definition = self._content_definition(content)
        public_definition: dict[str, Any]
        if activity_kind == LearningActivityKind.ASSESSMENT:
            public_definition = definition.assessment_public_definition.model_dump(mode="json")
            public_definition["persisted"] = True
            public_definition["message"] = "Assessment loaded from saved workspace content."
        elif activity_kind == LearningActivityKind.VERIFIED_LAB:
            public_definition = definition.verified_lab_definition.model_dump(mode="json")
            public_definition["persisted"] = True
            public_definition["message"] = "Verified lab loaded from saved workspace content."
        elif activity_kind == LearningActivityKind.SECURITY_CHALLENGE:
            public_definition = definition.security_challenge_definition.model_dump(mode="json")
            public_definition["persisted"] = True
            public_definition["message"] = "Security challenge loaded from saved workspace content."
        elif activity_kind == LearningActivityKind.ORAL_DEFENSE:
            public_definition = definition.oral_defense_definition.model_dump(mode="json")
            public_definition["persisted"] = True
            public_definition["message"] = "Oral defense loaded from saved workspace content."
        else:
            raise WorkspaceActivityUnavailableError()
        return PersistedActivityPreparationResponse(
            content_version_id=content.id,
            definition=public_definition,
        )

    def submit_assessment(
        self, session: Session, owner_id: UUID, project_id: UUID,
        request: WorkspaceAssessmentAttemptRequest, idempotency_key: str,
    ) -> PersistedAttemptResponse:
        progress, snapshot, content, definition, replay = self._reserve_attempt(
            session, owner_id, project_id, LearningActivityKind.ASSESSMENT,
            idempotency_key, request.model_dump(mode="json"), request.assessment_context_id,
        )
        if replay is not None:
            return replay
        if request.assessment_context_id != definition.assessment_public_definition.assessment_context_id:
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.ASSESSMENT)
            raise WorkspaceContextStaleError()
        try:
            internal = AssessmentEvaluationRequest(
                repository_url=snapshot.canonical_repository_url,
                learner_level=definition.learner_level,
                assessment_context_id=request.assessment_context_id,
                answers=request.answers,
            )
            result = self._evaluate_saved_assessment(definition, snapshot, internal)
        except Exception:
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.ASSESSMENT)
            raise
        return self._complete_attempt(
            session, owner_id, project_id, content.id, LearningActivityKind.ASSESSMENT,
            idempotency_key, result.model_dump(mode="json"), passed=None,
            earned_points=result.score.earned_points,
        )

    def submit_lab(
        self, session: Session, owner_id: UUID, project_id: UUID,
        request: WorkspaceLabAttemptRequest, idempotency_key: str,
    ) -> PersistedAttemptResponse:
        progress, snapshot, content, definition, replay = self._reserve_attempt(
            session, owner_id, project_id, LearningActivityKind.VERIFIED_LAB,
            idempotency_key, request.model_dump(mode="json"), request.lab_context_id,
        )
        if replay is not None:
            return replay
        prepared = definition.verified_lab_definition
        if not isinstance(prepared, FastAPIHealthCheckLabAvailableResponse):
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.VERIFIED_LAB)
            raise WorkspaceActivityUnavailableError()
        if request.lab_context_id != prepared.lab_context_id:
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.VERIFIED_LAB)
            raise WorkspaceContextStaleError()
        try:
            validated = LabEvaluationRequest(
                repository_url=snapshot.canonical_repository_url,
                learner_level=definition.learner_level,
                lab_context_id=request.lab_context_id,
                source_code=request.source_code,
            )
            verification = verify_fastapi_health_check(validated.source_code)
            result = LabEvaluationResponse(
                passed=verification.passed,
                checks=verification.checks,
                feedback=(
                    ["Your healthz teaching fixture matches the required deterministic response."]
                    if verification.passed
                    else [
                        "This lab parses the submitted fixture but never runs it.",
                        "Use one healthz function that returns the required literal response fields.",
                    ]
                ),
                inspection_limitations=self._snapshot_payload(snapshot).inspection.limitations,
            )
        except Exception:
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.VERIFIED_LAB)
            raise
        return self._complete_attempt(
            session, owner_id, project_id, content.id, LearningActivityKind.VERIFIED_LAB,
            idempotency_key, result.model_dump(mode="json"), passed=result.passed,
            earned_points=None,
        )

    def submit_security_challenge(
        self, session: Session, owner_id: UUID, project_id: UUID,
        request: WorkspaceSecurityAttemptRequest, idempotency_key: str,
    ) -> PersistedAttemptResponse:
        progress, snapshot, content, definition, replay = self._reserve_attempt(
            session, owner_id, project_id, LearningActivityKind.SECURITY_CHALLENGE,
            idempotency_key, request.model_dump(mode="json"), request.security_challenge_context_id,
        )
        if replay is not None:
            return replay
        prepared = definition.security_challenge_definition
        if not isinstance(prepared, FastAPICorsSecurityChallengeAvailableResponse):
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.SECURITY_CHALLENGE)
            raise WorkspaceActivityUnavailableError()
        if request.security_challenge_context_id != prepared.security_challenge_context_id:
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.SECURITY_CHALLENGE)
            raise WorkspaceContextStaleError()
        try:
            validated = SecurityChallengeEvaluationRequest(
                repository_url=snapshot.canonical_repository_url,
                learner_level=definition.learner_level,
                security_challenge_context_id=request.security_challenge_context_id,
                source_code=request.source_code,
            )
            verification = verify_fastapi_cors_fixture(validated.source_code)
            result = SecurityChallengeEvaluationResponse(
                passed=verification.passed,
                checks=verification.checks,
                feedback=(
                    ["Your teaching fixture restricts the CORS origin to the required explicit value."]
                    if verification.passed
                    else [
                        "This challenge parses the submitted fixture but never runs it.",
                        "Use only the required server-owned fixture structure and literal CORS settings.",
                    ]
                ),
                inspection_limitations=self._snapshot_payload(snapshot).inspection.limitations,
            )
        except Exception:
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.SECURITY_CHALLENGE)
            raise
        return self._complete_attempt(
            session, owner_id, project_id, content.id, LearningActivityKind.SECURITY_CHALLENGE,
            idempotency_key, result.model_dump(mode="json"), passed=result.passed,
            earned_points=None,
        )

    def submit_oral_defense(
        self, session: Session, owner_id: UUID, project_id: UUID,
        request: WorkspaceOralDefenseAttemptRequest, idempotency_key: str,
    ) -> PersistedAttemptResponse:
        progress, snapshot, content, definition, replay = self._reserve_attempt(
            session, owner_id, project_id, LearningActivityKind.ORAL_DEFENSE,
            idempotency_key, request.model_dump(mode="json"), request.oral_defense_context_id,
        )
        if replay is not None:
            return replay
        prepared = definition.oral_defense_definition
        if not isinstance(prepared, OralDefenseAvailableResponse):
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.ORAL_DEFENSE)
            raise WorkspaceActivityUnavailableError()
        if (
            request.oral_defense_context_id != prepared.oral_defense_context_id
            or request.question_id != prepared.question.id
        ):
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.ORAL_DEFENSE)
            raise WorkspaceContextStaleError()
        try:
            validated = OralDefenseEvaluationRequest(
                repository_url=snapshot.canonical_repository_url,
                learner_level=definition.learner_level,
                oral_defense_context_id=request.oral_defense_context_id,
                question_id=request.question_id,
                answer_text=request.answer_text,
            )
            self._oral_defense_client.ensure_configured()
            model_evaluation = self._oral_defense_client.evaluate(
                learner_level=definition.learner_level,
                question_prompt=prepared.question.prompt,
                boundary_evidence=prepared.question.boundary_evidence,
                inspection_limitations=self._snapshot_payload(snapshot).inspection.limitations,
                learner_answer=validated.answer_text,
            )
            validate_model_evidence(
                model_evaluation,
                OralDefenseDefinition(
                    context_id=prepared.oral_defense_context_id,
                    question=prepared.question,
                ),
            )
            dimensions = [
                OralDefenseRubricDimension(
                    id=item.id,
                    earned_points=item.earned_points,
                    feedback=item.feedback,
                )
                for item in model_evaluation.rubric_dimensions
            ]
            result = OralDefenseEvaluationResponse(
                oral_defense_points=OralDefensePoints(
                    earned_points=sum(item.earned_points for item in dimensions)
                ),
                rubric_dimensions=dimensions,
                evidence_ids=model_evaluation.evidence_ids,
                inspection_limitations=self._snapshot_payload(snapshot).inspection.limitations,
            )
        except Exception:
            self._fail_reserved_attempt(session, owner_id, project_id, content.id, idempotency_key, LearningActivityKind.ORAL_DEFENSE)
            raise
        return self._complete_attempt(
            session, owner_id, project_id, content.id, LearningActivityKind.ORAL_DEFENSE,
            idempotency_key, result.model_dump(mode="json"), passed=None,
            earned_points=result.oral_defense_points.earned_points,
        )

    def update_last_viewed_stage(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
        request: WorkspaceProgressUpdateRequest,
    ) -> WorkspaceProgressResponse:
        with session.begin():
            owned = self._require_owned_project(session, owner_id, project_id, lock=True)
            progress = self._repository.get_progress(session, project_id, lock=True)
            snapshot = self._repository.get_snapshot(session, project_id, progress.active_snapshot_id if progress else None)
            content = self._repository.get_content(session, project_id, progress.active_content_version_id if progress else None)
            response = self._progress_response(session, project_id, progress, snapshot, content)
            if request.last_viewed_stage not in response.unlocked_stages:
                raise WorkspaceOperationConflictError()
            if progress is None:
                raise WorkspaceOperationConflictError()
            progress.last_viewed_stage = request.last_viewed_stage
            self._touch_project(owned.project)
        return self._progress_response(session, project_id, progress, snapshot, content)

    def _reserve_attempt(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
        activity_kind: LearningActivityKind,
        idempotency_key: str,
        submitted_payload: dict[str, Any],
        context_fingerprint: str,
    ) -> tuple[
        ProjectLearningProgress,
        ProjectInspectionSnapshot,
        ProjectLearningContentVersion,
        StoredWorkspaceDefinition,
        PersistedAttemptResponse | None,
    ]:
        request_hash = canonical_request_hash(submitted_payload)
        with session.begin():
            owned = self._require_owned_project(session, owner_id, project_id, lock=True)
            self._require_existing_repository(owned.project.mode)
            progress, snapshot, content = self._active_workspace(session, project_id, lock=True)
            definition = self._content_definition(content)
            existing = self._repository.find_attempt_idempotency(
                session, project_id, content.id, activity_kind, idempotency_key
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise WorkspaceOperationConflictError()
                if existing.state == LearningOperationState.PENDING:
                    raise WorkspaceOperationConflictError()
                if existing.state == LearningOperationState.FAILED:
                    raise WorkspaceOperationPreviouslyFailedError()
                return (
                    progress,
                    snapshot,
                    content,
                    definition,
                    self._attempt_response(session, project_id, progress, snapshot, content, existing),
                )
            attempt = ProjectLearningAttempt(
                id=uuid4(),
                project_id=project_id,
                content_version_id=content.id,
                activity_kind=activity_kind,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                state=LearningOperationState.PENDING,
                context_fingerprint=context_fingerprint,
                submitted_payload=submitted_payload,
            )
            session.add(attempt)
        return progress, snapshot, content, definition, None

    def _complete_attempt(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
        content_id: UUID,
        activity_kind: LearningActivityKind,
        idempotency_key: str,
        result_payload: dict[str, Any],
        *,
        passed: bool | None,
        earned_points: int | None,
    ) -> PersistedAttemptResponse:
        with session.begin():
            owned = self._require_owned_project(session, owner_id, project_id, lock=True)
            progress, snapshot, content = self._active_workspace(session, project_id, lock=True)
            attempt = self._repository.find_attempt_idempotency(
                session, project_id, content_id, activity_kind, idempotency_key
            )
            if attempt is None or attempt.state != LearningOperationState.PENDING:
                raise WorkspaceOperationConflictError()
            attempt.result_payload = result_payload
            attempt.passed = passed
            attempt.earned_points = earned_points
            attempt.state = LearningOperationState.COMPLETED
            attempt.completed_at = datetime.now(timezone.utc)
            if content.id != content_id:
                raise WorkspaceContextStaleError()
            if activity_kind == LearningActivityKind.ASSESSMENT:
                progress.assessment_attempt_id = attempt.id
                progress.last_viewed_stage = "lab"
            elif activity_kind == LearningActivityKind.VERIFIED_LAB and passed:
                # A first successful verification remains the gate for this content version.
                if progress.verified_lab_attempt_id is None:
                    progress.verified_lab_attempt_id = attempt.id
                progress.last_viewed_stage = "secure"
            elif activity_kind == LearningActivityKind.SECURITY_CHALLENGE and passed:
                if progress.security_challenge_attempt_id is None:
                    progress.security_challenge_attempt_id = attempt.id
                progress.last_viewed_stage = "defend"
            elif activity_kind == LearningActivityKind.ORAL_DEFENSE:
                progress.oral_defense_attempt_id = attempt.id
                progress.last_viewed_stage = "score"
            self._touch_project(owned.project)
        return self._attempt_response(session, project_id, progress, snapshot, content, attempt)

    def _fail_content_operation(
        self, session: Session, owner_id: UUID, project_id: UUID, content_id: UUID
    ) -> None:
        with session.begin():
            self._require_owned_project(session, owner_id, project_id, lock=True)
            content = self._repository.get_content(session, project_id, content_id)
            if content is not None and content.state == LearningOperationState.PENDING:
                content.state = LearningOperationState.FAILED
                content.failure_code = "generation_failed"
                content.completed_at = datetime.now(timezone.utc)

    def _fail_reserved_attempt(
        self, session: Session, owner_id: UUID, project_id: UUID, content_id: UUID,
        idempotency_key: str, activity_kind: LearningActivityKind,
    ) -> None:
        with session.begin():
            self._require_owned_project(session, owner_id, project_id, lock=True)
            attempt = self._repository.find_attempt_idempotency(
                session, project_id, content_id, activity_kind, idempotency_key
            )
            if attempt is not None and attempt.state == LearningOperationState.PENDING:
                attempt.state = LearningOperationState.FAILED
                attempt.failure_code = "evaluation_failed"
                attempt.completed_at = datetime.now(timezone.utc)

    def _evaluate_saved_assessment(
        self,
        definition: StoredWorkspaceDefinition,
        snapshot: ProjectInspectionSnapshot,
        request: AssessmentEvaluationRequest,
    ) -> AssessmentEvaluationResponse:
        public = definition.assessment_public_definition
        multiple = next(
            question for question in public.questions if isinstance(question, MultipleChoiceQuestion)
        )
        evidence_question = next(
            question for question in public.questions if isinstance(question, EvidenceSelectionQuestion)
        )
        explain = next(
            question for question in public.questions if isinstance(question, ExplainBackQuestion)
        )
        if request.answers.multiple_choice.selected_option_id not in {item.id for item in multiple.options}:
            raise WorkspaceContextStaleError()
        if request.answers.evidence_selection.selected_evidence_id not in {item.id for item in evidence_question.evidence_choices}:
            raise WorkspaceContextStaleError()
        if any(item not in {choice.id for choice in explain.evidence_choices} for item in request.answers.explain_back.evidence_ids):
            raise WorkspaceContextStaleError()
        snapshot_payload = self._snapshot_payload(snapshot)
        by_id = {item.id: item for item in snapshot_payload.evidence_catalog.items}
        target = by_id.get(definition.assessment_private_definition.target_evidence_id)
        if target is None:
            raise StoredWorkspaceContractError()
        selected_choices = [
            {"id": choice.id, "label": choice.label}
            for choice in explain.evidence_choices
            if choice.id in request.answers.explain_back.evidence_ids
        ]
        self._assessment_client.ensure_configured()
        model = self._assessment_client.evaluate(
            learner_level=definition.learner_level,
            target_label=target.label,
            evidence_choices=selected_choices,
            inspection_limitations=snapshot_payload.inspection.limitations,
            learner_answer=request.answers.explain_back.answer_text,
        )
        multiple_correct = (
            request.answers.multiple_choice.selected_option_id
            == definition.assessment_private_definition.multiple_choice_correct_option_id
        )
        evidence_correct = (
            request.answers.evidence_selection.selected_evidence_id
            == definition.assessment_private_definition.evidence_selection_correct_id
        )
        deterministic_points = int(multiple_correct) + int(evidence_correct)
        return AssessmentEvaluationResponse(
            score=AssessmentScore(earned_points=deterministic_points + model.earned_points),
            feedback=[
                DeterministicFeedback(
                    question_id=MULTIPLE_CHOICE_QUESTION_ID,
                    earned_points=int(multiple_correct),
                    message=(
                        "Your selection matches a claim supported by the deterministic repository orientation."
                        if multiple_correct
                        else "That submitted claim is not supported by this bounded orientation. Revisit the inspection limitations and confirmed evidence."
                    ),
                ),
                DeterministicFeedback(
                    question_id=EVIDENCE_SELECTION_QUESTION_ID,
                    earned_points=int(evidence_correct),
                    message=(
                        "Your selected evidence directly supports the repository-orientation target."
                        if evidence_correct
                        else "That evidence does not directly support the repository-orientation target. Revisit the evidence labels."
                    ),
                ),
            ],
            explain_back_feedback=ExplainBackFeedback(
                question_id=EXPLAIN_BACK_QUESTION_ID,
                earned_points=model.earned_points,
                feedback=model.feedback,
            ),
            inspection_limitations=snapshot_payload.inspection.limitations,
        )

    def _active_workspace(
        self, session: Session, project_id: UUID, *, lock: bool = False
    ) -> tuple[ProjectLearningProgress, ProjectInspectionSnapshot, ProjectLearningContentVersion]:
        progress = self._repository.get_progress(session, project_id, lock=lock)
        snapshot = self._repository.get_snapshot(
            session, project_id, progress.active_snapshot_id if progress else None
        )
        content = self._repository.get_content(
            session, project_id, progress.active_content_version_id if progress else None
        )
        if progress is None or snapshot is None:
            raise WorkspaceInspectionRequiredError()
        if content is None or content.state != LearningOperationState.COMPLETED:
            raise WorkspaceContentRequiredError()
        return progress, snapshot, content

    def _replay_content_or_raise(
        self, session: Session, project_id: UUID, progress: ProjectLearningProgress,
        snapshot: ProjectInspectionSnapshot, content: ProjectLearningContentVersion, request_hash: str,
    ) -> PersistedContentResponse:
        if content.request_hash != request_hash:
            raise WorkspaceOperationConflictError()
        if content.state == LearningOperationState.PENDING:
            raise WorkspaceOperationConflictError()
        if content.state == LearningOperationState.FAILED:
            raise WorkspaceOperationPreviouslyFailedError()
        if progress.active_content_version_id != content.id:
            raise WorkspaceContextStaleError()
        return PersistedContentResponse(
            content=self._content_response(content, snapshot),
            progress=self._progress_response(session, project_id, progress, snapshot, content),
        )

    def _attempt_response(
        self, session: Session, project_id: UUID, progress: ProjectLearningProgress,
        snapshot: ProjectInspectionSnapshot, content: ProjectLearningContentVersion,
        attempt: ProjectLearningAttempt,
    ) -> PersistedAttemptResponse:
        if attempt.result_payload is None:
            raise StoredWorkspaceContractError()
        return PersistedAttemptResponse(
            attempt_id=attempt.id,
            result=attempt.result_payload,
            progress=self._progress_response(session, project_id, progress, snapshot, content),
        )

    @staticmethod
    def _touch_project(project: Project) -> None:
        now = datetime.now(timezone.utc)
        project.updated_at = now
        project.last_activity_at = now

    def _snapshot_payload(self, snapshot: ProjectInspectionSnapshot) -> StoredInspectionSnapshotPayload:
        if snapshot.contract_version != INSPECTION_SNAPSHOT_CONTRACT_VERSION:
            raise StoredWorkspaceContractError()
        try:
            return StoredInspectionSnapshotPayload.model_validate(snapshot.payload)
        except Exception as error:
            raise StoredWorkspaceContractError() from error

    def _content_definition(self, content: ProjectLearningContentVersion) -> StoredWorkspaceDefinition:
        if (
            content.state != LearningOperationState.COMPLETED
            or content.contract_version != WORKSPACE_DEFINITION_CONTRACT_VERSION
            or content.definition_payload is None
        ):
            raise StoredWorkspaceContractError()
        try:
            return StoredWorkspaceDefinition.model_validate(content.definition_payload)
        except Exception as error:
            raise StoredWorkspaceContractError() from error

    def _snapshot_response(self, snapshot: ProjectInspectionSnapshot) -> SavedInspectionSnapshotResponse:
        payload = self._snapshot_payload(snapshot)
        return SavedInspectionSnapshotResponse(
            id=snapshot.id,
            version=snapshot.version,
            evidence_fingerprint=snapshot.evidence_fingerprint,
            inspection=payload.inspection,
        )

    def _content_response(
        self, content: ProjectLearningContentVersion, snapshot: ProjectInspectionSnapshot
    ) -> SavedWorkspaceContentResponse:
        definition = self._content_definition(content)
        payload = self._snapshot_payload(snapshot)
        return SavedWorkspaceContentResponse(
            id=content.id,
            version=content.version,
            source_inspection_fingerprint=definition.source_inspection_fingerprint,
            learner_level=definition.learner_level,
            learning_goal=definition.learning_goal,
            lesson=definition.lesson,
            evidence_catalog=payload.evidence_catalog.items,
            inspection_limitations=payload.inspection.limitations,
            builder_versions=definition.builder_versions,
        )

    def _progress_response(
        self, session: Session, project_id: UUID, progress: ProjectLearningProgress | None,
        snapshot: ProjectInspectionSnapshot | None, content: ProjectLearningContentVersion | None,
    ) -> WorkspaceProgressResponse:
        assessment = self._repository.get_attempt(
            session, project_id, progress.assessment_attempt_id if progress else None
        )
        lab = self._repository.get_attempt(
            session, project_id, progress.verified_lab_attempt_id if progress else None
        )
        security = self._repository.get_attempt(
            session, project_id, progress.security_challenge_attempt_id if progress else None
        )
        oral = self._repository.get_attempt(
            session, project_id, progress.oral_defense_attempt_id if progress else None
        )
        assessment_points = assessment.earned_points if assessment and assessment.state == LearningOperationState.COMPLETED else None
        oral_points = oral.earned_points if oral and oral.state == LearningOperationState.COMPLETED else None
        lab_passed = bool(lab and lab.passed is True)
        security_passed = bool(security and security.passed is True)
        raw = (
            ((assessment_points or 0) / 4) * 30
            + (25 if lab_passed else 0)
            + (20 if security_passed else 0)
            + ((oral_points or 0) / 4) * 25
        )
        unlocked: list[str] = ["inspect"]
        if snapshot is not None:
            unlocked.append("learn")
        if content is not None and content.state == LearningOperationState.COMPLETED:
            unlocked.append("assess")
        if assessment_points is not None:
            unlocked.append("lab")
        if lab_passed:
            unlocked.append("secure")
        if security_passed:
            unlocked.append("defend")
        if oral_points is not None:
            unlocked.append("score")
        last = progress.last_viewed_stage if progress else "inspect"
        if last not in unlocked:
            last = "inspect"
        return WorkspaceProgressResponse(
            last_viewed_stage=last,  # type: ignore[arg-type]
            unlocked_stages=unlocked,  # type: ignore[arg-type]
            assessment_attempt_id=assessment.id if assessment else None,
            verified_lab_attempt_id=lab.id if lab else None,
            security_challenge_attempt_id=security.id if security else None,
            oral_defense_attempt_id=oral.id if oral else None,
            assessment_result=(
                assessment.result_payload
                if assessment and assessment.state == LearningOperationState.COMPLETED
                else None
            ),
            verified_lab_result=(
                lab.result_payload
                if lab and lab.state == LearningOperationState.COMPLETED
                else None
            ),
            security_challenge_result=(
                security.result_payload
                if security and security.state == LearningOperationState.COMPLETED
                else None
            ),
            oral_defense_result=(
                oral.result_payload
                if oral and oral.state == LearningOperationState.COMPLETED
                else None
            ),
            summary=CurrentProjectLearningSummary(
                assessment_points=assessment_points,
                verified_lab_passed=lab_passed,
                security_challenge_passed=security_passed,
                oral_defense_points=oral_points,
                raw_total=raw,
                rounded_total=round(raw),
            ),
        )

    def _require_owned_project(
        self, session: Session, owner_id: UUID, project_id: UUID, *, lock: bool = False
    ):
        owned = self._repository.get_owned_project(session, owner_id, project_id, lock=lock)
        if owned is None:
            raise WorkspaceNotFoundError()
        return owned

    @staticmethod
    def _require_existing_repository(mode: ProjectMode) -> None:
        if mode != ProjectMode.EXISTING_REPOSITORY:
            raise ExistingRepositoryWorkspaceRequiredError()

    def _require_existing_repository_source(
        self, mode: ProjectMode, repository_url: str | None
    ) -> str:
        self._require_existing_repository(mode)
        if repository_url is None:
            raise ExistingRepositoryWorkspaceRequiredError()
        return repository_url
