"""Create learner, goal, and job tables and seed the local learner."""

import sqlalchemy as sa
from alembic import op
from uuid import UUID

revision = "0001_foundation"
down_revision = None


def upgrade():
    learners = op.create_table(
        "learners",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
    )
    goals = op.create_table(
        "study_goals",
        sa.Column("learner_id", sa.Uuid(), sa.ForeignKey("learners.id"), primary_key=True),
        sa.Column("module", sa.String(16), primary_key=True),
        sa.Column("minimum_band", sa.Float(), nullable=False),
        sa.Column("maximum_band", sa.Float(), nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("learner_id", sa.Uuid(), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("deduplication_key", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("result", sa.JSON()),
        sa.Column("error", sa.String(160)),
        sa.UniqueConstraint("learner_id", "kind", "deduplication_key"),
    )
    op.create_index("ix_jobs_claim", "jobs", ["state", "available_at"])
    learner = UUID("00000000-0000-4000-8000-000000000001")
    op.bulk_insert(learners, [{"id": learner, "name": "Local learner"}])
    op.bulk_insert(goals, [
        {"learner_id": learner, "module": module, "minimum_band": lower, "maximum_band": upper}
        for module, lower, upper in [("listening", 9.0, 9.0), ("reading", 9.0, 9.0), ("writing", 7.5, 8.0)]
    ])


def downgrade():
    op.drop_table("jobs")
    op.drop_table("study_goals")
    op.drop_table("learners")
