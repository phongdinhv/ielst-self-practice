from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import Base


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (Index("ix_practice_history", "learner_id", "submitted_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"))
    module: Mapped[str] = mapped_column(String(16))
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("practice_sessions.id"))
    content: Mapped[dict] = mapped_column(JSON)
    draft: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
