"""Persist authenticated Existing Repository learning workspaces.

Revision ID: 20260716_02
Revises: 20260716_01
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260716_02"
down_revision: Union[str, Sequence[str], None] = "20260716_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


operation_state = postgresql.ENUM(
    "pending", "completed", "failed", name="learning_operation_state"
)
activity_kind = postgresql.ENUM(
    "lesson_generation",
    "assessment",
    "verified_lab",
    "security_challenge",
    "oral_defense",
    name="learning_activity_kind",
)
operation_state_column = postgresql.ENUM(
    "pending", "completed", "failed", name="learning_operation_state", create_type=False
)
activity_kind_column = postgresql.ENUM(
    "lesson_generation",
    "assessment",
    "verified_lab",
    "security_challenge",
    "oral_defense",
    name="learning_activity_kind",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    operation_state.create(bind, checkfirst=True)
    activity_kind.create(bind, checkfirst=True)

    op.create_table(
        "project_inspection_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("canonical_repository_url", sa.String(length=2048), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("contract_version", sa.String(length=96), nullable=False),
        sa.Column("payload", postgresql.JSONB(none_as_null=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_project_inspection_snapshots_version_positive"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_project_inspection_snapshots_project_id_projects"),
        sa.PrimaryKeyConstraint("id", name="pk_project_inspection_snapshots"),
        sa.UniqueConstraint("id", "project_id", name="uq_project_inspection_snapshots_id_project"),
        sa.UniqueConstraint("project_id", "version", name="uq_project_inspection_snapshots_project_version"),
    )
    op.create_index("ix_project_inspection_snapshots_project_created", "project_inspection_snapshots", ["project_id", "created_at"])

    op.create_table(
        "project_learning_content_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inspection_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("activity_kind", activity_kind_column, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("state", operation_state_column, nullable=False),
        sa.Column("contract_version", sa.String(length=96), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("definition_payload", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_project_learning_content_versions_version_positive"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_project_learning_content_versions_project_id_projects"),
        sa.ForeignKeyConstraint(["inspection_snapshot_id", "project_id"], ["project_inspection_snapshots.id", "project_inspection_snapshots.project_id"], name="fk_project_learning_content_versions_snapshot_project"),
        sa.PrimaryKeyConstraint("id", name="pk_project_learning_content_versions"),
        sa.UniqueConstraint("id", "project_id", name="uq_project_learning_content_versions_id_project"),
        sa.UniqueConstraint("project_id", "activity_kind", "idempotency_key", name="uq_project_learning_content_versions_idempotency"),
        sa.UniqueConstraint("project_id", "version", name="uq_project_learning_content_versions_project_version"),
    )
    op.create_index("ix_project_learning_content_versions_project_created", "project_learning_content_versions", ["project_id", "created_at"])

    op.create_table(
        "project_learning_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_kind", activity_kind_column, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("state", operation_state_column, nullable=False),
        sa.Column("context_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("submitted_payload", postgresql.JSONB(none_as_null=True), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("earned_points", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_project_learning_attempts_project_id_projects"),
        sa.ForeignKeyConstraint(["content_version_id", "project_id"], ["project_learning_content_versions.id", "project_learning_content_versions.project_id"], name="fk_project_learning_attempts_content_project"),
        sa.PrimaryKeyConstraint("id", name="pk_project_learning_attempts"),
        sa.UniqueConstraint("id", "project_id", name="uq_project_learning_attempts_id_project"),
        sa.UniqueConstraint("project_id", "activity_kind", "content_version_id", "idempotency_key", name="uq_project_learning_attempts_idempotency"),
    )
    op.create_index("ix_project_learning_attempts_project_content_created", "project_learning_attempts", ["project_id", "content_version_id", "created_at"])

    op.create_table(
        "project_learning_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active_content_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_viewed_stage", sa.String(length=16), server_default=sa.text("'inspect'"), nullable=False),
        sa.Column("assessment_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_lab_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("security_challenge_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("oral_defense_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("last_viewed_stage IN ('inspect', 'learn', 'assess', 'lab', 'secure', 'defend', 'score')", name="ck_project_learning_progress_last_viewed_stage"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_project_learning_progress_project_id_projects"),
        sa.ForeignKeyConstraint(["active_snapshot_id", "project_id"], ["project_inspection_snapshots.id", "project_inspection_snapshots.project_id"], name="fk_project_learning_progress_snapshot_project"),
        sa.ForeignKeyConstraint(["active_content_version_id", "project_id"], ["project_learning_content_versions.id", "project_learning_content_versions.project_id"], name="fk_project_learning_progress_content_project"),
        sa.ForeignKeyConstraint(["assessment_attempt_id", "project_id"], ["project_learning_attempts.id", "project_learning_attempts.project_id"], name="fk_project_learning_progress_assessment_attempt_project"),
        sa.ForeignKeyConstraint(["verified_lab_attempt_id", "project_id"], ["project_learning_attempts.id", "project_learning_attempts.project_id"], name="fk_project_learning_progress_lab_attempt_project"),
        sa.ForeignKeyConstraint(["security_challenge_attempt_id", "project_id"], ["project_learning_attempts.id", "project_learning_attempts.project_id"], name="fk_project_learning_progress_security_attempt_project"),
        sa.ForeignKeyConstraint(["oral_defense_attempt_id", "project_id"], ["project_learning_attempts.id", "project_learning_attempts.project_id"], name="fk_project_learning_progress_oral_attempt_project"),
        sa.PrimaryKeyConstraint("id", name="pk_project_learning_progress"),
        sa.UniqueConstraint("project_id", name="uq_project_learning_progress_project"),
    )


def downgrade() -> None:
    op.drop_table("project_learning_progress")
    op.drop_index("ix_project_learning_attempts_project_content_created", table_name="project_learning_attempts")
    op.drop_table("project_learning_attempts")
    op.drop_index("ix_project_learning_content_versions_project_created", table_name="project_learning_content_versions")
    op.drop_table("project_learning_content_versions")
    op.drop_index("ix_project_inspection_snapshots_project_created", table_name="project_inspection_snapshots")
    op.drop_table("project_inspection_snapshots")

    bind = op.get_bind()
    activity_kind.drop(bind, checkfirst=True)
    operation_state.drop(bind, checkfirst=True)
