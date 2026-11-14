from jobalerts.extract import Extraction, Requirement, parse_response, quote_found, verify
from jobalerts.models import Job

JOB = Job(
    source="greenhouse",
    company="Upstart",
    job_id="1",
    title="Software Engineer, ML Platform",
    location="Remote US",
    url="https://example.com/1",
    description="Bachelor\u2019s degree + 3 years of experience.\n"
                "Strong Python skills.\nInterest in machine learning research.",
)


def req(text, status="met"):
    return Requirement(requirement=text, importance="required", kind="hard", status=status)


def test_quote_found_ignores_case_spacing_and_curly_quotes():
    assert quote_found("bachelor's degree  + 3 YEARS", JOB.description)
    assert not quote_found("5 years of experience", JOB.description)
    assert not quote_found("", JOB.description)


def test_verified_fact_is_kept():
    facts = Extraction(years_required=3, years_required_quote="+ 3 years of experience")
    assert verify(facts, JOB).years_required == 3


def test_invented_fact_is_reset():
    facts = Extraction(years_required=5, years_required_quote="5+ years required")
    assert verify(facts, JOB).years_required is None


def test_invented_requirement_is_removed():
    facts = Extraction(requirements=[req("Strong Python skills."), req("Expert in Rust", "not_met")])
    assert [r.requirement for r in verify(facts, JOB).requirements] == ["Strong Python skills."]


def test_domain_from_description_only_is_reset():
    # The description mentions ML research, but the title doesn't, so it must not drop the job
    facts = Extraction(domain="ai_research", domain_quote="machine learning research")
    assert verify(facts, JOB).domain == "general"


def test_parse_response_reads_tool_output():
    fake = {"output": {"message": {"content": [
        {"toolUse": {"name": "record_job_facts", "input": {"years_required": 0}}}
    ]}}}
    assert parse_response(fake).years_required == 0