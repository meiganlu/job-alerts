"""Posts the last 24 hours of filtered jobs to #filtered-out. Runs daily (on AWS later)."""
from datetime import datetime, timedelta, timezone

from jobalerts import notifier
from jobalerts.digest import build_digest_lines, chunk
from jobalerts.store import SeenStore

store = SeenStore("seen.db")
since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
rows = store.decisions_since(since, ("drop", "digest"))
for message in chunk(build_digest_lines(rows)):
    notifier.send_text("filtered_out", message)
print(f"Digest sent: {len(rows)} job(s)")