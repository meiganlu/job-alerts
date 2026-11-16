"""Copies secrets from .env into AWS SSM Parameter Store (encrypted).
Run once now, and again whenever a value changes (e.g. a new webhook URL)."""
import os
import boto3

from jobalerts import config  # importing this also loads .env

SECRETS = [
    "DISCORD_WEBHOOK_APPLY_NOW",
    "DISCORD_WEBHOOK_MAYBE",
    "DISCORD_WEBHOOK_FILTERED_OUT",
    "DISCORD_WEBHOOK_SYSTEM_HEALTH",
    "DISCORD_ROLE_ID",
    "DISCORD_BOT_TOKEN",
]

client = boto3.client("ssm", region_name=config.aws_region())
for name in SECRETS:
    client.put_parameter(
        Name=config.SSM_PREFIX + name,
        Value=os.environ[name],
        Type="SecureString",  # encrypted at rest
        Overwrite=True,
    )
    print(f"Saved {config.SSM_PREFIX}{name}")