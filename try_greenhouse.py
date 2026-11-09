from jobalerts.sources.greenhouse import fetch_jobs

jobs = fetch_jobs("affirm")
print(f"Affirm has {len(jobs)} open jobs. First 5:")
for job in jobs[:5]:
    print(f"- {job.title} | {job.location} | {job.url}")