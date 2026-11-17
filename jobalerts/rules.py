"""Rule-based decisions: routes each new job using explicit facts in its posting."""
import re

from jobalerts.decide import RULES, Decision
from jobalerts.filters import CRITERIA, LEVEL_I, is_bay_area, is_early_career
from jobalerts.models import Job
from jobalerts.precheck import obvious_years_required, sentences, years_preferred
from jobalerts.text import trim_boilerplate

_ACTIVE_CLEARANCE = re.compile(
    r"\b(active|current)\b[^.\n]{0,40}\b(secret|top secret|ts/sci|ts|clearance)\b", re.IGNORECASE)
_OBTAIN_CLEARANCE = re.compile(
    r"\b(obtain|eligible|eligibility)\b[^.\n]{0,40}\bclearance\b", re.IGNORECASE)
_GRAD_DEGREE = re.compile(r"\b(master'?s|m\.s\.|ph\.?d|doctorate)", re.IGNORECASE)
_UNDERGRAD = re.compile(r"\b(bachelor'?s|b\.s\.|b\.a\.|undergraduate|equivalent)", re.IGNORECASE)
_REQUIRED_WORD = re.compile(r"\b(required|requires?|must|minimum)\b", re.IGNORECASE)
_LEVEL_WORDING = re.compile(r"\b(mid[- ]level|senior[- ]level|mid[- ]senior)\b", re.IGNORECASE)
_ALWAYS_MAYBE = [phrase.lower() for phrase in CRITERIA["decision"].get("always_maybe_titles", [])]

# Technology names: display spelling by lowercase name, plus aliases
_TECH = {name.lower(): name for name in CRITERIA["technologies"]}
_ALIASES = {alias.lower(): name for alias, name in CRITERIA.get("tech_aliases", {}).items()}
_MY_SKILLS = {name.lower() for name in CRITERIA["my_skills"]}
_TECH_PATTERN = re.compile(
    r"(?<!\w)(" + "|".join(re.escape(name) for name in
                           sorted(set(_TECH) | set(_ALIASES), key=len, reverse=True)) + r")(?!\w)",
    re.IGNORECASE)


def _snippet(pattern: re.Pattern, text: str) -> str | None:
    """The words around the first match, for the reason line."""
    match = pattern.search(text)
    if not match:
        return None
    return " ".join(text[max(0, match.start() - 60): match.end() + 60].split())


def tech_split(text: str) -> tuple[list[str], list[str]]:
    """(technologies you know, technologies new to you) mentioned in the posting."""
    found = []
    for match in _TECH_PATTERN.finditer(text):
        word = match.group(1).lower()
        name = _ALIASES.get(word) or _TECH.get(word)
        if name and name not in found:
            found.append(name)
    known = [name for name in found if name.lower() in _MY_SKILLS]
    new = [name for name in found if name.lower() not in _MY_SKILLS]
    return known, new


def graduate_degree_required(text: str) -> str | None:
    """A required Master's/PhD with no Bachelor's or 'equivalent' alternative in the same sentence."""
    for sentence, soft in sentences(text):
        if (not soft and _GRAD_DEGREE.search(sentence) and _REQUIRED_WORD.search(sentence)
                and not _UNDERGRAD.search(sentence)):
            return sentence[:200]
    return None


def classify(job: Job) -> Decision:
    text = trim_boilerplate(job.description)
    tags = ["⭐ Bay Area"] if is_bay_area(job.location) else []

    # Hard stops
    years = obvious_years_required(text, RULES["max_years_required"] + 1)
    if years:
        return Decision(channel="drop", tags=tags, reason=f'{years[0]}+ years required: "{years[1]}"')
    for pattern, label in ((_ACTIVE_CLEARANCE, "active clearance required"),
                           (_LEVEL_WORDING, "mid/senior-level role")):
        snippet = _snippet(pattern, text)
        if snippet:
            return Decision(channel="digest", tags=tags, reason=f'{label}: "{snippet}"')
    degree = graduate_degree_required(text)
    if degree:
        return Decision(channel="digest", tags=tags, reason=f'graduate degree required: "{degree}"')

    # Information for the card
    if _OBTAIN_CLEARANCE.search(text):
        tags.append("🔒 clearance obtainable")
    preferred = years_preferred(text)
    if preferred:
        tags.append(f"🔍 {preferred[0]}+ years preferred")
    known, new = tech_split(text)
    if known:
        tags.append("🌿 You know: " + ", ".join(known[:6]))
    if new:
        tags.append("🚩 New to you: " + ", ".join(new[:6]))

    # Routing
    title = job.title.lower()
    if any(phrase in title for phrase in _ALWAYS_MAYBE):
        return Decision(channel="maybe", tags=tags, reason="customer-facing role: check the qualifications")
    if is_early_career(job.title) or LEVEL_I.search(job.title):
        return Decision(channel="apply_now", tags=tags, reason="early-career title")
    return Decision(channel="maybe", tags=tags, reason="no early-career title; experience within your range")