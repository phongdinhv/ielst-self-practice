from datetime import UTC, datetime, timedelta
from json import dumps
from typing import Literal
from urllib.error import URLError
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, StrictBool
from sqlalchemy import literal, select

from backend.identity import LearnerId
from backend.db import Session
from backend.models import Job, Learner
from backend.practice_ai import ModelBusy, ModelQuotaExhausted, normalize, suggest_vocabulary
from backend.practice_models import PracticeSession
from backend.progress import practice_band_fields
from backend.reading_sources import PUBLISHER_FEEDS, PUBLISHERS, publisher_topic_ids
from backend.reading_topics import MIXED_TOPICS, TOPIC_CATEGORIES, TOPIC_GROUPS, TOPICS
from backend.writing_prompts import WRITING_CATEGORY_THEMES, WRITING_PROMPTS, uses_process_visual

router = APIRouter(prefix="/api/v1/practice")
MAX_WRITING_RETRIES = 3

class Start(BaseModel):
    task: Literal[1, 2, "full"] = 2
    writing_topics: dict[Literal["1", "2"], str] = Field(default_factory=dict)
    writing_job_id: UUID | None = None
    reading_job_id: UUID | None = None
    parent_id: UUID | None = None
    mode: Literal["exam", "learning"] = "exam"
    video_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{11}$")
    simulate: bool = False
    simulation_id: UUID | None = None


class Work(BaseModel):
    answers: dict[int, str] = Field(default_factory=dict, max_length=40)
    essay: str = Field(default="", max_length=30000)
    essay_task2: str = Field(default="", max_length=30000)


class MockRequest(BaseModel):
    topic: str | None = None
    source: str = "wikipedia"


class WritingGeneration(BaseModel):
    task: Literal[1, 2, "full"] = "full"
    mode: Literal["exam", "learning"] = "exam"
    categories: dict[Literal["1", "2"], str] = Field(default_factory=dict)


class HintRequest(BaseModel):
    task: Literal[1, 2]
    draft: str = Field(default="", max_length=30000)


class ListeningMarks(BaseModel):
    correct: list[StrictBool] = Field(min_length=40, max_length=40)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def find(session, attempt_id, learner_id, *, lock=False, include_deleted=False):
    query = select(PracticeSession).filter_by(id=attempt_id, learner_id=learner_id)
    if not include_deleted:
        query = query.where(PracticeSession.deleted_at.is_(None))
    attempt = session.scalar(query.with_for_update() if lock else query)
    if attempt is None:
        raise HTTPException(404, "Session not found")
    return attempt


def writing_series(session, attempt, *, lock=False):
    root = attempt
    while root.parent_id is not None:
        root = find(session, root.parent_id, attempt.learner_id, include_deleted=True)
    if lock:
        find(session, root.id, attempt.learner_id, lock=True, include_deleted=True)
    family = select(PracticeSession.id, literal(0).label("depth")).where(
        PracticeSession.id == root.id,
    ).cte(recursive=True)
    family = family.union_all(select(PracticeSession.id, family.c.depth + 1).join(
        family, PracticeSession.parent_id == family.c.id,
    ).where(PracticeSession.learner_id == attempt.learner_id, PracticeSession.module == "writing"))
    return list(session.scalars(select(PracticeSession).join(
        family, PracticeSession.id == family.c.id,
    ).order_by(PracticeSession.started_at.asc().nulls_first(), family.c.depth, PracticeSession.id)))


