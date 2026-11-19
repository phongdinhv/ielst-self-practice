"""Persist when an in-progress practice session was paused."""

import sqlalchemy as sa
from alembic import op

revision = "0004_pause_sessions"
down_revision = "0003_practice_sessions"


def upgrade():
    op.add_column("practice_sessions", sa.Column("paused_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("practice_sessions", "paused_at")
