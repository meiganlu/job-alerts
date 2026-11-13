from jobalerts.dedupe import split_new
from jobalerts.filters import passes_rule_filter
from jobalerts.sources import ashby, greenhouse, lever
from jobalerts.store import SeenStore

store = SeenStore("seen.db")

for fetch, slug in [
    (greenhouse.fetch_jobs, "affirm"),
    (lever.fetch_jobs, "spotify"),
    (ashby.fetch_jobs, "quora"),
]:
    kept = [job for job in fetch(slug) if passes_rule_filter(job)]
    new_jobs, copies = split_new(kept, store)
    print(f"\n{slug}: {len(kept)} kept by filter, {len(new_jobs)} new, {len(copies)} copies")
    for job in new_jobs:
        print(f"- NEW: {job.title} | {job.location}")