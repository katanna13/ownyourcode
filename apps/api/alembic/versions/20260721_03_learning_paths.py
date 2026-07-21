"""Add immutable multi-module learning paths.

Revision ID: 20260721_03
Revises: 20260716_02
Create Date: 2026-07-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260721_03"
down_revision: Union[str, Sequence[str], None] = "20260716_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


path_generation_state = postgresql.ENUM(
    "pending", "completed", "failed", name="learning_path_generation_state"
)
module_progress_state = postgresql.ENUM(
    "locked", "available", "in_progress", "remediation_required", "demonstrated",
    name="module_progress_state",
)
module_adaptation_kind = postgresql.ENUM(
    "remediation", "optional_stretch", name="module_adaptation_kind"
)
module_adaptation_state = postgresql.ENUM(
    "available", "completed", name="module_adaptation_state"
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        path_generation_state,
        module_progress_state,
        module_adaptation_kind,
        module_adaptation_state,
    ):
        enum_type.create(bind, checkfirst=True)

    path_generation_state_column = postgresql.ENUM(
        "pending", "completed", "failed", name="learning_path_generation_state", create_type=False
    )
    module_progress_state_column = postgresql.ENUM(
        "locked", "available", "in_progress", "remediation_required", "demonstrated",
        name="module_progress_state", create_type=False,
    )
    module_adaptation_kind_column = postgresql.ENUM(
        "remediation", "optional_stretch", name="module_adaptation_kind", create_type=False
    )
    module_adaptation_state_column = postgresql.ENUM(
        "available", "completed", name="module_adaptation_state", create_type=False
    )

    op.create_table(
        "project_learning_path_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inspection_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("generation_state", path_generation_state_column, nullable=False),
        sa.Column("contract_version", sa.String(length=96), nullable=False),
        sa.Column("planner_version", sa.String(length=96), nullable=False),
        sa.Column("source_evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("learner_level", sa.String(length=16), nullable=False),
        sa.Column("learning_goal", sa.String(length=240), nullable=True),
        sa.Column("definition_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("path_limitations", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_project_learning_path_versions_version_positive"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_project_learning_path_versions_project"),
        sa.ForeignKeyConstraint(["inspection_snapshot_id", "project_id"], ["project_inspection_snapshots.id", "project_inspection_snapshots.project_id"], name="fk_project_learning_path_versions_snapshot_project"),
        sa.PrimaryKeyConstraint("id", name="pk_project_learning_path_versions"),
        sa.UniqueConstraint("id", "project_id", name="uq_project_learning_path_versions_id_project"),
        sa.UniqueConstraint("project_id", "version", name="uq_project_learning_path_versions_project_version"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_project_learning_path_versions_idempotency"),
    )
    op.create_index("ix_project_learning_path_versions_project_created", "project_learning_path_versions", ["project_id", "created_at"])

    op.create_table(
        "project_learning_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("module_key", sa.String(length=96), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("contract_version", sa.String(length=96), nullable=False),
        sa.Column("definition_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("definition_payload", postgresql.JSONB(none_as_null=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("position > 0", name="ck_project_learning_modules_position_positive"),
        sa.ForeignKeyConstraint(["path_version_id", "project_id"], ["project_learning_path_versions.id", "project_learning_path_versions.project_id"], name="fk_project_learning_modules_path_project"),
        sa.PrimaryKeyConstraint("id", name="pk_project_learning_modules"),
        sa.UniqueConstraint("id", "project_id", name="uq_project_learning_modules_id_project"),
        sa.UniqueConstraint("id", "path_version_id", "project_id", name="uq_project_learning_modules_path_project"),
        sa.UniqueConstraint("path_version_id", "position", name="uq_project_learning_modules_path_position"),
        sa.UniqueConstraint("path_version_id", "module_key", name="uq_project_learning_modules_path_key"),
    )
    op.create_index("ix_project_learning_modules_project_path", "project_learning_modules", ["project_id", "path_version_id", "position"])

    op.create_table(
        "project_module_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", module_progress_state_column, nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["module_id", "path_version_id", "project_id"], ["project_learning_modules.id", "project_learning_modules.path_version_id", "project_learning_modules.project_id"], name="fk_project_module_progress_module_path_project"),
        sa.PrimaryKeyConstraint("id", name="pk_project_module_progress"),
        sa.UniqueConstraint("module_id", name="uq_project_module_progress_module"),
    )
    op.create_index("ix_project_module_progress_project_path", "project_module_progress", ["project_id", "path_version_id", "state"])

    op.create_table(
        "project_module_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_id", sa.String(length=96), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("state", path_generation_state_column, nullable=False),
        sa.Column("context_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("submitted_payload", postgresql.JSONB(none_as_null=True), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("earned_points", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["module_id", "path_version_id", "project_id"], ["project_learning_modules.id", "project_learning_modules.path_version_id", "project_learning_modules.project_id"], name="fk_project_module_attempts_module_path_project"),
        sa.PrimaryKeyConstraint("id", name="pk_project_module_attempts"),
        sa.UniqueConstraint("id", "project_id", name="uq_project_module_attempts_id_project"),
        sa.UniqueConstraint("module_id", "activity_id", "idempotency_key", name="uq_project_module_attempts_idempotency"),
    )
    op.create_index("ix_project_module_attempts_project_module_created", "project_module_attempts", ["project_id", "module_id", "created_at"])

    op.create_table(
        "project_module_adaptations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", module_adaptation_kind_column, nullable=False),
        sa.Column("rule_id", sa.String(length=96), nullable=False),
        sa.Column("rule_version", sa.String(length=96), nullable=False),
        sa.Column("learner_reason", sa.String(length=360), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("activity_id", sa.String(length=96), nullable=False),
        sa.Column("context_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("definition_payload", postgresql.JSONB(none_as_null=True), nullable=False),
        sa.Column("state", module_adaptation_state_column, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["module_id", "path_version_id", "project_id"], ["project_learning_modules.id", "project_learning_modules.path_version_id", "project_learning_modules.project_id"], name="fk_project_module_adaptations_module_path_project"),
        sa.ForeignKeyConstraint(["trigger_attempt_id", "project_id"], ["project_module_attempts.id", "project_module_attempts.project_id"], name="fk_project_module_adaptations_trigger_attempt_project"),
        sa.PrimaryKeyConstraint("id", name="pk_project_module_adaptations"),
        sa.UniqueConstraint("trigger_attempt_id", "rule_id", "rule_version", name="uq_project_module_adaptations_trigger_rule"),
    )
    op.create_index("ix_project_module_adaptations_project_module", "project_module_adaptations", ["project_id", "module_id", "state"])


def downgrade() -> None:
    op.drop_table("project_module_adaptations")
    op.drop_index("ix_project_module_attempts_project_module_created", table_name="project_module_attempts")
    op.drop_table("project_module_attempts")
    op.drop_index("ix_project_module_progress_project_path", table_name="project_module_progress")
    op.drop_table("project_module_progress")
    op.drop_index("ix_project_learning_modules_project_path", table_name="project_learning_modules")
    op.drop_table("project_learning_modules")
    op.drop_index("ix_project_learning_path_versions_project_created", table_name="project_learning_path_versions")
    op.drop_table("project_learning_path_versions")

    bind = op.get_bind()
    for enum_type in (
        module_adaptation_state,
        module_adaptation_kind,
        module_progress_state,
        path_generation_state,
    ):
        enum_type.drop(bind, checkfirst=True)
