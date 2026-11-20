from datetime import UTC, datetime
from io import BytesIO
from urllib.error import HTTPError
from uuid import UUID

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import api, db, practice, practice_ai, reading_sources, worker
from backend.models import Job
from backend.practice_ai import ReadingQuestion, WikipediaBusy, canonical_choice
from backend.practice_models import PracticeSession
from backend.progress import practice_band_fields


READING_ASSESSMENT = {
    "targeted_skill": "Find evidence", "difficulty_estimate": "moderate",
    "additional_evidence": [], "distractor_analysis": [],
}


def writing_reference():
    return {
        "key_features": ["Participation differs by group.", "Some groups rise over time."],
        "important_comparisons": ["Compare the initial and final rankings."],
        "accepted_numeric_interpretations": ["Use the displayed units consistently."],
        "secondary_details": [], "common_errors": ["Avoid confusing counts and shares."],
        "sample_response": "The visual presents data on participation across the groups. " * 20,
        "difficulty_estimate": "moderate",
    }


def test_migration_dashboard_and_worker(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    sessions = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(api, "Session", sessions)
    monkeypatch.setattr(practice, "Session", sessions)
    monkeypatch.setattr(worker, "Session", sessions)
    config = Config("alembic.ini")
    command.upgrade(config, "head")

    with TestClient(api.app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        goals = client.get("/api/v1/dashboard").json()["goals"]
        assert [(goal["module"], goal["minimum_band"], goal["maximum_band"]) for goal in goals] == [
            ("listening", 9.0, 9.0),
            ("reading", 9.0, 9.0),
            ("writing", 7.5, 9.0),
        ]
        headers = {"Idempotency-Key": "smoke-test"}
        path = "/api/v1/jobs/worker-check"
        created = client.post(path, headers=headers)
        assert created.status_code == 202
        assert client.post(path, headers=headers).json() == created.json()
        status_path = f"/api/v1/jobs/{created.json()['job_id']}"
        assert client.get(status_path).json()["state"] == "queued"
        assert worker.run_once()
        assert client.get(status_path).json()["result"] == {"ok": True}
        assert client.get(status_path).json()["state"] == "succeeded"
        assert not worker.run_once()

    command.downgrade(config, "base")
    engine.dispose()


def test_reading_and_writing_sessions(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'practice.db'}")
    sessions = sessionmaker(engine, expire_on_commit=False)
    for module in (api, practice, worker):
        monkeypatch.setattr(module, "Session", sessions)
    monkeypatch.setattr(db, "engine", engine)
    question = {"question_id": "passage-1-q1", "assessment": READING_ASSESSMENT,
                "type": "completion", "prompt": "Enter a word", "options": [], "word_limit": 1,
                "answers": ["sample"], "explanation": "The passage identifies the sample.", "evidence": "sample"}
    monkeypatch.setattr(worker, "generate_reading", lambda **_: {
        "title": "Mock", "passages": [
            {"title": f"Passage {index}", "text": "sample", "questions": [question] * count,
             "source": {"page_id": index, "title": f"Source {index}"}}
            for index, count in enumerate((13, 13, 14), 1)
        ],
    })
    monkeypatch.setattr(worker, "assess_writing", lambda content, essay: {
        "kind": "unofficial_writing_estimate", "band": 7.5, "criteria": {},
    })
    command.upgrade(Config("alembic.ini"), "head")
    with TestClient(api.app) as client:
        prefix = "/api/v1/practice"
        catalog = client.get(f"{prefix}/reading/topics").json()
        groups = catalog["groups"]
        assert sum(len(group["topics"]) for group in groups) > 20
        assert len(catalog["sources"]) == 10
        choices = {source["id"]: source["topic_ids"] for source in catalog["sources"]}
        assert all(choices.values())
        assert "astronomy" in choices["nasa"] and "archaeology" not in choices["nasa"]
        assert "archaeology" in choices["smithsonian"]
        assert client.post(
            f"{prefix}/reading/generate", json={"topic": "archaeology", "source": "nasa"},
        ).status_code == 422
        assert client.post(f"{prefix}/reading/generate", json={"source": "unknown"}).status_code == 422
        assert client.post(f"{prefix}/reading/generate", json={"topic": "unknown"}).status_code == 422
        generation = client.post(f"{prefix}/reading/generate").json()["job_id"]
        assert client.post(f"{prefix}/reading/generate").json()["job_id"] == generation
        assert worker.run_once()
        saved = client.get(f"{prefix}/reading/mocks").json()
        assert saved["ready_id"] == generation
        assert saved["items"][0]["title"] == "Mixed topics"
        assert saved["items"][0]["first_passage"] == "Passage 1"
        assert not saved["items"][0]["completed"]
        assert set(saved["items"][0]) == {"id", "title", "topic", "first_passage", "date", "completed", "source_name"}
        first_mock = worker.generate_reading

        def next_mock(topic, source, *, used_ids, used_titles, used_references, report_progress):
            assert topic == "climate-adaptation"
            assert source == "nasa"
            assert used_ids == {1, 2, 3}
            assert used_titles == {"Source 1", "Source 2", "Source 3"}
            status_url = f"/api/v1/jobs/{second_generation}"
            initial = client.get(status_url).json()
            assert initial["progress"]["stage"] == "finding_sources"
            report_progress("generating_passages", 1, drafted_passages=2, completed_groups=3)
            running = client.get(status_url).json()
            assert running["result"] is None
            assert running["progress"] == {
                "stage": "generating_passages", "completed_passages": 1, "drafted_passages": 2, "completed_groups": 3,
                "started_at": initial["progress"]["started_at"],
            }
            mock = first_mock()
            mock["source_name"] = "NASA"
            mock["passages"][0]["text"] = "A different sample."
            for index, passage in enumerate(mock["passages"], 1):
                passage["source"] = {"page_id": index + 100, "title": f"New source {index}"}
            return mock

        monkeypatch.setattr(worker, "generate_reading", next_mock)
        second_generation = client.post(
            f"{prefix}/reading/generate", json={"topic": "climate-adaptation", "source": "nasa"},
        ).json()["job_id"]
        assert worker.run_once()
        assert client.get(f"/api/v1/jobs/{second_generation}").json()["progress"] is None
        mocks = client.get(f"{prefix}/reading/mocks").json()["items"]
        assert [item["id"] for item in mocks] == [second_generation, generation]
        assert mocks[0]["title"] == "Environment"
        assert mocks[0]["topic"] == "Climate adaptation"
        assert mocks[0]["source_name"] == "NASA"
        assert client.get(f"/api/v1/jobs/{generation}").json()["result"] is None
        reading = client.post(f"{prefix}/reading/start", json={"reading_job_id": generation}).json()
        assert reading["content"]["reading_option_order"] == "shuffled-v1"
        assert "answers" not in reading["content"]["passages"][0]["questions"][0]
        assert "assessment" not in reading["content"]["passages"][0]["questions"][0]
        assert reading["content"]["passages"][0]["questions"][0]["question_id"] == "passage-1-q1"
        url = f"{prefix}/sessions/{reading['id']}"
        work = {"answers": {"1": " SAMPLE ", "2": "wrong"}}
        assert client.put(f"{url}/draft", json=work).json()["saved"]
        paused = client.post(f"{url}/pause", json=work).json()
        assert paused["paused_at"]
        assert client.get(url).json()["paused_at"] == paused["paused_at"]
        entry = client.get(f"{prefix}/sessions").json()["items"][0]
        assert entry["started_at"] and entry["paused_at"] == paused["paused_at"]
        assert not client.put(f"{url}/draft", json={}).json()["saved"]
        assert client.post(f"{url}/submit", json=work).status_code == 409
        resumed = client.post(f"{url}/resume").json()
        assert resumed["paused_at"] is None
        assert resumed["deadline"] > paused["deadline"]
        assert client.get(url).json()["draft"]["answers"] == work["answers"]
        result = client.post(f"{url}/submit", json=work).json()["result"]
        assert (result["score"], result["maximum"]) == (1, 40)
        assert result["band_upper_bound"] == 2.5 and result["band_estimated"]
        assert [item["status"] for item in result["items"][:3]] == ["correct", "incorrect", "unanswered"]
        assert client.post(f"{url}/submit", json={}).json()["result"] == result
        expected_completion = {second_generation: False, generation: True}
        saved = client.get(f"{prefix}/reading/mocks").json()["items"]
        assert {item["id"]: item["completed"] for item in saved} == expected_completion

        with sessions.begin() as session:
            legacy_attempt = session.get(PracticeSession, UUID(reading["id"]))
            legacy_attempt.content = {
                key: value for key, value in legacy_attempt.content.items() if key != "reading_mock_id"
            }
        saved = client.get(f"{prefix}/reading/mocks").json()["items"]
        assert {item["id"]: item["completed"] for item in saved} == expected_completion

        writing = client.post(f"{prefix}/writing/start", json={"task": 1}).json()
        assert writing["content"]["table"]
        url = f"{prefix}/sessions/{writing['id']}"
        submitted = client.post(f"{url}/submit", json={"essay": "Original response."}).json()
        assert submitted["result"]["kind"] == "writing_pending"
        assert worker.run_once()
        assert client.get(url).json()["result"]["band"] == 7.5
        revision = client.post(f"{prefix}/writing/start", json={"parent_id": writing["id"]}).json()
        assert revision["content"] == writing["content"]
        assert client.get(url).json()["draft"]["essay"] == "Original response."
        next_writing = client.post(f"{prefix}/writing/start", json={"task": 1}).json()
        assert next_writing["content"]["chart"]["years"] == ["2000", "2020"]
        history = client.get(f"{prefix}/sessions").json()["items"]
        assert {item["id"] for item in history} == {reading["id"], writing["id"], revision["id"], next_writing["id"]}
        graded = {item["id"]: item for item in history if item["submitted_at"]}
        assert graded[reading["id"]]["score"] == 1 and graded[reading["id"]]["maximum"] == 40
        assert graded[reading["id"]]["band_upper_bound"] == 2.5
        assert graded[writing["id"]]["band"] == 7.5
        estimates = client.get("/api/v1/dashboard").json()["estimates"]
        assert estimates["overall"] is None
        assert estimates["modules"]["reading"] == {"value": 1.0, "unit": "raw_40", "count": 1}
        assert estimates["modules"]["writing"] == {"value": 7.5, "unit": "band", "count": 1, "task": 1}
        task2 = client.post(f"{prefix}/writing/start", json={"task": 2}).json()
        hint_request = {"task": 2, "draft": "A draft for the second task."}
        assert client.post(f"{prefix}/sessions/{task2['id']}/vocabulary", json=hint_request).status_code == 409
        learning = client.post(f"{prefix}/writing/start", json={"task": "full", "mode": "learning"}).json()
        assert learning["content"]["mode"] == "learning"
        terms = ["congestion", "commute", "funding", "investment", "accessibility"]
        hints = {"words": [{"term": term, "meaning": "A definition", "phrase": "A collocation"} for term in terms]}

        def suggest(prompt, draft):
            assert prompt["task"] == 2
            assert draft == hint_request["draft"]
            return hints

        monkeypatch.setattr(practice, "suggest_vocabulary", suggest)
        assert client.post(f"{prefix}/sessions/{learning['id']}/vocabulary", json=hint_request).json() == hints
        monkeypatch.setattr(worker, "assess_writing", lambda content, essay: {
            "kind": "unofficial_writing_estimate", "band": 9.0, "criteria": {},
        })
        client.post(f"{prefix}/sessions/{task2['id']}/submit", json={"essay": "Second task response."})
        assert worker.run_once()
        estimate = client.get("/api/v1/dashboard").json()["estimates"]["modules"]["writing"]
        assert estimate == {"value": 8.5, "unit": "band", "count": 2}

        full = client.post(f"{prefix}/writing/start", json={"task": "full"}).json()
        assert [task["task"] for task in full["content"]["tasks"]] == [1, 2]
        full_url = f"{prefix}/sessions/{full['id']}"
        responses = {"essay": "Task one draft.", "essay_task2": "Task two draft."}
        paused = client.post(f"{full_url}/pause", json=responses).json()
        duration = datetime.fromisoformat(paused["deadline"]) - datetime.fromisoformat(paused["paused_at"])
        assert 3590 <= duration.total_seconds() <= 3600
        assert paused["draft"]["essay"] == responses["essay"]
        assert paused["draft"]["essay_task2"] == responses["essay_task2"]
        client.post(f"{full_url}/resume")
        monkeypatch.setattr(practice_ai, "assess_writing",
                            lambda content, essay: {"band": 6.0 if content["task"] == 1 else 9.0, "criteria": {}})
        client.post(f"{full_url}/submit", json=responses)
        assert worker.run_once()
        full_result = client.get(full_url).json()["result"]
        assert full_result["band"] == 8.0
        assert [task["band"] for task in full_result["tasks"]] == [6.0, 9.0]
        estimates = client.get("/api/v1/dashboard").json()["estimates"]
        assert estimates["modules"]["writing"]["count"] == 3

        duplicate = client.post(f"{prefix}/writing/start", json={"parent_id": writing["id"]}).json()
        assert duplicate["id"] == revision["id"]
        latest = revision
        for number in (1, 2, 3):
            latest_url = f"{prefix}/sessions/{latest['id']}"
            assert client.post(f"{latest_url}/submit", json={"essay": f"Rewrite {number}."}).status_code == 200
            assert worker.run_once()
            if number < 3:
                next_revision = client.post(f"{prefix}/writing/start", json={"parent_id": latest["id"]})
                assert next_revision.status_code == 201
                latest = next_revision.json()
        history = client.get(f"{url}/revisions").json()
        assert history["retry_limit"] == 3 and history["remaining"] == 0
        assert [item["band"] for item in history["items"]] == [7.5, 9.0, 9.0, 9.0]
        assert client.post(f"{prefix}/writing/start", json={"parent_id": latest["id"]}).status_code == 409
        assert client.delete(url).status_code == 204
        assert client.get(url).status_code == 404
        remaining_history = client.get(f"{prefix}/sessions/{latest['id']}/revisions").json()
        assert [item["number"] for item in remaining_history["items"]] == [1, 2, 3]
        assert remaining_history["remaining"] == 0

        listening = client.post(f"{prefix}/listening/start", json={
            "video_id": "I3cl8kj80Zw", "simulate": True,
        }).json()
        listening_url = f"{prefix}/sessions/{listening['id']}"
        listening_work = {"answers": {"1": " TRANSPORT ", "2": "incorrect"}}
        paused = client.post(f"{listening_url}/pause", json=listening_work).json()
        duration = datetime.fromisoformat(paused["deadline"]) - datetime.fromisoformat(paused["paused_at"])
        assert 1790 <= duration.total_seconds() <= 1800
        group = listening["content"]["simulation_id"]
        reading_request = {"simulation_id": group, "reading_job_id": generation}
        assert client.post(f"{prefix}/reading/start", json=reading_request).status_code == 409
        marks = {"correct": [True, False] + [True] * 25 + [False] * 13}
        assert client.post(f"{listening_url}/listening-score", json=marks).status_code == 409
        client.post(f"{listening_url}/resume")
        client.post(f"{listening_url}/submit", json=listening_work)
        assert client.post(f"{prefix}/reading/start", json=reading_request).status_code == 409
        assert client.post(f"{listening_url}/listening-score", json={"correct": [True]}).status_code == 422
        scored = client.post(f"{listening_url}/listening-score", json=marks).json()
        assert (scored["result"]["score"], scored["result"]["maximum"]) == (26, 40)
        assert scored["result"]["items"][0]["status"] == "correct"
        assert scored["result"]["items"][1]["status"] == "incorrect"
        assert scored["result"]["band"] == 6.5 and scored["result"]["band_estimated"]
        assert client.get(listening_url).json()["result"] == scored["result"]
        listing = client.get(f"{prefix}/sessions").json()["items"]
        listening_history = next(item for item in listing if item["id"] == listening["id"])
        assert listening_history["band"] == 6.5 and listening_history["band_estimated"]
        estimate = client.get("/api/v1/dashboard").json()["estimates"]["modules"]["listening"]
        assert estimate == {"value": 6.5, "unit": "band", "count": 1, "estimated": True, "raw_average": 26.0}
        reading_section = client.post(f"{prefix}/reading/start", json=reading_request).json()
        assert client.post(f"{prefix}/reading/start", json=reading_request).json()["id"] == reading_section["id"]
        client.post(f"{prefix}/sessions/{reading_section['id']}/submit", json={})
        writing_section = client.post(f"{prefix}/writing/start", json={"simulation_id": group, "task": "full"}).json()
        assert writing_section["content"]["task"] == "full"
        sections = client.get(f"{prefix}/simulation/{group}").json()["items"]
        assert [item["module"] for item in sections] == ["listening", "reading", "writing"]
        assert sections[0]["band"] == 6.5 and sections[0]["band_estimated"]
        assert client.delete(f"{prefix}/sessions/{writing_section['id']}").status_code == 204
        assert client.get(f"{prefix}/sessions/{writing_section['id']}").status_code == 404
        assert client.delete(listening_url).status_code == 204
        assert client.get(listening_url).status_code == 404
        assert "listening" not in client.get("/api/v1/dashboard").json()["estimates"]["modules"]
        assert listening["id"] not in {entry["id"] for entry in client.get(f"{prefix}/sessions").json()["items"]}
        assert client.delete(f"{prefix}/reading/mocks/{generation}").status_code == 409
        draft = client.post(f"{prefix}/reading/start", json={"reading_job_id": second_generation}).json()
        assert client.delete(f"{prefix}/reading/mocks/{second_generation}").status_code == 204
        assert client.get(f"/api/v1/jobs/{second_generation}").status_code == 404
        assert client.get(f"{prefix}/sessions/{draft['id']}").status_code == 200
        assert client.post(f"{prefix}/reading/start", json={"reading_job_id": second_generation}).status_code == 409
        assert [item["id"] for item in client.get(f"{prefix}/reading/mocks").json()["items"]] == [generation]

        def rate_limited(*, used_ids, used_titles, used_references, report_progress):
            assert used_ids == {1, 2, 3, 101, 102, 103}
            assert "New source 1" in used_titles
            raise WikipediaBusy(120)

        monkeypatch.setattr(worker, "generate_reading", rate_limited)
        limited_id = client.post(f"{prefix}/reading/generate").json()["job_id"]
        assert worker.run_once()
        limited = client.get(f"/api/v1/jobs/{limited_id}").json()
        assert limited["state"] == "queued"
        assert "Wikipedia is rate-limiting" in limited["error"]
        assert "UTC" not in limited["error"]
        assert datetime.fromisoformat(limited["retry_at"]).tzinfo is not None
        new_id = client.post(f"{prefix}/reading/generate").json()["job_id"]
        assert client.get(f"/api/v1/jobs/{new_id}").json()["error"] == limited["error"]
        assert not worker.run_once()

        writing_topics = client.get(f"{prefix}/writing/topics").json()
        writing_categories = writing_topics["categories"]
        assert writing_categories == sorted(set(writing_categories))
        assert len(writing_categories) == 20
        assert {group["name"] for group in groups} <= set(writing_categories)
        selected = client.post(f"{prefix}/writing/start", json={
            "task": "full", "mode": "learning",
            "writing_topics": {"1": "adult-education", "2": "digital-privacy"},
        })
        assert selected.status_code == 201
        content = selected.json()["content"]
        assert content["mode"] == "learning"
        assert [task["topic"] for task in content["tasks"]] == ["adult-education", "digital-privacy"]
        assert content["tasks"][0]["table"][0][0] == "Course"
        assert "personalise" in content["tasks"][1]["prompt"]
        assert client.post(f"{prefix}/writing/start", json={
            "task": 1, "writing_topics": {"1": "digital-privacy"},
        }).status_code == 422
        assert client.post(f"{prefix}/writing/start", json={
            "task": 2, "writing_topics": {"1": "adult-education"},
        }).status_code == 422

        def generate_prompt(instructions, material, output_model, **options):
            if output_model is practice_ai.WritingReferenceDraft:
                assert material["task"]["task"] == 1
                return writing_reference()
            if output_model is practice_ai.WritingChartDraft:
                assert material["category"] == "Education and learning"
                return {
                    "title": "Adult courses by subject" if "following visual: table" in instructions else "Adult education participation",
                    "measure": "the percentage of adults taking courses in each subject",
                    "years": ["2015", "2025"], "series": [
                        {"label": "Languages", "values": [25, 35]}, {"label": "Digital skills", "values": [20, 45]},
                        {"label": "Business", "values": [12, 29]},
                    ],
                }
            assert output_model is practice_ai.WritingEssayDraft and material["category"] == "Media and advertising"
            return {"title": "Advertising to children", "scenario": "Children see advertisements on television and online.",
                    "question": "Should governments set stricter limits on advertisements aimed at children?"}

        monkeypatch.setattr(practice_ai, "generate", generate_prompt)
        assert set(practice_ai.WRITING_VISUAL_PLANS) == {"bar", "line", "pie", "table", "bar_table", "bar_line"}
        monkeypatch.setattr(practice_ai, "WRITING_VISUAL_PLANS", {"bar": ((3, 2),), "table": ((3, 2),)})
        monkeypatch.setattr(practice_ai, "choice", lambda choices: choices[0])
        generation_url = f"{prefix}/writing/generate"
        configuration = {"task": "full", "mode": "learning",
                         "categories": {"1": "Education and learning", "2": "Media and advertising"}}
        generated = client.post(generation_url, json=configuration)
        assert generated.status_code == 202
        job_id = generated.json()["job_id"]
        assert client.post(generation_url, json=configuration).json()["job_id"] == job_id
        assert client.post(generation_url, json={**configuration, "task": 1}).status_code == 422
        assert client.post(generation_url, json={**configuration, "categories": {"2": "Imaginary"}}).status_code == 422
        start_payload = {"writing_job_id": job_id}
        assert client.post(f"{prefix}/writing/start", json=start_payload).status_code == 409
        assert worker.run_once()
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        assert status["state"] == "succeeded"
        assert status["result"] is None
        started = client.post(f"{prefix}/writing/start", json=start_payload).json()
        assert client.post(f"{prefix}/writing/start", json=start_payload).json()["id"] == started["id"]
        content = started["content"]
        assert content["mode"] == "learning"
        assert [task["category"] for task in content["tasks"]] == ["Education and learning", "Media and advertising"]
        assert content["tasks"][0]["chart"]["synthetic"] is True
        assert "reference_analysis" not in content["tasks"][0]
        assert "reference_analysis" not in client.get(f"{prefix}/sessions/{started['id']}").json()["content"]["tasks"][0]
        assert "2015 and 2025" in content["tasks"][0]["prompt"]
        assert "at least 250 words" in content["tasks"][1]["prompt"]
        submitted_generated = client.post(f"{prefix}/sessions/{started['id']}/submit", json={}).json()
        assert submitted_generated["content"]["tasks"][0]["reference_analysis"]["synthetic_data"] is True
        assert worker.run_once()
        retry = client.post(f"{prefix}/writing/start", json={"parent_id": started["id"]}).json()
        assert "reference_analysis" not in retry["content"]["tasks"][0]
        next_job = client.post(generation_url, json={
            "task": 1, "categories": {"1": "Education and learning"},
        }).json()["job_id"]
        assert worker.run_once()
        table = client.post(f"{prefix}/writing/start", json={"writing_job_id": next_job}).json()["content"]
        assert table["visual_kind"] == "table"
        assert table["table"][1] == ["Languages", "25%", "35%"]

        with sessions.begin() as session:
            original = session.get(Job, UUID(next_job))
            legacy = Job(learner_id=original.learner_id, kind="writing_prompt", state="succeeded",
                         deduplication_key="legacy-process", available_at=datetime.now(UTC),
                         payload={"task": 1}, result={
                             "task": 1, "title": "Course enrolment", "visual_kind": "process",
                             "process": ["Choose a course", "Apply", "Pay", "Attend"],
                         })
            session.add(legacy)
            session.flush()
            legacy_id = str(legacy.id)
        assert client.get(f"/api/v1/jobs/{legacy_id}").json()["replacement_required"] is True
        assert client.post(f"{prefix}/writing/start", json={"writing_job_id": legacy_id}).status_code == 409
    engine.dispose()


@pytest.mark.parametrize(("kind", "unit", "years", "values", "display"), [
    ("line", "%", ["2000", "2005", "2010", "2015"], [[15, 30, 26, 45]], "line graph"),
    ("pie", "%", ["2000", "2010", "2020"], [[25, 35, 50], [40, 40, 30], [35, 25, 20]], "pie charts"),
    ("table", "count", ["2000", "2005", "2010"], [[1500, 2500, 3600], [40, 50, 20], [35, 10, 60]], "table"),
    ("bar_table", "count", ["2000", "2010"], [[60, 20], [30, 40], [10, 140]], "bar chart"),
    ("bar_line", "count", ["2000", "2010"], [[60, 20], [30, 40], [10, 140]], "bar chart"),
])
def test_writing_task_one_visual_formats(monkeypatch, kind, unit, years, values, display):
    monkeypatch.setattr(practice_ai, "WRITING_VISUAL_PLANS", {kind: ((len(values), len(years)),)})
    monkeypatch.setattr(practice_ai, "choice", lambda choices: unit if choices == ("%", "count") else choices[0])
    requests = []

    def generate(instructions, material, output_model, **options):
        if output_model is practice_ai.WritingReferenceDraft:
            assert material["task"]["visual_kind"] == kind
            return writing_reference()
        requests.append(material.get("revision_instruction"))
        series = [{"label": f"Group {number}", "values": row[:]} for number, row in enumerate(values)]
        if kind == "pie" and len(requests) == 1:
            series[0]["values"][0] += 1
        return {"title": "Participation", "measure": "participation across groups", "years": years, "series": series}

    monkeypatch.setattr(practice_ai, "generate", generate)
    task = practice_ai.generate_writing_prompt(1, "Education and learning", [])
    assert task["visual_kind"] == kind
    assert task["reference_analysis"]["synthetic_data"] is True
    assert task["minimum_words"] == 150
    assert f"The {display} below" in task["prompt"]
    if kind == "table":
        assert task["table"][0] == ["Group", *years]
        assert task["table"][1][1:] == [f"{value:,}" for value in values[0]]
    else:
        assert task["chart"]["years"] == years
        assert task["chart"]["unit"] == unit
        assert [row["values"] for row in task["chart"]["series"]] == values
    if kind == "pie":
        assert "sum to 100 in every year" in requests[1]
    if kind == "bar_table":
        assert "percentage share of the total" in task["prompt"]
        assert task["table"] == [
            ["Group", "2000", "2010"], ["Group 0", "60.0%", "10.0%"], ["Group 1", "30.0%", "20.0%"],
            ["Group 2", "10.0%", "70.0%"],
        ]
    if kind == "bar_line":
        assert task["comparison_chart"]["series"][0]["values"] == [60, 10]


def test_reading_stops_starting_model_calls_at_generation_deadline(monkeypatch):
    monkeypatch.setattr(practice_ai, "wikipedia_sources", lambda *_args, **_kwargs: [{"title": "Source"}] * 3)
    times = iter([0])
    monkeypatch.setattr(practice_ai, "monotonic", lambda: next(times, 601))

    def unexpected_call(*args, **kwargs):
        pytest.fail("A model call started after the generation deadline.")

    monkeypatch.setattr(practice_ai, "generate", unexpected_call)
    with pytest.raises(practice_ai.ReadingGenerationTimeout, match="exceeded 10 minutes"):
        practice_ai.generate_reading()


def test_writing_feedback_keeps_topic_specific_examples(monkeypatch):
    examples = [
        {"type": "opening_paraphrase", "text": "Many towns are reconsidering the role of public libraries."},
        {"type": "argument", "text": "Free library access helps residents study and apply for work."},
        {"type": "qualification", "text": "These benefits depend on libraries being accessible outside working hours."},
    ]
    criterion = {"band": 6.5, "feedback": "Explain the benefit in more detail.", "quote": ""}

    def evaluate(instructions, material, schema):
        assert material["prompt"]["title"] == "Libraries"
        return {**{key: criterion for key in ("task", "coherence", "vocabulary", "grammar")},
                "revision_plan": {"plan": ["Clarify your position."], "develop": ["Explain one benefit."],
                                  "check": ["Read the final paragraph."], "examples": examples}}

    monkeypatch.setattr(practice_ai, "generate", evaluate)
    feedback = practice_ai.assess_writing({"task": 2, "title": "Libraries"}, "Local libraries are useful.")
    assert feedback["revision_plan"]["examples"] == examples
    examples[1]["type"] = examples[0]["type"]
    with pytest.raises(ValueError, match="distinct sentences and writing purposes"):
        practice_ai.assess_writing({"task": 2, "title": "Libraries"}, "Local libraries are useful.")


def test_reading_multiple_choice_requires_an_analysis_per_distractor(monkeypatch):
    text = practice_ai.ReadingTextDraft(title="Transit", text="Few residents take the bus. " + "word " * 745)
    trials = []

    def generate(instructions, material, schema, **options):
        trials.append(material.get("revision_instruction"))
        assert "scope (some vs all)" in instructions
        analyses = [{"option_text": option, "flaw": "The passage limits this claim to a small group."}
                    for option in ("All residents", "No residents", "Most residents")]
        return {"shared_options": [], "word_limit": None, "items": [{
            "prompt": "How common is bus use?", "options": ["A. Few residents", "B. All residents", "C. No residents", "D. Most residents"],
            "answers": ["A. Few residents"], "explanation": "The passage explicitly refers to a small group.",
            "evidence": "Few residents take the bus.",
            "assessment": {**READING_ASSESSMENT, "distractor_analysis": analyses if trials[-1] else analyses[:2]},
        }]}

    monkeypatch.setattr(practice_ai, "generate", generate)
    question = practice_ai.generate_reading_group(2, text, "multiple_choice", 1)[0]
    assert len(question.assessment.distractor_analysis) == 3
    assert "flaw for each" in trials[1]


def test_wikipedia_draw_filters_previously_used_sources(monkeypatch):
    candidates = {1: "Old ID", 2: "Previously used", 3: "First fresh", 4: "Second fresh", 5: "Third fresh"}

    def query(**params):
        if params.get("list") == "categorymembers":
            assert params["cmtitle"] == "Category:Renewable energy"
            return {"categorymembers": [
                {"pageid": key, "title": title, "ns": 0} for key, title in candidates.items()
            ]}
        page_ids = [int(value) for value in str(params["pageids"]).split("|")]
        assert set(page_ids).isdisjoint({1, 2})
        return {"pages": [
            {"pageid": key, "title": candidates[key], "extract": "text " * 300, "lastrevid": key + 100}
            for key in page_ids
        ]}

    monkeypatch.setattr(practice_ai, "wikipedia_query", query)
    monkeypatch.setattr(practice_ai, "wikipedia_rights", lambda: {"text": "CC BY-SA", "url": "license"})
    sources = practice_ai.wikipedia_sources("renewable-energy", used_ids={1}, used_titles={"Previously_used"})
    assert {source["page_id"] for source in sources} == {3, 4, 5}


def test_reading_choice_matches_visible_option():
    question = ReadingQuestion(
        type="matching_headings", prompt="Choose the heading.", options=["i. Origins", "ii. Growth"],
        answers=["II"], evidence="Growth", explanation="The paragraph explains growth.", word_limit=None,
    )
    assert canonical_choice(question) == "ii. Growth"
    question.answers = ["Unknown option"]
    with pytest.raises(ValueError, match="exactly one listed option"):
        canonical_choice(question)


def test_reading_choices_shuffle_the_stored_answer_with_the_option(monkeypatch):
    monkeypatch.setattr(practice_ai, "shuffle", lambda options: options.reverse())
    question = ReadingQuestion(
        type="multiple_choice", prompt="Which is correct?", options=["A. First", "B. Second", "C. Third", "D. Fourth"],
        answers=["A. First"], evidence="First", explanation="The passage mentions the first option.", word_limit=None,
    )
    practice_ai.shuffle_multiple_choice(question)
    assert question.options == ["A. Fourth", "B. Third", "C. Second", "D. First"]
    assert question.answers == ["D. First"]


@pytest.mark.parametrize(("raw", "expected"), [(40, 9.0), (39, 9.0), (38, 8.5), (30, 7.0), (29, 6.5), (4, 2.5)])
def test_academic_reading_practice_band(raw, expected):
    result = {"kind": "reading_raw", "score": raw, "maximum": 40}
    assert practice_band_fields(result) == {"band": expected, "band_estimated": True}


@pytest.mark.parametrize(("raw", "band_field"), [
    (40, {"band": 9.0}), (38, {"band": 8.5}), (32, {"band": 7.5}),
    (11, {"band": 4.0}), (10, {"band_upper_bound": 4.0}), (0, {"band_upper_bound": 4.0}),
])
def test_listening_self_score_practice_band(raw, band_field):
    result = {"kind": "listening_self_scored", "score": raw, "maximum": 40}
    assert practice_band_fields(result) == {"band_estimated": True, **band_field}
    assert practice_band_fields({**result, "maximum": 30}) == {}


def test_every_publisher_has_fresh_reference_options(monkeypatch):
    monkeypatch.setattr(reading_sources, "publisher_headlines", lambda *_: [])
    for publisher in reading_sources.PUBLISHERS:
        first = reading_sources.publisher_sources(publisher, None, set())
        used = {item["reference_id"] for item in first}
        second = reading_sources.publisher_sources(publisher, None, used)
        assert len(first) == len(second) == 3
        assert used.isdisjoint(item["reference_id"] for item in second)
        homepage = reading_sources.reference_url_key(reading_sources.PUBLISHERS[publisher][1])
        assert all(item["url"].startswith("https://") and reading_sources.reference_url_key(item["url"]) != homepage
                   for item in first + second)


def test_publisher_feed_uses_full_article_url_and_skips_homepage(monkeypatch):
    rss = b"""<rss><channel>
      <item><title>Homepage</title><link>https://www.nasa.gov/</link></item>
      <item><title>Launch update</title><link>https://www.nasa.gov/news/launch/?ref=feed#update</link></item>
    </channel></rss>"""
    monkeypatch.setattr(reading_sources, "urlopen", lambda *_args, **_kwargs: BytesIO(rss))
    headlines = reading_sources.publisher_headlines("nasa", None, set())
    assert [item["url"] for item in headlines] == ["https://www.nasa.gov/news/launch/?ref=feed#update"]
    assert reading_sources.publisher_headlines("nasa", None, {headlines[0]["reference_id"]}) == []


def test_model_rate_limit_and_quota_are_distinct(monkeypatch):
    for name in ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
        monkeypatch.setenv(name, "test")

    def reject(code):
        def request(*args, **kwargs):
            body = BytesIO(f'{{"error": {{"code": "{code}"}}}}'.encode())
            raise HTTPError("https://example.test", 429, "Too Many Requests", {"Retry-After": "27"}, body)
        return request

    monkeypatch.setattr(practice_ai, "request_json", reject("rate_limit_exceeded"))
    with pytest.raises(practice_ai.ModelBusy) as error:
        practice_ai.generate("test", {}, ReadingQuestion)
    assert error.value.retry_after == 27
    monkeypatch.setattr(practice_ai, "request_json", reject("insufficient_quota"))
    with pytest.raises(practice_ai.ModelQuotaExhausted):
        practice_ai.generate("test", {}, ReadingQuestion)
    monkeypatch.setattr(practice_ai, "request_json", reject("credit_balance_exhausted"))
    with pytest.raises(practice_ai.ModelQuotaExhausted, match="credit balance is exhausted"):
        practice_ai.generate("test", {}, ReadingQuestion)


@pytest.mark.parametrize("api_style", ["chat", "responses"])
def test_model_request_includes_configured_reasoning(monkeypatch, api_style):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test")
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setenv("LLM_MODEL", "gpt-6-luna")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "max" if api_style == "responses" else "xhigh")
    monkeypatch.setenv("LLM_API_STYLE", api_style)

    def request(url, *, headers, payload, timeout):
        assert payload["model"] == "gpt-6-luna"
        if api_style == "responses":
            assert url.endswith("/responses")
            assert payload["reasoning"] == {"effort": "max"}
            assert payload["text"]["format"]["type"] == "json_schema"
            assert payload["max_output_tokens"] == 6500
            return {"status": "completed", "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "content": [{"type": "output_text", "text": "{}"}]},
            ]}
        assert url.endswith("/chat/completions")
        assert payload["reasoning_effort"] == "xhigh"
        assert payload["max_completion_tokens"] == 6500
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr(practice_ai, "request_json", request)
    assert practice_ai.generate("test", {}, ReadingQuestion, completion_limit=6500) == {}


