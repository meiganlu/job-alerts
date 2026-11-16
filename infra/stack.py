"""All AWS resources for the job-alert system."""
import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_scheduler_targets as targets
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from constructs import Construct
from dotenv import dotenv_values

ENV = dotenv_values(".env")  # read non-secret settings like the model ID

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
        # Daily LLM call counter (the budget)
        self.usage = dynamodb.Table(
            self, "Usage",
            table_name="job-alerts-usage",
            partition_key=dynamodb.Attribute(name="counter_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # The company directory: ~10k boards to watch. On-demand billing because the
        # poller reads the whole table every 15 minutes
        self.companies = dynamodb.Table(
            self, "Companies",
            table_name="job-alerts-companies",
            partition_key=dynamodb.Attribute(name="company_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # --- The code bundle (shared by both Lambdas) ---
        self.code = lambda_.Code.from_asset(
            ".",
            exclude=[".venv", ".git", "cdk.out", "tests", "infra", "seen.db", ".env", "**/__pycache__"],
            bundling=cdk.BundlingOptions(
                image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                platform="linux/arm64",
                command=["bash", "-c", BUNDLE_COMMAND],
            ),
        )

        # --- Lambda 1: the poller (full pipeline) ---
        self.poller = self._function(
            "Poller", "job-alerts-poller", "jobalerts.handler.poll",
            timeout=cdk.Duration.minutes(10),
            environment={
                "BEDROCK_MODEL_ID": ENV["BEDROCK_MODEL_ID"],
                "LLM_LIMIT": "25",
                "DAILY_LLM_LIMIT": "50",
            },
        )
        for table in (self.seen_keys, self.seen_fingerprints, self.decisions, self.usage):
            table.grant_read_write_data(self.poller)
        self._grant_secrets(self.poller)
        self.poller.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/*",
                f"arn:aws:bedrock:*:{self.account}:inference-profile/*",
            ],
        ))

        # --- Lambda 2: the daily digest ---
        self.digest = self._function(
            "Digest", "job-alerts-digest", "jobalerts.handler.digest",
            timeout=cdk.Duration.minutes(1),
        )
        self.decisions.grant_read_data(self.digest)  # it only reads decisions
        self._grant_secrets(self.digest)

        # --- Schedules ---
        scheduler.Schedule(
            self, "PollEvery15Minutes",
            schedule=scheduler.ScheduleExpression.rate(cdk.Duration.minutes(15)),
            target=targets.LambdaInvoke(self.poller, retry_attempts=0),
            description="Check job boards every 15 minutes",
        )
        scheduler.Schedule(
            self, "DailyDigest",
            schedule=scheduler.ScheduleExpression.cron(
                minute="0", hour="7", time_zone=cdk.TimeZone.AMERICA_LOS_ANGELES,
            ),
            target=targets.LambdaInvoke(self.digest, retry_attempts=0),
            description="Post the daily digest at 7:00 AM Pacific",
        )

        # --- Alarms: email when something breaks ---
        alarm_topic = sns.Topic(self, "AlarmTopic", topic_name="job-alerts-alarms")
        alarm_topic.add_subscription(subscriptions.EmailSubscription(ENV["ALERT_EMAIL"]))
        email = cw_actions.SnsAction(alarm_topic)

        for function in (self.poller, self.digest):
            errors = function.metric_errors(period=cdk.Duration.minutes(15)).create_alarm(
                self, f"{function.node.id}Errors",
                threshold=1,
                evaluation_periods=1,
                alarm_description=f"{function.function_name} failed (crash or timeout)",
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            errors.add_alarm_action(email)

        not_running = self.poller.metric_invocations(period=cdk.Duration.hours(1)).create_alarm(
            self, "PollerNotRunning",
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=1,
            alarm_description="The poller hasn't run in the last hour",
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
        )
        not_running.add_alarm_action(email)
    
    # --- Helper functs ---

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

    def _function(self, construct_id: str, name: str, handler: str,
                  timeout: cdk.Duration, environment: dict | None = None) -> lambda_.Function:
        """A Lambda running our code bundle, with one month of logs and no automatic retries."""
        log_group = logs.LogGroup(
            self, f"{construct_id}Logs",
            log_group_name=f"/aws/lambda/{name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        return lambda_.Function(
            self, construct_id,
            function_name=name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler=handler,
            code=self.code,
            timeout=timeout,
            memory_size=512,
            log_group=log_group,
            environment=environment or {},
            retry_attempts=0,  # a failed run isn't repeated; the next scheduled run picks up
        )

    def _grant_secrets(self, function: lambda_.Function) -> None:
        """Lets a Lambda read and decrypt the /job-alerts/ secrets in SSM."""
        function.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/job-alerts/*"],
        ))
        function.add_to_role_policy(iam.PolicyStatement(
            actions=["kms:Decrypt"],
            resources=["*"],
            conditions={"StringEquals": {"kms:ViaService": f"ssm.{self.region}.amazonaws.com"}},
        ))