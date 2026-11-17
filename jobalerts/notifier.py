"""Sends job alerts to Discord channels through webhooks."""
import httpx
import re

from jobalerts import config
from jobalerts.models import Job
from jobalerts.filters import is_bay_area

PING_CHANNELS = {"apply_now", "maybe"}
STATUS_ICONS = {"met": "🌿", "partial": "🌙", "not_met": "🚩"}
GAPS_FIRST = {"not_met": 0, "partial": 1, "met": 2}
COLORS = {"apply_now": 0x2ECC71, "maybe": 0xF1C40F}  # green, amber
GRAY = 0x95A5A6  # not analyzed or restored (no score)
APPLIED_EMOJI = "🍀"

# Common openings that add length but no meaning
_LEAD_INS = re.compile(
    r"^(your experience demonstrates (that )?(you )?|you have|you are|you're|you will|"
    r"you can|you bring|comfortable (with )?|experience (with|in)|working knowledge of|"
    r"familiarity with|basic understanding (or|of)|solid understanding of|strong|"
    r"excellent|proficiency (in|with)|knowledge of|demonstrated|ability to)\s*",
    re.IGNORECASE,
)


def _check(response: httpx.Response) -> None:
    """Like raise_for_status, but includes Discord's explanation of what was wrong."""
    if response.is_error:
        raise RuntimeError(f"Discord said {response.status_code}: {response.text[:300]}")


def short_label(job: Job, max_len: int = 70) -> str:
    """'Company: Title', cut to fit a notification."""
    label = f"{job.company}: {job.title}"
    return label if len(label) <= max_len else label[: max_len - 1] + "…"


def short_requirement(text: str, max_len: int = 44) -> str:
    """Drops a common lead-in and cuts at a word boundary so it fits one phone line."""
    text = _LEAD_INS.sub("", text.strip()).rstrip(".")
    text = text[:1].upper() + text[1:]
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0].rstrip(",;:") + "…"


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


def requirement_fields(requirements: list) -> list[dict]:
    """Three blocks (Required, Preferred, Soft skills), gaps first within each."""
    sections = [
        ("Required", lambda r: r.importance == "required" and r.kind == "hard"),
        ("Preferred", lambda r: r.importance == "preferred" and r.kind == "hard"),
        ("Soft skills", lambda r: r.kind == "soft"),
    ]
    fields = []
    for name, belongs in sections:
        items = sorted((r for r in requirements if belongs(r)), key=lambda r: GAPS_FIRST[r.status])
        if items:
            value = "\n".join(f"{STATUS_ICONS[r.status]} {short_requirement(r.requirement)}" for r in items)
            fields.append({"name": name, "value": value[:1024], "inline": False})
    return fields


def applied_components(job_key: str, applied_on: str | None = None) -> list[dict]:
    """The 🍀 Applied button under an alert. Greyed out once clicked."""
    if len(job_key) > 92:  # Discord limits a button's ID to 100 characters
        return []
    label = f"{APPLIED_EMOJI} Applied {applied_on}" if applied_on else "Apply"
    button = {"type": 2, "style": 3, "custom_id": f"applied:{job_key}",  # style 3 = green
              "label": label, "disabled": bool(applied_on)}
    return [{"type": 1, "components": [button]}]  # type 1 = a row holding the button


def build_message(job: Job, channel: str, reason: str, role_id: str,
                  tags: list[str] | None = None, score: float | None = None,
                  requirements: list | None = None) -> dict:
    """Builds the message Discord will display. Makes no network calls."""
    ping = channel in PING_CHANNELS  # True only for apply_now and maybe
    tags = tags or []
    bay_area = "⭐ Bay Area" in tags

    # Line 1: "83% match · 📍 New York · San Francisco ⭐"
    meta = [f"{score:.0%} match"] if score is not None else []
    meta.append(f"📍 {short_locations(job.location)}" + (" ⭐" if bay_area else ""))
    lines = [" · ".join(meta)]
    # The reason only adds information when it isn't the plain score
    if score is None or not reason.startswith("meets"):
        lines.append(reason)
    other_tags = [tag for tag in tags if tag != "⭐ Bay Area"]
    if other_tags:
        lines.append(" ".join(other_tags))

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
                "fields": requirement_fields(requirements or []),
            }
        ],
        "components": applied_components(job.key) if ping else [],
    }


def send(job: Job, channel: str, reason: str, tags: list[str] | None = None,
         score: float | None = None, requirements: list | None = None) -> None:
    """Posts a job alert. If Discord refuses the button, the alert still goes out without it."""
    message = build_message(job, channel, reason, config.role_id(), tags, score, requirements)
    url = config.webhook_url(channel)
    response = httpx.post(url + "?with_components=true", json=message, timeout=10)
    if response.status_code == 400 and message.get("components"):
        message = {**message, "components": []}
        response = httpx.post(url, json=message, timeout=10)
    _check(response)


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


def build_text_message(text: str, role_id: str | None = None) -> dict:
    """Plain text with no link previews. With a role_id, it mentions Team Avatar (phone buzzes)."""
    if role_id:
        return {"content": f"{text} <@&{role_id}>",
                "allowed_mentions": {"roles": [role_id]}, "flags": 4}
    return {"content": text, "allowed_mentions": {"parse": []}, "flags": 4}


def send_text(channel: str, text: str, ping: bool = False) -> None:
    """Posts plain text, e.g. the digest (silent) or a crash report (ping=True)."""
    message = build_text_message(text, config.role_id() if ping else None)
    response = httpx.post(config.webhook_url(channel), json=message, timeout=10)
    response.raise_for_status()