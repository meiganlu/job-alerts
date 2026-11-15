"""Builds the daily digest of jobs that were dropped or scored low."""
import hashlib

HEADINGS = {"drop": "🔇 Dropped", "digest": "📋 Low match or active clearance"}


def short_code(job_key: str) -> str:
    """A 6-character code for a job, used to restore it. Same job → same code."""
    return hashlib.sha256(job_key.encode()).hexdigest()[:6]


def build_digest_lines(rows: list[dict]) -> list[str]:
    """One line per job, grouped by why it was filtered."""
    if not rows:
        return ["✅ Nothing filtered in the last 24 hours."]
    lines = [f"**Daily digest:** {len(rows)} filtered job(s). "
             "To restore one, run in Terminal: `python restore.py <code>`"]
    for channel in ("drop", "digest"):
        group = [row for row in rows if row["channel"] == channel]
        if not group:
            continue
        lines.append(f"\n__{HEADINGS[channel]}__")
        for row in group:
            reason = row["reason"] if len(row["reason"]) <= 150 else row["reason"][:149] + "…"
            lines.append(f"`#{short_code(row['job_key'])}` "
                         f"[{row['company']}: {row['title']}]({row['url']}) — {reason}")
    return lines


def chunk(lines: list[str], limit: int = 1900) -> list[str]:
    """Groups lines into messages under Discord's 2,000-character limit."""
    messages, current = [], ""
    for line in lines:
        if current and len(current) + len(line) + 1 > limit:
            messages.append(current)
            current = ""
        current += line + "\n"
    if current:
        messages.append(current)
    return messages