from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from ownyourcode.db.base import Base


class ProjectMode(StrEnum):
    EXISTING_REPOSITORY = "existing_repository"
    NEW_IDEA = "new_idea"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


PROJECT_MODE_TYPE = SQLAlchemyEnum(
    ProjectMode,
    name="project_mode",
    native_enum=True,
    values_callable=lambda enum_class: [item.value for item in enum_class],
)
PROJECT_STATUS_TYPE = SQLAlchemyEnum(
    ProjectStatus,
    name="project_status",
    native_enum=True,
    values_callable=lambda enum_class: [item.value for item in enum_class],
)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("id", "mode", name="uq_projects_id_mode"),
        Index("ix_projects_owner_id", "owner_id"),
        Index(
            "ix_projects_owner_archived_last_activity",
            "owner_id",
            "archived_at",
            "last_activity_at",
        ),
        CheckConstraint(
            "(status = 'active' AND archived_at IS NULL) OR "
            "(status = 'archived' AND archived_at IS NOT NULL)",
            name="ck_projects_status_archived_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    owner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", name="fk_projects_owner_id_users"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    mode: Mapped[ProjectMode] = mapped_column(PROJECT_MODE_TYPE, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        PROJECT_STATUS_TYPE,
        nullable=False,
        default=ProjectStatus.ACTIVE,
        server_default=text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectSource(Base):
    __tablename__ = "project_sources"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_sources_project_id"),
        ForeignKeyConstraint(
            ["project_id", "mode"],
            ["projects.id", "projects.mode"],
            name="fk_project_sources_project_id_mode_projects",
        ),
        CheckConstraint(
            "(mode = 'existing_repository' AND repository_url IS NOT NULL AND idea_brief IS NULL) "
            "OR (mode = 'new_idea' AND repository_url IS NULL AND idea_brief IS NOT NULL "
            "AND jsonb_typeof(idea_brief) = 'object')",
            name="ck_project_sources_mode_payload",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    mode: Mapped[ProjectMode] = mapped_column(PROJECT_MODE_TYPE, nullable=False)
    repository_url: Mapped[str | None] = mapped_column(String(2048))
    idea_brief: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
