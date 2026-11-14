"""Entry point for AWS CDK: defines which stacks to deploy, and where."""
import aws_cdk as cdk

from infra.stack import JobAlertsStack

app = cdk.App()
JobAlertsStack(
    app,
    "JobAlertsStack",
    env=cdk.Environment(account="097881405631", region="us-west-2"),
)
app.synth()