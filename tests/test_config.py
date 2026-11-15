import boto3
from moto import mock_aws

from jobalerts import config


def test_falls_back_to_ssm_when_not_in_env(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.delenv("DISCORD_WEBHOOK_MAYBE", raising=False)  # pretend we're on Lambda
    config._from_ssm.cache_clear()
    with mock_aws():
        boto3.client("ssm", region_name="us-west-2").put_parameter(
            Name="/job-alerts/DISCORD_WEBHOOK_MAYBE", Value="https://example.com/hook",
            Type="SecureString",
        )
        assert config.webhook_url("maybe") == "https://example.com/hook"
    config._from_ssm.cache_clear()


def test_env_value_wins(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_MAYBE", "https://local.example.com")
    assert config.webhook_url("maybe") == "https://local.example.com"