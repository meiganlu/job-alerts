"""Free, instant checks that drop obvious mismatches before the LLM step."""
import re
from pathlib import Path

import yaml

from jobalerts.models import Job

CRITERIA_FILE = Path(__file__).parent.parent / "criteria.yaml"
CRITERIA = yaml.safe_load(CRITERIA_FILE.read_text())


def _word_pattern(words: list[str]) -> re.Pattern:
    """One search pattern that matches any of the words as standalone words, any case."""
    alternatives = "|".join(re.escape(word) for word in words)
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


# Built once when the program starts, then reused for every job
TITLE_ALLOW = [phrase.lower() for phrase in CRITERIA["title_allow"]]
TITLE_INCLUDE = _word_pattern(CRITERIA["title_include"])
TITLE_EXCLUDE = _word_pattern(CRITERIA["title_exclude"])
US_MARKERS = _word_pattern(CRITERIA["us_markers"])
US_STATE_CODES = re.compile(
    rf",\s*(?:{'|'.join(CRITERIA['us_state_codes'])})(?!\w)", re.IGNORECASE
)
NON_US_MARKERS = _word_pattern(CRITERIA["non_us_markers"] + CRITERIA.get("non_us_countries", []))
BAY_AREA = _word_pattern(CRITERIA["bay_area"])
EARLY_CAREER = _word_pattern(CRITERIA["early_career"])
LEVEL_I = _word_pattern(["i"])
LEVEL_II = _word_pattern(["ii"])
LEVEL_II_ENTRY_COMPANIES = {name.lower() for name in CRITERIA["level_ii_entry_companies"]}
COMPANY_EXCLUDE = {name.lower() for name in CRITERIA.get("company_exclude", [])}
# QA words alone also describe non-software QA ("Video and Audio QA"), so they need a software word too
QA_WORDS = _word_pattern(["qa", "quality assurance", "tester", "test automation"])
SOFTWARE_CONTEXT = _word_pattern(["software", "automation", "sdet", "engineer", "engineering", "developer", "tester"])


def title_in_scope(title: str) -> bool:
    text = title.lower()
    for phrase in TITLE_ALLOW:
        # Swap allowed titles for a neutral in-scope word, so "staff" inside
        # "member of technical staff" isn't treated as senior
        text = text.replace(phrase, "software engineer")
    if not TITLE_INCLUDE.search(text) or TITLE_EXCLUDE.search(text):
        return False
    if not TITLE_INCLUDE.search(QA_WORDS.sub(" ", text)):  # in scope only because of a QA word
        return bool(SOFTWARE_CONTEXT.search(text))
    return True


def _is_us(part: str) -> bool:
    return bool(US_MARKERS.search(part) or US_STATE_CODES.search(part))


def location_in_scope(location: str) -> bool:
    """Keeps a job if any of its listed locations is US or unclear."""
    if not location.strip():
        return True  # no location given: keep it, decide later
    for part in re.split(r"[;|]", location):
        if _is_us(part) or not NON_US_MARKERS.search(part):
            return True
    return False


def is_bay_area(location: str) -> bool:
    return bool(BAY_AREA.search(location))


def is_early_career(title: str) -> bool:
    return bool(EARLY_CAREER.search(title))


def level_in_scope(job: Job) -> bool:
    """'II' titles are kept only if early-career, a combined 'I/II' posting, or at a company where II is the entry level."""
    if not LEVEL_II.search(job.title):
        return True
    return bool(
        LEVEL_I.search(job.title)
        or is_early_career(job.title)
        or job.company.lower() in LEVEL_II_ENTRY_COMPANIES
        or job.board.lower() in LEVEL_II_ENTRY_COMPANIES
    )


def passes_rule_filter(job: Job) -> bool:
    if job.company.lower() in COMPANY_EXCLUDE or job.board.lower() in COMPANY_EXCLUDE:
        return False
    return title_in_scope(job.title) and level_in_scope(job) and location_in_scope(job.location)