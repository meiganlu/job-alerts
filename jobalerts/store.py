"""Remembers which jobs have been seen, stored in a SQLite database file."""
import sqlite3
import json

from datetime import datetime, timezone
from jobalerts.models import Job


class SeenStore:
    def __init__(self, path: str = "seen.db"):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS seen_keys (key TEXT PRIMARY KEY)")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS seen_fingerprints "
            "(fingerprint TEXT PRIMARY KEY, first_key TEXT)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS decisions (key TEXT PRIMARY KEY, company TEXT, "
            "title TEXT, url TEXT, location TEXT, channel TEXT, reason TEXT, score REAL, "
            "tags TEXT, decided_at TEXT)"
        )

    def has_key(self, key: str) -> bool:
        row = self.db.execute("SELECT 1 FROM seen_keys WHERE key = ?", (key,)).fetchone()
        return row is not None

    def add_key(self, key: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO seen_keys VALUES (?)", (key,))

    def first_key_for(self, fingerprint: str) -> str | None:
        """The key of the first job seen with this content, or None if it's new content."""
        row = self.db.execute(
            "SELECT first_key FROM seen_fingerprints WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
        return row[0] if row else None

    def add_fingerprint(self, fingerprint: str, key: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO seen_fingerprints VALUES (?, ?)", (fingerprint, key)
        )

    def save(self) -> None:
        self.db.commit()

    def save_decision(self, job: Job, decision) -> None:
        """Logs what was decided for a job. `decision` is a Decision from decide.py."""
        self.db.execute(
            "INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job.key, job.company, job.title, str(job.url), job.location,
             decision.channel, decision.reason, decision.score,
             json.dumps(decision.tags), datetime.now(timezone.utc).isoformat()),
        )

    def channel_for(self, key: str) -> str | None:
        """The channel a job was sent to, or None if no decision was logged."""
        row = self.db.execute("SELECT channel FROM decisions WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def forget(self, key: str, fingerprint: str | None = None) -> None:
        """Un-marks a job as seen (used when processing fails, so it's retried next run)."""
        self.db.execute("DELETE FROM seen_keys WHERE key = ?", (key,))
        self.db.execute("DELETE FROM seen_fingerprints WHERE first_key = ?", (key,))

    def decisions_since(self, since: str, channels: tuple[str, ...]) -> list[dict]:
        """Decisions made after `since` (ISO time) in the given channels, oldest first."""
        placeholders = ", ".join("?" for _ in channels)
        rows = self.db.execute(
            "SELECT key, company, title, url, location, channel, reason, tags FROM decisions "
            f"WHERE decided_at >= ? AND channel IN ({placeholders}) ORDER BY decided_at",
            (since, *channels),
        ).fetchall()
        columns = ["job_key", "company", "title", "url", "location", "channel", "reason", "tags"]
        return [dict(zip(columns, row)) for row in rows]

    def set_channel(self, key: str, channel: str) -> None:
        self.db.execute("UPDATE decisions SET channel = ? WHERE key = ?", (channel, key))