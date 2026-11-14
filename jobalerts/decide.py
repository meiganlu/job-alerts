"""Turns verified job facts into a channel, a readable reason, and tags."""
from typing import Literal

from pydantic import BaseModel

from jobalerts.extract import Extraction
from jobalerts.filters import CRITERIA, is_bay_area
from jobalerts.models import Job

RULES = CRITERIA["decision"]
POINTS = {"met": 1.0, "partial": 0.5, "not_met": 0.0}


class Decision(BaseModel):
    channel: Literal["apply_now", "maybe", "digest", "drop"]
    reason: str
    score: float | None = None
    tags: list[str] = []


def qualification_score(facts: Extraction) -> float | None:
    """Share of required hard skills met (partial = half). None if nothing to score."""
    items = [r for r in facts.requirements if r.kind == "hard" and r.importance == "required"]
    if not items:
        items = [r for r in facts.requirements if r.kind == "hard"]  # fall back to all hard skills
    if not items:
        return None
    return sum(POINTS[r.status] for r in items) / len(items)


def grad_fits(facts: Extraction, graduation: str) -> bool:
    """True if my graduation date falls inside the posting's window (open ends allowed)."""
    if facts.grad_start and graduation < facts.grad_start:
        return False
    if facts.grad_end and graduation > facts.grad_end:
        return False
    return True


def decide(facts: Extraction, job: Job) -> Decision:
    score = qualification_score(facts)

    tags = []
    if is_bay_area(job.location):
        tags.append("⭐ Bay Area")
    if not grad_fits(facts, RULES["graduation"]):
        tags.append(f"⚠️ grad window: {facts.grad_start or 'any'} to {facts.grad_end or 'any'}")
    if facts.clearance == "obtainable":
        tags.append("🔒 clearance sponsored")
    if facts.domain == "ai_research":
        tags.append("🔬 research role")

    # Hard stops
    if facts.years_required is not None and facts.years_required > RULES["max_years_required"]:
        return Decision(channel="drop", score=score, tags=tags,
                        reason=f'{facts.years_required}+ years required: "{facts.years_required_quote}"')
    if facts.domain in RULES["drop_domains"]:
        return Decision(channel="drop", score=score, tags=tags,
                        reason=f'{facts.domain} role: "{facts.domain_quote}"')
    if facts.clearance == "active_required":
        return Decision(channel="digest", score=score, tags=tags,
                        reason=f'active clearance required: "{facts.clearance_quote}"')
    if facts.years_preferred is not None and facts.years_preferred >= RULES["maybe_if_years_preferred"]:
        return Decision(channel="maybe", score=score, tags=tags + ["🔍 check qualifications closely"],
                        reason=f'{facts.years_preferred}+ years preferred: "{facts.years_preferred_quote}"')

    # Score decides the Discord channel
    if score is None:
        return Decision(channel="maybe", tags=tags, reason="no checkable requirements found")
    if score >= RULES["apply_now_score"]:
        channel = "apply_now"
    elif score >= RULES["maybe_score"]:
        channel = "maybe"
    else:
        channel = "digest"
    return Decision(channel=channel, score=score, tags=tags,
                    reason=f"meets {score:.0%} of required qualifications")