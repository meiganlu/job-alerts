"""The functions AWS Lambda calls. Lambda always passes (event, context)."""
import os
import json
import boto3

from jobalerts import notifier, discord_bot
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
            ping=True,
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


def discord(event, context):
    """Katara. Two kinds of calls come in here:
    - from Discord (via the function URL): verify and answer within 3 seconds
    - from itself (in the background): do the actual work, then edit the reply"""
    if "discord_work" in event:
        interaction = event["discord_work"]
        try:
            discord_bot.run(interaction)
        except Exception as error:
            discord_bot.report_error(
                interaction, f"⚠️ Something went wrong: {type(error).__name__}: {str(error)[:200]}")
        return {"ok": True}

    def start_work(interaction):
        boto3.client("lambda").invoke(
            FunctionName=context.invoked_function_arn,
            InvocationType="Event",  # don't wait for it to finish
            Payload=json.dumps({"discord_work": interaction}),
        )

    return discord_bot.handle_request(event, start_work)