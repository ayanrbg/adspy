import asyncio
import re

from adspy.workers.celery_app import app
from adspy.config.searches import SEARCHES
from adspy.sources.registry import SOURCE_REGISTRY
from adspy.pipeline.processor import Pipeline
from adspy.pipeline.steps import (
    DeduplicateStep, DownloadCreativeStep,
    OCRStep, GeminiClassifyStep,
    SignalsStep, SnowballStep, SaveStep,
)

pipeline = Pipeline([
    DeduplicateStep(),
    DownloadCreativeStep(),
    OCRStep(),
    GeminiClassifyStep(),
    SignalsStep(),
    SnowballStep(),
    SaveStep(),
])


def parse_schedule(schedule_str: str) -> float:
    """Parse schedule string like '*/6 hours' into seconds."""
    match = re.match(r"\*/(\d+)\s*(hours?|minutes?|seconds?)", schedule_str)
    if not match:
        return 6 * 3600  # default 6 hours
    value = int(match.group(1))
    unit = match.group(2)
    if unit.startswith("hour"):
        return value * 3600
    elif unit.startswith("minute"):
        return value * 60
    return value


@app.task
def run_search(search_id: str):
    cfg = next(s for s in SEARCHES if s["id"] == search_id)

    all_ads = []
    for source_name in cfg["sources"]:
        source = SOURCE_REGISTRY[source_name]
        ads = asyncio.run(source.fetch(cfg))
        all_ads.extend(ads)

    asyncio.run(pipeline.run(all_ads))
    print(f"[{search_id}] done: {len(all_ads)} collected")


app.conf.beat_schedule = {
    s["id"]: {
        "task": "adspy.workers.tasks.run_search",
        "schedule": parse_schedule(s["schedule"]),
        "args": [s["id"]],
    }
    for s in SEARCHES if s["enabled"]
}