def test_reading_generation_splits_truncated_text_and_question_groups(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "xhigh")
    monkeypatch.setattr(practice_ai, "reading_plan", lambda _: (("true_false_not_given", 7), ("completion", 6)))
    text_calls = []
    group_calls = []

    def generate(instructions, material, output_model, *, completion_limit, timeout):
        assert timeout == 240
        if output_model is practice_ai.ReadingTextDraft:
            text_calls.append(completion_limit)
            if len(text_calls) <= 2:
                raise practice_ai.ModelOutputLimit()
            if len(text_calls) == 4:
                assert material["previous_text"] == "word " * 375
            return {"title": "Example", "text": "word " * 375}

        count = material["batch_count"]
        previous = material["previous_items"]
        group_calls.append((count, len(previous), completion_limit))
        if count == 6 and not previous:
            raise practice_ai.ModelOutputLimit()
        verdict = count == 7
        assert len(material["passage"].split()) == 750
        if previous:
            assert [item["prompt"] for item in previous] == [f"Item {index} contains ___." for index in range(3)]
            assert material["word_limit"] == 1
        return {"shared_options": [], "word_limit": None if verdict else 1, "items": [{
            "prompt": f"Claim {index}." if verdict else f"Item {index} contains ___.",
            "options": [], "answers": ["True" if verdict else "word"],
            "evidence": "word", "explanation": "The passage identifies it.", "assessment": READING_ASSESSMENT,
        } for index in range(len(previous), len(previous) + count)]}

    monkeypatch.setattr(practice_ai, "generate", generate)
    passage = practice_ai.generate_reading_passage(0, {"title": "Source"})
    assert len(passage["questions"]) == 13
    assert passage["questions"][0]["assessment"]["evidence_spans"] == [{"start": 0, "end": 4, "text": "word"}]
    assert [(group["start"], group["count"]) for group in passage["question_groups"]] == [(0, 7), (7, 6)]
    assert text_calls == [16384, 16384, 24576, 16384]
    assert group_calls == [(7, 0, 16384), (6, 0, 16384), (3, 0, 16384), (3, 3, 16384)]


