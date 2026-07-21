"""Create the Phase 11A ownership and project foundation.

Revision ID: 20260716_01
Revises: 
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260716_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


project_mode = postgresql.ENUM(
    "existing_repository", "new_idea", name="project_mode"
)
project_status = postgresql.ENUM("active", "archived", name="project_status")
project_mode_column_type = postgresql.ENUM(
    "existing_repository", "new_idea", name="project_mode", create_type=False
)
project_status_column_type = postgresql.ENUM(
    "active", "archived", name="project_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    project_mode.create(bind, checkfirst=True)
    project_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("auth_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("auth_subject", name="uq_users_auth_subject"),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("mode", project_mode_column_type, nullable=False),
        sa.Column(
            "status",
            project_status_column_type,
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'active' AND archived_at IS NULL) OR "
            "(status = 'archived' AND archived_at IS NOT NULL)",
            name="ck_projects_status_archived_at",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name="fk_projects_owner_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("id", "mode", name="uq_projects_id_mode"),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index(
        "ix_projects_owner_archived_last_activity",
        "projects",
        ["owner_id", "archived_at", "last_activity_at"],
    )

    op.create_table(
        "project_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", project_mode_column_type, nullable=False),
        sa.Column("repository_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "idea_brief",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(mode = 'existing_repository' AND repository_url IS NOT NULL AND idea_brief IS NULL) "
            "OR (mode = 'new_idea' AND repository_url IS NULL AND idea_brief IS NOT NULL "
            "AND jsonb_typeof(idea_brief) = 'object')",
            name="ck_project_sources_mode_payload",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "mode"],
            ["projects.id", "projects.mode"],
            name="fk_project_sources_project_id_mode_projects",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_sources"),
        sa.UniqueConstraint("project_id", name="uq_project_sources_project_id"),
    )


def downgrade() -> None:
    op.drop_table("project_sources")
    op.drop_index("ix_projects_owner_archived_last_activity", table_name="projects")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("users")

    bind = op.get_bind()
    project_status.drop(bind, checkfirst=True)
    project_mode.drop(bind, checkfirst=True)
