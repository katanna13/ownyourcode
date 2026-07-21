"""Authenticated HTTP surface for versioned project learning paths."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ownyourcode.modules.learning_paths.continuous_openai import (
    ContinuousLearningConfigurationError,
    ContinuousLearningProviderError,
    ContinuousLearningRateLimitedError,
    ContinuousLearningTimeoutError,
)
from ownyourcode.modules.learning_paths.continuous_schemas import (
    ContinuousLearningResponse,
    ContinuousLessonAttemptRequest,
    ContinuousLessonAttemptResponse,
)
from ownyourcode.modules.learning_paths.continuous_service import (
    ContinuousLearningDuplicateError,
    ContinuousLearningService,
    ContinuousLearningUnavailableError,
)
from ownyourcode.db.session import get_db_session
from ownyourcode.modules.authentication.dependencies import get_current_user
from ownyourcode.modules.authentication.models import User
from ownyourcode.modules.learning_paths.schemas import (
    LearningPathCreateRequest,
    LearningPathModuleResponse,
    LearningPathResponse,
    ModuleActivityAttemptRequest,
    ModuleAttemptResponse,
)
from ownyourcode.modules.learning_paths.service import (
    LearningPathActivityUnavailableError,
    LearningPathConflictError,
    LearningPathContextStaleError,
    LearningPathExistingRepositoryRequiredError,
    LearningPathInspectionRequiredError,
    LearningPathNotFoundError,
    LearningPathService,
)
from ownyourcode.modules.learning_workspaces.schemas import validate_idempotency_key


router = APIRouter(tags=["project learning paths"])


def get_learning_path_service() -> LearningPathService:
    return LearningPathService()


def get_continuous_learning_service() -> ContinuousLearningService:
    return ContinuousLearningService()


def _idempotency_key_or_422(value: str | None) -> str:
    try:
        return validate_idempotency_key(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


def _path_error(error: Exception) -> HTTPException:
    if isinstance(error, LearningPathNotFoundError):
        return HTTPException(status_code=404, detail="Project or learning path not found.")
    if isinstance(error, LearningPathInspectionRequiredError):
        return HTTPException(status_code=409, detail="Inspect the saved repository before generating a learning path.")
    if isinstance(error, LearningPathExistingRepositoryRequiredError):
        return HTTPException(status_code=422, detail="This saved learning path is available only for Existing Repository projects.")
    if isinstance(error, LearningPathContextStaleError):
        return HTTPException(status_code=409, detail="Saved repository evidence changed. Reload the project and generate a new learning path.")
    if isinstance(error, LearningPathActivityUnavailableError):
        return HTTPException(status_code=422, detail="This learning activity is not available at the current progress state.")
    if isinstance(error, LearningPathConflictError):
        return HTTPException(status_code=409, detail="This learning-path request conflicts with a saved operation. Use a new Idempotency-Key to retry.")
    return HTTPException(status_code=502, detail="The saved learning path could not be processed safely. Please try again.")


def _continuous_error(error: Exception) -> HTTPException:
    if isinstance(error, ContinuousLearningUnavailableError):
        return HTTPException(status_code=409, detail="Complete or resume the current saved lesson before generating another lesson.")
    if isinstance(error, ContinuousLearningConfigurationError):
        return HTTPException(status_code=503, detail="Continuous lesson generation is not configured.")
    if isinstance(error, ContinuousLearningRateLimitedError):
        return HTTPException(status_code=429, detail="Lesson generation is temporarily rate limited. Please try again later.")
    if isinstance(error, ContinuousLearningTimeoutError):
        return HTTPException(status_code=504, detail="Lesson generation timed out safely. Please try again.")
    if isinstance(error, ContinuousLearningDuplicateError):
        return HTTPException(status_code=502, detail="A sufficiently different lesson could not be generated safely. Please try again.")
    if isinstance(error, ContinuousLearningProviderError):
        return HTTPException(status_code=502, detail="The lesson provider could not return safe structured content.")
    return _path_error(error)


@router.get("/{project_id}/learning-path", response_model=LearningPathResponse)
def get_learning_path(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[LearningPathService, Depends(get_learning_path_service)],
) -> LearningPathResponse:
    try:
        return service.get_path(session, current_user.id, project_id)
    except Exception as error:
        raise _path_error(error) from None


@router.post("/{project_id}/learning-path", response_model=LearningPathResponse)
def create_learning_path(
    project_id: UUID,
    request: LearningPathCreateRequest,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    service: LearningPathService = Depends(get_learning_path_service),
) -> LearningPathResponse:
    try:
        return service.create_path(
            session,
            current_user.id,
            project_id,
            request,
            _idempotency_key_or_422(idempotency_header),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise _path_error(error) from None


@router.get("/{project_id}/learning-path/modules/{module_id}", response_model=LearningPathModuleResponse)
def get_learning_path_module(
    project_id: UUID,
    module_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[LearningPathService, Depends(get_learning_path_service)],
) -> LearningPathModuleResponse:
    try:
        return service.get_module(session, current_user.id, project_id, module_id)
    except Exception as error:
        raise _path_error(error) from None


@router.patch("/{project_id}/learning-path/modules/{module_id}/view", response_model=LearningPathModuleResponse)
def mark_learning_path_module_viewed(
    project_id: UUID,
    module_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[LearningPathService, Depends(get_learning_path_service)],
) -> LearningPathModuleResponse:
    try:
        return service.view_module(session, current_user.id, project_id, module_id)
    except Exception as error:
        raise _path_error(error) from None


@router.post(
    "/{project_id}/learning-path/modules/{module_id}/activities/{activity_id}/attempts",
    response_model=ModuleAttemptResponse,
)
def submit_module_activity_attempt(
    project_id: UUID,
    module_id: UUID,
    activity_id: str,
    request: ModuleActivityAttemptRequest,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    service: LearningPathService = Depends(get_learning_path_service),
) -> ModuleAttemptResponse:
    try:
        return service.submit_attempt(
            session,
            current_user.id,
            project_id,
            module_id,
            activity_id,
            request,
            _idempotency_key_or_422(idempotency_header),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise _path_error(error) from None


@router.get(
    "/{project_id}/learning-path/continuous-lessons",
    response_model=ContinuousLearningResponse,
)
def get_continuous_lessons(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[ContinuousLearningService, Depends(get_continuous_learning_service)],
) -> ContinuousLearningResponse:
    try:
        return service.list_lessons(session, current_user.id, project_id)
    except Exception as error:
        raise _continuous_error(error) from None


@router.post(
    "/{project_id}/learning-path/continuous-lessons",
    response_model=ContinuousLearningResponse,
)
def generate_continuous_lesson(
    project_id: UUID,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    service: ContinuousLearningService = Depends(get_continuous_learning_service),
) -> ContinuousLearningResponse:
    try:
        return service.generate_lesson(
            session,
            current_user.id,
            project_id,
            _idempotency_key_or_422(idempotency_header),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise _continuous_error(error) from None


@router.post(
    "/{project_id}/learning-path/continuous-lessons/{lesson_id}/attempts",
    response_model=ContinuousLessonAttemptResponse,
)
def submit_continuous_lesson_attempt(
    project_id: UUID,
    lesson_id: UUID,
    request: ContinuousLessonAttemptRequest,
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    service: ContinuousLearningService = Depends(get_continuous_learning_service),
) -> ContinuousLessonAttemptResponse:
    try:
        return service.submit_attempt(
            session,
            current_user.id,
            project_id,
            lesson_id,
            request,
            _idempotency_key_or_422(idempotency_header),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise _continuous_error(error) from None
