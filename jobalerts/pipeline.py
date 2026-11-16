"""Runs the whole job-alert pipeline once:
fetch → rule filter → dedupe → description → extract → verify → decide → notify."""
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from jobalerts import notifier
from jobalerts.decide import Decision, decide
from jobalerts.dedupe import fingerprint, split_new
from jobalerts.extract import extract, verify
from jobalerts.filters import is_bay_area, is_early_career, passes_rule_filter
from jobalerts.models import Job
from jobalerts.sources import ashby, greenhouse, lever

COMPANIES_FILE = Path(__file__).parent.parent / "companies.yaml"
SOURCES = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}
ALERT_CHANNELS = {"apply_now", "maybe"}
DAILY_LLM_LIMIT = int(os.getenv("DAILY_LLM_LIMIT", "50"))
NOT_ANALYZED = "⚡ Not analyzed: today's LLM budget is used up. Check the posting yourself."


def load_companies() -> list[dict]:
    return yaml.safe_load(COMPANIES_FILE.read_text())["companies"]


FAVORITES = {(company["source"], company["slug"]) for company in load_companies()}


def today_pacific() -> str:
    """The budget resets at midnight Pacific time."""
    return datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()


def priority(job: Job) -> tuple[bool, bool]:
    """Sort key: early-career titles first, then favorites. (False sorts before True.)"""
    return (not is_early_career(job.title), (job.source, job.board) not in FAVORITES)


def fetch_kept_jobs(counts: Counter) -> list[Job]:
    """Fetches every company's jobs and keeps the ones passing the rule filter."""
    kept = []
    for company in load_companies():
        name = f"{company['source']}/{company['slug']}"
        try:
            jobs = SOURCES[company["source"]].fetch_jobs(company["slug"])
        except Exception as error:  # one broken company shouldn't stop the whole run
            print(f"! could not fetch {name}: {error}")
            counts["fetch_errors"] += 1
            continue
        kept += [job for job in jobs if passes_rule_filter(job)]
    return kept


def fill_description(job: Job) -> None:
    """Greenhouse lists have no descriptions, so fetch them for new jobs only."""
    if job.source == "greenhouse" and not job.description:
        try:
            job.description = greenhouse.fetch_description(job.board, job.job_id)
        except Exception as error:
            print(f"! no description for {job.title} @ {job.company}: {error}")


def send_not_analyzed(job: Job, store) -> None:
    """Over budget: alert right away without the LLM, so nothing is delayed or lost."""
    tags = ["⭐ Bay Area"] if is_bay_area(job.location) else []
    decision = Decision(channel="maybe", reason=NOT_ANALYZED, tags=tags)
    store.save_decision(job, decision)
    notifier.send(job, "maybe", decision.reason, decision.tags)


def run(store, baseline: bool = False, limit: int = 10) -> Counter:
    counts = Counter()
    kept = fetch_kept_jobs(counts)

    # First real run: remember everything open now, alert on nothing
    if baseline:
        for job in kept:
            store.add_key(job.key)
        store.save()
        counts["marked_seen"] = len(kept)
        return counts

    # Unseen jobs, most important first, capped per run (the rest wait for the next run)
    fresh = sorted((job for job in kept if not store.has_key(job.key)), key=priority)[:limit]
    for job in fresh:
        fill_description(job)
    new_jobs, copies = split_new(fresh, store)

    for job in new_jobs:
        if not store.reserve_llm_call(today_pacific(), DAILY_LLM_LIMIT):
            send_not_analyzed(job, store)
            counts["not_analyzed"] += 1
            continue
        try:
            facts = verify(extract(job), job)
        except Exception as error:
            print(f"! LLM failed for {job.title} @ {job.company}: {error}")
            store.forget(job.key, fingerprint(job))  # retry next run
            counts["llm_errors"] += 1
            continue
        decision = decide(facts, job)
        store.save_decision(job, decision)
        if decision.channel in ALERT_CHANNELS:
            notifier.send(job, decision.channel, decision.reason, decision.tags, decision.score, facts.requirements)
        counts[decision.channel] += 1
        print(f"{decision.channel:>9}  {job.company}: {job.title}  ({decision.reason})")

    for job, original_key in copies:
        channel = store.channel_for(original_key)
        if channel in ALERT_CHANNELS:
            notifier.send_copy_note(job, channel)
        counts["copies"] += 1

    store.save()
    return counts