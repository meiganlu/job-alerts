"""Helpers for identifying companies consistently across sources."""

CASE_SENSITIVE = {"lever"}  # Lever slugs are case-sensitive; Greenhouse and Ashby aren't


def normalize_slug(ats: str, slug: str) -> str:
    """'Affirm' and 'affirm' are the same Greenhouse board, so store one spelling."""
    slug = slug.strip()
    return slug if ats in CASE_SENSITIVE else slug.lower()


def company_id(ats: str, slug: str) -> str:
    """A unique ID per board, e.g. 'greenhouse:affirm'."""
    return f"{ats}:{normalize_slug(ats, slug)}"