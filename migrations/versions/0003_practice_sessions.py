"""Store timed practice sessions and their results."""

import sqlalchemy as sa
from alembic import op

revision = "0003_practice_sessions"
down_revision = "0002_writing_goal"


def upgrade():
    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("learner_id", sa.Uuid(), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("module", sa.String(16), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("practice_sessions.id")),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_practice_history", "practice_sessions", ["learner_id", "submitted_at"])


def downgrade():
    op.drop_table("practice_sessions")
