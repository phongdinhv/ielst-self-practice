"""Keep source provenance for Reading mocks removed from the library."""

import sqlalchemy as sa
from alembic import op

revision = "0007_archived_reading_mocks"
down_revision = "0006_deleted_sessions"


def upgrade():
    op.add_column("jobs", sa.Column("archived_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("jobs", "archived_at")
