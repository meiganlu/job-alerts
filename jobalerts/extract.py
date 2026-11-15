"""Asks the LLM to pull facts out of a job posting, then verifies its quotes."""
import re
from pathlib import Path
from typing import Literal

import boto3
from pydantic import BaseModel

from jobalerts import config
from jobalerts.models import Job
from jobalerts.text import trim_boilerplate

RESUME_FILE = Path(__file__).parent.parent / "resume.txt"
TOOL_NAME = "record_job_facts"

SYSTEM_PROMPT = """You extract facts from a job posting for a new-grad software engineer.
Rules:
- Use only what the posting states. Every quote must be copied exactly from the posting.
- years_required: minimum years of professional experience REQUIRED. For a range like
  "0-2 years", use the lower number. If none is stated, use null.
- years_preferred: minimum years listed as preferred or nice-to-have, else null.
- A degree "or equivalent experience" is not a years requirement.
- grad_start / grad_end: the earliest and latest graduation dates the posting accepts, as
  YYYY-MM. "By August 2027" -> grad_start null, grad_end "2027-08". "2025 or 2026
  graduates" -> "2025-01" to "2026-12". Both null if no graduation window is stated.
- domain: "mobile" or "ai_research" ONLY if the job TITLE itself shows it (e.g. "iOS
  Engineer", "Research Scientist"), with domain_quote copied from the title. Building ML
  infrastructure or platforms is "general". Otherwise "general".
- clearance: "active_required" only if an ACTIVE clearance is required, "obtainable" if the
  candidate must be able to obtain one, otherwise "none".
- requirements: list EVERY qualification in the posting's requirements sections (often
  titled "Requirements", "Qualifications", "What you'll need", "Who you are", "Preferred",
  "Nice to have"). Do NOT include job duties or responsibilities (sections like "What
  you'll do", "Responsibilities", "In this role you will"). For each:
  - requirement: the full qualification, copied exactly.
    One entry per bullet: never split one bullet into several entries or merge several into one.
  - importance: "preferred" if the posting marks it preferred, nice-to-have, a plus, or a
    bonus; otherwise "required"
  - kind: "soft" for personality, interest, passion, curiosity, or communication;
    otherwise "hard"
  - status: rate against the resume as "met", "partial", or "not_met". Count related
    experience generously (JavaScript counts toward TypeScript). A skill listed on the
    resume but not shown in projects or experience counts as at least "partial".
    If a requirement pairs a skill area with a specific language or tool (e.g. "backend
    applications in Java"), and the resume shows that skill area in another language plus
    some exposure to the named one, rate it "partial".
  - evidence: a reason from the resume in 10 words or fewer.
- Each *_quote must include the number or date it supports (e.g. "by August 2027").
- Leave every *_quote field empty ("") when its value is null, "general", or "none"."""


class Requirement(BaseModel):
    requirement: str  # quoted from the posting
    importance: Literal["required", "preferred"]
    kind: Literal["hard", "soft"]  # hard = checkable skill/experience; soft = personality/interest
    status: Literal["met", "partial", "not_met"]
    evidence: str = ""


class Extraction(BaseModel):
    years_required: int | None = None
    years_required_quote: str = ""
    years_preferred: int | None = None
    years_preferred_quote: str = ""
    grad_start: str | None = None  # "YYYY-MM"
    grad_end: str | None = None  # "YYYY-MM"
    grad_quote: str = ""
    domain: Literal["general", "mobile", "ai_research"] = "general"
    domain_quote: str = ""
    clearance: Literal["none", "obtainable", "active_required"] = "none"
    clearance_quote: str = ""
    requirements: list[Requirement] = []


def build_prompt(job: Job) -> str:
    """The part that changes per job. The resume lives in the cached system prompt."""
    return (
        f"JOB POSTING:\nTitle: {job.title}\nCompany: {job.company}\n"
        f"Location: {job.location}\n\n{trim_boilerplate(job.description)}"
    )


def parse_response(response: dict) -> Extraction:
    """Pulls the facts out of Bedrock's reply and checks they match the expected shape."""
    for block in response["output"]["message"]["content"]:
        if "toolUse" in block:
            return Extraction.model_validate(block["toolUse"]["input"])
    raise ValueError("The model did not return job facts")


def extract(job: Job) -> Extraction:
    """Sends one job to the LLM and returns the facts it found (not yet verified)."""
    client = boto3.client("bedrock-runtime", region_name=config.aws_region())
    response = client.converse(
        modelId=config.bedrock_model_id(),
        system=[
            {"text": SYSTEM_PROMPT},
            {"text": f"RESUME:\n{RESUME_FILE.read_text()}"},
            {"cachePoint": {"type": "default"}},  # everything above is cached between calls
        ],
        messages=[{"role": "user", "content": [{"text": build_prompt(job)}]}],
        toolConfig={
            "tools": [
                {
                    "toolSpec": {
                        "name": TOOL_NAME,
                        "description": "Record the facts extracted from the job posting.",
                        "inputSchema": {"json": Extraction.model_json_schema()},
                    }
                }
            ],
            "toolChoice": {"tool": {"name": TOOL_NAME}},
        },
        inferenceConfig={"maxTokens": 3000, "temperature": 0},
    )
    print("tokens:", response["usage"])  # shows cost per call in logs
    return parse_response(response)


# --- Quote verification ---


def _normalize(text: str) -> str:
    """Lowercase, straighten curly quotes and dashes, collapse whitespace."""
    text = text.lower()
    for fancy, plain in [("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'),
                         ("\u201d", '"'), ("\u2013", "-"), ("\u2014", "-")]:
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text).strip()


def quote_found(quote: str, text: str) -> bool:
    return bool(quote.strip()) and _normalize(quote) in _normalize(text)


def verify(facts: Extraction, job: Job) -> Extraction:
    """Returns a copy where any fact without a real quote is reset to its safe default."""
    posting = f"{job.title}\n{job.description}"
    checked = facts.model_copy(deep=True)

    if checked.years_required is not None and not quote_found(checked.years_required_quote, posting):
        checked.years_required = None
    if checked.years_preferred is not None and not quote_found(checked.years_preferred_quote, posting):
        checked.years_preferred = None
    if (checked.grad_start or checked.grad_end) and not quote_found(checked.grad_quote, posting):
        checked.grad_start = checked.grad_end = None

    if checked.domain == "ai_research" and "research" not in checked.domain_quote.lower():
        checked.domain = "general"
    
    # A domain can only cause a drop if the evidence is in the TITLE
    if checked.domain != "general" and not quote_found(checked.domain_quote, job.title):
        checked.domain = "general"
    if checked.clearance != "none" and not quote_found(checked.clearance_quote, posting):
        checked.clearance = "none"
    checked.requirements = [r for r in checked.requirements if quote_found(r.requirement, posting)]
    return checked