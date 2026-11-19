from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from backend.db import Session
from backend.identity import LearnerId
from backend.models import Job, Learner, StudyGoal
from backend.practice import find as find_practice_session, router as practice_router
from backend.progress import dashboard_estimates
from backend.reading_topics import TOPICS
from backend.reading_sources import PUBLISHERS
from backend.writing_prompts import uses_process_visual

app = FastAPI(title="IELTS Academic Practice")
app.include_router(practice_router)
Module = Literal["listening", "reading", "writing"]


class BandTarget(BaseModel):
    minimum_band: float = Field(ge=0, le=9, multiple_of=0.5)
    maximum_band: float = Field(ge=0, le=9, multiple_of=0.5)

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum_band > self.maximum_band:
            raise ValueError("Minimum band must be at or below maximum band")
        return self


def goal_data(goal: StudyGoal):
    return {"module": goal.module, "minimum_band": goal.minimum_band, "maximum_band": goal.maximum_band}


@app.get("/api/v1/health")
def health():
    try:
        with Session() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "ok"}


@app.get("/api/v1/dashboard")
def dashboard(learner_id: LearnerId):
    with Session() as session:
        learner = session.get(Learner, learner_id)
        if learner is None:
            raise HTTPException(503, "Local learner has not been seeded")
        goals = session.scalars(
            select(StudyGoal).where(StudyGoal.learner_id == learner_id).order_by(StudyGoal.module)
        )
        return {
            "learner": {"id": learner.id, "name": learner.name},
            "goals": [goal_data(goal) for goal in goals],
            "estimates": dashboard_estimates(session, learner_id),
        }


@app.get("/api/v1/goals")
def list_goals(learner_id: LearnerId):
    return {"items": dashboard(learner_id)["goals"], "next_cursor": None}


@app.put("/api/v1/goals/{module}")
def replace_goal(module: Module, target: BandTarget, learner_id: LearnerId):
    with Session.begin() as session:
        goal = session.get(StudyGoal, (learner_id, module))
        if goal is None:
            raise HTTPException(404, "Study goal not found")
        goal.minimum_band = target.minimum_band
        goal.maximum_band = target.maximum_band
        return goal_data(goal)


@app.post("/api/v1/jobs/worker-check", status_code=202)
def enqueue_worker_check(
    learner_id: LearnerId,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
):
    with Session.begin() as session:
        if session.get(Learner, learner_id, with_for_update=True) is None:
            raise HTTPException(503, "Local learner has not been seeded")
        job = session.scalar(select(Job).filter_by(
            learner_id=learner_id, kind="worker_check", deduplication_key=idempotency_key,
        ))
        if job is None:
            job = Job(
                learner_id=learner_id, kind="worker_check", deduplication_key=idempotency_key,
                payload={}, available_at=datetime.now(UTC),
            )
            session.add(job)
            session.flush()
        return {"job_id": job.id}


@app.get("/api/v1/jobs/{job_id}")
def job_status(job_id: UUID, learner_id: LearnerId):
    with Session() as session:
        job = session.scalar(select(Job).filter_by(id=job_id, learner_id=learner_id, archived_at=None))
        if job is None:
            raise HTTPException(404, "Job not found")
        if job.kind == "writing_feedback":
            find_practice_session(session, UUID(job.payload["attempt_id"]), learner_id)
        result = None if job.kind in ("reading_mock", "writing_prompt") else job.result
        replacement_required = job.kind == "writing_prompt" and job.state == "succeeded" and uses_process_visual(job.result)
        progress = ((job.result or {}).get("progress")
                    if job.kind == "reading_mock" and job.state == "running" else None)
        topic = TOPICS.get(job.payload.get("topic")) if job.kind == "reading_mock" else None
        source_name = None
        if job.kind == "reading_mock":
            requested = job.payload.get("source", "wikipedia")
            source_name = (job.result or {}).get("source_name") or (
                PUBLISHERS[requested][0] if requested in PUBLISHERS else
                "Random source" if requested == "random" else "Wikipedia"
            )
        error = job.error
        retry_at = None
        if error and " Retry after " in error:
            error = error.split(" Retry after ", 1)[0]
            retry_at = job.available_at
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
        return {"id": job.id, "state": job.state, "result": result, "error": error, "retry_at": retry_at,
                "topic": topic[0] if topic else None, "source_name": source_name, "progress": progress,
                "replacement_required": replacement_required}
