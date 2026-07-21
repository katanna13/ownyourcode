from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ownyourcode.db.session import get_db_session
from ownyourcode.modules.authentication.dependencies import get_current_user
from ownyourcode.modules.authentication.models import User
from ownyourcode.modules.projects.repository import (
    InvalidProjectCursorError,
    OwnedProject,
    ProjectRepository,
)
from ownyourcode.modules.projects.schemas import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectPatchRequest,
    ProjectPreviewRequest,
    ProjectPreviewResponse,
    ProjectResponse,
    ProjectSourceResponse,
)
from ownyourcode.modules.projects.service import ProjectNotFoundError, ProjectService

router = APIRouter(tags=["projects"])


@router.post("/preview", response_model=ProjectPreviewResponse)
def preview_project(project: ProjectPreviewRequest) -> ProjectPreviewResponse:
    """Validate project details and return them without saving anything."""
    return ProjectPreviewResponse(project=project)


def get_project_service() -> ProjectService:
    return ProjectService(repository=ProjectRepository())


def project_response(owned_project: OwnedProject) -> ProjectResponse:
    project = owned_project.project
    source = owned_project.source
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        mode=project.mode,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        last_activity_at=project.last_activity_at,
        source=ProjectSourceResponse(
            mode=source.mode,
            repository_url=source.repository_url,
            idea_brief=source.idea_brief,
        ),
    )


def raise_not_found() -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")


@router.get("", response_model=ProjectListResponse)
def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[ProjectService, Depends(get_project_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> ProjectListResponse:
    try:
        page = service.list(session, current_user.id, limit, cursor)
    except InvalidProjectCursorError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid project cursor.",
        ) from None
    return ProjectListResponse(
        items=[project_response(item) for item in page.items], next_cursor=page.next_cursor
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    return project_response(service.create(session, current_user.id, request))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    try:
        return project_response(service.get(session, current_user.id, project_id))
    except ProjectNotFoundError:
        raise_not_found()


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    request: ProjectPatchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    try:
        return project_response(service.update(session, current_user.id, project_id, request))
    except ProjectNotFoundError:
        raise_not_found()


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_project(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> Response:
    try:
        service.archive(session, current_user.id, project_id)
    except ProjectNotFoundError:
        raise_not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
