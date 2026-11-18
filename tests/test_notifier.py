from jobalerts.models import Job
from jobalerts.notifier import (build_copy_note, build_message, build_text_message,
    requirement_fields, short_label, short_locations,
    short_requirement)
from jobalerts.extract import Requirement


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


def test_meta_line_replaces_score_and_location_fields():
    message = build_message(JOB, "apply_now", "meets 83% of required qualifications",
                            role_id="123", tags=["⭐ Bay Area", "🔒 clearance sponsored"], score=0.83)
    description = message["embeds"][0]["description"]
    assert description.startswith("83% match · 📍 Remote US ⭐")
    assert "meets 83%" not in description          # no repeated score
    assert "🔒 clearance sponsored" in description  # other tags still shown


def test_requirement_blocks_gaps_first():
    fields = requirement_fields([
        Requirement(requirement="Python", importance="required", kind="hard", status="met"),
        Requirement(requirement="Java backend", importance="required", kind="hard", status="not_met"),
        Requirement(requirement="Kubernetes", importance="preferred", kind="hard", status="partial"),
        Requirement(requirement="Curiosity", importance="required", kind="soft", status="met"),
    ])
    assert [field["name"] for field in fields] == ["Required", "Preferred", "Soft skills"]
    assert fields[0]["value"] == "🚩 Java backend\n🌿 Python"


def test_short_requirement():
    assert short_requirement("Working knowledge of SQL, Python, or other scripting languages.") \
        == "SQL, Python, or other scripting languages"
    cut = short_requirement("Familiarity with data mining, data visualization, and "
                            "foundational statistical modeling")
    assert cut == "Data mining, data visualization, and…"


def test_short_locations():
    assert short_locations("New York, New York, United States; "
                           "San Francisco, California, United States") == "San Francisco · New York"
    assert short_locations("Bellevue, WA; Mountain View, CA; San Francisco, CA; Vancouver, BC") \
        == "Mountain View · San Francisco +2"


def test_stripe_color_by_channel():
    assert build_message(JOB, "apply_now", "x", "123")["embeds"][0]["color"] == 0x2ECC71
    assert build_message(JOB, "maybe", "x", "123")["embeds"][0]["color"] == 0xF1C40F


def test_alert_has_applied_button():
    button = build_message(JOB, "apply_now", "x", "123")["components"][0]["components"][0]
    assert button["custom_id"] == f"applied:{JOB.key}"
    assert build_message(JOB, "filtered_out", "x", "123")["components"] == []
    assert button["label"] == "Apply"


def test_quiet_alert_keeps_button_but_does_not_ping():
    message = build_message(JOB, "maybe", "test", role_id="123", quiet=True)
    assert message["content"] == ""
    assert message["allowed_mentions"] == {"roles": []}
    assert message["components"]