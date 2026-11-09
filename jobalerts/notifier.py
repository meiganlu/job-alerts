"""Sends job alerts to Discord channels through webhooks."""
import httpx

from jobalerts import config
from jobalerts.models import Job

PING_CHANNELS = {"apply_now", "maybe"}


def build_message(job: Job, channel: str, reason: str, role_id: str) -> dict:
    """Builds the message Discord will display."""
    ping = channel in PING_CHANNELS
    return {
        "content": f"<@&{role_id}>" if ping else "", # decides ping/no ping
        "allowed_mentions": {"roles": [role_id] if ping else []}, # safety filter: tells Discord only role_id can be notified
        "embeds": [
            {
                "title": f"{job.title} @ {job.company}"[:256],
                "url": str(job.url),
                "description": reason,
                "fields": [
                    {"name": "Location", "value": job.location or "Not listed", "inline": True}
                ],
            }
        ],
    }


def send(job: Job, channel: str, reason: str) -> None:
    """Posts the message to the channel's webhook."""
    message = build_message(job, channel, reason, config.role_id())
    response = httpx.post(config.webhook_url(channel), json=message, timeout=10)
    response.raise_for_status()