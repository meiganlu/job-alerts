"""Katara: answers Discord slash commands and button clicks via this Lambda's function URL."""
import base64
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from jobalerts import config, notifier
from jobalerts.dedupe import title_key_of
from jobalerts.dynamo_store import DynamoStore
from jobalerts.restore import restore_job

PING, COMMAND, BUTTON = 1, 2, 3            # what Discord sends
PONG, DEFERRED, DEFERRED_UPDATE = 1, 5, 6  # "I'm here" / "thinking…" / "got the click"
ONLY_YOU = 64                              # reply visible only to me
API = "https://discord.com/api/v10"


def verify_signature(public_key: str, signature: str, timestamp: str, body: str) -> bool:
    """True only if Discord signed this exact request with its private key."""
    try:
        VerifyKey(bytes.fromhex(public_key)).verify((timestamp + body).encode(),
                                                    bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError):
        return False


def _respond(status: int, payload: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload)}


def handle_request(event: dict, start_work) -> dict:
    """Step 1 (must finish within 3 s): verify, acknowledge, and start the background work."""
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()
    headers = {name.lower(): value for name, value in (event.get("headers") or {}).items()}
    if not verify_signature(config.discord_public_key(), headers.get("x-signature-ed25519", ""),
                            headers.get("x-signature-timestamp", ""), body):
        return _respond(401, {"error": "invalid request signature"})

    interaction = json.loads(body)
    if interaction["type"] == PING:
        return _respond(200, {"type": PONG})
    if interaction["type"] == COMMAND:
        start_work(interaction)
        return _respond(200, {"type": DEFERRED, "data": {"flags": ONLY_YOU}})
    if interaction["type"] == BUTTON:
        start_work(interaction)
        return _respond(200, {"type": DEFERRED_UPDATE})
    return _respond(400, {"error": "unsupported interaction"})


def run_command(interaction: dict) -> str:
    name = interaction["data"]["name"]
    options = {option["name"]: option["value"] for option in interaction["data"].get("options", [])}
    if name == "restore":
        return restore_job(DynamoStore(), options["code"])
    return f"Unknown command: /{name}"


def click_applied(store, custom_id: str) -> list[dict]:
    """Records the application and returns the greyed-out button."""
    job_key = custom_id.removeprefix("applied:")
    row = store.decision_for(job_key)
    if row:
        store.mark_applied(title_key_of(row["company"], row["title"]), job_key)
        store.save()
    today = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%b %-d")
    return notifier.applied_components(job_key, applied_on=today)


def _edit_original(interaction: dict, payload: dict) -> None:
    """Edits the message the interaction belongs to (the reply, or the alert with the button)."""
    url = f"{API}/webhooks/{interaction['application_id']}/{interaction['token']}/messages/@original"
    httpx.patch(url, json=payload, timeout=10).raise_for_status()


def run(interaction: dict) -> None:
    """Step 2 (in the background): do the work, then update Discord."""
    if interaction["type"] == BUTTON:
        _edit_original(interaction, {"components": click_applied(DynamoStore(),
                                                                 interaction["data"]["custom_id"])})
    else:
        _edit_original(interaction, {"content": run_command(interaction)})


def report_error(interaction: dict, text: str) -> None:
    """Tells you something went wrong without overwriting an alert."""
    if interaction["type"] == BUTTON:
        url = f"{API}/webhooks/{interaction['application_id']}/{interaction['token']}"
        httpx.post(url, json={"content": text, "flags": ONLY_YOU}, timeout=10)
    else:
        _edit_original(interaction, {"content": text})