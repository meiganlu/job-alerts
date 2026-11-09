"""Sends two test alerts: one should buzz phone, one should stay silent."""
from jobalerts.models import Job
from jobalerts.notifier import send

job = Job(
    source="greenhouse",
    company="Affirm",
    job_id="8017340003",
    title="Software Engineer I, Fullstack (Search)",
    location="Remote US",
    url="https://job-boards.greenhouse.io/affirm/jobs/8017340003",
)

send(job, "apply_now", "Test alert: phone should buzz.")
send(job, "filtered_out", "Test alert: phone should stay silent.")
print("Sent! Check Discord and your phone.")