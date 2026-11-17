"""Fetches many job boards at once, keeping only jobs that pass the rule filter."""
import asyncio
import hashlib
import time
from dataclasses import dataclass, field

import httpx

from jobalerts.filters import location_in_scope, passes_rule_filter, title_in_scope
from jobalerts.models import Job
from jobalerts.sources import ashby, greenhouse, lever

LIMITS = {"greenhouse": 10, "lever": 6, "ashby": 6}  # requests in flight at once, per platform
MAX_RETRIES = 3
GIVE_UP_AFTER_THROTTLES = 20  # a platform that keeps saying "slow down" is skipped this run
BOARD_TIMEOUT = 60  # seconds one board may take in total, retries included
PARSERS = {"greenhouse": greenhouse.parse_jobs, "lever": lever.parse_jobs, "ashby": ashby.parse_jobs}


@dataclass
class FetchResult:
    company: dict
    status: str                      # "ok", "not_found", "throttled", "error", or "skipped"
    kept: list[Job] = field(default_factory=list)  # jobs passing the rule filter
    job_count: int = 0               # all open jobs on the board
    ids_hash: str = ""               # changes whenever the board's set of job IDs changes
    error: str = ""


def board_urls(ats: str, slug: str) -> list[str]:
    """Where to fetch a board. Note: Lever has a US host and an EU host, tried in order."""
    if ats == "greenhouse":
        return [greenhouse.API.format(token=slug)]
    if ats == "ashby":
        return [ashby.API.format(slug=slug)]
    if ats == "lever":
        return [f"{host}/v0/postings/{slug}?mode=json" for host in lever.HOSTS]
    raise ValueError(f"Unsupported platform: {ats}")


def _hash_ids(ids) -> str:
    joined = ",".join(sorted(ids))
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def ids_hash(jobs: list[Job]) -> str:
    """A short code for a board's job IDs. Same IDs (in any order) → same code."""
    return _hash_ids(job.job_id for job in jobs)


def _raw_items(ats: str, data) -> list[dict]:
    """The board's job entries, before building Job objects (Ashby: listed jobs only)."""
    if ats == "lever":
        return data
    items = data.get("jobs", [])
    if ats == "ashby":
        items = [item for item in items if item.get("isListed") is not False]
    return items


def _raw_title_location(ats: str, item: dict) -> tuple[str, str]:
    if ats == "greenhouse":
        return item.get("title") or "", (item.get("location") or {}).get("name") or ""
    if ats == "lever":
        return item.get("text") or "", (item.get("categories") or {}).get("location") or ""
    return item.get("title") or "", item.get("location") or ""


def _wrap(ats: str, items: list[dict]):
    """Puts entries back in the shape the source's parse_jobs expects."""
    return items if ats == "lever" else {"jobs": items}


def _retry_after(response: httpx.Response, attempt: int) -> float:
    """How long the site asked to wait (capped at 30 s), or 1, 2, 4… seconds if it didn't say."""
    try:
        return min(float(response.headers["Retry-After"]), 30)
    except (KeyError, ValueError):
        return 2 ** attempt


class Fetcher:
    def __init__(self, client: httpx.AsyncClient, sleep=asyncio.sleep, deadline: float | None = None):
        self.client = client
        self.sleep = sleep  # replaceable in tests, so they don't actually wait
        self.deadline = deadline  # time.monotonic() value after which no new board is started
        self.slots = {ats: asyncio.Semaphore(n) for ats, n in LIMITS.items()}
        self.throttles = {ats: 0 for ats in LIMITS}

    async def _get(self, ats: str, url: str) -> httpx.Response:
        """GET with retries for 'too many requests', server errors, and dropped connections."""
        for attempt in range(MAX_RETRIES + 1):
            last_try = attempt == MAX_RETRIES
            try:
                response = await self.client.get(url)
            except httpx.TransportError:  # timeout or dropped connection
                if last_try:
                    raise
                await self.sleep(2 ** attempt)
                continue
            if response.status_code == 429:
                self.throttles[ats] += 1
                if last_try:
                    return response
                await self.sleep(_retry_after(response, attempt))
                continue
            if response.status_code >= 500 and not last_try:
                await self.sleep(2 ** attempt)
                continue
            return response

    async def fetch_one(self, company: dict) -> FetchResult:
        if self.throttles[company["ats"]] >= GIVE_UP_AFTER_THROTTLES:
            return FetchResult(company, "skipped")
        async with self.slots[company["ats"]]:  # wait for a free slot on this platform
            if self.deadline is not None and time.monotonic() > self.deadline:
                return FetchResult(company, "skipped")  # out of time; checked next run
            try:  # one slow or broken board never stops the run
                return await asyncio.wait_for(self._fetch_board(company), BOARD_TIMEOUT)
            except Exception as error:
                return FetchResult(company, "error", error=f"{type(error).__name__}: {error}"[:200])

    async def _fetch_board(self, company: dict) -> FetchResult:
        ats, slug = company["ats"], company["slug"]
        for url in board_urls(ats, slug):
            response = await self._get(ats, url)
            if response.status_code == 404:
                continue  # not on this host (Lever: try the EU host next)
            if response.status_code == 429:
                return FetchResult(company, "throttled")
            response.raise_for_status()
            items = _raw_items(ats, response.json())
            # Cheap title/location check on raw data; build Job objects only for likely matches
            likely = [item for item in items
                      if title_in_scope(_raw_title_location(ats, item)[0])
                      and location_in_scope(_raw_title_location(ats, item)[1])]
            jobs = PARSERS[ats](_wrap(ats, likely), slug)
            return FetchResult(
                company, "ok",
                kept=[job for job in jobs if passes_rule_filter(job)],  # full rules
                job_count=len(items),
                ids_hash=_hash_ids(str(item["id"]) for item in items),
            )
        return FetchResult(company, "not_found")


async def fetch_all(companies: list[dict], transport=None, sleep=asyncio.sleep,
                    deadline: float | None = None) -> list[FetchResult]:
    """Fetches every company. Companies earlier in the list get the first slots,
    so favorites (sorted first) are checked first. Boards not started by `deadline` are skipped."""
    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        transport=transport,
        limits=httpx.Limits(max_connections=sum(LIMITS.values()) + 5),
        headers={"User-Agent": "job-alerts personal project (polls public job-board APIs)"},
    ) as client:
        fetcher = Fetcher(client, sleep, deadline)
        return await asyncio.gather(*(fetcher.fetch_one(company) for company in companies))