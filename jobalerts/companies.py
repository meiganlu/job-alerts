"""Helpers for identifying companies consistently across sources."""
import boto3

from jobalerts import config


CASE_SENSITIVE = {"lever"}  # Lever slugs are case-sensitive; Greenhouse and Ashby aren't


def normalize_slug(ats: str, slug: str) -> str:
    """'Affirm' and 'affirm' are the same Greenhouse board, so store one spelling."""
    slug = slug.strip()
    return slug if ats in CASE_SENSITIVE else slug.lower()


def company_id(ats: str, slug: str) -> str:
    """A unique ID per board, e.g. 'greenhouse:affirm'."""
    return f"{ats}:{normalize_slug(ats, slug)}"


def companies_table():
    return boto3.resource("dynamodb", region_name=config.aws_region()).Table("job-alerts-companies")


def load_all(table) -> list[dict]:
    """Every stored company, favorites first. Reads the table page by page."""
    items, kwargs = [], {}
    while True:
        page = table.scan(**kwargs)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return sorted(items, key=lambda company: not company.get("favorite", False))