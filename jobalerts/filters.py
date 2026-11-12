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
NON_US_MARKERS = _word_pattern(CRITERIA["non_us_markers"])
BAY_AREA = _word_pattern(CRITERIA["bay_area"])


def title_in_scope(title: str) -> bool:
    text = title.lower()
    for phrase in TITLE_ALLOW:
        # Swap allowed titles for a neutral in-scope word, so "staff" inside
        # "member of technical staff" isn't treated as senior
        text = text.replace(phrase, "software")
    return bool(TITLE_INCLUDE.search(text)) and not TITLE_EXCLUDE.search(text)


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


def passes_rule_filter(job: Job) -> bool:
    return title_in_scope(job.title) and location_in_scope(job.location)