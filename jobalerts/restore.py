"""Restores a filtered job to #maybe, by the code shown in the digest."""
import json
from datetime import datetime, timedelta, timezone

from jobalerts import notifier
from jobalerts.digest import short_code
from jobalerts.models import Job


def restore_job(store, code: str) -> str:
    """Finds the job by its digest code, re-sends it to #maybe, and returns a reply message."""
    code = code.strip().lstrip("#").lower()
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    matches = [row for row in store.decisions_since(since, ("drop", "digest"))
               if short_code(row["job_key"]) == code]
    if not matches:
        return f"No filtered job with code #{code} in the last 7 days."
    row = matches[0]
    source, _, job_id = row["job_key"].split(":", 2)
    job = Job(source=source, company=row["company"], job_id=job_id, title=row["title"],
              location=row["location"], url=row["url"])
    notifier.send(job, "maybe", f"♻️ Restored from digest. Originally: {row['reason']}",
                  json.loads(row["tags"]))
    store.set_channel(row["job_key"], "maybe")
    store.save()
    return f"♻️ Restored #{code}: {row['company']}: {row['title']} → #maybe"