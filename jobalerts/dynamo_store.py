"""Remembers seen jobs in DynamoDB. Same methods as SeenStore."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

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
        if decision.score is not None:
            item["score"] = Decimal(str(round(decision.score, 4)))
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

    def reserve_llm_call(self, day: str, limit: int) -> bool:
        """Counts one LLM call for `day`. Returns False if the day's budget is used up.
        One atomic update, so two runs at once can never both take the last call."""
        try:
            self.usage.update_item(
                Key={"counter_id": f"llm-calls#{day}"},
                UpdateExpression="ADD calls :one",
                ConditionExpression="attribute_not_exists(calls) OR calls < :limit",
                ExpressionAttributeValues={":one": 1, ":limit": limit},
            )
            return True
        except self.usage.meta.client.exceptions.ConditionalCheckFailedException:
            return False