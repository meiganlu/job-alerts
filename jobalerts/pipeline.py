"""Runs the job-alert pipeline once over every company in the companies table:
fetch all → skip unchanged boards → baseline new boards → dedupe → rules → LLM check → alert."""
import asyncio
import resource
import time
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from jobalerts import notifier
from jobalerts.companies import company_id, companies_table, load_all
from jobalerts.dedupe import fingerprint, split_new, title_key
from jobalerts.fetcher import fetch_all
from jobalerts.filters import is_early_career
from jobalerts.models import Job
from jobalerts.sources import greenhouse
from jobalerts.notifier import APPLIED_EMOJI
from jobalerts.rules import classify
from jobalerts.llmcheck import second_opinion


ALERT_CHANNELS = {"apply_now", "maybe"}
DEAD_AFTER_MISSES = 3


def priority(job: Job, favorites: set) -> tuple[bool, bool]:
    """Sort key: early-career titles first, then favs (False sorts before True.)"""
    return (not is_early_career(job.title), (job.source, job.board) not in favorites)


def _update(table, cid: str, fields: dict) -> None:
    """Sets fields on one company. '#name' placeholders avoid DynamoDB's reserved words."""
    table.update_item(
        Key={"company_id": cid},
        UpdateExpression="SET " + ", ".join(f"#{name} = :{name}" for name in fields),
        ExpressionAttributeNames={f"#{name}": name for name in fields},
        ExpressionAttributeValues={f":{name}": value for name, value in fields.items()},
    )


def _record_missing(table, company: dict) -> None:
    misses = int(company.get("missing_runs", 0)) + 1
    fields = {"missing_runs": misses}
    if misses >= DEAD_AFTER_MISSES:
        fields["dead"] = True  # stop checking this board
    _update(table, company["company_id"], fields)


def _company_of(job: Job) -> str:
    return company_id(job.source, job.board)


def fill_description(job: Job) -> None:
    """Greenhouse lists have no descriptions, so fetch for new jobs only."""
    if job.source == "greenhouse" and not job.description:
        try:
            job.description = greenhouse.fetch_description(job.board, job.job_id)
        except Exception as error:
            print(f"! no description for {job.title} @ {job.company}: {error}")


def applied_tag(job: Job, store) -> list[str]:
    """'🍀 You applied to a similar role on Nov 3', only if you clicked Applied before."""
    when = store.applied_at(title_key(job))
    if not when:
        return []
    day = datetime.fromisoformat(when).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%b %-d")
    return [f"{APPLIED_EMOJI} You applied to a similar role on {day}"]


def process(job: Job, store, counts: Counter) -> bool:
    """Rules decide; the LLM double-checks jobs that would alert you.
    On any failure (e.g. Discord is down), the job is un-marked as seen so the next run retries it."""
    try:
        decision = classify(job)
        if decision.channel in ALERT_CHANNELS:
            decision = second_opinion(job, decision, store)
        if decision.channel in ALERT_CHANNELS:  # still alerting after the check
            decision.tags += applied_tag(job, store)
        store.save_decision(job, decision)
        if decision.channel in ALERT_CHANNELS:
            notifier.send(job, decision.channel, decision.reason, decision.tags)
    except Exception as error:
        print(f"! failed on {job.company}: {job.title} ({error!r}); retrying next run")
        store.forget(job.key, fingerprint(job))
        counts["failed"] += 1
        return False
    counts[decision.channel] += 1
    print(f"{decision.channel:>9}  {job.company}: {job.title}  ({decision.reason})")
    return True


class Timer:
    """Prints how long each phase took, plus CPU time and peak memory so far."""
    def __init__(self):
        self.wall, self.cpu = time.monotonic(), time.process_time()

    def lap(self, phase: str) -> None:
        now_wall, now_cpu = time.monotonic(), time.process_time()
        peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Linux reports KB
        print(f"timing  {phase:<14} wall {now_wall - self.wall:6.1f}s   "
              f"cpu {now_cpu - self.cpu:6.1f}s   peak memory {peak_mb:5.0f} MB")
        self.wall, self.cpu = now_wall, now_cpu


def run(store, limit: int = 25, table=None) -> Counter:
    counts = Counter()
    table = table or companies_table()
    timer = Timer()
    companies = [company for company in load_all(table) if not company.get("dead")]
    favorites = {(c["ats"], c["slug"]) for c in companies if c.get("favorite")}
    timer.lap("load companies")
    results = asyncio.run(fetch_all(companies))
    timer.lap("fetch & filter")

    # 1. Sort every board into: missing, new (baseline), unchanged (skip), or changed
    candidates, changed = [], {}
    for result in results:
        company = result.company
        counts[result.status] += 1
        if result.status == "not_found":
            _record_missing(table, company)
        elif result.status == "ok":
            if not company.get("baselined"):
                store.add_keys([job.key for job in result.kept])  # remember, don't alert
                _update(table, company["company_id"],
                        {"baselined": True, "ids_hash": result.ids_hash, "missing_runs": 0})
                counts["baselined"] += 1
            elif result.ids_hash != company.get("ids_hash"):
                candidates += result.kept
                changed[company["company_id"]] = result
            elif company.get("missing_runs"):
                _update(table, company["company_id"], {"missing_runs": 0})
    timer.lap("sort boards")
    
    
    # 2. Unseen jobs from changed boards, most important first, capped per run
    unseen = sorted((job for job in candidates if not store.has_key(job.key)),
                    key=lambda job: priority(job, favorites))
    timer.lap("check seen")
    batch, waiting = unseen[:limit], unseen[limit:]
    pending = {_company_of(job) for job in waiting}  # boards with jobs left for next run
    counts["waiting"] = len(waiting)

    for job in batch:
        fill_description(job)
    new_jobs, copies = split_new(batch, store)

    # 3. Decide and alert
    for job in new_jobs:
        if not process(job, store, counts):
            pending.add(_company_of(job))
    for job, original_key in copies:
        channel = store.channel_for(original_key)
        if channel in ALERT_CHANNELS:
            try:
                notifier.send_copy_note(job, channel)
            except Exception as error:  # a missed "also posted" note isn't worth crashing for
                print(f"! copy note failed for {job.key}: {error!r}")
        counts["copies"] += 1
    timer.lap("decide & alert")

    # 4. Remember each changed board's new fingerprint, unless it still has jobs to handle
    for cid, result in changed.items():
        if cid not in pending:
            _update(table, cid, {"ids_hash": result.ids_hash, "missing_runs": 0})

    store.save()
    timer.lap("save boards")
    return counts