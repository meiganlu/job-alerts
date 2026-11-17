"""Turns HTML from job sites into clean plain text."""
import html
import re

from bs4 import BeautifulSoup


def html_to_text(raw: str) -> str:
    """Converts HTML into readable lines of text."""
    if not raw:
        return ""
    soup = BeautifulSoup(html.unescape(raw), "html.parser")
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


# Headings that start the qualifications part of a posting
_QUALIFICATION_HEADINGS = re.compile(
    r"qualifications|requirements|what you.ll need|who you are|you have|"
    r"what we.re looking for|nice to have|preferred",
    re.IGNORECASE,
)


# Headings of end-of-posting sections that don't affect fit
_END_HEADINGS = re.compile(
    r"^(benefits|perks|compensation|pay range|salary|what we offer|"
    r"equal (employment )?opportunity|eeo|accommodation|our commitment)",
    re.IGNORECASE,
)


def trim_boilerplate(text: str) -> str:
    """Cuts end-of-posting sections (benefits, EEO, accommodations) that come
    AFTER the qualifications. Anything before the qualifications is never cut."""
    lines = text.splitlines()
    last_qualification = max(
        (i for i, line in enumerate(lines) if len(line) < 80 and _QUALIFICATION_HEADINGS.search(line)),
        default=-1,
    )
    for i, line in enumerate(lines):
        if i > last_qualification and len(line) < 80 and _END_HEADINGS.match(line.strip()):
            return "\n".join(lines[:i])
    return text


def qualifications_part(text: str) -> str:
    """The posting from its first qualifications heading on (the whole text if there's none),
    so years in the company intro ("20 years of experience serving customers") aren't read."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if len(line) < 80 and _QUALIFICATION_HEADINGS.search(line):
            return "\n".join(lines[i:])
    return text
