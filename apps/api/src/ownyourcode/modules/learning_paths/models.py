"""Database records for versioned, owner-scoped learning paths."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
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


class LearningPathGenerationState(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ModuleProgressState(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    REMEDIATION_REQUIRED = "remediation_required"
    DEMONSTRATED = "demonstrated"


class ModuleAdaptationKind(StrEnum):
    REMEDIATION = "remediation"
    OPTIONAL_STRETCH = "optional_stretch"


class ModuleAdaptationState(StrEnum):
    AVAILABLE = "available"
    COMPLETED = "completed"


LEARNING_PATH_GENERATION_STATE_TYPE = SQLAlchemyEnum(
    LearningPathGenerationState,
    name="learning_path_generation_state",
    native_enum=True,
    values_callable=lambda enum_class: [item.value for item in enum_class],
)
MODULE_PROGRESS_STATE_TYPE = SQLAlchemyEnum(
    ModuleProgressState,
    name="module_progress_state",
    native_enum=True,
    values_callable=lambda enum_class: [item.value for item in enum_class],
)
MODULE_ADAPTATION_KIND_TYPE = SQLAlchemyEnum(
    ModuleAdaptationKind,
    name="module_adaptation_kind",
    native_enum=True,
    values_callable=lambda enum_class: [item.value for item in enum_class],
)
MODULE_ADAPTATION_STATE_TYPE = SQLAlchemyEnum(
    ModuleAdaptationState,
    name="module_adaptation_state",
    native_enum=True,
    values_callable=lambda enum_class: [item.value for item in enum_class],
)


class ProjectLearningPathVersion(Base):
    """One immutable path definition generated from one saved inspection."""

    __tablename__ = "project_learning_path_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_project_learning_path_versions_project_version"),
        UniqueConstraint("id", "project_id", name="uq_project_learning_path_versions_id_project"),
        UniqueConstraint(
            "project_id", "idempotency_key", name="uq_project_learning_path_versions_idempotency"
        ),
        ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_project_learning_path_versions_project"
        ),
        ForeignKeyConstraint(
            ["inspection_snapshot_id", "project_id"],
            ["project_inspection_snapshots.id", "project_inspection_snapshots.project_id"],
            name="fk_project_learning_path_versions_snapshot_project",
        ),
        CheckConstraint("version > 0", name="ck_project_learning_path_versions_version_positive"),
        Index("ix_project_learning_path_versions_project_created", "project_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    inspection_snapshot_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_state: Mapped[LearningPathGenerationState] = mapped_column(
        LEARNING_PATH_GENERATION_STATE_TYPE, nullable=False
    )
    contract_version: Mapped[str] = mapped_column(String(96), nullable=False)
    planner_version: Mapped[str] = mapped_column(String(96), nullable=False)
    source_evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    learner_level: Mapped[str] = mapped_column(String(16), nullable=False)
    learning_goal: Mapped[str | None] = mapped_column(String(240))
    definition_fingerprint: Mapped[str | None] = mapped_column(String(64))
    path_limitations: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectLearningModule(Base):
    """Frozen learner-facing and server-private definition for one path module."""

    __tablename__ = "project_learning_modules"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_project_learning_modules_id_project"),
        UniqueConstraint("id", "path_version_id", "project_id", name="uq_project_learning_modules_path_project"),
        UniqueConstraint("path_version_id", "position", name="uq_project_learning_modules_path_position"),
        UniqueConstraint("path_version_id", "module_key", name="uq_project_learning_modules_path_key"),
        ForeignKeyConstraint(
            ["path_version_id", "project_id"],
            ["project_learning_path_versions.id", "project_learning_path_versions.project_id"],
            name="fk_project_learning_modules_path_project",
        ),
        CheckConstraint("position > 0", name="ck_project_learning_modules_position_positive"),
        Index("ix_project_learning_modules_project_path", "project_id", "path_version_id", "position"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    path_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    module_key: Mapped[str] = mapped_column(String(96), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(96), nullable=False)
    definition_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    definition_payload: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class ProjectModuleProgress(Base):
    """A server-maintained projection; the browser never writes these states."""

    __tablename__ = "project_module_progress"
    __table_args__ = (
        UniqueConstraint("module_id", name="uq_project_module_progress_module"),
        ForeignKeyConstraint(
            ["module_id", "path_version_id", "project_id"],
            [
                "project_learning_modules.id",
                "project_learning_modules.path_version_id",
                "project_learning_modules.project_id",
            ],
            name="fk_project_module_progress_module_path_project",
        ),
        Index("ix_project_module_progress_project_path", "project_id", "path_version_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    path_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    module_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    state: Mapped[ModuleProgressState] = mapped_column(MODULE_PROGRESS_STATE_TYPE, nullable=False)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class ProjectModuleAttempt(Base):
    """One idempotent submission against a frozen activity definition."""

    __tablename__ = "project_module_attempts"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_project_module_attempts_id_project"),
        UniqueConstraint(
            "module_id", "activity_id", "idempotency_key",
            name="uq_project_module_attempts_idempotency",
        ),
        ForeignKeyConstraint(
            ["module_id", "path_version_id", "project_id"],
            [
                "project_learning_modules.id",
                "project_learning_modules.path_version_id",
                "project_learning_modules.project_id",
            ],
            name="fk_project_module_attempts_module_path_project",
        ),
        Index("ix_project_module_attempts_project_module_created", "project_id", "module_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    path_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    module_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    activity_id: Mapped[str] = mapped_column(String(96), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[LearningPathGenerationState] = mapped_column(LEARNING_PATH_GENERATION_STATE_TYPE, nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_payload: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True), nullable=False)
    result_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    passed: Mapped[bool | None] = mapped_column(Boolean)
    earned_points: Mapped[int | None] = mapped_column(Integer)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectModuleAdaptation(Base):
    """An explainable remediation or bounded optional extension."""

    __tablename__ = "project_module_adaptations"
    __table_args__ = (
        UniqueConstraint("trigger_attempt_id", "rule_id", "rule_version", name="uq_project_module_adaptations_trigger_rule"),
        ForeignKeyConstraint(
            ["module_id", "path_version_id", "project_id"],
            [
                "project_learning_modules.id",
                "project_learning_modules.path_version_id",
                "project_learning_modules.project_id",
            ],
            name="fk_project_module_adaptations_module_path_project",
        ),
        ForeignKeyConstraint(
            ["trigger_attempt_id", "project_id"],
            ["project_module_attempts.id", "project_module_attempts.project_id"],
            name="fk_project_module_adaptations_trigger_attempt_project",
        ),
        Index("ix_project_module_adaptations_project_module", "project_id", "module_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    path_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    module_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    trigger_attempt_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    kind: Mapped[ModuleAdaptationKind] = mapped_column(MODULE_ADAPTATION_KIND_TYPE, nullable=False)
    rule_id: Mapped[str] = mapped_column(String(96), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(96), nullable=False)
    learner_reason: Mapped[str] = mapped_column(String(360), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    activity_id: Mapped[str] = mapped_column(String(96), nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    definition_payload: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True), nullable=False)
    state: Mapped[ModuleAdaptationState] = mapped_column(MODULE_ADAPTATION_STATE_TYPE, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
