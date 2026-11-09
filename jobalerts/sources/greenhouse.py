"""Fetches jobs from a company's Greenhouse job board."""
import httpx

from jobalerts.models import Job

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def parse_jobs(data: dict, token: str) -> list[Job]:
    """Turns Greenhouse's JSON into Job objects."""
    jobs = []
    for item in data.get("jobs", []):
        jobs.append(
            Job(
                source="greenhouse",
                company=item.get("company_name") or token,
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