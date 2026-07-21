from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ownyourcode.modules.projects.models import Project, ProjectSource, ProjectStatus


class InvalidProjectCursorError(ValueError):
    pass


@dataclass(frozen=True)
class OwnedProject:
    project: Project
    source: ProjectSource


@dataclass(frozen=True)
class ProjectListPage:
    items: list[OwnedProject]
    next_cursor: str | None


@dataclass(frozen=True)
class ProjectCursor:
    last_activity_at: datetime
    project_id: UUID


class ProjectRepository:
    """Ownership-scoped persistence operations for the Phase 11A project shape."""

    def add_project(self, session: Session, project: Project) -> None:
        session.add(project)

    def add_source(self, session: Session, source: ProjectSource) -> None:
        session.add(source)

    def get_owned_active(
        self, session: Session, owner_id: UUID, project_id: UUID
    ) -> OwnedProject | None:
        row = session.execute(
            select(Project, ProjectSource)
            .join(ProjectSource, ProjectSource.project_id == Project.id)
            .where(
                Project.id == project_id,
                Project.owner_id == owner_id,
                Project.status == ProjectStatus.ACTIVE,
                Project.archived_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            return None
        return OwnedProject(project=row[0], source=row[1])

    def list_owned_active(
        self, session: Session, owner_id: UUID, limit: int, cursor: str | None
    ) -> ProjectListPage:
        decoded_cursor = decode_project_cursor(cursor) if cursor else None
        statement = (
            select(Project, ProjectSource)
            .join(ProjectSource, ProjectSource.project_id == Project.id)
            .where(
                Project.owner_id == owner_id,
                Project.status == ProjectStatus.ACTIVE,
                Project.archived_at.is_(None),
            )
            .order_by(Project.last_activity_at.desc(), Project.id.desc())
            .limit(limit + 1)
        )
        if decoded_cursor is not None:
            statement = statement.where(
                or_(
                    Project.last_activity_at < decoded_cursor.last_activity_at,
                    and_(
                        Project.last_activity_at == decoded_cursor.last_activity_at,
                        Project.id < decoded_cursor.project_id,
                    ),
                )
            )

        rows = session.execute(statement).all()
        has_next_page = len(rows) > limit
        page_rows = rows[:limit]
        items = [OwnedProject(project=row[0], source=row[1]) for row in page_rows]
        next_cursor = (
            encode_project_cursor(items[-1].project) if has_next_page and items else None
        )
        return ProjectListPage(items=items, next_cursor=next_cursor)


def encode_project_cursor(project: Project) -> str:
    payload = {
        "last_activity_at": project.last_activity_at.isoformat(),
        "project_id": str(project.id),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii")
    return encoded.rstrip("=")


def decode_project_cursor(value: str) -> ProjectCursor:
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
        if set(payload) != {"last_activity_at", "project_id"}:
            raise ValueError
        timestamp = datetime.fromisoformat(payload["last_activity_at"])
        project_id = UUID(payload["project_id"])
        if timestamp.tzinfo is None:
            raise ValueError
        return ProjectCursor(last_activity_at=timestamp, project_id=project_id)
    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        raise InvalidProjectCursorError("Invalid project cursor") from None
