"""Owner-scoped SQLAlchemy operations for saved learning workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ownyourcode.modules.learning_workspaces.models import (
    LearningActivityKind,
    ProjectInspectionSnapshot,
    ProjectLearningAttempt,
    ProjectLearningContentVersion,
    ProjectLearningProgress,
)
from ownyourcode.modules.projects.models import Project, ProjectSource, ProjectStatus


@dataclass(frozen=True)
class OwnedWorkspaceProject:
    project: Project
    source: ProjectSource


class LearningWorkspaceRepository:
    """Keep every persisted workspace lookup rooted at an owned active project."""

    def get_owned_project(
        self, session: Session, owner_id: UUID, project_id: UUID, *, lock: bool = False
    ) -> OwnedWorkspaceProject | None:
        statement = (
            select(Project, ProjectSource)
            .join(ProjectSource, ProjectSource.project_id == Project.id)
            .where(
                Project.id == project_id,
                Project.owner_id == owner_id,
                Project.status == ProjectStatus.ACTIVE,
                Project.archived_at.is_(None),
            )
        )
        if lock:
            statement = statement.with_for_update()
        row = session.execute(statement).one_or_none()
        return None if row is None else OwnedWorkspaceProject(project=row[0], source=row[1])

    def get_progress(
        self, session: Session, project_id: UUID, *, lock: bool = False
    ) -> ProjectLearningProgress | None:
        statement = select(ProjectLearningProgress).where(
            ProjectLearningProgress.project_id == project_id
        )
        if lock:
            statement = statement.with_for_update()
        return session.scalar(statement)

    def get_snapshot(
        self, session: Session, project_id: UUID, snapshot_id: UUID | None
    ) -> ProjectInspectionSnapshot | None:
        if snapshot_id is None:
            return None
        return session.scalar(
            select(ProjectInspectionSnapshot).where(
                ProjectInspectionSnapshot.id == snapshot_id,
                ProjectInspectionSnapshot.project_id == project_id,
            )
        )

    def get_content(
        self, session: Session, project_id: UUID, content_id: UUID | None
    ) -> ProjectLearningContentVersion | None:
        if content_id is None:
            return None
        return session.scalar(
            select(ProjectLearningContentVersion).where(
                ProjectLearningContentVersion.id == content_id,
                ProjectLearningContentVersion.project_id == project_id,
            )
        )

    def get_attempt(
        self, session: Session, project_id: UUID, attempt_id: UUID | None
    ) -> ProjectLearningAttempt | None:
        if attempt_id is None:
            return None
        return session.scalar(
            select(ProjectLearningAttempt).where(
                ProjectLearningAttempt.id == attempt_id,
                ProjectLearningAttempt.project_id == project_id,
            )
        )

    def next_snapshot_version(self, session: Session, project_id: UUID) -> int:
        """Called only while the project row is locked by the caller."""

        maximum = session.scalar(
            select(func.coalesce(func.max(ProjectInspectionSnapshot.version), 0)).where(
                ProjectInspectionSnapshot.project_id == project_id
            )
        )
        return int(maximum) + 1

    def next_content_version(self, session: Session, project_id: UUID) -> int:
        """Called only while the project row is locked by the caller."""

        maximum = session.scalar(
            select(func.coalesce(func.max(ProjectLearningContentVersion.version), 0)).where(
                ProjectLearningContentVersion.project_id == project_id
            )
        )
        return int(maximum) + 1

    def find_content_idempotency(
        self,
        session: Session,
        project_id: UUID,
        idempotency_key: str,
    ) -> ProjectLearningContentVersion | None:
        return session.scalar(
            select(ProjectLearningContentVersion).where(
                ProjectLearningContentVersion.project_id == project_id,
                ProjectLearningContentVersion.activity_kind
                == LearningActivityKind.LESSON_GENERATION,
                ProjectLearningContentVersion.idempotency_key == idempotency_key,
            )
        )

    def find_attempt_idempotency(
        self,
        session: Session,
        project_id: UUID,
        content_version_id: UUID,
        activity_kind: LearningActivityKind,
        idempotency_key: str,
    ) -> ProjectLearningAttempt | None:
        return session.scalar(
            select(ProjectLearningAttempt).where(
                ProjectLearningAttempt.project_id == project_id,
                ProjectLearningAttempt.content_version_id == content_version_id,
                ProjectLearningAttempt.activity_kind == activity_kind,
                ProjectLearningAttempt.idempotency_key == idempotency_key,
            )
        )
