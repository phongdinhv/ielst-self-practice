"""Retain session links after a finished session is removed."""

import sqlalchemy as sa
from alembic import op

revision = "0006_deleted_sessions"
down_revision = "0005_session_start"


def upgrade():
    op.add_column("practice_sessions", sa.Column("deleted_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("practice_sessions", "deleted_at")
