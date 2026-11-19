"""Record session start times for history."""

import sqlalchemy as sa
from alembic import op

revision = "0005_session_start"
down_revision = "0004_pause_sessions"


def upgrade():
    op.add_column("practice_sessions", sa.Column("started_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("practice_sessions", "started_at")
