from jobalerts.sources.greenhouse import parse_jobs

SAMPLE = {
    "jobs": [
        {
            "id": 8017340003,
            "title": "Software Engineer I, Fullstack (Search)",
            "location": {"name": "Remote US"},
            "absolute_url": "https://job-boards.greenhouse.io/affirm/jobs/8017340003",
            "first_published": "2026-11-01T10:00:00-05:00",
            "company_name": "Affirm",
        },
        {
            "id": 123,
            "title": "Senior Software Engineer",
            "location": None,
            "absolute_url": "https://job-boards.greenhouse.io/affirm/jobs/123",
        },
        {
            "id": 456,
            "title": "Software Engineer",
            "location": {"name": None},
            "absolute_url": "https://job-boards.greenhouse.io/affirm/jobs/456",
        },
    ]
}


def test_parses_every_job():
    jobs = parse_jobs(SAMPLE, "affirm")
    assert len(jobs) == 3


def test_fills_fields_correctly():
    job = parse_jobs(SAMPLE, "affirm")[0]
    assert job.company == "Affirm"
    assert job.job_id == "8017340003"
    assert job.location == "Remote US"
    assert job.key == "greenhouse:Affirm:8017340003"
    assert job.posted_at is not None


def test_handles_missing_fields():
    job = parse_jobs(SAMPLE, "affirm")[1]
    assert job.location == ""        # location was None
    assert job.company == "affirm"   # no company_name, so the board name is used
    assert job.posted_at is None     # no first_published