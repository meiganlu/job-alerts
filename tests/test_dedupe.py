from jobalerts.dedupe import fingerprint, split_new
from jobalerts.models import Job
from jobalerts.store import SeenStore


def make_job(job_id, location="Remote US", title="Software Engineer I"):
    return Job(
        source="greenhouse",
        company="Affirm",
        job_id=job_id,
        title=title,
        location=location,
        url=f"https://job-boards.greenhouse.io/affirm/jobs/{job_id}",
        description="Build backend services in Python.",
    )


def test_new_job_is_returned_once():
    store = SeenStore(":memory:")  # temporary database that lives only during the test
    job = make_job("1")
    assert split_new([job], store) == ([job], [])
    assert split_new([job], store) == ([], [])  # second run: already seen


def test_same_job_other_city_is_a_copy():
    store = SeenStore(":memory:")
    us = make_job("1", location="Remote US")
    nyc = make_job("2", location="New York, NY")
    new_jobs, copies = split_new([us, nyc], store)
    assert new_jobs == [us]
    assert copies == [(nyc, us.key)]


def test_different_titles_are_both_new():
    store = SeenStore(":memory:")
    a = make_job("1", title="Software Engineer I, Backend")
    b = make_job("2", title="Software Engineer I, Frontend")
    new_jobs, _ = split_new([a, b], store)
    assert len(new_jobs) == 2


def test_fingerprint_ignores_spacing_and_case():
    a = make_job("1", title="Software Engineer I")
    b = make_job("2", title="  software   ENGINEER i ")
    assert fingerprint(a) == fingerprint(b)