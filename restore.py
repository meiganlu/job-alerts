"""Re-sends a filtered job to #maybe. Usage: python restore.py a3f9c1"""
import argparse
import json
from datetime import datetime, timedelta, timezone

from jobalerts import notifier
from jobalerts.digest import short_code
from jobalerts.models import Job
from jobalerts.stores import open_store

parser = argparse.ArgumentParser(description="Restore a job from the daily digest.")
parser.add_argument("code", help="the #code shown in the digest, e.g. a3f9c1")
parser.add_argument("--store", choices=["dynamo", "sqlite"], default="dynamo")
args = parser.parse_args()

store = open_store(args.store)
code = args.code.lstrip("#").lower()
since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
matches = [row for row in store.decisions_since(since, ("drop", "digest"))
           if short_code(row["job_key"]) == code]
if not matches:
    raise SystemExit(f"No filtered job with code #{code} in the last 7 days.")

row = matches[0]
source, _, job_id = row["job_key"].split(":", 2)
job = Job(source=source, company=row["company"], job_id=job_id, title=row["title"],
          location=row["location"], url=row["url"])
notifier.send(job, "maybe", f"♻️ Restored from digest. Originally: {row['reason']}",
              json.loads(row["tags"]))
store.set_channel(row["job_key"], "maybe")
store.save()
print(f"Restored #{code}: {row['company']}: {row['title']}")