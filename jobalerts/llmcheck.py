"""Second opinion from Haiku on jobs the rules would alert me about. Finds blockers, lists requirements."""
import os
import re
from datetime import datetime
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config
from pydantic import BaseModel

from jobalerts import config
from jobalerts.decide import RULES, Decision
from jobalerts.models import Job
from jobalerts.precheck import is_preferred, min_years
from jobalerts.text import trim_boilerplate

PACIFIC = ZoneInfo("America/Los_Angeles")
BUDGET_MICROS = int(float(os.environ.get("LLM_DAILY_BUDGET", "0.16")) * 1_000_000)
GRADUATION = str(RULES["graduation"])  # "2025-06"
MAX_YEARS = RULES["max_years_required"]  # 2
_MONTH = re.compile(r"^\d{4}-\d{2}$")
# A field list that includes any of these still fits a CS degree, whatever the model says
_CS_FRIENDLY = re.compile(r"computer|software|related|technical|equivalent|stem|quantitative", re.IGNORECASE)

SYSTEM = f"""You review a job posting for one candidate and report facts.
For every fact, copy a quote from the posting word for word (under 25 words). Use "" if the posting doesn't say.
Candidate: BS in Computer Science, graduated {GRADUATION}; no graduate degree; in the US; no security clearance.
- years_quote: the sentence giving the minimum years of professional experience REQUIRED (not preferred).
- seniority: level of THIS role, not teammates. "entry" for new grad/junior/early career; "mid" or "senior"
  only when the posting says so; otherwise "unclear".
- grad_start / grad_end: only if applicants must graduate within a window. Format YYYY-MM.
- degree_required: minimum degree REQUIRED. "bachelors_or_none" if a Bachelor's or equivalent experience is accepted.
- clearance: "active_required" only if the candidate must already hold one; "obtainable" if they can get one after hire.
- outside_us: true if the job must be done from outside the United States, including when its Location is a
  non-US city or country. Copy the location exactly as written into location_quote.
- field_excludes_cs: true only if the posting REQUIRES a degree in specific fields and none of them is
  Computer Science, Computer/Software Engineering, or a "related"/"technical" field
  (e.g. "BS in Mechanical or Electrical Engineering required"). Quote the field wording in field_quote.
- requirements: up to 6 required qualifications, each under 8 words, most important first."""


class Report(BaseModel):
    years_quote: str = ""
    seniority: Literal["entry", "mid", "senior", "unclear"] = "unclear"
    seniority_quote: str = ""
    grad_start: str | None = None
    grad_end: str | None = None
    grad_quote: str = ""
    degree_required: Literal["bachelors_or_none", "masters", "phd"] = "bachelors_or_none"
    degree_quote: str = ""
    clearance: Literal["none", "obtainable", "active_required"] = "none"
    clearance_quote: str = ""
    outside_us: bool = False
    location_quote: str = ""
    field_excludes_cs: bool = False
    field_quote: str = ""
    requirements: list[str] = []


TOOLS = {"tools": [{"toolSpec": {"name": "report", "description": "Report facts about the job posting.",
                                 "inputSchema": {"json": Report.model_json_schema()}}}],
         "toolChoice": {"tool": {"name": "report"}}}  # forces the model to answer through the tool


@lru_cache
def _client():
    return boto3.client("bedrock-runtime", region_name=config.aws_region(),
                        config=Config(retries={"max_attempts": 2, "mode": "adaptive"},
                                      connect_timeout=5, read_timeout=20))


def _norm(text: str) -> str:
    """Lowercase letters/numbers only, so punctuation and bullet differences don't matter."""
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", text.lower()).split())


def _ask(job: Job, store, day: str, client) -> Report:
    posting = f"Title: {job.title}\nLocation: {job.location}\n\n{trim_boilerplate(job.description)[:8000]}"
    response = client.converse(
        modelId=config.bedrock_model_id(), system=[{"text": SYSTEM}],
        messages=[{"role": "user", "content": [{"text": posting}]}],
        toolConfig=TOOLS, inferenceConfig={"maxTokens": 600, "temperature": 0})
    usage = response["usage"]
    micros = usage["inputTokens"] * 1 + usage["outputTokens"] * 5  # Haiku 4.5: $1 / $5 per million tokens
    store.add_llm_spend(day, micros)
    print(f"llm ${micros / 1e6:.4f} ({usage['inputTokens']} in / {usage['outputTokens']} out)")
    tool_use = next(block["toolUse"] for block in response["output"]["message"]["content"] if "toolUse" in block)
    return Report.model_validate(tool_use["input"])


def _in_window(start: str | None, end: str | None) -> bool:
    if start and _MONTH.match(start) and GRADUATION < start:
        return False
    if end and _MONTH.match(end) and GRADUATION > end:
        return False
    return True


def find_blocker(report: Report, job: Job) -> tuple[str, str] | None:
    """(channel, reason) for the first verified blocker, or None."""
    source = _norm(f"{job.title} {job.location} {trim_boilerplate(job.description)}")

    def verified(quote: str) -> bool:
        return len(_norm(quote)) >= 4 and _norm(quote) in source

    if verified(report.years_quote) and not is_preferred(report.years_quote):
        years = min_years(report.years_quote)
        if years is not None and years > MAX_YEARS:
            return "drop", f'{years}+ years required: "{report.years_quote[:200]}"'
    location = _norm(job.location)
    # The model often adds the country ("Milan" → "Milan, Italy"); accept a quote containing the job's location
    location_ok = verified(report.location_quote) or (
        bool(location) and "remote" not in location and location in _norm(report.location_quote))
    checks = [
        (report.seniority in ("mid", "senior"), report.seniority_quote, f"{report.seniority}-level role"),
        (not _in_window(report.grad_start, report.grad_end), report.grad_quote,
         f"graduation window excludes {GRADUATION}"),
        (report.degree_required != "bachelors_or_none", report.degree_quote, "graduate degree required"),
        (report.clearance == "active_required", report.clearance_quote, "active clearance required"),
        (report.outside_us and location_ok,
         report.location_quote if verified(report.location_quote) else job.location, "outside the US"),
        (report.field_excludes_cs and not _CS_FRIENDLY.search(report.field_quote), report.field_quote,
         "degree field excludes CS"),
    ]
    for failed, quote, label in checks:
        if failed and verified(quote):
            return "digest", f'{label}: "{quote[:200]}"'
    return None


def second_opinion(job: Job, decision: Decision, store, client=None) -> Decision:
    """Checks a job the rules would alert on. Falls back to the rules' decision on any problem."""
    day = datetime.now(PACIFIC).date().isoformat()
    if store.llm_spent(day) >= BUDGET_MICROS:
        decision.tags.append("⚙️ rules only (daily LLM budget reached)")
        return decision
    try:
        report = _ask(job, store, day, client or _client())
    except Exception as error:  # throttling, timeout, bad output → keep the rules' decision
        print(f"llm check failed for {job.key}: {error!r}")
        return decision

    blocker = find_blocker(report, job)
    if blocker:
        channel, reason = blocker
        return Decision(channel=channel, tags=decision.tags, reason=f"LLM: {reason}")
    if report.clearance == "obtainable" and "🔒 clearance obtainable" not in decision.tags:
        decision.tags.append("🔒 clearance obtainable")
    if report.requirements:
        decision.tags.append("📋 Requires: " + " · ".join(item.strip() for item in report.requirements[:6]))
    return decision