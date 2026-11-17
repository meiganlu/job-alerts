import asyncio

import httpx

from jobalerts.companies import load_all
from jobalerts.fetcher import fetch_all, ids_hash
from jobalerts.models import Job

GREENHOUSE = {"jobs": [
    {"id": 1, "title": "Software Engineer", "location": {"name": "Remote US"},
     "absolute_url": "https://example.com/1"},
    {"id": 2, "title": "Senior Software Engineer", "location": {"name": "Remote US"},
     "absolute_url": "https://example.com/2"},
]}
LEVER = [{"id": "a", "text": "Software Engineer", "categories": {"location": "Austin, TX"},
          "hostedUrl": "https://jobs.lever.co/acme/a"}]


async def no_wait(seconds):
    pass


def fetch(companies, handler):
    return asyncio.run(fetch_all(companies, transport=httpx.MockTransport(handler), sleep=no_wait))


def test_fetches_and_filters():
    [result] = fetch([{"ats": "greenhouse", "slug": "acme"}],
                     lambda request: httpx.Response(200, json=GREENHOUSE))
    assert result.status == "ok"
    assert result.job_count == 2
    assert [job.title for job in result.kept] == ["Software Engineer"]  # Senior filtered out


def test_retries_after_too_many_requests():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json=GREENHOUSE)

    [result] = fetch([{"ats": "greenhouse", "slug": "acme"}], handler)
    assert result.status == "ok"
    assert len(calls) == 2


def test_missing_board_is_not_found():
    [result] = fetch([{"ats": "ashby", "slug": "gone"}], lambda request: httpx.Response(404))
    assert result.status == "not_found"


def test_lever_falls_back_to_eu_host():
    def handler(request):
        if request.url.host == "api.lever.co":
            return httpx.Response(404)
        return httpx.Response(200, json=LEVER)

    [result] = fetch([{"ats": "lever", "slug": "acme"}], handler)
    assert result.status == "ok"
    assert len(result.kept) == 1


def test_ids_hash_ignores_order():
    def job(job_id):
        return Job(source="ashby", company="acme", job_id=job_id, title="x", location="",
                   url="https://example.com")
    assert ids_hash([job("1"), job("2")]) == ids_hash([job("2"), job("1")])


def test_favorites_load_first():
    class FakeTable:
        def scan(self, **kwargs):
            return {"Items": [{"company_id": "a", "favorite": False},
                              {"company_id": "b", "favorite": True}]}

    assert [c["company_id"] for c in load_all(FakeTable())] == ["b", "a"]


def test_hash_matches_full_parse():
    from jobalerts.sources.greenhouse import parse_jobs
    [result] = fetch([{"ats": "greenhouse", "slug": "acme"}],
                     lambda request: httpx.Response(200, json=GREENHOUSE))
    assert result.ids_hash == ids_hash(parse_jobs(GREENHOUSE, "acme"))


def test_boards_after_the_deadline_are_skipped():
    import time
    results = asyncio.run(fetch_all([{"ats": "greenhouse", "slug": "acme"}],
                                    transport=httpx.MockTransport(lambda r: httpx.Response(200, json=GREENHOUSE)),
                                    sleep=no_wait, deadline=time.monotonic() - 1))
    assert results[0].status == "skipped"
