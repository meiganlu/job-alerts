"""A free check on the description, before the LLM call: an obviously required 3+ years."""
import re

_YEARS = re.compile(r"(\d{1,2})\s*(?:\+|-\s*\d{1,2}|to\s+\d{1,2})?\s*(?:or more\s+)?years?", re.IGNORECASE)
_SOFT = re.compile(r"prefer|nice to have|bonus|ideal|a plus|desired", re.IGNORECASE)
_HARD = re.compile(r"minimum|at least|required|must", re.IGNORECASE)
_REQUIRED_HEADING = re.compile(r"requir|qualif|minimum|basic|must|you have|what you", re.IGNORECASE)


def obvious_years_required(description: str, minimum: int = 3) -> tuple[int, str] | None:
    """Returns (years, quote) only when a requirement plainly asks for `minimum`+ years
    of experience. Anything ambiguous returns None and is left to the LLM."""
    in_preferred = False
    for line in description.splitlines():
        stripped = line.strip()
        if 0 < len(stripped) < 60 and not stripped.endswith("."):  # looks like a heading
            if _SOFT.search(stripped):
                in_preferred = True
            elif _REQUIRED_HEADING.search(stripped):
                in_preferred = False
        if in_preferred and not _HARD.search(stripped):
            continue  # soft section, unless this line says it's required
        for sentence in re.split(r"(?<=[.!?;])\s+", stripped):
            if "experience" not in sentence.lower() or _SOFT.search(sentence):
                continue
            numbers = [int(match.group(1)) for match in _YEARS.finditer(sentence)]
            if numbers and min(numbers) >= minimum:  # every option asks for 3+
                return min(numbers), sentence[:200]
    return None