def serialize(attempt):
    content = attempt.content
    result = attempt.result
    if result is not None:
        result = {**result, **practice_band_fields(result)}
    if attempt.module == "reading" and content["title"] == "Academic Reading mock":
        content = {**content, "title": MIXED_TOPICS}
    if attempt.module == "reading" and attempt.submitted_at is None:
        content = {**content, "passages": [
            {**passage, "questions": [
                {key: question[key] for key in ("question_id", "type", "prompt", "options", "word_limit") if key in question}
                for question in passage["questions"]
            ]} for passage in content["passages"]
        ]}
    if attempt.module == "writing" and attempt.submitted_at is None:
        if content.get("task") == "full":
            content = {**content, "tasks": [
                {key: value for key, value in task.items() if key != "reference_analysis"}
                for task in content["tasks"]
            ]}
        else:
            content = {key: value for key, value in content.items() if key != "reference_analysis"}
    return {
        "id": attempt.id, "module": attempt.module, "parent_id": attempt.parent_id, "content": content,
        "deadline": utc(attempt.deadline), "submitted_at": attempt.submitted_at,
        "paused_at": utc(attempt.paused_at) if attempt.paused_at else None,
        "draft": attempt.draft, "result": result,
    }


@router.get("/reading/topics")
def reading_topics():
    return {"groups": [
        {"name": group, "topics": [{"id": key, "label": label} for key, (label, _) in topics.items()]}
        for group, topics in TOPIC_GROUPS.items()
    ], "sources": [
        {"id": "random", "label": "Random source", "description": "Choose an available source for this mock.", "topic_ids": list(TOPICS)},
        {"id": "wikipedia", "label": "Wikipedia", "description": "Use Wikipedia article extracts.", "topic_ids": list(TOPICS)},
        *[{"id": key, "label": label, "description": f"{description} · " +
          ("Feed headlines and reference briefs" if key in PUBLISHER_FEEDS else "Original reference briefs"),
          "topic_ids": publisher_topic_ids(key)}
          for key, (label, _, description) in PUBLISHERS.items()],
    ]}


@router.post("/reading/generate", status_code=202)
def prepare_reading(learner_id: LearnerId, request: MockRequest | None = None):
    topic = request.topic if request else None
    source = request.source if request else "wikipedia"
    if topic is not None and topic not in TOPICS:
        raise HTTPException(422, "Choose a Reading topic from the list")
    if source not in PUBLISHERS and source not in ("wikipedia", "random"):
        raise HTTPException(422, "Choose a Reading source from the list")
    if topic is not None and source in PUBLISHERS and topic not in publisher_topic_ids(source):
        raise HTTPException(422, "Choose a topic available for this source, or use random topics")
    with Session.begin() as session:
        if session.get(Learner, learner_id, with_for_update=True) is None:
            raise HTTPException(503, "Local learner has not been seeded")
        active = session.scalar(select(Job.id).where(
            Job.learner_id == learner_id, Job.kind == "reading_mock",
            Job.state.in_(("queued", "running")),
        ).order_by(Job.available_at.desc()).limit(1))
        if active:
            return {"job_id": active}
        now = datetime.now(UTC)
        provider_limited = Job.error.startswith("The AI provider is rate-limiting requests.")
        if source == "wikipedia":
            provider_limited |= Job.error.startswith("Wikipedia is rate-limiting requests.")
        cooldown = session.scalar(select(Job).where(
            Job.kind.in_(("reading_mock", "writing_feedback")),
            Job.available_at > now, provider_limited,
        ).order_by(Job.available_at.desc()).limit(1))
        payload = {"topic": topic} if topic else {}
        if source != "wikipedia":
            payload["source"] = source
        job = Job(learner_id=learner_id, kind="reading_mock", payload=payload,
                  deduplication_key=str(uuid4()),
                  available_at=cooldown.available_at if cooldown else now,
                  error=cooldown.error if cooldown else None)
        session.add(job)
        session.flush()
        return {"job_id": job.id}


def completed_reading_mocks(session, learner_id):
    attempts = list(session.execute(select(
        PracticeSession.content["reading_mock_id"].as_string(), PracticeSession.content["passages"],
    ).where(
        PracticeSession.learner_id == learner_id, PracticeSession.module == "reading",
        PracticeSession.submitted_at.is_not(None), PracticeSession.deleted_at.is_(None),
    )))
    completed_ids = {mock_id for mock_id, _ in attempts if mock_id}
    # Older attempts saved the passages without recording the source mock ID.
    legacy_passages = {dumps(passages, sort_keys=True) for mock_id, passages in attempts if not mock_id}
    return completed_ids, legacy_passages


