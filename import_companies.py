"""Loads public company directories and my favs into DynamoDB.
Safe to re-run: companies already stored (and their progress) are never overwritten.

Sources:
- LastRound AI ATS Company Directory (CC BY 4.0),
  https://lastroundai.com/blog/salary-transparency-study-2026
- datakit457/ats-company-slugs (CC0), https://github.com/datakit457/ats-company-slugs
"""
import csv
import io
from datetime import datetime, timezone

import boto3
import httpx
import yaml

from jobalerts import config
from jobalerts.companies import company_id, normalize_slug

# Each directory: where to download it, and which columns hold the platform, slug, and name
DIRECTORIES = [
    {
        "name": "LastRound AI",
        "url": "https://datahub.io/lastroundai-hiring-data/lastroundai-hiring-data/_r/-/"
               "ats-directory/lastroundai-ats-company-directory-2026-08.csv",
        "ats_column": "ats_vendor",
        "slug_column": "board_slug",
        "name_column": "company_name",
    },
    {
        "name": "datakit457",
        "url": "https://raw.githubusercontent.com/datakit457/ats-company-slugs/main/data/boards.csv",
        "ats_column": "ats",
        "slug_column": "slug",
        "name_column": "company",
        "ok_column": "board_ok",  # skip boards the list found dead
    },
]
SUPPORTED = {"greenhouse", "lever", "ashby"}

table = boto3.resource("dynamodb", region_name=config.aws_region()).Table("job-alerts-companies")
now = datetime.now(timezone.utc).isoformat()


def add_company(ats: str, slug: str, name: str, favorite: bool) -> bool:
    """Adds a company if it isn't already stored. Returns True if it was new."""
    try:
        table.put_item(
            Item={
                "company_id": company_id(ats, slug),
                "ats": ats,
                "slug": normalize_slug(ats, slug),
                "name": name,
                "favorite": favorite,   # favorites are checked first in every run
                "baselined": False,     # first check marks current jobs seen, no alerts
                "added_at": now,
            },
            ConditionExpression="attribute_not_exists(company_id)",
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False


# Public directories
for directory in DIRECTORIES:
    print(f"Downloading {directory['name']}...")
    response = httpx.get(directory["url"], timeout=60, follow_redirects=True)
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text)))
    added = 0
    for i, row in enumerate(rows, start=1):
        ats = row[directory["ats_column"]].strip().lower()
        ok_column = directory.get("ok_column")
        if ok_column and row[ok_column].strip().lower() != "true":
            continue  # the source marks this board as dead
        if ats in SUPPORTED:
            added += add_company(ats, row[directory["slug_column"]],
                                 row[directory["name_column"]], favorite=False)
        if i % 1000 == 0:
            print(f"  {i}/{len(rows)} checked, {added} new")
    print(f"{directory['name']}: {added} new companies")

# My favs (added if missing, marked favorite either way)
with open("companies.yaml") as f:
    favorites = yaml.safe_load(f)["companies"]
for favorite in favorites:
    ats, slug = favorite["source"], favorite["slug"]
    add_company(ats, slug, slug, favorite=True)
    table.update_item(
        Key={"company_id": company_id(ats, slug)},
        UpdateExpression="SET favorite = :yes",
        ExpressionAttributeValues={":yes": True},
    )
print(f"Favorites marked: {len(favorites)}")