import boto3
import pytest
from moto import mock_aws
from datetime import datetime, timedelta, timezone

from jobalerts.decide import Decision
from jobalerts.dedupe import split_new
from jobalerts.dynamo_store import DynamoStore
from jobalerts.models import Job


@pytest.fixture
def store(monkeypatch):
    """A DynamoStore backed by moto's fake DynamoDB: offline, free, and empty for each test."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-west-2")
        for name, key in [("seen-keys", "job_key"), ("seen-fingerprints", "fingerprint"), ("applied", "title_key")]:
            db.create_table(
                TableName=f"test-{name}",
                KeySchema=[{"AttributeName": key, "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": key, "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
        db.create_table(
            TableName="test-decisions",
            KeySchema=[{"AttributeName": "job_key", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "job_key", "AttributeType": "S"},
                {"AttributeName": "day", "AttributeType": "S"},
                {"AttributeName": "decided_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "by-day",
                "KeySchema": [{"AttributeName": "day", "KeyType": "HASH"},
                              {"AttributeName": "decided_at", "KeyType": "RANGE"}],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        db.create_table(
            TableName="test-usage",
            KeySchema=[{"AttributeName": "counter_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "counter_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoStore(prefix="test")


def make_job(job_id, location="Remote US"):
    return Job(source="greenhouse", company="Affirm", job_id=job_id, title="Software Engineer I",
               location=location, url=f"https://example.com/{job_id}", description="Python.")


def test_dedupe_works_with_dynamo(store):
    us, nyc = make_job("1"), make_job("2", "New York, NY")
    assert split_new([us, nyc], store) == ([us], [(nyc, us.key)])
    assert split_new([us, nyc], store) == ([], [])  # second run: both already seen


def test_decision_round_trip(store):
    job = make_job("1")
    store.save_decision(job, Decision(channel="digest", reason="low match", score=0.2))
    assert store.channel_for(job.key) == "digest"
    store.set_channel(job.key, "maybe")
    assert store.channel_for(job.key) == "maybe"


def test_decisions_since_finds_recent(store):
    store.save_decision(make_job("1"), Decision(channel="drop", reason="3+ years"))
    store.save_decision(make_job("2"), Decision(channel="apply_now", reason="good"))

    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    rows = store.decisions_since(since, ("drop", "digest"))
    assert [row["job_key"] for row in rows] == [make_job("1").key]


def test_forget(store):
    job = make_job("1")
    split_new([job], store)
    store.forget(job.key)
    assert not store.has_key(job.key)


def test_daily_llm_budget_dynamo(store):
    assert store.reserve_llm_call("2026-11-15", limit=1)
    assert not store.reserve_llm_call("2026-11-15", limit=1)