@router.get("/reading/mocks")
def recent_mocks(learner_id: LearnerId):
    with Session() as session:
        scope = (Job.learner_id == learner_id, Job.kind == "reading_mock", Job.archived_at.is_(None))
        order = (Job.available_at.desc(), Job.id)
        completed_ids, legacy_passages = completed_reading_mocks(session, learner_id)
        saved_query = select(
            Job.id, Job.payload["topic"].as_string(),
            Job.result["passages"][0]["title"].as_string(), Job.available_at,
            Job.result["source_name"].as_string(),
        ).where(*scope, Job.state == "succeeded").order_by(*order)
        if legacy_passages:
            saved_query = saved_query.add_columns(Job.result["passages"])
        saved = []
        for job_id, topic_id, first_passage, date, source_name, *content in session.execute(saved_query):
            completed = str(job_id) in completed_ids or (
                bool(content) and dumps(content[0], sort_keys=True) in legacy_passages
            )
            category = TOPIC_CATEGORIES.get(topic_id, MIXED_TOPICS)
            saved.append({
                "id": job_id, "title": category, "topic": TOPICS[topic_id][0] if topic_id in TOPICS else None,
                "first_passage": first_passage,
                "date": utc(date), "completed": completed, "source_name": source_name or "Wikipedia",
            })
        return {
            "latest_id": session.scalar(select(Job.id).where(*scope).order_by(*order).limit(1)),
            "ready_id": saved[0]["id"] if saved else None,
            "items": saved,
        }


@router.delete("/reading/mocks/{mock_id}", status_code=204)
def delete_reading_mock(mock_id: UUID, learner_id: LearnerId):
    with Session.begin() as session:
        job = session.scalar(select(Job).filter_by(
            id=mock_id, learner_id=learner_id, kind="reading_mock", state="succeeded", archived_at=None,
        ).with_for_update())
        if job is None:
            raise HTTPException(404, "Reading mock not found")
        completed_ids, legacy_passages = completed_reading_mocks(session, learner_id)
        if str(job.id) in completed_ids or dumps(job.result["passages"], sort_keys=True) in legacy_passages:
            raise HTTPException(409, "Only unfinished Reading mocks can be deleted")
        job.archived_at = datetime.now(UTC)
    return Response(status_code=204)


@router.get("/writing/topics")
def writing_topics():
    return {"categories": sorted(WRITING_CATEGORY_THEMES)}


@router.post("/writing/generate", status_code=202)
def prepare_writing(request: WritingGeneration, learner_id: LearnerId):
    if any(category not in WRITING_CATEGORY_THEMES for category in request.categories.values()):
        raise HTTPException(422, "Choose a Writing category from the list")
    if request.task != "full" and set(request.categories) - {str(request.task)}:
        raise HTTPException(422, "Choose a category for the Writing task you are generating")
    payload = request.model_dump()
    with Session.begin() as session:
        if session.get(Learner, learner_id, with_for_update=True) is None:
            raise HTTPException(503, "Local learner has not been seeded")
        active = session.scalar(select(Job).where(
            Job.learner_id == learner_id, Job.kind == "writing_prompt", Job.state.in_(("queued", "running")),
        ))
        if active is not None:
            if active.payload != payload:
                raise HTTPException(409, "Finish generating your current Writing prompts before changing categories")
            return {"job_id": active.id}
        now = datetime.now(UTC)
        cooldown = session.scalar(select(Job).where(
            Job.available_at > now,
            Job.error.startswith("The AI provider is rate-limiting requests."),
        ).order_by(Job.available_at.desc()).limit(1))
        job = Job(learner_id=learner_id, kind="writing_prompt", payload=payload, deduplication_key=str(uuid4()),
                  available_at=cooldown.available_at if cooldown else now, error=cooldown.error if cooldown else None)
        session.add(job)
        session.flush()
        return {"job_id": job.id}