@pytest.mark.parametrize("rejected_length", [680, 935])
def test_reading_passage_splits_after_repeated_length_errors(monkeypatch, rejected_length):
    calls = []

    def generate(instructions, material, output_model, **options):
        calls.append(material.copy())
        if len(calls) <= 2:
            if len(calls) == 2:
                assert f"Got {rejected_length} words" in material["revision_instruction"]
            return {"title": "Example", "text": "word " * rejected_length}
        if len(calls) == 3:
            assert "opening half" in instructions
            labels, paragraph_length = "ABCD", 86
        else:
            assert "386–546 words" in instructions
            assert material["previous_text"].startswith("A. ")
            labels, paragraph_length = "EFGH", 114
        text = "\n\n".join(f"{label}. " + "word " * (paragraph_length - 1) for label in labels)
        return {"title": "Example", "text": text}

    monkeypatch.setattr(practice_ai, "generate", generate)
    passage = practice_ai.generate_reading_text(1, {"title": "Source"}, (("matching_headings", 6),))
    assert len(calls) == 4
    assert len(passage.text.split()) == 800
    assert [line[0] for line in passage.text.splitlines() if line] == list("ABCDEFGH")


@pytest.mark.parametrize("invalid_evidence", [False, True])
def test_reading_matching_batches_keep_one_shared_bank(monkeypatch, invalid_evidence):
    options = ["i. First subject", "ii. Second subject", "iii. Extra heading"]
    text = practice_ai.ReadingTextDraft(title="Example", text="A. First fact.\n\nB. Second fact. " + "word " * 745)
    calls = []

    def generate(instructions, material, output_model, **kwargs):
        count = material["batch_count"]
        calls.append(count)
        if count == 2 and not invalid_evidence:
            raise practice_ai.ModelOutputLimit()
        if count == 2:
            return {"shared_options": options, "word_limit": None, "items": [{
                "prompt": f"Paragraph {letter}", "options": [],
                "answers": [answer], "evidence": "This quote was invented.",
                "explanation": "The heading captures the main idea.", "assessment": READING_ASSESSMENT,
            } for letter, answer in zip("AB", options)]}
        second = bool(material["previous_items"])
        assert material["shared_options"] == (options if second else [])
        return {"shared_options": options, "word_limit": None, "items": [{
            "prompt": "Paragraph B" if second else "Paragraph A", "options": [],
            "answers": [options[int(second)]], "evidence": "Second fact." if second else "First fact.",
            "explanation": "The heading captures the main idea.", "assessment": READING_ASSESSMENT,
        }]}

    monkeypatch.setattr(practice_ai, "generate", generate)
    items = practice_ai.generate_reading_group(1, text, "matching_headings", 2)
    assert calls == ([2, 2, 1, 1] if invalid_evidence else [2, 1, 1])
    assert [item.answers[0] for item in items] == options[:2]
    assert all(item.options == options for item in items)


