from jobalerts.sources import ashby, greenhouse, lever

for name, fetch, slug in [
    ("Greenhouse", greenhouse.fetch_jobs, "affirm"),
    ("Lever", lever.fetch_jobs, "spotify"),
    ("Ashby", ashby.fetch_jobs, "quora"),
]:
    jobs = fetch(slug)
    print(f"\n{name} / {slug}: {len(jobs)} open jobs")
    for job in jobs[:3]:
        print(f"- {job.title} | {job.location}")