"""Remembers seen jobs in DynamoDB. Same methods as SeenStore."""
import json
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

from jobalerts import config
from jobalerts.models import Job


class DynamoStore:
    def __init__(self, prefix: str = "job-alerts"):
        db = boto3.resource("dynamodb", region_name=config.aws_region())
        self.keys = db.Table(f"{prefix}-seen-keys")
        self.fingerprints = db.Table(f"{prefix}-seen-fingerprints")
        self.decisions = db.Table(f"{prefix}-decisions")
        self.usage = db.Table(f"{prefix}-usage")
        self.applied = db.Table(f"{prefix}-applied")

    # --- Seen keys ---
    def has_key(self, key: str) -> bool:
        return "Item" in self.keys.get_item(Key={"job_key": key})

    def add_key(self, key: str) -> None:
        self.keys.put_item(Item={"job_key": key})

    # --- Fingerprints ---
    def first_key_for(self, fingerprint: str) -> str | None:
        item = self.fingerprints.get_item(Key={"fingerprint": fingerprint}).get("Item")
        return item["first_key"] if item else None

    def add_fingerprint(self, fingerprint: str, key: str) -> None:
        try:
            self.fingerprints.put_item(
                Item={"fingerprint": fingerprint, "first_key": key},
                ConditionExpression="attribute_not_exists(fingerprint)",  # keep the first listing
            )
        except self.fingerprints.meta.client.exceptions.ConditionalCheckFailedException:
            pass  # already recorded, like SQLite's INSERT OR IGNORE

    def save(self) -> None:
        pass  # DynamoDB saves each write immediately; nothing to commit

    # --- Decisions ---
    def save_decision(self, job: Job, decision) -> None:
        now = datetime.now(timezone.utc)
        item = {
            "job_key": job.key,
            "company": job.company,
            "title": job.title,
            "url": str(job.url),
            "location": job.location,
            "channel": decision.channel,
            "reason": decision.reason,
            "tags": json.dumps(decision.tags),
            "day": now.strftime("%Y-%m-%d"),  # for the by-day index
            "decided_at": now.isoformat(),
        }
        self.decisions.put_item(Item=item)

    def channel_for(self, key: str) -> str | None:
        item = self.decisions.get_item(Key={"job_key": key}).get("Item")
        return item["channel"] if item else None

    def set_channel(self, key: str, channel: str) -> None:
        self.decisions.update_item(
            Key={"job_key": key},
            UpdateExpression="SET channel = :c",
            ExpressionAttributeValues={":c": channel},
        )

    def forget(self, key: str, fingerprint: str | None = None) -> None:
        """Un-marks a job as seen so it's retried next run."""
        self.keys.delete_item(Key={"job_key": key})
        if fingerprint:
            try:
                self.fingerprints.delete_item(
                    Key={"fingerprint": fingerprint},
                    ConditionExpression="first_key = :k",  # only if this job recorded it
                    ExpressionAttributeValues={":k": key},
                )
            except self.fingerprints.meta.client.exceptions.ConditionalCheckFailedException:
                pass

    def decisions_since(self, since: str, channels: tuple[str, ...]) -> list[dict]:
        """Decisions made after `since` (ISO time) in the given channels, oldest first."""
        start = datetime.fromisoformat(since).date()
        today = datetime.now(timezone.utc).date()
        results = []
        day = start
        while day <= today:
            kwargs = {
                "IndexName": "by-day",
                "KeyConditionExpression": Key("day").eq(day.isoformat()) & Key("decided_at").gte(since),
            }
            while True:  # DynamoDB returns results in pages
                page = self.decisions.query(**kwargs)
                results += [item for item in page["Items"] if item["channel"] in channels]
                if "LastEvaluatedKey" not in page:
                    break
                kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
            day += timedelta(days=1)
        return results

    def add_keys(self, keys: list[str]) -> None:
        """Writes many keys in batches of 25 (much faster than one at a time)."""
        with self.keys.batch_writer(overwrite_by_pkeys=["job_key"]) as batch:
            for key in keys:
                batch.put_item(Item={"job_key": key})

    def mark_applied(self, title_key: str, job_key: str) -> bool:
        """Records an application the first time only. Returns True if it was new."""
        try:
            self.applied.put_item(
                Item={"title_key": title_key, "job_key": job_key,
                      "applied_at": datetime.now(timezone.utc).isoformat()},
                ConditionExpression="attribute_not_exists(title_key)",
            )
            return True
        except self.applied.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    def applied_at(self, title_key: str) -> str | None:
        item = self.applied.get_item(Key={"title_key": title_key}).get("Item")
        return item["applied_at"] if item else None

    def decision_for(self, key: str) -> dict | None:
        return self.decisions.get_item(Key={"job_key": key}).get("Item")

    def llm_spent(self, day: str) -> int:
        """Micro-dollars spent on the LLM today (1,000,000 = $1)."""
        item = self.usage.get_item(Key={"counter_id": f"llm-spend#{day}"}).get("Item") or {}
        return int(item.get("spent_micros", 0))

    def add_llm_spend(self, day: str, micros: int) -> None:
        self.usage.update_item(Key={"counter_id": f"llm-spend#{day}"},
                               UpdateExpression="ADD spent_micros :m",
                               ExpressionAttributeValues={":m": micros})