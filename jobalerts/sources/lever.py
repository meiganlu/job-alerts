"""Fetches jobs from a company's Lever job board."""
from datetime import datetime, timezone

import httpx

from jobalerts.models import Job

HOSTS = ["https://api.lever.co", "https://api.eu.lever.co"]


def parse_jobs(data: list, slug: str) -> list[Job]:
    """Turns Lever's JSON into Job objects."""
    jobs = []
    for item in data:
        created_ms = item.get("createdAt")
        jobs.append(
            Job(
                source="lever",
                company=slug,
                job_id=item["id"],
                title=item["text"],
                location=(item.get("categories") or {}).get("location") or "",
                url=item["hostedUrl"],
                posted_at=(
                    datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
                    if created_ms
                    else None
                ),
                description=item.get("descriptionPlain") or "",
            )
        )
    return jobs


def fetch_jobs(slug: str) -> list[Job]:
    """Downloads a company's Lever postings. Tries the US host, then the EU host."""
    for host in HOSTS:
        response = httpx.get(
            f"{host}/v0/postings/{slug}", params={"mode": "json"}, timeout=20
        )
        if response.status_code == 404:
            continue  # not on this host; try the next one
        response.raise_for_status()
        return parse_jobs(response.json(), slug)
    raise ValueError(f"No Lever board found for '{slug}'")