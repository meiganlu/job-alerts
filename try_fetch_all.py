"""Measures one full pass over every company. No alerts, no LLM calls.
Saves a snapshot so the next run can count jobs that are NEW since this one."""
import asyncio
import json
import re
import time
from collections import Counter
from pathlib import Path

from jobalerts.companies import companies_table, load_all
from jobalerts.fetcher import fetch_all

SNAPSHOT = Path("snapshot.json")


def role(title: str) -> str:
    """'Software Engineer II, Backend (Search)' → 'software engineer'."""
    core = re.split(r"[,(|/–-]", title.lower())[0]
    return re.sub(r"\b(i|ii|iii|1|2|3)\b", "", core).strip()


companies = load_all(companies_table())
print(f"Fetching {len(companies)} companies...")
start = time.monotonic()
results = asyncio.run(fetch_all(companies))
print(f"\nTook {(time.monotonic() - start) / 60:.1f} minutes")
print("Results:", dict(Counter(result.status for result in results)))

kept = [job for result in results for job in result.kept]
print(f"Open jobs: {sum(r.job_count for r in results):,}   Passing your filter: {len(kept):,}")

print("\nMost common roles passing the filter:")
for name, count in Counter(role(job.title) for job in kept).most_common(40):
    print(f"  {count:>5}  {name}")

print("\nCompanies with the most passing jobs:")
for name, count in Counter(job.company for job in kept).most_common(15):
    print(f"  {count:>5}  {name}")

keys = {job.key for job in kept}
if SNAPSHOT.exists():
    previous = set(json.loads(SNAPSHOT.read_text())["keys"])
    print(f"\nNew since last snapshot: {len(keys - previous):,} passing jobs")
SNAPSHOT.write_text(json.dumps({"taken_at": time.time(), "keys": sorted(keys)}))