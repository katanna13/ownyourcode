"""Authenticated HTTP surface for versioned project learning paths."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

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
