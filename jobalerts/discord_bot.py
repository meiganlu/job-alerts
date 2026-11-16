"""Katara: answers Discord slash commands. Discord calls this Lambda's function URL."""
import base64
import json

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from jobalerts import config
from jobalerts.dynamo_store import DynamoStore
from jobalerts.restore import restore_job

PING, COMMAND = 1, 2          # what Discord sends
PONG, DEFERRED = 1, 5         # how we answer: "I'm here" / "thinking…"
ONLY_YOU = 64                 # reply visible only to the person who typed the command


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
    """Step 1 (must finish within 3 s): verify, then answer 'thinking…' and start the work."""
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()
    headers = {name.lower(): value for name, value in (event.get("headers") or {}).items()}
    if not verify_signature(config.discord_public_key(), headers.get("x-signature-ed25519", ""),
                            headers.get("x-signature-timestamp", ""), body):
        return _respond(401, {"error": "invalid request signature"})

    interaction = json.loads(body)
    if interaction["type"] == PING:  # Discord checking the URL works
        return _respond(200, {"type": PONG})
    if interaction["type"] == COMMAND:
        start_work(interaction)
        return _respond(200, {"type": DEFERRED, "data": {"flags": ONLY_YOU}})
    return _respond(400, {"error": "unsupported interaction"})


def run_command(interaction: dict) -> str:
    """Step 2 (in the background): do the work and return the reply text."""
    name = interaction["data"]["name"]
    options = {option["name"]: option["value"] for option in interaction["data"].get("options", [])}
    if name == "restore":
        return restore_job(DynamoStore(), options["code"])
    return f"Unknown command: /{name}"


def finish(interaction: dict, text: str) -> None:
    """Replaces 'thinking…' with the final reply."""
    url = (f"https://discord.com/api/v10/webhooks/{interaction['application_id']}/"
           f"{interaction['token']}/messages/@original")
    httpx.patch(url, json={"content": text}, timeout=10).raise_for_status()