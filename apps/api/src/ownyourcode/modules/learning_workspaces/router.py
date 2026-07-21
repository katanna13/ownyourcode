"""Authenticated HTTP surface for persisted Existing Repository workspaces."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ownyourcode.core.config import get_settings
from ownyourcode.db.session import get_db_session
from ownyourcode.modules.assessments.openai_client import (
    AssessmentConfigurationError,
    AssessmentIncompleteError,
    AssessmentProviderError,
    AssessmentRateLimitedError,
    AssessmentRefusalError,
    AssessmentTimeoutError,
    OpenAIAssessmentClient,
)
from ownyourcode.modules.authentication.dependencies import get_current_user
from ownyourcode.modules.authentication.models import User
from ownyourcode.modules.learning_workspaces.models import LearningActivityKind
from ownyourcode.modules.learning_workspaces.repository import LearningWorkspaceRepository
from ownyourcode.modules.learning_workspaces.schemas import (
    PersistedActivityPreparationResponse,
    PersistedAttemptResponse,
    PersistedContentResponse,
    PersistedInspectionResponse,
    ProjectWorkspaceResponse,
    WorkspaceAssessmentAttemptRequest,
    WorkspaceContentGenerateRequest,
    WorkspaceLabAttemptRequest,
    WorkspaceOralDefenseAttemptRequest,
    WorkspaceProgressResponse,
    WorkspaceProgressUpdateRequest,
    WorkspaceSecurityAttemptRequest,
    validate_idempotency_key,
)
from ownyourcode.modules.learning_workspaces.service import (
    ExistingRepositoryWorkspaceRequiredError,
    PersistedLearningWorkspaceService,
    StoredWorkspaceContractError,
    StoredWorkspaceSizeError,
    WorkspaceActivityUnavailableError,
    WorkspaceContentRequiredError,
    WorkspaceContextStaleError,
    WorkspaceInspectionRequiredError,
    WorkspaceNotFoundError,
    WorkspaceOperationConflictError,
    WorkspaceOperationPreviouslyFailedError,
)
from ownyourcode.modules.lessons.evidence import EvidenceCatalogError, EvidenceGroundingError
from ownyourcode.modules.lessons.openai_client import (
    LessonConfigurationError,
    LessonIncompleteError,
    LessonProviderError,
    LessonRateLimitedError,
    LessonRefusalError,
    LessonTimeoutError,
    OpenAILessonClient,
)
from ownyourcode.modules.oral_defenses.definition import OralDefenseGroundingError
from ownyourcode.modules.oral_defenses.openai_client import (
    OpenAIOralDefenseClient,
    OralDefenseConfigurationError,
    OralDefenseIncompleteError,
    OralDefenseProviderError,
    OralDefenseRateLimitedError,
    OralDefenseRefusalError,
    OralDefenseTimeoutError,
)
from ownyourcode.modules.repositories.github_client import GitHubClientError
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService


router = APIRouter(tags=["saved learning workspaces"])


def get_workspace_service() -> PersistedLearningWorkspaceService:
    settings = get_settings()
    return PersistedLearningWorkspaceService(
        repository=LearningWorkspaceRepository(),
        inspection_service=PublicRepositoryInspectionService(github_token=settings.github_token),
        lesson_client=OpenAILessonClient(settings),
        assessment_client=OpenAIAssessmentClient(settings),
        oral_defense_client=OpenAIOralDefenseClient(settings),
    )


def workspace_error(error: Exception) -> HTTPException:
    if isinstance(error, WorkspaceNotFoundError):
        return HTTPException(status_code=404, detail="Project not found.")
    if isinstance(error, ExistingRepositoryWorkspaceRequiredError):
        return HTTPException(status_code=422, detail="This saved workspace is available only for Existing Repository projects.")
    if isinstance(error, WorkspaceInspectionRequiredError):
        return HTTPException(status_code=409, detail="Inspect the saved repository before preparing learning content.")
    if isinstance(error, WorkspaceContentRequiredError):
        return HTTPException(status_code=409, detail="Generate saved learning content before opening this activity.")
    if isinstance(error, WorkspaceContextStaleError):
        return HTTPException(status_code=409, detail="Saved workspace content changed. Reload the project and try again.")
    if isinstance(error, WorkspaceActivityUnavailableError):
        return HTTPException(status_code=422, detail="This activity is unavailable for the saved repository evidence.")
    if isinstance(error, WorkspaceOperationPreviouslyFailedError):
        return HTTPException(status_code=409, detail="The previous operation for this Idempotency-Key failed. Send a new key to try again.")
    if isinstance(error, WorkspaceOperationConflictError):
        return HTTPException(status_code=409, detail="This operation is already pending or conflicts with saved workspace state.")
    if isinstance(error, (StoredWorkspaceContractError, StoredWorkspaceSizeError, EvidenceCatalogError, EvidenceGroundingError, OralDefenseGroundingError)):
        return HTTPException(status_code=502, detail="Saved workspace data could not be prepared safely. Please try again.")
    if isinstance(error, GitHubClientError):
        return HTTPException(status_code=error.status_code, detail=error.public_message)
    if isinstance(error, (LessonConfigurationError, AssessmentConfigurationError, OralDefenseConfigurationError)):
        return HTTPException(status_code=503, detail="Learning evaluation is not configured on this server.")
    if isinstance(error, (LessonRateLimitedError, AssessmentRateLimitedError, OralDefenseRateLimitedError)):
        return HTTPException(status_code=429, detail="Learning evaluation is temporarily rate limited. Please try again later.")
    if isinstance(error, (LessonTimeoutError, AssessmentTimeoutError, OralDefenseTimeoutError)):
        return HTTPException(status_code=504, detail="Learning evaluation timed out. Please try again.")
    if isinstance(error, (LessonRefusalError, AssessmentRefusalError, OralDefenseRefusalError)):
        return HTTPException(status_code=422, detail="The submitted learning response could not be evaluated for this request.")
    if isinstance(error, (LessonIncompleteError, AssessmentIncompleteError, OralDefenseIncompleteError, LessonProviderError, AssessmentProviderError, OralDefenseProviderError)):
        return HTTPException(status_code=502, detail="Learning evaluation returned incomplete or unavailable output. Please try again.")
    return HTTPException(status_code=502, detail="Saved workspace processing could not finish safely. Please try again.")


def idempotency_key_or_422(value: str | None) -> str:
    try:
        return validate_idempotency_key(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/{project_id}/workspace", response_model=ProjectWorkspaceResponse)
def get_workspace(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[PersistedLearningWorkspaceService, Depends(get_workspace_service)],
) -> ProjectWorkspaceResponse:
    try:
        return service.get_workspace(session, current_user.id, project_id)
    except Exception as error:
        raise workspace_error(error) from None


@router.post("/{project_id}/workspace/inspection", response_model=PersistedInspectionResponse)
def inspect_workspace_repository(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[PersistedLearningWorkspaceService, Depends(get_workspace_service)],
) -> PersistedInspectionResponse:
    try:
        return service.inspect(session, current_user.id, project_id)
    except Exception as error:
        raise workspace_error(error) from None


@router.post("/{project_id}/workspace/content", response_model=PersistedContentResponse)
def generate_workspace_content(
    project_id: UUID,
    request: WorkspaceContentGenerateRequest,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    service: PersistedLearningWorkspaceService = Depends(get_workspace_service),
) -> PersistedContentResponse:
    try:
        return service.generate_content(
            session, current_user.id, project_id, request, idempotency_key_or_422(idempotency_header)
        )
    except HTTPException:
        raise
    except Exception as error:
        raise workspace_error(error) from None


@router.get("/{project_id}/workspace/assessment", response_model=PersistedActivityPreparationResponse)
def prepare_assessment(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[PersistedLearningWorkspaceService, Depends(get_workspace_service)],
) -> PersistedActivityPreparationResponse:
    return _prepare(project_id, LearningActivityKind.ASSESSMENT, current_user, session, service)


@router.get("/{project_id}/workspace/labs/fastapi-health-check", response_model=PersistedActivityPreparationResponse)
def prepare_lab(
    project_id: UUID, current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)], service: Annotated[PersistedLearningWorkspaceService, Depends(get_workspace_service)],
) -> PersistedActivityPreparationResponse:
    return _prepare(project_id, LearningActivityKind.VERIFIED_LAB, current_user, session, service)


@router.get("/{project_id}/workspace/security-challenges/fastapi-cors", response_model=PersistedActivityPreparationResponse)
def prepare_security_challenge(
    project_id: UUID, current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)], service: Annotated[PersistedLearningWorkspaceService, Depends(get_workspace_service)],
) -> PersistedActivityPreparationResponse:
    return _prepare(project_id, LearningActivityKind.SECURITY_CHALLENGE, current_user, session, service)


@router.get("/{project_id}/workspace/oral-defenses/architecture-boundaries", response_model=PersistedActivityPreparationResponse)
def prepare_oral_defense(
    project_id: UUID, current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)], service: Annotated[PersistedLearningWorkspaceService, Depends(get_workspace_service)],
) -> PersistedActivityPreparationResponse:
    return _prepare(project_id, LearningActivityKind.ORAL_DEFENSE, current_user, session, service)


def _prepare(
    project_id: UUID, kind: LearningActivityKind, current_user: User,
    session: Session, service: PersistedLearningWorkspaceService,
) -> PersistedActivityPreparationResponse:
    try:
        return service.prepare_activity(session, current_user.id, project_id, kind)
    except Exception as error:
        raise workspace_error(error) from None


@router.post("/{project_id}/workspace/assessment/attempts", response_model=PersistedAttemptResponse)
def submit_assessment(
    project_id: UUID, request: WorkspaceAssessmentAttemptRequest,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(get_current_user), session: Session = Depends(get_db_session),
    service: PersistedLearningWorkspaceService = Depends(get_workspace_service),
) -> PersistedAttemptResponse:
    return _submit(lambda key: service.submit_assessment(session, current_user.id, project_id, request, key), idempotency_header)


@router.post("/{project_id}/workspace/labs/fastapi-health-check/attempts", response_model=PersistedAttemptResponse)
def submit_lab(
    project_id: UUID, request: WorkspaceLabAttemptRequest,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(get_current_user), session: Session = Depends(get_db_session),
    service: PersistedLearningWorkspaceService = Depends(get_workspace_service),
) -> PersistedAttemptResponse:
    return _submit(lambda key: service.submit_lab(session, current_user.id, project_id, request, key), idempotency_header)


@router.post("/{project_id}/workspace/security-challenges/fastapi-cors/attempts", response_model=PersistedAttemptResponse)
def submit_security_challenge(
    project_id: UUID, request: WorkspaceSecurityAttemptRequest,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(get_current_user), session: Session = Depends(get_db_session),
    service: PersistedLearningWorkspaceService = Depends(get_workspace_service),
) -> PersistedAttemptResponse:
    return _submit(lambda key: service.submit_security_challenge(session, current_user.id, project_id, request, key), idempotency_header)


@router.post("/{project_id}/workspace/oral-defenses/architecture-boundaries/attempts", response_model=PersistedAttemptResponse)
def submit_oral_defense(
    project_id: UUID, request: WorkspaceOralDefenseAttemptRequest,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(get_current_user), session: Session = Depends(get_db_session),
    service: PersistedLearningWorkspaceService = Depends(get_workspace_service),
) -> PersistedAttemptResponse:
    return _submit(lambda key: service.submit_oral_defense(session, current_user.id, project_id, request, key), idempotency_header)


def _submit(callback, idempotency_header: str | None) -> PersistedAttemptResponse:  # type: ignore[no-untyped-def]
    try:
        return callback(idempotency_key_or_422(idempotency_header))
    except HTTPException:
        raise
    except Exception as error:
        raise workspace_error(error) from None


@router.patch("/{project_id}/workspace/progress", response_model=WorkspaceProgressResponse)
def update_workspace_progress(
    project_id: UUID, request: WorkspaceProgressUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[PersistedLearningWorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceProgressResponse:
    try:
        return service.update_last_viewed_stage(session, current_user.id, project_id, request)
    except Exception as error:
        raise workspace_error(error) from None
