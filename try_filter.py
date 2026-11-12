from jobalerts.filters import is_bay_area, passes_rule_filter
from jobalerts.sources import ashby, greenhouse, lever

for fetch, slug in [
    (greenhouse.fetch_jobs, "affirm"),
    (lever.fetch_jobs, "spotify"),
    (ashby.fetch_jobs, "quora"),
]:
    jobs = fetch(slug)
    kept = [job for job in jobs if passes_rule_filter(job)]
    print(f"\n{slug}: kept {len(kept)} of {len(jobs)}")
    for job in kept:
        star = "⭐ " if is_bay_area(job.location) else ""
        print(f"- {star}{job.title} | {job.location}")