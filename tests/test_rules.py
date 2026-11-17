from jobalerts.models import Job
from jobalerts.rules import classify, tech_split


def job(title="Software Engineer", description=""):
    return Job(source="greenhouse", company="Acme", job_id="1", title=title,
               location="Remote US", url="https://example.com/1", description=description)


def test_early_career_title_goes_to_apply_now():
    assert classify(job("Software Engineer, New Grad")).channel == "apply_now"
    assert classify(job("Software Engineer I, Backend")).channel == "apply_now"


def test_plain_title_within_range_goes_to_maybe():
    assert classify(job(description="Requirements\n- 2+ years of experience")).channel == "maybe"
    assert classify(job()).channel == "maybe"  # no years stated


def test_three_years_is_filtered_out():
    assert classify(job(description="- 3+ years of experience")).channel == "drop"
    assert classify(job(description="- three (3) years of professional experience")).channel == "drop"


def test_hard_stops_go_to_digest():
    assert classify(job(description="Must hold an active TS/SCI clearance.")).channel == "digest"
    assert classify(job(description="We are hiring a mid-level engineer.")).channel == "digest"
    assert classify(job(description="Master's degree in CS required.")).channel == "digest"


def test_bachelors_or_masters_is_fine():
    text = "Bachelor's or Master's degree in CS required."
    assert classify(job(description=text)).channel == "maybe"


def test_forward_deployed_is_maybe_even_if_new_grad():
    assert classify(job("Forward Deployed Engineer, New Grad")).channel == "maybe"


def test_tech_split():
    known, new = tech_split("Experience with Python, React, k8s and Terraform.")
    assert known == ["Python", "React"]
    assert new == ["Kubernetes", "Terraform"]


def test_tags_on_card():
    decision = classify(job("Software Engineer, New Grad",
                            "Python and Kubernetes. Ability to obtain a security clearance."))
    assert "🔒 clearance obtainable" in decision.tags
    assert "🌿 You know: Python" in decision.tags
    assert "🚩 New to you: Kubernetes" in decision.tags

def test_teammates_level_and_obtainable_clearance_are_not_blockers():
    assert classify(job(description="You will work with senior-level engineers.")).channel == "maybe"
    decision = classify(job(description="Ability to obtain and maintain an active Secret clearance."))
    assert decision.channel == "maybe"
    assert "🔒 clearance obtainable" in decision.tags


def test_company_years_are_not_requirements():
    intro = "With over 20 years of experience serving customers, Acme leads.\nRequirements\n- Python"
    assert classify(job(description=intro)).channel == "maybe"
    assert classify(job(description="Our team has 15 years of experience in payments.")).channel == "maybe"


def test_clearance_already_held_goes_to_digest():
    for text in ("Must hold a TS/SCI clearance.", "Secret clearance required.",
                 "Requires an existing Top Secret clearance.", "TS/SCI with Full Scope Polygraph required.",
                 "Clearance: Top Secret/SCI", "Candidates must currently hold a security clearance."):
        assert classify(job(description=text)).channel == "digest", text


def test_clearance_you_can_get_or_dont_need_is_fine():
    for text in ("Must be able to obtain a Secret clearance.", "US citizenship required due to clearance eligibility.",
                 "Security clearance is a plus.", "No clearance required.",
                 "This role does not require a security clearance."):
        assert classify(job(description=text)).channel == "maybe", text



def test_part_time_and_freelance_go_to_digest():
    for text in ("Engagement Type: Freelance", "This is a part-time role (20 hours/week).",
                 "Temporary 6-month position."):
        assert classify(job(description=text)).channel == "digest", text
    assert classify(job(description="Full-time or part-time schedules available.")).channel == "maybe"