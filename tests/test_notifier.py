from jobalerts.models import Job
from jobalerts.notifier import build_message, build_copy_note, short_label, build_text_message

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
    assert message["content"] == "Affirm: Software Engineer I, Fullstack (Search) <@&123>"
    assert message["allowed_mentions"] == {"roles": ["123"]}


def test_filtered_out_is_silent():
    message = build_message(JOB, "filtered_out", "test", role_id="123")
    assert message["content"] == ""
    assert message["allowed_mentions"] == {"roles": []}


def test_score_and_tags_are_shown():
    message = build_message(JOB, "apply_now", "meets 83%", role_id="123",
                            tags=["⭐ Bay Area"], score=0.83)
    embed = message["embeds"][0]
    assert "⭐ Bay Area" in embed["description"]
    assert {"name": "Score", "value": "83%", "inline": True} in embed["fields"]


def test_copy_note_never_pings():
    assert build_copy_note(JOB)["allowed_mentions"] == {"parse": []}


def test_long_titles_are_shortened():
    long_job = JOB.model_copy(update={"title": "Software Engineer " * 10})
    label = short_label(long_job)
    assert len(label) == 70
    assert label.endswith("…")


def test_text_message_pings_only_when_asked():
    loud = build_text_message("🚨 crash", role_id="123")
    assert loud["content"] == "🚨 crash <@&123>"
    assert loud["allowed_mentions"] == {"roles": ["123"]}

    quiet = build_text_message("digest")
    assert quiet["allowed_mentions"] == {"parse": []}