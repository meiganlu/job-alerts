"""Builds the daily digest of jobs that were dropped or scored low."""

HEADINGS = {"drop": "🔇 Dropped", "digest": "📋 Low match or active clearance"}


def build_digest_lines(rows: list[tuple]) -> list[str]:
    """One line per job, grouped by why it was filtered."""
    if not rows:
        return ["✅ Nothing filtered in the last 24 hours."]
    lines = [f"**Daily digest:** {len(rows)} filtered job(s). "
            "To restore one, run in /job-alerts terminal: `python restore.py <number>`"]
    for channel in ("drop", "digest"):
        group = [row for row in rows if row[4] == channel]
        if not group:
            continue
        lines.append(f"\n__{HEADINGS[channel]}__")
        for number, company, title, url, _, reason in group:
            short_reason = reason if len(reason) <= 150 else reason[:149] + "…"
            lines.append(f"`#{number}` [{company}: {title}]({url}) — {short_reason}")
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