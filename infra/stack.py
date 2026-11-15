"""All AWS resources for the job-alert system."""
import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam # permissions
from aws_cdk import aws_lambda as lambda_ # Lambda functions
from aws_cdk import aws_logs as logs # CloudWatch log groups
from constructs import Construct
from dotenv import dotenv_values

ENV = dotenv_values(".env")  # read non-secret settings

# Files the Lambda bundle needs
BUNDLE_COMMAND = (
    "pip install -r requirements.txt -t /asset-output && "
    "cp -r jobalerts companies.yaml criteria.yaml resume.txt /asset-output"
)


class JobAlertsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        cdk.Tags.of(self).add("project", "job-alerts")

        # --- Storage (replaces seen.db) ---
        self.seen_keys = self._table("SeenKeys", "seen-keys", "job_key")
        self.seen_fingerprints = self._table("SeenFingerprints", "seen-fingerprints", "fingerprint")
        self.decisions = self._table("Decisions", "decisions", "job_key")
        self.decisions.add_global_secondary_index(
            index_name="by-day",
            partition_key=dynamodb.Attribute(name="day", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="decided_at", type=dynamodb.AttributeType.STRING),
            read_capacity=5,
            write_capacity=5,
        )

        # --- The code bundle built inside Docker ---
        code = lambda_.Code.from_asset(
            ".",
            exclude=[".venv", ".git", "cdk.out", "tests", "infra", "seen.db", ".env", "**/__pycache__"],
            bundling=cdk.BundlingOptions(
                image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                platform="linux/arm64",
                command=["bash", "-c", BUNDLE_COMMAND],
            ),
        )

        # --- The poller Lambda ---
        # Each run adds a log stream to CloudWatch
        poller_logs = logs.LogGroup(
            self,
            "PollerLogs",
            log_group_name="/aws/lambda/job-alerts-poller",
            retention=logs.RetentionDays.ONE_MONTH,  # old logs auto-delete
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        self.poller = lambda_.Function(
            self,
            "Poller",
            function_name="job-alerts-poller",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="jobalerts.handler.poll",
            code=code,
            timeout=cdk.Duration.minutes(10),
            memory_size=512,
            log_group=poller_logs,
            environment={
                "BEDROCK_MODEL_ID": ENV["BEDROCK_MODEL_ID"],
                "LLM_LIMIT": "25",  # max LLM calls per run (cost safety)
            },
        )

        # --- Permissions (exactly what the poller needs) ---
        for table in (self.seen_keys, self.seen_fingerprints, self.decisions):
            table.grant_read_write_data(self.poller)
        self.poller.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/job-alerts/*"],
        ))
        self.poller.add_to_role_policy(iam.PolicyStatement(
            actions=["kms:Decrypt"],  # to decrypt SecureString secrets
            resources=["*"],
            conditions={"StringEquals": {"kms:ViaService": f"ssm.{self.region}.amazonaws.com"}},
        ))
        self.poller.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/*",
                f"arn:aws:bedrock:*:{self.account}:inference-profile/*",
            ],
        ))

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
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )