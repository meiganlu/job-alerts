"""Remembers which jobs have been seen, stored in a SQLite database file."""
import sqlite3


class SeenStore:
    def __init__(self, path: str = "seen.db"):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS seen_keys (key TEXT PRIMARY KEY)")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS seen_fingerprints "
            "(fingerprint TEXT PRIMARY KEY, first_key TEXT)"
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