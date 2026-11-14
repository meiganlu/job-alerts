"""Runs the whole job-alert pipeline:
fetch → rule filter → dedupe → description → extract → verify → decide → notify."""
from collections import Counter
from pathlib import Path

import yaml

from jobalerts import notifier
from jobalerts.decide import decide
from jobalerts.dedupe import split_new, fingerprint
from jobalerts.extract import extract, verify
from jobalerts.filters import passes_rule_filter
from jobalerts.models import Job
from jobalerts.sources import ashby, greenhouse, lever
from jobalerts.store import SeenStore

COMPANIES_FILE = Path(__file__).parent.parent / "companies.yaml"
SOURCES = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}
ALERT_CHANNELS = {"apply_now", "maybe"}


def load_companies() -> list[dict]:
    return yaml.safe_load(COMPANIES_FILE.read_text())["companies"]


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


def run(store: SeenStore, baseline: bool = False, limit: int = 10) -> Counter:
    counts = Counter()
    kept = fetch_kept_jobs(counts)

    # First real run: remember everything open now, alert on nothing
    if baseline:
        for job in kept:
            store.add_key(job.key)
        store.save()
        counts["marked_seen"] = len(kept)
        return counts

    # Only unseen jobs, capped by the limit; the rest wait for the next run
    fresh = [job for job in kept if not store.has_key(job.key)][:limit]
    for job in fresh:
        fill_description(job)
    new_jobs, copies = split_new(fresh, store)

    for job in new_jobs:
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
            notifier.send(job, decision.channel, decision.reason, decision.tags, decision.score)
        counts[decision.channel] += 1
        print(f"{decision.channel:>9}  {job.company}: {job.title}  ({decision.reason})")

    for job, original_key in copies:
        channel = store.channel_for(original_key)
        if channel in ALERT_CHANNELS:
            notifier.send_copy_note(job, channel)
        counts["copies"] += 1

    store.save()
    return counts