def next_writing_prompt(task, previous, topic=None):
    prompts = WRITING_PROMPTS[task]
    if topic is not None:
        selected = next((prompt for prompt in prompts if prompt["topic"] == topic), None)
        if selected is None:
            raise HTTPException(422, f"Choose a topic available for Writing Task {task}")
        return {**selected, "task": task}
    last_prompt = next((
        prompt
        for item in previous
        for prompt in (item["tasks"] if item.get("task") == "full" else [item])
        if prompt.get("task") == task
    ), {})
    last_index = next((index for index, prompt in enumerate(prompts) if prompt["title"] == last_prompt.get("title")), -1)
    return {**prompts[(last_index + 1) % len(prompts)], "task": task}


SIMULATION_ORDER = ("listening", "reading", "writing")


def simulation_sessions(session, learner_id, simulation_id):
    return list(session.scalars(select(PracticeSession).where(
        PracticeSession.learner_id == learner_id,
        PracticeSession.content["simulation_id"].as_string() == str(simulation_id),
    )))


@router.post("/{module}/start", status_code=201)
def start(module: Literal["listening", "reading", "writing"], request: Start, learner_id: LearnerId):
    if request.writing_job_id and (module != "writing" or request.parent_id or request.simulation_id or request.writing_topics):
        raise HTTPException(422, "Use a Writing generation job to start a new standalone Writing session")
    if request.writing_topics:
        if module != "writing" or request.parent_id or request.simulation_id:
            raise HTTPException(422, "Choose Writing topics when starting a new standalone Writing session")
        if request.task != "full" and set(request.writing_topics) != {str(request.task)}:
            raise HTTPException(422, "Select a topic for the Writing task you are starting")
    with Session.begin() as session:
        simulation_id = request.simulation_id
        if request.simulate:
            if module != "listening" or simulation_id is not None:
                raise HTTPException(422, "Start a three-skill simulation with Listening")
            simulation_id = uuid4()
        elif simulation_id is not None:
            session.get(Learner, learner_id, with_for_update=True)
            sections = {item.module: item for item in simulation_sessions(session, learner_id, simulation_id)}
            if module in sections:
                if sections[module].deleted_at is not None:
                    raise HTTPException(409, "This simulation section was deleted")
                return serialize(sections[module])
            expected = SIMULATION_ORDER[len(sections)] if len(sections) < 3 else None
            if not sections or module != expected or any(
                item.submitted_at is None or (item.result is None and item.deleted_at is None)
                for item in sections.values()
            ):
                raise HTTPException(409, "Finish the current simulation section first")
            if module == "writing" and (request.task != "full" or request.mode != "exam" or request.parent_id):
                raise HTTPException(422, "Use the full Writing exam for the simulation")
        if module == "listening":
            if request.video_id is None:
                raise HTTPException(422, "Choose a Listening video before starting")
            content, minutes = {"title": "Listening practice", "video_id": request.video_id}, 30
        elif module == "reading":
            job = session.scalar(select(Job).filter_by(
                id=request.reading_job_id, learner_id=learner_id, kind="reading_mock", state="succeeded", archived_at=None,
            ).with_for_update())
            if job is None:
                raise HTTPException(409, "Generate a Reading mock before starting")
            topic_id = job.payload.get("topic")
            content, minutes = {
                **job.result,
                "title": TOPIC_CATEGORIES.get(topic_id, MIXED_TOPICS),
                "reading_topic": TOPICS[topic_id][0] if topic_id in TOPICS else None,
                "reading_mock_id": str(job.id),
                "reading_option_order": "shuffled-v1",
            }, 60
        else:
            if request.parent_id:
                parent = find(session, request.parent_id, learner_id)
                if parent.module != "writing" or not parent.submitted_at:
                    raise HTTPException(409, "Choose a submitted Writing session")
                series = writing_series(session, parent, lock=True)
                latest = next(item for item in reversed(series) if item.deleted_at is None)
                if latest.parent_id == parent.id and latest.submitted_at is None:
                    return serialize(latest)
                if latest.id != parent.id:
                    raise HTTPException(409, "Open your latest Writing attempt to continue")
                if len(series) > MAX_WRITING_RETRIES:
                    raise HTTPException(409, "You have used all three rewrites for this test")
                content = {key: value for key, value in parent.content.items() if key != "simulation_id"}
            elif request.writing_job_id:
                job = session.scalar(select(Job).filter_by(
                    id=request.writing_job_id, learner_id=learner_id, kind="writing_prompt", state="succeeded",
                ).with_for_update())
                if job is None:
                    raise HTTPException(409, "Generate the Writing prompts before starting")
                existing = session.scalar(select(PracticeSession).where(
                    PracticeSession.learner_id == learner_id, PracticeSession.module == "writing",
                    PracticeSession.parent_id.is_(None), PracticeSession.deleted_at.is_(None),
                    PracticeSession.content["writing_job_id"].as_string() == str(job.id),
                ))
                if existing is not None:
                    return serialize(existing)
                if uses_process_visual(job.result):
                    raise HTTPException(409, "Generate a new Writing prompt with numerical data before starting")
                content = {**job.result, "writing_job_id": str(job.id)}
            else:
                previous = list(session.scalars(select(PracticeSession.content).filter_by(
                    learner_id=learner_id, module="writing", deleted_at=None,
                ).order_by(PracticeSession.started_at.desc().nulls_last(), PracticeSession.id)))
                if request.task == "full":
                    content = {
                        "title": "Academic Writing test", "task": "full",
                        "tasks": [next_writing_prompt(task, previous, request.writing_topics.get(str(task)))
                                  for task in (1, 2)],
                    }
                else:
                    content = next_writing_prompt(request.task, previous, request.writing_topics.get(str(request.task)))
                if request.mode == "learning":
                    content["mode"] = "learning"
            minutes = {1: 20, 2: 40, "full": 60}[content["task"]]
        if simulation_id is not None:
            content = {**content, "simulation_id": str(simulation_id)}
        now = datetime.now(UTC)
        attempt = PracticeSession(
            learner_id=learner_id, module=module, content=content, draft={},
            parent_id=request.parent_id if module == "writing" else None,
            started_at=now, deadline=now + timedelta(minutes=minutes),
        )
        session.add(attempt)
        session.flush()
        return serialize(attempt)


