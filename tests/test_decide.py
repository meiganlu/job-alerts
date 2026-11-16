from jobalerts.decide import decide, qualification_score
from jobalerts.extract import Extraction, Requirement
from jobalerts.models import Job


def job(location="Remote US"):
    return Job(source="greenhouse", company="Acme", job_id="1", title="Software Engineer",
               location=location, url="https://example.com/1")


def reqs(*statuses):
    """Required hard requirements with the given statuses, e.g. reqs("met", "partial")."""
    return [Requirement(requirement=f"skill {i}", importance="required", kind="hard", status=s)
            for i, s in enumerate(statuses)]


# --- Hard stops ---
def test_three_years_required_is_dropped():  # like Upstart
    facts = Extraction(years_required=3, years_required_quote="+ 3 years", requirements=reqs("met"))
    assert decide(facts, job()).channel == "drop"


def test_two_years_required_has_no_penalty():
    facts = Extraction(years_required=2, years_required_quote="2+ years", requirements=reqs("met"))
    assert decide(facts, job()).channel == "apply_now"


def test_mobile_domain_is_dropped():
    facts = Extraction(domain="mobile", domain_quote="iOS Engineer", requirements=reqs("met"))
    assert decide(facts, job()).channel == "drop"


def test_active_clearance_goes_to_digest():
    facts = Extraction(clearance="active_required", clearance_quote="Active TS/SCI", requirements=reqs("met"))
    assert decide(facts, job()).channel == "digest"


def test_three_years_preferred_is_maybe():
    facts = Extraction(years_preferred=3, years_preferred_quote="3+ years preferred", requirements=reqs("met"))
    assert decide(facts, job()).channel == "maybe"


# --- Scores ---
def test_score_counts_partial_as_half():  # like Spotify
    assert qualification_score(Extraction(requirements=reqs("partial", "met"))) == 0.75


def test_score_thresholds():
    assert decide(Extraction(requirements=reqs("met", "not_met")), job()).channel == "apply_now"  # 50%
    assert decide(Extraction(requirements=reqs("met", "not_met", "not_met")), job()).channel == "maybe"  # 33%, like Zscaler
    assert decide(Extraction(requirements=reqs("met", "not_met", "not_met", "not_met", "not_met")), job()).channel == "digest"  # 20%


def test_no_requirements_is_maybe():
    assert decide(Extraction(), job()).channel == "maybe"


# --- Tags ---
def test_grad_window_tag():
    outside = Extraction(grad_start="2026-09", grad_end="2027-06", grad_quote="x", requirements=reqs("met"))
    inside = Extraction(grad_end="2027-08", grad_quote="x", requirements=reqs("met"))  # like Affirm
    assert any("grads" in t for t in decide(outside, job()).tags)
    assert not any("grads" in t for t in decide(inside, job()).tags)
    assert "⚠️ For Sep 2026 – Jun 2027 grads" in decide(outside, job()).tags


def test_bay_area_tag():
    facts = Extraction(requirements=reqs("met"))
    assert "⭐ Bay Area" in decide(facts, job("San Jose, CA")).tags


def test_research_role_is_scored_not_dropped():
    facts = Extraction(domain="ai_research", domain_quote="Research Engineer", requirements=reqs("met", "not_met", "not_met"))
    decision = decide(facts, job())
    assert decision.channel == "maybe"  # 33% → #maybe, not dropped
    assert "🔬 research role" in decision.tags


def test_mid_level_goes_to_digest():  # like Affirm CIAM
    facts = Extraction(seniority="mid", seniority_quote="mid-level engineer", requirements=reqs("met"))
    decision = decide(facts, job())
    assert decision.channel == "digest"
    assert "mid-level" in decision.reason