from jobalerts.extract import extract, verify
from jobalerts.filters import passes_rule_filter
from jobalerts.sources import ashby, greenhouse, lever

jobs = []
gh = [j for j in greenhouse.fetch_jobs("affirm") if passes_rule_filter(j)][:1]
for job in gh:  # Greenhouse descriptions must be fetched separately
    job.description = greenhouse.fetch_description(job.board, job.job_id)
jobs += gh
jobs += [j for j in lever.fetch_jobs("spotify") if passes_rule_filter(j)][:1]
jobs += [j for j in ashby.fetch_jobs("quora") if passes_rule_filter(j)][:1]

for job in jobs:
    facts = verify(extract(job), job)
    scored = [r for r in facts.requirements if r.importance == "required" and r.kind == "hard"]
    met = sum(r.status == "met" for r in scored)
    print(f"\n=== {job.company}: {job.title} ===")
    print(f"years required: {facts.years_required}  ({facts.years_required_quote})")
    print(f"years preferred: {facts.years_preferred}  ({facts.years_preferred_quote})")
    print(f"grad window: {facts.grad_start} to {facts.grad_end}   domain: {facts.domain}   clearance: {facts.clearance}")
    print(f"required hard skills met: {met} of {len(scored)}")
    for r in facts.requirements:
        print(f"  [{r.status}] ({r.importance}, {r.kind}) {r.requirement}")