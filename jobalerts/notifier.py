"""Sends job alerts to Discord channels through webhooks."""
import re
import time

import httpx

from jobalerts import config
from jobalerts.models import Job
from jobalerts.filters import is_bay_area

PING_CHANNELS = {"apply_now", "maybe"}
COLORS = {"apply_now": 0x2ECC71, "maybe": 0xF1C40F}  # green, amber
GRAY = 0x95A5A6  # any other channel
APPLIED_EMOJI = "🍀"


def _check(response: httpx.Response) -> None:
    """Like raise_for_status, but includes Discord's explanation of what was wrong."""
    if response.is_error:
        raise RuntimeError(f"Discord said {response.status_code}: {response.text[:300]}")


def _post(url: str, message: dict) -> httpx.Response:
    """POST to Discord, waiting and retrying if it says we're sending too fast (429)."""
    for _ in range(3):
        response = httpx.post(url, json=message, timeout=10)
        if response.status_code != 429:
            return response
        time.sleep(min(float(response.headers.get("Retry-After", 1)), 10))
    return response


def short_label(job: Job, max_len: int = 70) -> str:
    """'Company: Title', cut to fit a notification."""
    label = f"{job.company}: {job.title}"
    return label if len(label) <= max_len else label[: max_len - 1] + "…"


def short_locations(location: str, max_shown: int = 2) -> str:
    """Bay Area cities first, at most two, then '+N': 'Mountain View · San Francisco +2'."""
    cities = []
    for part in re.split(r"[;|]", location):
        city = part.split(",")[0].strip()
        if city and city not in cities:
            cities.append(city)
    if not cities:
        return "Not listed"
    cities.sort(key=lambda city: not is_bay_area(city))  # Bay Area first, others keep their order
    extra = len(cities) - max_shown
    return " · ".join(cities[:max_shown]) + (f" +{extra}" if extra > 0 else "")


def applied_components(job_key: str, applied_on: str | None = None) -> list[dict]:
    """The 🍀 Applied button under an alert. Greyed out once clicked."""
    if len(job_key) > 92:  # Discord limits a button's ID to 100 characters
        return []
    label = f"{APPLIED_EMOJI} Applied {applied_on}" if applied_on else "Apply"
    button = {"type": 2, "style": 3, "custom_id": f"applied:{job_key}",  # style 3 = green
              "label": label, "disabled": bool(applied_on)}
    return [{"type": 1, "components": [button]}]  # type 1 = a row holding the button


def build_message(job: Job, channel: str, reason: str, role_id: str,
                  tags: list[str] | None = None, quiet: bool = False) -> dict:
    """Builds the message Discord will display. Makes no network calls.
    quiet=True posts an alert card without pinging your phone."""
    alert = channel in PING_CHANNELS  # apply_now and maybe get the Apply button
    ping = alert and not quiet
    tags = tags or []
    bay_area = "⭐ Bay Area" in tags

    # Line 1: "📍 New York · San Francisco ⭐", then the reason, then one tag per line
    lines = [f"📍 {short_locations(job.location)}" + (" ⭐" if bay_area else ""), reason]
    other_tags = [tag for tag in tags if tag != "⭐ Bay Area"]
    if other_tags:
        lines += other_tags  # one tag per line

    return {
        # Who is CALLED: "<@&id>" shows as @Team Avatar and pings it.
        # Empty = no one is mentioned, so no ping.
        "content": (
            f"{'⭐ ' if bay_area else ''}{short_label(job)} <@&{role_id}>" if ping else ""
        ),
        # Who is ALLOWED to be notified: a safety filter.
        "allowed_mentions": {"roles": [role_id] if ping else []},
        "embeds": [
            {
                "title": f"{job.title} @ {job.company}"[:256],  # Discord's 256-char limit
                "url": str(job.url),
                "description": "\n".join(lines)[:4000],
                "color": COLORS.get(channel, GRAY),
            }
        ],
        "components": applied_components(job.key) if alert else [],
    }


def send(job: Job, channel: str, reason: str, tags: list[str] | None = None,
         quiet: bool = False) -> None:
    """Posts a job alert. If Discord refuses the button, the alert still goes out without it."""
    message = build_message(job, channel, reason, config.role_id(), tags, quiet)
    url = config.webhook_url(channel)
    response = _post(url + "?with_components=true", message)
    if response.status_code == 400 and message.get("components"):
        message = {**message, "components": []}
        response = _post(url, message)
    _check(response)


def build_copy_note(job: Job) -> dict:
    """A short, silent note for another listing of a job already alerted."""
    return {
        "content": f"↳ Also posted: [{job.title} — {job.location}]({job.url})",
        "allowed_mentions": {"parse": []},  # never ping
        "flags": 4,  # don't show a link preview
    }


def send_copy_note(job: Job, channel: str) -> None:
    response = _post(config.webhook_url(channel), build_copy_note(job))
    response.raise_for_status()


def build_text_message(text: str, role_id: str | None = None) -> dict:
    """Plain text with no link previews. With a role_id, it mentions Team Avatar (phone buzzes)."""
    if role_id:
        return {"content": f"{text} <@&{role_id}>",
                "allowed_mentions": {"roles": [role_id]}, "flags": 4}
    return {"content": text, "allowed_mentions": {"parse": []}, "flags": 4}


def send_text(channel: str, text: str, ping: bool = False) -> None:
    """Posts plain text, e.g. the digest (silent) or a crash report (ping=True)."""
    message = build_text_message(text, config.role_id() if ping else None)
    response = _post(config.webhook_url(channel), message)
    response.raise_for_status()