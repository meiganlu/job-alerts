"""Fetches jobs from a company's Greenhouse job board."""
import httpx

from jobalerts.models import Job
from jobalerts.text import html_to_text

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def parse_jobs(data: dict, token: str) -> list[Job]:
    """Turns Greenhouse's JSON into Job objects."""
    jobs = []
    for item in data.get("jobs", []):
        jobs.append(
            Job(
                source="greenhouse",
                company=item.get("company_name") or token,
                board=token,
                job_id=str(item["id"]),
                title=item["title"],
                location=(item.get("location") or {}).get("name", ""),
                url=item["absolute_url"],
                posted_at=item.get("first_published"),
            )
        )
    return jobs


def fetch_jobs(token: str) -> list[Job]:
    """Downloads a company's open jobs and returns them as Job objects."""
    response = httpx.get(API.format(token=token), timeout=20)
    response.raise_for_status()
    return parse_jobs(response.json(), token)


def fetch_description(token: str, job_id: str) -> str:
    """Downloads one job's full description as plain text."""
    response = httpx.get(f"{API.format(token=token)}/{job_id}", timeout=20)
    response.raise_for_status()
    return html_to_text(response.json().get("content", ""))