@router.get("/simulation/{simulation_id}")
def simulation_detail(simulation_id: UUID, learner_id: LearnerId):
    with Session() as session:
        sections = {item.module: item for item in simulation_sessions(session, learner_id, simulation_id)}
        if not sections:
            raise HTTPException(404, "Simulation not found")
        return {"items": [{
            "id": item.id, "module": item.module, "submitted": item.submitted_at is not None,
            "score": (item.result or {}).get("score"), "band": (item.result or {}).get("band"),
            **practice_band_fields(item.result),
        } for module in SIMULATION_ORDER if (item := sections.get(module)) is not None and item.deleted_at is None]}


def finalize(session, attempt):
    attempt.submitted_at = datetime.now(UTC)
    if attempt.module == "reading":
        questions = [question for passage in attempt.content["passages"] for question in passage["questions"]]
        answers = attempt.draft.get("answers", {})
        items = []
        for number, question in enumerate(questions, 1):
            answer = answers.get(str(number), "")
            normalized = normalize(answer)
            correct = normalized in map(normalize, question["answers"])
            items.append({"number": number, "answer": answer,
                          "status": "correct" if correct else "incorrect" if normalized else "unanswered"})
        attempt.result = {"kind": "reading_raw", "score": sum(item["status"] == "correct" for item in items),
                          "maximum": len(items), "items": items}
    elif attempt.module == "writing":
        job = Job(learner_id=attempt.learner_id, kind="writing_feedback", payload={"attempt_id": str(attempt.id)},
                  deduplication_key=str(attempt.id), available_at=datetime.now(UTC))
        session.add(job)
        session.flush()
        attempt.result = {"kind": "writing_pending", "job_id": str(job.id)}


