"""The function AWS Lambda calls. Lambda always passes (event, context)."""
import os

from jobalerts.dynamo_store import DynamoStore
from jobalerts.pipeline import run
from jobalerts.digest import send_daily_digest


def poll(event, context):
    """One full pipeline run: fetch → filter → dedupe → LLM → decide → alert."""
    counts = run(DynamoStore(), limit=int(os.getenv("LLM_LIMIT", "25")))
    print("Summary:", dict(counts))  # appears in CloudWatch Logs
    return dict(counts)


def digest(event, context):
    """Daily digest of dropped and low-match jobs."""
    count = send_daily_digest(DynamoStore())
    print("Digest jobs:", count)
    return {"jobs": count}