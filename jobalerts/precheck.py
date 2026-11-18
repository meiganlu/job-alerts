"""Free checks on a job description: years of experience, stated as numbers or words."""
import re

from jobalerts.text import qualifications_part

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                 "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15}
_WORD_NUMBER = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)
_PAREN_REPEAT = re.compile(r"(\d+)\s*\(\s*\d+\s*\)")  # "5 (5)" → "5"
_YEARS = re.compile(r"(\d{1,2})\s*(?:\+|-?\s*plus|-\s*\d{1,2}|to\s+\d{1,2})?\s*(?:or more\s+)?years?",
                    re.IGNORECASE)
_SOFT = re.compile(r"prefer|nice to have|bonus|ideal|a plus|desired", re.IGNORECASE)
_SOFT_WHOLE = re.compile(r"\bpreferred\b|nice to have|bonus|a plus|desired", re.IGNORECASE)
_HARD = re.compile(r"minimum|at least|required|must", re.IGNORECASE)
_REQUIRED_HEADING = re.compile(r"requir|qualif|minimum|basic|must|you have|what you", re.IGNORECASE)
# "N years in/of/building …" counts as work experience even without the word "experience"
_YEARS_AT_WORK = re.compile(
    r"years?\s+(?:of\s+)?(?:[\w-]+\s+){0,2}(?:in|building|developing|development|working|"
    r"writing|designing|shipping|professional|industry|software|engineering|coding|programming|hands-on)\b",
    re.IGNORECASE)
_EDUCATION = re.compile(r"coursework|course|degree|study|studies|school|universit|college|graduat|academic",
                        re.IGNORECASE)
_ABOUT_COMPANY = re.compile(r"\b(we|we've|we're|our|founded)\b", re.IGNORECASE)
_ABOUT_CANDIDATE = re.compile(r"\b(you|your|candidates?|applicants?|requir\w*|minimum|at least|must)\b",
                              re.IGNORECASE)


def normalize_numbers(text: str) -> str:
    """'five (5) years' → '5 years', 'three years' → '3 years'."""
    text = _WORD_NUMBER.sub(lambda match: str(_NUMBER_WORDS[match.group(1).lower()]), text)
    return _PAREN_REPEAT.sub(r"\1", text)


def _looks_like_heading(line: str) -> bool:
    """'Preferred Qualifications', 'Nice to have:' — short, no period, no numbers.
    A short bullet like '4+ years of experience, preferably in fintech' is not a heading."""
    return (0 < len(line) < 60 and not line.endswith(".") and len(line.split()) <= 6
            and not re.search(r"\d", line))


def _section_sentences(description: str):
    """Yields (sentence, section_soft): section_soft = under a 'Preferred…' heading."""
    in_preferred = False
    for line in normalize_numbers(description).splitlines():
        stripped = line.strip()
        if _looks_like_heading(stripped):
            if _SOFT.search(stripped):
                in_preferred = True
            elif _REQUIRED_HEADING.search(stripped):
                in_preferred = False
        section_soft = in_preferred and not _HARD.search(stripped)
        for sentence in re.split(r"(?<=[.!?;])\s+", stripped):
            if sentence:
                yield sentence, section_soft


def sentences(description: str):
    """Yields (sentence, soft) for every sentence. 'soft' = preferred / nice-to-have."""
    for sentence, section_soft in _section_sentences(description):
        yield sentence, section_soft or bool(_SOFT.search(sentence))


def _years_soft(sentence: str, section_soft: bool, first_number_at: int) -> bool:
    """Is this years sentence a preference? "4+ years preferred" and "Ideally 4+ years" are;
    "Minimum of 4 years…, ideally supporting executives" and "4+ years, preferably in fintech" aren't."""
    if section_soft:
        return True
    if _HARD.search(sentence):
        return False
    if _SOFT_WHOLE.search(sentence):
        return True
    return bool(_SOFT.search(sentence[:first_number_at]))  # "preferably/ideally" only before the number


def _required_years(sentence: str, matches: list) -> int:
    """The years a sentence requires. Options joined by "or" → the smallest one counts
    ("BS and 3 years, or MS and 1 year" → 1). Otherwise the first number is the main
    requirement ("4 years…, including 2 years supporting executives" → 4)."""
    numbers = [int(match.group(1)) for match in matches]
    if re.search(r"\bor\b", sentence[matches[0].start():], re.IGNORECASE):
        return min(numbers)
    return numbers[0]


def _about_experience(sentence: str) -> bool:
    if "experience" in sentence.lower():
        return True
    return bool(_YEARS_AT_WORK.search(sentence)) and not _EDUCATION.search(sentence)


def _years(description: str, minimum: int, want_soft: bool) -> tuple[int, str] | None:
    for sentence, section_soft in _section_sentences(qualifications_part(description)):
        matches = list(_YEARS.finditer(sentence))
        if not matches or not _about_experience(sentence):
            continue
        if _years_soft(sentence, section_soft, matches[0].start()) != want_soft:
            continue
        if _ABOUT_COMPANY.search(sentence) and not _ABOUT_CANDIDATE.search(sentence):
            continue  # "Our team has 15 years of experience…" describes the company
        years = _required_years(sentence, matches)
        if years >= minimum:
            return years, sentence[:200]
    return None


def obvious_years_required(description: str, minimum: int = 3) -> tuple[int, str] | None:
    return _years(description, minimum, want_soft=False)


def years_preferred(description: str, minimum: int = 3) -> tuple[int, str] | None:
    return _years(description, minimum, want_soft=True)


def min_years(sentence: str) -> int | None:
    """Years one sentence requires ('2-4 years' → 2), or None."""
    sentence = normalize_numbers(sentence)
    matches = list(_YEARS.finditer(sentence))
    return _required_years(sentence, matches) if matches else None


def is_preferred(sentence: str) -> bool:
    """True for 'preferred' / 'nice to have' wording."""
    return bool(_SOFT.search(sentence))