@router.post("/sessions/{attempt_id}/listening-score")
def self_score_listening(attempt_id: UUID, request: ListeningMarks, learner_id: LearnerId):
    with Session.begin() as session:
        attempt = find(session, attempt_id, learner_id, lock=True)
        if attempt.module != "listening" or attempt.submitted_at is None:
            raise HTTPException(409, "Submit the Listening session before marking your answers")
        if attempt.result is None:
            responses = attempt.draft.get("answers", {})
            items = [{
                "number": number,
                "answer": responses.get(str(number), ""),
                "status": "correct" if correct else "incorrect",
            } for number, correct in enumerate(request.correct, 1)]
            attempt.result = {"kind": "listening_self_scored",
                              "score": sum(request.correct),
                              "maximum": 40, "items": items}
        return serialize(attempt)


@router.get("/sessions")
def history(learner_id: LearnerId):
    with Session.begin() as session:
        expired = session.scalars(select(PracticeSession).where(
            PracticeSession.learner_id == learner_id, PracticeSession.submitted_at.is_(None),
            PracticeSession.deleted_at.is_(None),
            PracticeSession.paused_at.is_(None), PracticeSession.deadline <= datetime.now(UTC),
        ).with_for_update())
        for attempt in expired:
            finalize(session, attempt)
        attempts = session.scalars(select(PracticeSession).filter_by(learner_id=learner_id, deleted_at=None)
                                   .order_by(PracticeSession.submitted_at.desc().nulls_first(),
                                             PracticeSession.started_at.desc().nulls_last(), PracticeSession.id))
        return {"items": [{
            "id": item.id, "module": item.module,
            "title": MIXED_TOPICS if item.module == "reading" and item.content["title"] == "Academic Reading mock"
            else item.content["title"],
            "task": item.content.get("task"), "submitted_at": item.submitted_at,
            "mode": item.content.get("mode", "exam"),
            "started_at": utc(item.started_at) if item.started_at else None,
            "paused_at": utc(item.paused_at) if item.paused_at else None,
            "deadline": utc(item.deadline),
            "score": (item.result or {}).get("score"), "maximum": (item.result or {}).get("maximum"),
            "band": (item.result or {}).get("band"),
            **practice_band_fields(item.result),
        } for item in attempts]}


@router.get("/sessions/{attempt_id}")
def detail(attempt_id: UUID, learner_id: LearnerId):
    with Session.begin() as session:
        attempt = find(session, attempt_id, learner_id, lock=True)
        if attempt.submitted_at is None and attempt.paused_at is None and datetime.now(UTC) >= utc(attempt.deadline):
            finalize(session, attempt)
        return serialize(attempt)


@router.delete("/sessions/{attempt_id}", status_code=204)
def delete_session(attempt_id: UUID, learner_id: LearnerId):
    with Session.begin() as session:
        attempt = find(session, attempt_id, learner_id, lock=True)
        if attempt.submitted_at is None:
            session.delete(attempt)
        else:
            attempt.deleted_at = datetime.now(UTC)
            attempt.draft = {}
            attempt.result = None
    return Response(status_code=204)


