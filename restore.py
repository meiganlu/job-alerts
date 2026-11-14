"""Re-sends a filtered job to #maybe. Usage: python restore.py 12"""
import argparse
import json

from jobalerts import notifier
from jobalerts.models import Job
from jobalerts.store import SeenStore

parser = argparse.ArgumentParser(description="Restore a job from the daily digest.")
parser.add_argument("number", type=int, help="the #number shown in the digest")
args = parser.parse_args()

store = SeenStore("seen.db")
row = store.get_decision(args.number)
if row is None:
    raise SystemExit(f"No job #{args.number} found.")

key, company, title, url, location, reason, tags = row
source, _, job_id = key.split(":", 2)
job = Job(source=source, company=company, job_id=job_id, title=title, location=location, url=url)

notifier.send(job, "maybe", f"♻️ Restored from digest. Originally: {reason}", json.loads(tags))
store.set_channel(key, "maybe")
store.save()
print(f"Restored #{args.number}: {company}: {title}")