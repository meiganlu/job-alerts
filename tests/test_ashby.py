from jobalerts.sources.ashby import parse_jobs

SAMPLE = {
    "jobs": [
        {
            "id": "5494e6a1-a973-46af-b9f3-57208eb91b52",
            "title": "Full Stack Software Engineer, New Grad",
            "location": "Remote",
            "jobUrl": "https://jobs.ashbyhq.com/quora/5494e6a1-a973-46af-b9f3-57208eb91b52",
            "publishedAt": "2026-11-01T10:00:00Z",
            "isListed": True,
        },
        {
            "id": "hidden-1",
            "title": "Internal Role",
            "jobUrl": "https://jobs.ashbyhq.com/quora/hidden-1",
            "isListed": False,
        },
    ]
}


def test_skips_hidden_postings():
    jobs = parse_jobs(SAMPLE, "quora")
    assert len(jobs) == 1


def test_parses_fields():
    job = parse_jobs(SAMPLE, "quora")[0]
    assert job.title == "Full Stack Software Engineer, New Grad"
    assert job.location == "Remote"
    assert job.key == "ashby:quora:5494e6a1-a973-46af-b9f3-57208eb91b52"