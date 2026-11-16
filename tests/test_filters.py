from jobalerts.filters import is_bay_area, location_in_scope, title_in_scope
from jobalerts.filters import passes_rule_filter
from jobalerts.models import Job


# --- Titles ---
def test_titles_kept():
    assert title_in_scope("Software Engineer I, Fullstack (Search)")  # Affirm
    assert title_in_scope("Production Engineer")  # Zscaler, should reach #maybe
    assert title_in_scope("Software Engineer, Public Sector - New Grad")  # Scale AI
    assert title_in_scope("QA Engineer")
    assert title_in_scope("Software Development Engineer in Test")
    assert title_in_scope("Analyst, Early Career (Full Stack)")
    assert title_in_scope("Software Engineer - Infrastructure Security")
    assert title_in_scope("Member of Technical Staff")
    assert title_in_scope("SWE II, Backend")
    assert title_in_scope("Full-Stack Engineer")
    assert title_in_scope("Software Quality Engineer")
    assert title_in_scope("QA Tester")
    assert title_in_scope("Test Automation Engineer")
    assert title_in_scope("Distributed Systems Engineer")


def test_titles_dropped():
    assert not title_in_scope("Senior Software Engineer")
    assert not title_in_scope("Sr. Software Engineer")
    assert not title_in_scope("Staff Engineer")
    assert not title_in_scope("Engineering Manager")
    assert not title_in_scope("Software Engineer Intern")
    assert not title_in_scope("Sales Engineer")
    assert not title_in_scope("Accounting Manager")
    assert not title_in_scope("Account Executive - Commercial")
    assert not title_in_scope("Security Engineer - Detection and Response")
    assert not title_in_scope("Detection & CorpSec Engineer (Remote)")
    assert not title_in_scope("Senior Member of Technical Staff")  # still senior
    assert not title_in_scope("iOS Engineer")
    assert not title_in_scope("Software Engineer, Mobile (App Infrastructure)")
    assert not title_in_scope("Clinical Testing Psychologist")
    assert not title_in_scope("Account Executive, Software")
    assert not title_in_scope("Electrical Engineer")
    assert not title_in_scope("Manufacturing Engineer")
    assert not title_in_scope("Technical Support Engineer")
    assert not title_in_scope("Legal Engineer")
    assert not title_in_scope("Systems Engineer, Avionics")
    assert not title_in_scope("GNC Engineer")


# --- Locations ---
def test_locations_kept():
    assert location_in_scope("Remote US")
    assert location_in_scope(
        "New York, New York, United States; San Francisco, California, United States"
    )
    assert location_in_scope("Bellevue, Washington, USA; San Jose, California, USA")
    assert location_in_scope("Remote - Multiple Locations")  # unclear, so keep
    assert location_in_scope("Home Based - Americas")  # Canonical
    assert location_in_scope("Indianapolis, IN")  # "india" must not match "Indianapolis"
    assert location_in_scope("")
    assert location_in_scope("Vancouver, WA")
    assert location_in_scope("Remote")
    assert location_in_scope("Atlanta, Georgia")
    assert location_in_scope("Santa Fe, New Mexico")
    assert location_in_scope("Jersey City, NJ")


def test_locations_dropped():
    assert not location_in_scope("Remote UK")
    assert not location_in_scope("London")
    assert not location_in_scope("Toronto")
    assert not location_in_scope("Bengaluru, India")
    assert not location_in_scope("Remote - UK or Ireland")  # the "or" bug
    assert not location_in_scope("Vancouver, BC")
    assert not location_in_scope("Remote - Kenya")


def test_bay_area():
    assert is_bay_area("San Jose, California, USA")
    assert not is_bay_area("Remote US")


def job_titled(title, company="Affirm"):
    return Job(source="greenhouse", company=company, board=company.lower(), job_id="1",
               title=title, location="Remote US", url="https://example.com/1")


def test_level_rules():
    assert not passes_rule_filter(job_titled("Software Engineer II - CIAM"))       # mid-level
    assert passes_rule_filter(job_titled("Software Engineer II, Early Career"))    # early-career
    assert passes_rule_filter(job_titled("Software Engineer I/II"))                # combined
    assert passes_rule_filter(job_titled("Software Engineer II", company="Google"))  # entry at Google
    assert not passes_rule_filter(job_titled("Software Engineer III"))