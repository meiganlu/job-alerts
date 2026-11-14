from jobalerts.filters import passes_rule_filter
from jobalerts.sources import greenhouse, lever

job = next(j for j in greenhouse.fetch_jobs("affirm") if passes_rule_filter(j))
print(f"=== Greenhouse: {job.title} ===")
print(greenhouse.fetch_description(job.board, job.job_id)[:800])

job = next(j for j in lever.fetch_jobs("spotify") if passes_rule_filter(j))
print(f"\n=== Lever: {job.title} ===")
print(job.description[:800])