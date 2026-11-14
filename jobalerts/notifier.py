"""Sends job alerts to Discord channels through webhooks."""
import httpx

from jobalerts import config
from jobalerts.models import Job

PING_CHANNELS = {"apply_now", "maybe"}


def short_label(job: Job, max_len: int = 70) -> str:
    """'Company: Title', cut to fit a notification."""
    label = f"{job.company}: {job.title}"
    return label if len(label) <= max_len else label[: max_len - 1] + "…"


def build_message(job: Job, channel: str, reason: str, role_id: str, tags: list[str] | None = None, score: float | None = None) -> dict:
    """Builds the message Discord will display. Makes no network calls."""
    ping = channel in PING_CHANNELS  # True only for apply_now and maybe
    description = reason
    if tags:
        description += "\n" + " ".join(tags)
    fields = [{"name": "Location", "value": job.location or "Not listed", "inline": True}]
    if score is not None:
        fields.append({"name": "Score", "value": f"{score:.0%}", "inline": True})
    return {
        # Who is CALLED: "<@&id>" shows as @Team Avatar and pings it.
        # Empty = no one is mentioned, so no ping.
        "content": (
            f"{'⭐ ' if tags and '⭐ Bay Area' in tags else ''}{short_label(job)} <@&{role_id}>"
            if ping else ""
        ),
        # Who is ALLOWED to be notified: a safety filter.
        "allowed_mentions": {"roles": [role_id] if ping else []},
        # The job card shown in Discord (never pings, whatever it contains).
        "embeds": [
            {
                "title": f"{job.title} @ {job.company}"[:256],  # Discord's 256-char limit
                "url": str(job.url),
                "description": description,
                "fields": fields,
            }
        ],
    }


def send(job: Job, channel: str, reason: str, tags: list[str] | None = None, score: float | None = None) -> None:
    """Posts a job alert to the channel's webhook."""
    message = build_message(job, channel, reason, config.role_id(), tags, score)
    response = httpx.post(config.webhook_url(channel), json=message, timeout=10)
    response.raise_for_status()


def build_copy_note(job: Job) -> dict:
    """A short, silent note for another listing of a job already alerted."""
    return {
        "content": f"↳ Also posted: [{job.title} — {job.location}]({job.url})",
        "allowed_mentions": {"parse": []},  # never ping
        "flags": 4,  # don't show a link preview
    }


def send_copy_note(job: Job, channel: str) -> None:
    response = httpx.post(config.webhook_url(channel), json=build_copy_note(job), timeout=10)
    response.raise_for_status()