def test_reading_evidence_recovers_only_a_contiguous_quote():
    text = "The city’s early records\n  describe the water‐supply network."
    assert practice_ai.exact_reading_evidence(text, "city's early records describe the water-supply") == (
        "city’s early records\n  describe the water‐supply"
    )
    assert practice_ai.exact_reading_evidence(text, "records describe the electricity network") is None
    assert practice_ai.exact_reading_evidence(text, "records … the water-supply") is None


def test_reading_group_validation_rejects_unrelated_options_and_wrong_evidence_order():
    passage = practice_ai.Passage(
        title="Sample", text="A. First fact.\n\nB. Second fact. " + "word " * 745,
        questions=[
            ReadingQuestion(type="matching_information", prompt="The opening observation.", options=["A", "C"],
                            answers=["A"], explanation="It appears in A.", evidence="First fact.", word_limit=None),
        ],
    )
    with pytest.raises(ValueError, match="Paragraph options"):
        practice_ai.validate_reading_passage(passage, (("matching_information", 1),))

    passage.questions = [
        ReadingQuestion(type="short_answer", prompt=f"Which fact is {answer.lower()}?", options=[],
                        answers=[answer], explanation="This detail is stated.", evidence=f"{answer} fact.", word_limit=1)
        for answer in ("Second", "First")
    ]
    with pytest.raises(ValueError, match="passage order"):
        practice_ai.validate_reading_passage(passage, (("short_answer", 2),))
