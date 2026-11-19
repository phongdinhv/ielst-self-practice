"""Raise the default local Writing goal ceiling to band 9."""

from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision = "0002_writing_goal"
down_revision = "0001_foundation"


def update_ceiling(previous, new):
    goals = sa.table(
        "study_goals",
        sa.column("learner_id", sa.Uuid()),
        sa.column("module", sa.String()),
        sa.column("minimum_band", sa.Float()),
        sa.column("maximum_band", sa.Float()),
    )
    learner = op.inline_literal(UUID("00000000-0000-4000-8000-000000000001"), sa.Uuid())
    op.execute(goals.update().where(
        goals.c.learner_id == learner,
        goals.c.module == op.inline_literal("writing"),
        goals.c.minimum_band == op.inline_literal(7.5),
        goals.c.maximum_band == op.inline_literal(previous),
    ).values(maximum_band=op.inline_literal(new)))


def upgrade():
    update_ceiling(8.0, 9.0)


def downgrade():
    update_ceiling(9.0, 8.0)
