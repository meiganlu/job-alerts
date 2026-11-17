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