"""Reads settings from the .env file."""
import os
import boto3

from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()

SSM_PREFIX = "/job-alerts/" # every secret is stored as /job-alerts/<NAME>
CHANNELS = {
    "apply_now": "DISCORD_WEBHOOK_APPLY_NOW",
    "maybe": "DISCORD_WEBHOOK_MAYBE",
    "filtered_out": "DISCORD_WEBHOOK_FILTERED_OUT",
    "system_health": "DISCORD_WEBHOOK_SYSTEM_HEALTH",
}


@lru_cache(maxsize=None)
def _from_ssm(name: str) -> str | None:
    """Reads one encrypted value from SSM Parameter Store, or None if it doesn't exist."""
    client = boto3.client("ssm", region_name=aws_region())
    try:
        response = client.get_parameter(Name=SSM_PREFIX + name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except client.exceptions.ParameterNotFound:
        return None


def _require(name: str) -> str:
    value = os.getenv(name) or _from_ssm(name)
    if not value:
        raise RuntimeError(f"Missing {name} in .env or SSM Parameter Store")
    return value


def webhook_url(channel: str) -> str:
    return _require(CHANNELS[channel])


def role_id() -> str:
    return _require("DISCORD_ROLE_ID")


def aws_region() -> str:
    return os.getenv("AWS_REGION")


def bedrock_model_id() -> str:
    return _require("BEDROCK_MODEL_ID")