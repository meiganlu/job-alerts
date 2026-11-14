"""All AWS resources for the job-alert system."""
import aws_cdk as cdk
from constructs import Construct


class JobAlertsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        cdk.Tags.of(self).add("project", "job-alerts")
        # Resources get added here later: tables, Lambda, schedules.