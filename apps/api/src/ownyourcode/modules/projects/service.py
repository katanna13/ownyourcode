from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from ownyourcode.modules.projects.models import (
    Project,
    ProjectSource,
    ProjectStatus,
)
from ownyourcode.modules.projects.repository import (
    OwnedProject,
    ProjectListPage,
    ProjectRepository,
)
from ownyourcode.modules.projects.schemas import (
    ProjectCreateRequest,
    ProjectPatchRequest,
)


class ProjectNotFoundError(Exception):
    pass


@dataclass
class ProjectService:
    repository: ProjectRepository

    def create(
        self, session: Session, owner_id: UUID, request: ProjectCreateRequest
    ) -> OwnedProject:
        now = datetime.now(timezone.utc)
        project = Project(
            id=uuid4(),
            owner_id=owner_id,
            name=request.name,
            description=request.description,
            mode=request.mode,
            status=ProjectStatus.ACTIVE,
            updated_at=now,
            last_activity_at=now,
        )
        source = ProjectSource(
            id=uuid4(),
            project_id=project.id,
            mode=request.mode,
            repository_url=request.repository_url,
            idea_brief=(
                request.idea_brief.model_dump(mode="json")
                if request.idea_brief is not None
                else None
            ),
        )
        with session.begin():
            self.repository.add_project(session, project)
            self.repository.add_source(session, source)
            session.flush()
        return OwnedProject(project=project, source=source)

    def get(self, session: Session, owner_id: UUID, project_id: UUID) -> OwnedProject:
        project = self.repository.get_owned_active(session, owner_id, project_id)
        if project is None:
            raise ProjectNotFoundError
        return project

    def list(
        self, session: Session, owner_id: UUID, limit: int, cursor: str | None
    ) -> ProjectListPage:
        return self.repository.list_owned_active(session, owner_id, limit, cursor)

    def update(
        self,
        session: Session,
        owner_id: UUID,
        project_id: UUID,
        request: ProjectPatchRequest,
    ) -> OwnedProject:
        now = datetime.now(timezone.utc)
        with session.begin():
            owned_project = self.repository.get_owned_active(session, owner_id, project_id)
            if owned_project is None:
                raise ProjectNotFoundError
            if request.name is not None:
                owned_project.project.name = request.name
            if request.description is not None:
                owned_project.project.description = request.description
            owned_project.project.updated_at = now
            owned_project.project.last_activity_at = now
            session.flush()
        return owned_project

    def archive(self, session: Session, owner_id: UUID, project_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        with session.begin():
            owned_project = self.repository.get_owned_active(session, owner_id, project_id)
            if owned_project is None:
                raise ProjectNotFoundError
            owned_project.project.status = ProjectStatus.ARCHIVED
            owned_project.project.archived_at = now
            owned_project.project.updated_at = now
            owned_project.project.last_activity_at = now
            session.flush()
