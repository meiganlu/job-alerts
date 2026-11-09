"""Fetches jobs from a company's Ashby job board."""
import httpx

from jobalerts.models import Job

API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def parse_jobs(data: dict, slug: str) -> list[Job]:
    """Turns Ashby's JSON into Job objects."""
    jobs = []
    for item in data.get("jobs", []):
        if item.get("isListed") is False:
            continue  # hidden posting; skip it
        jobs.append(
            Job(
                source="ashby",
                company=slug,
                job_id=item["id"],
                title=item["title"],
                location=item.get("location") or "",
                url=item["jobUrl"],
                posted_at=item.get("publishedAt"),
                description=item.get("descriptionPlain") or "",
            )
        )
    return jobs


def fetch_jobs(slug: str) -> list[Job]:
    """Downloads a company's open jobs and returns them as Job objects."""
    response = httpx.get(API.format(slug=slug), timeout=20)
    response.raise_for_status()
    return parse_jobs(response.json(), slug)