"""All AWS resources for the job-alert system."""
import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


class JobAlertsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        cdk.Tags.of(self).add("project", "job-alerts")

        # --- Storage (replaces seen.db) ---
        self.seen_keys = self._table("SeenKeys", "seen-keys", "job_key")
        self.seen_fingerprints = self._table("SeenFingerprints", "seen-fingerprints", "fingerprint")
        self.decisions = self._table("Decisions", "decisions", "job_key")
        # Lets the digest ask "all decisions from this day" without reading the whole table
        self.decisions.add_global_secondary_index(
            index_name="by-day",
            partition_key=dynamodb.Attribute(name="day", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="decided_at", type=dynamodb.AttributeType.STRING),
            read_capacity=5,
            write_capacity=5,
        )

    def _table(self, construct_id: str, short_name: str, partition_key: str) -> dynamodb.Table:
        """A small provisioned table that stays inside DynamoDB's always-free allowance."""
        return dynamodb.Table(
            self,
            construct_id,
            table_name=f"job-alerts-{short_name}",
            partition_key=dynamodb.Attribute(name=partition_key, type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PROVISIONED,
            read_capacity=5,
            write_capacity=5,
            removal_policy=cdk.RemovalPolicy.RETAIN,  # never delete your data by accident
        )