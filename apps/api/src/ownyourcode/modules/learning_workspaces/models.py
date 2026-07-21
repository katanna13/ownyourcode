from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from ownyourcode.db.base import Base


class LearningOperationState(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class LearningActivityKind(StrEnum):
    LESSON_GENERATION = "lesson_generation"
    ASSESSMENT = "assessment"
    VERIFIED_LAB = "verified_lab"
    SECURITY_CHALLENGE = "security_challenge"
    ORAL_DEFENSE = "oral_defense"


LEARNING_OPERATION_STATE_TYPE = SQLAlchemyEnum(
    LearningOperationState,
    name="learning_operation_state",
    native_enum=True,
    values_callable=lambda enum_class: [item.value for item in enum_class],
)
LEARNING_ACTIVITY_KIND_TYPE = SQLAlchemyEnum(
    LearningActivityKind,
    name="learning_activity_kind",
    native_enum=True,
    values_callable=lambda enum_class: [item.value for item in enum_class],
)


class ProjectInspectionSnapshot(Base):
    __tablename__ = "project_inspection_snapshots"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_project_inspection_snapshots_project_version"),
        UniqueConstraint("id", "project_id", name="uq_project_inspection_snapshots_id_project"),
        ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_inspection_snapshots_project_id_projects",
        ),
        Index("ix_project_inspection_snapshots_project_created", "project_id", "created_at"),
        CheckConstraint("version > 0", name="ck_project_inspection_snapshots_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_repository_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(96), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class ProjectLearningContentVersion(Base):
    __tablename__ = "project_learning_content_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_project_learning_content_versions_project_version"),
        UniqueConstraint("id", "project_id", name="uq_project_learning_content_versions_id_project"),
        UniqueConstraint(
            "project_id", "activity_kind", "idempotency_key",
            name="uq_project_learning_content_versions_idempotency",
        ),
        ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_project_learning_content_versions_project_id_projects",
        ),
        ForeignKeyConstraint(
            ["inspection_snapshot_id", "project_id"],
            ["project_inspection_snapshots.id", "project_inspection_snapshots.project_id"],
            name="fk_project_learning_content_versions_snapshot_project",
        ),
        Index("ix_project_learning_content_versions_project_created", "project_id", "created_at"),
        CheckConstraint("version > 0", name="ck_project_learning_content_versions_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    inspection_snapshot_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_kind: Mapped[LearningActivityKind] = mapped_column(LEARNING_ACTIVITY_KIND_TYPE, nullable=False, default=LearningActivityKind.LESSON_GENERATION)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[LearningOperationState] = mapped_column(LEARNING_OPERATION_STATE_TYPE, nullable=False)
    contract_version: Mapped[str] = mapped_column(String(96), nullable=False)
    content_fingerprint: Mapped[str | None] = mapped_column(String(64))
    definition_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectLearningAttempt(Base):
    __tablename__ = "project_learning_attempts"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_project_learning_attempts_id_project"),
        UniqueConstraint(
            "project_id", "activity_kind", "content_version_id", "idempotency_key",
            name="uq_project_learning_attempts_idempotency",
        ),
        ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_project_learning_attempts_project_id_projects",
        ),
        ForeignKeyConstraint(
            ["content_version_id", "project_id"],
            ["project_learning_content_versions.id", "project_learning_content_versions.project_id"],
            name="fk_project_learning_attempts_content_project",
        ),
        Index("ix_project_learning_attempts_project_content_created", "project_id", "content_version_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    content_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    activity_kind: Mapped[LearningActivityKind] = mapped_column(LEARNING_ACTIVITY_KIND_TYPE, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[LearningOperationState] = mapped_column(LEARNING_OPERATION_STATE_TYPE, nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_payload: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True), nullable=False)
    result_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    passed: Mapped[bool | None] = mapped_column(Boolean)
    earned_points: Mapped[int | None] = mapped_column(Integer)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectLearningProgress(Base):
    __tablename__ = "project_learning_progress"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_learning_progress_project"),
        ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_project_learning_progress_project_id_projects",
        ),
        ForeignKeyConstraint(
            ["active_snapshot_id", "project_id"],
            ["project_inspection_snapshots.id", "project_inspection_snapshots.project_id"],
            name="fk_project_learning_progress_snapshot_project",
        ),
        ForeignKeyConstraint(
            ["active_content_version_id", "project_id"],
            ["project_learning_content_versions.id", "project_learning_content_versions.project_id"],
            name="fk_project_learning_progress_content_project",
        ),
        ForeignKeyConstraint(
            ["assessment_attempt_id", "project_id"],
            ["project_learning_attempts.id", "project_learning_attempts.project_id"],
            name="fk_project_learning_progress_assessment_attempt_project",
        ),
        ForeignKeyConstraint(
            ["verified_lab_attempt_id", "project_id"],
            ["project_learning_attempts.id", "project_learning_attempts.project_id"],
            name="fk_project_learning_progress_lab_attempt_project",
        ),
        ForeignKeyConstraint(
            ["security_challenge_attempt_id", "project_id"],
            ["project_learning_attempts.id", "project_learning_attempts.project_id"],
            name="fk_project_learning_progress_security_attempt_project",
        ),
        ForeignKeyConstraint(
            ["oral_defense_attempt_id", "project_id"],
            ["project_learning_attempts.id", "project_learning_attempts.project_id"],
            name="fk_project_learning_progress_oral_attempt_project",
        ),
        CheckConstraint(
            "last_viewed_stage IN ('inspect', 'learn', 'assess', 'lab', 'secure', 'defend', 'score')",
            name="ck_project_learning_progress_last_viewed_stage",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    active_snapshot_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    active_content_version_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    last_viewed_stage: Mapped[str] = mapped_column(String(16), nullable=False, default="inspect", server_default=text("'inspect'"))
    assessment_attempt_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    verified_lab_attempt_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    security_challenge_attempt_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    oral_defense_attempt_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
