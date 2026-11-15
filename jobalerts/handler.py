"""The functions AWS Lambda calls. Lambda always passes (event, context)."""
import os

from jobalerts import notifier
from jobalerts.digest import send_daily_digest
from jobalerts.dynamo_store import DynamoStore
from jobalerts.pipeline import run


def _report_crash(name: str, error: Exception) -> None:
    """Posts a crash to #system-health. Never raises, so it can't hide the original error."""
    try:
        notifier.send_text(
            "system_health",
            f"🚨 **{name} failed:** `{type(error).__name__}: {str(error)[:300]}`\n"
            f"Logs: CloudWatch → /aws/lambda/job-alerts-{name}",
        )
    except Exception as report_error:
        print("Could not post to #system-health:", report_error)


def poll(event, context):
    """One full pipeline run: fetch → filter → dedupe → LLM → decide → alert."""
    try:
        if (event or {}).get("test_crash"):
            raise RuntimeError("Test crash (triggered on purpose)")
        counts = run(DynamoStore(), limit=int(os.getenv("LLM_LIMIT", "25")))
    except Exception as error:
        _report_crash("poller", error)
        raise  # still fail the run, so CloudWatch counts it as an error
    print("Summary:", dict(counts))
    return dict(counts)


def digest(event, context):
    """Daily digest of dropped and low-match jobs."""
    try:
        count = send_daily_digest(DynamoStore())
    except Exception as error:
        _report_crash("digest", error)
        raise
    print("Digest jobs:", count)
    return {"jobs": count}