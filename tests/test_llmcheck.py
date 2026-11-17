import os
os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")  # tests never call Bedrock

from jobalerts import llmcheck
from jobalerts.decide import Decision
from jobalerts.models import Job

POSTING = ("Requirements\n- 3+ years building backend services\n- Python and SQL\n"
           "Open to candidates graduating between December 2025 and August 2026.\n"
           "- BS in Mechanical or Electrical Engineering required\n"
           "- BS in Computer Science or related field")


class FakeStore:
    def __init__(self, spent=0):
        self.spent = spent

    def llm_spent(self, day):
        return self.spent

    def add_llm_spend(self, day, micros):
        self.spent += micros


class FakeClient:
    def __init__(self, report, error=None):
        self.report, self.error, self.calls = report, error, 0

    def converse(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return {"usage": {"inputTokens": 1500, "outputTokens": 150},
                "output": {"message": {"content": [{"toolUse": {"name": "report", "input": self.report}}]}}}


def job():
    return Job(source="greenhouse", company="Acme", job_id="1", title="Software Engineer",
               location="Remote US", url="https://example.com/1", description=POSTING)


def check(report, store=None, error=None):
    client = FakeClient(report, error)
    decision = llmcheck.second_opinion(job(), Decision(channel="maybe", tags=[], reason="rules"),
                                       store or FakeStore(), client)
    return decision, client


def test_years_the_rules_missed_are_dropped():
    # The rules skip this sentence (no word "experience"); the LLM catches it
    assert check({"years_quote": "3+ years building backend services"})[0].channel == "drop"


def test_made_up_quote_is_ignored():
    assert check({"seniority": "senior", "seniority_quote": "senior engineer role"})[0].channel == "maybe"


def test_graduation_window_excluding_you_goes_to_digest():
    decision, _ = check({"grad_start": "2025-12", "grad_end": "2026-08",
                         "grad_quote": "graduating between December 2025 and August 2026"})
    assert decision.channel == "digest"


def test_requirements_on_card():
    decision, _ = check({"requirements": ["Python", "SQL"]})
    assert decision.channel == "maybe"
    assert "📋 Requires: Python · SQL" in decision.tags


def test_spend_is_recorded():
    store = FakeStore()
    check({}, store)
    assert store.spent == 1500 + 5 * 150


def test_over_budget_skips_the_llm():
    decision, client = check({}, FakeStore(spent=10**9))
    assert client.calls == 0
    assert decision.channel == "maybe"


def test_llm_error_keeps_rules_decision():
    assert check({}, error=RuntimeError("throttled"))[0].channel == "maybe"


def test_non_cs_field_goes_to_digest():
    decision, _ = check({"field_excludes_cs": True,
                         "field_quote": "BS in Mechanical or Electrical Engineering required"})
    assert decision.channel == "digest"


def test_cs_or_related_field_is_never_blocked():
    decision, _ = check({"field_excludes_cs": True, "field_quote": "BS in Computer Science or related field"})
    assert decision.channel == "maybe"