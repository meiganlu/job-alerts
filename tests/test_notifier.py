from jobalerts.models import Job
from jobalerts.notifier import build_message

JOB = Job(
    source="greenhouse",
    company="Affirm",
    job_id="8017340003",
    title="Software Engineer I, Fullstack (Search)",
    location="Remote US",
    url="https://job-boards.greenhouse.io/affirm/jobs/8017340003",
)


def test_apply_now_pings_role():
    message = build_message(JOB, "apply_now", "test", role_id="123")
    assert message["content"] == "<@&123>"
    assert message["allowed_mentions"] == {"roles": ["123"]}


def test_filtered_out_is_silent():
    message = build_message(JOB, "filtered_out", "test", role_id="123")
    assert message["content"] == ""
    assert message["allowed_mentions"] == {"roles": []}