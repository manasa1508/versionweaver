"""Add read-path indexes for the operations console.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_projects_created", "projects", ["created_at", "id"])
    op.create_index("ix_changes_created", "change_requests", ["created_at", "id"])
    op.create_index(
        "ix_changes_project_created", "change_requests", ["project_id", "created_at", "id"]
    )
    op.create_index("ix_jobs_created", "jobs", ["created_at", "id"])
    op.create_index("ix_audit_created", "audit_events", ["created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_audit_created", table_name="audit_events")
    op.drop_index("ix_jobs_created", table_name="jobs")
    op.drop_index("ix_changes_project_created", table_name="change_requests")
    op.drop_index("ix_changes_created", table_name="change_requests")
    op.drop_index("ix_projects_created", table_name="projects")
