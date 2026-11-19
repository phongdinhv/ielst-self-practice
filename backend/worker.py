import logging
from datetime import UTC, datetime, timedelta
from time import sleep
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError

from backend.db import Session
from backend.models import Job
from backend.practice_ai import (
    DraftValidationError, ModelBusy, ModelOutputLimit, ModelQuotaExhausted, ReadingGenerationTimeout,
    ReadingSourcesExhausted, WikipediaBusy,
    assess_full_writing, assess_writing, generate_reading, generate_writing_test,
)
from backend.practice_models import PracticeSession
from backend.reading_sources import reference_url_key

MAX_ATTEMPTS = 3


def process(job):
    if job.kind == "worker_check":
        return {"ok": True}
    if job.kind == "reading_mock":
        started_at = job.result["progress"]["started_at"]

        def report_progress(stage, completed_passages, **details):
            with Session.begin() as session:
                session.execute(update(Job).where(
                    Job.id == job.id, Job.state == "running", Job.lease_token == job.lease_token,
                ).values(result={"progress": {
                    "stage": stage, "completed_passages": completed_passages, "started_at": started_at, **details,
                }}))

        with Session() as session:
            previous = session.execute(select(
                *(Job.result["passages"][index]["source"] for index in range(3))
            ).where(Job.learner_id == job.learner_id, Job.kind == "reading_mock", Job.state == "succeeded"))
            sources = [source for row in previous for source in row if source]
        return generate_reading(
            **job.payload, used_ids={source["page_id"] for source in sources if source.get("page_id")},
            used_titles={source["title"] for source in sources if source.get("title") and not source.get("reference_id")},
            used_references={source["reference_id"] for source in sources if source.get("reference_id")} |
            {reference_url_key(source["url"]) for source in sources if source.get("reference_id") and source.get("url")},
            report_progress=report_progress,
        )
    if job.kind == "writing_prompt":
        with Session() as session:
            previous = session.scalars(select(PracticeSession.content).filter_by(
                learner_id=job.learner_id, module="writing", deleted_at=None, parent_id=None,
            ).order_by(PracticeSession.started_at.desc().nulls_last()).limit(12))
            titles = {1: [], 2: []}
            for content in previous:
                for task in content.get("tasks", [content]):
                    if task.get("task") in titles:
                        titles[task["task"]].append(task["title"])
            last_test = session.scalar(select(Job.result).where(
                Job.learner_id == job.learner_id, Job.kind == "writing_prompt", Job.state == "succeeded",
                func.coalesce(
                    Job.result["visual_kind"].as_string(), Job.result["tasks"][0]["visual_kind"].as_string(),
                    Job.result["chart"]["title"].as_string(), Job.result["tasks"][0]["chart"]["title"].as_string(),
                ).is_not(None),
            ).order_by(Job.available_at.desc(), Job.id).limit(1))
        previous_visual = None
        if last_test:
            previous_visual = last_test.get("tasks", [last_test])[0].get("visual_kind", "bar")
        return generate_writing_test(**job.payload, recent_titles=titles, previous_visual=previous_visual)
    if job.kind == "writing_feedback":
        with Session() as session:
            attempt = session.get(PracticeSession, UUID(job.payload["attempt_id"]))
        if attempt.deleted_at is not None:
            return None
        if attempt.content["task"] == "full":
            return assess_full_writing(attempt.content, attempt.draft)
        return assess_writing(attempt.content, attempt.draft["essay"])
    raise ValueError("Unknown job type")


def run_once():
    now = datetime.now(UTC)
    with Session.begin() as session:
        job = session.scalar(
            select(Job)
            .where(or_(
                and_(Job.state == "queued", Job.available_at <= now),
                and_(Job.state == "running", Job.lease_expires_at <= now),
            ))
            .order_by(Job.available_at, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return False
        if job.attempts >= MAX_ATTEMPTS:
            job.state = "failed"
            job.error = "Worker lease expired."
            job.lease_token = job.lease_expires_at = None
            return True
        token = uuid4()
        job.state = "running"
        job.error = None
        job.attempts += 1
        job.lease_token = token
        job.lease_expires_at = now + timedelta(minutes=20 if job.kind == "reading_mock" else 10)
        if job.kind == "reading_mock":
            job.result = {"progress": {
                "stage": "finding_sources", "completed_passages": 0, "started_at": now.isoformat(),
            }}

    retry = True
    limited_kinds = ()
    try:
        result = process(job)
        error = None
        cooldown = None
    except WikipediaBusy as failure:
        result = None
        cooldown = datetime.now(UTC) + timedelta(seconds=failure.retry_after)
        error = f"Wikipedia is rate-limiting requests. Retry after {cooldown:%H:%M:%S} UTC."
        limited_kinds = ("reading_mock",)
        logging.warning("Wikipedia limited job %s; retry after %s", job.id, cooldown)
    except ModelBusy as failure:
        result = None
        cooldown = datetime.now(UTC) + timedelta(seconds=failure.retry_after)
        error = f"The AI provider is rate-limiting requests. Retry after {cooldown:%H:%M:%S} UTC."
        limited_kinds = ("reading_mock", "writing_feedback", "writing_prompt")
        logging.warning("AI provider limited job %s; retry after %s", job.id, cooldown)
    except (ReadingSourcesExhausted, ModelQuotaExhausted, ModelOutputLimit, ReadingGenerationTimeout) as failure:
        result = None
        cooldown = None
        error = str(failure)
        retry = False
    except DraftValidationError as failure:
        logging.warning("Job %s generated an invalid draft: %s", job.id, failure)
        result = None
        error = str(failure)[:160]
        cooldown = None
    except Exception:
        logging.exception("Job %s failed", job.id)
        result = None
        error = "Job processing failed."
        cooldown = None

    with Session.begin() as session:
        current = session.get(Job, job.id, with_for_update=True)
        if current is not None and current.lease_token == token:
            current.result = result
            current.error = error
            current.lease_token = current.lease_expires_at = None
            if error and retry and current.attempts < MAX_ATTEMPTS:
                current.state = "queued"
                current.available_at = cooldown or (datetime.now(UTC) + timedelta(seconds=2 ** current.attempts))
            else:
                current.state = "failed" if error else "succeeded"
                if current.kind == "writing_feedback" and result is not None:
                    attempt = session.get(PracticeSession, UUID(current.payload["attempt_id"]), with_for_update=True)
                    if attempt.deleted_at is None:
                        attempt.result = result
                    else:
                        current.result = None
            if cooldown is not None:
                current.available_at = cooldown
                queued = session.query(Job).filter(
                    Job.kind.in_(limited_kinds), Job.state == "queued", Job.available_at < cooldown,
                )
                if limited_kinds == ("reading_mock",):
                    queued = queued.filter(func.coalesce(Job.payload["source"].as_string(), "wikipedia") == "wikipedia")
                queued.update({Job.available_at: cooldown, Job.error: error})
    return True


if __name__ == "__main__":
    while True:
        try:
            if not run_once():
                sleep(1)
        except SQLAlchemyError:
            logging.exception("Worker database operation failed")
            sleep(3)
