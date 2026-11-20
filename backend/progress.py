from math import floor
from statistics import mean

from sqlalchemy import String, and_, cast, or_, select

from backend.practice_models import PracticeSession

RECENT_ATTEMPTS = 5
# IDP's Academic Reading reference ranges stop at four correct answers.
READING_BAND_THRESHOLDS = (
    (39, 9.0), (37, 8.5), (35, 8.0), (33, 7.5), (30, 7.0),
    (27, 6.5), (23, 6.0), (19, 5.5), (15, 5.0), (13, 4.5),
    (10, 4.0), (8, 3.5), (6, 3.0), (4, 2.5),
)


# IDP's Listening reference ranges stop at eleven correct answers.
LISTENING_BAND_THRESHOLDS = (
    (39, 9.0), (37, 8.5), (35, 8.0), (32, 7.5), (30, 7.0),
    (26, 6.5), (23, 6.0), (18, 5.5), (16, 5.0), (13, 4.5), (11, 4.0),
)
PRACTICE_BAND_THRESHOLDS = {
    "reading_raw": READING_BAND_THRESHOLDS,
    "listening_self_scored": LISTENING_BAND_THRESHOLDS,
}


def practice_band_fields(result):
    if not result or result.get("maximum") != 40:
        return {}
    thresholds = PRACTICE_BAND_THRESHOLDS.get(result.get("kind"))
    if not thresholds:
        return {}
    score = result["score"]
    for minimum, band in thresholds:
        if score >= minimum:
            return {"band": band, "band_estimated": True}
    return {"band_upper_bound": thresholds[-1][1], "band_estimated": True}


def round_band(value):
    return floor(value * 2 + 0.5) / 2


def dashboard_estimates(session, learner_id):
    result = PracticeSession.result
    base = (
        select(result)
        .where(PracticeSession.learner_id == learner_id, PracticeSession.submitted_at.is_not(None),
               PracticeSession.deleted_at.is_(None))
        .order_by(PracticeSession.submitted_at.desc(), PracticeSession.id)
        .limit(RECENT_ATTEMPTS)
    )

    def recent(module, kind, *conditions):
        return list(session.scalars(base.where(
            PracticeSession.module == module, result["kind"].as_string() == kind, *conditions,
        )))

    bands = {}
    estimates = {}
    for module in ("listening", "reading"):
        scores = recent(module, f"{module}_calibrated", result["calibration_id"].as_string().is_not(None))
        if scores:
            bands[module] = mean(score["band"] for score in scores)
            estimates[module] = {"value": round_band(bands[module]), "unit": "band", "count": len(scores)}

    for module, kind in (("reading", "reading_raw"), ("listening", "listening_self_scored")):
        if module not in estimates:
            scores = recent(module, kind, result["maximum"].as_integer() == 40)
            if scores:
                raw_average = round(mean(score["score"] for score in scores), 1)
                practice_bands = [practice_band_fields(score).get("band") for score in scores]
                if all(band is not None for band in practice_bands):
                    bands[module] = mean(practice_bands)
                    estimates[module] = {"value": round_band(bands[module]), "unit": "band", "count": len(scores),
                                         "estimated": True, "raw_average": raw_average}
                else:
                    estimates[module] = {"value": raw_average, "unit": "raw_40", "count": len(scores)}

    writing_tasks = []
    writing_ids = set()
    for task in (1, 2):
        rows = list(session.execute(base.add_columns(PracticeSession.id).where(
            PracticeSession.module == "writing",
            or_(PracticeSession.content["mode"].as_string().is_(None),
                PracticeSession.content["mode"].as_string() == "exam"),
            or_(
                result["kind"].as_string() == "unofficial_full_writing_estimate",
                and_(result["kind"].as_string() == "unofficial_writing_estimate",
                     cast(PracticeSession.content["task"].as_string(), String) == str(task)),
            ),
        )))
        if rows:
            bands_for_task = []
            for score, attempt_id in rows:
                feedback = score["tasks"][task - 1] if "tasks" in score else score
                bands_for_task.append(feedback.get("criterion_average", feedback["band"]))
                writing_ids.add(attempt_id)
            writing_tasks.append({"task": task, "average": mean(bands_for_task), "count": len(rows)})
    if len(writing_tasks) == 2:
        task1, task2 = writing_tasks
        bands["writing"] = (task1["average"] + 2 * task2["average"]) / 3
        estimates["writing"] = {"value": round_band(bands["writing"]), "unit": "band",
                                "count": len(writing_ids)}
    elif writing_tasks:
        task = writing_tasks[0]
        estimates["writing"] = {"value": round_band(task["average"]), "unit": "band",
                                "task": task["task"], "count": task["count"]}

    required = ("listening", "reading", "writing")
    return {
        "overall": round_band(mean(bands.values())) if len(bands) == len(required) else None,
        "missing": [module for module in required if module not in bands],
        "modules": estimates,
        "sample_limit": RECENT_ATTEMPTS,
    }
