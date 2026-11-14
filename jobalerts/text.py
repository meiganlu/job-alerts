"""Turns HTML from job sites into clean plain text."""
import html

from bs4 import BeautifulSoup


def html_to_text(raw: str) -> str:
    """Converts HTML into readable lines of text."""
    if not raw:
        return ""
    soup = BeautifulSoup(html.unescape(raw), "html.parser")
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)