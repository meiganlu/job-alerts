"""Reads settings from the .env file."""
import os

from dotenv import load_dotenv

load_dotenv()

CHANNELS = {
    "apply_now": "DISCORD_WEBHOOK_APPLY_NOW",
    "maybe": "DISCORD_WEBHOOK_MAYBE",
    "filtered_out": "DISCORD_WEBHOOK_FILTERED_OUT",
    "system_health": "DISCORD_WEBHOOK_SYSTEM_HEALTH",
}


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name} in .env")
    return value


def webhook_url(channel: str) -> str:
    return _require(CHANNELS[channel])


def role_id() -> str:
    return _require("DISCORD_ROLE_ID")


def aws_region() -> str:
    return os.getenv("AWS_REGION")


def bedrock_model_id() -> str:
    return _require("BEDROCK_MODEL_ID")