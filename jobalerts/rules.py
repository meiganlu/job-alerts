"""Rule-based decisions: routes each new job using explicit facts in its posting."""
import re

from jobalerts.decide import RULES, Decision
from jobalerts.filters import CRITERIA, LEVEL_I, is_bay_area, is_early_career
from jobalerts.models import Job
from jobalerts.precheck import obvious_years_required, sentences, years_preferred
from jobalerts.text import trim_boilerplate

# A clearance the candidate must ALREADY hold: a clearance word plus "active/hold/must/required…",
# unless the same sentence says they can obtain one, or that none is needed
_CLEARANCE_TERM = re.compile(r"\b(clearance|ts/sci|top secret|polygraph)\b", re.IGNORECASE)
_HOLD_WORD = re.compile(r"\b(active|current\w*|existing|hold\w*|possess\w*|have|has|requir\w*|must)\b|clearance:",
                        re.IGNORECASE)
_OBTAIN_WORD = re.compile(r"\b(obtain\w*|eligib\w*|acquire|sponsor\w*|willing|able to get)\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(no|not|without|never)\b", re.IGNORECASE)
_OBTAIN_CLEARANCE = re.compile(
    r"\b(obtain|eligible|eligibility)\b[^.\n]{0,40}\bclearance\b", re.IGNORECASE)
_NOT_FULL_TIME = re.compile(r"\b(part[- ]time|freelance\w*|temporary|seasonal)\b", re.IGNORECASE)
_FULL_TIME = re.compile(r"\bfull[- ]time\b", re.IGNORECASE)
_BENEFITS = re.compile(r"\b(benefits?|employees|eligible)\b", re.IGNORECASE)  # "Benefits for temporary employees"
# The posting itself says the role is early-career ("0-2 years…; entry-level candidate")
_EARLY_WORDING = re.compile(
    r"\b(entry[- ]level|new grad(uate)?s?|recent (college )?grad(uate)?s?|early[- ]career)\b"
    r"|\b0\s*(-|to)\s*[12]\s*years?\b|\b0\+?\s*years?\b", re.IGNORECASE)
_MENTOR = re.compile(r"\b(mentor\w*|coach\w*|onboard\w*)\b", re.IGNORECASE)  # "you'll mentor new grads"
_GRAD_DEGREE = re.compile(r"\b(master'?s|m\.s\.|ph\.?d|doctorate)", re.IGNORECASE)
_UNDERGRAD = re.compile(r"\b(bachelor'?s|b\.s\.|b\.a\.|undergraduate|equivalent)", re.IGNORECASE)
_REQUIRED_WORD = re.compile(r"\b(required|requires?|must|minimum)\b", re.IGNORECASE)
# The role's own level, not teammates': "a mid-level engineer" counts, "senior-level engineers" doesn't
_LEVEL_WORDING = re.compile(
    r"\b(mid[- ]level|senior[- ]level|mid[- ]senior)\b"
    r"(?!\s+(?:\w+\s+)?(?:engineers|developers|colleagues|teammates|peers|mentors|leaders|staff))",
    re.IGNORECASE)
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


def active_clearance(text: str) -> str | None:
    """A sentence requiring an active clearance, unless it says the candidate can obtain one."""
    for sentence, soft in sentences(text):
        if (not soft and _CLEARANCE_TERM.search(sentence) and _HOLD_WORD.search(sentence)
                and not _OBTAIN_WORD.search(sentence) and not _NEGATION.search(sentence)):
            return sentence[:200]
    return None


def not_full_time(text: str) -> str | None:
    """A sentence saying the job is part-time, freelance, or temporary (and not also full-time)."""
    for sentence, _ in sentences(text):
        if (_NOT_FULL_TIME.search(sentence) and not _FULL_TIME.search(sentence)
                and not _BENEFITS.search(sentence)):
            return sentence[:200]
    return None


def early_career_wording(text: str) -> str | None:
    """A sentence where the posting calls the role entry-level / early-career / 0-2 years."""
    for sentence, _ in sentences(text):
        if (_EARLY_WORDING.search(sentence) and not _NEGATION.search(sentence)
                and not _MENTOR.search(sentence)):
            return sentence[:200]
    return None


def level_wording(text: str) -> str | None:
    return _snippet(_LEVEL_WORDING, text)


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
    for check, label in ((not_full_time, "not full-time"),
                         (active_clearance, "active clearance required"),
                         (level_wording, "mid/senior-level role"),
                         (graduate_degree_required, "graduate degree required")):
        found = check(text)
        if found:
            return Decision(channel="digest", tags=tags, reason=f'{label}: "{found}"')

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
    wording = early_career_wording(text)
    if wording:
        return Decision(channel="apply_now", tags=tags, reason=f'early-career per posting: "{wording}"')
    return Decision(channel="maybe", tags=tags, reason="no early-career title; experience within your range")