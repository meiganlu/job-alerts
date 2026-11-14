from jobalerts.sources.lever import parse_jobs

SAMPLE = [
    {
        "id": "ddc10181-6ecc-4dfc-9d02-2c5ce820cfdd",
        "text": "Backend Engineer",
        "categories": {"location": "New York, NY"},
        "hostedUrl": "https://jobs.lever.co/spotify/ddc10181-6ecc-4dfc-9d02-2c5ce820cfdd",
        "createdAt": 1762000000000,
    },
    {
        "id": "abc",
        "text": "Data Engineer",
        "categories": None,
        "hostedUrl": "https://jobs.lever.co/spotify/abc",
    },
]


def test_parses_fields():
    job = parse_jobs(SAMPLE, "spotify")[0]
    assert job.title == "Backend Engineer"
    assert job.location == "New York, NY"
    assert job.key == "lever:spotify:ddc10181-6ecc-4dfc-9d02-2c5ce820cfdd"
    assert job.posted_at.year == 2025  # milliseconds converted to a real date


def test_handles_missing_fields():
    job = parse_jobs(SAMPLE, "spotify")[1]
    assert job.location == ""
    assert job.posted_at is None


def test_requirements_list_is_included():
    item = {
        "id": "x",
        "text": "Backend Engineer",
        "hostedUrl": "https://jobs.lever.co/spotify/x",
        "descriptionPlain": "Join our team.",
        "lists": [{"text": "Requirements", "content": "<li>2+ years of Python</li>"}],
    }
    job = parse_jobs([item], "spotify")[0]
    assert "Requirements" in job.description
    assert "2+ years of Python" in job.description