@router.get("/sessions/{attempt_id}/revisions")
def writing_revisions(attempt_id: UUID, learner_id: LearnerId):
    with Session() as session:
        attempt = find(session, attempt_id, learner_id)
        if attempt.module != "writing":
            raise HTTPException(404, "Writing session not found")
        series = writing_series(session, attempt)
        return {
            "retry_limit": MAX_WRITING_RETRIES,
            "remaining": max(0, 1 + MAX_WRITING_RETRIES - len(series)),
            "latest_id": next(item.id for item in reversed(series) if item.deleted_at is None),
            "items": [{
                "id": item.id, "number": index, "submitted": item.submitted_at is not None,
                "band": (item.result or {}).get("band"),
                "task_bands": [task["band"] for task in (item.result or {}).get("tasks", [])],
            } for index, item in enumerate(series) if item.deleted_at is None],
        }


@router.put("/sessions/{attempt_id}/draft")
def save(attempt_id: UUID, work: Work, learner_id: LearnerId):
    with Session.begin() as session:
        attempt = find(session, attempt_id, learner_id, lock=True)
        if attempt.submitted_at is None and attempt.paused_at is None and datetime.now(UTC) < utc(attempt.deadline):
            attempt.draft = work.model_dump(mode="json")
            return {"saved": True}
        return {"saved": False}


@router.post("/sessions/{attempt_id}/submit")
def submit(attempt_id: UUID, work: Work, learner_id: LearnerId):
    with Session.begin() as session:
        attempt = find(session, attempt_id, learner_id, lock=True)
        if attempt.submitted_at is None:
            if attempt.paused_at is not None:
                raise HTTPException(409, "Resume the session before submitting")
            if datetime.now(UTC) < utc(attempt.deadline):
                attempt.draft = work.model_dump(mode="json")
            finalize(session, attempt)
        return serialize(attempt)


@router.post("/sessions/{attempt_id}/pause")
def pause(attempt_id: UUID, work: Work, learner_id: LearnerId):
    with Session.begin() as session:
        attempt = find(session, attempt_id, learner_id, lock=True)
        if attempt.submitted_at is None and attempt.paused_at is None:
            now = datetime.now(UTC)
            if now >= utc(attempt.deadline):
                finalize(session, attempt)
            else:
                attempt.draft = work.model_dump(mode="json")
                attempt.paused_at = now
        return serialize(attempt)


@router.post("/sessions/{attempt_id}/resume")
def resume(attempt_id: UUID, learner_id: LearnerId):
    with Session.begin() as session:
        attempt = find(session, attempt_id, learner_id, lock=True)
        if attempt.submitted_at is None and attempt.paused_at:
            attempt.deadline = utc(attempt.deadline) + (datetime.now(UTC) - utc(attempt.paused_at))
            attempt.paused_at = None
        return serialize(attempt)


@router.post("/sessions/{attempt_id}/vocabulary")
def writing_vocabulary(attempt_id: UUID, request: HintRequest, learner_id: LearnerId):
    with Session() as session:
        attempt = find(session, attempt_id, learner_id)
        if (attempt.module != "writing" or attempt.content.get("mode") != "learning"
                or attempt.submitted_at or attempt.paused_at or datetime.now(UTC) >= utc(attempt.deadline)):
            raise HTTPException(409, "Vocabulary hints are available during active Writing learning sessions")
        content = serialize(attempt)["content"]
        if content["task"] == "full":
            content = content["tasks"][request.task - 1]
        if content["task"] != request.task:
            raise HTTPException(422, "Choose the current Writing task")
    try:
        return suggest_vocabulary(content, request.draft)
    except ModelBusy as error:
        raise HTTPException(429, "The AI provider is rate-limiting requests. Try again shortly.",
                            headers={"Retry-After": str(error.retry_after)}) from error
    except ModelQuotaExhausted as error:
        raise HTTPException(503, str(error)) from error
    except (ValueError, URLError, TimeoutError, OSError) as error:
        raise HTTPException(502, "Vocabulary hints are unavailable right now. Try again.") from error
