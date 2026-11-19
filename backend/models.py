from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class StudyGoal(Base):
    __tablename__ = "study_goals"

    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), primary_key=True)
    module: Mapped[str] = mapped_column(String(16), primary_key=True)
    minimum_band: Mapped[float]
    maximum_band: Mapped[float]


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("learner_id", "kind", "deduplication_key"),
        Index("ix_jobs_claim", "state", "available_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"))
    kind: Mapped[str] = mapped_column(String(40))
    deduplication_key: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None]
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(160))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
